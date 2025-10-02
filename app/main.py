# main.py
import os

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from google import genai

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("LOCATION")

# Geminiクライアント初期化
_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT_ID,
    location=LOCATION,
)

# --- アプリケーション設定 ---
app = FastAPI(title="Sample Application for Serverless WebApp")
# Allow all origins for CORS (useful for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== エンドポイント ======
# 静的ファイル提供
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse('static/index.html')

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)