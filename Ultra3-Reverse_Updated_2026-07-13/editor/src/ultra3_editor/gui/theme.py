from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

TOKENS = {
    "background_primary": "#111315",
    "background_sidebar": "#181A1D",
    "background_panel": "#202327",
    "background_elevated": "#25282D",
    "border_default": "#30343A",
    "divider": "#2A2D32",
    "text_primary": "#F2F3F5",
    "text_secondary": "#A6ABB3",
    "text_disabled": "#686D75",
    "accent": "#4C9AFF",
    "accent_hover": "#66A8FF",
    "accent_pressed": "#357FD6",
    "state_verified": "#3FB950",
    "state_experimental": "#D29922",
    "state_unknown": "#8B949E",
    "state_unsupported": "#686D75",
    "state_error": "#F85149",
}


def apply_theme(app: QApplication) -> None:
    _load_windows_ui_font()
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(TOKENS["background_primary"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TOKENS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(TOKENS["background_panel"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(TOKENS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(TOKENS["background_elevated"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TOKENS["text_primary"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(TOKENS["accent"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TOKENS["text_disabled"]))
    app.setPalette(palette)
    app.setStyleSheet(_stylesheet())


def _stylesheet() -> str:
    t = TOKENS
    return f"""
    * {{ font-family: 'Microsoft YaHei UI', 'Segoe UI'; font-size: 13px; color: {t['text_primary']}; }}
    QMainWindow, QWidget#root {{ background: {t['background_primary']}; }}
    QFrame#titleBar, QFrame#sidebar, QFrame#statusBar {{
        background: {t['background_sidebar']}; border: none;
    }}
    QFrame#card, QFrame#placeholderCard {{
        background: {t['background_panel']}; border: 1px solid {t['border_default']};
        border-radius: 10px;
    }}
    QLabel#appTitle {{ font-size: 21px; font-weight: 650; }}
    QLabel#pageTitle {{ font-size: 19px; font-weight: 650; }}
    QLabel#sectionTitle {{ font-size: 14px; font-weight: 650; }}
    QLabel#muted, QLabel#fieldLabel {{ color: {t['text_secondary']}; }}
    QLabel#mono, QLineEdit#mono, QPlainTextEdit#mono {{
        font-family: 'Cascadia Mono', 'Consolas'; font-size: 12px;
    }}
    QPushButton {{
        background: {t['background_elevated']}; border: 1px solid {t['border_default']};
        border-radius: 7px; padding: 7px 12px; min-height: 20px;
    }}
    QPushButton:hover {{ border-color: {t['accent_hover']}; }}
    QPushButton:pressed {{ background: {t['accent_pressed']}; }}
    QPushButton:focus {{ border: 2px solid {t['accent']}; }}
    QPushButton:disabled {{ color: {t['text_disabled']}; border-color: {t['divider']}; }}
    QPushButton#primaryButton {{ background: {t['accent']}; color: white; border: none; font-weight: 650; }}
    QPushButton#primaryButton:disabled {{
        background: {t['background_elevated']}; color: {t['text_disabled']};
        border: 1px solid {t['divider']};
    }}
    QPushButton#navButton {{ text-align: left; border: none; background: transparent; padding: 9px 14px; }}
    QPushButton#navButton:checked {{
        background: {t['background_elevated']}; border-left: 3px solid {t['accent']};
        padding-left: 11px;
    }}
    QLineEdit, QPlainTextEdit {{
        background: {t['background_primary']}; border: 1px solid {t['border_default']};
        border-radius: 6px; padding: 6px;
    }}
    QLineEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {t['accent']}; }}
    QRadioButton {{ spacing: 8px; }}
    QRadioButton:disabled {{ color: {t['text_disabled']}; }}
    QCheckBox:disabled {{ color: {t['text_disabled']}; }}
    QComboBox:disabled {{
        color: {t['text_disabled']}; background: {t['background_primary']};
        border: 1px solid {t['divider']}; padding: 6px;
    }}
    QTabBar::tab {{
        background: {t['background_panel']}; color: {t['text_secondary']};
        border: 1px solid {t['border_default']}; padding: 8px 16px;
    }}
    QTabBar::tab:selected {{
        color: {t['text_primary']}; border-bottom: 2px solid {t['accent']};
        background: {t['background_elevated']};
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {t['border_default']}; border-radius: 5px; min-height: 28px; }}
    QLabel#badge {{ border-radius: 9px; padding: 2px 8px; font-size: 11px; font-weight: 700; }}
    QLabel#badge[state='verified'] {{ color: {t['state_verified']}; border: 1px solid {t['state_verified']}; }}
    QLabel#badge[state='experimental'] {{ color: {t['state_experimental']}; border: 1px solid {t['state_experimental']}; }}
    QLabel#badge[state='unknown'] {{ color: {t['state_unknown']}; border: 1px solid {t['state_unknown']}; }}
    QLabel#badge[state='unsupported'] {{ color: {t['state_unsupported']}; border: 1px solid {t['state_unsupported']}; }}
    QLabel#badge[state='error'] {{ color: {t['state_error']}; border: 1px solid {t['state_error']}; }}
    """


def _load_windows_ui_font() -> None:
    if "Microsoft YaHei UI" in QFontDatabase.families():
        return
    font = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts" / "msyh.ttc"
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
