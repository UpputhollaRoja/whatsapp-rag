import os
from io import BytesIO
from typing import List
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pinecone import Pinecone
from config import settings
from database import supabase

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
        reader = PdfReader(BytesIO(file_content))
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
        return text

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        response = self.openai_client.embeddings.create(
            input=texts,
            model="nvidia/nv-embed-v1"
        )
        return [data.embedding for data in response.data]

    def process_and_ingest_document(self, doc_id: str, filename: str, file_content: bytes, mimetype: str):
        # 1. Extract text based on file type
        if mimetype == "application/pdf":
            text = self.extract_text_from_pdf(file_content)
        elif mimetype == "text/plain":
            text = file_content.decode("utf-8", errors="ignore")
        else:
            raise ValueError("Unsupported file type")
        
        # 2. Chunk text
        chunks = self.text_splitter.split_text(text)
        
        if not chunks:
            return

        # 3. Get embeddings
        embeddings = self.get_embeddings(chunks)
        
        # 4. Ingest into Pinecone
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
            
        self.index.upsert(vectors=vectors)
        
        # 5. Update Supabase
        supabase.table("documents").update({"status": "indexed"}).eq("id", doc_id).execute()

document_service = DocumentService()
