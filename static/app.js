document.addEventListener('DOMContentLoaded', () => {
    // Navigation Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(target).classList.add('active');

            if (target === 'documents-tab') {
                loadDocuments();
            } else if (target === 'conversations-tab') {
                loadConversations();
            }
        });
    });

    // Chat Simulator Logic
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatMessages = document.getElementById('chat-messages');
    const phoneInput = document.getElementById('user-phone');

    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message-bubble ${sender}`;
        
        const textSpan = document.createElement('div');
        textSpan.innerText = text;
        msgDiv.appendChild(textSpan);

        const timeSpan = document.createElement('div');
        timeSpan.className = 'message-time';
        timeSpan.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        msgDiv.appendChild(timeSpan);

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendQuery() {
        const text = chatInput.value.trim();
        const phone = phoneInput.value.trim() || '+919876543210';
        if (!text) return;

        // Visual append user query
        appendMessage(text, 'user');
        chatInput.value = '';

        showToast('Processing query...');

        try {
            // Direct API call for instantaneous live web chat response
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phone: phone, message: text })
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
        }
    }



    async function fetchLatestBotResponse(phone) {
        try {
            const cleanPhone = phone.startsWith('+') ? phone : `+${phone}`;
            const res = await fetch(`/api/conversations/${encodeURIComponent(cleanPhone)}`);
            if (res.ok) {
                const data = await res.json();
                if (data.conversations && data.conversations.length > 0) {
                    const latest = data.conversations[0];
                    if (latest.sender === 'bot') {
                        appendMessage(latest.message, 'bot');
                    }
                }
            }
        } catch (e) {
            console.error(e);
        }
    }

    sendBtn.addEventListener('click', sendQuery);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendQuery();
    });

    // Quick Chip Click
    document.querySelectorAll('.query-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            chatInput.value = chip.innerText;
            chatInput.focus();
        });
    });

    // Document Upload Drag & Drop
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#10b981';
    });
    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = '#3b82f6';
    });
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = '#3b82f6';
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    async function handleFileUpload(file) {
        const MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024; // 2 GB overall system limit
        const DIRECT_UPLOAD_LIMIT = 4.5 * 1024 * 1024; // 4.5 MB Vercel Serverless Function proxy limit

        if (file.size > MAX_TOTAL_SIZE) {
            const sizeGB = (file.size / (1024 * 1024 * 1024)).toFixed(2);
            showToast(`Upload rejected: '${file.name}' is ${sizeGB} GB. Maximum allowed file size is 2 GB.`, true);
            return;
        }

        showToast(`Uploading ${file.name}...`);

        try {
            // For files under 4.5 MB, attempt direct API upload first
            if (file.size <= DIRECT_UPLOAD_LIMIT) {
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch('/api/documents/upload', {
                    method: 'POST',
                    body: formData
                });

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

            // For files > 4.5 MB or on 413 response, bypass Vercel serverless proxy via direct Supabase Storage upload
            showToast(`Uploading ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB) via cloud storage...`);
            
            const credsRes = await fetch('/api/storage/credentials');
            if (!credsRes.ok) {
                throw new Error('Failed to retrieve cloud storage credentials');
            }
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
                    'Content-Type': file.type || 'application/octet-stream'
                },
                body: file
            });

            if (!storageUploadRes.ok) {
                const errText = await storageUploadRes.text();
                throw new Error(`Cloud storage upload failed: ${errText || storageUploadRes.statusText}`);
            }

            // Trigger FastAPI ingestion from Supabase Storage
            showToast(`Extracting text and generating embeddings for ${file.name}...`);
            const ingestRes = await fetch('/api/documents/ingest-from-storage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: file.name,
                    storage_path: storagePath,
                    mimetype: file.type
                })
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
    }

    // Load Documents List
    async function loadDocuments() {
        const tbody = document.getElementById('documents-tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Loading documents...</td></tr>';

        try {
            const res = await fetch('/api/documents');
            const data = await res.json();
            if (res.ok && data.documents) {
                if (data.documents.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: #94a3b8;">No documents ingested yet. Upload a PDF or TXT file above.</td></tr>';
                    return;
                }
                tbody.innerHTML = '';
                data.documents.forEach(doc => {
                    const tr = document.createElement('tr');
                    const statusClass = doc.status === 'indexed' ? 'indexed' : (doc.status === 'processing' ? 'processing' : 'failed');
                    const dateStr = (doc.created_at || doc.uploaded_at) ? new Date(doc.created_at || doc.uploaded_at).toLocaleString() : 'Just now';
                    
                    tr.innerHTML = `
                        <td><strong>${escapeHtml(doc.filename)}</strong></td>
                        <td><span class="tag-badge ${statusClass}">${doc.status}</span></td>
                        <td style="font-family: var(--font-mono); font-size: 0.8rem;">${doc.id}</td>
                        <td>${dateStr}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: #ef4444;">Error loading documents: ${e.message}</td></tr>`;
        }
    }

    // Load Conversations
    async function loadConversations() {
        const phone = document.getElementById('search-phone').value.trim() || '+919876543210';
        const tbody = document.getElementById('conversations-tbody');
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">Loading conversation history...</td></tr>';

        try {
            const res = await fetch(`/api/conversations/${encodeURIComponent(phone)}`);
            const data = await res.json();
            if (res.ok && data.conversations) {
                if (data.conversations.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: #94a3b8;">No conversations found for ${escapeHtml(phone)}.</td></tr>`;
                    return;
                }
                tbody.innerHTML = '';
                data.conversations.forEach(conv => {
                    const tr = document.createElement('tr');
                    const isUser = conv.sender === 'user';
                    tr.innerHTML = `
                        <td>${escapeHtml(conv.user_phone)}</td>
                        <td><span class="tag-badge ${isUser ? 'indexed' : 'processing'}">${conv.sender}</span></td>
                        <td>${escapeHtml(conv.message)}</td>
                        <td>${conv.created_at ? new Date(conv.created_at).toLocaleString() : 'N/A'}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: #ef4444;">Error loading history: ${e.message}</td></tr>`;
        }
    }

    document.getElementById('btn-load-conversations')?.addEventListener('click', loadConversations);

    // Toast Notifications
    function showToast(msg, isError = false) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        if (isError) toast.style.borderColor = '#ef4444';
        toast.innerText = msg;
        document.getElementById('toast-container').appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    function escapeHtml(str) {
        return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Initial Load
    loadDocuments();
});
