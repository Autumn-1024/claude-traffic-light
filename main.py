"""
Claude Traffic Light - Claude Code 运行状态桌面红绿灯
极简版：只显示三个灯，右键弹出设置菜单
"""

import sys
import time
import psutil
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSystemTrayIcon, QMenu, QAction,
    QSlider, QDialog, QVBoxLayout, QLabel, QCheckBox, QWidgetAction
)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import (
    QPainter, QColor, QBrush, QPen, QIcon, QPixmap, QRadialGradient
)


# ── 状态 ───────────────────────────────────────────────────
class Status:
    RUNNING = "running"
    WAITING = "waiting"
    READY = "ready"
    OFFLINE = "offline"


# ── Claude 进程检测（带防抖和滞后） ─────────────────────────
class ClaudeDetector:
    def __init__(self):
        self._cpu_samples = []          # CPU 采样窗口
        self._sample_count = 15         # 采样数量
        self._current_status = Status.OFFLINE
        self._last_switch_time = 0.0    # 上次状态切换时间
        self._cooldown_sec = 3.0        # 切换冷却（秒）
        # 滞后阈值：防止在边界来回跳
        # 进入 RUNNING 需要 CPU > _enter_running，退出 RUNNING 需要 CPU < _exit_running
        self._enter_running = 6.0
        self._exit_running = 2.0
        # 进入 WAITING 需要 CPU < _enter_waiting，退出 WAITING 需要 CPU > _exit_waiting
        self._enter_waiting = 1.0
        self._exit_waiting = 3.0

    def detect(self) -> str:
        procs = self._find_claude_processes()
        if not procs:
            self._cpu_samples.clear()
            self._current_status = Status.OFFLINE
            return Status.OFFLINE

        # 采集 CPU
        total_cpu = 0.0
        for proc in procs:
            try:
                total_cpu += proc.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self._cpu_samples.append(total_cpu)
        if len(self._cpu_samples) > self._sample_count:
            self._cpu_samples.pop(0)

        # 加权移动平均：近期权重更高
        weights = [i + 1 for i in range(len(self._cpu_samples))]
        weighted_avg = sum(s * w for s, w in zip(self._cpu_samples, weights)) / sum(weights)

        # 采样不够时保持当前状态
        if len(self._cpu_samples) < 3:
            return self._current_status

        # 冷却期内不切换
        now = time.time()
        if now - self._last_switch_time < self._cooldown_sec:
            return self._current_status

        # 状态决策（带滞后）
        new_status = self._current_status

        if self._current_status == Status.RUNNING:
            # 运行中 → CPU 降到 _exit_running 以下才考虑切换
            if weighted_avg < self._exit_running:
                new_status = Status.WAITING
        elif self._current_status == Status.WAITING:
            # 等待中 → CPU 升到 _exit_waiting 以上才切运行，否则保持
            if weighted_avg > self._exit_waiting:
                new_status = Status.RUNNING
            elif weighted_avg > self._enter_waiting:
                new_status = Status.READY
        elif self._current_status == Status.READY:
            # 就绪 → CPU 高了切运行，低了切等待
            if weighted_avg > self._enter_running:
                new_status = Status.RUNNING
            elif weighted_avg < self._enter_waiting:
                new_status = Status.WAITING
        else:
            # OFFLINE → 采样够了就进 WAITING
            new_status = Status.WAITING

        if new_status != self._current_status:
            self._current_status = new_status
            self._last_switch_time = now

        return self._current_status

    def _find_claude_processes(self) -> list:
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'] or ''
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'claude' in (name + cmdline).lower():
                    if 'code' not in name.lower() and 'electron' not in name.lower():
                        procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs


