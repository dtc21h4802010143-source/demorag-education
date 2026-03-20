# EduChat RAG - Tro ly giao duc

Ung dung web chat ho tro giao duc su dung FastAPI + React + RAG.

## 1. Kien truc tong quan

- Frontend: React + Vite + TailwindCSS
- Backend: FastAPI + SQLAlchemy + JWT + SSE streaming
- RAG:
  - Embedding: `sentence-transformers/all-MiniLM-L6-v2`
  - Vector store: local JSON + cosine similarity (khong can native build tools)
  - Generator: Groq API (OpenAI-compatible), co fallback demo mode neu chua co API key
- Storage:
  - SQLite cho dev (chat sessions, chat messages, documents)
  - Chroma persistent folder cho vector index

Luong xu ly:
1. Admin upload file PDF/DOCX/TXT/JSON.
2. Backend extract text, chunk theo word window, tao embedding, index vao Chroma.
3. User dat cau hoi tai trang chat.
4. Backend embed cau hoi, truy xuat top-k chunks, tao prompt, stream token tu LLM qua SSE.
5. Lich su hoi dap duoc luu theo chat session.

## 2. Cau truc thu muc

```text
backend/
  app/
    api/            # auth, chat, documents, admin
    core/           # settings + JWT helpers
    db/             # init DB + session
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    services/       # RAG services
    utils/          # chunking
frontend/
  src/
    pages/          # Chat, Upload, Admin
    components/     # UI components
docker-compose.yml
```

## 3. Chay local (khong Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Backend mac dinh chay o: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend mac dinh chay o: `http://localhost:5173`

## 4. Chay bang Docker

```bash
docker compose up --build
```

## 5. API chinh

- `POST /auth/admin-login`: Dang nhap admin, tra JWT.
- `POST /auth/user-login`: Dang nhap nguoi dung chat, tra JWT.
- `GET /chat/sessions`: Lay danh sach phien chat.
- `GET /chat/sessions/{id}/messages`: Lay lich su chat theo phien.
- `POST /chat/stream`: Chat streaming SSE (`text/event-stream`).
- `GET /chat/quota?client_id=...`: Xem gioi han cau hoi cho nguoi dung chua login.
- `DELETE /chat/sessions/{id}`: Xoa 1 phien chat.
- `DELETE /chat/sessions`: Xoa toan bo lich su chat.
- `GET /documents`: Danh sach tai lieu.
- `POST /documents/upload`: Upload + index (admin, ho tro PDF/DOCX/TXT/JSON).
- `POST /documents/{id}/reindex`: Re-index tai lieu (admin).
- `DELETE /documents/{id}`: Xoa tai lieu (admin).
- `GET /admin/dashboard`: So lieu tong hop (admin).
- `GET /admin/chat-logs`: Log hoi dap (admin).
- `GET /admin/config`, `PUT /admin/config`: Xem/sua cau hinh runtime (admin).

## 6. Bao mat co ban da co

- JWT cho admin actions.
- Input validation bang Pydantic.
- Gioi han request rate limit middleware (`slowapi`).
- Validate file type upload.
- CORS cau hinh tu env.
- Nguoi dung khong login bi gioi han so cau hoi (`ANONYMOUS_QUESTION_LIMIT`, mac dinh 5).

## 7. Giao dien quan tri backend

- Mo trang `http://localhost:8000/admin/ui`.
- Login bang tai khoan admin de upload/reindex/delete du lieu.
- Frontend (`http://localhost:5173`) chi de chat.

## 7. Bien moi truong quan trong

Xem file `backend/.env.example`:

- `GROQ_API_KEY`: Khoa API Groq.
- `GROQ_MODEL`: Model Groq dung de sinh cau tra loi.
- `RAG_TOP_K`, `RAG_TEMPERATURE`, `RAG_MAX_OUTPUT_TOKENS`: tinh chinh RAG.
- `RAG_CHUNK_SIZE_WORDS`, `RAG_CHUNK_OVERLAP_WORDS`: tinh chinh chunking.

## 8. Ghi chu van hanh

- Neu chua co `GROQ_API_KEY`, he thong van stream du lieu o che do demo.
- He thong se tu dong seed `backend/data/education_knowledge.json` vao index khi startup (neu chua ton tai trong DB).
- Du lieu upload luu trong `backend/uploads`.
- Vector index luu trong `backend/chroma_data`.
- DB SQLite luu trong `backend/app.db`.

## 9. Huong mo rong

- Thay SQLite bang PostgreSQL bang cach doi `DATABASE_URL`.
- Them user system day du (register/login, per-user chat history).
- Them observability (OpenTelemetry, structured logs).
- Tach worker background (Celery/RQ) cho indexing tai lieu lon.

## 10. So do Use Case (chi tiet theo tung ca)

### 10.1 Tong quan actor va ca su dung

```mermaid
flowchart LR
  Admin[Admin]
  User[User]

  UC1((Dang nhap))
  UC2((Chat hoi dap RAG))
  UC3((Xem lich su chat))
  UC4((Xoa phien chat))
  UC5((Upload tai lieu + Index))
  UC6((Re-index tai lieu))
  UC7((Xoa tai lieu))
  UC8((Xem dashboard va chat logs))
  UC9((Xem/Sua cau hinh runtime))

  User --- UC1
  User --- UC2
  User --- UC3
  User --- UC4

  Admin --- UC1
  Admin --- UC5
  Admin --- UC6
  Admin --- UC7
  Admin --- UC8
  Admin --- UC9
```

### 10.2 UC1 - Dang nhap (Admin/User)

