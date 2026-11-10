# Shivansh Raghuvanshi — Engineering Portfolio

A responsive React/TypeScript portfolio with a FastAPI backend. It combines live GitHub data, EIVA AI features, a read-only SQL sandbox, a parameterized-query security demo, contact delivery, and an honest CI status dashboard.

## Requirements

- Node.js 20+ and npm
- Python 3.10+
- Optional OpenAI API key for EIVA
- Optional SMTP credentials for contact delivery
- Optional GitHub owner/repository for Actions status

## Run locally

1. Install frontend dependencies: `npm install`.
2. Copy `.env.example` to `.env` and set any available public profile details.
3. Run `npm run dev` from the project root.
4. In a second terminal, enter `backend`, create and activate a virtual environment, then run `pip install -r requirements.txt`.
5. Copy `backend/.env.example` to `backend/.env`. Configure `OPENAI_API_KEY` and `GITHUB_REPOSITORY=owner/repository` if available.
6. From `backend/`, run `uvicorn main:app --reload --port 8000`.

Frontend: http://localhost:5173. API health: http://localhost:8000/api/health. OpenAPI Swagger UI: http://localhost:8000/docs. Without backend services, their UI modules report unavailable states rather than mock results.

## Engineering modules

- **Recruiter mode:** concise experience/education/skills view, browser speech synthesis overview, downloadable HTML resume, and browser print-to-PDF.
- **EIVA:** portfolio assistant, mock interview, and repository explanation. The backend requires `OPENAI_API_KEY`; explanations only use selected public repository metadata.
- **GitHub:** live public repositories, repository language metadata, and recent events from the public Events API. Events are not a complete contribution graph.
- **Live demos:** links only to HTTPS deployment URLs listed in real public repository metadata. Empty state appears when there are no deployment URLs.
- **Architecture map:** interactive overview of the browser, GitHub, FastAPI, SQLite, OpenAI, SMTP, and Actions connections used by this portfolio.
- **SQL playground:** fresh in-memory SQLite database per request. It contains fictional tutorial rows in `sample_products` and `sample_orders`, allows read-only `SELECT`/`WITH`, limits results to 100 rows, and stops long-running queries after 350 ms.
- **REST explorer:** loads the running FastAPI OpenAPI schema and links to Swagger UI at `/docs`.
- **Testing/CI:** `.github/workflows/ci.yml` runs the backend pytest suite and frontend production build. The dashboard fetches actual workflow and job status from GitHub Actions. It shows no runs until this workflow has been pushed to the configured repository and executed.
- **Cybersecurity demo:** a real parameterized SQL lookup against the fictional sample database. The injection test string is treated as data; no vulnerable query is executed.
- **Problem solving:** executes binary search against the entered sorted integer list and reports measured comparisons alongside O(log n) time and O(1) space.
- **Analytics:** downloads the public Iris CSV from the seaborn-data repository and computes species counts and mean petal length from the downloaded rows. No cached/fabricated metrics are displayed.
- **Credentials:** only renders verified credentials configured in `src/config.ts`. It is intentionally empty until issuer and verification URL details are supplied.

## Tests

From `backend/`, install requirements and run `python -m pytest -q`. The current suite covers health, SQL read-only restrictions and extension loading, safe parameterized lookup behavior, missing AI credentials, and an unconfigured CI state. GitHub Actions runs these checks on pushes and pull requests.

## Configuration

Frontend public configuration is in `src/config.ts`. Optional `.env` values include `VITE_LINKEDIN_URL`, `VITE_CONTACT_EMAIL`, `VITE_PROFILE_IMAGE`, `VITE_API_URL`, and `VITE_GITHUB_REPOSITORY`.

Backend configuration lives in `backend/.env`:

- `OPENAI_API_KEY` and `OPENAI_MODEL` for EIVA (model defaults to `gpt-4o-mini`).
- `GITHUB_REPOSITORY=owner/repository` to read the latest `.github/workflows/ci.yml` run and job results. It defaults to the verified public portfolio repository `Ryoishin/Shivansh`; override it if this code is published elsewhere. `GITHUB_TOKEN` is optional and backend-only.
- `CONTACT_EMAIL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` to deliver contact form messages.
- `FRONTEND_ORIGIN` for the allowed CORS origin list.

Never put OpenAI or GitHub secrets in a `VITE_` variable or frontend source. Email, LinkedIn, and profile imagery remain unset until supplied.

## Production deployment

- Build the frontend with `npm run build`; deploy `dist/` to Vercel or another static host. Set the `VITE_API_URL` build variable to the deployed API origin.
- Deploy `backend/` as a Python web service. Install `backend/requirements.txt`, start with `uvicorn main:app --host 0.0.0.0 --port $PORT`, and configure backend secrets and `FRONTEND_ORIGIN` in the host environment.
- Configure the host to serve `index.html` for frontend fallback routes.
- The API uses in-memory per-IP rate limits. For multi-instance production, also configure rate limiting at the trusted proxy/platform layer.
- GitHub's unauthenticated REST API has rate limits. If GitHub is unavailable or rate-limited, the relevant module shows an error state and profile link.
