import os
import json
from django.conf import settings
from django.urls import reverse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import google.auth.transport.requests
import requests
from ..models import CredencialesGoogle

# Permitir Oauth2 sobre HTTP para desarrollo local (evita error insecure_transport)
if settings.DEBUG:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Los scopes necesarios para el proyecto:
# 1. Crear/gestionar clases de Classroom
# 2. Ver información básica del perfil (para obtener la foto y el email)
SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses',
    'https://www.googleapis.com/auth/classroom.coursework.students',
    'https://www.googleapis.com/auth/classroom.rosters',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

def obtener_configuracion_cliente():
    """Construye el diccionario de cliente desde las variables de entorno"""
    return {
        "web": {
            "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
            "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET'),
            "redirect_uris": [
                "http://localhost:8000/oauth2callback/",
                "http://127.0.0.1:8000/oauth2callback/",
                "https://planeauml.codeader.com/oauth2callback/"
            ]
        }
    }


def iniciar_autorizacion(request):
    """Genera la URL de autorización para redirigir al usuario a Google."""
    # Obtenemos la url de retorno absoluta (ej. http://localhost:8000/oauth2callback/)
    redirect_uri = request.build_absolute_uri(reverse('oauth2callback'))
    
    # Nos aseguramos que termine en /oauth2callback/ y coincida exactamente con el host llamado
    if 'planeauml.codeader.com' in redirect_uri:
        redirect_uri = "https://planeauml.codeader.com/oauth2callback/"
    elif '127.0.0.1' in redirect_uri:
        redirect_uri = "http://127.0.0.1:8000/oauth2callback/"
    else:
        redirect_uri = "http://localhost:8000/oauth2callback/"

    # Usamos from_client_config pasando el diccionario armado en lugar del .json
    client_config = obtener_configuracion_cliente()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    # force para que pida inicio de sesion (conveniente en periodo de dev) 
    # offline para obtener el refresh_token importante para sesiones a largo plazo
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    # Guardamos el estado y el code_verifier temporal para el CSRF y PKCE en el callback
    request.session['state'] = state
    request.session['code_verifier'] = flow.code_verifier
    return authorization_url

def obtener_foto_perfil(credentials):
    """Obtiene la foto de perfil usando el token otorgado."""
    try:
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        return user_info.get('picture')
    except Exception as e:
        print(f"Error obteniendo foto de perfil: {e}")
        return None

def guardar_credenciales_desde_callback(request, usuario):
    """Toma la respuesta de Google y guarda el token asociado al usuario de Django."""
    state = request.session.get('state')
    
    redirect_uri = request.build_absolute_uri(reverse('oauth2callback'))
    if 'planeauml.codeader.com' in redirect_uri:
        redirect_uri = "https://planeauml.codeader.com/oauth2callback/"
    elif '127.0.0.1' in redirect_uri:
        redirect_uri = "http://127.0.0.1:8000/oauth2callback/"
    else:
        redirect_uri = "http://localhost:8000/oauth2callback/"

    client_config = obtener_configuracion_cliente()
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri
    )
    
    # Recuperamos el code verifier de la sesión
    code_verifier = request.session.get('code_verifier')
    if code_verifier:
        flow.code_verifier = code_verifier

    authorization_response = request.build_absolute_uri()
    
    # Obtenemos físicamente el token haciendo el intercambio del authorization codce
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials
    
    # Obtenemos la foto del perfil gracias al scope userinfo
    foto_perfil = obtener_foto_perfil(credentials)

    # Lo guardamos en el modelo CredencialesGoogle
    CredencialesGoogle.objects.update_or_create(
        usuario=usuario,
        defaults={
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': ','.join(credentials.scopes),
            'foto_perfil': foto_perfil
        }
    )
    return True

def obtener_servicio_classroom(usuario):
    """Devuelve el cliente de la API de Classroom listo para ser utilizado."""
    try:
        credenciales_bd = CredencialesGoogle.objects.get(usuario=usuario)
        
        # Reconstruir las credenciales a partir de los atributos extraídos en bbdd
        creds = Credentials(
            token=credenciales_bd.token,
            refresh_token=credenciales_bd.refresh_token,
            token_uri=credenciales_bd.token_uri,
            client_id=credenciales_bd.client_id,
            client_secret=credenciales_bd.client_secret,
            scopes=credenciales_bd.scopes.split(',')
        )

        # Refrescamos si expiró
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
            credenciales_bd.token = creds.token
            credenciales_bd.save()

        # Genera y devuelve el constructor (hook de google client)
        service = build('classroom', 'v1', credentials=creds)
        return service
    except CredencialesGoogle.DoesNotExist:
        return None

def obtener_credenciales_sistema():
    """Devuelve el servicio Classroom utilizando la primera cuenta de administrador vinculada."""
    # Buscar el primer usuario maestro/administrador con credenciales
    credenciales_admin = CredencialesGoogle.objects.filter(
        usuario__is_staff=True
    ).first()

    if not credenciales_admin:
        # Fallback: si no hay staff, buscar el primer superusuario
        credenciales_admin = CredencialesGoogle.objects.filter(
            usuario__is_superuser=True
        ).first()

    if not credenciales_admin:
        return None

    return obtener_servicio_classroom(credenciales_admin.usuario)


