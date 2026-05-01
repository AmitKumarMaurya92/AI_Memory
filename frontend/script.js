/**
 * script.js — AI Memory Companion Frontend
 * =========================================
 * Handles:
 *   - Tab switching (Chat / History / Files)
 *   - File upload via drag-and-drop or file picker
 *   - Chat with the RAG backend
 *   - Loading & rendering query history
 *   - Loading & rendering uploaded files list
 *   - Toast notifications
 */

const API = '';   // Empty = same origin (FastAPI serves the frontend)

// ──────────────────────────────────────────────────────────
// DOM References
// ──────────────────────────────────────────────────────────

const uploadZone      = document.getElementById('upload-zone');
const fileInput       = document.getElementById('file-input');
const progressWrap    = document.getElementById('progress-wrap');
const progressBar     = document.getElementById('progress-bar');
const sidebarFileList = document.getElementById('sidebar-file-list');
const chatMessages    = document.getElementById('chat-messages');
const welcomeScreen   = document.getElementById('welcome-screen');
const queryInput      = document.getElementById('query-input');
const sendBtn         = document.getElementById('send-btn');
const historyList     = document.getElementById('history-list');
const filesList       = document.getElementById('files-list');
const memoryCount     = document.getElementById('memory-count');
const toastContainer  = document.getElementById('toast-container');

// ──────────────────────────────────────────────────────────
// Tab Switching
// ──────────────────────────────────────────────────────────

const tabBtns  = document.querySelectorAll('.tab-btn');
const navItems = document.querySelectorAll('.nav-item');
const views    = document.querySelectorAll('.view');

function switchTab(tab) {
    // Update buttons
    tabBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));

    // Update sidebar nav
    navItems.forEach(item => item.classList.toggle('active', item.dataset.tab === tab));

    // Show correct view
    views.forEach(view => {
        const isActive = view.id === `view-${tab}`;
        view.classList.toggle('active', isActive);
    });

    // Load data for the selected tab
    if (tab === 'history') loadHistory();
    if (tab === 'files')   loadFiles();
}

tabBtns.forEach(btn  => btn.addEventListener('click', () => switchTab(btn.dataset.tab)));
navItems.forEach(item => item.addEventListener('click', () => switchTab(item.dataset.tab)));


// ──────────────────────────────────────────────────────────
// File Upload
// ──────────────────────────────────────────────────────────

/** Open file picker when the upload zone is clicked */
uploadZone.addEventListener('click', () => fileInput.click());

/** File input change */
fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) uploadFile(e.target.files[0]);
});

/** Drag & Drop */
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});


async function uploadFile(file) {
    const allowed = ['.txt', '.pdf', '.docx'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowed.includes(ext)) {
        showToast(`Unsupported file: ${ext}. Use .txt, .pdf, or .docx`, 'error');
        return;
    }

    // Show progress bar
    progressWrap.style.display = 'block';
    progressBar.style.width = '0%';

    // Fake progress animation (real progress needs XHR)
    let fakeProgress = 0;
    const interval = setInterval(() => {
        fakeProgress = Math.min(fakeProgress + 10, 85);
        progressBar.style.width = fakeProgress + '%';
    }, 150);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res  = await fetch(`${API}/upload`, { method: 'POST', body: formData });
        const data = await res.json();

        clearInterval(interval);
        progressBar.style.width = '100%';

        if (!res.ok) {
            showToast(data.detail || 'Upload failed', 'error');
        } else {
            showToast(`✓ ${data.message}`, 'success');
            addSidebarFile(file.name, data.num_chunks);
            refreshMemoryCount();
        }

    } catch (err) {
        clearInterval(interval);
        showToast('Network error – is the server running?', 'error');
    } finally {
        setTimeout(() => {
            progressWrap.style.display = 'none';
            progressBar.style.width    = '0%';
        }, 800);
    }
}


function addSidebarFile(name, chunks) {
    const icons = { txt: '📄', pdf: '📕', docx: '📝' };
    const ext   = name.split('.').pop().toLowerCase();
    const icon  = icons[ext] || '📄';

    const el = document.createElement('div');
    el.className = 'file-item';
    el.innerHTML = `<span class="file-icon">${icon}</span>
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${name}</span>
                    <span style="color:var(--text-muted);font-size:0.7rem">${chunks}c</span>`;
    sidebarFileList.appendChild(el);
}


// ──────────────────────────────────────────────────────────
// Chat
// ──────────────────────────────────────────────────────────

/** Auto-grow textarea */
queryInput.addEventListener('input', () => {
    queryInput.style.height = 'auto';
    queryInput.style.height = queryInput.scrollHeight + 'px';
});

/** Enter = send, Shift+Enter = newline */
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQuery();
    }
});

sendBtn.addEventListener('click', sendQuery);

/** Click a suggestion chip to pre-fill the input */
document.getElementById('suggestion-chips').addEventListener('click', (e) => {
    if (e.target.classList.contains('chip')) {
        queryInput.value = e.target.textContent;
        sendQuery();
    }
});


