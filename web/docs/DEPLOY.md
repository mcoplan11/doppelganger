# Deployment

## Backend → Railway

1. Create a Railway account at railway.app
2. "New Project" → "Deploy from GitHub repo" → select this repo
3. Set the root directory to `web/backend`
4. Railway auto-detects Python; set start command:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. Add environment variables (same as .env.example, with production values):
   - `DATABASE_URL` = Railway's Postgres plugin URL (add the Postgres plugin first)
   - `SECRET_KEY` = new random 32-byte hex
   - `GEMINI_API_KEY` = your production Gemini key
   - `STRIPE_SECRET_KEY` = sk_live_...
   - `STRIPE_WEBHOOK_SECRET` = whsec_... (from Stripe → Webhooks → add endpoint)
   - `RESEND_API_KEY` = re_... (from resend.com)
   - `FROM_EMAIL` = noreply@yourdomain.com (must be a verified sender in Resend)
   - `FRONTEND_URL` = https://your-app.vercel.app

6. Add Railway Postgres plugin, copy `DATABASE_URL` into env vars.

7. Backend URL will be something like `https://your-app.up.railway.app`.

### Stripe webhook endpoint (production)
In Stripe Dashboard → Developers → Webhooks:
- Endpoint URL: `https://your-app.up.railway.app/webhooks/stripe`
- Events: `checkout.session.completed`
- Copy the signing secret → `STRIPE_WEBHOOK_SECRET`

---

## Frontend → Vercel

1. Push this repo to GitHub
2. Go to vercel.com → New Project → import repo
3. Set framework: Next.js, root directory: `web/frontend`
4. Add environment variables:
   - `NEXT_PUBLIC_API_URL` = https://your-backend.up.railway.app
   - `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` = pk_live_...
5. Deploy.

---

## Switching to Postgres (production)

When `DATABASE_URL` starts with `postgresql://`, SQLAlchemy automatically uses
Postgres instead of SQLite. No code changes needed.

Install psycopg2 on Railway by adding to requirements.txt:
```
psycopg2-binary==2.9.10
```

---

## Custom domain

- Railway: Settings → Networking → Custom Domain
- Vercel: Settings → Domains → Add

Set `FRONTEND_URL` on the backend to your Vercel custom domain, and update
the `CORS` origins in `main.py` if needed.

---

## Scaling runs

Currently, simulations run as FastAPI `BackgroundTasks` (same process, thread-based).
This works fine for up to ~10 concurrent runs. For higher scale:

1. Move to Celery + Redis (add to requirements, swap `background_tasks.add_task` for `.delay()`)
2. Railway has a Redis plugin — add it and set `REDIS_URL`

This is a future-you problem. Background tasks are fine for launch.