```mermaid
flowchart LR
  A[Actor: Admin/User] --> B[Nhap thong tin dang nhap]
  B --> C{Loai tai khoan?}
  C -->|Admin| D[POST /auth/admin-login]
  C -->|User| E[POST /auth/user-login]
  D --> F[Xac thuc credentials]
  E --> F
  F -->|Hop le| G[Tra JWT]
  F -->|Khong hop le| H[Tra loi 401]
```

### 10.3 UC2 - Chat hoi dap RAG (streaming)

```mermaid
flowchart LR
  A[Actor: User] --> B[Gui cau hoi]
  B --> C[POST /chat/stream]
  C --> D[Embed cau hoi]
  D --> E[Truy xuat top-k chunks]
  E --> F[Tao prompt tu context]
  F --> G[Goi LLM]
  G --> H[Stream token SSE ve frontend]
  H --> I[Luu session va messages]
```

### 10.4 UC3 - Quan ly lich su chat

```mermaid
flowchart LR
  A[Actor: User] --> B[Xem danh sach phien]
  B --> C[GET /chat/sessions]
  C --> D[Xem tin nhan cua phien]
  D --> E[GET /chat/sessions/{id}/messages]

  A --> F[Xoa 1 phien]
  F --> G[DELETE /chat/sessions/{id}]

  A --> H[Xoa toan bo lich su]
  H --> I[DELETE /chat/sessions]
```

### 10.5 UC4 - Upload tai lieu va cap nhat kho tri thuc

```mermaid
flowchart LR
  A[Actor: Admin] --> B[Upload file PDF/DOCX/TXT/JSON]
  B --> C[POST /documents/upload]
  C --> D[Parse noi dung file]
  D --> E[Chunking van ban]
  E --> F[Tao embedding]
  F --> G[Index vao Chroma]
  G --> H[Luu metadata vao DB]
```

### 10.6 UC5 - Van hanh tri thuc va quan tri he thong

```mermaid
flowchart LR
  A[Actor: Admin] --> B[Re-index tai lieu]
  B --> C[POST /documents/{id}/reindex]

  A --> D[Xoa tai lieu]
  D --> E[DELETE /documents/{id}]

  A --> F[Xem dashboard]
  F --> G[GET /admin/dashboard]

  A --> H[Xem chat logs]
  H --> I[GET /admin/chat-logs]

  A --> J[Xem/Sua cau hinh runtime]
  J --> K[GET/PUT /admin/config]
```

## 11. UML text (PlantUML) cho tung use case

### 11.1 Tong quan Use Case

```plantuml
@startuml
left to right direction
actor User
actor Admin

rectangle EduChatRAG {
  usecase "UC1 Dang nhap" as UC1
  usecase "UC2 Chat hoi dap RAG" as UC2
  usecase "UC3 Quan ly lich su chat" as UC3
  usecase "UC4 Upload + Index tai lieu" as UC4
  usecase "UC5 Van hanh quan tri" as UC5
}

User --> UC1
User --> UC2
User --> UC3

Admin --> UC1
Admin --> UC4
Admin --> UC5
@enduml
```

### 11.2 UC1 - Dang nhap

```plantuml
@startuml
left to right direction
actor "Admin/User" as Actor

rectangle Auth {
  usecase "Nhap thong tin dang nhap" as U1
  usecase "Xac thuc credentials" as U2
  usecase "Tra JWT" as U3
  usecase "Tra loi 401" as U4
}

Actor --> U1
U1 ..> U2 : <<include>>
U2 ..> U3 : <<extend>> [hop le]
U2 ..> U4 : <<extend>> [khong hop le]
@enduml
```

### 11.3 UC2 - Chat hoi dap RAG

```plantuml
@startuml
left to right direction
actor User

rectangle ChatRAG {
  usecase "Gui cau hoi" as U1
  usecase "Embed cau hoi" as U2
  usecase "Truy xuat top-k chunks" as U3
  usecase "Tao prompt" as U4
  usecase "Sinh cau tra loi LLM" as U5
  usecase "Stream SSE" as U6
  usecase "Luu session/messages" as U7
}

User --> U1
U1 ..> U2 : <<include>>
U2 ..> U3 : <<include>>
U3 ..> U4 : <<include>>
U4 ..> U5 : <<include>>
U5 ..> U6 : <<include>>
U6 ..> U7 : <<include>>
@enduml
```

### 11.4 UC3 - Quan ly lich su chat

```plantuml
@startuml
left to right direction
actor User

rectangle ChatHistory {
  usecase "Xem sessions" as U1
  usecase "Xem messages theo session" as U2
  usecase "Xoa 1 session" as U3
  usecase "Xoa toan bo sessions" as U4
}

User --> U1
User --> U2
User --> U3
User --> U4
@enduml
```

### 11.5 UC4 - Upload + Index tai lieu

```plantuml
@startuml
left to right direction
actor Admin

rectangle DocumentIngestion {
  usecase "Upload file" as U1
  usecase "Parse noi dung" as U2
  usecase "Chunking" as U3
  usecase "Tao embedding" as U4
  usecase "Index vao Chroma" as U5
  usecase "Luu metadata DB" as U6
}

Admin --> U1
U1 ..> U2 : <<include>>
U2 ..> U3 : <<include>>
U3 ..> U4 : <<include>>
U4 ..> U5 : <<include>>
U5 ..> U6 : <<include>>
@enduml
```

### 11.6 UC5 - Van hanh quan tri

```plantuml
@startuml
left to right direction
actor Admin

rectangle AdminOps {
  usecase "Re-index tai lieu" as U1
  usecase "Xoa tai lieu" as U2
  usecase "Xem dashboard" as U3
  usecase "Xem chat logs" as U4
  usecase "Xem/Sua config runtime" as U5
}

Admin --> U1
Admin --> U2
Admin --> U3
Admin --> U4
Admin --> U5
@enduml
```
