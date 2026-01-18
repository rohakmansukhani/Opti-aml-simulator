# The Easiest Way to Deploy (Managed Services)

If you want the absolute easiest process with automated updates, use **Vercel** for the frontend and **Railway** or **Render** for the backend/worker.

## 1. Frontend (Vercel) - 2 Minutes
Vercel is the creator of Next.js and provides the best experience.
1. Sign in to [Vercel.com](https://vercel.com) with GitHub.
2. Click **"Add New"** -> **"Project"** -> Import your repository.
3. **Configuration**:
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend`
   - **Environment Variables**: 
     - `NEXT_PUBLIC_SUPABASE_URL`
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
     - `NEXT_PUBLIC_API_URL`: Your backend URL (e.g., `https://...railway.app`)

## 2. Backend & Worker (Railway/Render)
Managed services can run both your API and your Celery worker using the `Dockerfile`.

### Critical Environment Variables (Backend)
Regardless of the platform, you **must** set these:
- `DATABASE_URL`: Use the **Supabase IPv4 Pooler** string (Port 6543) with `?pgbouncer=true`.
- `ALLOWED_ORIGINS`: Set this to your Vercel URL (e.g., `https://opti-aml-simulator.vercel.app`).
- `REDIS_URL`: Your Upstash or Railway Redis URL.

### Railway Setup
1. Click **"New"** -> **"GitHub Repo"** -> Import repository.
2. Railway will detect the Dockerfile.
3. To add the Worker, add a **"New"** service from the same repo and change the **Start Command** to:
   `celery -A tasks worker --loglevel=info`

---

> [!CAUTION]
> **CORS Blockers**: If your frontend can't talk to the backend, double-check that `ALLOWED_ORIGINS` in the backend exactly matches your Vercel URL (no trailing slash).

> [!IMPORTANT]
> **Database Host**: If you see `Network is unreachable`, it means you are using an IPv6 address. Ensure your `DATABASE_URL` hostname is the pooler (e.g., `aws-0-...pooler.supabase.com`).
