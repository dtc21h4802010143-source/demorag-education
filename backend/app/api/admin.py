from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def admin_ui():
    return """
<!doctype html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>EduChat Admin Console</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f6f8ef;
            --bg-accent: #fff9e7;
            --ink: #10211b;
            --muted: #5a6c64;
            --card: #ffffff;
            --primary: #0f766e;
            --primary-strong: #0b5f59;
            --danger: #b91c1c;
            --ok: #166534;
            --warn: #b45309;
            --border: #dbe5dc;
            --shadow: 0 14px 40px rgba(15, 118, 110, 0.12);
            --radius-lg: 18px;
            --radius-md: 12px;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            color: var(--ink);
            font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
            background:
                radial-gradient(circle at 12% 10%, #fff7d2 0, transparent 38%),
                radial-gradient(circle at 90% 0%, #dff5f0 0, transparent 40%),
                linear-gradient(180deg, var(--bg-accent) 0%, var(--bg) 50%, #f1f6f2 100%);
            min-height: 100vh;
            padding: 32px 18px 48px;
        }

        .container {
            max-width: 1020px;
            margin: 0 auto;
            display: grid;
            gap: 14px;
        }

        .hero {
            background: linear-gradient(135deg, #0f766e 0%, #115e59 50%, #1d4ed8 150%);
            color: #eefdfb;
            border-radius: 24px;
            padding: 24px;
            box-shadow: var(--shadow);
        }

        .hero h1 {
            margin: 0 0 6px;
            letter-spacing: 0.3px;
            font-size: clamp(24px, 4vw, 34px);
        }

        .hero p {
            margin: 0;
            color: #daf6f2;
            font-size: 15px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 14px;
        }

        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 18px;
            box-shadow: 0 8px 24px rgba(16, 33, 27, 0.06);
        }

        .login-card { grid-column: span 5; }
        .upload-card { grid-column: span 7; }
        .docs-card { grid-column: span 12; }

        h2 {
            margin: 0 0 14px;
            font-size: 18px;
            letter-spacing: 0.2px;
        }

        .muted {
            margin: -8px 0 14px;
            color: var(--muted);
            font-size: 13px;
        }

        .status {
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 13px;
            margin-top: 10px;
            border: 1px solid #cae4de;
            background: #f0faf8;
            color: #12423c;
        }

        .status.error {
            background: #fff5f5;
            border-color: #f3cccc;
            color: #7f1d1d;
        }

        .status.warn {
            background: #fff8ed;
            border-color: #f3ddbc;
            color: #8a4b08;
        }

        .field {
            margin: 8px 0;
        }

        .field label {
            display: block;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 6px;
            color: #1a3a31;
        }

        input[type=\"text\"],
        input[type=\"password\"],
        input[type=\"file\"] {
            width: 100%;
            padding: 11px 12px;
            border: 1px solid #cbd9d0;
            border-radius: var(--radius-md);
            font: inherit;
            background: #fff;
        }

        input:focus {
            outline: 2px solid #79c2b8;
            outline-offset: 1px;
            border-color: #6ab7ab;
        }

        .btn {
            cursor: pointer;
            padding: 10px 14px;
            border: none;
            border-radius: 11px;
            background: var(--primary);
            color: #fff;
            font-weight: 600;
            font-family: inherit;
            transition: transform .16s ease, background-color .16s ease, box-shadow .16s ease;
            box-shadow: 0 6px 16px rgba(15, 118, 110, 0.26);
        }

        .btn:hover {
            background: var(--primary-strong);
            transform: translateY(-1px);
        }

        .btn:disabled {
            opacity: .65;
            cursor: not-allowed;
            transform: none;
        }

        .btn.subtle {
            background: #e5f3f1;
            color: #0d5f58;
            box-shadow: none;
        }

        .btn.subtle:hover {
            background: #d8ebe8;
        }

        .btn.danger {
            background: var(--danger);
            box-shadow: 0 6px 16px rgba(185, 28, 28, 0.2);
        }

        .btn.danger:hover {
            background: #991b1b;
        }

        .docs-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 12px;
        }

        .docs {
            display: grid;
            gap: 10px;
        }

        .doc-item {
            border: 1px solid #dde7df;
            border-radius: 14px;
            padding: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            background: #fbfdfc;
            animation: slideUp .25s ease;
        }

        .doc-main b {
            font-size: 15px;
            word-break: break-word;
        }

        .doc-meta {
            font-size: 12px;
            color: var(--muted);
            margin-top: 4px;
        }

        .actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            border-radius: 999px;
            padding: 4px 9px;
            margin-left: 6px;
            border: 1px solid #d4e8de;
            background: #eef9f3;
            color: var(--ok);
        }

        .empty {
            border: 1px dashed #c8d8ce;
            border-radius: 12px;
            padding: 18px;
            text-align: center;
            color: var(--muted);
            background: #fcfffd;
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 920px) {
            .login-card, .upload-card, .docs-card { grid-column: span 12; }
            .actions { justify-content: flex-start; }
        }
    </style>
</head>
<body>
    <div class=\"container\">
        <section class=\"hero\">
            <h1>EduChat Admin Console</h1>
            <p>Quan ly tri thuc RAG, tai lieu va tien trinh indexing tren cung mot man hinh.</p>
        </section>

        <section class=\"grid\">
            <div class=\"card login-card\">
                <h2>Admin Login</h2>
                <p class=\"muted\">Dang nhap de su dung cac thao tac upload, reindex va delete.</p>
                <div class=\"field\">
                    <label for=\"user\">Username</label>
                    <input id=\"user\" type=\"text\" placeholder=\"admin username\" value=\"admin\" />
                </div>
                <div class=\"field\">
                    <label for=\"pass\">Password</label>
                    <input id=\"pass\" type=\"password\" placeholder=\"password\" value=\"admin123\" />
                </div>
                <button id=\"login-btn\" class=\"btn\" onclick=\"login()\">Login</button>
                <div id=\"login-status\" class=\"status warn\">Chua dang nhap.</div>
            </div>

            <div class=\"card upload-card\">
                <h2>Upload Data File</h2>
                <p class=\"muted\">Ho tro PDF, DOCX, TXT, JSON. Tep se duoc parse, chunk va index tu dong.</p>
                <div class=\"field\">
                    <label for=\"file\">Choose file</label>
                    <input id=\"file\" type=\"file\" accept=\".pdf,.docx,.txt,.json\" />
                </div>
                <button id=\"upload-btn\" class=\"btn\" onclick=\"upload()\">Upload & Index</button>
                <div id=\"upload-status\" class=\"status\">San sang upload.</div>
            </div>

            <div class=\"card docs-card\">
                <div class=\"docs-header\">
                    <h2>Documents</h2>
                    <button class=\"btn subtle\" onclick=\"loadDocs()\">Refresh</button>
                </div>
                <div id=\"docs\" class=\"docs\"></div>
            </div>
        </section>
    </div>

<script>
const api = '';
const getToken = () => localStorage.getItem('admin_token') || '';
const loginStatusEl = document.getElementById('login-status');
const uploadStatusEl = document.getElementById('upload-status');

function setStatus(el, text, tone) {
    el.textContent = text;
    el.className = 'status' + (tone ? ' ' + tone : '');
}

async function login() {
    const username = document.getElementById('user').value;
    const password = document.getElementById('pass').value;
    const loginBtn = document.getElementById('login-btn');
    loginBtn.disabled = true;
    setStatus(loginStatusEl, 'Dang dang nhap...', 'warn');

    const res = await fetch(api + '/auth/admin-login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });

    loginBtn.disabled = false;
    if (!res.ok) {
        setStatus(loginStatusEl, 'Login failed. Kiem tra username/password.', 'error');
        return;
    }

    const data = await res.json();
    localStorage.setItem('admin_token', data.access_token);
    setStatus(loginStatusEl, 'Login success. Ban da co quyen admin.', '');
    loadDocs();
}

async function upload() {
    const token = getToken();
    if (!token) {
        setStatus(uploadStatusEl, 'Vui long login truoc khi upload.', 'warn');
        return;
    }

    const fileInput = document.getElementById('file');
    const uploadBtn = document.getElementById('upload-btn');
    if (!fileInput.files.length) {
        setStatus(uploadStatusEl, 'Hay chon 1 file truoc khi upload.', 'warn');
        return;
    }

    uploadBtn.disabled = true;
    setStatus(uploadStatusEl, 'Dang upload va index...', 'warn');

    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    const res = await fetch(api + '/documents/upload', {
        method: 'POST', headers: { Authorization: 'Bearer ' + token }, body: fd
    });

    uploadBtn.disabled = false;
    if (!res.ok) {
        setStatus(uploadStatusEl, 'Upload failed. Thu lai sau.', 'error');
        return;
    }

    setStatus(uploadStatusEl, 'Upload thanh cong va da index xong.', '');
    await loadDocs();
}

async function loadDocs() {
    const res = await fetch(api + '/documents');
    if (!res.ok) {
        document.getElementById('docs').innerHTML = '<div class="empty">Khong tai duoc danh sach tai lieu.</div>';
        return;
    }

    const docs = await res.json();
    const root = document.getElementById('docs');
    root.innerHTML = '';

    if (!docs.length) {
        root.innerHTML = '<div class="empty">Chua co tai lieu nao. Hay upload du lieu moi.</div>';
        return;
    }

    docs.forEach((d) => {
        const item = document.createElement('div');
        item.className = 'doc-item';
        item.innerHTML = `<div class="doc-main"><b>${d.filename}</b><div class="doc-meta">${d.status} <span class="badge">${d.chunk_count} chunks</span></div></div>`;

        const actions = document.createElement('div');
        actions.className = 'actions';

        const reindex = document.createElement('button');
        reindex.textContent = 'Reindex';
        reindex.className = 'btn subtle';
        reindex.onclick = async () => {
            const token = getToken();
            if (!token) {
                setStatus(loginStatusEl, 'Please login first.', 'warn');
                return;
            }

            await fetch(api + `/documents/${d.id}/reindex`, { method: 'POST', headers: { Authorization: 'Bearer ' + token } });
            loadDocs();
        };

        const del = document.createElement('button');
        del.textContent = 'Delete';
        del.className = 'btn danger';
        del.onclick = async () => {
            const token = getToken();
            if (!token) {
                setStatus(loginStatusEl, 'Please login first.', 'warn');
                return;
            }

            await fetch(api + `/documents/${d.id}`, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } });
            loadDocs();
        };

        actions.appendChild(reindex);
        actions.appendChild(del);
        item.appendChild(actions);
        root.appendChild(item);
    });
}

loadDocs();
</script>
</body>
</html>
"""