# ── 红绿灯窗口 ─────────────────────────────────────────────
class TrafficLight(QWidget):
    COLORS = {
        Status.WAITING:  QColor(220, 50, 50),      # 红
        Status.READY:    QColor(240, 200, 30),      # 黄
        Status.RUNNING:  QColor(50, 200, 50),       # 绿
        Status.OFFLINE:  QColor(80, 80, 80),        # 灰
    }
    LIGHT_ORDER = [Status.WAITING, Status.READY, Status.RUNNING]

    def __init__(self):
        super().__init__()
        self._status = Status.OFFLINE
        self._light_size = 36
        self._horizontal = False  # False=竖向, True=横向
        self._drag_pos = QPoint()
        self._always_on_top = True

        self._setup_window()
        self._init_tray()
        self._init_timer()

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_size()

    def _update_size(self):
        ls = self._light_size
        margin = ls // 3
        if self._horizontal:
            w = ls * 3 + margin * 4
            h = ls * 2 + 20
        else:
            w = ls * 2 + 20
            h = ls * 3 + margin * 4
        self.setFixedSize(w, h)

    # ── 绘制 ───────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        ls = self._light_size
        margin = ls // 3
        r = ls // 2

        for i, status in enumerate(self.LIGHT_ORDER):
            color = self.COLORS[status]

            if self._horizontal:
                lx = margin + r + i * (ls + margin)
                ly = h // 2
            else:
                lx = w // 2
                ly = margin + r + i * (ls + margin)

            if self._status == status:
                grad = QRadialGradient(lx, ly, r * 1.2)
                grad.setColorAt(0, color.lighter(160))
                grad.setColorAt(0.6, color)
                grad.setColorAt(1, color.darker(200))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.NoPen)
                glow = QColor(color)
                glow.setAlpha(50)
                p.setPen(QPen(glow, 5))
                p.drawEllipse(lx - r - 2, ly - r - 2, (r + 2) * 2, (r + 2) * 2)
                p.setPen(Qt.NoPen)
            else:
                dark = color.darker(500)
                dark.setAlpha(80)
                p.setBrush(QBrush(dark))
                p.setPen(QPen(QColor(35, 35, 35), 1))

            p.drawEllipse(lx - r, ly - r, r * 2, r * 2)

        p.end()

    # ── 状态检测 ───────────────────────────────────────────
    def _init_timer(self):
        self._detector = ClaudeDetector()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(1500)
        self._check()

    def _check(self):
        status = self._detector.detect()
        if status != self._status:
            self._status = status
            self._update_tray_icon()
            self.update()

    # ── 系统托盘 ───────────────────────────────────────────
    def _init_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("Claude Traffic Light")
        self._update_tray_icon()

        menu = QMenu()
        show_act = QAction("显示", self)
        show_act.triggered.connect(lambda: (self.show(), self.activateWindow()))
        menu.addAction(show_act)

        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    def _update_tray_icon(self):
        color = self.COLORS.get(self._status, QColor(80, 80, 80))
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        self._tray.setIcon(QIcon(pix))

        names = {
            Status.RUNNING: "运行中 ⚡",
            Status.WAITING: "等待中 ⏸️",
            Status.READY: "就绪 ✅",
            Status.OFFLINE: "离线",
        }
        self._tray.setToolTip(f"Claude: {names.get(self._status, '未知')}")

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    # ── 右键菜单 ───────────────────────────────────────────
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #2d2d2d;
                color: white;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #404040;
            }
        """)

        # 方向
        orient_menu = menu.addMenu("方向")
        v_act = orient_menu.addAction("竖向")
        v_act.setCheckable(True)
        v_act.setChecked(not self._horizontal)
        v_act.triggered.connect(lambda: self._set_orientation(False))
        h_act = orient_menu.addAction("横向")
        h_act.setCheckable(True)
        h_act.setChecked(self._horizontal)
        h_act.triggered.connect(lambda: self._set_orientation(True))

        # 灯大小
        size_label = QAction(f"灯大小: {self._light_size}px", self)
        size_label.setEnabled(False)
        menu.addAction(size_label)

        size_slider = QSlider(Qt.Horizontal)
        size_slider.setRange(10, 100)
        size_slider.setValue(self._light_size)
        size_slider.setMinimumWidth(120)
        size_slider.setStyleSheet("""
            QSlider { padding: 4px 8px; }
            QSlider::groove:horizontal { background: #555; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #4CAF50; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        size_slider.valueChanged.connect(lambda v: self._set_light_size(v, size_label))
        size_action = QWidgetAction(self)
        size_action.setDefaultWidget(size_slider)
        menu.addAction(size_action)

        # 置顶
        topmost_act = QAction("窗口置顶", self)
        topmost_act.setCheckable(True)
        topmost_act.setChecked(self._always_on_top)
        topmost_act.triggered.connect(self._toggle_topmost)
        menu.addAction(topmost_act)

        menu.addSeparator()

        # 最小化到托盘
        hide_act = QAction("最小化到托盘", self)
        hide_act.triggered.connect(self.hide)
        menu.addAction(hide_act)

        menu.addSeparator()

        # 退出
        quit_act = QAction("退出", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)

        menu.exec_(event.globalPos())

    def _set_light_size(self, size, label=None):
        self._light_size = size
        if label:
            label.setText(f"灯大小: {size}px")
        self._update_size()
        self.update()

    def _set_orientation(self, horizontal):
        self._horizontal = horizontal
        self._update_size()
        self.update()

    def _toggle_topmost(self, checked):
        self._always_on_top = checked
        flags = Qt.FramelessWindowHint | Qt.Tool
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _quit(self):
        self._tray.hide()
        QApplication.quit()

    # ── 拖动 ───────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = QPoint()


# ── 启动 ───────────────────────────────────────────────────
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    light = TrafficLight()
    light.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
