# AI Developer Assistant — Project-Aware GenAI Workspace

An enterprise-grade, project-aware developer workspace that ingests source codebases and uses Retrieval-Augmented Generation (RAG) powered by LangChain, FAISS, and Google Gemini to answer questions with grounded source-file references and verified line ranges.

---

## 1. System Architecture & Technology Stack

* **Frontend**: React 19, JavaScript (ES2022), Vite, Monaco Editor (`@monaco-editor/react`), Lucide React, Vanilla CSS Design System.
* **Backend**: Python 3.12, Flask 3.1 REST API, Flask-SQLAlchemy, PyMySQL, Cryptography, LangChain, FAISS-CPU.
* **Vector Store**: FAISS vector indices partitioned per-project with exact line number offsets and atomic directory swap to prevent partial writes.
* **Relational Database**: MySQL 8.0 (with automatic local dev fallback to SQLite if MySQL is unconfigured).
* **AI Orchestration**: LangChain + Google Gemini API (`gemini-2.5-flash` & `models/text-embedding-004` via the official `google-genai` Python SDK).
* **Repository Ingestion**: Sandboxed `.zip` extraction pipeline and GitHub REST API zipball fetcher with SSRF guards.

```
AI Developer Assistant/
├── backend/
│   ├── app/
│   │   ├── models/            # User, Project, ProjectFile, IndexingJob, Conversation, Message, GitHubImport
│   │   ├── routes/            # Auth, Projects, Files, RAG, GitHub, AI, Health Blueprints (/api/v1)
│   │   ├── services/          # IngestionService, ChunkingService, VectorService, RAGService,
│   │   │                      # GitHubService, GeminiService, DevToolsService, ProjectRepository
│   │   ├── utils/             # Security sanitization, ignore filters, auth decorator, logger
│   │   ├── config.py          # App configuration and environment loader
│   │   ├── database.py        # SQLAlchemy & Flask-Migrate bindings
│   │   └── __init__.py        # App factory, database initialization, and CORS configuration
│   ├── migrations/            # Alembic database migrations (Flask-Migrate)
│   ├── storage/projects/      # Isolated sandbox for project source files & FAISS indexes
│   ├── tests/                 # Comprehensive pytest test suite (141 unit & integration tests)
│   ├── requirements.txt
│   ├── schema.sql             # Canonical MySQL 8.0 DDL schema
│   ├── run.py                 # Backend entrypoint (port 5000)
│   ├── .env.example           # Backend environment template
│   └── .env                   # Local backend environment
│
├── frontend/
│   ├── src/
│   │   ├── components/        # FileTree, EditorView (Monaco), AiPanel, ChatPanel,
│   │   │                      # UploadPanel, GitHubImportPanel, SemanticSearchTab,
│   │   │                      # CodeReviewTab, TestGeneratorTab, ReadmeGeneratorTab
│   │   ├── context/           # AuthContext, ProjectContext
│   │   ├── pages/             # LoginPage, RegisterPage, DashboardPage, WorkspacePage
│   │   ├── services/          # REST API clients (api, authApi, projectApi, fileApi, ragApi, githubApi, aiApi)
│   │   ├── styles/            # Curated dark-theme design tokens and workspace CSS
│   │   └── App.jsx            # Router and top-level workspace orchestrator
│   ├── package.json
│   └── vite.config.js         # Port 3000 with /api proxy to Flask port 5000
│
├── .env.example               # Root environment template
├── .gitignore
└── README.md
```

---

## 2. Core Features

1. **Authentication & Authorization Lifecycle**:
   - Secure registration, login, profile retrieval (`/api/v1/auth/me`), and logout.
   - Dual-mode JWT authentication: HttpOnly `SameSite=Lax` cookies for browser security plus `Authorization: Bearer <token>` support for automated clients.
   - Strict project ownership validation enforced on every protected route.

2. **Project Management & Workspaces**:
   - Create, list, rename, and delete projects.
   - Real metrics (total projects, file counts, chunk counts) without fabricated statistics.

3. **Sandboxed Codebase Ingestion**:
   - **ZIP Upload**: Validates ZIP integrity, enforces file count & size bounds, rejects symlinks, absolute paths, and path traversal sequences (`..`).
   - **Automatic Chunking & Indexing**: Ingested files are filtered against ignore lists, parsed into line-bounded chunks, and immediately indexed into FAISS.
   - **Monaco Code Editor**: Browse the source tree, open files with syntax highlighting, and edit/save code directly back to the project filesystem.

