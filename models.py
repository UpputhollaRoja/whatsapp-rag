from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class MessageKey(BaseModel):
    id: str
    fromMe: bool
    remoteJid: str
    senderPn: Optional[str] = None
    cleanedSenderPn: Optional[str] = None
    senderLid: Optional[str] = None
    addressingMode: Optional[str] = None


class MessageContent(BaseModel):
    conversation: Optional[str] = None


class WhatsAppMessage(BaseModel):
    key: MessageKey
    messageBody: Optional[str] = None
    message: Optional[MessageContent] = None


class WebhookData(BaseModel):
    messages: Optional[List[WhatsAppMessage]] = None


class WebhookPayload(BaseModel):
    event: str
    timestamp: Optional[int] = None
    data: Optional[WebhookData] = None


class DocumentMetadata(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    status: str