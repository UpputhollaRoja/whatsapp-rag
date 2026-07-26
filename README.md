# AI-Powered WhatsApp Chatbot System Using RAG

An intelligent, production-ready WhatsApp Retrieval-Augmented Generation (RAG) chatbot designed for educational institutes, customer support, and automated knowledge base assistance. Built with **FastAPI**, **WasenderAPI**, **Pinecone Vector DB**, **NVIDIA AI Models**, and **Supabase**.

---

## 🌟 Key Features

- **📱 WhatsApp Integration**: Real-time message sending and receiving via **WasenderAPI** with instant async webhook handling (<400ms acknowledgment).
- **📄 Dual Document Ingestion**: 
  - **Direct WhatsApp Attachment**: Send any PDF or TXT file directly in a WhatsApp chat to instantly ingest it into the knowledge base.
  - **REST API / Swagger UI**: Ingest documents via `POST /api/documents/upload`.
- **🔍 Semantic Vector Search**: High-dimensional vector embeddings powered by NVIDIA (`nvidia/nv-embed-v1`) and indexed in **Pinecone Vector DB**.
- **🗣️ Bilingual AI Agent (English & Telugu)**:
  - Automatic language detection for English and Telugu (both Telugu script like `రాముడు ఎవరు?` and transliterated Telugu like `Ramudu evaru?`).
  - Seamless translation of English document context into fluent, natural Telugu when requested.
- **💬 Human Conversational Persona**: Answers in warm, smooth paragraphs like a real human assistant on WhatsApp—no robotic bullet points or stiff markdown headers.
- **⚡ Trigger Symbol Protection**: Requires leading `@` prefix (e.g., `@who is rama`) to prevent accidental auto-replies during normal personal chat.
- **📊 User Session Tracking & History**: Tracks conversation history per phone number in **Supabase** database with dedicated management API endpoints.
- **⚠️ Human Escalation Logging**: Automatically flags unanswerable queries or staff request triggers into a Supabase escalation log table.

---

## 🏗️ System Architecture

```text
[WhatsApp User / Phone]
          │
          ▼
   [WasenderAPI Webhook]
          │ (POST /webhook)
          ▼
[FastAPI Server (main.py)] ── (Asynchronous Background Task)
          │
          ├──► [Supabase DB] (Session History & Escalation Logs)
          │
          ├──► [NVIDIA Embeddings (nv-embed-v1)]
          │         │
          │         ▼
          ├──► [Pinecone Vector DB (whatsapp-rag-index)] ── (Semantic Context)
          │         │
          │         ▼
          └──► [NVIDIA LLM (Nemotron-3-550B)] ──► [WasenderAPI] ──► [WhatsApp User Reply]
```

---

## 🛠️ Key Technologies & Stack

