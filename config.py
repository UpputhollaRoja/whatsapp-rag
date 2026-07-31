from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Required secrets with no fallback defaults to ensure fast failure if .env is missing key variables
    nvidia_api_key: str
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"

    pinecone_api_key: str
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "whatsapp-rag-index"

    supabase_url: str
    supabase_key: str

    wasender_token: str
    wasender_api_url: str = "https://www.wasenderapi.com/api/send-message"
    wasender_webhook_secret: str

    # Security & Server Settings
    internal_api_key: Optional[str] = None
    allowed_origins: str = "*"
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def clean_phone_number(phone: str) -> str:
    """
    Sanitizes phone number string into clean '+<digits>' format following E.164 standards (8-15 digits).
    Returns empty string if invalid or digit count is not between 8 and 15.
    """
    if not phone:
        return ""
    if "@" in phone:
        phone = phone.split("@")[0]
    digits = "".join(filter(str.isdigit, phone))
    if not (8 <= len(digits) <= 15):
        return ""
    return f"+{digits}"

settings = Settings()
