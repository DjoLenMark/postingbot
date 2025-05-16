
from fastapi import FastAPI
import uvicorn
import threading

app = FastAPI()

@app.get("/ping")
def ping():
    return {"status": "alive"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()
