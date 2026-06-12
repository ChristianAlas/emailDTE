from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QLineEdit, QTextEdit, QFileDialog,
                              QGroupBox, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt
import json

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Configuración")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Credenciales Gmail
        creds_group = QGroupBox("Credenciales Gmail")
        creds_layout = QFormLayout()
        
        self.email_input = QLineEdit(self.config.get('email', ''))
        self.email_input.setPlaceholderText("tu_correo@gmail.com")
        creds_layout.addRow("Correo Gmail:", self.email_input)
        
        self.password_input = QLineEdit(self.config.get('password', ''))
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Contraseña de aplicación de 16 caracteres")
        creds_layout.addRow("Contraseña App:", self.password_input)
        
        # Información sobre contraseña de aplicación
        info_label = QLabel(
            "ℹ️ <b>Importante:</b> Debes usar una contraseña de aplicación de Google.\n"
            "1. Ve a myaccount.google.com/security\n"
            "2. Activa verificación en 2 pasos\n"
            "3. Ve a 'Contraseñas de aplicación'\n"
            "4. Genera una contraseña para 'Correo' y 'Otra aplicación'"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        creds_layout.addRow("", info_label)
        
        creds_group.setLayout(creds_layout)
        layout.addWidget(creds_group)
        
        # Paths group
        paths_group = QGroupBox("Rutas")
        paths_layout = QFormLayout()
        
        self.download_path = QLineEdit(self.config.get('base_download_path', './downloads'))
        browse_btn = QPushButton("Examinar...")
        browse_btn.clicked.connect(self.browse_download_path)
        
        path_widget = QHBoxLayout()
        path_widget.addWidget(self.download_path)
        path_widget.addWidget(browse_btn)
        paths_layout.addRow("Directorio descargas:", path_widget)
        
        paths_group.setLayout(paths_layout)
        layout.addWidget(paths_group)
        
        # Keywords group
        keywords_group = QGroupBox("Palabras Clave")
        keywords_layout = QVBoxLayout()
        
        keywords_layout.addWidget(QLabel("Una palabra o frase por línea:"))
        self.keywords_edit = QTextEdit()
        keywords = self.config.get('keywords', [])
        self.keywords_edit.setText('\n'.join(keywords))
        self.keywords_edit.setMaximumHeight(100)
        keywords_layout.addWidget(self.keywords_edit)
        
        keywords_group.setLayout(keywords_layout)
        layout.addWidget(keywords_group)
        
        # Opciones adicionales
        options_group = QGroupBox("Opciones")
        options_layout = QFormLayout()
        
        self.max_emails = QLineEdit(str(self.config.get('max_emails_per_run', 100)))
        options_layout.addRow("Máx. correos por ejecución:", self.max_emails)
        
        self.days_to_check = QLineEdit(str(self.config.get('days_to_check', 30)))
        options_layout.addRow("Días a revisar:", self.days_to_check)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Gmail label
        label_group = QGroupBox("Etiqueta de Gmail")
        label_layout = QFormLayout()

        self.label_edit = QLineEdit(self.config.get('label_name', 'DTE_Processed'))
        self.label_edit.setPlaceholderText("Nombre de la etiqueta en Gmail")
        label_layout.addRow("Etiqueta:", self.label_edit)

        # Note: folder option removed — use Gmail labels only

        info_label = QLabel(
            "🏷️ Esta etiqueta se aplicará a los correos procesados exitosamente.\n"
            "Los correos con esta etiqueta no se volverán a procesar."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        label_layout.addRow("", info_label)

        label_group.setLayout(label_layout)
        layout.addWidget(label_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        test_btn = QPushButton("Probar Conexión")
        test_btn.clicked.connect(self.test_connection)
        test_btn.setStyleSheet("background-color: #2196F3; color: white;")
        buttons_layout.addWidget(test_btn)
        
        buttons_layout.addStretch()
        
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        buttons_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def browse_download_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar directorio de descargas")
        if folder:
            self.download_path.setText(folder)
    
    def test_connection(self):
        """Prueba la conexión IMAP"""
        try:
            from infrastructure.imap_service import ImapService
            
            service = ImapService(
                email_address=self.email_input.text(),
                password=self.password_input.text()
            )
            
            if service.connect():
                QMessageBox.information(self, "Éxito", "✅ Conexión exitosa a Gmail")
                service.disconnect()
            else:
                QMessageBox.warning(
                    self, 
                    "Error", 
                    "❌ No se pudo conectar.\n\n"
                    "Verifica:\n"
                    "1. Que el correo sea correcto\n"
                    "2. Que uses contraseña de aplicación\n"
                    "3. Que tengas IMAP habilitado en Gmail"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error de conexión:\n{str(e)}")
    
    def save_settings(self):
        # Validar campos requeridos
        if not self.email_input.text() or not self.password_input.text():
            QMessageBox.warning(self, "Campos requeridos", "Email y contraseña son obligatorios")
            return
        
        # Guardar configuración
        self.config.set('email', self.email_input.text())
        self.config.set('password', self.password_input.text())
        self.config.set('base_download_path', self.download_path.text())
        self.config.set('max_emails_per_run', int(self.max_emails.text()))
        self.config.set('days_to_check', int(self.days_to_check.text()))
        self.config.set('label_name', self.label_edit.text())
        
        # Guardar keywords
        keywords = self.keywords_edit.toPlainText().strip().split('\n')
        keywords = [k.strip() for k in keywords if k.strip()]
        self.config.set('keywords', keywords)
        
        self.accept()