| Component | Technology / Platform |
| :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.13) |
| **WhatsApp Gateway** | [WasenderAPI](https://www.wasenderapi.com/) |
| **Vector Database** | [Pinecone](https://www.pinecone.io/) (`whatsapp-rag-index`) |
| **Embeddings & LLM** | NVIDIA NIM API (`nvidia/nv-embed-v1`, `nvidia/nemotron-3-ultra-550b-a55b`) |
| **Database & Auth** | [Supabase](https://supabase.com/) PostgreSQL (`documents`, `conversations`, `logs`) |
| **Tunnel / Webhook** | [ngrok](https://ngrok.com/) |

---

## 📁 Repository Structure

```text
.
├── main.py                     # FastAPI application entry point & API routes
├── config.py                   # Pydantic environment configuration loader
├── database.py                 # Supabase client initialization
├── models.py                   # Pydantic data models for Webhooks & Documents
├── requirements.txt            # Python dependencies manifest
├── pyrightconfig.json          # Language server configuration
├── .gitignore                  # Git ignore rules for secrets and virtualenv
├── .env.example                # Environment variables template
└── services/
    ├── chat_handler.py         # Asynchronous WhatsApp webhook & payload parser
    ├── document_service.py     # PDF/TXT extraction, chunking & Pinecone ingestion
    ├── rag_service.py          # Vector retrieval & Bilingual LLM completion
    └── whatsapp_service.py     # WasenderAPI HTTP client integration
```

---

## 📡 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | API Root status check |
| `GET` | `/webhook` | WasenderAPI Webhook verification health check |
| `POST` | `/webhook` | Receives incoming WhatsApp messages & document attachments |
| `POST` | `/api/documents/upload` | Upload PDF or TXT files to ingest into Pinecone & Supabase |
| `GET` | `/api/documents` | List all ingested documents and their status |
| `GET` | `/api/conversations/{phone}` | Retrieve session conversation history for a specific phone number |

---

## 🚀 Setup & Installation Guide

### 1. Prerequisites
- Python 3.10+ installed
- Active accounts on **WasenderAPI**, **Pinecone**, **Supabase**, and **NVIDIA Developer/API Key**.

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/UpputhollaRoja/whatsapp-rag.git
cd whatsapp-rag

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory (refer to `.env.example`):

```env
NVIDIA_API_KEY="your_nvidia_api_key"
NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL="nvidia/nemotron-3-ultra-550b-a55b"

PINECONE_API_KEY="your_pinecone_api_key"
PINECONE_INDEX_NAME="whatsapp-rag-index"

SUPABASE_URL="https://your-supabase-id.supabase.co"
SUPABASE_KEY="your_supabase_service_role_key"

WASENDER_TOKEN="your_wasender_session_api_key"
WASENDER_API_URL="https://www.wasenderapi.com/api/send-message"
WASENDER_WEBHOOK_SECRET="your_wasender_webhook_secret"
```

### 4. Database Setup (Supabase)
Create the following 3 tables in your Supabase project:
- **`documents`**: `id` (text/uuid), `filename` (text), `status` (text), `uploaded_at` (timestamp)
- **`conversations`**: `id` (uuid), `user_phone` (text), `message` (text), `sender` (text), `created_at` (timestamp)
- **`logs`**: `id` (uuid), `type` (text), `user_phone` (text), `details` (jsonb), `created_at` (timestamp)

### 5. Running the Application
```bash
# Start FastAPI application with Uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Expose Webhook via ngrok
```bash
ngrok http 8000 --url=https://your-custom-ngrok-domain.ngrok-free.dev
```

In your **WasenderAPI Dashboard** (`https://www.wasenderapi.com`), set **Payload URL** to:
`https://your-custom-ngrok-domain.ngrok-free.dev/webhook` and enable `messages.received` events.

---

## 💬 Usage Examples

### 1. Direct Document Upload on WhatsApp
Attach and send any PDF or TXT file to your WhatsApp bot line. The bot will automatically download, chunk, generate embeddings, index the file into Pinecone, and reply with confirmation:
> 📄 *Document 'admission_policy.pdf' received and ingested successfully into knowledge base! You can now ask questions using @*

### 2. Asking Questions (English)
Send `@who is rama` to your bot:
> *Rama, also known as Ramachandra, is one of the most beloved figures in Hinduism—he's the seventh avatar of Lord Vishnu, born as the prince of Ayodhya to King Dasharatha and Queen Kausalya...*

### 3. Asking Questions (Telugu)
Send `@రాముడు ఎవరు?` or `@who is rama in telugu` to your bot:
> *రాముడు అంటే హిందూ ధర్మంలో అత్యంత ముఖ్యమైన దేవతలలో ఒకరు, శ్రీమన్నారాయణుడి ఏడవ అవతారం. అయోధ్య రాజైన దశరథుడు మరియు కౌసల్యాదేవిల పుత్రుడు. సీతాదేవి వారి భార్య...*

---

## 📜 License
Distributed under the MIT License.
