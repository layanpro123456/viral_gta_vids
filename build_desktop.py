
"""Build ViceClip Archiver Windows executable."""

import os
import sys
from pathlib import Path

# Force UTF-8 console output on Windows.
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

import PyInstaller.__main__


def build_executable():
    root_dir = Path(__file__).resolve().parent
    entrypoint = root_dir / "gui_main.py"

    print("=" * 50)
    print("Building ViceClip Archiver Desktop Executable")
    print("=" * 50)

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

    print("Running PyInstaller...")

    try:
        PyInstaller.__main__.run(args)

        exe_path = root_dir / "dist" / "ViceClipArchiver.exe"

        if not exe_path.exists():
            raise FileNotFoundError(
                f"Executable not found: {exe_path}"
            )

        size_mb = exe_path.stat().st_size / (1024 * 1024)

        print("\n" + "=" * 50)
        print("BUILD SUCCESSFUL!")
        print(f"Executable: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        print("=" * 50)

    except Exception as exc:
        print(f"\nBUILD FAILED: {exc}")
        raise


if __name__ == "__main__":
    build_executable()
