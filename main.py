#!/usr/bin/env python3
import sys
import os
from PySide6.QtWidgets import QApplication
import logging
from ui.main_window import MainWindow
from scheduler.cron_job import SchedulerManager
from config import Config
import argparse

def main():
    parser = argparse.ArgumentParser(description='Email Processor - DTE')
    parser.add_argument('--scheduler', action='store_true', 
                       help='Ejecutar en modo scheduler (segundo plano)')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Archivo de configuración')
    
    args = parser.parse_args()
    
    if args.scheduler:
        # Modo scheduler
        from scheduler.cron_job import run_scheduler_standalone
        run_scheduler_standalone()
    else:
        # Modo GUI
        app = QApplication(sys.argv)

        # Try to apply qt-material theme; fall back to built-in stylesheet if not available
        try:
            from qt_material import apply_stylesheet
            # Apply a pleasant dark material theme; if the theme name is unavailable,
            # qt_material will raise — we catch and fallback.
            apply_stylesheet(app, theme='dark_teal.xml')
        except Exception as e:
            logging.getLogger(__name__).info('qt_material not available or failed; using default stylesheet')
            app.setStyle('Fusion')
            # Set application style (fallback)
            app.setStyleSheet("""
                QMainWindow {
                    background-color: #f5f5f5;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 1ex;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QPushButton {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    padding: 5px 10px;
                    background-color: white;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())

if __name__ == "__main__":
    main()