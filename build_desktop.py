"""Desktop Executable Build Script using PyInstaller.

Compiles ViceClip Archiver into a standalone Windows .exe with all dependencies
bundled (CustomTkinter themes, yt-dlp extractors, SQLite, Pydantic).
"""

import os
from pathlib import Path
import subprocess
import sys


def build_executable() -> None:
    """Build standalone desktop executable."""
    root_dir = Path(__file__).parent.resolve()
    entrypoint = root_dir / "gui_main.py"
    config_file = root_dir / "config.toml"
    env_example = root_dir / "config.toml"

    print("==================================================")
    print("  Building ViceClip Archiver Desktop Executable   ")
    print("==================================================")

    # PyInstaller arguments
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=ViceClipArchiver",
        "--onefile",
        "--windowed",  # GUI mode without console window
        "--collect-all=customtkinter",
        "--collect-all=yt_dlp",
        "--collect-all=rich",
        "--add-data=config.toml;.",
        "--add-data=.env.example;.",
        "--add-data=assets;assets",
        str(entrypoint),
    ]

    print(f"Running command:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(root_dir))

    if result.returncode == 0:
        exe_path = root_dir / "dist" / "ViceClipArchiver.exe"
        print("\n==================================================")
        print("  BUILD SUCCESSFUL! 🎉")
        print(f"  Executable location: {exe_path}")
        print("==================================================")
    else:
        print(f"\nBuild failed with exit code: {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_executable()