@router.get("/dashboard")
def dashboard(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    total_sessions = db.query(func.count(ChatSession.id)).scalar() or 0
    total_messages = db.query(func.count(ChatMessage.id)).scalar() or 0
    total_documents = db.query(func.count(Document.id)).scalar() or 0
    total_chunks = db.query(func.coalesce(func.sum(Document.chunk_count), 0)).scalar() or 0

    return {
        "sessions": total_sessions,
        "messages": total_messages,
        "documents": total_documents,
        "chunks": int(total_chunks),
    }


@router.get("/chat-logs")
def chat_logs(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ChatMessage, ChatSession)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "session_id": sess.id,
            "session_title": sess.title,
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at,
        }
        for msg, sess in rows
    ]


@router.get("/config")
def get_config(_: str = Depends(require_admin)):
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "openai_model": settings.openai_model,
        "groq_model": settings.groq_model,
        "rag_top_k": settings.rag_top_k,
        "rag_temperature": settings.rag_temperature,
        "rag_max_output_tokens": settings.rag_max_output_tokens,
    }


@router.put("/config")
def update_config(payload: dict, _: str = Depends(require_admin)):
    settings = get_settings()
    allowed = {
        "llm_provider",
        "openai_model",
        "groq_model",
        "rag_top_k",
        "rag_temperature",
        "rag_max_output_tokens",
    }
    for key, value in payload.items():
        if key in allowed:
            setattr(settings, key, value)

    return {
        "message": "Config updated",
        "config": {
            "llm_provider": settings.llm_provider,
            "openai_model": settings.openai_model,
            "groq_model": settings.groq_model,
            "rag_top_k": settings.rag_top_k,
            "rag_temperature": settings.rag_temperature,
            "rag_max_output_tokens": settings.rag_max_output_tokens,
        },
    }
