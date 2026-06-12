import os
from pathlib import Path
from typing import List
from domain.interfaces import IFileStorage
from domain.entities import EmailMessage

class FileStorage(IFileStorage):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_download_path(self, email: EmailMessage) -> str:
        # Extraer email username
        email_user = email.sender.split('<')[-1].strip('>').strip()
        # Limpiar caracteres no válidos para carpeta
        email_user = "".join(c for c in email_user if c.isalnum() or c in ('@', '_', '-'))
        email_user = email_user.replace('@', '_at_')
        
        # Crear path: YYYY/MM MonthName/email/
        year = email.date.strftime('%Y')
        month_num = email.date.strftime('%m')
        
        # Nombres de meses en español
        meses = {
            '01': 'Enero', '02': 'Febrero', '03': 'Marzo',
            '04': 'Abril', '05': 'Mayo', '06': 'Junio',
            '07': 'Julio', '08': 'Agosto', '09': 'Septiembre',
            '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
        }
        month_name = meses.get(month_num, month_num)
        
        folder_name = f"{month_num} {month_name}"
        path = self.base_path / year / folder_name / email_user
        path.mkdir(parents=True, exist_ok=True)
        
        return str(path)
    
    def save_file(self, email: EmailMessage, filename: str, content: bytes) -> str:
        download_path = self.get_download_path(email)
        file_path = Path(download_path) / filename
        
        # Manejar nombres duplicados
        counter = 1
        original_path = file_path
        while file_path.exists():
            name, ext = os.path.splitext(filename)
            file_path = Path(download_path) / f"{name}_{counter}{ext}"
            counter += 1
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return str(file_path)