from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Signal, QTimer
from .command_block import CommandBlock
from .input_bar import InputBar
from .sidebar import Sidebar
from .tab_bar import TabBar
from ..domain.block import Block


class MainWindow(QMainWindow):
    command_submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Terminator")
        self.resize(1100, 700)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        root.addWidget(self._sidebar)

        # Vertical divider
        v_sep = QFrame()
        v_sep.setFrameShape(QFrame.VLine)
        v_sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-width: 1px; }")
        root.addWidget(v_sep)

        # Right panel (tab bar + scroll + input)
        right = QWidget()
        right.setStyleSheet("QWidget { background-color: #0d0f1a; }")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._tab_bar = TabBar()
        right_layout.addWidget(self._tab_bar)

        h_sep = QFrame()
        h_sep.setFrameShape(QFrame.HLine)
        h_sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        right_layout.addWidget(h_sep)

        # Scrollable blocks area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._blocks_container = QWidget()
        self._blocks_container.setStyleSheet("QWidget { background: transparent; }")
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(20, 16, 20, 16)
        self._blocks_layout.setSpacing(12)
        self._blocks_layout.addStretch()

        self._scroll.setWidget(self._blocks_container)
        right_layout.addWidget(self._scroll)

        # Bottom divider
        b_sep = QFrame()
        b_sep.setFrameShape(QFrame.HLine)
        b_sep.setStyleSheet("QFrame { color: #1e2235; background: #1e2235; max-height: 1px; }")
        right_layout.addWidget(b_sep)

        self._input_bar = InputBar()
        self._input_bar.command_submitted.connect(self.command_submitted)
        right_layout.addWidget(self._input_bar)

        root.addWidget(right)
        self._input_bar.focus()

    def add_block(self, block: Block) -> None:
        widget = CommandBlock(block)
        widget.remove_requested.connect(self._remove_block)
        self._blocks_layout.insertWidget(
            self._blocks_layout.count() - 1,
            widget,
        )
        # Defer scroll to the next event loop tick so the layout finishes
        # recalculating sizes before we read verticalScrollBar().maximum()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _remove_block(self, block_widget: QWidget) -> None:
        self._blocks_layout.removeWidget(block_widget)
        block_widget.deleteLater()

    def update_input_history(self, commands: list[str]) -> None:
        self._input_bar.update_history(commands)

    def update_cwd(self, display_path: str) -> None:
        self._sidebar.update_cwd(display_path)
        self._input_bar.update_cwd(display_path)
