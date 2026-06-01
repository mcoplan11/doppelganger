# Local Development Setup

## Prerequisites
- Python 3.11 (via pyenv: `pyenv activate env_3.11.8`)
- Node.js 18+ (`node --version`)
- A Stripe account (free, test mode)
- A Resend account (free tier) OR leave blank to print links to console

---

## 1. Backend setup

```bash
cd web/backend

# Copy and fill in .env
cp .env.example .env
# Edit .env:
#   GEMINI_API_KEY   = your shared Gemini key
#   SECRET_KEY       = python -c "import secrets; print(secrets.token_hex(32))"
#   STRIPE_SECRET_KEY = sk_test_... (from Stripe dashboard)
#   STRIPE_WEBHOOK_SECRET = whsec_... (from Stripe CLI or dashboard)
#   RESEND_API_KEY   = re_... (leave blank to use console output)
#   FRONTEND_URL     = http://localhost:3000

# Install dependencies (in your pyenv virtualenv)
eval "$(pyenv init -)" && eval "$(pyenv virtualenv-init -)" && pyenv activate env_3.11.8
pip install -r requirements.txt

# Start backend
uvicorn main:app --reload --port 8000
```

The backend auto-creates `app.db` (SQLite) on first start.

---

## 2. Frontend setup

```bash
cd web/frontend

cp .env.local.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL = http://localhost:8000
#   NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY = pk_test_... (from Stripe dashboard)

npm install
npm run dev
```

Frontend runs at http://localhost:3000.

---

## 3. Stripe webhook (local testing)

Install Stripe CLI, then:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
# Copy the whsec_... printed and put it in backend .env as STRIPE_WEBHOOK_SECRET
```

---

## 4. Testing magic links locally

When `RESEND_API_KEY` is blank, the backend prints the magic link to its console.
Copy the link and open it in the browser — it will set the session cookie and redirect to /dashboard.

---

## 5. Verifying everything works

1. Open http://localhost:3000
2. Enter your email → see magic link in backend console
3. Visit the link → redirected to /dashboard
4. Click "Buy credits" → Stripe test checkout → come back with credits
5. Click "+ New simulation" → enter survey URL + your Qualtrics API token
6. Click "Smoke test" → watch status page update → download CSV

---

## Common issues

| Problem | Fix |
|---------|-----|
| SSL error calling Qualtrics | `truststore` is already imported in simulator_runner.py |
| "Not enough credits" on smoke test | Smoke tests are free — check `smoke_test: True` is being sent |
| Backend can't import simulator | Check `SIMULATOR_ROOT` in simulator_runner.py points to your qualtrics_ai directory |
| Stripe webhook fails | Run `stripe listen` and make sure STRIPE_WEBHOOK_SECRET matches |
