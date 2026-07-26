# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    nvidia_api_key: str = "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"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"

    pinecone_api_key: str
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "whatsapp-rag-index"

    supabase_url: str
    supabase_key: str

    wasender_token: str
    wasender_api_url: str = "https://www.wasenderapi.com/api/send-message"
    wasender_webhook_secret: str = "a40d15265a49d82663d37e38ba794ea9"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()