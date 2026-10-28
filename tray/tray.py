#!/usr/bin/env python3

import sys
import subprocess
from PySide6.QtCore import Qt, QProcess, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class VPNTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            raise RuntimeError("No system tray is available")

        self.connected = False
        self.status_known = False

        # Process used to query the VPN status without blocking the UI
        self.status_process = QProcess()
        self.status_process.finished.connect(self.on_status_finished)
        self.status_process.errorOccurred.connect(self.on_status_error)

        # Refresh the status every 5 seconds
        self.status_timer = QTimer()
        self.status_timer.setInterval(5000)
        self.status_timer.timeout.connect(self.refresh_status)

        # System tray icon and menu
        self.tray = QSystemTrayIcon()
        self.menu = QMenu()

        self.status_action = QAction("Status unknown")
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        self.connect_action = QAction("Connect")
        self.connect_action.triggered.connect(self.connect)
        self.menu.addAction(self.connect_action)

        self.disconnect_action = QAction("Disconnect")
        self.disconnect_action.triggered.connect(self.disconnect)
        self.menu.addAction(self.disconnect_action)

        self.menu.addSeparator()

        self.quit_action = QAction("Quit")
        self.quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)
        self.update_status()
        self.tray.show()

        self.status_timer.start()
        self.refresh_status()

    def refresh_status(self):
        if self.status_process.state() != QProcess.ProcessState.NotRunning:
            return

        self.status_process.start(
            "sudo",
            [
                "-n",
                "/usr/local/libexec/fortigate-saml-vpn/venv/bin/python",
                "/usr/local/libexec/fortigate-saml-vpn/vpn_status.py",
            ],
        )

    def on_status_finished(self, exit_code, exit_status):
        if exit_status != QProcess.ExitStatus.NormalExit:
            self.status_known = False
        elif exit_code == 0:
            self.connected = True
            self.status_known = True
        elif exit_code == 1:
            self.connected = False
            self.status_known = True
        else:
            self.status_known = False
            error = bytes(self.status_process.readAllStandardError()).decode(
                errors="replace"
            ).strip()
            if error:
                print(f"VPN status error: {error}", file=sys.stderr)

        self.update_status()

    def on_status_error(self, error):
        self.status_known = False
        self.update_status()

    def create_icon(self, connected: bool) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor("#27ae60" if connected else "#909090")

        # Shield outline
        shield = QPainterPath()
        shield.moveTo(32, 6)
        shield.cubicTo(24, 11, 16, 13, 11, 14)
        shield.lineTo(11, 30)
        shield.cubicTo(11, 44, 20, 53, 32, 59)
        shield.cubicTo(44, 53, 53, 44, 53, 30)
        shield.lineTo(53, 14)
        shield.cubicTo(48, 13, 40, 11, 32, 6)
        shield.closeSubpath()

        painter.setPen(QPen(color, 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shield)

        if connected:
            # Check mark
            painter.setPen(
                QPen(
                    color,
                    5,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawLine(22, 32, 29, 39)
            painter.drawLine(29, 39, 43, 24)
        else:
            # Horizontal line for disconnected state
            painter.setPen(
                QPen(
                    color,
                    5,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(23, 33, 41, 33)

        painter.end()
        return QIcon(pixmap)

    def update_status(self):
        if not self.status_known:
            self.tray.setIcon(self.create_icon(False))
            self.tray.setToolTip("FortiGate VPN — Status unknown")
            self.status_action.setText("Status unknown")

        elif self.connected:
            self.tray.setIcon(self.create_icon(True))
            self.tray.setToolTip("FortiGate VPN — Connected")
            self.status_action.setText("Connected")

        else:
            self.tray.setIcon(self.create_icon(False))
            self.tray.setToolTip("FortiGate VPN — Disconnected")
            self.status_action.setText("Disconnected")

        self.connect_action.setEnabled(self.status_known and not self.connected)
        self.disconnect_action.setEnabled(self.status_known and self.connected)

    def connect(self):
        subprocess.Popen([
            "konsole",
            "--hold",
            "-e",
            "fortigate-saml-vpn",
            "connect",
        ])


    def disconnect(self):
        subprocess.Popen([
            "konsole",
            "--hold",
            "-e",
            "fortigate-saml-vpn",
            "disconnect",
        ])

    def run(self):
        return self.app.exec()


if __name__ == "__main__":
    sys.exit(VPNTray().run())
