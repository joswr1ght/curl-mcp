# /// script
# dependencies = ["fastmcp", "rich", "httpx", "sse-starlette", "starlette", "uvicorn"]
# ///

import sys
from main import main_sync

if __name__ == "__main__":
    main_sync()
