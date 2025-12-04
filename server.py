import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List
import os
import data_engine
import ground_truth_engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections: List[WebSocket] = []

@app.get("/")
def home():
    return {"status": "alive", "system": "SentinLK Brain"}

@app.on_event("startup")
async def startup_event():
    print("SYSTEM STARTUP")
    asyncio.create_task(data_engine.async_listen_loop(active_connections))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.post("/broadcast")
async def broadcast(request: Request):
    data = await request.json()
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except:
            continue
    return {"status": "sent"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
