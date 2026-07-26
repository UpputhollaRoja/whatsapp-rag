from models import WebhookPayload
from services.rag_service import rag_service
from services.whatsapp_service import whatsapp_service
from services.document_service import document_service
from database import supabase
import logging
import asyncio
import httpx
import uuid

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

                # Skip messages sent by ourselves
                if key.get("fromMe", False):
                    continue

                # Get phone number
                user_phone = (
                    key.get("cleanedSenderPn")
                    or key.get("senderPn")
                    or key.get("participant")
                    or key.get("remoteJid", "")
                    or msg.get("from", "")
                )
                
                # Strip @s.whatsapp.net or @c.us if present
                if "@" in user_phone:
                    user_phone = user_phone.split("@")[0]
                
                # Clean phone number digits
                user_phone = "".join(filter(str.isdigit, user_phone))
                if user_phone and not user_phone.startswith("+"):
                    user_phone = f"+{user_phone}"

                if not user_phone or user_phone == "+":
                    continue

                # Get message content object
                message_content = msg.get("message", {})
                if not isinstance(message_content, dict):
                    message_content = {}

                # Check if message contains a document attachment
                document_msg = message_content.get("documentMessage", {})
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
                        or "application/pdf"
                    )
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

                logger.info(f"Processing trigger message from {user_phone}: {cleaned_query}")
                await self._handle_single_message(user_phone, cleaned_query)

        except Exception as e:
            logger.error(f"Error processing raw webhook: {e}", exc_info=True)

    async def _handle_whatsapp_document(self, user_phone: str, media_url: str, filename: str, mimetype: str):
        try:
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

    async def process_webhook(self, payload: WebhookPayload):
        try:
            if not payload.data or not payload.data.messages:
                logger.info(f"Received non-message webhook event: {payload.event}")
                return

            # A single webhook call can contain multiple messages — loop through all of them
            for msg in payload.data.messages:

                # Skip messages that WE sent (our own bot replies) to avoid reply loops
                if msg.key.fromMe:
                    continue

                # Get the sender's phone number
                user_phone = msg.key.cleanedSenderPn or msg.key.remoteJid

                # Get the actual text — prefer messageBody, fall back to message.conversation
                user_message = msg.messageBody or (msg.message.conversation if msg.message else None)

                # Skip if there's no usable text (e.g., image/audio messages for now)
                if not user_message:
                    continue

                user_message = user_message.strip()
                if not user_message.startswith("@"):
                    logger.info(f"Skipping message from {user_phone} (does not start with '@'): {user_message}")
                    continue

                cleaned_query = user_message[1:].strip()
                if not cleaned_query:
                    continue

                await self._handle_single_message(user_phone, cleaned_query)
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)

    async def _handle_single_message(self, user_phone: str, user_message: str):
        # 1. Save user message to Supabase
        await asyncio.to_thread(self._save_message, user_phone, user_message, "user")

        # 2. Get answer from RAG
        bot_answer = await asyncio.to_thread(rag_service.generate_answer, user_message, user_phone)

        # 3. Check for escalation
        is_escalated = self._needs_escalation(bot_answer)

        if is_escalated:
            await asyncio.to_thread(self._flag_escalation, user_phone, user_message)

        # 4. Save bot message to Supabase
        await asyncio.to_thread(self._save_message, user_phone, bot_answer, "bot")

        # 5. Send message via WhatsApp
        await whatsapp_service.send_message(user_phone, bot_answer)

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
            "do not have that information",
            "don't have that information",
            "cannot answer that",
            "speak to a staff member"
        ]
        answer_lower = answer.lower()
        return any(phrase in answer_lower for phrase in escalation_phrases)

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
