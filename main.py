"""
Claude Traffic Light - Claude Code 运行状态桌面红绿灯
极简版：只显示三个灯，右键弹出设置菜单
"""

import sys
import os
import json
import shutil
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


# ── Claude 状态检测（Hook 文件模式 + CPU 兜底） ─────────────
class ClaudeDetector:
    STATUS_FILE = os.path.join(os.path.expanduser("~"), ".claude", "traffic-light-status")

    def __init__(self):
        self._fallback = CpuFallbackDetector()

    def detect(self) -> str:
        # 优先读 hook 写入的状态文件
        if os.path.exists(self.STATUS_FILE):
            try:
                mtime = os.path.getmtime(self.STATUS_FILE)
                import time
                age = time.time() - mtime
                with open(self.STATUS_FILE, "r") as f:
                    status = f.read().strip()
                # 文件超过 60 秒没更新，认为 Claude 已离线
                if age > 60:
                    return Status.OFFLINE
                if status == "running":
                    return Status.RUNNING
                elif status == "ready":
                    return Status.READY
                elif status == "waiting":
                    return Status.WAITING
                elif status == "offline":
                    return Status.OFFLINE
            except Exception:
                pass

        # 兜底：用 CPU 检测
        return self._fallback.detect()


class CpuFallbackDetector:
    """CPU 检测兜底方案"""
    def __init__(self):
        self._cpu_samples = []
        self._sample_count = 15
        self._current_status = Status.OFFLINE
        self._enter_running = 6.0
        self._exit_running = 2.0
        self._enter_waiting = 1.0
        self._exit_waiting = 3.0

    def detect(self) -> str:
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

        if not procs:
            self._cpu_samples.clear()
            self._current_status = Status.OFFLINE
            return Status.OFFLINE

        total_cpu = 0.0
        for proc in procs:
            try:
                total_cpu += proc.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self._cpu_samples.append(total_cpu)
        if len(self._cpu_samples) > self._sample_count:
            self._cpu_samples.pop(0)

        if len(self._cpu_samples) < 3:
            return self._current_status

        weights = [i + 1 for i in range(len(self._cpu_samples))]
        avg = sum(s * w for s, w in zip(self._cpu_samples, weights)) / sum(weights)

        if avg > self._enter_running:
            self._current_status = Status.RUNNING
        elif avg < self._enter_waiting:
            self._current_status = Status.WAITING

        return self._current_status


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

        menu.addSeparator()

        # 安装 Hook
        hook_act = QAction("安装 Hook (提升精准度)", self)
        hook_act.triggered.connect(self._install_hooks)
        menu.addAction(hook_act)

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

    def _install_hooks(self):
        """安装 Claude Code hooks"""
        import subprocess
        # 找到源 hook 脚本
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        src_hook = os.path.join(base, "hooks", "claude-status-hook.py")
        setup_script = os.path.join(base, "hooks", "setup-hooks.py")

        if not os.path.exists(src_hook) or not os.path.exists(setup_script):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "hook files not found in: " + base)
            return

        # 复制 hook 脚本到 ~/.claude/hooks/ 持久化
        persistent_dir = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
        os.makedirs(persistent_dir, exist_ok=True)
        import shutil
        persistent_hook = os.path.join(persistent_dir, "claude-status-hook.py")
        shutil.copy2(src_hook, persistent_hook)

        # 直接写入 settings.json
        settings_file = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
        settings = {}
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.loads(f.read())

        cmd = f"python -X utf8 \"{persistent_hook}\""
        def make_hook(matcher=None):
            g = {"hooks": [{"type": "command", "command": cmd}]}
            if matcher:
                g["matcher"] = matcher
            return g

        settings["hooks"] = {
            "PreToolUse":       [make_hook("*")],
            "PostToolUse":      [make_hook("*")],
            "UserPromptSubmit": [make_hook()],
            "Stop":             [make_hook()],
            "StopFailure":      [make_hook()],
            "PermissionRequest": [make_hook()],
            "SessionStart":     [make_hook()],
            "SessionEnd":       [make_hook()],
        }

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "Hook", "Done! Restart Claude Code.")

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
