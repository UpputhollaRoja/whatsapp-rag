from supabase import create_client, Client
from config import settings

def get_supabase_client() -> Client:
    url: str = settings.supabase_url
    key: str = settings.supabase_key
    return create_client(url, key)

supabase = get_supabase_client()
