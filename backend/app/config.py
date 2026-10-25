import os
import pathlib

from dotenv import load_dotenv

# Local runs read the repo-root .env; in Cloud Run the values come from Secret Manager instead.
load_dotenv(pathlib.Path(__file__).resolve().parents[2] / ".env")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
GCP_PROJECT = os.getenv("GCP_PROJECT", "ai-learning-499409")
ALLOWED_EMAIL = os.getenv("ALLOWED_EMAIL", "noam2030@gmail.com")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GENERATED_REPO = os.getenv("GENERATED_REPO", "noam2030/cloud-code-agent-generated")
WORKSPACE = os.getenv("WORKSPACE", "/workspace/generated")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
