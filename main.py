"""
Claude Traffic Light - Claude Code 运行状态桌面红绿灯
"""

import sys
import time
import threading
import psutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QCheckBox,
    QPushButton, QGraphicsDropShadowEffect, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QIcon, QPixmap,
    QLinearGradient, QRadialGradient, QFont, QCursor
)


# ── 状态枚举 ──────────────────────────────────────────────
class Status:
    RUNNING = "running"      # 绿灯 - 运行中
    WAITING = "waiting"      # 红灯 - 等待中
    READY = "ready"          # 黄灯 - 就绪
    OFFLINE = "offline"      # 灰灯 - Claude 未运行


# ── 状态检测器 ─────────────────────────────────────────────
class ClaudeDetector:
    """检测 Claude CLI 的运行状态"""

    def __init__(self):
        self._last_cpu = 0.0
        self._cpu_samples = []
        self._sample_count = 5
        self._running_threshold = 5.0    # CPU > 5% 认为在运行
        self._waiting_threshold = 1.0    # CPU < 1% 认为在等待

    def detect(self) -> str:
        """检测 Claude 状态"""
        claude_procs = self._find_claude_processes()

        if not claude_procs:
            return Status.OFFLINE

        # 计算所有 claude 进程的总 CPU 占用
        total_cpu = 0.0
        for proc in claude_procs:
            try:
                total_cpu += proc.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 采样平均
        self._cpu_samples.append(total_cpu)
        if len(self._cpu_samples) > self._sample_count:
            self._cpu_samples.pop(0)

        avg_cpu = sum(self._cpu_samples) / len(self._cpu_samples)

        # 判断状态
        if avg_cpu > self._running_threshold:
            return Status.RUNNING
        elif avg_cpu < self._waiting_threshold and len(self._cpu_samples) >= 3:
            return Status.WAITING
        else:
            # 还在采样中，默认等待
            return Status.WAITING if len(self._cpu_samples) < 3 else Status.READY

    def _find_claude_processes(self) -> list:
        """查找所有 claude 相关进程"""
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'] or ''
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'claude' in name.lower() or 'claude' in cmdline.lower():
                    # 排除 vscode 等的 claude 插件进程
                    if 'code' not in name.lower() and 'electron' not in name.lower():
                        procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs


