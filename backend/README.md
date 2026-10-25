# cloud-code-agent backend

FastAPI service that runs the Writer, Reviewer and Answerer agents.

- Run locally: put the keys in the repo-root `.env`, then `uvicorn app.main:app --port 8080` from `backend/`.
- Deploy: `deploy-backend.yml` runs on merge to `main` and deploys to Cloud Run (`cloud-code-agent`).
- Secrets come from Secret Manager (`openai-api-key`, `github-token`), not from the repo.
