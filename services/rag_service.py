from typing import List, Dict
from openai import OpenAI
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
        try:
            response = self.openai_client.embeddings.create(
                input=query,
                model="nvidia/nv-embed-v1"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            raise e

    def search_documents(self, query_embedding: List[float], top_k: int = 5, min_score: float = 0.25) -> str:
        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            contexts = []
            if results and results.matches:
                for match in results.matches:
                    # Filter matches by relevance similarity threshold
                    score = getattr(match, "score", 1.0)
                    if score is not None and score < min_score:
                        continue
                    if match.metadata and 'text' in match.metadata:
                        contexts.append(match.metadata['text'])
            
            return "\n\n---\n\n".join(contexts)

        except Exception as e:
            logger.error(f"Error searching Pinecone documents: {e}")
            return ""


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
            if response and response.data:
                # Reversing to chronological order
                for row in reversed(response.data):
                    role = "user" if row["sender"] == "user" else "assistant"
                    history.append({"role": role, "content": row["message"]})
                
            return history
        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            return []

    def generate_answer(self, query: str, user_phone: str) -> str:
        try:
            query_embedding = self.get_query_embedding(query)
            context = self.search_documents(query_embedding)
            
            history = self.get_conversation_history(user_phone)
            
            context_str = context.strip() if context else "No relevant documents found."

            system_prompt = (
                "You are a friendly, warm, and helpful bilingual AI assistant fluent in English and Telugu (తెలుగు).\n"
                "LANGUAGE SELECTION RULES:\n"
                "1. IF the user requests the answer in Telugu (e.g. 'in telugu', 'telugu lo', 'telugu', or asks in Telugu script/language like 'రాముడు ఎవరు?'), respond ENTIRELY in clear, natural, authentic Telugu (తెలుగు).\n"
                "2. Otherwise, if the user asks in English without requesting Telugu, respond in clear, warm English.\n\n"
                "FALLBACK & ESCALATION RULES:\n"
                "3. IF the retrieved context is empty, insufficient, or does not contain the answer, state clearly and politely: 'I do not have that information in my knowledge base. Please speak to a staff member for assistance.' (In Telugu: 'నా వద్ద ఆ సమాచారం లేదు. దయచేసి సిబ్బందిని సంప్రదించండి.').\n\n"
                "PERSONA & STYLE:\n"
                "- Write in a natural, smooth, conversational human voice suitable for WhatsApp.\n"
                "- Do NOT use robotic bullet points, numbered lists, or markdown headers.\n"
                "- Seamlessly translate or adapt the retrieved document context into the requested language.\n"
                "- When asked about a figure or topic, provide a complete, warm answer covering who they are, their lineage/parents, spouse, children, and key story/purpose based on the context.\n\n"
                f"Context:\n{context_str}"
            )
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": query})

            response = self.openai_client.chat.completions.create(
                model=settings.nvidia_model,
                messages=messages,
                temperature=0.7,
                top_p=0.9,
                max_tokens=1024,
                stream=False
            )

            return response.choices[0].message.content or "I do not have that information in my knowledge base."
        except Exception as e:
            logger.error(f"Error generating answer in RAGService: {e}")
            return "I am sorry, I am currently unable to process your request. Please try again later or speak to a staff member."

rag_service = RAGService()