async function sendQuery() {
    const query = queryInput.value.trim();
    if (!query) return;

    // Hide welcome screen once conversation starts
    if (welcomeScreen) welcomeScreen.remove();

    appendMessage(query, 'user');
    queryInput.value = '';
    queryInput.style.height = 'auto';

    const loadingEl = appendLoading();
    sendBtn.disabled = true;

    try {
        const res  = await fetch(`${API}/query`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ query, top_k: 5 }),
        });

        const data = await res.json();
        loadingEl.remove();

        if (!res.ok) {
            appendMessage(data.detail || 'Something went wrong.', 'ai', null);
            showToast('Query failed', 'error');
        } else {
            appendMessage(data.answer, 'ai', data.summary, data.chunks_used);
        }

    } catch (err) {
        loadingEl.remove();
        appendMessage('Cannot connect to the server. Please make sure the backend is running.', 'ai');
        showToast('Network error', 'error');
    } finally {
        sendBtn.disabled = false;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}


function appendMessage(text, sender, summary = null, chunksUsed = null) {
    const isAI   = sender === 'ai';
    const avatar = isAI ? '🧠' : '👤';

    const msgEl = document.createElement('div');
    msgEl.className = `message ${sender}`;

    let summaryHTML = '';
    if (isAI && summary) {
        summaryHTML = `
        <div class="summary-card">
            <div class="label">📋 Memory Summary</div>
            <p>${escapeHtml(summary)}</p>
            ${chunksUsed != null ? `<span class="chunks-badge">🔍 ${chunksUsed} memory chunk${chunksUsed !== 1 ? 's' : ''} retrieved</span>` : ''}
        </div>`;
    }

    msgEl.innerHTML = `
        <div class="avatar">${avatar}</div>
        <div class="bubble">
            ${escapeHtml(text).replace(/\n/g, '<br/>')}
            ${summaryHTML}
        </div>`;

    chatMessages.appendChild(msgEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgEl;
}


function appendLoading() {
    const el = document.createElement('div');
    el.className = 'message ai';
    el.innerHTML = `
        <div class="avatar">🧠</div>
        <div class="bubble loading-bubble">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        </div>`;
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return el;
}


// ──────────────────────────────────────────────────────────
// History View
// ──────────────────────────────────────────────────────────

async function loadHistory() {
    historyList.innerHTML = '<div class="history-empty">Loading…</div>';

    try {
        const res  = await fetch(`${API}/history`);
        const data = await res.json();

        if (!data.history || data.history.length === 0) {
            historyList.innerHTML = '<div class="history-empty">No queries yet. Start chatting!</div>';
            return;
        }

        historyList.innerHTML = '';
        data.history.forEach(item => {
            const date = new Date(item.created_at + 'Z').toLocaleString();
            const el   = document.createElement('div');
            el.className = 'history-item';
            el.innerHTML = `
                <div class="history-q">❓ ${escapeHtml(item.query)}</div>
                <div class="history-a">${escapeHtml(item.answer).replace(/\n/g, '<br/>')}</div>
                <div class="history-meta">🕐 ${date}</div>`;
            historyList.appendChild(el);
        });

    } catch {
        historyList.innerHTML = '<div class="history-empty">Failed to load history.</div>';
    }
}


// ──────────────────────────────────────────────────────────
// Files View
// ──────────────────────────────────────────────────────────

const fileIcons = { txt: '📄', pdf: '📕', docx: '📝' };

async function loadFiles() {
    filesList.innerHTML = '<div class="files-empty">Loading…</div>';

    try {
        const res  = await fetch(`${API}/files`);
        const data = await res.json();

        if (!data.files || data.files.length === 0) {
            filesList.innerHTML = '<div class="files-empty">No files uploaded yet.</div>';
            return;
        }

        filesList.innerHTML = '';
        data.files.forEach(f => {
            const ext  = f.filename.split('.').pop().toLowerCase();
            const icon = fileIcons[ext] || '📄';
            const date = new Date(f.upload_date + 'Z').toLocaleDateString();
            const el   = document.createElement('div');
            el.className = 'file-card';
            el.innerHTML = `
                <div class="file-type-icon">${icon}</div>
                <div class="file-card-info">
                    <div class="file-card-name">${escapeHtml(f.filename)}</div>
                    <div class="file-card-meta">Uploaded ${date}</div>
                </div>
                <div class="file-card-badge">${f.num_chunks} chunks</div>`;
            filesList.appendChild(el);
        });

    } catch {
        filesList.innerHTML = '<div class="files-empty">Failed to load files.</div>';
    }
}


// ──────────────────────────────────────────────────────────
// Memory Count
// ──────────────────────────────────────────────────────────

async function refreshMemoryCount() {
    try {
        const res  = await fetch(`${API}/files`);
        const data = await res.json();
        const total = (data.files || []).reduce((sum, f) => sum + f.num_chunks, 0);
        memoryCount.textContent = `${total} memories stored`;
    } catch { /* ignore */ }
}

refreshMemoryCount();  // Load on startup


// ──────────────────────────────────────────────────────────
// Toast Notifications
// ──────────────────────────────────────────────────────────

function showToast(msg, type = 'info', duration = 4000) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    toastContainer.appendChild(el);

    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transform = 'translateX(30px)';
        el.style.transition = 'all 0.3s ease';
        setTimeout(() => el.remove(), 300);
    }, duration);
}


// ──────────────────────────────────────────────────────────
// Utility
// ──────────────────────────────────────────────────────────

function escapeHtml(str) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(str));
    return d.innerHTML;
}
