import os
import logging
from io import BytesIO
from typing import List
from pypdf import PdfReader

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
        try:
            reader = PdfReader(BytesIO(file_content))
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            return text
        except Exception as e:
            logger.error(f"Error reading PDF content: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

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
            elif lower_name.endswith(".txt") or mimetype in ["text/plain", "text/csv", "application/txt"]:
                effective_mimetype = "text/plain"
            else:
                effective_mimetype = mimetype

            # 1. Extract text based on file type
            if effective_mimetype == "application/pdf":
                text = self.extract_text_from_pdf(file_content)
            elif effective_mimetype == "text/plain":
                text = file_content.decode("utf-8", errors="ignore")
            else:
                raise ValueError(f"Unsupported file type: {mimetype} for file {filename}")
            
            if not text or not text.strip():
                logger.warning(f"No text extracted from document {filename} (doc_id: {doc_id})")
                supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
                raise ValueError("No readable text found in document.")

            # 2. Chunk text
            chunks = self.text_splitter.split_text(text)
            
            if not chunks:
                logger.warning(f"No text chunks created for document {filename} (doc_id: {doc_id})")
                supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
                raise ValueError("Document yielded zero text chunks.")

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

