import asyncio
import sys

import uvicorn

from .extraction.app import run_main as extractor
from .web.app import run as web

if __name__ == "__main__":
    match sys.argv[1:]:
        case ["extractor"]:
            extractor()
        case ["web"]:
            web()
        case _:
            exit(f"Unknown command {' '.join(sys.argv[1:])}")