4. **GitHub Repository Import**:
   - Validate and fetch metadata from public GitHub repositories using the GitHub REST API.
   - Download zipballs, unpack into the project source sandbox, parse files, chunk code, and index vectors without requiring local `git` CLI binaries.
   - Strict SSRF defense: host strictly restricted to `github.com`.

5. **Project-Aware RAG Chat**:
   - Ask natural-language questions about the codebase.
   - Answers are grounded strictly in retrieved chunks from the project FAISS index.
   - Traceable source citations (`file_path:start_line-end_line`) with one-click navigation that opens the target file in Monaco and highlights the exact line range.
   - Threaded conversation history with persistent database storage.

6. **Semantic Codebase Search**:
   - Natural-language similarity search over indexed code vectors.
   - Displays relevance percentages, line ranges, and syntax snippets.
   - Honest status reporting for unindexed projects or empty queries.
   - Clicking a search result jumps directly to the file and line range in Monaco.

7. **AI Code Review**:
   - Reviews active editor files or selected snippets across 5 categories: Correctness, Security, Performance, Maintainability, and Error Handling.
   - Structured findings with severity rating (`critical`, `high`, `medium`, `low`), verified line ranges, explanation, and remediation advice.
   - Distinguishes verified observations from potential risks.

8. **Test-Case Generator**:
   - Automatically detects the testing framework (`pytest`, `unittest`, `jest`, `mocha`, `vitest`) with manual override.
   - Generates categorized test scenarios: Happy Path, Edge Cases, Invalid Inputs, and Failure Scenarios.
   - Tests are displayed separately from original source files with Copy and Download options.
   - Explicit disclaimer that generated tests are not automatically executed.

9. **README & Documentation Generator**:
   - Scans project manifests (`package.json`, `requirements.txt`, `Dockerfile`, etc.) and retrieved RAG context.
   - Formulates structured documentation covering purpose, architecture, setup, environment configuration, and API endpoints.
   - Strict grounding: unknown details are explicitly marked with `[Unknown: Not specified in repository files]` to eliminate hallucinations.
   - Automatic secret redaction strips API keys, tokens, and passwords from generated outputs.
   - Preview with Markdown rendering, Copy, Download, and "Save to Project" actions.

10. **Manual Reindexing with Atomic Staging**:
    - Trigger reindexing at any time via `POST /api/v1/projects/<id>/index` or `POST /api/v1/rag/<id>/index`.
    - Uses temporary staging directory swap to guarantee that failed indexing runs do not corrupt existing indices or retain deleted files.

---

## 3. Security Architecture & Controls

* **Untrusted Code Execution Boundary**: Source code uploaded, imported, or generated is treated strictly as static text data and is never executed or compiled by the server.
* **Path Traversal Guards**: Every file access is validated with `is_safe_path()` ensuring that resolved paths never escape the project's sandboxed `storage/projects/proj_<id>/source` directory.
* **Archive Decompression Safety**: ZIP uploads enforce entry count caps (max 10,000 entries), total uncompressed size limits (max 500 MB), per-file size limits (max 10 MB), and explicitly reject Unix symlinks.
* **SSRF Protection**: GitHub import endpoints parse and validate repository URLs against an allowlist containing only official `github.com` and `www.github.com` hosts with alphanumeric repository paths.
* **Secret Redaction**: Environment files (`.env`, `.env.*`), private keys (`*.pem`, `id_rsa`), and credentials are automatically excluded during ingestion. In addition, regex secret sanitization redacts key strings before AI prompts are submitted.
* **CORS & CSRF**: Configured with explicit allowed origins (`ALLOWED_ORIGINS`) and `supports_credentials=True`. Wildcard origins are rejected for credentialed requests.
* **Storage Isolation**: FAISS indices and project sources are stored outside public web roots and partitioned by project ID.

---

## 4. Local Development Setup

### Prerequisites
* Python 3.12+
* Node.js 18+ and npm
* MySQL 8.0+ (optional; SQLite fallback is activated automatically for local development)

### Backend Setup
1. Navigate to the backend directory and activate the virtual environment:
   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   ```
2. Install Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configure environment variables in `backend/.env`:
   ```ini
   PORT=5000
   FLASK_ENV=development
   SECRET_KEY=dev-secret-key-ai-assistant-2026
   JWT_SECRET_KEY=dev-secret-key-ai-assistant-2026

   # MySQL Settings (or leave default for local SQLite fallback)
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_NAME=ai_developer_assistant
   DB_USER=root
   DB_PASSWORD=

   # Google Gemini API Key (acquire from https://aistudio.google.com/)
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-2.5-flash

   STORAGE_DIR=storage/projects
   ```
4. Start the backend development server:
   ```powershell
   python run.py
   ```
   The backend will start on `http://127.0.0.1:5000`.

