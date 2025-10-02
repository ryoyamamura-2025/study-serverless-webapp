# main.py
from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import models
import domain.gemini as gem

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

@app.get("/video", include_in_schema=False)
async def get_video_analysis_page():
    return FileResponse('static/video_analysis.html')

@app.get("/mock-endpoint")
async def mock_endpoint():
    return {"message": "This is a mock endpoint."}

@app.post("simple-chat")
async def simple_chat(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    response_text, response = await gem.simple_chat(prompt)
    return {"response_text": response_text, "response": response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)