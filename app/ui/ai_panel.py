from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QPushButton, QPlainTextEdit, QTextEdit, QFrame, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QKeyEvent

from .theme import Palette, ThemeManager, TY, FONT_FAMILY


# ── tool call row ─────────────────────────────────────────────────────────────

_TOOL_ICONS = {
    "read_file":    "📄",
    "list_dir":     "📂",
    "search_files": "🔍",
    "run_command":  "⚙",
    "ask_user":     "💬",
}


class _ToolCallRow(QWidget):
    def __init__(self, name: str, args_preview: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolCallRow")
        self._name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)

        icon = QLabel(_TOOL_ICONS.get(name, "🔧"))
        icon.setFixedWidth(16)
        icon.setStyleSheet(f"background: transparent; font-size: {TY.base}px;")
        layout.addWidget(icon)

        preview = args_preview[:60] + ("…" if len(args_preview) > 60 else "")
        self._label = QLabel(f"<b>{name}</b>({preview})")
        self._label.setStyleSheet("background: transparent;")
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._label, 1)

        self._status = QLabel("…")
        self._status.setFixedWidth(18)
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setStyleSheet("background: transparent;")
        layout.addWidget(self._status)

        p = ThemeManager.instance().current
        self.apply_theme(p)

    def set_result(self, result: str, is_error: bool) -> None:
        self._status.setText("✗" if is_error else "✓")
        p = ThemeManager.instance().current
        color = p.red if is_error else p.green
        self._status.setStyleSheet(f"color: {color}; background: transparent; font-weight: bold;")
        preview = result[:80].replace("\n", " ")
        if preview:
            self._label.setToolTip(preview)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget#ToolCallRow {{ background: {p.bg_overlay}; border-radius: 6px;"
            f" border: 1px solid {p.border}; }}"
        )
        self._label.setStyleSheet(
            f"color: {p.fg_muted}; background: transparent;"
            f" font-family: '{FONT_FAMILY}'; font-size: {TY.mono_sm}px;"
        )


# ── permission / ask inline widget ────────────────────────────────────────────

class _InlinePrompt(QWidget):
    allowed  = Signal()
    denied   = Signal()
    answered = Signal(str)

    def __init__(self, question: str, mode: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("InlinePrompt")
        self._mode = mode
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        icon = QLabel("🤖")
        icon.setFixedWidth(22)
        icon.setStyleSheet(f"background: transparent; font-size: {TY.md}px;")
        layout.addWidget(icon)

        short = question[:100] + ("…" if len(question) > 100 else "")
        self._lbl = QLabel(f"<b>{'Run:' if mode == 'permission' else 'Question:'}</b>  {short}")
        self._lbl.setWordWrap(True)
        layout.addWidget(self._lbl, 1)

        if mode == "permission":
            allow = QPushButton("Allow")
            allow.setFixedHeight(26)
            allow.clicked.connect(lambda: (self.hide(), self.allowed.emit()))
            layout.addWidget(allow)
            deny = QPushButton("Deny")
            deny.setFixedHeight(26)
            deny.clicked.connect(lambda: (self.hide(), self.denied.emit()))
            layout.addWidget(deny)
            self._allow_btn = allow
            self._deny_btn  = deny
        else:
            self._input = QPlainTextEdit()
            self._input.setFixedHeight(32)
            self._input.setPlaceholderText("Your answer…")
            layout.addWidget(self._input, 1)
            send = QPushButton("Send")
            send.setFixedHeight(26)
            send.clicked.connect(self._on_send)
            self._input.installEventFilter(self)
            layout.addWidget(send)

        p = ThemeManager.instance().current
        self.apply_theme(p)

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        self.hide()
        self.answered.emit(text)

    def eventFilter(self, obj, event) -> bool:
        if isinstance(event, QKeyEvent) and event.key() == Qt.Key_Return:
            if not (event.modifiers() & Qt.ShiftModifier):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget#InlinePrompt {{ background: {p.bg_overlay};"
            f" border: 1px solid {p.border}; border-radius: 8px; }}"
        )
        self._lbl.setStyleSheet(
            f"color: {p.fg}; background: transparent;"
            f" font-family: '{FONT_FAMILY}'; font-size: {TY.mono_sm}px;"
        )


# ── assistant turn widget ─────────────────────────────────────────────────────

