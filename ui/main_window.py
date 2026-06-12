from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QPushButton, QTextEdit, QLabel, QDateTimeEdit,
                              QProgressBar, QGroupBox, QCheckBox, QMessageBox,
                              QStatusBar, QTabWidget, QLineEdit, QSpinBox,
                              QApplication)
from PySide6.QtCore import Qt, QThread, Signal, QDateTime, QTimer
from PySide6.QtGui import QFont, QIcon
from datetime import datetime, timedelta
from application.email_processor import EmailProcessor
from infrastructure.imap_service import ImapService
from infrastructure.file_storage import FileStorage
from config import Config
from ui.settings_dialog import SettingsDialog
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
        self.processor = None
        self.worker = None
        self.imap_service = None
        self.init_ui()
        self.load_settings()
    
    def init_ui(self):
        self.setWindowTitle("Email Processor - DTE (IMAP)")
        self.setGeometry(100, 100, 900, 700)
        
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
        self.start_date.setDateTime(QDateTime.currentDateTime().addDays(-30))
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("Hasta:"))
        self.end_date = QDateTimeEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDateTime(QDateTime.currentDateTime())
        date_layout.addWidget(self.end_date)
        
        # Quick date buttons
        quick_layout = QHBoxLayout()
        for days, label in [(1, "24h"), (7, "7d"), (30, "30d")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, d=days: self.set_quick_date(d))
            quick_layout.addWidget(btn)
        
        date_layout.addLayout(quick_layout)
        date_group.setLayout(date_layout)
        processing_layout.addWidget(date_group)
        
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
    
    def set_quick_date(self, days):
        """Establece fecha rápida"""
        self.start_date.setDateTime(QDateTime.currentDateTime().addDays(-days))
        self.end_date.setDateTime(QDateTime.currentDateTime())
    
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
            # Verificar credenciales
            email_addr = self.config.get('email')
            password = self.config.get('password')
            
            if not email_addr or not password:
                QMessageBox.warning(
                    self,
                    "Configuración requerida",
                    "Debe configurar su correo y contraseña de aplicación.\n"
                    "Vaya a 'Configuración' para establecerlos."
                )
                return False
            
            # Crear servicio IMAP
            self.imap_service = ImapService(
                email_address=email_addr,
                password=password,
                imap_server=self.config.get('imap_server', 'imap.gmail.com'),
                imap_port=self.config.get('imap_port', 993)
            )
            
            # Conectar
            self.log("Conectando a Gmail...")
            if not self.imap_service.connect():
                QMessageBox.critical(
                    self,
                    "Error de conexión",
                    "No se pudo conectar a Gmail.\n\n"
                    "Verifique:\n"
                    "1. Email y contraseña de aplicación correctos\n"
                    "2. IMAP habilitado en configuración de Gmail\n"
                    "3. Conexión a internet"
                )
                return False
            
            self.log("✅ Conectado a Gmail exitosamente")
            
            # Asegurar que la etiqueta exista
            folder_name = self.config.get('label_name', 'DTE_Processed')
            self.imap_service.create_label_if_not_exists(folder_name)
            
            # Crear storage
            file_storage = FileStorage(self.config.get('base_download_path', './downloads'))
            
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