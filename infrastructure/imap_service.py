import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import pytz
import logging
from domain.interfaces import IEmailService
from domain.entities import EmailMessage, EmailAttachment

logger = logging.getLogger(__name__)

class ImapService(IEmailService):
    def __init__(self, email_address: str, password: str, 
                 imap_server: str = "imap.gmail.com", imap_port: int = 993, use_ssl: bool = True):
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.use_ssl = use_ssl
        self.connection = None
    
    def _normalize_date_to_utc(self, dt: datetime) -> datetime:
        """
        Normaliza una fecha a UTC para comparación consistente
        """
        if dt.tzinfo is None:
            # Si no tiene timezone, asumir hora local del sistema
            local_tz = datetime.now().astimezone().tzinfo
            dt = dt.replace(tzinfo=local_tz)
            logger.debug(f"Asignando timezone local {local_tz} a fecha sin timezone")
        
        # Convertir a UTC
        return dt.astimezone(timezone.utc)

    def _format_date_for_log(self, dt: datetime) -> str:
        """
        Formatea una fecha para logging incluyendo zona horaria
        """
        if dt.tzinfo:
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} {dt.strftime('%Z')} (UTC{dt.strftime('%z')})"
        else:
            return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} (sin timezone)"
    
    def connect(self) -> bool:
        """Conecta al servidor IMAP usando los parámetros configurados"""
        try:
            # Crear conexión (SSL o no SSL según configuración)
            if self.use_ssl:
                self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                self.connection = imaplib.IMAP4(self.imap_server, self.imap_port)

            # Login con contraseña (puede ser contraseña de aplicación)
            self.connection.login(self.email_address, self.password)

            # Seleccionar INBOX por defecto
            self.connection.select('INBOX')

            logger.info(f"Conectado exitosamente a {self.email_address} via {self.imap_server}:{self.imap_port} (SSL={self.use_ssl})")
            return True

        except imaplib.IMAP4.error as e:
            logger.error(f"Error de autenticación IMAP: {e}")
            return False
        except Exception as e:
            logger.error(f"Error conectando a IMAP: {e}")
            return False
    
    def disconnect(self) -> None:
        """Cierra la conexión IMAP"""
        try:
            if self.connection:
                self.connection.close()
                self.connection.logout()
                logger.info("Conexión IMAP cerrada")
        except Exception as e:
            logger.error(f"Error al cerrar conexión: {e}")
    
    def fetch_emails(self, start_date: datetime, end_date: datetime, 
                max_emails: int = 100, exclude_labels: List[str] = None) -> List[EmailMessage]:
        """Obtiene correos en un rango de fechas, excluyendo ciertas etiquetas"""
        if not self.connection:
            raise Exception("No hay conexión IMAP activa")
        
        try:
            # Seleccionar INBOX
            self.connection.select('INBOX')
            
            # Convertir fechas a UTC si no lo están
            # IMPORTANTE: Gmail IMAP trabaja en UTC
            if start_date.tzinfo is None:
                # Asumimos que las fechas de entrada están en hora local
                local_tz = datetime.now().astimezone().tzinfo
                start_date = start_date.replace(tzinfo=local_tz)
                end_date = end_date.replace(tzinfo=local_tz)
                logger.info(f"Fechas asumidas como hora local: {local_tz}")
            
            # Convertir a UTC para comparación con Gmail
            start_date_utc = start_date.astimezone(timezone.utc)
            end_date_utc = end_date.astimezone(timezone.utc)
            
            logger.info(f"Rango de búsqueda (local): {start_date.strftime('%Y-%m-%d %H:%M:%S %Z')} a {end_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"Rango de búsqueda (UTC):   {start_date_utc.strftime('%Y-%m-%d %H:%M:%S %Z')} a {end_date_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Construir criterio de búsqueda por fecha usando fechas UTC
            # IMAP SINCE y BEFORE solo trabajan con fecha, no con hora
            # Usamos la fecha UTC para asegurar consistencia
            imap_end_date = end_date_utc + timedelta(days=1)
            
            date_criteria = f'(SINCE {start_date_utc.strftime("%d-%b-%Y")} BEFORE {imap_end_date.strftime("%d-%b-%Y")})'
            
            # Si hay etiquetas a excluir, agregar al criterio
            if exclude_labels:
                for label in exclude_labels:
                    date_criteria = f'({date_criteria} NOT X-GM-LABELS "{label}")'
            
            logger.info(f"Criterio de búsqueda IMAP: {date_criteria}")
            
            # Buscar mensajes
            result, data = self.connection.uid('SEARCH', None, date_criteria)
            
            if result != 'OK':
                logger.error("Error en la búsqueda de correos")
                return []
            
            email_uids = data[0].split()
            
            # Limitar cantidad de correos (tomar los más recientes primero)
            if len(email_uids) > max_emails:
                email_uids = email_uids[-max_emails:]
            
            logger.info(f"Encontrados {len(email_uids)} correos en el rango de fechas (antes de filtrar por hora)")
            
            emails = []
            for uid in email_uids:
                try:
                    email_msg = self._fetch_email_by_uid(uid)
                    if email_msg:
                        # Asegurar que la fecha del email esté en UTC
                        email_date_utc = email_msg.date
                        if email_date_utc.tzinfo is None:
                            # Si no tiene zona horaria, asumir UTC (Gmail IMAP devuelve en UTC)
                            email_date_utc = email_date_utc.replace(tzinfo=timezone.utc)
                            logger.debug(f"Asignando UTC a fecha sin timezone: {email_date_utc}")
                        else:
                            # Convertir a UTC si tiene otra zona horaria
                            email_date_utc = email_date_utc.astimezone(timezone.utc)
                        
                        # FILTRAR POR HORA EXACTA (comparación en UTC)
                        if start_date_utc <= email_date_utc <= end_date_utc:
                            # Guardar la fecha original del email (con su timezone)
                            emails.append(email_msg)
                            logger.debug(f"✅ Correo {uid.decode()}: {email_date_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                        else:
                            logger.debug(f"⏭️ Correo {uid.decode()} descartado: {email_date_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    else:
                        logger.warning(f"No se pudo obtener email para UID {uid.decode()}")
                except Exception as e:
                    logger.error(f"Error procesando email UID {uid}: {e}")
                    continue
            
            # Ordenar por fecha descendente (más recientes primero)
            emails.sort(key=lambda x: x.date, reverse=True)
            
            logger.info(f"✅ Recuperados {len(emails)} correos después del filtro por hora")
            if emails:
                logger.info(f"Rango real: {emails[-1].date.strftime('%Y-%m-%d %H:%M:%S %Z')} a {emails[0].date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            return emails
            
        except Exception as e:
            logger.error(f"Error obteniendo correos: {e}")
            return []
    
    def _fetch_email_by_uid(self, uid: bytes) -> Optional[EmailMessage]:
        """Obtiene los detalles de un correo por UID con manejo correcto de zona horaria"""
        try:
            # Obtener el mensaje completo por UID incluyendo fecha interna
            result, msg_data = self.connection.uid('FETCH', uid, '(RFC822 FLAGS X-GM-LABELS INTERNALDATE)')
            
            if result != 'OK' or not msg_data[0]:
                return None
            
            # Parsear la respuesta
            raw_email = None
            flags = []
            labels = []
            internal_date = None
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    # Extraer información del primer elemento
                    info_str = response_part[0].decode('utf-8', errors='ignore')
                    
                    # Extraer fecha interna del servidor (INTERNALDATE)
                    # IMPORTANTE: INTERNALDATE viene en UTC según RFC 3501
                    if 'INTERNALDATE' in info_str:
                        import re
                        date_match = re.search(r'INTERNALDATE "(.+?)"', info_str)
                        if date_match:
                            date_str = date_match.group(1)
                            try:
                                # Parsear fecha IMAP: "DD-Mon-YYYY HH:MM:SS +ZZZZ"
                                # El offset en INTERNALDATE siempre es +0000 (UTC)
                                internal_date = datetime.strptime(
                                    date_str[:-6],  # Quitar el " +0000"
                                    "%d-%b-%Y %H:%M:%S"
                                ).replace(tzinfo=timezone.utc)
                                logger.debug(f"INTERNALDATE (UTC): {internal_date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                            except Exception as e:
                                logger.warning(f"No se pudo parsear INTERNALDATE '{date_str}': {e}")
                    
                    # Extraer labels de Gmail
                    if 'X-GM-LABELS' in info_str:
                        import re
                        labels_match = re.findall(r'X-GM-LABELS \((.*?)\)', info_str)
                        if labels_match:
                            labels = labels_match[0].split()
                    
                    # Extraer FLAGS
                    if 'FLAGS' in info_str:
                        flags_match = re.findall(r'FLAGS \((.*?)\)', info_str)
                        if flags_match:
                            flags = flags_match[0].split()
                    
                    # Obtener el contenido del email
                    if len(response_part) > 1:
                        raw_email = response_part[1]
                    break
            
            if not raw_email:
                return None
            
            # Parsear mensaje
            if isinstance(raw_email, bytes):
                email_message = email.message_from_bytes(raw_email)
            else:
                email_message = email.message_from_string(raw_email)
            
            if not email_message:
                return None
            
            # Extraer encabezados
            subject = self._decode_header(email_message['Subject'])
            sender = self._decode_header(email_message['From'])
            recipient = self._decode_header(email_message['To'])
            
            # Obtener fecha del email
            # Prioridad: INTERNALDATE (UTC) > Date header (puede tener zona horaria)
            if internal_date:
                # INTERNALDATE es la hora real en que el servidor recibió el email (UTC)
                date = internal_date
            else:
                # Usar el header Date del email
                date_str = email_message['Date']
                try:
                    from email.utils import parsedate_to_datetime
                    date = parsedate_to_datetime(date_str)
                    
                    # parsedate_to_datetime ya incluye la zona horaria del header Date
                    if date.tzinfo is None:
                        # Si no tiene, asumir UTC
                        logger.debug(f"Fecha sin timezone en header, asumiendo UTC: {date_str}")
                        date = date.replace(tzinfo=timezone.utc)
                    
                    logger.debug(f"Fecha del header Date: {date.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                except Exception as e:
                    logger.warning(f"No se pudo parsear fecha del header '{date_str}': {e}")
                    date = datetime.now(timezone.utc)
            
            # Generar Message-ID
            message_id = email_message.get('Message-ID', uid.decode())
            
            # Obtener cuerpo y adjuntos
            body = ""
            html_body = ""
            attachments = []
            has_json = False
            has_pdf = False
            
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))
                    
                    # Si es un adjunto
                    if 'attachment' in content_disposition or part.get_filename():
                        filename = part.get_filename()
                        if filename:
                            filename = self._decode_header(filename)
                            size = len(part.get_payload(decode=True) or b'')
                            
                            attachment = EmailAttachment(
                                filename=filename,
                                content_type=content_type,
                                part=part,
                                size=size
                            )
                            attachments.append(attachment)
                            
                            if filename.lower().endswith('.json'):
                                has_json = True
                            elif filename.lower().endswith('.pdf'):
                                has_pdf = True
                    
                    # Si es texto plano
                    elif content_type == 'text/plain' and 'attachment' not in content_disposition:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode('utf-8', errors='ignore')
                        except:
                            pass
                    
                    # Si es HTML (como fallback si no hay text/plain)
                    elif content_type == 'text/html' and 'attachment' not in content_disposition:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_body = payload.decode('utf-8', errors='ignore')
                        except:
                            pass
            else:
                # Mensaje no multipart
                content_type = email_message.get_content_type()
                if content_type == 'text/plain':
                    try:
                        payload = email_message.get_payload(decode=True)
                        if payload:
                            body = payload.decode('utf-8', errors='ignore')
                    except:
                        pass
                elif content_type == 'text/html':
                    try:
                        payload = email_message.get_payload(decode=True)
                        if payload:
                            html_body = payload.decode('utf-8', errors='ignore')
                    except:
                        pass
            
            # Si no hay texto plano, usar HTML limpio de tags
            if not body and html_body:
                import re
                # Remover tags HTML y entidades
                clean_html = re.sub('<[^<]+?>', '', html_body)
                clean_html = clean_html.replace('&nbsp;', ' ')
                clean_html = clean_html.replace('&lt;', '<')
                clean_html = clean_html.replace('&gt;', '>')
                clean_html = clean_html.replace('&amp;', '&')
                body = clean_html
            
            return EmailMessage(
                uid=uid.decode(),
                message_id=message_id,
                sender=sender,
                recipient=recipient,
                subject=subject,
                date=date,  # Fecha con timezone UTC
                body=body,
                attachments=attachments,
                has_json=has_json,
                has_pdf=has_pdf,
                flags=flags,
                labels=labels
            )
            
        except Exception as e:
            logger.error(f"Error al obtener email UID {uid}: {e}")
            return None
    
    def _decode_header(self, header_value: str) -> str:
        """Decodifica encabezados de correo"""
        if not header_value:
            return ""
        
        try:
            decoded_parts = decode_header(header_value)
            result = []
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        result.append(part.decode(encoding, errors='ignore'))
                    else:
                        result.append(part.decode('utf-8', errors='ignore'))
                else:
                    result.append(str(part))
            return ' '.join(result)
        except:
            return str(header_value)
    
    def download_attachment(self, email_uid: str, attachment_part) -> Optional[bytes]:
        """Descarga un adjunto específico"""
        try:
            # Obtener el payload decodificado
            payload = attachment_part.get_payload(decode=True)
            return payload
        except Exception as e:
            logger.error(f"Error descargando adjunto: {e}")
            return None
    
    def add_label(self, email_uid: str, label_name: str) -> bool:
        """
        Aplica una etiqueta de Gmail a un correo específico
        En Gmail, las etiquetas se aplican con X-GM-LABELS
        """
        try:
            # Seleccionar INBOX
            self.connection.select('INBOX')
            
            # Primero, obtener etiquetas actuales
            result, data = self.connection.uid('FETCH', email_uid.encode(), '(X-GM-LABELS)')
            
            if result != 'OK':
                logger.error(f"No se pudo obtener etiquetas para UID {email_uid}")
                return False
            
            # Extraer etiquetas actuales
            current_labels = []
            if data and data[0]:
                response = data[0].decode('utf-8', errors='ignore')
                import re
                labels_match = re.findall(r'X-GM-LABELS \((.*?)\)', response)
                if labels_match:
                    current_labels = labels_match[0].split()
            
            # Agregar la nueva etiqueta si no existe
            if label_name not in current_labels:
                current_labels.append(f'"{label_name}"')
                
                # Construir comando para almacenar etiquetas
                labels_str = ' '.join(current_labels)
                
                # Aplicar etiquetas usando STORE con X-GM-LABELS
                result = self.connection.uid(
                    'STORE', 
                    email_uid.encode(), 
                    'X-GM-LABELS', 
                    f'({labels_str})'
                )
                
                if result[0] == 'OK':
                    logger.info(f"✅ Etiqueta '{label_name}' aplicada al correo UID {email_uid}")
                    return True
                else:
                    logger.error(f"Error aplicando etiqueta: {result}")
                    return False
            else:
                logger.info(f"El correo UID {email_uid} ya tiene la etiqueta '{label_name}'")
                return True
                
        except Exception as e:
            logger.error(f"Error al aplicar etiqueta: {e}")
            return False
    
    def create_label_if_not_exists(self, label_name: str) -> bool:
        """
        Crea una etiqueta en Gmail si no existe
        En IMAP de Gmail, las etiquetas se crean como carpetas
        """
        try:
            # Listar todas las carpetas/etiquetas
            result, folders = self.connection.list()
            
            # Verificar si la etiqueta ya existe
            label_exists = False
            for folder in folders:
                folder_str = folder.decode('utf-8', errors='ignore')
                if label_name in folder_str:
                    label_exists = True
                    break
            
            if not label_exists:
                # Crear la etiqueta como carpeta IMAP
                result = self.connection.create(f'"{label_name}"')
                if result[0] == 'OK':
                    logger.info(f"Etiqueta '{label_name}' creada exitosamente")
                    return True
                else:
                    logger.error(f"Error creando etiqueta '{label_name}': {result}")
                    return False
            else:
                logger.info(f"La etiqueta '{label_name}' ya existe")
                return True
                
        except Exception as e:
            logger.error(f"Error creando etiqueta: {e}")
            return False

    # NOTE: folder-based aliases removed — use `create_label_if_not_exists`.
    
    def get_labels_for_email(self, email_uid: str) -> List[str]:
        """Obtiene las etiquetas actuales de un correo"""
        try:
            self.connection.select('INBOX')
            result, data = self.connection.uid('FETCH', email_uid.encode(), '(X-GM-LABELS)')
            
            if result == 'OK' and data and data[0]:
                response = data[0].decode('utf-8', errors='ignore')
                import re
                labels_match = re.findall(r'X-GM-LABELS \((.*?)\)', response)
                if labels_match:
                    return labels_match[0].split()
            
            return []
        except Exception as e:
            logger.error(f"Error obteniendo etiquetas: {e}")
            return []