import os
import hmac
import uuid
import tempfile
import logging
import asyncio
import uvicorn
from typing import Dict, Any, Optional

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

app = FastAPI(
    title="WhatsApp RAG Chatbot",
    description="Intelligent, production-ready WhatsApp Retrieval-Augmented Generation (RAG) chatbot API."
)

# Configure CORS Middleware
allowed_origins_list = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

def verify_internal_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None)
):
    """
    Enforces API key authentication if settings.internal_api_key is configured.
    Uses constant-time comparison via hmac.compare_digest.
    """
    expected_key = settings.internal_api_key
    if expected_key:
        provided_key = x_api_key or api_key
        if not provided_key or not hmac.compare_digest(provided_key, expected_key):
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing X-API-Key.")

def verify_webhook_secret(
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    secret: Optional[str] = Query(None)
):
    """
    Enforces webhook secret authentication using constant-time comparison via hmac.compare_digest.
    """
    expected_secret = settings.wasender_webhook_secret
    if expected_secret:
        provided_secret = x_webhook_signature or x_webhook_secret or secret
        if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
            raise HTTPException(status_code=401, detail="Unauthorized webhook request: Invalid signature or secret.")

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
    verify_webhook_secret(x_webhook_signature=x_webhook_signature, secret=secret)
    return {"status": "success", "message": "WhatsApp webhook endpoint is active"}

@app.post("/webhook")
async def receive_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    secret: Optional[str] = Query(None)
):
    verify_webhook_secret(
        x_webhook_signature=x_webhook_signature,
        x_webhook_secret=x_webhook_secret,
        secret=secret
    )

    # Process webhook asynchronously in background task to return 200 OK immediately to WasenderAPI
    background_tasks.add_task(chat_handler.process_raw_webhook, payload)
    return {"status": "success", "message": "Webhook received"}

@app.post("/api/chat", dependencies=[Depends(verify_internal_api_key)])
async def web_chat(payload: Dict[str, Any]):
    phone = payload.get("phone")
    if not phone or not str(phone).strip():
        raise HTTPException(status_code=400, detail="Phone number is required.")

    clean_phone = clean_phone_number(phone)
    if not clean_phone:
        raise HTTPException(status_code=400, detail=f"Invalid phone number provided: '{phone}'")

    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message content is required.")

    query = message[1:].strip() if message.startswith("@") else message.strip()

    from services.rag_service import rag_service

    bot_answer = await asyncio.to_thread(rag_service.generate_answer, query, clean_phone)

    # Save conversation log to Supabase
    await asyncio.to_thread(chat_handler._save_message, clean_phone, query, "user")
    await asyncio.to_thread(chat_handler._save_message, clean_phone, bot_answer, "bot")

    # Check escalation requirement and log unanswerable queries to Supabase logs table
    if chat_handler._needs_escalation(bot_answer):
        await asyncio.to_thread(chat_handler._flag_escalation, clean_phone, query)

    return {"status": "success", "phone": clean_phone, "query": query, "response": bot_answer}


MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit

@app.post("/api/documents/upload", response_model=DocumentUploadResponse, dependencies=[Depends(verify_internal_api_key)])
async def upload_document(file: UploadFile = File(...)):
    filename = file.filename or "uploaded_document"
    lower_filename = filename.lower()

    allowed_extensions = (".pdf", ".txt")
    disallowed_extensions = (".exe", ".dll", ".bin", ".sh", ".bat", ".cmd", ".msi", ".dmg")

    if any(lower_filename.endswith(ext) for ext in disallowed_extensions):
        raise HTTPException(status_code=400, detail="Unsupported file type. Executables and binary files are not allowed.")

    content_type = file.content_type or ""  # avoid AttributeError when header is missing
    allowed = (
        content_type in ["application/pdf", "text/plain"]
        or any(lower_filename.endswith(ext) for ext in allowed_extensions)
    )
    if not allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a PDF or TXT document.")

    doc_id = str(uuid.uuid4())

    # Memory-safe disk streaming upload check (streams chunks to temporary file on disk)
    total_bytes = 0
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            while chunk := await file.read(1024 * 1024):  # 1 MB chunk
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 50 MB.")
                tmp.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        with open(tmp_path, "rb") as f:
            content = f.read()

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

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
    except ValueError as ve:
        logger.warning(f"Validation error uploading document {filename}: {ve}")
        try:
            supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error uploading document {filename}: {e}", exc_info=True)
        try:
            supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents", response_model=DocumentListResponse, dependencies=[Depends(verify_internal_api_key)])
def list_documents():
    try:
        try:
            response = supabase.table("documents").select("*").order("uploaded_at", desc=True).execute()
        except Exception as err:
            logger.warning(f"Could not order documents by uploaded_at: {err}. Falling back to simple select.")
            response = supabase.table("documents").select("*").execute()
        # pyrefly: ignore [bad-argument-type]
        return DocumentListResponse(status="success", documents=response.data or [])
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{phone}", response_model=ConversationResponse, dependencies=[Depends(verify_internal_api_key)])
def get_user_conversations(
    phone: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    try:
        clean_phone = clean_phone_number(phone)
        if not clean_phone:
            raise HTTPException(status_code=400, detail=f"Invalid phone number provided: '{phone}'")

        response = (
            supabase.table("conversations")
            .select("*")
            .eq("user_phone", clean_phone)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return ConversationResponse(status="success", phone=clean_phone, conversations=response.data or [])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user conversations for {phone}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
