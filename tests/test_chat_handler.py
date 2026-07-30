import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from services.chat_handler import chat_handler

def test_needs_escalation_english():
    assert chat_handler._needs_escalation("I do not have that information in my knowledge base.") is True
    assert chat_handler._needs_escalation("Please speak to a staff member for assistance.") is True
    assert chat_handler._needs_escalation("Lord Rama is the seventh avatar of Lord Vishnu.") is False

def test_needs_escalation_telugu():
    assert chat_handler._needs_escalation("నా వద్ద ఆ సమాచారం లేదు. దయచేసి సిబ్బందిని సంప్రదించండి.") is True
    assert chat_handler._needs_escalation("సమాచారం లేదు") is True
    assert chat_handler._needs_escalation("శ్రీరాముడు అయోధ్యాధిపతి మరియు విష్ణుమూర్తి ఏడవ అవతారము.") is False

def test_process_raw_webhook_ignores_group_chats():
    async def _test():
        payload = {
            "event": "messages.received",
            "data": {
                "key": {
                    "remoteJid": "1234567890-1612345@g.us",
                    "fromMe": False
                },
                "messageBody": "@hello"
            }
        }
        with patch.object(chat_handler, "_handle_single_message", new_callable=AsyncMock) as mock_handle:
            await chat_handler.process_raw_webhook(payload)
            mock_handle.assert_not_called()
    asyncio.run(_test())

def test_process_raw_webhook_ignores_messages_without_at_prefix():
    async def _test():
        payload = {
            "event": "messages.received",
            "data": {
                "key": {
                    "remoteJid": "919876543210@s.whatsapp.net",
                    "fromMe": False
                },
                "messageBody": "hello bot"
            }
        }
        with patch.object(chat_handler, "_handle_single_message", new_callable=AsyncMock) as mock_handle:
            await chat_handler.process_raw_webhook(payload)
            mock_handle.assert_not_called()
    asyncio.run(_test())

def test_process_raw_webhook_triggers_on_at_prefix():
    async def _test():
        payload = {
            "event": "messages.received",
            "data": {
                "key": {
                    "remoteJid": "919876543210@s.whatsapp.net",
                    "fromMe": False
                },
                "messageBody": "@who is rama"
            }
        }
        with patch.object(chat_handler, "_handle_single_message", new_callable=AsyncMock) as mock_handle:
            await chat_handler.process_raw_webhook(payload)
            mock_handle.assert_called_once_with("+919876543210", "who is rama")
    asyncio.run(_test())


