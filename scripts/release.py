"""Automated Build & Release Automation Script.

Executes end-to-end verification, builds the standalone Windows executable,
computes SHA-256 checksums, and automates Git tag generation.
"""

import hashlib
import os
from pathlib import Path
import subprocess
import sys


def run_cmd(cmd: list[str], desc: str) -> None:
    print(f"\n[RUNNING] {desc}...")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"[ERROR] {desc} failed with exit code {res.returncode}")
        sys.exit(res.returncode)
    print(f"[SUCCESS] {desc}")


def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def main() -> None:
    root = Path(__file__).parent.parent.resolve()
    os.chdir(root)

    print("==================================================")
    print("  ViceClip Archiver — Automated Release Pipeline   ")
    print("==================================================")

    # 1. Run Tests
    run_cmd([sys.executable, "-m", "pytest", "-v"], "Running Automated Test Suite")

    # 2. Build Executable
    run_cmd([sys.executable, "build_desktop.py"], "Building Standalone Executable")

    exe_path = root / "dist" / "ViceClipArchiver.exe"
    if not exe_path.exists():
        print(f"[ERROR] Executable not found at {exe_path}")
        sys.exit(1)

    # 3. Checksum Generation
    hash_val = compute_sha256(exe_path)
    hash_file = root / "dist" / "ViceClipArchiver.exe.sha256"
    hash_file.write_text(hash_val + "\n", encoding="utf-8")
    print(f"\n✔ SHA-256 Checksum: {hash_val}")
    print(f"✔ Checksum written to {hash_file}")

    print("\n==================================================")
    print("  AUTOMATED BUILD COMPLETE! 🎉                    ")
    print(f"  Binary:   {exe_path} ({exe_path.stat().st_size / (1024*1024):.1f} MB)")
    print(f"  Checksum: {hash_file}")
    print("==================================================")


if __name__ == "__main__":
    main()
