import pytest
from config import clean_phone_number, Settings

def test_clean_phone_number():
    assert clean_phone_number("1234567890") == "+1234567890"
    assert clean_phone_number("+1234567890") == "+1234567890"
    assert clean_phone_number("1234567890@s.whatsapp.net") == "+1234567890"
    assert clean_phone_number("1234567890@c.us") == "+1234567890"
    assert clean_phone_number("+91 98765-43210") == "+919876543210"
    assert clean_phone_number("") == ""
    assert clean_phone_number("invalid_string_no_digits") == ""

def test_settings_initialization():
    s = Settings()
    assert s.nvidia_model == "nvidia/nemotron-3-ultra-550b-a55b"
    assert s.pinecone_index_name == "whatsapp-rag-index"
