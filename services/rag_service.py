from typing import List, Dict
from openai import OpenAI
from pinecone import Pinecone
from config import settings
from database import supabase
import logging

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self._openai_client = None
        self._pc = None
        self._index = None

    @property
    def openai_client(self):
        if self._openai_client is None:
            self._openai_client = OpenAI(
                base_url=settings.nvidia_base_url,
                api_key=settings.nvidia_api_key
            )
        return self._openai_client

    @property
    def pc(self):
        if self._pc is None:
            self._pc = Pinecone(api_key=settings.pinecone_api_key)
        return self._pc

    @property
    def index(self):
        if self._index is None:
            self._index = self.pc.Index(settings.pinecone_index_name)
        return self._index


    def get_query_embedding(self, query: str) -> List[float]:
        try:
            response = self.openai_client.embeddings.create(
                input=query,
                model=settings.nvidia_embed_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting query embedding: {e}")
            raise e

    def search_documents(self, query_embedding: List[float], top_k: int = 5, min_score: float = 0.15) -> str:
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
                    # pyrefly: ignore [bad-index, unsupported-operation]
                    role = "user" if row["sender"] == "user" else "assistant"
                    # pyrefly: ignore [bad-index, unsupported-operation]
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
                "INSTRUCTIONS:\n"
                "- Answer the user's question using the provided Document Context as your primary knowledge source.\n"
                "- If the user asks for a summary or what information is available, provide a clear, engaging overview of the document context.\n"
                "- If the context discusses the event/person (e.g. Rama's exile, Kaikeyi's boons, Sita & Lakshmana following Rama to the forest) but does not state an exact specific numeric value requested (like numeric age), explain what the document specifies about the event.\n"
                "- ONLY if the retrieved context is completely empty or completely unrelated to the question, state: 'I do not have that information in my knowledge base. Please speak to a staff member for assistance.' (In Telugu: 'నా వద్ద ఆ సమాచారం లేదు. దయచేసి సిబ్బందిని సంప్రదించండి.').\n\n"
                "LANGUAGE SELECTION RULES:\n"
                "1. IF the user requests the answer in Telugu (e.g. 'in telugu', 'telugu lo', 'telugu', or asks in Telugu script/language like 'రాముడు ఎవరు?'), respond ENTIRELY in clear, natural, authentic Telugu (తెలుగు).\n"
                "2. Otherwise, if the user asks in English without requesting Telugu, respond in clear, warm English.\n\n"
                "PERSONA & STYLE:\n"
                "- Write in a natural, smooth, conversational human voice suitable for WhatsApp.\n"
                "- Do NOT use robotic bullet points, numbered lists, or markdown headers.\n\n"
                f"Document Context:\n{context_str}"
            )
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history)
            messages.append({"role": "user", "content": query})

            # pyrefly: ignore [no-matching-overload]
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

