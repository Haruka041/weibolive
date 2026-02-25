import uvicorn
import sys
import asyncio

from app.core.config import CONFIG

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=CONFIG.host,
        port=CONFIG.port,
        reload=False,
        loop="asyncio"
    )
