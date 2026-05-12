from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QWidget,
    QScrollArea, QComboBox, QDialogButtonBox, QFrame,
)
from PySide6.QtCore import Qt

from ..domain.workflow import Workflow, WorkflowStep
from .theme import ThemeManager, TY


class _StepRow(QWidget):
    def __init__(self, step: WorkflowStep, index: int, parent: "WorkflowEditor"):
        super().__init__()
        self._step = step
        self._parent = parent
        self._build(index)

    def _build(self, index: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        num = QLabel(f"{index + 1}.")
        num.setFixedWidth(20)
        num.setStyleSheet("color: #6c7086; font-size: 9pt; background: transparent;")
        layout.addWidget(num)

        self._cmd_edit = QLineEdit(self._step.command_template)
        self._cmd_edit.setPlaceholderText("command (use {var} for variables)")
        layout.addWidget(self._cmd_edit, 1)

        err_lbl = QLabel("on error:")
        err_lbl.setStyleSheet("color: #6c7086; font-size: 8pt; background: transparent;")
        layout.addWidget(err_lbl)

        self._on_error = QComboBox()
        self._on_error.addItems(["stop", "continue"])
        self._on_error.setCurrentText(self._step.on_error)
        self._on_error.setFixedWidth(80)
        layout.addWidget(self._on_error)

        up_btn = QPushButton("↑")
        up_btn.setFixedSize(22, 22)
        up_btn.clicked.connect(lambda: self._parent._move_step(self, -1))
        layout.addWidget(up_btn)

        down_btn = QPushButton("↓")
        down_btn.setFixedSize(22, 22)
        down_btn.clicked.connect(lambda: self._parent._move_step(self, 1))
        layout.addWidget(down_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.clicked.connect(lambda: self._parent._remove_step(self))
        layout.addWidget(del_btn)

    def get_step(self, order: int) -> WorkflowStep:
        return WorkflowStep(
            id=self._step.id,
            command_template=self._cmd_edit.text().strip(),
            on_error=self._on_error.currentText(),
            step_order=order,
        )


class WorkflowEditor(QDialog):
    def __init__(self, workflow: Workflow | None = None, parent=None):
        super().__init__(parent)
        self._workflow = workflow
        self._step_rows: list[_StepRow] = []
        self.setWindowTitle("Edit Workflow" if workflow else "New Workflow")
        self.setMinimumSize(560, 480)
        self.setModal(True)
        self._build_ui()
        if workflow:
            self._populate(workflow)
        p = ThemeManager.instance().current
        self._apply_theme(p)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Deploy to production")
        form.addRow("Name *", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Optional description")
        self._desc_edit.setMaximumHeight(60)
        form.addRow("Description", self._desc_edit)
        layout.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        steps_header = QHBoxLayout()
        steps_lbl = QLabel("Steps")
        steps_lbl.setStyleSheet(f"font-size: {TY.mono_sm}pt; font-weight: bold; background: transparent;")
        steps_header.addWidget(steps_lbl)
        steps_header.addStretch()
        add_btn = QPushButton("+ Add Step")
        add_btn.setFixedHeight(26)
        add_btn.clicked.connect(self._add_step)
        steps_header.addWidget(add_btn)
        layout.addLayout(steps_header)

        self._steps_scroll = QScrollArea()
        self._steps_scroll.setWidgetResizable(True)
        self._steps_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._steps_container = QWidget()
        self._steps_container.setStyleSheet("QWidget { background: transparent; }")
        self._steps_layout = QVBoxLayout(self._steps_container)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.setSpacing(2)
        self._steps_layout.addStretch()

        self._steps_scroll.setWidget(self._steps_container)
        layout.addWidget(self._steps_scroll, 1)

        self._error_lbl = QLabel()
        self._error_lbl.setStyleSheet("color: #f38ba8; font-size: 8pt;")
        self._error_lbl.hide()
        layout.addWidget(self._error_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, wf: Workflow) -> None:
        self._name_edit.setText(wf.name)
        self._desc_edit.setPlainText(wf.description)
        for step in wf.steps:
            self._insert_step_row(step)

    def _add_step(self) -> None:
        step = WorkflowStep(command_template="", step_order=len(self._step_rows))
        self._insert_step_row(step)

    def _insert_step_row(self, step: WorkflowStep) -> None:
        row = _StepRow(step, len(self._step_rows), self)
        self._step_rows.append(row)
        idx = self._steps_layout.count() - 1  # before stretch
        self._steps_layout.insertWidget(idx, row)
        self._renumber()

    def _remove_step(self, row: _StepRow) -> None:
        self._step_rows.remove(row)
        self._steps_layout.removeWidget(row)
        row.deleteLater()
        self._renumber()

    def _move_step(self, row: _StepRow, direction: int) -> None:
        idx = self._step_rows.index(row)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._step_rows):
            return
        self._step_rows[idx], self._step_rows[new_idx] = (
            self._step_rows[new_idx], self._step_rows[idx]
        )
        for r in self._step_rows:
            self._steps_layout.removeWidget(r)
        stretch = self._steps_layout.takeAt(0)
        for i, r in enumerate(self._step_rows):
            self._steps_layout.insertWidget(i, r)
        self._steps_layout.addStretch()
        self._renumber()

    def _renumber(self) -> None:
        for i, row in enumerate(self._step_rows):
            lbl = row.findChild(QLabel)
            if lbl:
                lbl.setText(f"{i + 1}.")

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            self._error_lbl.setText("Name is required.")
            self._error_lbl.show()
            return
        if not self._step_rows:
            self._error_lbl.setText("Add at least one step.")
            self._error_lbl.show()
            return
        self.accept()

    def result_workflow(self) -> Workflow:
        steps = [row.get_step(i) for i, row in enumerate(self._step_rows)]
        if self._workflow:
            self._workflow.name = self._name_edit.text().strip()
            self._workflow.description = self._desc_edit.toPlainText().strip()
            self._workflow.steps = steps
            return self._workflow
        return Workflow(
            name=self._name_edit.text().strip(),
            description=self._desc_edit.toPlainText().strip(),
            steps=steps,
        )

    def _apply_theme(self, p) -> None:
        self.setStyleSheet(
            f"QDialog {{ background: {p.bg_panel}; color: {p.fg}; }}"
            f"QLabel  {{ color: {p.fg}; background: transparent; }}"
            f"QLineEdit, QTextEdit, QComboBox {{ background: {p.bg}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 4px 6px; }}"
            f"QLineEdit:focus, QTextEdit:focus {{ border-color: {p.blue}; }}"
            f"QPushButton {{ background: {p.bg_overlay}; color: {p.fg};"
            f"  border: 1px solid {p.border}; border-radius: 4px; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background: {p.bg_selected}; }}"
            f"QDialogButtonBox QPushButton[text='Save'] {{"
            f"  background: {p.blue}; color: {p.bg}; border: none; font-weight: bold; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QScrollArea {{ border: none; }}"
            f"QFrame[frameShape='4'] {{ color: {p.bg_overlay}; max-height: 1px; }}"
        )
