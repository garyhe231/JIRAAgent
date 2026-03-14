import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

os.makedirs("data/tickets", exist_ok=True)
os.makedirs("data/sprints", exist_ok=True)
os.makedirs("data/users", exist_ok=True)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8009))
    reload = os.environ.get("RELOAD", "false").lower() == "true"
    workers = int(os.environ.get("WORKERS", 1))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
    )