class _AssistantTurn(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AssistantTurn")
        self._accumulated = ""
        self._tool_rows: list[_ToolCallRow] = []
        self._pending_prompts: list[_InlinePrompt] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._tools_container = QWidget()
        self._tools_container.setStyleSheet("background: transparent;")
        self._tools_layout    = QVBoxLayout(self._tools_container)
        self._tools_layout.setContentsMargins(0, 0, 0, 0)
        self._tools_layout.setSpacing(4)
        layout.addWidget(self._tools_container)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFrameShape(QFrame.NoFrame)
        self._text_edit.document().setDocumentMargin(0)
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._text_edit)

        self._prompts_container = QWidget()
        self._prompts_container.setStyleSheet("background: transparent;")
        self._prompts_layout    = QVBoxLayout(self._prompts_container)
        self._prompts_layout.setContentsMargins(0, 0, 0, 0)
        self._prompts_layout.setSpacing(4)
        layout.addWidget(self._prompts_container)

        p = ThemeManager.instance().current
        self.apply_theme(p)
        ThemeManager.instance().theme_changed.connect(self.apply_theme)

    def append_text(self, delta: str) -> None:
        self._accumulated += delta
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(delta)
        self._text_edit.setTextCursor(cursor)
        self._adjust_height()

    def finalize_markdown(self) -> None:
        if self._accumulated.strip():
            self._text_edit.setMarkdown(self._accumulated)
            self._adjust_height()

    def add_tool_row(self, name: str, args_preview: str) -> _ToolCallRow:
        row = _ToolCallRow(name, args_preview, self._tools_container)
        row.apply_theme(ThemeManager.instance().current)
        self._tools_layout.addWidget(row)
        self._tool_rows.append(row)
        return row

    def last_tool_row(self) -> _ToolCallRow | None:
        return self._tool_rows[-1] if self._tool_rows else None

    def add_permission_prompt(self, question: str, mode: str) -> _InlinePrompt:
        prompt = _InlinePrompt(question, mode, self._prompts_container)
        prompt.apply_theme(ThemeManager.instance().current)
        self._prompts_layout.addWidget(prompt)
        self._pending_prompts.append(prompt)
        return prompt

    def _adjust_height(self) -> None:
        doc_h = int(self._text_edit.document().size().height())
        self._text_edit.setFixedHeight(max(doc_h + 4, 20))

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget#AssistantTurn {{ background: {p.bg_surface};"
            f" border-radius: 10px; border-left: 3px solid {p.blue}; }}"
        )
        self._text_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none; color: {p.fg}; }}"
        )
        f = QFont(FONT_FAMILY)
        f.setPixelSize(TY.mono_base)
        self._text_edit.setFont(f)
        for row in self._tool_rows:
            row.apply_theme(p)
        for pr in self._pending_prompts:
            pr.apply_theme(p)


# ── user message bubble ───────────────────────────────────────────────────────

class _UserBubble(QWidget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.addStretch()
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(420)
        layout.addWidget(lbl)
        self._lbl = lbl
        p = ThemeManager.instance().current
        self.apply_theme(p)
        ThemeManager.instance().theme_changed.connect(self.apply_theme)

    def apply_theme(self, p: Palette) -> None:
        self._lbl.setStyleSheet(
            f"background: {p.blue}; color: {p.bg}; padding: 8px 12px;"
            f" border-radius: 10px; font-family: '{FONT_FAMILY}';"
            f" font-size: {TY.mono_base}px;"
        )


# ── conversation view ─────────────────────────────────────────────────────────

class _ConversationView(QScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

        self._container = QWidget()
        self._layout    = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(10)
        self._layout.addStretch()
        self.setWidget(self._container)

        p = ThemeManager.instance().current
        self.apply_theme(p)
        ThemeManager.instance().theme_changed.connect(self.apply_theme)

    def add_user(self, text: str) -> None:
        bubble = _UserBubble(text, self._container)
        self._layout.insertWidget(self._layout.count() - 1, bubble)
        QTimer.singleShot(0, self._scroll_bottom)

    def begin_turn(self) -> _AssistantTurn:
        turn = _AssistantTurn(self._container)
        self._layout.insertWidget(self._layout.count() - 1, turn)
        QTimer.singleShot(0, self._scroll_bottom)
        return turn

    def _scroll_bottom(self) -> None:
        vsb = self.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QScrollArea {{ background: {p.bg}; border: none; }}"
        )
        self._container.setStyleSheet(f"background: {p.bg};")


# ── input bar ─────────────────────────────────────────────────────────────────

class _AiInputBar(QWidget):
    submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AiInputBar")
        self.setFixedHeight(64)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(0)

        # inner card container
        self._card = QFrame()
        self._card.setObjectName("AiInputCard")
        card_layout = QHBoxLayout(self._card)
        card_layout.setContentsMargins(10, 6, 8, 6)
        card_layout.setSpacing(8)

        self._edit = QPlainTextEdit()
        self._edit.setFixedHeight(36)
        self._edit.setPlaceholderText("Ask anything… (Enter to send, Shift+Enter for newline)")
        self._edit.installEventFilter(self)
        card_layout.addWidget(self._edit, 1)

        self._send = QPushButton("Send ↵")
        self._send.setFixedHeight(28)
        self._send.setFixedWidth(72)
        self._send.clicked.connect(self._on_send)
        card_layout.addWidget(self._send)

        outer.addWidget(self._card)

        p = ThemeManager.instance().current
        self.apply_theme(p)
        ThemeManager.instance().theme_changed.connect(self.apply_theme)

    def focus(self) -> None:
        self._edit.setFocus()

    def set_enabled(self, v: bool) -> None:
        self._edit.setEnabled(v)
        self._send.setEnabled(v)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._edit and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if not (event.modifiers() & Qt.ShiftModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)

    def _on_send(self) -> None:
        text = self._edit.toPlainText().strip()
        if text:
            self._edit.clear()
            self.submitted.emit(text)

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"QWidget#AiInputBar {{ background: {p.bg_overlay};"
            f" border-top: 1px solid {p.border}; }}"
        )
        self._card.setStyleSheet(
            f"QFrame#AiInputCard {{ background: {p.bg_surface};"
            f" border: 1px solid {p.border}; border-radius: 10px; }}"
            f"QFrame#AiInputCard:focus-within {{ border-color: {p.blue}; }}"
        )
        self._edit.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; color: {p.fg}; border: none;"
            f" font-family: '{FONT_FAMILY}'; font-size: {TY.mono_base}px; padding: 2px 4px; }}"
        )
        self._send.setStyleSheet(
            f"QPushButton {{ background: {p.blue}; color: {p.bg}; border: none;"
            f" border-radius: 6px; font-family: '{FONT_FAMILY}';"
            f" font-size: {TY.mono_sm}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #74b0e8; }}"
            f"QPushButton:disabled {{ background: {p.bg_overlay}; color: {p.fg_muted}; }}"
        )


