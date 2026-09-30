"""
Tests for the PyQt5 port in RQB2-config/demo-patches/led-painter-convert-to-pwm.py
(issue #302): LED Painter moves from PySide6 (crashes on the Pi 5 kernel) to the
system PyQt5.
"""

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONVERTER = os.path.join(_HERE, "..", "..", "RQB2-config", "demo-patches", "led-painter-convert-to-pwm.py")

# The relevant parts of upstream LED_painter.py at the pinned commit
UPSTREAM = '''import sys
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)
from PySide6.QtGui import QImage, QPixmap, QPen, QAction, QPainter, QColor
from PySide6.QtCore import Qt, QPoint

class Window(QMainWindow):
    def mousePressEvent(self, event):
        scaled_pos = self.scalePosition(event.position())

    def scalePosition(self, pos):
        scaled_x = pos.x() / self.xScaleFactor
        scaled_y = pos.y() / self.yScaleFactor
        return QPoint(min(scaled_x, 31), min(scaled_y, 7))

    def save(self):
        fileSavedDialog.exec()


def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
'''


@pytest.fixture
def converter():
    spec = importlib.util.spec_from_file_location("painter_converter", _CONVERTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _port(converter, tmp_path, source=UPSTREAM):
    (tmp_path / "LED_painter.py").write_text(source)
    assert converter.port_to_pyqt5(str(tmp_path))
    return (tmp_path / "LED_painter.py").read_text()


def test_imports_move_to_pyqt5(converter, tmp_path):
    out = _port(converter, tmp_path)
    assert "PySide6" not in out
    assert "from PyQt5.QtWidgets import (\n    QAction," in out
    assert "from PyQt5.QtGui import QImage, QPixmap, QPen, QPainter, QColor" in out
    assert "from PyQt5.QtCore import Qt, QPoint" in out


def test_qt6_only_calls_are_replaced(converter, tmp_path):
    out = _port(converter, tmp_path)
    assert "event.pos()" in out and ".position()" not in out
    assert ".exec_()" in out and ".exec()" not in out
    assert "QPoint(int(min(scaled_x, 31)), int(min(scaled_y, 7)))" in out


def test_ctrl_c_handler_is_installed(converter, tmp_path):
    out = _port(converter, tmp_path)
    assert "signal.signal(signal.SIGINT, lambda *_: app.quit())" in out
    compile(out, "LED_painter.py", "exec")


def test_port_is_idempotent(converter, tmp_path):
    once = _port(converter, tmp_path)
    assert _port(converter, tmp_path, once) == once


def test_unexpected_upstream_fails_loudly(converter, tmp_path):
    changed = UPSTREAM.replace("from PySide6.QtCore import Qt, QPoint", "import PySide6.QtCore as QtCore")
    (tmp_path / "LED_painter.py").write_text(changed)
    with pytest.raises(RuntimeError):
        converter.port_to_pyqt5(str(tmp_path))


def test_requirements_drop_pyside6(converter, tmp_path):
    (tmp_path / "requirements.txt").write_text("PySide6\nPySide6_Addons\nshiboken6\nsetuptools==75.5.0\n")
    converter.update_requirements(str(tmp_path))
    active = [l for l in (tmp_path / "requirements.txt").read_text().splitlines() if l and not l.startswith("#")]
    assert active == ["setuptools==75.5.0"]