### Frontend Setup
1. Open a new terminal and navigate to the frontend directory:
   ```powershell
   cd frontend
   npm install
   ```
2. Start the Vite development server:
   ```powershell
   npm run dev
   ```
3. Open `http://localhost:3000` in your browser.

---

## 5. Verification & Testing

### Backend Test Suite
Run the full pytest test suite covering authentication, ZIP validation, GitHub import, chunking, FAISS vector indexing, Gemini error fallbacks, code review, test generator, documentation generator, and project isolation:

```powershell
cd backend
.\venv\Scripts\pytest tests/
```
*Current Result*: **141 passed** (100% passing across 11 test modules).

### Frontend Production Build
Validate that all React JSX components, CSS styles, and assets bundle cleanly:

```powershell
cd frontend
npm run build
```
*Current Result*: **2,156 modules transformed, zero build errors**.

---

## 6. Production Deployment Preparation

### Environment Variables
Configure the following production variables in your production environment or secret manager:

| Variable | Description | Example / Default |
|---|---|---|
| `FLASK_ENV` | Application environment | `production` |
| `PORT` | Backend HTTP port | `5000` |
| `SECRET_KEY` | Cryptographic secret for session signing | High-entropy random string |
| `JWT_SECRET_KEY` | Secret for HMAC-SHA256 JWT tokens | High-entropy random string |
| `BACKEND_URL` | Public API URL of backend | `https://api.yourdomain.com` |
| `FRONTEND_URL` | Public origin of frontend | `https://app.yourdomain.com` |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed CORS origins | `https://app.yourdomain.com` |
| `COOKIE_SECURE` | Enforces HTTPS-only cookies | `true` |
| `DB_HOST` | MySQL database host | `127.0.0.1` |
| `DB_PORT` | MySQL database port | `3306` |
| `DB_NAME` | MySQL database name | `ai_developer_assistant` |
| `DB_USER` | MySQL database user | `app_user` |
| `DB_PASSWORD` | MySQL database password | Database password |
| `GEMINI_API_KEY` | Google Gemini API key | Google AI Studio key |
| `GEMINI_MODEL` | Gemini LLM model | `gemini-2.5-flash` |
| `GEMINI_EMBEDDING_MODEL` | Embedding model | `models/text-embedding-004` |
| `STORAGE_DIR` | Path to persistent storage mount | `/var/data/ai_assistant/projects` |
| `GITHUB_API_TOKEN` | Optional GitHub personal access token | `ghp_...` |

### Database Migrations
For production MySQL, initialize the database using either:
```bash
# Method A: Direct SQL script execution
mysql -u root -p ai_developer_assistant < backend/schema.sql

# Method B: Flask-Migrate (Alembic)
cd backend
flask db upgrade
```

### Durable Storage & Persistence Considerations
> **Critical Production Note**:
> Project source code trees and FAISS vector index files are stored on disk under `STORAGE_DIR` (`proj_<id>/source` and `proj_<id>/faiss_index`).
> - In containerized or serverless deployments (Docker, Kubernetes, AWS ECS, Google Cloud Run), **do not use ephemeral container storage**. Mount a persistent volume (e.g., AWS EBS, AWS EFS, GCP Persistent Disk, or Azure Files) to `STORAGE_DIR`.
> - If storage is rebuilt or transferred, the database retains all file metadata and project structures. Triggering `POST /api/v1/projects/<id>/index` will automatically re-chunk and rebuild the FAISS vector index from the stored source files.

### Production WSGI Startup Command
Run the backend using a production WSGI server such as Gunicorn:
```bash
cd backend
gunicorn --workers 4 --bind 0.0.0.0:5000 --timeout 120 "run:app"
```

### Health Check Endpoint
Automated load balancers and orchestrators can query the health endpoint:
* `GET /api/v1/health`
* Returns HTTP `200 OK` with JSON status:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-10-10T12:00:00Z",
    "database": { "status": "connected" },
    "ai_service": { "configured": true, "model": "gemini-2.5-flash" }
  }
  ```

---

## 7. Known Limitations

1. **GitHub API Rate Limits**: Unauthenticated GitHub import requests are limited to 60 requests per hour by GitHub. Supplying a `GITHUB_API_TOKEN` increases this limit to 5,000 requests per hour.
2. **Private Repositories**: Repository import currently targets public repositories. For private repositories, upload via the secure `.zip` upload feature.
3. **Polyglot Monorepos**: Automated test framework detection inspects manifest files in repository roots. For multi-language repositories with sub-packages, developers can manually select their target testing framework in the UI dropdown.
