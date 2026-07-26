import httpx
from config import settings
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
        # Ensure phone number has a '+' prefix, as WasenderAPI expects
        if not to.startswith("+"):
            to = f"+{to}"

        payload = {
            "to": to,
            "text": message
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Message sent to {to} successfully.")
                return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

whatsapp_service = WhatsAppService()