#!/bin/sh
set -e

: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

git config --global user.name "cloud-code-agent"
git config --global user.email "noam2030@users.noreply.github.com"
git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/"
export GH_TOKEN="$GITHUB_TOKEN"

# Fresh clone on every container start, as required.
rm -rf /workspace/generated
mkdir -p /workspace
git clone "https://github.com/${GENERATED_REPO:-noam2030/cloud-code-agent-generated}.git" /workspace/generated

cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
