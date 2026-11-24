from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
DIST_APP_DIR = ROOT / "dist" / "ShanziGEO"
BUILD_ROOT = ROOT / "build"
STAGE_DIST_DIR = BUILD_ROOT / "pyinstaller_dist"
WORK_DIR = BUILD_ROOT / "pyinstaller_work"
SPEC_DIR = BUILD_ROOT / "pyinstaller_spec"

PRESERVED_DIST_ENTRIES = {"browsers", "data"}


def verify_prerequisites() -> None:
    required_files = [
        ROOT / "desktop_app" / "main.py",
        ROOT / "desktop_app" / "api.py",
        ROOT / "desktop_app" / "db.py",
        ROOT / "desktop_app" / "services.py",
        ROOT / "desktop_app" / "seed_data.json",
        ROOT / "desktop_app" / "static" / "index.html",
        ROOT / "desktop_app" / "assets" / "app_icon.ico",
        ROOT / "geo" / "baseline_10q.yaml",
    ]
    missing = [str(p) for p in required_files if not p.exists() or p.stat().st_size == 0]
    if missing:
        raise FileNotFoundError(f"Cannot build ShanziGEO.exe; missing or empty required files: {missing}")


def build_to_staging() -> pathlib.Path:
    staged_app = STAGE_DIST_DIR / "ShanziGEO"
    if staged_app.exists():
        shutil.rmtree(staged_app)
    STAGE_DIST_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)

    sep = os.pathsep
    icon_path = ROOT / "desktop_app" / "assets" / "app_icon.ico"
    entry_script = ROOT / "desktop_app" / "main.py"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "ShanziGEO",
        "--distpath",
        str(STAGE_DIST_DIR),
        "--workpath",
        str(WORK_DIR),
        "--specpath",
        str(SPEC_DIR),
        "--paths",
        str(ROOT),
        "--icon",
        str(icon_path),
        "--add-data",
        f"{ROOT / 'desktop_app' / 'seed_data.json'}{sep}desktop_app",
        "--add-data",
        f"{ROOT / 'desktop_app' / 'static'}{sep}desktop_app/static",
        "--add-data",
        f"{ROOT / 'desktop_app' / 'assets'}{sep}desktop_app/assets",
        "--add-data",
        f"{ROOT / 'geo' / 'baseline_10q.yaml'}{sep}geo",
        "--collect-all",
        "playwright",
        "--collect-all",
        "webview",
        "--collect-data",
        "certifi",
        "--hidden-import",
        "desktop_app.api",
        "--hidden-import",
        "desktop_app.db",
        "--hidden-import",
        "desktop_app.services",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "markdown.extensions.tables",
        "--hidden-import",
        "markdown.extensions.fenced_code",
        str(entry_script),
    ]

    print("[build_exe] Running PyInstaller into staging folder...")
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    exe_path = staged_app / "ShanziGEO.exe"
    if not exe_path.exists():
        raise RuntimeError(f"PyInstaller finished without producing {exe_path}")
    return staged_app


def sync_into_dist(staged_app: pathlib.Path) -> pathlib.Path:
    DIST_APP_DIR.mkdir(parents=True, exist_ok=True)
    (DIST_APP_DIR / "data").mkdir(parents=True, exist_ok=True)

    # Sync local gitignored settings.json if dist/ShanziGEO/data/settings.json is absent
    dev_settings = ROOT / "data" / "settings.json"
    dist_settings = DIST_APP_DIR / "data" / "settings.json"
    if dev_settings.exists() and not dist_settings.exists():
        shutil.copy2(dev_settings, dist_settings)

    # Remove ONLY non-preserved entries in dist/ShanziGEO (NEVER touch browsers/ or data/)
    for existing in DIST_APP_DIR.iterdir():
        if existing.name in PRESERVED_DIST_ENTRIES:
            continue
        if existing.is_dir():
            shutil.rmtree(existing)
        else:
            existing.unlink()

    # Copy fresh ShanziGEO.exe and _internal/ from staging
    for item in staged_app.iterdir():
        if item.name in PRESERVED_DIST_ENTRIES:
            continue
        dest = DIST_APP_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Also place geo/baseline_10q.yaml beside exe root so both _MEIPASS/geo and app_root/geo resolve
    dist_geo_dir = DIST_APP_DIR / "geo"
    dist_geo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "geo" / "baseline_10q.yaml", dist_geo_dir / "baseline_10q.yaml")

    exe_path = DIST_APP_DIR / "ShanziGEO.exe"
    browsers_dir = DIST_APP_DIR / "browsers"
    if not browsers_dir.exists():
        print("[build_exe] WARNING: dist/ShanziGEO/browsers directory was not found!")
    else:
        print(f"[build_exe] Verified preserved portable browsers at {browsers_dir}")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[build_exe] Synced {exe_path} ({size_mb:.2f} MB)")
    return exe_path


def run_exe_smoke_test(exe_path: pathlib.Path) -> dict:
    print(f"[build_exe] Running smoke test: {exe_path} --smoke-test")
    proc = subprocess.run(
        [str(exe_path), "--smoke-test"],
        cwd=str(exe_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        raise RuntimeError(
            f"ShanziGEO.exe --smoke-test exited with code {proc.returncode}.\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    data = json.loads(proc.stdout.strip())
    if not data.get("ok"):
        raise RuntimeError(f"Smoke test returned ok=False: {data}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build portable ShanziGEO.exe with PyInstaller")
    parser.add_argument("--skip-smoke-test", action="store_true", help="Skip post-build --smoke-test execution")
    args = parser.parse_args()

    verify_prerequisites()
    staged = build_to_staging()
    exe_path = sync_into_dist(staged)
    if not args.skip_smoke_test:
        run_exe_smoke_test(exe_path)
    print("[build_exe] Build and verification completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
