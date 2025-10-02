from pydantic import BaseModel, Field

# --- モデル定義 ---
class TaskRequest(BaseModel):
    prompt: str

class TaskResponse(BaseModel):
    task_id: str