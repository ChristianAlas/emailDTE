from typing import List, Optional
from datetime import datetime, timedelta
import logging
import unicodedata
from domain.interfaces import IEmailService, IFileStorage
from domain.entities import EmailMessage, ProcessingResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailProcessor:
    def __init__(self, email_service: IEmailService, file_storage: IFileStorage, 
                 keywords: List[str], label_name: str):
        self.email_service = email_service
        self.file_storage = file_storage
        # Normalize and casefold keywords to handle accents and special chars
        self.keywords = [self._normalize_text(k) for k in keywords]
        self.label_name = label_name
        # Log normalized keywords for debugging
        logger.info(f"Keywords configuradas (originales): {keywords}")
        logger.info(f"Keywords normalizadas (sin acentos): {self.keywords}")

    def _normalize_text(self, text: Optional[str]) -> str:
        """Normalize unicode and remove diacritics (accents) for robust keyword matching.
        E.g., 'Factura  Electrónica' -> 'factura electronica', 'DTE' -> 'dte'.
        Also removes special characters and collapses multiple spaces into single spaces.
        """
        if not text:
            return ""
        text_str = str(text).strip()
        # Normalize to NFD form (decomposed) to separate letters and diacritics
        nfd = unicodedata.normalize('NFD', text_str)
        # Filter out combining marks (accents, diacritics)
        without_accents = ''.join(
            ch for ch in nfd
            if unicodedata.category(ch) != 'Mn'  # Mn = Mark, nonspacing
        )
        # Casefold for case-insensitive matching (handles ß -> ss, etc.)
        casefolded = without_accents.casefold()
        # Remove special characters, keep only alphanumeric, accented chars (now removed), and spaces
        # This removes [*], ., ,, etc.
        cleaned = ''.join(
            ch for ch in casefolded
            if ch.isalnum() or ch.isspace()
        )
        # Collapse multiple spaces into single space
        normalized_spaces = ' '.join(cleaned.split())
        # Remove leading/trailing whitespace
        return normalized_spaces.strip()
    
    def process_emails(self, start_date: datetime, end_date: datetime, 
                      max_emails: int = 100) -> List[ProcessingResult]:
        results = []
        
        try:
            # Asegurar que la etiqueta existe
            self.email_service.create_label_if_not_exists(self.label_name)
            logger.info(f"Usando etiqueta: '{self.label_name}'")
            
            # Obtener correos, excluyendo los que ya tienen la etiqueta
            emails = self.email_service.fetch_emails(
                start_date, 
                end_date, 
                max_emails,
                exclude_labels=[self.label_name]  # No reprocesar los ya etiquetados
            )
            
            logger.info(f"Encontrados {len(emails)} correos para procesar (sin etiqueta '{self.label_name}')")
            
            for i, email in enumerate(emails, 1):
                logger.info(f"Procesando {i}/{len(emails)}: {email.subject[:50]}...")
                result = self._process_single_email(email)
                results.append(result)
                
                # Log detallado
                if result.success:
                    logger.info(f"✅ {email.subject[:50]}: {len(result.downloaded_files)} archivos, etiquetado: {result.label_applied}")
                else:
                    logger.info(f"⏭️ {email.subject[:50]}: {result.error_message}")
            
        except Exception as e:
            logger.error(f"Error procesando correos: {e}")
        
        return results
    
    def _process_single_email(self, email: EmailMessage) -> ProcessingResult:
        try:
            # Verificar que NO tenga ya la etiqueta (doble verificación)
            current_labels = self.email_service.get_labels_for_email(email.uid)
            if self.label_name in current_labels:
                # Ya etiquetado
                local_dt = email.date
                try:
                    if getattr(local_dt, 'tzinfo', None):
                        local_dt = local_dt.astimezone()
                except Exception:
                    pass
                return ProcessingResult(
                    success=False,
                    local_date=local_dt,
                    email_address=email.sender,
                    subject=email.subject,
                    downloaded_files=[],
                    error_message=f"Ya tiene etiqueta '{self.label_name}'"
                )
            
            # Verificar que tenga JSON (requisito principal)
            if not email.has_json:
                local_dt = email.date
                try:
                    if getattr(local_dt, 'tzinfo', None):
                        local_dt = local_dt.astimezone()
                except Exception:
                    pass
                return ProcessingResult(
                    success=False,
                    local_date=local_dt,
                    email_address=email.sender,
                    subject=email.subject,
                    downloaded_files=[],
                    error_message="No tiene archivo JSON"
                )
            
            # Verificar palabras clave en asunto, cuerpo o nombres de adjuntos
            if not self._contains_keywords(email):
                local_dt = email.date
                try:
                    if getattr(local_dt, 'tzinfo', None):
                        local_dt = local_dt.astimezone()
                except Exception:
                    pass
                return ProcessingResult(
                    success=False,
                    local_date=local_dt,
                    email_address=email.sender,
                    subject=email.subject,
                    downloaded_files=[],
                    error_message="No contiene palabras clave requeridas"
                )
            
            # Descargar adjuntos JSON y PDF
            downloaded_files = []
            
            for attachment in email.attachments:
                filename_lower = attachment.filename.lower()
                
                # Solo descargar JSON y PDF
                if filename_lower.endswith('.json') or filename_lower.endswith('.pdf'):
                    logger.info(f"Descargando: {attachment.filename}")
                    
                    content = self.email_service.download_attachment(
                        email.uid, 
                        attachment.part
                    )
                    
                    if content:
                        # Validar que no esté vacío
                        if len(content) == 0:
                            logger.warning(f"Archivo vacío: {attachment.filename}")
                            continue
                        
                        # Guardar archivo
                        file_path = self.file_storage.save_file(
                            email, 
                            attachment.filename, 
                            content
                        )
                        downloaded_files.append(file_path)
                        logger.info(f"Guardado: {file_path}")
            
            # Si se descargaron archivos, APLICAR ETIQUETA en Gmail
            label_applied = False
            if downloaded_files:
                label_applied = self.email_service.add_label(email.uid, self.label_name)
                if label_applied:
                    logger.info(f"✅ Etiqueta '{self.label_name}' aplicada al correo")
                else:
                    logger.warning(f"⚠️ No se pudo aplicar etiqueta al correo")
            
            local_dt = email.date
            try:
                if getattr(local_dt, 'tzinfo', None):
                    local_dt = local_dt.astimezone()
            except Exception:
                pass
            return ProcessingResult(
                success=True,
                local_date=local_dt,
                email_address=email.sender,
                subject=email.subject,
                downloaded_files=downloaded_files,
                label_applied=label_applied
            )
            
        except Exception as e:
            logger.error(f"Error procesando email {email.uid}: {e}")
            local_dt = getattr(email, 'date', datetime.now())
            try:
                if getattr(local_dt, 'tzinfo', None):
                    local_dt = local_dt.astimezone()
            except Exception:
                pass
            return ProcessingResult(
                success=False,
                local_date=local_dt,
                email_address=getattr(email, 'sender', ''),
                subject=getattr(email, 'subject', ''),
                downloaded_files=[],
                error_message=str(e)
            )
    
    def _contains_keywords(self, email: EmailMessage) -> bool:
        """Verifica si el correo contiene las palabras clave (case-insensitive, accent-insensitive).
        Busca en: asunto, cuerpo, nombres de adjuntos.
        """
        # Normalizar texto del correo
        subject_norm = self._normalize_text(email.subject)
        body_norm = self._normalize_text(email.body)
        
        # Revisar en el asunto
        for keyword in self.keywords:
            if keyword and keyword in subject_norm:
                logger.info(f"✓ Keyword encontrada en asunto: '{keyword}' en '{email.subject}'")
                return True
        
        # Revisar en el cuerpo
        for keyword in self.keywords:
            if keyword and keyword in body_norm:
                logger.info(f"✓ Keyword encontrada en cuerpo: '{keyword}'")
                return True
        
        # Revisar en nombres de adjuntos
        for attachment in email.attachments:
            filename_norm = self._normalize_text(attachment.filename)
            for keyword in self.keywords:
                if keyword and keyword in filename_norm:
                    logger.info(f"✓ Keyword encontrada en adjunto: '{keyword}' en '{attachment.filename}'")
                    return True
        
        # No encontró keywords - loguear información de debug
        logger.warning(f"✗ Ninguna keyword encontrada en asunto, cuerpo o adjuntos.")
        logger.warning(f"  Asunto: '{email.subject}' → normalizado: '{subject_norm}'")
        logger.warning(f"  Cuerpo RAW (primeros 300 chars): {repr(email.body[:300] if email.body else 'VACÍO')}")
        logger.warning(f"  Cuerpo normalizado (primeros 300 chars): '{body_norm[:300] if body_norm else 'VACÍO'}'")
        logger.warning(f"  Keywords buscadas: {self.keywords}")
        return False