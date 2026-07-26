import uvicorn
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException
from config import settings
from models import WebhookPayload
from services.chat_handler import chat_handler
from services.document_service import document_service
from database import supabase
import uuid

app = FastAPI(title="WhatsApp RAG Chatbot")

@app.get("/")
def read_root():
    return {"message": "WhatsApp RAG Chatbot API is running"}

@app.get("/webhook")
def verify_webhook():
    return {"status": "success", "message": "WhatsApp webhook endpoint is active"}

from typing import Dict, Any

@app.post("/webhook")
async def receive_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    # Process webhook in background to return 200 OK immediately to WasenderAPI
    background_tasks.add_task(chat_handler.process_raw_webhook, payload)
    return {"status": "success", "message": "Webhook received"}

MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type not in ["application/pdf", "text/plain"]:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and TXT are allowed.")
    
    doc_id = str(uuid.uuid4())
    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum allowed size is 30 MB.")

    try:
        supabase.table("documents").insert({
            "id": doc_id,
            "filename": file.filename,
            "status": "processing"
        }).execute()

        document_service.process_and_ingest_document(
            doc_id=doc_id,
            filename=file.filename,
            file_content=content,
            mimetype=file.content_type
        )
        return {"status": "success", "message": f"Document {file.filename} ingested successfully.", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
def list_documents():
    try:
        response = supabase.table("documents").select("*").order("uploaded_at", desc=True).execute()
        return {"status": "success", "documents": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{phone}")
def get_user_conversations(phone: str):
    try:
        clean_phone = "".join(filter(str.isdigit, phone))
        if clean_phone and not clean_phone.startswith("+"):
            clean_phone = f"+{clean_phone}"
        response = supabase.table("conversations").select("*").eq("user_phone", clean_phone).order("created_at", desc=True).execute()
        return {"status": "success", "phone": clean_phone, "conversations": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
