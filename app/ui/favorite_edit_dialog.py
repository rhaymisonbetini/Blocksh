from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLineEdit, QLabel, QDialogButtonBox,
)
from PySide6.QtCore import Qt

from ..domain.favorite import Favorite
from .theme import ThemeManager


class FavoriteEditDialog(QDialog):
    """Add or edit a favorite command."""

    def __init__(self, favorite: Favorite | None = None, parent=None):
        super().__init__(parent)
        self._favorite = favorite
        self.setWindowTitle("Edit Favorite" if favorite else "Add Favorite")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._build_ui()
        if favorite:
            self._populate(favorite)
        self.apply_theme(ThemeManager.instance().current)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. deploy, build, test")

        self._cmd = QLineEdit()
        self._cmd.setPlaceholderText("e.g. git push origin main")

        self._cwd = QLineEdit()
        self._cwd.setPlaceholderText("optional — leave empty for any directory")

        form.addRow("Name *",      self._name)
        form.addRow("Command *",   self._cmd)
        form.addRow("Directory",   self._cwd)
        layout.addLayout(form)

        self._error_lbl = QLabel()
        self._error_lbl.setStyleSheet("color: #f38ba8; font-size: 8pt;")
        self._error_lbl.hide()
        layout.addWidget(self._error_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, fav: Favorite) -> None:
        self._name.setText(fav.name)
        self._cmd.setText(fav.command_text)
        self._cwd.setText(fav.cwd)

    def _on_accept(self) -> None:
        if not self._name.text().strip() or not self._cmd.text().strip():
            self._error_lbl.setText("Name and Command are required.")
            self._error_lbl.show()
            return
        self.accept()

    def result_data(self) -> tuple[str, str, str]:
        """Returns (name, command_text, cwd). Call after exec() == Accepted."""
        return (
            self._name.text().strip(),
            self._cmd.text().strip(),
            self._cwd.text().strip(),
        )

    def apply_theme(self, p) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {p.bg_panel}; color: {p.fg}; }}"
            f"QLabel  {{ color: {p.fg}; background: transparent; }}"
            f"QLineEdit {{ background: {p.bg}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 6px; }}"
            f"QLineEdit:focus {{ border-color: {p.blue}; }}"
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: {p.bg_selected}; }}"
            f"QDialogButtonBox QPushButton[text='Save'] {{"
            f"  background: {p.blue}; color: {p.bg}; border: none; font-weight: bold; }}"
        )
