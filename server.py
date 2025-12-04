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

print("⚡ SYSTEM: INITIALIZING UNIFIED SERVER...")

@app.on_event("startup")
async def startup_event():
    print("🔥 IGNITING DATA ENGINE (BACKGROUND TASK)...")
    
    asyncio.create_task(data_engine.async_listen_loop(active_connections))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"🔌 NEW DASHBOARD CONNECTED. TOTAL: {len(active_connections)}")
    try:
        while True:
            
            await websocket.receive_text()
    except:
        if websocket in active_connections:
            active_connections.remove(websocket)
            print("🔌 DASHBOARD DISCONNECTED.")


@app.post("/broadcast")
async def broadcast(request: Request):
    data = await request.json()
    print(f"📨 EXTERNAL PUSH (Telegram/Api): {data.get('headline', 'Unknown')}")
    
    
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except:
            continue
    return {"status": "sent"}

if __name__ == "__main__":
   
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)