# cloud-code-agent UI

React + TypeScript (Vite) chat UI for the cloud-code-agent backend.

- Local: copy `.env.example` to `.env.local`, set `VITE_API_URL` and `VITE_GOOGLE_CLIENT_ID`, then `npm install && npm run dev`.
- Deploy: `deploy-frontend.yml` runs on merge to `main` and deploys to Vercel production (`cloud-code-agent-ui`).
