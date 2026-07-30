from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class MessageKey(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    fromMe: bool = False
    remoteJid: Optional[str] = None
    senderPn: Optional[str] = None
    cleanedSenderPn: Optional[str] = None
    senderLid: Optional[str] = None
    addressingMode: Optional[str] = None
    participant: Optional[str] = None


class DocumentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url: Optional[str] = None
    mimetype: Optional[str] = None
    title: Optional[str] = None
    fileName: Optional[str] = None


class ExtendedTextMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: Optional[str] = None


class MessageContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation: Optional[str] = None
    documentMessage: Optional[DocumentMessage] = None
    extendedTextMessage: Optional[ExtendedTextMessage] = None
    mediaUrl: Optional[str] = None


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    key: Optional[MessageKey] = None
    messageBody: Optional[str] = None
    message: Optional[MessageContent] = None
    mediaUrl: Optional[str] = None
    fileName: Optional[str] = None
    mimetype: Optional[str] = None
    from_number: Optional[str] = None


class WebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")
    messages: Optional[List[WhatsAppMessage]] = None


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event: str
    timestamp: Optional[int] = None
    data: Optional[WebhookData] = None


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    filename: str
    uploaded_at: Optional[datetime] = None
    status: str


class DocumentUploadResponse(BaseModel):
    status: str
    message: str
    doc_id: str


class DocumentListResponse(BaseModel):
    status: str
    documents: List[Dict[str, Any]]


class ConversationResponse(BaseModel):
    status: str
    phone: str
    conversations: List[Dict[str, Any]]