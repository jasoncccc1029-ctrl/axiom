# Axiom v1.3.2 — Personalized AI Learning Agent

**開發歷程（GitHub Pages）：**  
https://jasoncccc1029-ctrl.github.io/axiom/

**Phase-1 雲端上線（Railway + Vercel，不用自管 VPS）：**  
見 [`docs/DEPLOY_PHASE1.md`](docs/DEPLOY_PHASE1.md)

Axiom **不是** ChatGPT clone，也不是「選 GPT／Claude 來聊天」。

```text
Axiom = Student Model + Memory + Context + Policy + Agent + Learning Loop
Model  = Brain（可替換：Ollama / OpenAI / Gemini …）
```

核心價值：越用越懂學習者（掌握度、錯因、歷史），並用該理解決定 **如何** 用 AI 教學。
文字／圖片／PDF → 可確認的學習問題 → 工具驗證 → 依真實紀錄調整（Observe → Understand → Adapt → Teach）。

核心技術：Next.js 15、TypeScript、Tailwind CSS、FastAPI、Python 3.12、
SQLite、SQLAlchemy；本機預設 Brain 為 Ollama `llama3.2:latest`，Vision 為 `moondream:latest`。

## Installation

### 前置需求

- Node.js 20+
- Python 3.12+（建議；避免 3.14 需從原始碼編譯部分套件）
- Git
- [Ollama](https://ollama.com)
- 已確認存在的 `llama3.2:latest`、`moondream:latest`

Backend:

```bash
cd backend
py -3.12 -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Frontend:

```bash
cd frontend
npm install
```

## Development

在 `backend/`：

```bash
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康檢查：

```bash
curl http://127.0.0.1:8000/health
```

API docs：http://127.0.0.1:8000/docs

在另一個 terminal 執行 `cd frontend; npm run dev`，開啟
http://localhost:3000。API docs 位於 http://127.0.0.1:8000/docs。

## Ollama setup

安裝並啟動 Ollama（`ollama serve`），再確認模型存在。Axiom 不會自動下載或更換大型模型：

```bash
ollama list
```

確認 API：

```bash
curl http://127.0.0.1:11434/api/tags
```

複製 `backend/.env.example` 為 `backend/.env`。重要設定：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:latest
AI_PROVIDER=ollama
VISION_PROVIDER=ollama
OLLAMA_VISION_MODEL=moondream:latest
MAX_AGENT_STEPS=6
MAX_UPLOAD_SIZE=20971520
```

若 Ollama 未啟動，API／UI 會明確顯示：`Ollama 未啟動，請執行 ollama serve。`  
若模型不存在：`找不到 llama3.2:latest，請先執行 ollama pull llama3.2:latest.`

完整設定與 timeout、chunk、sandbox 限制見 `.env.example`。不要提交
`.env` 或 secrets。

## Testing

在專案根目錄 `studyos/`：

```bash
.\backend\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

可選：真實 Ollama integration：

```powershell
$env:RUN_OLLAMA_TESTS='true'
pytest -q
```

一般測試不要求 Ollama。只有 `RUN_OLLAMA_TESTS=true` 才執行本機模型整合測試。

## Architecture

```text
API -> Application Services -> Agent Core -> Providers / Tools -> Infrastructure
```

`ModelProvider` 與 `VisionProvider` 分離。Agent 有 bounded Planner、
ToolRouter、ContextBuilder、Verifier 與 AdaptiveTutor。教材 ingestion 使用
可替換的 `EmbeddingProvider`、`VectorStore`、`Retriever`；第一版採 SQLite
與 local hash embedding，不下載新模型。

主要 API：`/api/chat`、`/api/vision/analyze`、`/api/materials/upload`、
`/api/problems/solve`、`/api/agent/run`、`/api/learning/record`、
`/api/progress`、`/api/recommendations`、`/api/agent/{trace_id}`。
Student Model 查詢：`/api/student`、`/api/topics`、`/api/mastery`、
`/api/memory`。
舊 `/api/solve` 保留相容。

## Security

Upload 會驗證 MIME/magic、大小、UUID 路徑與 traversal。文件與 user input
都是 untrusted；工具結果為 semi-trusted。MathTool 不 eval user input。
PythonTool 是受限 AST interpreter，禁止 import、attribute、filesystem、
network、subprocess、OS 與 shell。

## Documentation

詳細設計見 `docs/architecture.md`、`agent.md`、`vision.md`、`rag.md`、
`tools.md`、`verifier.md`、`memory.md`、`adaptive-learning.md`、
`database.md`、`development.md`。

## Troubleshooting

- `Ollama 未啟動`：執行 `ollama serve`。
- `找不到模型`：先用 `ollama list` 確認；不要自行更換模型。
- Vision confidence 低：在 Tutor 的 Problem Confirmation 修正文字。
- PDF 顯示 `failed`：確認檔案 magic、大小、頁數及是否加密。
- 無推薦或趨勢：系統顯示 `Not enough data yet.`，不產生假資料。

## License

Private / educational prototype.
