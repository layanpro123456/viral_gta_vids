"""Desktop Executable Build Script using PyInstaller.

Compiles ViceClip Archiver into a standalone Windows .exe with all dependencies
bundled (CustomTkinter themes, yt-dlp extractors, SQLite, Pydantic).
"""

import os
from pathlib import Path
import sys

import PyInstaller.__main__


def build_executable() -> None:
    """Build standalone desktop executable."""
    root_dir = Path(__file__).parent.resolve()
    entrypoint = root_dir / "gui_main.py"

    print("==================================================")
    print("  Building ViceClip Archiver Desktop Executable   ")
    print("==================================================")

    # Cross-platform data separator (; on Windows, : on Linux/macOS)
    sep = os.pathsep

    args = [
        str(entrypoint),
        "--noconfirm",
        "--clean",
        "--name=ViceClipArchiver",
        "--onefile",
        "--windowed",
        "--collect-all=customtkinter",
        "--collect-all=yt_dlp",
        "--collect-all=rich",
        f"--add-data=config.toml{sep}.",
        f"--add-data=.env.example{sep}.",
        f"--add-data=assets{sep}assets",
        f"--distpath={root_dir / 'dist'}",
        f"--workpath={root_dir / 'build'}",
        f"--specpath={root_dir}",
    ]

    print(f"Executing PyInstaller with args:\n{' '.join(args)}\n")

    try:
        PyInstaller.__main__.run(args)
        exe_suffix = ".exe" if sys.platform == "win32" else ""
        exe_path = root_dir / "dist" / f"ViceClipArchiver{exe_suffix}"
        if exe_path.exists():
            print("\n==================================================")
            print("  BUILD SUCCESSFUL! 🎉")
            print(f"  Executable location: {exe_path}")
            print(f"  Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
            print("==================================================")
        else:
            print(f"\n[ERROR] Build finished but expected binary not found at {exe_path}")
            sys.exit(1)
    except Exception as exc:
        print(f"\n[FATAL] PyInstaller execution failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
