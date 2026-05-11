from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QDialogButtonBox, QFrame,
)
from PySide6.QtCore import Qt, Signal

from ..domain.workflow import Workflow
from .theme import ThemeManager


class WorkflowRunner(QDialog):
    """Shows workflow steps and lets user confirm before executing."""
    run_requested = Signal(list)  # list of command strings

    def __init__(self, workflow: Workflow, parent=None):
        super().__init__(parent)
        self._workflow = workflow
        self.setWindowTitle(f"Run: {workflow.name}")
        self.setMinimumSize(480, 320)
        self.setModal(True)
        self._build_ui()
        p = ThemeManager.instance().current
        self._apply_theme(p)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(self._workflow.name)
        title.setStyleSheet("font-size: 12pt; font-weight: bold; background: transparent;")
        layout.addWidget(title)

        if self._workflow.description:
            desc = QLabel(self._workflow.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #6c7086; font-size: 9pt; background: transparent;")
            layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        steps_w = QWidget()
        steps_w.setStyleSheet("QWidget { background: transparent; }")
        steps_layout = QVBoxLayout(steps_w)
        steps_layout.setContentsMargins(0, 4, 0, 4)
        steps_layout.setSpacing(6)

        for i, step in enumerate(self._workflow.steps):
            row = QWidget()
            row.setStyleSheet("QWidget { background: transparent; }")
            h = QHBoxLayout(row)
            h.setContentsMargins(4, 4, 4, 4)
            h.setSpacing(8)

            num_lbl = QLabel(f"{i + 1}.")
            num_lbl.setFixedWidth(20)
            num_lbl.setStyleSheet("color: #6c7086; font-size: 9pt; background: transparent;")
            h.addWidget(num_lbl)

            cmd_lbl = QLabel(step.command_template)
            cmd_lbl.setStyleSheet(
                "color: #cdd6f4; font-family: Monospace; font-size: 9pt; background: transparent;"
            )
            cmd_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            h.addWidget(cmd_lbl, 1)

            if step.on_error == "continue":
                tag = QLabel("continue on err")
                tag.setStyleSheet(
                    "color: #f9e2af; font-size: 7pt; background: transparent; padding: 1px 4px;"
                )
                h.addWidget(tag)

            steps_layout.addWidget(row)

        steps_layout.addStretch()
        scroll.setWidget(steps_w)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox()
        run_btn = QPushButton("Run")
        run_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        buttons.addButton(run_btn, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_btn, QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._on_run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_run(self) -> None:
        commands = [s.command_template for s in self._workflow.steps]
        self.run_requested.emit(commands)
        self.accept()

    def _apply_theme(self, p) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {p.bg_panel}; color: {p.fg}; }}"
            f"QLabel  {{ color: {p.fg}; background: transparent; }}"
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {p.bg_selected}; }}"
            f"QPushButton[text='Run'] {{"
            f"  background: {p.green}; color: {p.bg}; border: none; font-weight: bold; }}"
            f"QScrollArea {{ border: none; }}"
            f"QFrame[frameShape='4'] {{ color: {p.bg_overlay}; max-height: 1px; }}"
        )
