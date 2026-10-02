# Development

Use Python 3.12 and Node.js 20 or newer.

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Run deterministic tests from the repository root with `pytest -q`; they do
not require Ollama. Enable live model tests only when both configured models
already exist:

```powershell
$env:RUN_OLLAMA_TESTS="true"
pytest -q
```

Run `npm run build` for frontend type checking and production compilation.
