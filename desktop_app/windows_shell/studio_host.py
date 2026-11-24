"""Host the existing VideoFlow checkout on a loopback port owned by the desktop app."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from starlette.responses import JSONResponse


def main() -> None:
    workspace = Path(sys.argv[1]).resolve(strict=True)
    os.chdir(workspace)
    sys.path.insert(0, str(workspace))
    import studio_server

    studio_server.C["python"] = sys.executable
    studio_server.workflow.C["python"] = sys.executable

    def running_jobs() -> int:
        with studio_server.JOBS_LOCK:
            return sum(job["status"] == "running" for job in studio_server.JOBS.values())

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        origin = f"http://127.0.0.1:{port}"

        @studio_server.app.middleware("http")
        async def local_origin(request, call_next):
            request_origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            if request.url.netloc != f"127.0.0.1:{port}":
                return JSONResponse({"detail": "Invalid host"}, status_code=403)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if request_origin and request_origin != origin:
                    return JSONResponse({"detail": "Invalid origin"}, status_code=403)
                if referer and urlsplit(referer).netloc != request.url.netloc:
                    return JSONResponse({"detail": "Invalid referer"}, status_code=403)
                if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
                    return JSONResponse({"detail": "Cross-origin request"}, status_code=403)
            return await call_next(request)

        @studio_server.app.get("/_geo/status")
        def desktop_status():
            return {"running_jobs": running_jobs()}

        server = uvicorn.Server(uvicorn.Config(
            studio_server.app, loop="asyncio", log_level="warning", access_log=False,
        ))

        def wait_for_desktop_exit() -> None:
            sys.stdin.buffer.read(1)
            while running_jobs():
                time.sleep(1)
            server.should_exit = True

        threading.Thread(target=wait_for_desktop_exit, daemon=True).start()
        print(f"VIDEOFLOW_READY {origin}", flush=True)
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()
