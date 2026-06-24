from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox, 
                              QComboBox, QLabel, QPushButton, QMessageBox, QVBoxLayout, QGroupBox)
from PySide6.QtCore import Qt
import imaplib
import ssl


class AccountDialog(QDialog):
    def __init__(self, parent=None, account=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Cuenta de Correo")
        self.setMinimumWidth(550)
        self.setMinimumHeight(520)
        self.account = account or {}

        main_layout = QVBoxLayout(self)
        layout = QFormLayout()

        self.email_edit = QLineEdit(self.account.get('email', ''))
        self.email_edit.setPlaceholderText('tu_correo@gmail.com')
        layout.addRow("Email:", self.email_edit)

        self.password_edit = QLineEdit(self.account.get('password', ''))
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText('Contraseña o contraseña de aplicación')
        layout.addRow("Contraseña:", self.password_edit)

        # Proveedor (selector)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gmail", "Outlook", "Otro"])
        current_provider = self.account.get('provider', 'Gmail')
        idx = self.provider_combo.findText(current_provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        else:
            self.provider_combo.setCurrentIndex(0)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        layout.addRow("Proveedor:", self.provider_combo)

        self.server_edit = QLineEdit(self.account.get('imap_server', 'imap.gmail.com'))
        self.server_edit.setPlaceholderText('imap.gmail.com')
        layout.addRow("IMAP Servidor:", self.server_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(self.account.get('imap_port', 993)))
        layout.addRow("IMAP Puerto:", self.port_spin)

        self.ssl_check = QCheckBox("Usar SSL/TLS")
        self.ssl_check.setChecked(bool(self.account.get('use_ssl', 1)))
        layout.addRow("Seguridad:", self.ssl_check)

        # Información importante
        info = QLabel(
            "⚠️ IMPORTANTE:\n"
            "• Gmail y Outlook requieren contraseña de aplicación si usan 2FA\n"
            "• Gmail: https://myaccount.google.com/apppasswords\n"
            "• Outlook: https://account.microsoft.com/security-info"
        )
        info.setWordWrap(True)
        info.setStyleSheet('color: #d84315; font-size: 10px; background-color: #fff3e0; padding: 8px; border-radius: 4px;')
        layout.addRow("", info)

        # Botón de probar conexión
        test_btn = QPushButton("✓ Probar Conexión")
        test_btn.clicked.connect(self.test_connection)
        test_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 6px; font-weight: bold; border-radius: 4px;")
        layout.addRow("", test_btn)

        # Agrupar en un QGroupBox para mejor presentación
        group = QGroupBox("Detalles de la Cuenta")
        group.setLayout(layout)
        main_layout.addWidget(group)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)
        self.setLayout(main_layout)

    def get_data(self):
        return {
            'email': self.email_edit.text().strip(),
            'password': self.password_edit.text(),
            'imap_server': self.server_edit.text().strip(),
            'imap_port': int(self.port_spin.value()),
            'use_ssl': 1 if self.ssl_check.isChecked() else 0,
            'provider': self.provider_combo.currentText().strip(),
        }

    def on_provider_changed(self, text: str):
        """Ajusta valores por defecto según proveedor seleccionado"""
        if text == 'Gmail':
            self.server_edit.setText('imap.gmail.com')
            self.port_spin.setValue(993)
            self.ssl_check.setChecked(True)
        elif text == 'Outlook':
            self.server_edit.setText('outlook.office365.com')
            self.port_spin.setValue(993)
            self.ssl_check.setChecked(True)
        else:
            # Otro -> permitir edición manual
            self.server_edit.setPlaceholderText('imap.ejemplo.com')

    def test_connection(self):
        """Prueba la conexión IMAP con autenticación"""
        context = ssl.create_default_context()
        try:
            email = self.email_edit.text().strip()
            password = self.password_edit.text()
            server = self.server_edit.text().strip()
            port = int(self.port_spin.value())
            use_ssl = bool(self.ssl_check.isChecked())

            if not email or not password or not server:
                QMessageBox.warning(self, "Validación", "Email, contraseña y servidor IMAP son obligatorios")
                return

            try:
                if use_ssl:
                    conn = imaplib.IMAP4_SSL(server, port, ssl_context = context, timeout=10)
                else:
                    conn = imaplib.IMAP4(server, port, timeout=10)

                # Intentar login
                result = conn.login(email, password)    
                print("Resultado del login:", result)  # Debug: mostrar resultado del login
                
                try:
                    conn.logout()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass

                if result[0] == 'OK':
                    QMessageBox.information(self, "✅ Éxito", f"Conexión IMAP exitosa a {server}:{port}\nAutenticación correcta")
                else:
                    QMessageBox.warning(self, "⚠️ Error", "No se pudo autenticar con las credenciales proporcionadas")

            except imaplib.IMAP4.error as e:
                QMessageBox.critical(self, "❌ Error de autenticación", f"Credenciales inválidas o servidor incorrecto:\n{str(e)}")
            except Exception as e:
                QMessageBox.critical(self, "❌ Error de conexión", f"No se pudo conectar a {server}:{port}\n{str(e)}")

        except ValueError:
            QMessageBox.warning(self, "Validación", "El puerto debe ser un número válido")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
