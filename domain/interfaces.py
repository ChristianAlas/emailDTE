from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from .entities import EmailMessage, ProcessingResult

class IEmailService(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def fetch_emails(self, start_date: datetime, end_date: datetime, 
                    max_emails: int = 100, exclude_labels: List[str] = None) -> List[EmailMessage]:
        pass
    
    @abstractmethod
    def download_attachment(self, email_uid: str, attachment_part) -> Optional[bytes]:
        pass
    
    @abstractmethod
    def add_label(self, email_uid: str, label_name: str) -> bool:
        pass
    
    @abstractmethod
    def create_label_if_not_exists(self, label_name: str) -> bool:
        pass
    
    @abstractmethod
    def get_labels_for_email(self, email_uid: str) -> List[str]:
        pass

class IFileStorage(ABC):
    @abstractmethod
    def save_file(self, email: EmailMessage, filename: str, content: bytes) -> str:
        pass
    
    @abstractmethod
    def get_download_path(self, email: EmailMessage) -> str:
        pass