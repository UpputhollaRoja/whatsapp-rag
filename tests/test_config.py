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
    # E.164 boundary tests (must be between 8 and 15 digits)
    assert clean_phone_number("1234567") == ""  # 7 digits -> invalid
    assert clean_phone_number("12345678") == "+12345678"  # 8 digits -> valid
    assert clean_phone_number("1234567890123456") == ""  # 16 digits -> invalid

def test_settings_initialization():
    s = Settings()
    assert bool(s.nvidia_model)
    assert bool(s.nvidia_embed_model)
    assert s.pinecone_index_name == "whatsapp-rag-index"
