import uvicorn
import asyncio
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException, Header, Query
from config import settings, clean_phone_number
from models import (
    DocumentUploadResponse,
    DocumentListResponse,
    ConversationResponse
)
from services.chat_handler import chat_handler
from services.document_service import document_service
from database import supabase

logger = logging.getLogger(__name__)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(
    title="WhatsApp RAG Chatbot",
    description="Intelligent, production-ready WhatsApp Retrieval-Augmented Generation (RAG) chatbot API."
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "WhatsApp RAG Chatbot API is running"}


@app.get("/webhook")
def verify_webhook(
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    secret: Optional[str] = Query(None)
):
    provided_secret = x_webhook_signature or secret
    # Require 401 status code on webhook authentication failure
    if settings.wasender_webhook_secret:
        if not provided_secret or provided_secret != settings.wasender_webhook_secret:
            raise HTTPException(status_code=401, detail="Unauthorized webhook request: Invalid secret.")
    return {"status": "success", "message": "WhatsApp webhook endpoint is active"}

@app.post("/webhook")
async def receive_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    secret: Optional[str] = Query(None)
):
    provided_secret = x_webhook_signature or x_webhook_secret or secret
    # Require 401 status code on webhook authentication failure
    if settings.wasender_webhook_secret:
        if not provided_secret or provided_secret != settings.wasender_webhook_secret:
            raise HTTPException(status_code=401, detail="Unauthorized webhook request: Invalid signature or secret.")



    # Process webhook asynchronously in background task to return 200 OK immediately to WasenderAPI
    background_tasks.add_task(chat_handler.process_raw_webhook, payload)
    return {"status": "success", "message": "Webhook received"}

@app.post("/api/chat")
async def web_chat(payload: Dict[str, Any]):
    phone = payload.get("phone", "+919876543210")
    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message content is required.")
    
    clean_phone = clean_phone_number(phone) or "+919876543210"
    query = message[1:].strip() if message.startswith("@") else message.strip()
    
    from services.rag_service import rag_service
    from services.whatsapp_service import whatsapp_service
    
    bot_answer = await asyncio.to_thread(rag_service.generate_answer, query, clean_phone)
    
    # Save conversation log to Supabase
    await asyncio.to_thread(chat_handler._save_message, clean_phone, query, "user")
    await asyncio.to_thread(chat_handler._save_message, clean_phone, bot_answer, "bot")
    
    # Send the answer to the connected WhatsApp number via WasenderAPI
    await whatsapp_service.send_message(clean_phone, bot_answer)
    
    return {"status": "success", "phone": clean_phone, "query": query, "response": bot_answer}



MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB

@app.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "uploaded_document"
    lower_filename = filename.lower()
    
    # Check MIME type and file extension
    allowed = (
        file.content_type in ["application/pdf", "text/plain", "text/csv", "application/txt"]
        or lower_filename.endswith(".pdf")
        or lower_filename.endswith(".txt")
    )
    if not allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and TXT documents are allowed.")
    
    doc_id = str(uuid.uuid4())
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 2 GB.")


    try:
        supabase.table("documents").insert({
            "id": doc_id,
            "filename": filename,
            "status": "processing"
        }).execute()

        # Run heavy document ingestion in worker thread so event loop remains non-blocking
        mimetype = file.content_type or ("text/plain" if lower_filename.endswith(".txt") else "application/pdf")
        await asyncio.to_thread(
            document_service.process_and_ingest_document,
            doc_id,
            filename,
            content,
            mimetype
        )
        return DocumentUploadResponse(
            status="success",
            message=f"Document {filename} ingested successfully.",
            doc_id=doc_id
        )
    except Exception as e:
        logger.error(f"Error uploading document {filename}: {e}", exc_info=True)
        try:
            supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents", response_model=DocumentListResponse)
def list_documents():
    try:
        try:
            response = supabase.table("documents").select("*").order("uploaded_at", desc=True).execute()
        except Exception as err:
            logger.warning(f"Could not order documents by uploaded_at: {err}. Falling back to simple select.")
            response = supabase.table("documents").select("*").execute()
        return DocumentListResponse(status="success", documents=response.data or [])
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{phone}", response_model=ConversationResponse)
def get_user_conversations(phone: str):
    try:
        clean_phone = clean_phone_number(phone)
        if not clean_phone:
            raise HTTPException(status_code=400, detail=f"Invalid phone number provided: '{phone}'")
        
        response = supabase.table("conversations").select("*").eq("user_phone", clean_phone).order("created_at", desc=True).execute()
        return ConversationResponse(status="success", phone=clean_phone, conversations=response.data or [])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user conversations for {phone}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

