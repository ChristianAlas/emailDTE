import schedule
import time
import threading
from datetime import datetime, timedelta
from application.email_processor import EmailProcessor
from infrastructure.imap_service import ImapService
from infrastructure.file_storage import FileStorage
from config import Config
import logging
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_processor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self, config: Config):
        self.config = config
        self.processor = None
        self.imap_service = None
        self.running = False
        self.thread = None
    
    def initialize(self):
        """Inicializa los servicios"""
        try:
            # Verificar credenciales
            email_addr = self.config.get('email')
            password = self.config.get('password')
            
            if not email_addr or not password:
                logger.error("Credenciales no configuradas")
                return False
            
            # Crear servicio IMAP
            self.imap_service = ImapService(
                email_address=email_addr,
                password=password
            )
            
            if not self.imap_service.connect():
                logger.error("No se pudo conectar a Gmail")
                return False
            
            logger.info("Conectado a Gmail exitosamente")
            
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
            logger.error(f"Error inicializando: {e}")
            return False
    
    def start(self):
        """Inicia el scheduler"""
        if not self.processor:
            if not self.initialize():
                return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("Scheduler iniciado en segundo plano")
    
    def stop(self):
        """Detiene el scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        if self.imap_service:
            self.imap_service.disconnect()
        
        logger.info("Scheduler detenido")
    
    def _run_scheduler(self):
        """Ejecuta el bucle del scheduler"""
        interval = self.config.get('schedule_interval', 30)
        schedule.every(interval).minutes.do(self._process_job)
        
        logger.info(f"Scheduler configurado cada {interval} minutos")
        
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def _process_job(self):
        """Trabajo programado"""
        try:
            logger.info("=" * 50)
            logger.info("Iniciando procesamiento programado")
            
            end_date = datetime.now()
            days = self.config.get('days_to_check', 30)
            start_date = end_date - timedelta(days=days)
            max_emails = self.config.get('max_emails_per_run', 100)
            
            logger.info(f"Rango: {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
            
            # Reconectar si es necesario
            if not self.imap_service:
                self.initialize()
            
            results = self.processor.process_emails(start_date, end_date, max_emails)
            
            # Estadísticas
            successful = sum(1 for r in results if r.success)
            total_files = sum(len(r.downloaded_files) for r in results if r.success)
            
            logger.info(f"Procesados: {len(results)} correos")
            logger.info(f"Exitosos: {successful}")
            logger.info(f"Archivos descargados: {total_files}")
            
            # Actualizar última ejecución
            self.config.set('last_run', datetime.now().isoformat())
            
            logger.info("Procesamiento programado completado")
            
        except Exception as e:
            logger.error(f"Error en procesamiento programado: {e}", exc_info=True)

def run_scheduler_standalone():
    """Ejecuta el scheduler de forma independiente (para cron)"""
    config = Config()
    
    # Verificar configuración mínima
    if not config.get('email') or not config.get('password'):
        logger.error("ERROR: Debe configurar email y contraseña en config.json")
        sys.exit(1)
    
    manager = SchedulerManager(config)
    
    if manager.initialize():
        logger.info("Scheduler iniciado en modo standalone")
        
        # Ejecutar procesamiento inmediato
        logger.info("Ejecutando procesamiento inicial...")
        manager._process_job()
        
        # Mantener vivo para programación
        manager.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Deteniendo scheduler...")
            manager.stop()
    else:
        logger.error("No se pudo inicializar el scheduler")
        sys.exit(1)

if __name__ == "__main__":
    run_scheduler_standalone()