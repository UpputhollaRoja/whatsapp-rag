// WhatsApp RAG Chatbot — React Frontend (CDN / Babel Standalone)
// All API calls, business logic, and UI behaviour preserved from the original vanilla JS version.

const { useState, useEffect, useRef, useCallback } = React;

// ─── Utility helpers ──────────────────────────────────────────────────────────

function escapeHtml(str) {
    return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ─── Toast Notification System ───────────────────────────────────────────────

function ToastContainer({ toasts }) {
    return (
        <div className="toast-container">
            {toasts.map(t => (
                <div key={t.id} className="toast" style={t.isError ? { borderColor: '#ef4444' } : {}}>
                    {t.msg}
                </div>
            ))}
        </div>
    );
}

function useToast() {
    const [toasts, setToasts] = useState([]);

    const showToast = useCallback((msg, isError = false) => {
        const id = Date.now() + Math.random();
        setToasts(prev => [...prev, { id, msg, isError }]);
        setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
    }, []);

    return { toasts, showToast };
}

// ─── Header ──────────────────────────────────────────────────────────────────

function Header() {
    return (
        <header className="header">
            <div className="brand">
                <div className="brand-icon">💬</div>
                <div>
                    <h1 className="brand-title">WhatsApp RAG Chatbot System</h1>
                    <div className="brand-subtitle">FastAPI • WasenderAPI • Pinecone • NVIDIA AI • Supabase • React</div>
                </div>
            </div>
            <div className="system-status">
                <div className="status-badge">
                    <span className="status-dot"></span>
                    <span>FastAPI Active</span>
                </div>
                <div className="status-badge">
                    <span className="status-dot"></span>
                    <span>Pinecone RAG Ready</span>
                </div>
                <div className="status-badge">
                    <span className="status-dot"></span>
                    <span>Bilingual Agent (EN / TE)</span>
                </div>
            </div>
        </header>
    );
}

// ─── Navigation Tabs ─────────────────────────────────────────────────────────

function NavTabs({ activeTab, onTabChange }) {
    const tabs = [
        { id: 'simulator', label: '💬 Live Web Chatbot' },
        { id: 'documents', label: '📄 Ingestion & Knowledge Base' },
        { id: 'conversations', label: '📊 Session History & Logs' },
        { id: 'webhook', label: '⚡ WasenderAPI & Webhook Setup' },
    ];
    return (
        <nav className="nav-tabs">
            {tabs.map(tab => (
                <button
                    key={tab.id}
                    className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
                    onClick={() => onTabChange(tab.id)}
                >
                    {tab.label}
                </button>
            ))}
        </nav>
    );
}

// ─── Tab 1: Chat Simulator ────────────────────────────────────────────────────

function ChatSimulator({ showToast }) {
    const [messages, setMessages] = useState([
        {
            id: 0,
            text: 'Welcome! I am your AI-powered WhatsApp Assistant. Send a message starting with @ (e.g. @who is rama or @రాముడు ఎవరు?) to search our knowledge base in English or Telugu!',
            sender: 'bot',
            time: 'System',
        }
    ]);
    const [input, setInput] = useState('');
    const [phone, setPhone] = useState('+919876543210');
    const [sending, setSending] = useState(false);
    const chatEndRef = useRef(null);

    const sampleQueries = [
        { label: '@who is rama', telugu: false },
        { label: '@రాముడు ఎవరు?', telugu: true },
        { label: '@who is rama in telugu', telugu: true },
        { label: '@what are the admission requirements?', telugu: false },
        { label: '@కోర్సుల వివరాలు తెలపండి', telugu: true },
    ];

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const appendMessage = (text, sender) => {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        setMessages(prev => [...prev, { id: Date.now() + Math.random(), text, sender, time }]);
    };

    const sendQuery = async () => {
        const text = input.trim();
        const phoneVal = phone.trim() || '+919876543210';
        if (!text || sending) return;

        appendMessage(text, 'user');
        setInput('');
        setSending(true);
        showToast('Processing query...');

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: phoneVal, message: text }),
            });
            const data = await res.json();
            if (res.ok && data.response) {
                appendMessage(data.response, 'bot');
                showToast('RAG Response received!');
            } else {
                showToast(`Error: ${data.detail || 'Failed to get response'}`, true);
            }
        } catch (e) {
            showToast(`Connection error: ${e.message}`, true);
        } finally {
            setSending(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') sendQuery();
    };

    return (
        <section className="tab-content active">
            <div className="chat-layout">
                {/* Sidebar */}
                <div className="chat-sidebar">
                    <div className="card">
                        <h2 className="card-title">📱 Simulator Settings</h2>
                        <div className="phone-input-group">
                            <label htmlFor="user-phone">Simulated Phone Number</label>
                            <input
                                type="text"
                                id="user-phone"
                                className="input-field"
                                value={phone}
                                onChange={e => setPhone(e.target.value)}
                                placeholder="+919876543210"
                            />
                        </div>
                    </div>

                    <div className="card" style={{ flex: 1 }}>
                        <h2 className="card-title">💡 Quick Sample Prompts</h2>
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                            Messages require leading <code style={{ color: 'var(--accent-primary)' }}>@</code> symbol to trigger RAG response.
                        </p>
                        <div className="sample-queries">
                            {sampleQueries.map((q, i) => (
                                <button
                                    key={i}
                                    className={`query-chip${q.telugu ? ' telugu' : ''}`}
                                    onClick={() => setInput(q.label)}
                                >
                                    {q.label}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Phone Screen */}
                <div className="phone-screen">
                    <div className="phone-header">
                        <div className="bot-avatar">AI</div>
                        <div className="bot-info">
                            <div className="bot-name">WhatsApp RAG Assistant</div>
                            <div className="bot-status">● Online • WasenderAPI Connected</div>
                        </div>
                    </div>

                    <div id="chat-messages" className="chat-messages">
                        {messages.map(m => (
                            <div key={m.id} className={`message-bubble ${m.sender}`}>
                                <div>{m.text}</div>
                                <div className="message-time">{m.time}</div>
                            </div>
                        ))}
                        <div ref={chatEndRef} />
                    </div>

                    <div className="chat-input-bar">
                        <input
                            type="text"
                            id="chat-input"
                            className="input-field"
                            style={{ flex: 1 }}
                            placeholder="Type message starting with @ (e.g. @who is rama or @రాముడు ఎవరు?)..."
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            disabled={sending}
                        />
                        <button id="send-btn" className="btn-send" onClick={sendQuery} disabled={sending}>
                            {sending ? '...' : 'Send'}
                        </button>
                    </div>
                </div>
            </div>
        </section>
    );
}

// ─── Tab 2: Documents / Ingestion ─────────────────────────────────────────────

function DocumentsTab({ showToast }) {
    const [documents, setDocuments] = useState([]);
    const [loadingDocs, setLoadingDocs] = useState(true);
    const dropzoneRef = useRef(null);
    const fileInputRef = useRef(null);

    const loadDocuments = useCallback(async () => {
        setLoadingDocs(true);
        try {
            const res = await fetch('/api/documents');
            const data = await res.json();
            if (res.ok && data.documents) {
                setDocuments(data.documents);
            }
        } catch (e) {
            showToast(`Error loading documents: ${e.message}`, true);
        } finally {
            setLoadingDocs(false);
        }
    }, [showToast]);

    useEffect(() => { loadDocuments(); }, [loadDocuments]);

    const handleFileUpload = async (file) => {
        const MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024;
        const DIRECT_UPLOAD_LIMIT = 4.5 * 1024 * 1024;

        if (file.size > MAX_TOTAL_SIZE) {
            const sizeGB = (file.size / (1024 * 1024 * 1024)).toFixed(2);
            showToast(`Upload rejected: '${file.name}' is ${sizeGB} GB. Maximum allowed file size is 2 GB.`, true);
            return;
        }

        showToast(`Uploading ${file.name}...`);

        try {
            if (file.size <= DIRECT_UPLOAD_LIMIT) {
                const formData = new FormData();
                formData.append('file', file);
                const res = await fetch('/api/documents/upload', { method: 'POST', body: formData });
                if (res.ok) {
                    const data = await res.json();
                    showToast(`Success: ${data.message}`);
                    loadDocuments();
                    return;
                } else if (res.status !== 413) {
                    const contentType = res.headers.get('content-type') || '';
                    const data = contentType.includes('application/json') ? await res.json() : { detail: await res.text() };
                    showToast(`Error: ${data.detail || 'Upload failed'}`, true);
                    return;
                }
            }

            showToast(`Uploading ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB) via cloud storage...`);
            const credsRes = await fetch('/api/storage/credentials');
            if (!credsRes.ok) throw new Error('Failed to retrieve cloud storage credentials');
            const creds = await credsRes.json();

            const sanitizedName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
            const storagePath = `upload_${Date.now()}_${sanitizedName}`;
            const storageUrl = `${creds.url.replace(/\/$/, '')}/storage/v1/object/documents/${storagePath}`;

            const storageUploadRes = await fetch(storageUrl, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${creds.key}`,
                    'apikey': creds.key,
                    'x-upsert': 'true',
                    'Content-Type': file.type || 'application/octet-stream',
                },
                body: file,
            });

            if (!storageUploadRes.ok) {
                const errText = await storageUploadRes.text();
                throw new Error(`Cloud storage upload failed: ${errText || storageUploadRes.statusText}`);
            }

            showToast(`Extracting text and generating embeddings for ${file.name}...`);
            const ingestRes = await fetch('/api/documents/ingest-from-storage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: file.name, storage_path: storagePath, mimetype: file.type }),
            });
            const ingestData = await ingestRes.json();
            if (ingestRes.ok) {
                showToast(`Success: ${ingestData.message}`);
                loadDocuments();
            } else {
                showToast(`Error: ${ingestData.detail || 'Ingestion failed'}`, true);
            }
        } catch (e) {
            showToast(`Upload failed: ${e.message}`, true);
        }
    };

    const deleteSingleDocument = async (docId, filename) => {
        if (!confirm(`Are you sure you want to delete '${filename}'? This will remove the document record and all indexed vector embeddings from Pinecone.`)) return;
        showToast(`Deleting document '${filename}'...`);
        try {
            const res = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
            const data = await res.json();
            if (res.ok) {
                showToast(`Deleted '${filename}' successfully.`);
                loadDocuments();
            } else {
                showToast(`Error deleting document: ${data.detail || 'Delete failed'}`, true);
            }
        } catch (e) {
            showToast(`Delete failed: ${e.message}`, true);
        }
    };

    const deleteAllDocuments = async () => {
        if (!confirm('Are you sure you want to delete ALL documents? This will permanently remove all documents from Supabase and clear the entire Pinecone vector index.')) return;
        showToast('Deleting all documents and clearing vector database...');
        try {
            const res = await fetch('/api/documents', { method: 'DELETE' });
            const data = await res.json();
            if (res.ok) {
                showToast('All documents and vectors deleted successfully.');
                loadDocuments();
            } else {
                showToast(`Error: ${data.detail || 'Clear all failed'}`, true);
            }
        } catch (e) {
            showToast(`Delete all failed: ${e.message}`, true);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        if (dropzoneRef.current) dropzoneRef.current.style.borderColor = '#10b981';
    };
    const handleDragLeave = () => {
        if (dropzoneRef.current) dropzoneRef.current.style.borderColor = '#3b82f6';
    };
    const handleDrop = (e) => {
        e.preventDefault();
        if (dropzoneRef.current) dropzoneRef.current.style.borderColor = '#3b82f6';
        if (e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    };

    return (
        <section className="tab-content active">
            <div className="card">
                <h2 className="card-title">📄 Ingest Documents into Vector DB (Pinecone)</h2>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
                    Upload PDF or TXT files to automatically extract text, generate NVIDIA high-dimensional embeddings (<code>nv-embed-v1</code>), and index into Pinecone for RAG retrieval.
                </p>
                <div
                    id="dropzone"
                    className="dropzone"
                    ref={dropzoneRef}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                >
                    <div className="dropzone-icon">📁</div>
                    <h3>Drag &amp; Drop PDF or TXT files here</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Or click to select a file from your computer (Max 2 GB)</p>
                    <input
                        type="file"
                        id="file-input"
                        accept=".pdf,.txt"
                        style={{ display: 'none' }}
                        ref={fileInputRef}
                        onChange={e => { if (e.target.files.length > 0) handleFileUpload(e.target.files[0]); }}
                    />
                </div>
            </div>

            <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                    <h2 className="card-title" style={{ marginBottom: 0 }}>📚 Knowledge Base Ingested Documents</h2>
                    <button
                        id="btn-delete-all-docs"
                        style={{ background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)', padding: '0.4rem 0.9rem', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem', transition: 'all 0.2s ease' }}
                        onClick={deleteAllDocuments}
                    >
                        🗑️ Clear All Files
                    </button>
                </div>
                <div className="table-responsive">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Filename</th>
                                <th>Status</th>
                                <th>Document ID</th>
                                <th>Uploaded Date</th>
                                <th style={{ width: '100px', textAlign: 'center' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="documents-tbody">
                            {loadingDocs ? (
                                <tr><td colSpan="5" style={{ textAlign: 'center' }}>Loading documents...</td></tr>
                            ) : documents.length === 0 ? (
                                <tr><td colSpan="5" style={{ textAlign: 'center', color: '#94a3b8' }}>No documents ingested yet. Upload a PDF or TXT file above.</td></tr>
                            ) : documents.map(doc => {
                                const statusClass = doc.status === 'indexed' ? 'indexed' : (doc.status === 'processing' ? 'processing' : 'failed');
                                const dateStr = (doc.created_at || doc.uploaded_at) ? new Date(doc.created_at || doc.uploaded_at).toLocaleString() : 'Just now';
                                return (
                                    <tr key={doc.id}>
                                        <td><strong>{escapeHtml(doc.filename)}</strong></td>
                                        <td><span className={`tag-badge ${statusClass}`}>{doc.status}</span></td>
                                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{doc.id}</td>
                                        <td>{dateStr}</td>
                                        <td style={{ textAlign: 'center' }}>
                                            <button
                                                className="btn-delete-single"
                                                data-id={doc.id}
                                                data-filename={escapeHtml(doc.filename)}
                                                title="Delete Document"
                                                style={{ background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)', padding: '0.35rem 0.65rem', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500, transition: 'all 0.2s ease' }}
                                                onClick={() => deleteSingleDocument(doc.id, doc.filename)}
                                            >
                                                🗑️ Delete
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}

// ─── Tab 3: Conversations / Session History ───────────────────────────────────

function ConversationsTab({ showToast }) {
    const [searchPhone, setSearchPhone] = useState('+919876543210');
    const [conversations, setConversations] = useState(null);
    const [loading, setLoading] = useState(false);

    const loadConversations = async () => {
        const phone = searchPhone.trim() || '+919876543210';
        setLoading(true);
        try {
            const res = await fetch(`/api/conversations/${encodeURIComponent(phone)}`);
            const data = await res.json();
            if (res.ok && data.conversations) {
                setConversations(data.conversations);
            } else {
                showToast(`Error: ${data.detail || 'Failed to load'}`, true);
            }
        } catch (e) {
            showToast(`Error loading history: ${e.message}`, true);
        } finally {
            setLoading(false);
        }
    };

    return (
        <section className="tab-content active">
            <div className="card">
                <h2 className="card-title">📊 User Conversation History (Supabase)</h2>
                <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
                    <input
                        type="text"
                        id="search-phone"
                        className="input-field"
                        value={searchPhone}
                        onChange={e => setSearchPhone(e.target.value)}
                        placeholder="Enter phone number (+91...)"
                        style={{ maxWidth: '320px' }}
                        onKeyDown={e => { if (e.key === 'Enter') loadConversations(); }}
                    />
                    <button id="btn-load-conversations" className="btn-send" onClick={loadConversations}>
                        Search History
                    </button>
                </div>
                <div className="table-responsive">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>User Phone</th>
                                <th>Sender</th>
                                <th>Message Content</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody id="conversations-tbody">
                            {conversations === null ? (
                                <tr><td colSpan="4" style={{ textAlign: 'center' }}>Enter phone number and click search...</td></tr>
                            ) : loading ? (
                                <tr><td colSpan="4" style={{ textAlign: 'center' }}>Loading conversation history...</td></tr>
                            ) : conversations.length === 0 ? (
                                <tr><td colSpan="4" style={{ textAlign: 'center', color: '#94a3b8' }}>No conversations found for {escapeHtml(searchPhone)}.</td></tr>
                            ) : conversations.map((conv, i) => {
                                const isUser = conv.sender === 'user';
                                return (
                                    <tr key={i}>
                                        <td>{escapeHtml(conv.user_phone)}</td>
                                        <td><span className={`tag-badge ${isUser ? 'indexed' : 'processing'}`}>{conv.sender}</span></td>
                                        <td>{escapeHtml(conv.message)}</td>
                                        <td>{conv.created_at ? new Date(conv.created_at).toLocaleString() : 'N/A'}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}

// ─── Tab 4: Webhook Setup Guide ───────────────────────────────────────────────

function WebhookTab() {
    return (
        <section className="tab-content active">
            <div className="card">
                <h2 className="card-title">⚡ WasenderAPI Webhook Configuration</h2>
                <div style={{ lineHeight: 1.6, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                    <p style={{ marginBottom: '1rem' }}>To connect your live WhatsApp phone line to this FastAPI backend:</p>
                    <ol style={{ paddingLeft: '1.5rem', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <li>Expose your local FastAPI server (port 8000) using ngrok:
                            <br /><code style={{ background: 'rgba(255,255,255,0.06)', padding: '0.4rem 0.8rem', borderRadius: '6px', fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>ngrok http 8000</code>
                        </li>
                        <li>Log into your <strong>WasenderAPI Dashboard</strong> (<code>https://www.wasenderapi.com</code>).</li>
                        <li>Navigate to <strong>Webhooks Settings</strong> and set Payload URL to:
                            <br /><code style={{ background: 'rgba(255,255,255,0.06)', padding: '0.4rem 0.8rem', borderRadius: '6px', fontFamily: 'var(--font-mono)', color: 'var(--accent-success)' }}>https://your-ngrok-domain.ngrok-free.dev/webhook</code>
                        </li>
                        <li>Enable <code>messages.received</code> events. Any message received with <code>@</code> prefix will trigger immediate RAG retrieval and WhatsApp automated reply!</li>
                    </ol>
                </div>
            </div>
        </section>
    );
}

// ─── Root App Component ───────────────────────────────────────────────────────

function App() {
    const [activeTab, setActiveTab] = useState('simulator');
    const { toasts, showToast } = useToast();

    const renderTab = () => {
        switch (activeTab) {
            case 'simulator':    return <ChatSimulator showToast={showToast} />;
            case 'documents':    return <DocumentsTab showToast={showToast} />;
            case 'conversations': return <ConversationsTab showToast={showToast} />;
            case 'webhook':      return <WebhookTab />;
            default:             return null;
        }
    };

    return (
        <>
            <Header />
            <NavTabs activeTab={activeTab} onTabChange={setActiveTab} />
            <main className="main-container">
                {renderTab()}
            </main>
            <ToastContainer toasts={toasts} />
        </>
    );
}

// ─── Mount ────────────────────────────────────────────────────────────────────

const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement);
root.render(<App />);
