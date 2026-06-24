import os
import json
from pathlib import Path

class Config:
    def __init__(self, config_file="config.json"):
        self.config_file = Path(config_file)
        self.default_config = {
            "email": "tu_correo@gmail.com",
            "password": "",  # Contraseña de aplicación
            "imap_server": "imap.gmail.com",
            "imap_use_ssl": True,
            "provider": "Gmail",
            "imap_port": 993,
            "base_download_path": "./downloads",
            "storage_create_year": True,
            "storage_create_month": True,
            "storage_create_sender": True,
            "keywords": ["DTE", "Factura Electronica", "Factura", "Boleta"],
            "label_name": "DTE_Processed",  # Nombre de la etiqueta en Gmail
            "schedule_interval": 30,  # minutos
            "days_to_check": 30,  # Días hacia atrás para revisar
            "last_run": None,
            "max_emails_per_run": 100
        }
        self.config = self.load_config()
    
    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {**self.default_config, **config}
        return self.default_config.copy()
    
    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save_config()