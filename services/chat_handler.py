from services.rag_service import rag_service
from services.whatsapp_service import whatsapp_service
from services.document_service import document_service
from database import supabase
from config import clean_phone_number
import logging
import asyncio
import httpx
import uuid
import urllib.parse

logger = logging.getLogger(__name__)

class ChatHandler:
    async def process_raw_webhook(self, payload: dict):
        try:
            logger.info(f"Received webhook payload event: {payload.get('event')}")
            
            data = payload.get("data", {})
            messages = []
            if isinstance(data, dict):
                if "messages" in data:
                    msgs = data["messages"]
                    if isinstance(msgs, list):
                        messages = msgs
                    elif isinstance(msgs, dict):
                        messages = [msgs]
                elif "key" in data or "message" in data or "messageBody" in data or "from" in data:
                    messages = [data]
            elif isinstance(data, list):
                messages = data
            elif "messages" in payload:
                msgs = payload["messages"]
                if isinstance(msgs, list):
                    messages = msgs
                elif isinstance(msgs, dict):
                    messages = [msgs]
            
            if not messages:
                logger.info(f"No messages found in webhook payload event: {payload.get('event')}")
                return

            for msg in messages:
                if not isinstance(msg, dict):
                    continue

                key = msg.get("key", {})
                if not isinstance(key, dict):
                    key = {}

                # Debug log full message payload and key object for diagnostic tracking
                logger.debug(f"Processing incoming WhatsApp message dict: msg={msg}, key={key}")

                # Skip messages sent by ourselves
                if key.get("fromMe", False):
                    continue

                # In 1:1 direct chats, key.remoteJid (or msg.from) is the authoritative conversation JID.
                # Check for group chats (@g.us) or broadcast channels (@broadcast)
                remote_jid = str(key.get("remoteJid") or msg.get("from") or msg.get("from_number") or "")
                
                if "@g.us" in remote_jid or "@broadcast" in remote_jid:
                    # In group chats, participant identifies the sender while remoteJid is the group
                    participant = str(key.get("participant") or "")
                    logger.info(f"Skipping non-direct chat message from group/broadcast JID: '{remote_jid}' (participant: '{participant}')")
                    continue

                # For 1:1 direct chats, remoteJid is the user's phone number JID
                raw_phone = remote_jid or str(key.get("participant") or "")
                user_phone = clean_phone_number(raw_phone)
                
                if not user_phone:
                    logger.warning(f"Could not extract valid phone number from message key={key}")
                    continue

                # Get message content object
                message_content = msg.get("message", {})
                if not isinstance(message_content, dict):
                    message_content = {}

                # Check if message contains a document attachment (defensive check for null values)
                document_msg = message_content.get("documentMessage")
                if not isinstance(document_msg, dict):
                    document_msg = {}

                media_url = (
                    msg.get("mediaUrl")
                    or document_msg.get("url")
                    or message_content.get("mediaUrl")
                )

                if media_url:
                    filename = (
                        msg.get("fileName")
                        or document_msg.get("title")
                        or document_msg.get("fileName")
                        or "whatsapp_doc.pdf"
                    )
                    mimetype = (
                        msg.get("mimetype")
                        or document_msg.get("mimetype")
                    )
                    # Auto-detect mime if missing or default
                    if not mimetype or mimetype == "application/octet-stream":
                        if filename.lower().endswith(".txt"):
                            mimetype = "text/plain"
                        else:
                            mimetype = "application/pdf"

                    logger.info(f"Routing document upload for user_phone='{user_phone}' from key={key}")
                    await self._handle_whatsapp_document(user_phone, media_url, filename, mimetype)
                    continue

                # Get actual text content
                user_message = (
                    msg.get("messageBody")
                    or message_content.get("conversation")
                    or message_content.get("extendedTextMessage", {}).get("text")
                    or msg.get("text")
                    or msg.get("body")
                )

                if not user_message:
                    continue

                user_message = user_message.strip()
                if not user_message.startswith("@"):
                    logger.info(f"Skipping message from {user_phone} (does not start with '@'): {user_message}")
                    continue

                # Remove the leading '@' symbol and whitespace
                cleaned_query = user_message[1:].strip()
                if not cleaned_query:
                    continue

                logger.info(f"Routing trigger query for user_phone='{user_phone}' derived from key={key}: '{cleaned_query}'")
                await self._handle_single_message(user_phone, cleaned_query)


        except Exception as e:
            logger.error(f"Error processing raw webhook: {e}", exc_info=True)

    async def _handle_whatsapp_document(self, user_phone: str, media_url: str, filename: str, mimetype: str):
        try:
            # Validate media_url domain against allowlist to prevent SSRF attacks
            parsed_url = urllib.parse.urlparse(media_url)
            if parsed_url.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme '{parsed_url.scheme}' in media_url")
            
            hostname = (parsed_url.hostname or "").lower()
            allowed_domains = ["wasenderapi.com", "www.wasenderapi.com", "api.wasenderapi.com", "cdn.wasenderapi.com", "s3.amazonaws.com"]
            if not any(hostname == d or hostname.endswith("." + d) for d in allowed_domains):
                raise ValueError(f"SSRF Prevention: Media URL hostname '{hostname}' is not in the allowed domain list.")

            logger.info(f"Downloading WhatsApp document for {user_phone}: {filename} from {media_url}")
            async with httpx.AsyncClient() as client:
                resp = await client.get(media_url, timeout=30.0)
                resp.raise_for_status()
                file_content = resp.content

            doc_id = str(uuid.uuid4())
            
            # Save document entry to Supabase
            supabase.table("documents").insert({
                "id": doc_id,
                "filename": filename,
                "status": "processing"
            }).execute()

            # Process and ingest document into Pinecone
            await asyncio.to_thread(
                document_service.process_and_ingest_document,
                doc_id, filename, file_content, mimetype
            )

            reply_msg = f"📄 Document '{filename}' received and ingested successfully into knowledge base! You can now ask questions using @"
            await whatsapp_service.send_message(user_phone, reply_msg)
        except Exception as e:
            logger.error(f"Error handling WhatsApp document upload: {e}", exc_info=True)
            error_msg = f"Sorry, there was an issue processing your document '{filename}'."
            await whatsapp_service.send_message(user_phone, error_msg)

    async def _handle_single_message(self, user_phone: str, user_message: str):
        try:
            # 1. Get answer from RAG before saving current message to Supabase history to prevent duplicate prompt context
            bot_answer = await asyncio.to_thread(rag_service.generate_answer, user_message, user_phone)

            # 2. Save user message to Supabase
            await asyncio.to_thread(self._save_message, user_phone, user_message, "user")

            # 3. Check for escalation
            is_escalated = self._needs_escalation(bot_answer)

            if is_escalated:
                await asyncio.to_thread(self._flag_escalation, user_phone, user_message)

            # 4. Save bot message to Supabase
            await asyncio.to_thread(self._save_message, user_phone, bot_answer, "bot")

            # 5. Send message via WhatsApp
            await whatsapp_service.send_message(user_phone, bot_answer)
        except Exception as e:
            logger.error(f"Error handling message for {user_phone}: {e}", exc_info=True)
            fallback_msg = "Sorry, I encountered an issue processing your message. Please try again or speak to a staff member."
            await whatsapp_service.send_message(user_phone, fallback_msg)


    def _save_message(self, phone: str, message: str, sender: str):
        try:
            supabase.table("conversations").insert({
                "user_phone": phone,
                "message": message,
                "sender": sender
            }).execute()
        except Exception as e:
            logger.error(f"Error saving message: {e}")

    def _needs_escalation(self, answer: str) -> bool:
        escalation_phrases = [
            # English phrases
            "do not have that information",
            "don't have that information",
            "cannot answer that",
            "speak to a staff member",
            "no information in my knowledge base",
            "not available in the documents",
            "contact staff",

            # Telugu phrases
            "సమాచారం లేదు",
            "సంప్రదించండి",
            "లభ్యం కాలేదు",
            "వివరాలు లేవు",
            "సమాచారం అందుబాటులో లేదు"
        ]
        answer_lower = answer.lower()
        return any(phrase in answer_lower or phrase in answer for phrase in escalation_phrases)

    def _flag_escalation(self, phone: str, message: str):
        try:
            supabase.table("logs").insert({
                "type": "escalation",
                "user_phone": phone,
                "details": {"original_message": message}
            }).execute()
            logger.warning(f"Escalation flagged for {phone}")
        except Exception as e:
            logger.error(f"Error flagging escalation: {e}")

chat_handler = ChatHandler()

