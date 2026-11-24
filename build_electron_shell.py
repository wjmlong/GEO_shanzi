"""Assemble the Windows GEO shell without copying the adjacent VideoFlow workspace."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from PyInstaller.compat import win32api
from PyInstaller.utils.win32.icon import IconFile

ROOT = Path(__file__).resolve().parent
LOCALES = ("en-US", "zh-CN", "zh-TW")


def install_icon(executable: Path, icon_path: Path) -> None:
    loaded = win32api.LoadLibraryEx(str(executable), 0, 2)
    try:
        group = win32api.EnumResourceNames(loaded, 14)[0]
        languages = win32api.EnumResourceLanguages(loaded, 14, group)
    finally:
        win32api.FreeLibrary(loaded)
    icon = IconFile(str(icon_path))
    handle = win32api.BeginUpdateResource(str(executable), 0)
    try:
        for language in languages:
            win32api.UpdateResource(handle, 14, group, icon.grp_icon_dir() + icon.grp_icondir_entries(1), language)
            for index, image in enumerate(icon.images, start=1):
                win32api.UpdateResource(handle, 3, index, image, language)
    except BaseException:
        win32api.EndUpdateResource(handle, 1)
        raise
    win32api.EndUpdateResource(handle, 0)


def assemble(runtime: Path, backend: Path, output: Path) -> None:
    if not (runtime / "electron.exe").is_file() or not (backend / "ShanziGEO.exe").is_file():
        raise FileNotFoundError("The Electron runtime or staged GEO backend is missing.")
    output.mkdir()
    for item in runtime.iterdir():
        if item.name in ("electron.exe", "locales"):
            continue
        target = output / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    (output / "locales").mkdir()
    for language in LOCALES:
        shutil.copy2(runtime / "locales" / (language + ".pak"), output / "locales")

    executable = output / "ShanziGEO.exe"
    icon = ROOT / "desktop_app" / "assets" / "app_icon.ico"
    shutil.copy2(runtime / "electron.exe", executable)
    install_icon(executable, icon)

    app = output / "resources" / "app"
    shutil.copytree(ROOT / "desktop_app" / "windows_shell", app, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(icon, app)
    driver = backend / "_internal" / "playwright" / "driver"

    def exclude_duplicate_node(directory, names):
        return {"node.exe"} & set(names) if Path(directory) == driver else set()

    packed_backend = output / "resources" / "backend"
    shutil.copytree(backend, packed_backend, ignore=exclude_duplicate_node)
    shutil.copytree(ROOT / "desktop_app" / "static", packed_backend / "_internal" / "desktop_app" / "static",
                    dirs_exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    assemble(options.runtime.resolve(), options.backend.resolve(), options.output.resolve())
