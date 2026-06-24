from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, 
                              QMessageBox, QLineEdit, QLabel, QGroupBox)
from PySide6.QtCore import Qt
from ui.account_dialog import AccountDialog
from infrastructure.account_db import AccountDB


class AccountsManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Administrar Cuentas de Correo")
        self.setMinimumWidth(850)
        self.setMinimumHeight(600)
        self.db = AccountDB()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # Título
        title = QLabel("Cuentas Registradas")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1976d2;")
        layout.addWidget(title)

        # Filtros
        filter_group = QGroupBox("Filtros")
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        filter_layout.addWidget(QLabel("Email:"))
        self.filter_email = QLineEdit()
        self.filter_email.setPlaceholderText("Buscar por email...")
        self.filter_email.setMaximumWidth(250)
        filter_layout.addWidget(self.filter_email)
        
        filter_layout.addWidget(QLabel("Proveedor:"))
        self.filter_provider = QLineEdit()
        self.filter_provider.setPlaceholderText("Gmail, Outlook, Otro...")
        self.filter_provider.setMaximumWidth(250)
        filter_layout.addWidget(self.filter_provider)
        
        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Email", "Proveedor", "Servidor IMAP", "Puerto", "SSL"])
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setMinimumHeight(350)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #fafafa;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #1976d2;
                color: white;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """)
        # Ajustar ancho de columnas
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        # Botones de control
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.add_btn = QPushButton("➕ Agregar Cuenta")
        self.add_btn.setMinimumWidth(150)
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
        self.edit_btn = QPushButton("✏️ Editar")
        self.edit_btn.setMinimumWidth(120)
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0056b3;
            }
        """)
        
        self.delete_btn = QPushButton("🗑️ Eliminar")
        self.delete_btn.setMinimumWidth(120)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #ba0000;
            }
        """)

        self.add_btn.clicked.connect(self.add_account)
        self.edit_btn.clicked.connect(self.edit_account)
        self.delete_btn.clicked.connect(self.delete_account)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Conectar filtros
        self.filter_email.textChanged.connect(self.refresh)
        self.filter_provider.textChanged.connect(self.refresh)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        self.accounts = self.db.list_accounts()
        email_filter = self.filter_email.text().strip().lower()
        provider_filter = self.filter_provider.text().strip().lower()
        
        displayed_count = 0
        for a in self.accounts:
            if email_filter and email_filter not in a['email'].lower():
                continue
            prov = (a.get('provider') or '')
            if provider_filter and provider_filter not in prov.lower():
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(a['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(a['email']))
            self.table.setItem(row, 2, QTableWidgetItem(prov))
            self.table.setItem(row, 3, QTableWidgetItem(a.get('imap_server') or ''))
            self.table.setItem(row, 4, QTableWidgetItem(str(a.get('imap_port') or '')))
            self.table.setItem(row, 5, QTableWidgetItem('✓ Sí' if a.get('use_ssl') else '✗ No'))
            displayed_count += 1
        
        # Resizar columnas
        self.table.resizeColumnsToContents()

    def add_account(self):
        dlg = AccountDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self.db.add_account(**data)
                self.refresh()
                QMessageBox.information(self, "✅ Éxito", f"Cuenta {data['email']} agregada correctamente")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", f"No se pudo agregar la cuenta:\n{str(e)}")

    def edit_account(self):
        sel = self.table.selectedItems()
        if not sel:
            QMessageBox.warning(self, "⚠️ Aviso", "Selecciona una cuenta para editar")
            return
        row = sel[0].row()
        account_id = int(self.table.item(row, 0).text())
        account = self.db.get_account(account_id)
        dlg = AccountDialog(self, account)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self.db.update_account(account['id'], **data)
                self.refresh()
                QMessageBox.information(self, "✅ Éxito", f"Cuenta {data['email']} actualizada correctamente")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", f"No se pudo actualizar la cuenta:\n{str(e)}")

    def delete_account(self):
        sel = self.table.selectedItems()
        if not sel:
            QMessageBox.warning(self, "⚠️ Aviso", "Selecciona una cuenta para eliminar")
            return
        row = sel[0].row()
        account_id = int(self.table.item(row, 0).text())
        account = self.db.get_account(account_id)
        reply = QMessageBox.question(
            self, 
            "⚠️ Confirmar eliminación", 
            f"¿Estás seguro de que deseas eliminar la cuenta {account['email']}?\n\nEsta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self.db.delete_account(account['id'])
                self.refresh()
                QMessageBox.information(self, "✅ Éxito", f"Cuenta {account['email']} eliminada correctamente")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error", f"No se pudo eliminar la cuenta:\n{str(e)}")
