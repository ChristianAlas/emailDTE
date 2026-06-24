from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QLineEdit, QTextEdit, QFileDialog,
                              QFormLayout, QMessageBox, QComboBox, QCheckBox, QTabWidget)

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

        tabs = QTabWidget()

        # Nota: la gestión de cuentas (email/contraseña/servidor) se realiza en "Administrar cuentas"

        # Organización tab (cómo se crean las carpetas)
        org_tab = QWidget()
        org_layout = QVBoxLayout()


        self.download_path = QLineEdit(self.config.get('base_download_path', './downloads'))
        browse_btn = QPushButton("Examinar...")
        browse_btn.clicked.connect(self.browse_download_path)
        org_layout.addWidget(self.download_path)
        org_layout.addWidget(browse_btn)


        self.create_year_cb = QCheckBox("Crear carpeta por año (YYYY)")
        self.create_year_cb.setChecked(bool(self.config.get('storage_create_year', True)))
        org_layout.addWidget(self.create_year_cb)

        self.create_month_cb = QCheckBox("Crear carpeta por mes (MM Nombre)")
        self.create_month_cb.setChecked(bool(self.config.get('storage_create_month', True)))
        org_layout.addWidget(self.create_month_cb)

        self.create_sender_cb = QCheckBox("Crear carpeta por remitente (email)")
        self.create_sender_cb.setChecked(bool(self.config.get('storage_create_sender', True)))
        org_layout.addWidget(self.create_sender_cb)

        self.preview_label = QLabel("Ejemplo de ruta: ")
        org_layout.addWidget(self.preview_label)

        # Conectar para actualizar vista previa
        self.create_year_cb.toggled.connect(self.update_preview)
        self.create_month_cb.toggled.connect(self.update_preview)
        self.create_sender_cb.toggled.connect(self.update_preview)
        self.download_path.textChanged.connect(self.update_preview)

        # Inicializar preview
        self.update_preview()

        org_tab.setLayout(org_layout)
        tabs.addTab(org_tab, "Descargas")

        # --- Opciones (máx correos, días, etiqueta, keywords) ---
        options_tab = QWidget()
        options_layout = QVBoxLayout()

        form = QFormLayout()
        self.max_emails = QLineEdit(str(self.config.get('max_emails_per_run', 100)))
        form.addRow("Máx. correos por ejecución:", self.max_emails)

        self.days_to_check = QLineEdit(str(self.config.get('days_to_check', 30)))
        form.addRow("Días a revisar:", self.days_to_check)

        self.label_edit = QLineEdit(self.config.get('label_name', 'DTE_Processed'))
        self.label_edit.setPlaceholderText("Nombre de la etiqueta en Gmail")
        form.addRow("Etiqueta:", self.label_edit)

        options_layout.addLayout(form)

        options_layout.addWidget(QLabel("Palabras clave (una por línea):"))
        self.keywords_edit = QTextEdit()
        keywords = self.config.get('keywords', [])
        self.keywords_edit.setText('\n'.join(keywords))
        self.keywords_edit.setMaximumHeight(120)
        options_layout.addWidget(self.keywords_edit)

        options_tab.setLayout(options_layout)
        tabs.addTab(options_tab, "Opciones")

        layout.addWidget(tabs)

        # Bottom buttons
        buttons_layout = QHBoxLayout()
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
    
    def save_settings(self):
        # Validar campos requeridos
        # No se guardan cuentas en este diálogo; use 'Administrar cuentas' para ello.
        
        # Guardar configuración

        self.config.set('base_download_path', self.download_path.text())
        # Organización de archivos
        self.config.set('storage_create_year', bool(self.create_year_cb.isChecked()))
        self.config.set('storage_create_month', bool(self.create_month_cb.isChecked()))
        self.config.set('storage_create_sender', bool(self.create_sender_cb.isChecked()))
        try:
            self.config.set('max_emails_per_run', int(self.max_emails.text()))
        except Exception:
            self.config.set('max_emails_per_run', self.config.get('max_emails_per_run', 100))
        try:
            self.config.set('days_to_check', int(self.days_to_check.text()))
        except Exception:
            self.config.set('days_to_check', self.config.get('days_to_check', 30))
        self.config.set('label_name', self.label_edit.text())
        
        # Guardar keywords
        keywords = self.keywords_edit.toPlainText().strip().split('\n')
        keywords = [k.strip() for k in keywords if k.strip()]
        self.config.set('keywords', keywords)
        
        self.accept()

    def update_preview(self):
        base = self.download_path.text() or './downloads'
        # ejemplo
        example_year = '2026'
        example_month = '06 Junio'
        example_sender = 'proveedor_at_example.com'

        parts = [base]
        if getattr(self, 'create_year_cb', None) and self.create_year_cb.isChecked():
            parts.append(example_year)
        if getattr(self, 'create_month_cb', None) and self.create_month_cb.isChecked():
            parts.append(example_month)
        if getattr(self, 'create_sender_cb', None) and self.create_sender_cb.isChecked():
            parts.append(example_sender)

        example_path = "/".join(parts)
        if hasattr(self, 'preview_label'):
            self.preview_label.setText(f"Ejemplo de ruta: {example_path}")