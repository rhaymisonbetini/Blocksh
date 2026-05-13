from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeySequence, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QLabel, QFrame, QGraphicsDropShadowEffect,
)

from .theme import Palette, ThemeManager, get_mono_font, TY


def _time_ago(dt: datetime) -> str:
    diff = datetime.now() - dt
    s = int(diff.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{diff.days}d ago"


class _ResultItem(QWidget):
    def __init__(self, text: str, cwd: str, source_icon: str,
                 time_label: str, parent=None):
        super().__init__(parent)
        self._text = text
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        icon_lbl = QLabel(source_icon)
        icon_lbl.setFixedWidth(18)
        icon_lbl.setStyleSheet(f"font-size: {TY.mono_sm}px; background: transparent;")
        top_row.addWidget(icon_lbl)

        cmd_lbl = QLabel(text[:80] + ("…" if len(text) > 80 else ""))
        cmd_lbl.setStyleSheet(
            f"font-family: {get_mono_font()}; font-size: {TY.sm}px; font-weight: bold; background: transparent;"
        )
        top_row.addWidget(cmd_lbl, 1)

        time_lbl = QLabel(time_label)
        time_lbl.setStyleSheet(f"font-size: {TY.xs}px; background: transparent;")
        top_row.addWidget(time_lbl)

        layout.addLayout(top_row)

        if cwd:
            cwd_lbl = QLabel(cwd)
            cwd_lbl.setStyleSheet(
                f"font-size: {TY.xs}px; padding-left: 24px; background: transparent;"
            )
            layout.addWidget(cwd_lbl)
        else:
            layout.addSpacing(2)

        self.setMinimumHeight(46)

    @property
    def command_text(self) -> str:
        return self._text


class CommandPalette(QWidget):
    """VS Code-style command palette overlay — Ctrl+P."""

    command_selected  = Signal(str)
    command_executed  = Signal(str)   # Ctrl+Enter: select AND execute
    closed            = Signal()

    def __init__(self, repository, favorites_service, parent=None):
        super().__init__(parent)
        self._repository        = repository
        self._favorites_service = favorites_service
        self._debounce          = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._do_search)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_StyledBackground, False)

        self._build_ui()
        _tm = ThemeManager.instance()
        self.apply_theme(_tm.current)
        _tm.theme_changed.connect(self.apply_theme)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QFrame()
        self._card.setObjectName("palette_card")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Search input
        input_row = QWidget()
        input_row.setObjectName("palette_input_row")
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)

        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(f"font-size: {TY.xl}px; background: transparent;")
        search_icon.setFixedWidth(22)
        input_layout.addWidget(search_icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search history, favorites…")
        self._input.textChanged.connect(lambda: self._debounce.start())
        self._input.installEventFilter(self)
        input_layout.addWidget(self._input)
        card_layout.addWidget(input_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("palette_sep")
        card_layout.addWidget(sep)

        self._list = QListWidget()
        self._list.setObjectName("palette_list")
        self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSpacing(0)
        self._list.itemActivated.connect(self._on_item_activate)
        card_layout.addWidget(self._list)

        # Footer hint
        hint = QLabel("Enter — insert   Ctrl+Enter — insert & run   Esc — close")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("palette_hint")
        hint.setStyleSheet(f"font-size: {TY.xs}px; padding: 4px;")
        card_layout.addWidget(hint)

        outer.addWidget(self._card)

    # ── public API ─────────────────────────────────────────────────────────

    def focus_input(self) -> None:
        self._input.setFocus()
        self._input.selectAll()
        self._do_search()

    # ── search ─────────────────────────────────────────────────────────────

    def _do_search(self) -> None:
        query = self._input.text().strip()
        self._list.clear()

        results: list[tuple[str, str, str, str]] = []  # (text, cwd, icon, time)

        # Favorites first
        for fav in self._favorites_service.all():
            if not query or query.lower() in fav.command_text.lower():
                results.append((fav.command_text, fav.cwd, "★", "favorite"))

        # History
        if query:
            blocks = self._repository.search(query, limit=50)
        else:
            blocks = self._repository.load_recent(limit=40)

        seen: set[str] = {r[0] for r in results}
        for block in blocks:
            txt = block.command.text
            if txt not in seen:
                seen.add(txt)
                time_str = _time_ago(block.command.created_at)
                results.append((txt, block.cwd, "🕐", time_str))

        for text, cwd, icon, time_label in results[:60]:
            item_widget = _ResultItem(text, cwd, icon, time_label)
            item = QListWidgetItem(self._list)
            item.setSizeHint(item_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, item_widget)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ── event filter (keyboard nav) ────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.KeyPress:
            key  = event.key()
            mods = event.modifiers()
            if key == Qt.Key_Down:
                self._list.setFocus()
                if self._list.count():
                    self._list.setCurrentRow(0)
                return True
            if key == Qt.Key_Return or key == Qt.Key_Enter:
                if mods & Qt.ControlModifier:
                    self._accept(execute=True)
                else:
                    self._accept(execute=False)
                return True
            if key == Qt.Key_Escape:
                self.hide()
                self.closed.emit()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        key  = event.key()
        mods = event.modifiers()
        if key == Qt.Key_Escape:
            self.hide()
            self.closed.emit()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ControlModifier:
                self._accept(execute=True)
            else:
                self._accept(execute=False)
        elif key == Qt.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
            else:
                self._input.setFocus()
        elif key == Qt.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)

    def _on_item_activate(self, item: QListWidgetItem) -> None:
        self._accept(execute=False)

    def _accept(self, execute: bool) -> None:
        item = self._list.currentItem()
        if not item:
            return
        widget = self._list.itemWidget(item)
        if not isinstance(widget, _ResultItem):
            return
        text = widget.command_text
        self.hide()
        self.closed.emit()
        if execute:
            self.command_executed.emit(text)
        else:
            self.command_selected.emit(text)

    # ── theming ────────────────────────────────────────────────────────────

    def apply_theme(self, p: Palette) -> None:
        self._card.setStyleSheet(
            f"QFrame#palette_card {{"
            f"  background: {p.surface_glass};"
            f"  border: 1px solid rgba(255,255,255,0.08);"
            f"  border-radius: 12px;"
            f"}}"
            f"QWidget#palette_input_row {{"
            f"  background: transparent;"
            f"}}"
            f"QFrame#palette_sep {{"
            f"  color: {p.border}; max-height: 1px;"
            f"}}"
            f"QListWidget#palette_list {{"
            f"  background: transparent;"
            f"  outline: none;"
            f"}}"
            f"QListWidget#palette_list::item:selected {{"
            f"  background: {p.bg_selected};"
            f"  border-radius: 4px;"
            f"}}"
            f"QLabel#palette_hint {{"
            f"  color: {p.fg_muted}; background: transparent;"
            f"  border-top: 1px solid {p.border};"
            f"}}"
        )
        self._input.setStyleSheet(
            f"QLineEdit {{"
            f"  background: {p.bg_overlay}; color: {p.fg}; border: none;"
            f"  border-radius: 6px; padding: 8px 14px;"
            f"  font-size: {TY.base}px; font-family: {get_mono_font()};"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 1px solid {p.border_focus};"
            f"}}"
        )
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._card.setGraphicsEffect(shadow)
        # update child label colors
        for lbl in self.findChildren(QLabel):
            if "cwd" in (lbl.styleSheet()):
                lbl.setStyleSheet(
                    f"font-size: {TY.xs}px; padding-left: 24px; background: transparent; color: {p.fg_muted};"
                )
