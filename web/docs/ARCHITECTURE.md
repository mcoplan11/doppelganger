# Architecture

## Overview

Web application that lets researchers buy credits and run AI-powered Qualtrics survey simulations.

## Services

```
┌─────────────────────┐     ┌─────────────────────┐
│   Next.js Frontend  │────▶│   FastAPI Backend    │
│   (Vercel)          │     │   (Railway)          │
└─────────────────────┘     └──────────┬──────────┘
                                        │
                        ┌───────────────┼───────────────┐
                        │               │               │
                   ┌────▼────┐  ┌───────▼──────┐ ┌──────▼─────┐
                   │ SQLite/ │  │ Gemini API   │ │ Qualtrics  │
                   │Postgres │  │ (shared key) │ │    API     │
                   └─────────┘  └──────────────┘ └────────────┘
```

## Key Design Decisions

- **Shared Gemini key**: App absorbs Gemini costs; users buy credits (1 credit = 1 participant).
- **User brings Qualtrics key**: Stored encrypted per-run, not persisted.
- **Magic link auth**: No passwords. Users enter email → get link → session cookie.
- **Async runs**: Simulations run as background tasks; frontend polls status.
- **Credits model**: Users buy packs via Stripe. Credits deducted when run completes (not when started, so failures don't penalize).

## Credit Pricing (v1)

| Pack | Credits | Price | Per-participant |
|------|---------|-------|-----------------|
| Starter | 50 | $4.99 | $0.10 |
| Standard | 100 | $8.99 | $0.09 |
| Pro | 250 | $19.99 | $0.08 |
| Research | 500 | $34.99 | $0.07 |

Gemini cost per participant ≈ $0.01–0.02 (batch mode, gemini-3.5-flash). Margin ≈ 4–9×.

## User Flow

1. Land on homepage → see pricing
2. Enter email → receive magic link
3. Click link → logged in, see dashboard
4. Buy credits via Stripe Checkout
5. Create run: paste Qualtrics survey URL, Qualtrics API key, n_participants
6. System auto-converts survey to AI-compatible copy
7. Smoke test (5 participants) before committing credits
8. Approve → full run starts in background
9. Poll status page → download CSV/JSON results when done
10. Credits deducted on completion

## Database Schema

```sql
users          (id, email, created_at)
sessions       (id, user_id, token, expires_at, created_at)
credits        (user_id, balance)
purchases      (id, user_id, stripe_session_id, credits, amount_cents, status, created_at)
runs           (id, user_id, survey_id, n_participants, status, credits_used, error, created_at, completed_at)
```

## Environment Variables

### Backend
```
DATABASE_URL          sqlite:///./app.db  (or postgres://...)
SECRET_KEY            random 32-byte hex
GEMINI_API_KEY        shared Gemini key
GEMINI_MODEL          gemini-3.5-flash
RESEND_API_KEY        for sending magic link emails
FROM_EMAIL            noreply@yourdomain.com
STRIPE_SECRET_KEY     sk_live_...
STRIPE_WEBHOOK_SECRET whsec_...
FRONTEND_URL          https://yourapp.vercel.app
QUALTRICS_DATACENTER  yul1
```

### Frontend (Next.js)
```
NEXT_PUBLIC_API_URL   https://your-backend.railway.app
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY  pk_live_...
```
