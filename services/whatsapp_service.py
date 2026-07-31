import httpx
from config import settings, clean_phone_number
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        self.api_url = settings.wasender_api_url
        self.token = settings.wasender_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def send_message(self, to: str, message: str) -> bool:
        """
        Sends a WhatsApp text message using WasenderAPI.
        """
        clean_to = clean_phone_number(to)
        if not clean_to:
            logger.error(f"Cannot send WhatsApp message: invalid recipient phone number '{to}'")
            return False

        digits_only = clean_to.lstrip("+")

        payload = {
            "to": digits_only,
            "phone": digits_only,
            "recipient": clean_to,
            "number": digits_only,
            "text": message,
            "message": message,
            "token": self.token
        }

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Sending WhatsApp response to {clean_to} (digits: {digits_only}) via WasenderAPI")
                response = await client.post(self.api_url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Message sent to {clean_to} successfully.")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False


whatsapp_service = WhatsAppService()