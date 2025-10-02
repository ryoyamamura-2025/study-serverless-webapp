# main.py
import os
import uuid
import asyncio
import time

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from google.cloud import firestore, tasks_v2
from google.protobuf import timestamp_pb2
from sse_starlette.sse import EventSourceResponse

from models import *
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

# 環境変数から設定を読み込み
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("LOCATION")
QUEUE_ID = os.getenv("GCP_TASK_QUEUE_ID")
GCP_FIRESTORE_DB_NAME=os.getenv("GCP_FIRESTORE_DB_NAME")
BASE_URL = os.getenv("BASE_URL")

# GCPクライアントの初期化
db = firestore.AsyncClient(database=GCP_FIRESTORE_DB_NAME)
tasks_client = tasks_v2.CloudTasksClient()

# Cloud Tasksキューの親パス
task_queue_path = tasks_client.queue_path(PROJECT_ID, LOCATION, QUEUE_ID)
print(f"Cloud Tasks Queue Path: {task_queue_path}")

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

@app.post("/simple-chat")
async def simple_chat(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    response_text, response = await gem.simple_chat(prompt)
    return {"response_text": response_text, "response": response}

@app.post("/start-task", response_model=TaskResponse)
async def start_task(task_req: TaskRequest):
    """タスクを開始し、Cloud Tasksにキューイングするエンドポイント"""
    task_id = str(uuid.uuid4())
    
    # 1. Firestoreにタスクドキュメントを初期状態で作成
    task_ref = db.collection("tasks").document(task_id)
    await task_ref.set({
        "id": task_id,
        "prompt": task_req.prompt,
        "status": "Queued",
        "progress": 0,
        "message": "タスクをキューに追加しました。",
        "created_at": firestore.SERVER_TIMESTAMP,
    })

    # 2. Cloud Tasksにタスクを作成
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{BASE_URL}/run-task",
            "headers": {"Content-Type": "application/json"},
            "body": f'{{"task_id": "{task_id}"}}'.encode(),
        }
    }
    
    tasks_client.create_task(parent=task_queue_path, task=task)
    
    return {"task_id": task_id}

@app.post("/run-task")
async def run_task(request: Request):
    """
    Cloud Tasksから呼び出されるワーカーエンドポイント
    数分かかる重い処理をシミュレートする
    """
    body = await request.json()
    task_id = body.get("task_id")
    
    if not task_id:
        return {"status": "error", "message": "task_id is required"}

    task_ref = db.collection("tasks").document(task_id)

    try:
        # ステータスを「処理中」に更新
        await task_ref.update({"status": "Processing", "message": "処理を開始しました。"})
        
        # --- 時間のかかる処理のシミュレーション ---
        total_steps = 5
        for i in range(1, total_steps + 1):
            await asyncio.sleep(10) # 10秒待機
            progress = int((i / total_steps) * 100)
            await task_ref.update({
                "progress": progress,
                "message": f"ステップ {i}/{total_steps} が完了しました..."
            })
        # ----------------------------------------
        
        # 最終結果を更新
        await task_ref.update({
            "status": "Completed",
            "progress": 100,
            "message": "すべての処理が正常に完了しました！",
            "finished_at": firestore.SERVER_TIMESTAMP,
        })
        
        return {"status": "success"}

    except Exception as e:
        await task_ref.update({
            "status": "Failed",
            "message": f"エラーが発生しました: {str(e)}",
            "finished_at": firestore.SERVER_TIMESTAMP,
        })
        # エラーを返すことでCloud Tasksのリトライをトリガーすることも可能
        raise e
    
@app.get("/progress/{task_id}")
async def stream_progress(task_id: str):
    """SSEでタスクの進捗をクライアントにストリーミングするエンドポイント"""
    
    async def progress_generator():
        last_known_message = None
        while True:
            doc_snapshot = await db.collection("tasks").document(task_id).get()
            if not doc_snapshot.exists:
                yield {"event": "error", "data": "Task not found"}
                break
            
            data = doc_snapshot.to_dict()
            current_message = data.get("message")

            # メッセージに変更があった場合のみイベントを送信
            if current_message != last_known_message:
                yield {
                    "event": "update",
                    "data": f'{{"status": "{data.get("status")}", "progress": {data.get("progress", 0)}, "message": "{current_message}"}}'
                }
                last_known_message = current_message

            # タスクが完了または失敗したらストリームを終了
            if data.get("status") in ["Completed", "Failed"]:
                yield {"event": "end", "data": "Stream closed"}
                break

            await asyncio.sleep(1) # 1秒ごとにFirestoreをポーリング

    return EventSourceResponse(progress_generator())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