def crear_clase_e_invitar_maestro(asignacion):
    """
    Crea una clase en Google Classroom para una AsignacionPlanEstudio 
    y envía una invitación al maestro asignado.
    """
    servicio = obtener_credenciales_sistema()
    if not servicio:
        print("No se encontraron credenciales del sistema para crear la clase en Google Classroom.")
        return False, "No hay credenciales del sistema vinculadas."

    plan = asignacion.plan_de_estudio
    maestro = asignacion.usuario

    # Construir el nombre y sección de la clase
    nombre_clase = plan.asignatura.nombre
    seccion = f"{plan.carrera.nombre} | {plan.año} | Trimestre {plan.trimestre}"

    course_data = {
        'name': nombre_clase,
        'section': seccion,
        'descriptionHeading': 'Clase generada automáticamente por PLANEAUML',
        'room': asignacion.bloque if asignacion.bloque else '',
        'ownerId': 'me',
        'courseState': 'PROVISIONED' # La clase se crea en estado 'PROVISIONED' (inactiva) o 'ACTIVE'
    }

    try:
        # 1. Crear el curso
        nuevo_curso = servicio.courses().create(body=course_data).execute()
        curso_id = nuevo_curso.get('id')
        curso_url = nuevo_curso.get('alternateLink')

        # Guardar en el modelo AsignacionPlanEstudio
        asignacion.curso_classroom_id = curso_id
        asignacion.curso_classroom_url = curso_url
        asignacion.save()

        # 2. Invitar al maestro como profesor colaborador (si no es el mismo owner)
        if maestro.email:
            try:
                invitation_data = {
                    'userId': maestro.email,
                    'courseId': curso_id,
                    'role': 'TEACHER'
                }
                servicio.invitations().create(body=invitation_data).execute()
            except Exception as inv_err:
                # Si el usuario ya es profesor (ej. es el dueño del curso), ignorar el error
                if "already has the course role" in str(inv_err) or "TeacherRoleAlreadyAdded" in str(inv_err):
                    print(f"El usuario {maestro.email} ya es profesor del curso.")
                else:
                    print(f"Error invitando al maestro: {inv_err}")
        
        return True, "Clase creada e invitación procesada."

    except Exception as e:
        print(f"Error creando clase en Classroom: {e}")
        return False, str(e)


def subir_tareas_desde_guia(guia):
    """
    Sube las tareas de una Guía de Estudio Independiente a la clase de Google Classroom.
    """
    asignacion = guia.silabo.asignacion_plan
    curso_id = asignacion.curso_classroom_id

    if not curso_id:
        print("La asignación no tiene un curso de Google Classroom asociado.")
        return False, "La asignación no tiene un curso asociado."

    # Intentamos primero con las credenciales del maestro. 
    # Si no tiene, usamos las del sistema.
    servicio = obtener_servicio_classroom(asignacion.usuario)
    if not servicio:
        servicio = obtener_credenciales_sistema()
        
    if not servicio:
        return False, "No hay credenciales válidas para interactuar con Google Classroom."

    def crear_tarea(num_tarea, titulo, descripcion, puntaje):
        if not titulo or not descripcion:
            return None
        
        # Limitar longitud si existiese validación y setear default
        max_points = int(puntaje) if puntaje else 100

        work_data = {
            'title': f"Actividad {num_tarea} - {titulo.strip()[:60]}...",
            'description': f"{descripcion}\n\nVer plataforma PLANEAUML para detalles de evaluación y rúbrica.",
            'state': 'PUBLISHED',
            'workType': 'ASSIGNMENT',
            'maxPoints': max_points
        }

        try:
            tarea_creada = servicio.courses().courseWork().create(
                courseId=curso_id,
                body=work_data
            ).execute()
            print(f"Tarea {num_tarea} creada exitosamente: {tarea_creada.get('id')}")
            return tarea_creada
        except Exception as e:
            print(f"Error creando tarea {num_tarea}: {e}")
            return None

    tareas_creadas = []
    
    # Evaluar las 4 tareas de la guía
    # Tarea 1
    if guia.actividad_aprendizaje_1:
         crear_tarea(
            num_tarea=1, 
            titulo=guia.objetivo_aprendizaje_1 or "Actividad de la Guía",
            descripcion=guia.actividad_aprendizaje_1,
            puntaje=guia.puntaje_1
        )
    
    # Tarea 2
    if guia.actividad_aprendizaje_2:
         crear_tarea(
            num_tarea=2, 
            titulo=guia.objetivo_aprendizaje_2 or "Actividad de la Guía",
            descripcion=guia.actividad_aprendizaje_2,
            puntaje=guia.puntaje_2
        )

    # Tarea 3
    if guia.actividad_aprendizaje_3:
         crear_tarea(
            num_tarea=3, 
            titulo=guia.objetivo_aprendizaje_3 or "Actividad de la Guía",
            descripcion=guia.actividad_aprendizaje_3,
            puntaje=guia.puntaje_3
        )

    # Tarea 4
    if guia.actividad_aprendizaje_4:
         crear_tarea(
            num_tarea=4, 
            titulo=guia.objetivo_aprendizaje_4 or "Actividad de la Guía",
            descripcion=guia.actividad_aprendizaje_4,
            puntaje=guia.puntaje_4
        )

    return True, "Tareas subidas a Google Classroom."
