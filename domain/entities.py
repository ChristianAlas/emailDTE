from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class EmailAttachment:
    filename: str
    content_type: str
    part: object  # Referencia a la parte del mensaje
    size: int

@dataclass
class EmailMessage:
    uid: str
    message_id: str
    sender: str
    recipient: str
    subject: str
    date: datetime
    body: str
    attachments: List[EmailAttachment]
    has_json: bool
    has_pdf: bool
    flags: List[str]
    labels: List[str]  # Lista de etiquetas de Gmail

@dataclass
class ProcessingResult:
    success: bool
    local_date: datetime
    email_address: str
    subject: str
    downloaded_files: List[str]
    error_message: Optional[str] = None
    label_applied: bool = False  # Cambiado de moved_to_folder a label_applied