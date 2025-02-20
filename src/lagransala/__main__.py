import asyncio
import sys

import uvicorn

from .extraction.app import main as extractor
from .web.app import app as web_app

if __name__ == "__main__":
    match sys.argv[1:]:
        case ["extractor"]:
            asyncio.run(extractor())
        case ["web"]:
            uvicorn.run(web_app, host="0.0.0.0", port=8000)
        case _:
            exit(f"Unknown command {' '.join(sys.argv[1:])}")
