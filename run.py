import os
import uvicorn

os.makedirs("data/tickets", exist_ok=True)
os.makedirs("data/sprints", exist_ok=True)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8009, reload=True)