# ── main AI panel ─────────────────────────────────────────────────────────────

class AiPanel(QWidget):
    """Floating overlay panel for multi-turn AI conversations."""

    closed          = Signal()
    command_ready   = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session        = None
        self._worker         = None
        self._current_turn:  _AssistantTurn | None = None
        self._pending_prompt: _InlinePrompt | None  = None
        self._tool_row_map:  dict[str, _ToolCallRow] = {}

        self._build_ui()
        self.hide()

        p = ThemeManager.instance().current
        self.apply_theme(p)
        ThemeManager.instance().theme_changed.connect(self.apply_theme)

    # ── public API ────────────────────────────────────────────────────────────

    def attach_session(self, session) -> None:
        self._session = session

    def submit(self, text: str) -> None:
        if self._session is None:
            return
        self._conv.add_user(text)
        self._start_worker(text)

    def show_panel(self) -> None:
        self.show()
        self.raise_()
        self._input.focus()

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setObjectName("AiHeader")
        self._header.setFixedHeight(52)
        hlay = QHBoxLayout(self._header)
        hlay.setContentsMargins(16, 0, 12, 0)
        hlay.setSpacing(10)

        self._title_icon = QLabel("✦")
        self._title_icon.setStyleSheet(f"font-size: {TY.lg}px; background: transparent;")
        hlay.addWidget(self._title_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._title_lbl = QLabel("AI Assistant")
        self._title_lbl.setStyleSheet(
            f"font-family: '{FONT_FAMILY}'; font-size: {TY.lg}px;"
            f" font-weight: bold; background: transparent;"
        )
        title_col.addWidget(self._title_lbl)
        self._subtitle_lbl = QLabel("Multi-turn agent")
        self._subtitle_lbl.setStyleSheet(
            f"font-family: '{FONT_FAMILY}'; font-size: {TY.xs}px; background: transparent;"
        )
        title_col.addWidget(self._subtitle_lbl)
        hlay.addLayout(title_col, 1)

        self._new_btn = QPushButton("New Chat")
        self._new_btn.setFixedHeight(26)
        self._new_btn.clicked.connect(self._on_new)
        hlay.addWidget(self._new_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.clicked.connect(self._on_close)
        hlay.addWidget(self._close_btn)

        root.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("AiSep")
        root.addWidget(sep)

        self._conv = _ConversationView(self)
        root.addWidget(self._conv, 1)

        self._input = _AiInputBar(self)
        self._input.submitted.connect(self.submit)
        root.addWidget(self._input)

    # ── worker lifecycle ──────────────────────────────────────────────────────

    def _start_worker(self, text: str) -> None:
        from ..services.ai_service import AgentWorker

        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker.deleteLater()
            self._worker = None

        self._current_turn = self._conv.begin_turn()
        self._tool_row_map.clear()
        self._pending_prompt = None

        self._input.set_enabled(False)

        worker = AgentWorker(self._session, text)
        self._worker = worker

        worker.text_delta.connect(self._on_text_delta)
        worker.tool_call_start.connect(self._on_tool_start)
        worker.tool_call_end.connect(self._on_tool_end)
        worker.turn_complete.connect(self._on_turn_complete)
        worker.permission_needed.connect(self._on_permission_needed)
        worker.user_asked.connect(self._on_user_asked)
        worker.command_ready.connect(self._on_command_ready)
        worker.error_occurred.connect(self._on_error)
        worker.finished.connect(lambda w=worker: self._retire_worker(w))

        worker.start()

    def _retire_worker(self, worker) -> None:
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()

    # ── agent signal handlers ─────────────────────────────────────────────────

    def _on_text_delta(self, text: str) -> None:
        if self._current_turn:
            self._current_turn.append_text(text)
            QTimer.singleShot(0, self._conv._scroll_bottom)

    def _on_tool_start(self, name: str, args_preview: str) -> None:
        if self._current_turn:
            row = self._current_turn.add_tool_row(name, args_preview)
            self._tool_row_map[name + args_preview] = row
            QTimer.singleShot(0, self._conv._scroll_bottom)

    def _on_tool_end(self, name: str, result: str, is_error: bool) -> None:
        row = self._current_turn.last_tool_row() if self._current_turn else None
        if row:
            row.set_result(result, is_error)

    def _on_turn_complete(self) -> None:
        if self._current_turn:
            self._current_turn.finalize_markdown()
        self._input.set_enabled(True)
        self._input.focus()

    def _on_permission_needed(self, command: str) -> None:
        if self._current_turn is None:
            return
        prompt = self._current_turn.add_permission_prompt(command, "permission")
        self._pending_prompt = prompt
        worker = self._worker

        def _allow():
            if worker:
                worker.grant_permission(True)
        def _deny():
            if worker:
                worker.grant_permission(False)

        prompt.allowed.connect(_allow)
        prompt.denied.connect(_deny)
        QTimer.singleShot(0, self._conv._scroll_bottom)

    def _on_user_asked(self, question: str) -> None:
        if self._current_turn is None:
            return
        prompt = self._current_turn.add_permission_prompt(question, "ask")
        self._pending_prompt = prompt
        worker = self._worker

        def _answer(text: str):
            if worker:
                worker.answer_question(text)

        prompt.answered.connect(_answer)
        QTimer.singleShot(0, self._conv._scroll_bottom)

    def _on_command_ready(self, cmd: str) -> None:
        if self._current_turn:
            self._current_turn.finalize_markdown()
        self._input.set_enabled(True)
        self.command_ready.emit(cmd)

    def _on_error(self, msg: str) -> None:
        if self._current_turn:
            self._current_turn.append_text(f"\n⚠  {msg}")
        self._input.set_enabled(True)

    # ── header actions ────────────────────────────────────────────────────────

    def _on_new(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker.deleteLater()
            self._worker = None
        if self._session is not None:
            self._session.clear()
        while self._conv._layout.count() > 1:
            item = self._conv._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_turn = None
        self._input.set_enabled(True)
        self._input.focus()

    def _on_close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait(3000)
            self._worker.deleteLater()
            self._worker = None
        self.hide()
        self.closed.emit()

    # ── keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self._on_close()
        else:
            super().keyPressEvent(event)

    # ── theming ───────────────────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self.setStyleSheet(
            f"AiPanel {{ background: {p.bg}; border-left: 1px solid {p.border}; }}"
        )
        self._header.setStyleSheet(
            f"QWidget#AiHeader {{ background: {p.bg_overlay};"
            f" border-bottom: 1px solid {p.border}; }}"
        )
        self._title_icon.setStyleSheet(
            f"color: {p.blue}; font-size: {TY.lg}px; background: transparent;"
        )
        self._title_lbl.setStyleSheet(
            f"color: {p.fg}; font-family: '{FONT_FAMILY}'; font-size: {TY.lg}px;"
            f" font-weight: bold; background: transparent;"
        )
        self._subtitle_lbl.setStyleSheet(
            f"color: {p.fg_muted}; font-family: '{FONT_FAMILY}';"
            f" font-size: {TY.xs}px; background: transparent;"
        )
        self._new_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted};"
            f" border: 1px solid {p.border}; border-radius: 6px;"
            f" font-family: '{FONT_FAMILY}'; font-size: {TY.mono_sm}px;"
            f" padding: 2px 10px; }}"
            f"QPushButton:hover {{ color: {p.fg}; border-color: {p.fg_muted}; }}"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.fg_muted};"
            f" border: none; font-size: {TY.base}px; }}"
            f"QPushButton:hover {{ color: {p.red}; }}"
        )
        self.findChild(QFrame, "AiSep").setStyleSheet(
            f"QFrame {{ color: {p.border}; max-height: 1px; }}"
        )
