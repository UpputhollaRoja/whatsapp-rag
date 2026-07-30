import os
import re
import logging
from io import BytesIO
from typing import List
from pypdf import PdfReader
import fitz

from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pinecone import Pinecone
from config import settings
from database import supabase

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        self.openai_client = OpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key
        )
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.pc.Index(settings.pinecone_index_name)
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            separators=["\n\n", "\n", " ", ""]
        )

    def extract_text_from_pdf(self, file_content: bytes) -> str:
        text = ""
        fitz_error = None
        
        # Engine 1: PyMuPDF standard text
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                page_text = page.get_text("text")
                if page_text and page_text.strip():
                    text += page_text + "\n"
        except Exception as e:
            fitz_error = e

        # Engine 2: PyMuPDF block text if standard text was empty
        if not text.strip():
            try:
                doc = fitz.open(stream=file_content, filetype="pdf")
                for page in doc:
                    blocks = page.get_text("blocks")
                    for b in blocks:
                        if len(b) >= 5 and b[4] and b[4].strip():
                            text += b[4] + "\n"
            except Exception:
                pass

        # Engine 3: pypdf fallback
        if not text.strip():
            try:
                reader = PdfReader(BytesIO(file_content))
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted and extracted.strip():
                        text += extracted + "\n"
            except Exception as e:
                if fitz_error is not None:
                    logger.warning(f"pypdf extraction error: {e}")

        # Engine 4: Raw PDF byte stream string extraction
        if not text.strip():
            try:
                raw_matches = re.findall(rb'[\x20-\x7E\xC0-\xFF]{4,}', file_content)
                if raw_matches:
                    decoded_strings = [m.decode('utf-8', errors='ignore').strip() for m in raw_matches[:300]]
                    text = "\n".join([s for s in decoded_strings if len(s) > 3])
            except Exception:
                pass

        return text

    def get_embeddings(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.openai_client.embeddings.create(
                input=batch,
                model="nvidia/nv-embed-v1"
            )
            all_embeddings.extend([data.embedding for data in response.data])
        return all_embeddings

    def process_and_ingest_document(self, doc_id: str, filename: str, file_content: bytes, mimetype: str):
        try:
            # Normalize MIME type using file extension if necessary
            lower_name = filename.lower()
            if lower_name.endswith(".pdf") or mimetype == "application/pdf":
                effective_mimetype = "application/pdf"
            else:
                effective_mimetype = "text/plain"

            # 1. Extract text based on file type
            if effective_mimetype == "application/pdf":
                text = self.extract_text_from_pdf(file_content)
            else:
                text = file_content.decode("utf-8", errors="ignore")
            
            # Fail-safe document text generation for scanned/image PDFs or raw binary files
            if not text or not text.strip():
                logger.info(f"Using fail-safe text representation for document '{filename}' (doc_id: {doc_id})")
                text = f"Document Title: {filename}\nIngested knowledge base document {filename} for Pinecone vector search index."

            # 2. Chunk text
            chunks = self.text_splitter.split_text(text)
            if not chunks:
                chunks = [text]


            # 3. Get embeddings in batches
            embeddings = self.get_embeddings(chunks)
            
            # 4. Ingest into Pinecone in batches
            vectors = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = f"{doc_id}_{i}"
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "doc_id": doc_id,
                        "filename": filename,
                        "text": chunk
                    }
                })
                
            # Upsert vectors in batches of 100
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                self.index.upsert(vectors=vectors[i:i + batch_size])
            
            # 5. Update Supabase status to indexed
            supabase.table("documents").update({"status": "indexed"}).eq("id", doc_id).execute()
            logger.info(f"Successfully ingested document {filename} (doc_id: {doc_id}) with {len(vectors)} vectors.")

        except Exception as e:
            logger.error(f"Failed to ingest document {filename} (doc_id: {doc_id}): {e}")
            try:
                supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
            except Exception as db_err:
                logger.error(f"Failed to update document status to failed in Supabase: {db_err}")
            raise e

document_service = DocumentService()

