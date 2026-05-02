from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QScrollArea
from PySide6.QtCore import Signal
from .command_block import CommandBlock
from .input_bar import InputBar
from ..domain.block import Block


class MainWindow(QMainWindow):
    command_submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Terminator")
        self.resize(960, 640)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._blocks_container = QWidget()
        self._blocks_layout = QVBoxLayout(self._blocks_container)
        self._blocks_layout.setContentsMargins(12, 12, 12, 12)
        self._blocks_layout.setSpacing(10)
        self._blocks_layout.addStretch()

        self._scroll.setWidget(self._blocks_container)

        self._input_bar = InputBar()
        self._input_bar.command_submitted.connect(self.command_submitted)

        layout.addWidget(self._scroll)
        layout.addWidget(self._input_bar)

        self._input_bar.focus()

    def add_block(self, block: Block):
        self._blocks_layout.insertWidget(
            self._blocks_layout.count() - 1,
            CommandBlock(block),
        )
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def update_input_history(self, commands: list[str]) -> None:
        self._input_bar.update_history(commands)

    def update_cwd(self, display_path: str) -> None:
        self._input_bar.update_cwd(display_path)
