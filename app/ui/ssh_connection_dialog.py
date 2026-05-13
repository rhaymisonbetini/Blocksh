from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QFileDialog, QLabel,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from ..domain.ssh_connection import SshConnection
from .theme import ThemeManager, TY


class SshConnectionDialog(QDialog):
    """Add or edit an SSH connection."""

    def __init__(self, connection: SshConnection | None = None, parent=None):
        super().__init__(parent)
        self._connection = connection
        self.setWindowTitle("Edit SSH Connection" if connection else "Add SSH Connection")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui()
        if connection:
            self._populate(connection)
        p = ThemeManager.instance().current
        self.apply_theme(p)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._name  = QLineEdit(); self._name.setPlaceholderText("Production API")
        self._host  = QLineEdit(); self._host.setPlaceholderText("192.168.1.10 or example.com")
        self._user  = QLineEdit(); self._user.setPlaceholderText("ubuntu")
        self._port  = QSpinBox(); self._port.setRange(1, 65535); self._port.setValue(22)
        self._group = QLineEdit(); self._group.setPlaceholderText("production (optional)")

        key_row = QHBoxLayout()
        self._key = QLineEdit(); self._key.setPlaceholderText("~/.ssh/id_rsa (optional)")
        browse = QPushButton("Browse…"); browse.setFixedWidth(80)
        browse.clicked.connect(self._browse_key)
        key_row.addWidget(self._key)
        key_row.addWidget(browse)

        form.addRow("Name *",     self._name)
        form.addRow("Host *",     self._host)
        form.addRow("Username *", self._user)
        form.addRow("Port",       self._port)
        form.addRow("SSH Key",    key_row)
        form.addRow("Group",      self._group)
        layout.addLayout(form)

        self._error_lbl = QLabel()
        p = ThemeManager.instance().current
        self._error_lbl.setStyleSheet(f"color: {p.red}; font-size: {TY.sm}px;")
        self._error_lbl.hide()
        layout.addWidget(self._error_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, c: SshConnection) -> None:
        self._name.setText(c.name)
        self._host.setText(c.host)
        self._user.setText(c.user)
        self._port.setValue(c.port)
        self._key.setText(c.key_path)
        self._group.setText(c.group)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Key", "", "All Files (*)"
        )
        if path:
            self._key.setText(path)

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        host = self._host.text().strip()
        user = self._user.text().strip()
        if not name or not host or not user:
            self._error_lbl.setText("Name, Host, and Username are required.")
            self._error_lbl.show()
            return
        self.accept()

    def result_connection(self) -> SshConnection:
        """Call after exec() returns Accepted."""
        if self._connection:
            self._connection.name     = self._name.text().strip()
            self._connection.host     = self._host.text().strip()
            self._connection.user     = self._user.text().strip()
            self._connection.port     = self._port.value()
            self._connection.key_path = self._key.text().strip()
            self._connection.group    = self._group.text().strip()
            return self._connection
        return SshConnection(
            name=self._name.text().strip(),
            host=self._host.text().strip(),
            user=self._user.text().strip(),
            port=self._port.value(),
            key_path=self._key.text().strip(),
            group=self._group.text().strip(),
        )

    def apply_theme(self, p) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {p.bg_panel}; color: {p.fg}; }}"
            f"QLabel  {{ color: {p.fg}; background: transparent; }}"
            f"QLineEdit, QSpinBox {{ background: {p.bg}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 6px; }}"
            f"QLineEdit:focus, QSpinBox:focus {{ border-color: {p.blue}; }}"
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: {p.bg_selected}; }}"
            f"QDialogButtonBox QPushButton[text='Save'] {{"
            f"  background: {p.blue}; color: {p.bg}; border: none; font-weight: bold; }}"
        )
