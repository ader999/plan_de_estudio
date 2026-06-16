import os
import subprocess
import datetime
import base64
import logging
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.contrib.auth import get_user_model
import resend

logger = logging.getLogger(__name__)

def run_backup(send_email=False):
    db_config = settings.DATABASES['default']
    db_name = db_config['NAME']
    db_user = db_config.get('USER')
    db_password = db_config.get('PASSWORD')
    db_host = db_config.get('HOST')
    db_port = db_config.get('PORT')
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Intentamos primero usar pg_dump
    filepath = None
    filename = None
    use_pg_dump = False
    
    if db_config['ENGINE'] == 'django.db.backends.postgresql' and db_name and db_user and db_password and db_host:
        filename = f"backup_{db_name}_{timestamp}.dump"
        filepath = os.path.join('/tmp', filename)
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port or 5432),
            '-U', db_user,
            '-d', db_name,
            '-F', 'c',  # Formato comprimido personalizado
            '-b',
            '-f', filepath
        ]
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                use_pg_dump = True
                logger.info(f"pg_dump completado exitosamente: {filepath}")
            else:
                logger.warning(f"pg_dump falló (código de salida {result.returncode}): {result.stderr}. Usando dumpdata de fallback.")
        except FileNotFoundError:
            logger.warning("Utilidad pg_dump no encontrada. Usando dumpdata de fallback.")
        except Exception as e:
            logger.warning(f"Error al ejecutar pg_dump: {e}. Usando dumpdata de fallback.")
            
    if not use_pg_dump:
        # Fallback a serialización nativa JSON de Django
        filename = f"backup_{db_name or 'db'}_{timestamp}.json"
        filepath = os.path.join('/tmp', filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                call_command('dumpdata', stdout=f, indent=4)
            logger.info(f"dumpdata de fallback completado exitosamente: {filepath}")
        except Exception as e:
            logger.error(f"dumpdata de fallback falló: {e}")
            raise e
            
    # 2. Subir a MinIO usando el default_storage configurado
    try:
        with open(filepath, 'rb') as f:
            storage_path = f"copias_db/{filename}"
            default_storage.save(storage_path, ContentFile(f.read()))
            logger.info(f"Copia de seguridad subida a MinIO: {storage_path}")
    except Exception as e:
        logger.error(f"Error al subir copia de seguridad a MinIO: {e}")
        
    # 3. Enviar correo usando Resend si está habilitado
    success_email = False
    if send_email:
        resend_key = os.environ.get("RESEND")
        if resend_key:
            resend.api_key = resend_key
            User = get_user_model()
            superusers = User.objects.filter(is_superuser=True, email__isnull=False).exclude(email='')
            emails = [u.email for u in superusers]
            if not emails:
                emails = ['aderjasmirzeasrocha@gmail.com']  # Fallback a correo del creador
                
            try:
                with open(filepath, 'rb') as f:
                    file_content = f.read()
                    encoded_content = base64.b64encode(file_content).decode("utf-8")
                
                resend.Emails.send({
                    "from": "planeauml@codeader.com",
                    "to": emails,
                    "subject": f"Copia de seguridad de la Base de Datos - {filename}",
                    "html": f"""
                    <h3>Copia de Seguridad de la Base de Datos</h3>
                    <p>Se ha generado una copia de seguridad de la base de datos automáticamente.</p>
                    <ul>
                        <li><strong>Nombre del archivo:</strong> {filename}</li>
                        <li><strong>Formato:</strong> {'PostgreSQL Dump (.dump)' if use_pg_dump else 'Django Serialized JSON (.json)'}</li>
                        <li><strong>Fecha y Hora:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                    </ul>
                    <p>Adjunto encontrarás el archivo de copia de seguridad.</p>
                    """,
                    "attachments": [
                        {
                            "content": encoded_content,
                            "filename": filename,
                        }
                    ]
                })
                success_email = True
                logger.info(f"Correo de copia de seguridad enviado a: {emails}")
            except Exception as e:
                logger.error(f"Error al enviar correo de copia de seguridad: {e}")
        else:
            logger.warning("Clave API de Resend no configurada. Saltando envío de correo.")
            
    return filepath, filename, success_email