# ── 红绿灯绘制 ─────────────────────────────────────────────
class TrafficLightWidget(QWidget):
    """红绿灯控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = Status.OFFLINE
        self._light_size = 40
        self.setMinimumSize(80, 200)

    def set_status(self, status: str):
        if self._status != status:
            self._status = status
            self.update()

    def set_light_size(self, size: int):
        self._light_size = size
        self.setMinimumSize(size * 2, size * 6)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        ls = self._light_size
        margin = ls // 4
        center_x = w // 2

        # 绘制灯箱背景（深灰色圆角矩形）
        box_w = ls * 2
        box_h = ls * 3 + margin * 4
        box_x = center_x - box_w // 2
        box_y = h // 2 - box_h // 2
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        painter.setPen(QPen(QColor(30, 30, 30), 2))
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 12, 12)

        # 三个灯的位置
        colors = [
            (Status.WAITING, QColor(220, 50, 50)),     # 红
            (Status.READY, QColor(240, 200, 30)),       # 黄
            (Status.RUNNING, QColor(50, 200, 50)),      # 绿
        ]

        for i, (status, color) in enumerate(colors):
            cx = center_x
            cy = box_y + margin + ls // 2 + i * (ls + margin)
            r = ls // 2

            if self._status == status:
                # 亮灯 - 带发光效果
                gradient = QRadialGradient(cx, cy, r * 1.2)
                lighter = color.lighter(150)
                gradient.setColorAt(0, lighter)
                gradient.setColorAt(0.6, color)
                gradient.setColorAt(1, color.darker(200))
                painter.setBrush(QBrush(gradient))

                # 外发光
                glow = QColor(color)
                glow.setAlpha(60)
                painter.setPen(QPen(glow, 6))
                painter.drawEllipse(cx - r - 3, cy - r - 3, (r + 3) * 2, (r + 3) * 2)
                painter.setPen(Qt.NoPen)
            else:
                # 灭灯 - 暗色
                dark = color.darker(400)
                dark.setAlpha(120)
                painter.setBrush(QBrush(dark))
                painter.setPen(QPen(QColor(40, 40, 40), 1))

            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        painter.end()


# ── 主窗口 ─────────────────────────────────────────────────
class MainWindow(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._status = Status.OFFLINE
        self._light_size = 40
        self._always_on_top = True
        self._drag_pos = QPoint()
        self._settings_visible = False

        self._init_ui()
        self._init_tray()
        self._init_detector()
        self._init_timer()

    def _init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("Claude Traffic Light")
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(120, 320)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 红绿灯
        self._traffic_light = TrafficLightWidget()
        layout.addWidget(self._traffic_light, alignment=Qt.AlignCenter)

        # 状态文字
        self._status_label = QLabel("检测中...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 12px;
                font-weight: bold;
                background: rgba(0, 0, 0, 120);
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        layout.addWidget(self._status_label)

        # 设置面板（默认隐藏）
        self._settings_panel = self._create_settings_panel()
        self._settings_panel.hide()
        layout.addWidget(self._settings_panel)

        # 按钮栏
        btn_layout = QHBoxLayout()

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(60, 60, 60, 180);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(80, 80, 80, 200);
            }
        """)
        self._settings_btn.clicked.connect(self._toggle_settings)
        btn_layout.addWidget(self._settings_btn)

        self._minimize_btn = QPushButton("—")
        self._minimize_btn.setFixedSize(28, 28)
        self._minimize_btn.setStyleSheet(self._settings_btn.styleSheet())
        self._minimize_btn.clicked.connect(self._minimize_to_tray)
        btn_layout.addWidget(self._minimize_btn)

        layout.addLayout(btn_layout)

    def _create_settings_panel(self) -> QWidget:
        """创建设置面板"""
        panel = QGroupBox("设置")
        panel.setStyleSheet("""
            QGroupBox {
                background: rgba(40, 40, 40, 200);
                border-radius: 10px;
                border: 1px solid rgba(80, 80, 80, 150);
                color: white;
                font-size: 11px;
                padding-top: 20px;
                margin-top: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 20, 10, 10)

        # 灯大小滑块
        size_label = QLabel("灯大小")
        size_label.setStyleSheet("color: white; font-size: 11px;")
        layout.addWidget(size_label)

        self._size_slider = Qt.Horizontal
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setRange(20, 80)
        size_slider.setValue(self._light_size)
        size_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: rgba(100, 100, 100, 100);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        size_slider.valueChanged.connect(self._on_size_changed)
        layout.addWidget(size_slider)

        # 置顶复选框
        self._topmost_cb = QCheckBox("窗口置顶")
        self._topmost_cb.setChecked(True)
        self._topmost_cb.setStyleSheet("color: white; font-size: 11px;")
        self._topmost_cb.stateChanged.connect(self._on_topmost_changed)
        layout.addWidget(self._topmost_cb)

        return panel

    def _init_tray(self):
        """初始化系统托盘"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("Claude Traffic Light")

        # 托盘图标（简单画一个灯）
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor(100, 100, 100)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        self._tray.setIcon(QIcon(pixmap))

        # 托盘菜单
        menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _init_detector(self):
        """初始化状态检测器"""
        self._detector = ClaudeDetector()

    def _init_timer(self):
        """初始化定时器"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_status)
        self._timer.start(1500)  # 1.5秒检测一次
        self._check_status()  # 立即检测一次

    def _check_status(self):
        """检测 Claude 状态"""
        status = self._detector.detect()
        if status != self._status:
            self._status = status
            self._update_display()

    def _update_display(self):
        """更新显示"""
        status_map = {
            Status.RUNNING: ("运行中 ⚡", "green"),
            Status.WAITING: ("等待中 ⏸️", "red"),
            Status.READY: ("就绪 ✅", "yellow"),
            Status.OFFLINE: ("离线", "gray"),
        }

        text, color = status_map.get(self._status, ("未知", "gray"))

        self._traffic_light.set_status(self._status)
        self._status_label.setText(text)

        # 更新托盘图标颜色
        color_map = {
            "green": QColor(50, 200, 50),
            "red": QColor(220, 50, 50),
            "yellow": QColor(240, 200, 30),
            "gray": QColor(100, 100, 100),
        }
        c = color_map.get(color, QColor(100, 100, 100))
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        self._tray.setIcon(QIcon(pixmap))
        self._tray.setToolTip(f"Claude: {text}")

    def _toggle_settings(self):
        """切换设置面板"""
        self._settings_visible = not self._settings_visible
        if self._settings_visible:
            self._settings_panel.show()
            self.setFixedSize(120, 450)
        else:
            self._settings_panel.hide()
            self.setFixedSize(120, 320)

    def _on_size_changed(self, value: int):
        """灯大小改变"""
        self._light_size = value
        self._traffic_light.set_light_size(value)

    def _on_topmost_changed(self, state: int):
        """置顶状态改变"""
        self._always_on_top = (state == Qt.Checked)
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self._always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _minimize_to_tray(self):
        """最小化到托盘"""
        self.hide()

    def _show_from_tray(self):
        """从托盘恢复显示"""
        self.show()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _quit(self):
        """退出"""
        self._tray.hide()
        QApplication.quit()

    # ── 窗口拖动 ──────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()

    def paintEvent(self, event):
        """绘制窗口背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.setPen(QPen(QColor(60, 60, 60, 150), 1))
        painter.drawRoundedRect(self.rect(), 16, 16)
        painter.end()


# ── 启动 ───────────────────────────────────────────────────
def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口时不退出，最小化到托盘

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
