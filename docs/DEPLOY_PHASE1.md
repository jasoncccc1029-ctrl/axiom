# Axiom Phase-1 Deploy（不用自己買 VPS）

目標：用 **Railway（後端 + Postgres）** + **Vercel（前端）** + **Gemini/OpenAI Brain**，
讓任何人用網址開啟 Axiom，不必連你的本機。

Phase-1 仍是**單一預設學生**（`default_user_id=1`）。完整多用戶登入留到下一階段。

---

## 0. 前置

- GitHub 上已有 `jasoncccc1029-ctrl/axiom`（public）
- 準備好 **Gemini** 或 **OpenAI** API key（雲端不要跑 Ollama）
- 註冊 [Railway](https://railway.app) 與 [Vercel](https://vercel.com)（可用 GitHub 登入）

---

## 1. Railway：後端 + Postgres

1. New Project → **Deploy from GitHub** → 選 `axiom`
2. 服務設定 **Root Directory = `backend`**（推薦；用 Nixpacks 跑 `Procfile` / uvicorn）  
   或用 repo 根目錄 + `backend/Dockerfile`（見根目錄 `railway.toml`）
3. **Add Plugin → PostgreSQL**
4. 在後端服務 Variables 設定：

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
AI_PROVIDER=gemini
GEMINI_API_KEY=你的key
GEMINI_MODEL=gemini-2.5-flash
VISION_PROVIDER=mock
DEBUG=false
ACCESS_TOKEN=自己想一組長密碼
CORS_ORIGINS=https://你的前端.vercel.app
```

（若用 OpenAI：改 `AI_PROVIDER=openai` + `OPENAI_API_KEY`）

5. 產生公開網域：Settings → Networking → **Generate Domain**  
   記下來，例如：

```text
https://axiom-production-xxxx.up.railway.app
```

6. 確認健康檢查：

```text
https://你的後端網域/health
```

應回 `status: ok`。

---

## 2. Vercel：前端

1. Import GitHub repo `axiom`
2. Root Directory 設為：

```text
frontend
```

3. Framework：Next.js（自動）
4. Environment Variables：

```text
API_PROXY_TARGET=https://你的後端網域
NEXT_PUBLIC_AXIOM_ACCESS_TOKEN=與後端 ACCESS_TOKEN 相同
```

不要把 `GEMINI_API_KEY` / `OPENAI_API_KEY` 放到 Vercel。

5. Deploy 完成後得到：

```text
https://xxx.vercel.app
```

6. 回到 Railway，把 `CORS_ORIGINS` 更新成這個 Vercel 網址（若你改用 `NEXT_PUBLIC_API_BASE` 直連 API 才必須；走 rewrite 代理時仍建議設上）。

---

## 3. 本機驗證（可選）

```powershell
cd C:\Users\Jason\studyos\backend
.\.venv\Scripts\pip.exe install -r requirements.txt
# 本機可繼續用 SQLite；雲端才用 Postgres
```

前端：

```powershell
cd C:\Users\Jason\studyos\frontend
copy .env.example .env.local
npm run dev
```

---

## 4. 使用方式

開 Vercel 網址即可。API 經 Next rewrite 轉到 Railway，瀏覽器不必打後端網域。

若設了 `ACCESS_TOKEN`，前端需有對應的 `NEXT_PUBLIC_AXIOM_ACCESS_TOKEN`（或瀏覽器 `localStorage.axiom_access_token`）。

---

## 5. Phase-1 刻意不做

- 多用戶註冊／OAuth
- Ollama / 本機 Vision 上雲
- 多實例 + 共用上傳磁碟（上傳檔在 Railway 磁碟可能重啟後消失；教材文字已進 DB 仍可用）

下一階段再加：真正登入、物件儲存（R2/S3）、佇列。
