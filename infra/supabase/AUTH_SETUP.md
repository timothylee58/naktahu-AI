# Supabase Auth setup

This guide configures Supabase Auth for the FastAPI backend (`apps/api`), which validates access tokens with **`JWT_SECRET`** (Supabase **JWT Secret**, not the anon key).

## 1. Enable Google OAuth

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project → **Authentication** → **Providers**.
2. Open **Google** and toggle **Enable Sign in with Google**.
3. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create **OAuth 2.0 Client IDs** (type **Web application**).
4. Copy **Client ID** and **Client Secret** into the Supabase Google provider fields.
5. Save the provider settings.

## 1b. Enable Microsoft (Azure) OAuth

1. Supabase → **Authentication** → **Providers** → **Azure** → enable.
2. [Azure Portal](https://portal.azure.com/) → **Microsoft Entra ID** → **App registrations** → **New registration**:
   - **Redirect URI** (Web): `https://khmezwofokrbuoaxrsii.supabase.co/auth/v1/callback`
   - Pick **Supported account types** (personal Microsoft accounts and/or work/school).
3. Copy **Application (client) ID** + create a **Client secret** → paste into Supabase Azure provider.
4. **Fix `Error getting user email from external provider`:**
   - Azure app → **Token configuration** → **Add optional claim** → Token type **ID** → check **email** → Save.
   - **API permissions** → **Microsoft Graph** → **User.Read** (delegated) → Grant admin consent if required.
5. Single-tenant apps: set Supabase Azure **Tenant URL** to your directory tenant ID.

The web app requests scopes `email openid profile offline_access` (`AuthButton.tsx`).

## 2. Redirect URLs

Supabase → **Authentication** → **URL Configuration**.

Add **Redirect URLs** (exact paths depend on your client; include both dev and prod):

| Environment | Example redirect URL |
|-------------|----------------------|
| Local Next.js | `http://localhost:3000/**` (or your app route that handles the auth callback, e.g. `http://localhost:3000/auth/callback`) |
| Production (Netlify) | `https://naktahu.netlify.app/**` and `https://naktahu.netlify.app/auth/callback` |
| Production (Vercel) | `https://<your-project>.vercel.app/**` or your custom domain callback route |

Also set **Site URL**:

- Local: `http://localhost:3000`
- Production: `https://naktahu.netlify.app` (or your custom domain)

If **Site URL** is still `http://localhost:3000` in production, OAuth failures redirect to localhost and show browser security errors.

Use the same paths your frontend passes to `signInWithOAuth({ options: { redirectTo: ... } })` (or equivalent).

## 3. Email confirmation

1. **Authentication** → **Providers** → **Email**.
2. Enable **Confirm email** (required confirmations before session is fully trusted).
3. Optionally customize templates under **Authentication** → **Email Templates**.
4. For local testing, you can use [Inbucket](https://supabase.com/docs/guides/local-development/customizing-email-templates) with Supabase CLI or rely on dashboard **Authentication** → **Users** to confirm manually.

## 4. JWT secret for the API

1. **Project Settings** → **API** → **JWT Secret** (legacy JWT signing secret for HS256 tokens).
2. Set the same value in `apps/api` as **`JWT_SECRET`** so `services/auth.py` can verify Bearer tokens.

The API expects audience **`authenticated`** by default (`SUPABASE_JWT_AUD`).

## 5. Database: `user_sessions`

Create a table for persisted history (matches `services/history.py` inserts):

```sql
create table if not exists public.user_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  query text not null,
  language text not null default 'en',
  domain text not null default 'general',
  response_summary text not null,
  citations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.user_sessions enable row level security;

-- Service role bypasses RLS; optional policies for direct client reads can be added later.
```

Use the **service role** key only on the server (`SUPABASE_SERVICE_KEY`); never expose it to the browser.
