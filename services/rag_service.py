from typing import List, Dict
# pyrefly: ignore [missing-import]
from openai import OpenAI
# pyrefly: ignore [missing-import]
from pinecone import Pinecone
from config import settings
from database import supabase
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.openai_client = OpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key
        )
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.pc.Index(settings.pinecone_index_name)

    def get_query_embedding(self, query: str) -> List[float]:
        response = self.openai_client.embeddings.create(
            input=query,
            model="nvidia/nv-embed-v1"
        )
        return response.data[0].embedding

    def search_documents(self, query_embedding: List[float], top_k: int = 5) -> str:
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        
        contexts = []
        for match in results.matches:
            if match.metadata and 'text' in match.metadata:
                contexts.append(match.metadata['text'])
        
        return "\n\n---\n\n".join(contexts)

    def get_conversation_history(self, user_phone: str, limit: int = 5) -> List[Dict]:
        try:
            # Fetch last N messages from Supabase for context
            response = supabase.table("conversations")\
                .select("message, sender")\
                .eq("user_phone", user_phone)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            history = []
            # Reversing to chronological order
            for row in reversed(response.data):
                role = "user" if row["sender"] == "user" else "assistant"
                history.append({"role": role, "content": row["message"]})
                
            return history
        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            return []

    def generate_answer(self, query: str, user_phone: str) -> str:
        query_embedding = self.get_query_embedding(query)
        context = self.search_documents(query_embedding)
        
        history = self.get_conversation_history(user_phone)
        
        system_prompt = (
            "You are a friendly, warm, and helpful bilingual AI assistant fluent in English and Telugu (తెలుగు).\n"
            "LANGUAGE SELECTION RULES:\n"
            "1. IF the user requests the answer in Telugu (e.g. 'in telugu', 'telugu lo', 'telugu', or asks in Telugu script/language like 'రాముడు ఎవరు?'), respond ENTIRELY in clear, natural, authentic Telugu (తెలుగు).\n"
            "2. Otherwise, if the user asks in English without requesting Telugu, respond in clear, warm English.\n\n"
            "PERSONA & STYLE:\n"
            "- Write in a natural, smooth, conversational human voice suitable for WhatsApp.\n"
            "- Do NOT use robotic bullet points, numbered lists, or markdown headers.\n"
            "- Seamlessly translate or adapt the retrieved document context into the requested language.\n"
            "- When asked about a figure or topic, provide a complete, warm answer covering who they are, their lineage/parents, spouse, children, and key story/purpose.\n\n"
            f"Context:\n{context}"
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": query})

        response = self.openai_client.chat.completions.create(
            model=settings.nvidia_model,
            messages=messages,
            temperature=0.7,
            top_p=0.9,
            max_tokens=512,
            stream=False
        )

        return response.choices[0].message.content or ""

rag_service = RAGService()
