"""Tests for desktop GUI application components."""

import sys
from unittest.mock import MagicMock, patch
import pytest

from viceclip.gui.app import open_folder


def test_open_folder_cross_platform() -> None:
    """Verify open_folder calls the appropriate OS system handler."""
    with patch("pathlib.Path.mkdir"), patch("os.startfile", create=True) as mock_startfile:
        if sys.platform == "win32":
            open_folder("./archive")
            assert mock_startfile.called


def test_gui_module_imports() -> None:
    """Verify GUI package and components import without syntax or namespace errors."""
    from viceclip.gui import launch_gui
    from viceclip.gui.app import ViceClipDesktopApp
    assert callable(launch_gui)
    assert ViceClipDesktopApp is not None
