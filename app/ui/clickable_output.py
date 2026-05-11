from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QTextEdit


class ClickableOutput(QTextEdit):
    """QTextEdit that handles anchor clicks for URLs and file paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )

    def mousePressEvent(self, event) -> None:
        anchor = self.anchorAt(event.pos())
        if anchor and event.button() == Qt.LeftButton:
            _open_anchor(anchor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        anchor = self.anchorAt(event.pos())
        self.viewport().setCursor(
            Qt.PointingHandCursor if anchor else Qt.IBeamCursor
        )
        super().mouseMoveEvent(event)


def _open_anchor(href: str) -> None:
    """Dispatch a href to the appropriate opener."""
    if href.startswith("file://"):
        # Decode optional :line suffix encoded as ?line=N in the href
        line = None
        if "?line=" in href:
            href_base, _, line_str = href.partition("?line=")
            try:
                line = int(line_str)
            except ValueError:
                pass
            href = href_base

        path = QUrl(href).toLocalFile()
        if line is not None:
            _open_in_editor(path, line)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    else:
        QDesktopServices.openUrl(QUrl(href))


def _open_in_editor(path: str, line: int) -> None:
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", ""))
    if not editor:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return
    try:
        subprocess.Popen([editor, f"+{line}", path])
    except Exception:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
