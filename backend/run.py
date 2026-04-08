import os

import uvicorn


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    reload_enabled = os.environ.get("RELOAD", "false").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload_enabled)
