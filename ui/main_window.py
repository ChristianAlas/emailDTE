from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QTextEdit, QLabel, QDateTimeEdit,
                              QProgressBar, QGroupBox, QCheckBox, QMessageBox,
                              QStatusBar, QTabWidget, QLineEdit, QSpinBox,
                              QApplication, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QDateTime, QTimer, QDate, QTime
from PySide6.QtGui import QFont, QIcon
from datetime import datetime, timedelta
from application.email_processor import EmailProcessor
from infrastructure.imap_service import ImapService
from infrastructure.file_storage import FileStorage
from infrastructure.account_db import AccountDB
from config import Config
from ui.settings_dialog import SettingsDialog
from ui.accounts_manager import AccountsManagerDialog
import os
import traceback

class ProcessingWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, list)
    error = Signal(str)
    
    def __init__(self, processor, start_date, end_date, max_emails):
        super().__init__()
        self.processor = processor
        self.start_date = start_date
        self.end_date = end_date
        self.max_emails = max_emails
    
    def run(self):
        try:
            self.progress.emit("Conectando al servidor IMAP...")
            
            results = self.processor.process_emails(
                self.start_date, 
                self.end_date,
                self.max_emails
            )
            
            self.finished.emit(True, results)
            
        except Exception as e:
            self.error.emit(f"Error: {str(e)}\n{traceback.format_exc()}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.account_db = AccountDB()
        self.processor = None
        self.worker = None
        self.imap_service = None
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        self.setWindowTitle("Email Processor - DTE (IMAP)")
        # Ajustar tamaño inicial según resolución de pantalla para soportar pantallas pequeñas
        screen = QApplication.primaryScreen().availableGeometry()
        width = min(900, screen.width() - 100)
        height = min(700, int(screen.height() * 0.85))
        self.setGeometry(100, 100, width, height)
        self.setMinimumSize(640, 360)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Processing tab
        processing_tab = QWidget()
        processing_layout = QVBoxLayout(processing_tab)
        
        # Date range group
        date_group = QGroupBox("Rango de Fechas")
        date_layout = QHBoxLayout()
        
        date_layout.addWidget(QLabel("Desde:"))
        self.start_date = QDateTimeEdit()
        self.start_date.setCalendarPopup(True)
        # Mostrar segundos y permitir edición de tiempo
        self.start_date.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_date.setDateTime(QDateTime(QDate.currentDate().addDays(-30), QTime(0, 0, 0)))
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("Hasta:"))
        self.end_date = QDateTimeEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_date.setDateTime(QDateTime(QDate.currentDate(), QTime(23, 59, 59)))
        date_layout.addWidget(self.end_date)
        
        # Quick date buttons
        quick_layout = QHBoxLayout()
        for days, label in [(1, "24h"), (7, "7d"), (30, "30d")]:
            btn = QPushButton(label)
            # Aceptar el parámetro 'checked' si la señal lo envía, o no recibir nada.
            btn.clicked.connect(lambda checked=False, d=days: self.set_quick_date(d))
            quick_layout.addWidget(btn)
        
        date_layout.addLayout(quick_layout)
        date_group.setLayout(date_layout)
        processing_layout.addWidget(date_group)

        # Cuenta selector
        account_layout = QHBoxLayout()
        account_layout.addWidget(QLabel("Cuenta:"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(300)
        account_layout.addWidget(self.account_combo)
        self.manage_accounts_btn = QPushButton("Administrar cuentas")
        self.manage_accounts_btn.clicked.connect(self.open_accounts_manager)
        account_layout.addWidget(self.manage_accounts_btn)
        processing_layout.addLayout(account_layout)
        
        # Max emails
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Máx. correos a procesar:"))
        self.max_emails = QSpinBox()
        self.max_emails.setRange(10, 1000)
        self.max_emails.setValue(100)
        max_layout.addWidget(self.max_emails)
        max_layout.addStretch()
        processing_layout.addLayout(max_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.process_btn = QPushButton("🔄 Procesar Correos")
        self.process_btn.clicked.connect(self.start_processing)
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        controls_layout.addWidget(self.process_btn)
        
        self.stop_btn = QPushButton("⏹ Detener")
        self.stop_btn.clicked.connect(self.stop_processing)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        
        self.settings_btn = QPushButton("⚙ Configuración")
        self.settings_btn.clicked.connect(self.open_settings)
        controls_layout.addWidget(self.settings_btn)
        
        processing_layout.addLayout(controls_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        processing_layout.addWidget(self.progress_bar)
        
        # Log output
        log_label = QLabel("Registro de actividad:")
        processing_layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Courier", 9))
        self.log_output.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        processing_layout.addWidget(self.log_output)
        
        # Stats
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("Correos procesados: 0 | Archivos descargados: 0")
        stats_layout.addWidget(self.stats_label)
        processing_layout.addLayout(stats_layout)
        
        tabs.addTab(processing_tab, "Procesamiento")
        
        # Schedule tab
        schedule_tab = QWidget()
        schedule_layout = QVBoxLayout(schedule_tab)
        
        schedule_group = QGroupBox("Programación Automática")
        schedule_group_layout = QVBoxLayout()
        
        self.enable_schedule = QCheckBox("Activar procesamiento programado")
        self.enable_schedule.stateChanged.connect(self.on_schedule_changed)
        schedule_group_layout.addWidget(self.enable_schedule)
        
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Intervalo (minutos):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 1440)
        self.interval_spin.setValue(self.config.get('schedule_interval', 30))
        interval_layout.addWidget(self.interval_spin)
        schedule_group_layout.addLayout(interval_layout)
        
        self.schedule_status = QLabel("Estado: Desactivado")
        self.schedule_status.setStyleSheet("font-weight: bold; color: #666;")
        schedule_group_layout.addWidget(self.schedule_status)
        
        self.save_schedule_btn = QPushButton("Guardar Programación")
        self.save_schedule_btn.clicked.connect(self.save_schedule)
        schedule_group_layout.addWidget(self.save_schedule_btn)
        
        schedule_group.setLayout(schedule_group_layout)
        schedule_layout.addWidget(schedule_group)
        schedule_layout.addStretch()
        
        tabs.addTab(schedule_tab, "Programación")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo | Configure sus credenciales en 'Configuración'")
        
        # Timer para programación
        self.schedule_timer = QTimer()
        self.schedule_timer.timeout.connect(self.scheduled_process)
    
    def load_settings(self):
        """Carga la configuración guardada"""
        interval = self.config.get('schedule_interval', 30)
        self.interval_spin.setValue(interval)
        self.max_emails.setValue(self.config.get('max_emails_per_run', 100))
        # Cargar cuentas desde la DB
        self.populate_accounts()

    def populate_accounts(self):
        """Carga cuentas desde la base de datos en el combo"""
        try:
            self.account_combo.clear()
            accounts = self.account_db.list_accounts()
            for a in accounts:
                display = f"{a['email']} ({a.get('provider','')})" if a.get('provider') else a['email']
                self.account_combo.addItem(display, a['id'])

            # Select default if exists
            default_id = self.config.get('default_account_id')
            if default_id:
                for i in range(self.account_combo.count()):
                    if self.account_combo.itemData(i) == default_id:
                        self.account_combo.setCurrentIndex(i)
                        break
        except Exception:
            pass

    def open_accounts_manager(self):
        dlg = AccountsManagerDialog(self)
        dlg.exec()
        # refrescar lista de cuentas después de administrar
        self.populate_accounts()
    
    def set_quick_date(self, days):
        """Establece fecha rápida"""
        # Calcular usando el valor actual de 'Hasta'
        try:
            end_dt = self.end_date.dateTime()
            if days == 1:
                # Para 24h: poner mismo día/mes/año que 'Hasta' y hora 00:00:00
                start_dt = QDateTime(end_dt.date(), QTime(0, 0, 0))
            else:
                # Para 7d/30d: restar días sin modificar horas/minutos/segundos
                start_dt = QDateTime(end_dt.date().addDays(-days), QTime(0, 0, 0))

            self.start_date.setDateTime(start_dt)
        except Exception:
            # fallback: usar ahora relativo
            start_dt = QDateTime.currentDateTime().addDays(-days)
            end_dt = QDateTime.currentDateTime()
            self.start_date.setDateTime(start_dt)
            self.end_date.setDateTime(end_dt)
    
    def start_processing(self):
        """Inicia el procesamiento manual"""
        if not self.initialize_processor():
            return
        
        self.process_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setRange(0, 0)  # Modo indeterminado
        
        sd = self.start_date.dateTime()
        ed = self.end_date.dateTime()
        start_date = datetime(
            sd.date().year(),
            sd.date().month(),
            sd.date().day(),
            sd.time().hour(),
            sd.time().minute(),
            sd.time().second()
        )
        end_date = datetime(
            ed.date().year(),
            ed.date().month(),
            ed.date().day(),
            ed.time().hour(),
            ed.time().minute(),
            ed.time().second()
        )
        
        self.log("=" * 60)
        self.log("INICIANDO PROCESAMIENTO MANUAL")
        self.log(f"Rango: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
        self.log(f"Máx. correos: {self.max_emails.value()}")
        self.log("=" * 60)
        
        self.worker = ProcessingWorker(
            self.processor,
            start_date,
            end_date,
            self.max_emails.value()
        )
        
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.processing_finished)
        self.worker.error.connect(self.processing_error)
        self.worker.start()
    
    def stop_processing(self):
        """Detiene el procesamiento"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.log("⚠️ Procesamiento detenido por el usuario")
            self.reset_ui_after_processing()
    
    def processing_finished(self, success, results):
        """Callback cuando termina el procesamiento"""
        self.reset_ui_after_processing()
        
        if success:
            # Estadísticas
            successful = sum(1 for r in results if r.success)
            total_files = sum(len(r.downloaded_files) for r in results if r.success)
            labeled = sum(1 for r in results if r.label_applied)
            
            self.log("=" * 60)
            self.log("✅ PROCESAMIENTO COMPLETADO")
            self.log(f"Correos procesados: {len(results)}")
            self.log(f"Correos exitosos: {successful}")
            self.log(f"Archivos descargados: {total_files}")
            self.log(f"Correos etiquetados: {labeled}")
            
            # Mostrar detalle
            for result in results:
                if result.success:
                    label_status = "🏷️" if result.label_applied else "⚠️"
                    date_str = result.local_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(result, 'local_date') else ''
                    self.log(f"  ✅ {label_status} {date_str} | {result.email_address} | {result.subject}: {len(result.downloaded_files)} archivos")
                else:
                    date_str = result.local_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(result, 'local_date') else ''
                    self.log(f"  ⏭️ {date_str} | {result.email_address} | {result.subject}: {result.error_message}")
            
            self.log("=" * 60)
            
            self.stats_label.setText(
                f"Procesados: {len(results)} | Exitosos: {successful} | Etiquetados: {labeled}"
            )
            self.status_bar.showMessage(f"Completado: {successful} exitosos, {labeled} etiquetados")
        else:
            self.log("❌ Error en el procesamiento")
    
    def processing_error(self, error_msg):
        """Callback cuando hay error"""
        self.log(f"❌ {error_msg}")
        self.reset_ui_after_processing()
        self.status_bar.showMessage("Error en el procesamiento")
    
    def update_progress(self, message):
        """Actualiza el log de progreso"""
        self.log(message)
    
    def reset_ui_after_processing(self):
        """Restablece la UI después del procesamiento"""
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.process_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def log(self, message):
        """Agrega mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        # Auto-scroll
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def initialize_processor(self):
        """Inicializa el procesador con la configuración actual"""
        try:
            # Verificar cuenta seleccionada
            account_id = self.account_combo.currentData()
            if not account_id:
                QMessageBox.warning(
                    self,
                    "Cuenta requerida",
                    "Debe seleccionar o configurar al menos una cuenta en 'Administrar cuentas'."
                )
                return False

            account = self.account_db.get_account(account_id)
            if not account:
                QMessageBox.warning(self, "Cuenta no encontrada", "La cuenta seleccionada no existe.")
                return False

            email_addr = account.get('email')
            password = account.get('password')

            if not email_addr or not password:
                QMessageBox.warning(
                    self,
                    "Configuración requerida",
                    "La cuenta seleccionada no tiene email o password. Editela en 'Administrar cuentas'."
                )
                return False
            
            # Crear servicio IMAP
            # Crear servicio IMAP usando datos de la cuenta
            server = account.get('imap_server') or self.config.get('imap_server', 'imap.gmail.com')
            port = int(account.get('imap_port') or self.config.get('imap_port', 993))
            use_ssl = bool(account.get('use_ssl', 1))

            self.imap_service = ImapService(
                email_address=email_addr,
                password=password,
                imap_server=server,
                imap_port=port,
                use_ssl=use_ssl
            )
            self.log(f"Conectando a {server}:{port} (SSL={use_ssl})...")
            if not self.imap_service.connect():
                QMessageBox.critical(
                    self,
                    "Error de conexión",
                    f"No se pudo conectar a {server}:{port}.\n\n"
                    "Verifique:\n"
                    "1. Email y contraseña correctos\n"
                    "2. Servidor/puerto IMAP configurados\n"
                    "3. Conexión a internet"
                )
                return False
            
            self.log(f"✅ Conectado a {server}:{port} exitosamente")
            
            # Asegurar que la etiqueta exista
            folder_name = self.config.get('label_name', 'DTE_Processed')
            self.imap_service.create_label_if_not_exists(folder_name)
            
            # Crear storage con opciones de organización
            file_storage = FileStorage(
                self.config.get('base_download_path', './downloads'),
                create_year=self.config.get('storage_create_year', True),
                create_month=self.config.get('storage_create_month', True),
                create_sender=self.config.get('storage_create_sender', True)
            )
            
            # Crear procesador
            self.processor = EmailProcessor(
                self.imap_service,
                file_storage,
                self.config.get('keywords', ['DTE', 'Factura Electronica']),
                folder_name
            )
            
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error de inicialización", 
                f"Error al inicializar:\n{str(e)}"
            )
            return False
    
    def open_settings(self):
        """Abre el diálogo de configuración"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.log("✅ Configuración actualizada")
            self.status_bar.showMessage("Configuración guardada correctamente")
    
    def on_schedule_changed(self, state):
        """Maneja el cambio en el checkbox de programación"""
        if state:
            self.schedule_status.setText("Estado: Configurado (debe guardar)")
            self.schedule_status.setStyleSheet("font-weight: bold; color: orange;")
        else:
            self.schedule_status.setText("Estado: Desactivado")
            self.schedule_status.setStyleSheet("font-weight: bold; color: #666;")
    
    def save_schedule(self):
        """Guarda la configuración de programación"""
        interval = self.interval_spin.value()
        enabled = self.enable_schedule.isChecked()
        
        self.config.set('schedule_interval', interval)
        
        if enabled:
            # Configurar timer
            self.schedule_timer.start(interval * 60 * 1000)  # Convertir a milisegundos
            self.schedule_status.setText(f"Estado: Activo (cada {interval} min)")
            self.schedule_status.setStyleSheet("font-weight: bold; color: green;")
            self.status_bar.showMessage(f"Programación activada: cada {interval} minutos")
        else:
            self.schedule_timer.stop()
            self.schedule_status.setText("Estado: Desactivado")
            self.schedule_status.setStyleSheet("font-weight: bold; color: #666;")
            self.status_bar.showMessage("Programación desactivada")
        
        QMessageBox.information(self, "Programación", "Configuración de programación guardada")
    
    def scheduled_process(self):
        """Procesamiento programado"""
        if not self.worker or not self.worker.isRunning():
            self.log("=" * 60)
            self.log("INICIANDO PROCESAMIENTO PROGRAMADO")
            
            # Configurar fechas automáticas
            days = self.config.get('days_to_check', 30)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Actualizar UI (incluye hora)
            from PySide6.QtCore import QDateTime
            self.start_date.setDateTime(QDateTime(start_date.year, start_date.month, start_date.day, 0, 0, 0))
            self.end_date.setDateTime(QDateTime(end_date.year, end_date.month, end_date.day, 23, 59, 59))
            
            # Iniciar procesamiento
            self.start_processing()
    
    def closeEvent(self, event):
        """Maneja el cierre de la aplicación"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Procesamiento en curso",
                "Hay un procesamiento en curso. ¿Desea detenerlo y salir?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.stop_processing()
                event.accept()
            else:
                event.ignore()
        else:
            # Limpiar conexión IMAP
            if self.imap_service:
                self.imap_service.disconnect()
            event.accept()