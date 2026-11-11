# Shivansh Raghuvanshi — Engineering Portfolio

A responsive React/TypeScript portfolio with a FastAPI backend. It combines live GitHub data, EIVA AI features, a read-only SQL sandbox, a parameterized-query security demo, contact delivery, and an honest CI status dashboard.

## Requirements

- Node.js 22.12+ and npm (Node 24 recommended)
- Python 3.10+
- Optional OpenAI API key for EIVA
- Optional SMTP credentials for contact delivery
- Optional GitHub owner/repository for Actions status
- A server-side `PAT_1` GitHub token for contribution statistics

## Run locally

1. Install frontend dependencies from the lockfile: `npm ci`.
2. Copy `.env.example` to `.env` and set any available public profile details.
3. Run `npm run dev` from the project root.
4. In a second terminal, enter `backend`, create and activate a virtual environment, then run `pip install -r requirements-dev.txt`.
5. Copy `backend/.env.example` to `backend/.env`. Configure `OPENAI_API_KEY`, `PAT_1`, and `GITHUB_REPOSITORY=owner/repository` if available.
6. From `backend/`, run `uvicorn main:app --reload --port 8000`.

Frontend: http://localhost:5173. API health: http://localhost:8000/api/health. OpenAPI Swagger UI: http://localhost:8000/docs. Without backend services, their UI modules report unavailable states rather than mock results.

## Engineering modules

- **Recruiter mode:** concise experience/education/skills view, browser speech synthesis overview, downloadable PDF resume, and browser print-to-PDF.
- **EIVA:** portfolio assistant, mock interview, and repository explanation. The backend requires `OPENAI_API_KEY`; explanations only use selected public repository metadata.
- **GitHub:** authenticated server-side profile and contribution statistics, public repository/language data, and recent public events. Contribution totals and streaks follow GitHub's calendar and attribution rules.
- **Live demos:** links only to HTTPS deployment URLs listed in real public repository metadata. Empty state appears when there are no deployment URLs.
- **Architecture map:** interactive overview of the browser, GitHub, FastAPI, SQLite, OpenAI, SMTP, and Actions connections used by this portfolio.
- **SQL playground:** fresh in-memory SQLite database per request. It contains fictional tutorial rows in `sample_products` and `sample_orders`, allows read-only `SELECT`/`WITH`, limits results to 100 rows, and stops long-running queries after 350 ms.
- **REST explorer:** loads the running FastAPI OpenAPI schema and links to Swagger UI at `/docs`.
- **Testing/CI:** GitHub Actions runs backend pytest and pip-audit checks, frontend type checking, npm audit, and a production build. `.github/workflows/refactoring.yml` runs the same focused checks for changes to application code. The dashboard fetches actual workflow and job status from GitHub Actions.
- **Cybersecurity demo:** a real parameterized SQL lookup against the fictional sample database. The injection test string is treated as data; no vulnerable query is executed.
- **Problem solving:** executes binary search against the entered sorted integer list and reports measured comparisons alongside O(log n) time and O(1) space.
- **Analytics:** downloads the public Iris CSV from the seaborn-data repository and computes species counts and mean petal length from the downloaded rows. No cached/fabricated metrics are displayed.
- **Credentials:** only renders verified credentials configured in `src/config.ts`. It is intentionally empty until issuer and verification URL details are supplied.

## Tests

From `backend/`, install `requirements-dev.txt`, then run `python -m pytest -q` and `python -m pip_audit -r requirements.txt`. The tests cover health, CORS, SQL read-only restrictions, safe parameterized lookup behavior, GitHub contribution streak calculations, pagination, retries, caching, missing credentials, CI status handling, and rate-limit cleanup. GitHub Actions runs these checks on pushes and pull requests.

## Configuration

Frontend public configuration is in `src/config.ts`. Optional `.env` values include `VITE_LINKEDIN_URL`, `VITE_CONTACT_EMAIL`, `VITE_PROFILE_IMAGE`, `VITE_API_URL`, and `VITE_GITHUB_REPOSITORY`.

Backend configuration lives in `backend/.env`:

- `OPENAI_API_KEY` and `OPENAI_MODEL` for EIVA (model defaults to `gpt-4o-mini`).
- `GITHUB_REPOSITORY=owner/repository` to read the latest `.github/workflows/ci.yml` run and job results. It defaults to the verified public portfolio repository `Ryoishin/Inventory`; override it if this code is published elsewhere. `GITHUB_TOKEN` is optional and backend-only.
- `PAT_1` for the server-side GitHub GraphQL request used by `/api/github/stats`. Use a token owned by `Ryoishin` with the minimum `read:user` permission needed for contribution data. Do not put this value in a `VITE_` variable, the frontend, or source control. The API caches successful responses for 15 minutes and can serve a clearly marked last-good snapshot for up to 6 hours when GitHub is unavailable.
- `CONTACT_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` to deliver contact form messages.
- `FRONTEND_ORIGIN` for the allowed CORS origin list.

Never put OpenAI or GitHub secrets in a `VITE_` variable or frontend source. `GITHUB_TOKEN` for Actions status and `PAT_1` for statistics are separate backend-only settings.

## Production deployment

- This repository's `vercel.json` routes `/api/*` requests to the FastAPI backend service and all other routes to the Vite app. Deploy the repository to Vercel with both services enabled.
- In Vercel, open **Project Settings → Environment Variables** and add `PAT_1` with a token for the `Ryoishin` account. Enable it for **Production**, **Preview**, and **Development** as needed. Keep it server-side; do not name it `VITE_PAT_1`.
- After saving or changing `PAT_1`, redeploy the relevant Vercel environment so the backend function receives the new value. The dashboard displays a retry action and a professional unavailable state until the variable is configured.
- For local development, set `PAT_1` in `backend/.env`; do not commit that file. For a non-Vercel host, configure the same variable in the backend service environment.
- To deploy elsewhere, build the frontend with `npm run build`, deploy `dist/`, and set `VITE_API_URL` to the API origin. Deploy `backend/` as a Python web service, install `backend/requirements.txt`, and start it with `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Configure the host to serve `index.html` for frontend fallback routes.
- The API uses in-memory per-IP rate limits. For multi-instance production, also configure rate limiting at the trusted proxy/platform layer.
- GitHub GraphQL data requires `PAT_1`; transient failures are retried with bounded backoff. The dashboard uses an in-memory cache per backend instance, so serverless cold starts may require a fresh upstream request.
- `total_commits` is GitHub's contribution-calendar commit count, not a raw count of every commit in all repositories. Language rankings aggregate GitHub-reported code bytes for original public repositories; forks are excluded from stars and language totals.
