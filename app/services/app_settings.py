"""Persistent application settings backed by QSettings."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


class AppSettings:
    """Thin wrapper around QSettings for the app's user preferences."""

    MAX_RECENT_FILES = 10
    _KEY_LAST_OPEN_DIR = "files/last_open_dir"
    _KEY_RECENT_FILES = "files/recent_files"

    def __init__(self) -> None:
        self._settings = QSettings("Tax Helper", "Tax PDF Redactor")

    def last_open_dir(self) -> str:
        """Return last directory used for the Open dialog (defaults to home)."""
        return self._settings.value(
            self._KEY_LAST_OPEN_DIR, str(Path.home()), type=str
        )

    def set_last_open_dir(self, directory: str) -> None:
        """Persist the directory."""
        self._settings.setValue(self._KEY_LAST_OPEN_DIR, directory)

    def recent_files(self) -> list[str]:
        """Return up to MAX_RECENT_FILES paths, most-recent first."""
        raw = self._settings.value(self._KEY_RECENT_FILES, [], type=list)
        # Filter out paths that no longer exist
        return [p for p in raw if Path(p).exists()]

    def add_recent_file(self, file_path: str) -> None:
        """Prepend path, deduplicate, trim to MAX_RECENT_FILES, and save."""
        existing = self._settings.value(self._KEY_RECENT_FILES, [], type=list)
        updated = [file_path] + [p for p in existing if p != file_path]
        self._settings.setValue(
            self._KEY_RECENT_FILES, updated[: self.MAX_RECENT_FILES]
        )
        # Also remember the directory
        self.set_last_open_dir(str(Path(file_path).parent))

    def clear_recent_files(self) -> None:
        """Wipe the recent files list."""
        self._settings.remove(self._KEY_RECENT_FILES)
