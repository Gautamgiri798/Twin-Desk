"""Theme tokens and Qt stylesheet for DualDesk."""

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}

QWidget {
    color: #f8fafc;
    font-size: 13px;
}

/* Sidebar navigation */
QFrame#Sidebar {
    background-color: #090d16;
    border-right: 1px solid #1e293b;
    min-width: 210px;
    max-width: 210px;
}

QPushButton.NavButton {
    text-align: left;
    padding: 12px 16px;
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton.NavButton:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QPushButton.NavButton:checked {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
}

/* Card panels */
QFrame.Card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
}

QFrame.StatCard {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 14px;
}

/* Notice banner */
QFrame.NoticeBanner {
    background-color: rgba(217, 119, 6, 0.12);
    border: 1px solid #d97706;
    border-radius: 8px;
    padding: 12px 16px;
}

/* Standard Buttons */
QPushButton.PrimaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: 600;
}

QPushButton.PrimaryButton:hover {
    background-color: #1d4ed8;
}

QPushButton.PrimaryButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton.SecondaryButton {
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton.SecondaryButton:hover {
    background-color: #475569;
}

QPushButton.DangerButton {
    background-color: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid #ef4444;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton.DangerButton:hover {
    background-color: #ef4444;
    color: #ffffff;
}

/* Inputs and Comboboxes */
QLineEdit, QComboBox, QSpinBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f8fafc;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    color: #f8fafc;
}

/* Tables and Lists */
QTableWidget, QListWidget {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 8px;
    color: #f8fafc;
    gridline-color: #1e293b;
}

QHeaderView::section {
    background-color: #090d16;
    color: #94a3b8;
    padding: 8px;
    border: 1px solid #1e293b;
    font-weight: 600;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""
