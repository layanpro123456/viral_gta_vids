"""Standalone Desktop Application Entrypoint for ViceClip Archiver."""

import sys
from viceclip.gui.app import launch_gui

if __name__ == "__main__":
    cfg_arg = sys.argv[1] if len(sys.argv) > 1 else "config.toml"
    launch_gui(cfg_arg)
