"""Serve the real FastAPI app over stdin/stdout JSON lines for socket-free combined UI tests.

Each input line is ``{"id", "method", "path", "body"}``, or ``{"id", "method", "path",
"body_base64", "content_type"}`` for a binary upload; each output line is
``{"id", "status", "headers", "body"}``. Requests go through ``httpx.ASGITransport`` into the
unmodified ``geo_companion.main.app``, which lazily opens its SQLite database under
``GEO_COMPANION_DATA_DIR`` exactly as a uvicorn process would. The variable is required so a test
can never touch a learner's real application data.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "api" / "src"))

import httpx  # noqa: E402
from geo_companion.main import app  # noqa: E402


async def serve() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://bridge") as client:
        print(json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            request = json.loads(line)
            if "body_base64" in request:
                content: str | bytes | None = base64.b64decode(request["body_base64"])
                headers = {"content-type": request["content_type"]}
            else:
                content = request.get("body")
                headers = {"content-type": "application/json"} if content else {}
            response = await client.request(
                request["method"], request["path"], content=content, headers=headers
            )
            print(
                json.dumps(
                    {
                        "id": request["id"],
                        "status": response.status_code,
                        "headers": {"content-type": response.headers.get("content-type", "")},
                        "body": response.text,
                    }
                ),
                flush=True,
            )


def main() -> int:
    if not os.environ.get("GEO_COMPANION_DATA_DIR"):
        print("GEO_COMPANION_DATA_DIR must name a disposable data directory.", file=sys.stderr)
        return 2
    asyncio.run(serve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
