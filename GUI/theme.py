# Copyright (C) 2025
# PyBirch GUI Theme Module
# Central theming and styling for all GUI components
"""
Global theme and styling module for PyBirch GUI.

This module provides:
- Color palette definitions
- Font specifications
- Consistent widget styling
- Stylesheet generation for Qt widgets

Usage:
    from GUI.theme import Theme, apply_theme
    
    # Apply to entire application
    apply_theme(app)
    
    # Or get specific styles
    label.setStyleSheet(Theme.label_style())
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtCore import Qt


@dataclass
class ColorPalette:
    """Color palette for the application theme."""
    
    # Background colors
    background_primary: str = "#ffffff"      # Main background
    background_secondary: str = "#f8f9fa"    # Secondary/alternate background
    background_tertiary: str = "#e9ecef"     # Tertiary background (headers, etc.)
    background_hover: str = "#e3f2fd"        # Hover state background
    background_selected: str = "#0078d4"     # Selected item background
    background_dark: str = "#1e1e1e"         # Dark background (for logs, code, etc.)
    
    # Text colors
    text_primary: str = "#212529"            # Primary text
    text_secondary: str = "#6c757d"          # Secondary/muted text
    text_tertiary: str = "#adb5bd"           # Tertiary/disabled text
    text_inverse: str = "#ffffff"            # Text on dark backgrounds
    text_link: str = "#0078d4"               # Link text
    
    # Accent colors
    accent_primary: str = "#0078d4"          # Primary accent (buttons, highlights)
    accent_secondary: str = "#5c6bc0"        # Secondary accent
    accent_success: str = "#28a745"          # Success state
    accent_warning: str = "#ffc107"          # Warning state
    accent_error: str = "#dc3545"            # Error state
    accent_info: str = "#17a2b8"             # Info state
    
    # Border colors
    border_light: str = "#dee2e6"            # Light borders
    border_medium: str = "#ced4da"           # Medium borders
    border_dark: str = "#adb5bd"             # Dark borders
    border_focus: str = "#0078d4"            # Focus state border
    
    # Status colors (for scan states, etc.)
    status_queued: str = "#e9ecef"
    status_running: str = "#cce5ff"
    status_paused: str = "#fff3cd"
    status_completed: str = "#d4edda"
    status_aborted: str = "#ffe5d0"
    status_failed: str = "#f8d7da"
    
    # Log level colors (for dark background)
    log_info: str = "#4ec9b0"
    log_warning: str = "#dcdcaa"
    log_error: str = "#f14c4c"
    log_debug: str = "#808080"


@dataclass
class FontSpec:
    """Font specifications for the application."""
    
    # Font families
    family_primary: str = "Segoe UI"
    family_monospace: str = "Consolas"
    
    # Font sizes
    size_xs: int = 9
    size_sm: int = 10
    size_base: int = 11
    size_md: int = 12
    size_lg: int = 14
    size_xl: int = 16
    size_xxl: int = 20
    size_title: int = 24


class Theme:
    """
    Central theme class providing styling for all GUI components.
    
    All methods are class methods that can be called without instantiation.
    """
    
    colors = ColorPalette()
    fonts = FontSpec()
    
    # Spacing and sizing constants
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 20
    
    BORDER_RADIUS_SM = 4
    BORDER_RADIUS_MD = 6
    BORDER_RADIUS_LG = 8
    
    @classmethod
    def get_font(cls, size: Optional[int] = None, bold: bool = False, 
                 monospace: bool = False) -> QFont:
        """Get a QFont with theme specifications."""
        family = cls.fonts.family_monospace if monospace else cls.fonts.family_primary
        font = QFont(family, size or cls.fonts.size_base)
        if bold:
            font.setBold(True)
        return font
    
    # ==================== Global Application Stylesheet ====================
    
    @classmethod
    def application_stylesheet(cls) -> str:
        """Get the complete application stylesheet."""
        c = cls.colors
        f = cls.fonts
        
        return f"""
            /* ===== Global Defaults ===== */
            QWidget {{
                font-family: "{f.family_primary}";
                font-size: {f.size_base}px;
                color: {c.text_primary};
                background-color: {c.background_primary};
            }}
            
            QMainWindow {{
                background-color: {c.background_secondary};
            }}
            
            /* ===== Labels ===== */
            QLabel {{
                color: {c.text_primary};
                background-color: transparent;
                padding: 2px;
            }}
            
            QLabel[heading="true"] {{
                font-size: {f.size_lg}px;
                font-weight: bold;
                color: {c.text_primary};
            }}
            
            QLabel[subheading="true"] {{
                font-size: {f.size_md}px;
                font-weight: 600;
                color: {c.text_secondary};
            }}
            
            QLabel[muted="true"] {{
                color: {c.text_secondary};
            }}
            
            /* ===== Buttons ===== */
            QPushButton {{
                background-color: {c.background_tertiary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 6px 16px;
                font-size: {f.size_base}px;
                min-height: 24px;
            }}
            
            QPushButton:hover {{
                background-color: {c.background_hover};
                border-color: {c.accent_primary};
            }}
            
            QPushButton:pressed {{
                background-color: {c.border_light};
            }}
            
            QPushButton:disabled {{
                background-color: {c.background_secondary};
                color: {c.text_tertiary};
                border-color: {c.border_light};
            }}
            
            QPushButton[primary="true"] {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
                border: none;
            }}
            
            QPushButton[primary="true"]:hover {{
                background-color: #106ebe;
            }}
            
            QPushButton[primary="true"]:pressed {{
                background-color: #005a9e;
            }}
            
            QPushButton[danger="true"] {{
                background-color: {c.accent_error};
                color: {c.text_inverse};
                border: none;
            }}
            
            QPushButton[danger="true"]:hover {{
                background-color: #c82333;
            }}
            
            /* ===== Input Fields ===== */
            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {c.background_primary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 6px 10px;
                selection-background-color: {c.accent_primary};
                selection-color: {c.text_inverse};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
                border-color: {c.border_focus};
                outline: none;
            }}
            
            QLineEdit:disabled, QTextEdit:disabled {{
                background-color: {c.background_secondary};
                color: {c.text_tertiary};
            }}
            
            /* ===== ComboBox ===== */
            QComboBox {{
                background-color: {c.background_primary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 6px 10px;
                min-height: 24px;
            }}
            
            QComboBox:hover {{
                border-color: {c.accent_primary};
            }}
            
            QComboBox:focus {{
                border-color: {c.border_focus};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {c.text_secondary};
                margin-right: 8px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_medium};
                selection-background-color: {c.accent_primary};
                selection-color: {c.text_inverse};
            }}
            
            /* ===== SpinBox ===== */
            QSpinBox, QDoubleSpinBox {{
                background-color: {c.background_primary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 4px 8px;
            }}
            
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: {c.border_focus};
            }}
            
            /* ===== CheckBox & RadioButton ===== */
            QCheckBox, QRadioButton {{
                color: {c.text_primary};
                spacing: 8px;
            }}
            
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 14px;
                height: 14px;
            }}
            
            QCheckBox::indicator {{
                border: 2px solid {c.border_medium};
                border-radius: 3px;
                background-color: {c.background_primary};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {c.accent_primary};
                border-color: {c.accent_primary};
            }}
            
            QCheckBox::indicator:hover {{
                border-color: {c.accent_primary};
            }}
            
            /* Style for checkboxes inside tree/table/list items */
            QTreeWidget::indicator, QTableWidget::indicator, QListWidget::indicator {{
                width: 14px;
                height: 14px;
                border: 2px solid {c.border_medium};
                border-radius: 3px;
                background-color: {c.background_primary};
            }}
            
            QTreeWidget::indicator:checked, QTableWidget::indicator:checked, QListWidget::indicator:checked {{
                background-color: {c.accent_primary};
                border-color: {c.accent_primary};
            }}
            
            QTreeWidget::indicator:selected, QTableWidget::indicator:selected, QListWidget::indicator:selected {{
                border: 2px solid {c.border_medium};
                background-color: {c.background_primary};
            }}
            
            QTreeWidget::indicator:checked:selected, QTableWidget::indicator:checked:selected, QListWidget::indicator:checked:selected {{
                background-color: {c.accent_primary};
                border-color: {c.text_inverse};
            }}
            
            QRadioButton::indicator {{
                border: 2px solid {c.border_medium};
                border-radius: 9px;
                background-color: {c.background_primary};
            }}
            
            QRadioButton::indicator:checked {{
                background-color: {c.accent_primary};
                border-color: {c.accent_primary};
            }}
            
            /* ===== GroupBox ===== */
            QGroupBox {{
                font-weight: bold;
                font-size: {f.size_md}px;
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_MD}px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: {c.background_primary};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: {c.background_primary};
            }}
            
            /* ===== Frame ===== */
            QFrame[frameShape="4"] {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_MD}px;
            }}
            
            /* ===== Tab Widget ===== */
            QTabWidget::pane {{
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                background-color: {c.background_primary};
            }}
            
            QTabBar::tab {{
                background-color: {c.background_tertiary};
                color: {c.text_secondary};
                border: 1px solid {c.border_light};
                border-bottom: none;
                border-top-left-radius: {cls.BORDER_RADIUS_SM}px;
                border-top-right-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 8px 16px;
                margin-right: 2px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {c.background_primary};
                color: {c.text_primary};
                border-bottom: 2px solid {c.accent_primary};
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {c.background_hover};
            }}
            
            /* ===== List Widget ===== */
            QListWidget, QListView {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                outline: none;
            }}
            
            QListWidget::item, QListView::item {{
                padding: 8px;
                border-bottom: 1px solid {c.background_tertiary};
            }}
            
            QListWidget::item:selected, QListView::item:selected {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
            }}
            
            QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
                background-color: {c.background_hover};
            }}
            
            /* ===== Tree Widget ===== */
            QTreeWidget, QTreeView {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                outline: none;
                alternate-background-color: {c.background_secondary};
            }}
            
            QTreeWidget::item, QTreeView::item {{
                padding: 4px;
                border: none;
            }}
            
            QTreeWidget::item:selected, QTreeView::item:selected {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
            }}
            
            QTreeWidget::item:hover:!selected, QTreeView::item:hover:!selected {{
                background-color: {c.background_hover};
            }}
            
            QTreeWidget::branch, QTreeView::branch {{
                background-color: transparent;
            }}
            
            /* ===== Table Widget ===== */
            QTableWidget, QTableView {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                gridline-color: {c.border_light};
                outline: none;
            }}
            
            QTableWidget::item, QTableView::item {{
                padding: 6px;
            }}
            
            QTableWidget::item:selected, QTableView::item:selected {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
            }}
            
            QHeaderView::section {{
                background-color: {c.background_tertiary};
                color: {c.text_primary};
                font-weight: bold;
                padding: 8px;
                border: none;
                border-right: 1px solid {c.border_light};
                border-bottom: 1px solid {c.border_light};
            }}
            
            /* ===== ScrollBar ===== */
            QScrollBar:vertical {{
                background-color: {c.background_secondary};
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }}
            
            QScrollBar::handle:vertical {{
                background-color: {c.border_medium};
                border-radius: 6px;
                min-height: 30px;
                margin: 2px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background-color: {c.border_dark};
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QScrollBar:horizontal {{
                background-color: {c.background_secondary};
                height: 12px;
                border-radius: 6px;
                margin: 0;
            }}
            
            QScrollBar::handle:horizontal {{
                background-color: {c.border_medium};
                border-radius: 6px;
                min-width: 30px;
                margin: 2px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background-color: {c.border_dark};
            }}
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            
            /* ===== Splitter ===== */
            QSplitter::handle {{
                background-color: {c.border_light};
            }}
            
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            
            QSplitter::handle:hover {{
                background-color: {c.accent_primary};
            }}
            
            /* ===== Menu Bar ===== */
            QMenuBar {{
                background-color: {c.background_secondary};
                color: {c.text_primary};
                border-bottom: 1px solid {c.border_light};
                padding: 4px;
            }}
            
            QMenuBar::item {{
                padding: 6px 12px;
                border-radius: {cls.BORDER_RADIUS_SM}px;
            }}
            
            QMenuBar::item:selected {{
                background-color: {c.background_hover};
            }}
            
            QMenuBar::item:pressed {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
            }}
            
            /* ===== Menu ===== */
            QMenu {{
                background-color: {c.background_primary};
                border: 1px solid {c.border_light};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 4px;
            }}
            
            QMenu::item {{
                padding: 8px 32px 8px 24px;
                border-radius: {cls.BORDER_RADIUS_SM}px;
            }}
            
            QMenu::item:selected {{
                background-color: {c.accent_primary};
                color: {c.text_inverse};
            }}
            
            QMenu::separator {{
                height: 1px;
                background-color: {c.border_light};
                margin: 4px 8px;
            }}
            
            /* ===== Tool Bar ===== */
            QToolBar {{
                background-color: {c.background_secondary};
                border: none;
                border-bottom: 1px solid {c.border_light};
                padding: 4px;
                spacing: 4px;
            }}
            
            QToolBar::separator {{
                width: 1px;
                background-color: {c.border_light};
                margin: 4px 8px;
            }}
            
            /* ===== Status Bar ===== */
            QStatusBar {{
                background-color: {c.background_secondary};
                color: {c.text_secondary};
                border-top: 1px solid {c.border_light};
            }}
            
            /* ===== Progress Bar ===== */
            QProgressBar {{
                background-color: {c.background_tertiary};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                text-align: center;
                color: {c.text_primary};
                height: 20px;
            }}
            
            QProgressBar::chunk {{
                background-color: {c.accent_primary};
                border-radius: {cls.BORDER_RADIUS_SM}px;
            }}
            
            /* ===== Scroll Area ===== */
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            /* ===== ToolTip ===== */
            QToolTip {{
                background-color: {c.background_dark};
                color: {c.text_inverse};
                border: 1px solid {c.border_dark};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 6px 10px;
                font-size: {f.size_sm}px;
            }}
        """
    
    # ==================== Component-Specific Styles ====================
    
    @classmethod
    def title_label_style(cls) -> str:
        """Style for main title labels."""
        return f"""
            QLabel {{
                font-size: {cls.fonts.size_lg}px;
                font-weight: bold;
                color: {cls.colors.text_primary};
                background-color: transparent;
                padding: 4px 0;
            }}
        """
    
    @classmethod
    def section_title_style(cls) -> str:
        """Style for section/heading labels."""
        return f"""
            QLabel {{
                font-size: {cls.fonts.size_md}px;
                font-weight: 600;
                color: {cls.colors.text_primary};
                background-color: transparent;
                margin-bottom: 4px;
            }}
        """
    
    @classmethod
    def muted_label_style(cls) -> str:
        """Style for secondary/muted labels."""
        return f"""
            QLabel {{
                font-size: {cls.fonts.size_base}px;
                color: {cls.colors.text_secondary};
                background-color: transparent;
            }}
        """
    
    @classmethod
    def card_frame_style(cls) -> str:
        """Style for card-like frames."""
        return f"""
            QFrame {{
                background-color: {cls.colors.background_primary};
                border: 1px solid {cls.colors.border_light};
                border-radius: {cls.BORDER_RADIUS_MD}px;
                padding: 12px;
            }}
        """
    
    @classmethod
    def primary_button_style(cls) -> str:
        """Style for primary action buttons."""
        return f"""
            QPushButton {{
                background-color: {cls.colors.accent_primary};
                color: {cls.colors.text_inverse};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 8px 20px;
                font-weight: bold;
                qproperty-iconSize: 16px 16px;
            }}
            QPushButton:hover {{
                background-color: #106ebe;
            }}
            QPushButton:pressed {{
                background-color: #005a9e;
            }}
            QPushButton:disabled {{
                background-color: {cls.colors.border_medium};
                color: {cls.colors.text_tertiary};
            }}
        """
    
    @classmethod
    def danger_button_style(cls) -> str:
        """Style for danger/destructive buttons."""
        return f"""
            QPushButton {{
                background-color: {cls.colors.accent_error};
                color: {cls.colors.text_inverse};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 8px 20px;
                font-weight: bold;
                qproperty-iconSize: 16px 16px;
            }}
            QPushButton:hover {{
                background-color: #c82333;
            }}
            QPushButton:pressed {{
                background-color: #bd2130;
            }}
            QPushButton:disabled {{
                background-color: {cls.colors.border_medium};
                color: {cls.colors.text_tertiary};
            }}
        """
    
    @classmethod
    def success_button_style(cls) -> str:
        """Style for success buttons."""
        return f"""
            QPushButton {{
                background-color: {cls.colors.accent_success};
                color: {cls.colors.text_inverse};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 8px 20px;
                font-weight: bold;
                qproperty-iconSize: 16px 16px;
            }}
            QPushButton:hover {{
                background-color: #218838;
            }}
            QPushButton:pressed {{
                background-color: #1e7e34;
            }}
            QPushButton:disabled {{
                background-color: {cls.colors.border_medium};
                color: {cls.colors.text_tertiary};
            }}
        """
    
    @classmethod
    def warning_button_style(cls) -> str:
        """Style for warning/caution buttons."""
        return f"""
            QPushButton {{
                background-color: {cls.colors.accent_warning};
                color: {cls.colors.text_primary};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 8px 20px;
                font-weight: bold;
                qproperty-iconSize: 16px 16px;
            }}
            QPushButton:hover {{
                background-color: #e0a800;
            }}
            QPushButton:pressed {{
                background-color: #c69500;
            }}
            QPushButton:disabled {{
                background-color: {cls.colors.border_medium};
                color: {cls.colors.text_tertiary};
            }}
        """
    
    @classmethod
    def icon_button_style(cls) -> str:
        """Style for icon-only buttons (like toolbar buttons)."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {cls.colors.text_primary};
                border: none;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {cls.colors.background_hover};
            }}
            QPushButton:pressed {{
                background-color: {cls.colors.border_light};
            }}
        """
    
    @classmethod
    def log_text_style(cls) -> str:
        """Style for log/code text displays."""
        return f"""
            QTextEdit {{
                background-color: {cls.colors.background_dark};
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: {cls.BORDER_RADIUS_SM}px;
                font-family: "{cls.fonts.family_monospace}";
                font-size: {cls.fonts.size_sm}px;
            }}
        """
    
    @classmethod
    def status_badge_style(cls, status: str) -> str:
        """Get style for a status badge based on status type."""
        status_colors = {
            "queued": (cls.colors.text_secondary, cls.colors.status_queued),
            "running": (cls.colors.text_inverse, cls.colors.accent_primary),
            "paused": (cls.colors.text_primary, cls.colors.accent_warning),
            "completed": (cls.colors.text_inverse, cls.colors.accent_success),
            "aborted": (cls.colors.text_inverse, "#fd7e14"),
            "failed": (cls.colors.text_inverse, cls.colors.accent_error),
        }
        
        fg, bg = status_colors.get(status.lower(), (cls.colors.text_primary, cls.colors.border_light))
        
        return f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border-radius: {cls.BORDER_RADIUS_SM}px;
                padding: 4px 12px;
                font-weight: bold;
            }}
        """


def apply_theme(app: QApplication) -> None:
    """Apply the global theme to the application.
    
    Args:
        app: The QApplication instance to apply the theme to.
    """
    app.setStyleSheet(Theme.application_stylesheet())
    
    # Set default font
    app.setFont(Theme.get_font())


def get_status_color(status: str) -> str:
    """Get the background color for a status.
    
    Args:
        status: The status string (queued, running, paused, completed, aborted, failed)
        
    Returns:
        Hex color string for the status.
    """
    status_map = {
        "queued": Theme.colors.status_queued,
        "running": Theme.colors.status_running,
        "paused": Theme.colors.status_paused,
        "completed": Theme.colors.status_completed,
        "aborted": Theme.colors.status_aborted,
        "failed": Theme.colors.status_failed,
    }
    return status_map.get(status.lower(), Theme.colors.background_tertiary)
