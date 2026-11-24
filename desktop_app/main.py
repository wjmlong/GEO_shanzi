from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import os
import pathlib
import socket
import subprocess
import sys
import threading
import time
from typing import Any
import webbrowser

if __package__ in (None, "") and not getattr(sys, "frozen", False):
    _project_root = str(pathlib.Path(__file__).resolve().parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

import httpx
import uvicorn

from desktop_app.api import create_app
from desktop_app.db import app_root_dir, bundle_resource_dir, data_dir, settings_path
from desktop_app.services import find_portable_chromium

WINDOW_TITLE = "山子高科 GEO 智能工作台"


def _attach_cli_streams() -> None:
    """Restore stdout/stderr when a --windowed PyInstaller exe is invoked from CLI or pipes."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import msvcrt

        kernel32 = ctypes.windll.kernel32
        for attr, std_id in (("stdout", -11), ("stderr", -12)):
            if getattr(sys, attr) is None:
                handle = kernel32.GetStdHandle(std_id)
                if handle and handle not in (0, -1):
                    try:
                        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_TEXT)
                        stream = open(fd, "w", encoding="utf-8", buffering=1, closefd=False)
                        setattr(sys, attr, stream)
                    except OSError:
                        pass

        if sys.stdout is None and kernel32.AttachConsole(-1):
            for attr in ("stdout", "stderr"):
                if getattr(sys, attr) is None:
                    try:
                        setattr(sys, attr, open("CONOUT$", "w", encoding="utf-8", buffering=1))
                    except OSError:
                        pass
    except Exception:
        pass


def setup_logging(cli_mode: bool = False) -> pathlib.Path:
    """Configure rotating file logging into data/app.log and guard None stdio in --noconsole mode."""
    log_file = data_dir() / "app.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    if not cli_mode:
        # Prevent crashes in --noconsole mode when libraries write to sys.stdout / sys.stderr
        if sys.stdout is None:
            sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
        if sys.stderr is None:
            sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)

    return log_file


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def start_api_server(port: int) -> tuple[uvicorn.Server, threading.Thread]:
    app = create_app()
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, name="shanzi-geo-uvicorn", daemon=True)
    thread.start()
    return server, thread


def wait_for_server(base_url: str, timeout_sec: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout_sec
    with httpx.Client(timeout=1.0, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                resp = client.get(f"{base_url}/api/health")
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.15)
    return False


def run_smoke_test(port_override: int = 0) -> int:
    _attach_cli_streams()
    log_file = setup_logging(cli_mode=True)
    logger = logging.getLogger("desktop_app.smoke")

    port = port_override or find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server, thread = start_api_server(port)

    try:
        if not wait_for_server(base_url, timeout_sec=20.0):
            err_payload = {"ok": False, "error": "FastAPI server failed to pass /api/health within 20s", "port": port}
            _emit_json(err_payload)
            return 1

        with httpx.Client(timeout=15.0, trust_env=False) as client:
            health_resp = client.get(f"{base_url}/api/health")
            state_resp = client.get(f"{base_url}/api/state")
            root_resp = client.get(f"{base_url}/")

        health_json = health_resp.json() if health_resp.status_code == 200 else {}
        state_json = state_resp.json() if state_resp.status_code == 200 else {}

        d_dir = data_dir()
        db_file = d_dir / "shanzi_geo.db"
        s_file = settings_path()
        chromium_str = str(state_json.get("chromium_path") or find_portable_chromium() or "")
        chromium_ok = bool(chromium_str and pathlib.Path(chromium_str).exists())

        exam_raw = state_json.get("exam_questions")
        if isinstance(exam_raw, dict):
            exam_cnt = len(exam_raw.get("questions") or [])
        elif isinstance(exam_raw, list):
            exam_cnt = len(exam_raw)
        else:
            exam_cnt = 0

        ok = bool(
            health_resp.status_code == 200
            and health_json.get("ok") is True
            and state_resp.status_code == 200
            and state_json.get("ok") is True
            and root_resp.status_code == 200
            and len(root_resp.content) > 0
            and db_file.exists()
        )

        summary: dict[str, Any] = {
            "ok": ok,
            "mode": "smoke-test",
            "frozen": bool(getattr(sys, "frozen", False)),
            "port": port,
            "app_root": str(app_root_dir()),
            "bundle_dir": str(bundle_resource_dir()),
            "data_dir": str(d_dir),
            "log_file": str(log_file),
            "db_path": str(db_file),
            "db_exists": db_file.exists(),
            "settings_path": str(s_file),
            "settings_exists": s_file.exists(),
            "settings_masked": state_json.get("settings_masked", {}),
            "chromium_path": chromium_str,
            "chromium_exists": chromium_ok,
            "health": health_json,
            "ui_status": root_resp.status_code,
            "ui_html_bytes": len(root_resp.content),
            "counts": {
                "platforms": len(state_json.get("platforms") or []),
                "ledger": len(state_json.get("ledger") or []),
                "knowledge_bases": len(state_json.get("knowledge_bases") or []),
                "titles": len(state_json.get("titles") or []),
                "keywords": len(state_json.get("keywords") or []),
                "exam_questions": exam_cnt,
            },
        }
        logger.info("Smoke test result: ok=%s port=%s counts=%s", ok, port, summary["counts"])
        _emit_json(summary)
        return 0 if ok else 1
    except Exception as exc:
        logger.exception("Smoke test failed")
        _emit_json({"ok": False, "error": str(exc), "port": port})
        return 1
    finally:
        server.should_exit = True
        thread.join(timeout=3.0)


def _emit_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        (data_dir() / "smoke_test_last.json").write_text(text, encoding="utf-8")
    except Exception:
        pass
    if sys.stdout is not None:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()


def _launch_chromium_app_fallback(url: str, logger: logging.Logger) -> None:
    chrome_bin = find_portable_chromium()
    if chrome_bin and chrome_bin.exists():
        shell_profile = data_dir() / "app-shell-profile"
        shell_profile.mkdir(parents=True, exist_ok=True)
        args = [
            str(chrome_bin),
            f"--app={url}",
            f"--user-data-dir={shell_profile}",
            "--window-size=1380,880",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        logger.info("Launching portable Chromium app-mode fallback: %s", chrome_bin)
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return

    logger.warning("Portable Chromium not found; opening default system browser for %s", url)
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


def run_desktop_app(port_override: int = 0, serve_only: bool = False) -> int:
    if serve_only:
        _attach_cli_streams()
    log_file = setup_logging(cli_mode=serve_only)
    logger = logging.getLogger("desktop_app.main")
    logger.info("Starting ShanziGEO desktop workbench (frozen=%s, log=%s)", getattr(sys, "frozen", False), log_file)

    port = port_override or find_free_port()
    url = f"http://127.0.0.1:{port}"
    server, thread = start_api_server(port)

    if not wait_for_server(url, timeout_sec=20.0):
        logger.error("Local FastAPI server failed to start on %s", url)
        server.should_exit = True
        return 1

    logger.info("Local FastAPI server ready at %s", url)

    if serve_only:
        if sys.stdout is not None:
            sys.stdout.write(f"READY {url}\n")
            sys.stdout.flush()
        try:
            while thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            server.should_exit = True
            thread.join(timeout=3.0)
        return 0

    try:
        import webview

        webview.create_window(
            WINDOW_TITLE,
            url,
            width=1380,
            height=880,
            min_size=(1080, 720),
            background_color="#F5F7FA",
        )
        webview.start()
    except Exception as exc:
        logger.warning("pywebview native window unavailable (%s); falling back to portable Chromium --app mode", exc)
        _launch_chromium_app_fallback(url, logger)
    finally:
        logger.info("Shutting down local FastAPI server")
        server.should_exit = True
        thread.join(timeout=3.0)

    return 0


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("PYTHONUTF8", "1")
    parser = argparse.ArgumentParser(description=WINDOW_TITLE)
    parser.add_argument("--smoke-test", action="store_true", help="Boot local API, verify /api/health & /api/state, print JSON, and exit 0")
    parser.add_argument("--serve-only", action="store_true", help="Run local FastAPI server without opening GUI window")
    parser.add_argument("--port", type=int, default=0, help="Optional fixed localhost port")
    args, _unknown = parser.parse_known_args(argv)

    if args.smoke_test:
        return run_smoke_test(port_override=args.port)
    return run_desktop_app(port_override=args.port, serve_only=args.serve_only)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
