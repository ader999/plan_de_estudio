import json
import os
import re
from dotenv import load_dotenv
import logging
import datetime  # Añadido para usar datetime.now()
import traceback  # Añadido para mejor manejo de errores

from django.db.models.functions import Lower
from django.http import HttpResponse, request ,HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
import logging

#librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo, Guia, AsignacionPlanEstudio, Asignatura, Plan_de_estudio

from .forms import SilaboForm
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from django.urls import reverse

# Importaciones para IA
import openai  # Importar openai directamente, sin la clase OpenAI
import google.generativeai as genai
import httpx

# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_GENERATIVE_API_KEY"))

@login_required
def detalle_silabo(request):
    # Recupera todos los objetos Silabo con sus guías relacionadas
    silabos = Silabo.objects.all().prefetch_related('guias')
    
    # Agrupar sílabos por código de asignatura
    silabos_agrupados = {}
    
    for silabo in silabos:
        codigo = silabo.asignacion.codigo
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []
        
        silabos_agrupados[codigo].append(silabo)
    
    # Añadir información adicional a cada grupo
    for codigo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)
        
        # Añadir nombre de asignatura como atributo del grupo
        if grupo:
            grupo.asignatura = grupo[0].asignacion.nombre
    
    return render(request, 'plan_estudio_template/detalle_silabo.html', {'silabos_agrupados': silabos_agrupados})



@login_required
def inicio(request):
    nombre_de_usuario = request.user.username
    # Ajusta el filtro al campo correspondiente en AsignacionPlanEstudio para el usuario
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario__username=nombre_de_usuario)
    rango = range(1, 13)  # Crear el rango para pasarlo al template

    return render(request, 'inicio.html', {'asignaciones': asignaciones, 'rango': rango, 'usuario': nombre_de_usuario})



def acerca_de(request):
    nombre_de_usuario = request.user.username
    return  render(request, 'acerca_de.html',{'usuario':nombre_de_usuario})


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Inicio de sesión exitoso.')
            return redirect('inicio')  # Cambia 'profile' por la URL deseada después del inicio de sesión
        else:
            messages.error(request, 'Credenciales incorrectas. Por favor, intenta de nuevo.')
    else:  # Si la solicitud es GET, muestra el formulario
        return render(request, 'login.html')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')  # Cambia 'login' por la URL de tu página de inicio de sesión



@login_required
def plan_estudio(request):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.username
    # Filtra los silabos del maestro autenticado
    silabos = Silabo.objects.filter(maestro=usuario_autenticado)

    # Crear un diccionario para agrupar los silabos por código
    silabos_agrupados = {}
    for silabo in silabos:
        codigo = silabo.codigo
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []
        silabos_agrupados[codigo].append(silabo)

    context = {
        'silabos_agrupados': silabos_agrupados,
        'usuario': nombre_de_usuario
    }

    return render(request, 'plan_estudio.html', context)


@login_required
def Plan_de_clase(request):
    return render(request, 'plan_estudio_template/detalle_plandeclase.html')




@login_required
def generar_excel(request):
    from .document_generators import generar_excel as generate_excel_file
    return generate_excel_file(request)


@login_required
def generar_excel_original(request):
    from .document_generators import generar_excel_original as generate_excel_original_file
    return generate_excel_original_file(request)


@login_required
def generar_docx(request):
    from .document_generators import generar_docx as generate_docx_file
    return generate_docx_file(request)


@login_required
def success_view(request):
    return render(request, 'exito.html', {
        'message': '¡Gracias por llenar el silabo! Apreciamos el tiempo que has dedicado a completarlo.',
        'usuario': request.user.username,
    })



def obtener_estudios_independientes(asignacion_id):
    """
    Función para obtener todas las guías de estudio independiente asociadas a una asignación.
    
    Args:
        asignacion_id (int): ID de la asignación de plan de estudio
        
    Returns:
        QuerySet: Conjunto de guías de estudio independiente relacionadas con la asignación
    """
    # Primero obtenemos los sílabos relacionados con esta asignación
    silabos = Silabo.objects.filter(asignacion_plan_id=asignacion_id)
    
    # Luego obtenemos todas las guías asociadas a estos sílabos
    guias = Guia.objects.filter(silabo__in=silabos)
    
    return guias


@login_required
def ver_formulario_silabo(request, asignacion_id=None, id=None):
    """
    Función para mostrar el formulario de sílabo.
    Maneja la operación de mostrar el formulario para crear un sílabo.
    """
    if asignacion_id or id:
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)
        nombre_de_usuario = request.user.username
        silabos_creados = asignacion.silabo_set.count()

        form = SilaboForm(initial={
            'codigo': asignacion.plan_de_estudio.codigo,
            'carrera': asignacion.plan_de_estudio.carrera,
            'asignatura': asignacion.plan_de_estudio,  # Asignar el plan de estudio como asignatura
            'maestro': request.user,
            'encuentros': silabos_creados + 1,
        })

        asignaturas = Asignatura.objects.all()

        return render(request, 'formulario_silabo.html', {
            'form': form,
            'asignacion': asignacion,
            'usuario': nombre_de_usuario,
            'silabos_creados': silabos_creados,
            'encuentro': silabos_creados + 1,
            'asignaturas': asignaturas,
        })
    
    # Caso de error: falta asignacion_id
    return JsonResponse({'error': 'Falta ID de asignación'}, status=400)

@login_required
def ver_formulario_guia(request, asignacion_id=None, id=None, silabo_id=None):
    """
    Función para mostrar el formulario de guía de estudio independiente.
    Maneja la operación de mostrar el formulario para crear una guía.
    """
    print(f"Entrando a ver_formulario_guia con asignacion_id={asignacion_id}, id={id}, silabo_id={silabo_id}")
    
    if asignacion_id or id:
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)
        nombre_de_usuario = request.user.username
        silabos_creados = asignacion.silabo_set.count()
        
        print(f"Asignación encontrada: {asignacion}, Sílabos creados: {silabos_creados}")
        
        # Obtener el sílabo correspondiente al encuentro actual
        # Primero intentamos encontrar si ya existe un sílabo para este encuentro
        silabo = None
        if silabo_id:
            try:
                silabo = Silabo.objects.get(id=silabo_id)
                print(f"Sílabo encontrado por silabo_id {silabo_id}: {silabo}")
                # No necesitamos acceder a asignacion para guardar la guía
                # Lo que necesitamos es el sílabo, que ya tenemos
                print(f"Sílabo ID: {silabo.id}")
            except Silabo.DoesNotExist:
                print(f"No se encontró sílabo con ID {silabo_id}")
        
        # Si no tenemos sílabo por ID, buscar por asignación y encuentro
        if not silabo:
            silabo = Silabo.objects.filter(
                asignacion_plan=asignacion,
                encuentros=silabos_creados + 1
            ).first()
            if silabo:
                print(f"Sílabo encontrado para el encuentro {silabos_creados + 1}: {silabo}")
            else:
                print(f"No se encontró sílabo para el encuentro {silabos_creados + 1}")
        
        # Si todavía no tenemos sílabo, intentar obtener el último
        if not silabo and silabos_creados > 0:
            silabo = Silabo.objects.filter(
                asignacion_plan=asignacion
            ).order_by('-encuentros').first()
            if silabo:
                print(f"Último sílabo encontrado: {silabo}")
            else:
                print("No se encontró ningún sílabo para esta asignación")
        
        # Si aún no hay sílabo, verificar si necesitamos crear uno
        if not silabo:
            print("No se encontró ningún sílabo. Se pasará 'silabo=None' a la plantilla.")
            # No creamos un sílabo aquí para evitar efectos secundarios,
            # solo pasamos None a la plantilla
        
        # Obtener las guías existentes para esta asignación
        guias = obtener_estudios_independientes(asignacion.id)
        
        # Obtener las opciones para los campos de selección desde el modelo Silabo
        unidad_choices = Silabo.UNIDAD_LIST
        tecnica_evaluacion_choices = Silabo.TECNICA_EVALUACION_LIST
        tipo_evaluacion_choices = Silabo.TIPO_EVALUACION_LIST
        instrumento_evaluacion_choices = Silabo.INSTRUMENTO_EVALUACION_LIST
        agente_evaluador_choices = Silabo.AGENTE_EVALUADOR_LIST
        periodo_tiempo_choices = Silabo.PERIODO_TIEMPO_LIST
        tipo_objetivo_choices = Guia.TIPO_OBJETIVO_LIST

        return render(request, 'formulario_estudio_independiente.html', {
            'asignacion': asignacion,
            'silabo': silabo,  # Pasar el sílabo a la plantilla
            'usuario': nombre_de_usuario,
            'silabos_creados': silabos_creados,
            'encuentro': silabos_creados + 1,
            'guias': guias,
            'unidad_choices': unidad_choices,
            'tecnica_evaluacion_choices': tecnica_evaluacion_choices,
            'tipo_evaluacion_choices': tipo_evaluacion_choices,
            'instrumento_evaluacion_choices': instrumento_evaluacion_choices,
            'agente_evaluador_choices': agente_evaluador_choices,
            'periodo_tiempo_choices': periodo_tiempo_choices,
            'tipo_objetivo_choices': tipo_objetivo_choices,
        })
    
    # Caso de error: falta asignacion_id
    return JsonResponse({'error': 'Falta ID de asignación'}, status=400)

@login_required
def guardar_silabo(request, asignacion_id=None, id=None):
    """
    Función para guardar sílabos.
    Maneja la operación de guardar un nuevo sílabo (método POST con form data).
    """
    if request.method == 'POST':
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)
        
        # Procesar el formulario de sílabo
        form = SilaboForm(request.POST)
        if form.is_valid():
            silabo = form.save(commit=False)
            silabo.asignacion_plan = asignacion  # Corregido: asignacion_plan en lugar de asignacion
            silabo.save()
            
            # Incrementar contador de sílabos creados
            asignacion.silabos_creados += 1
            asignacion.save()
            
            messages.success(request, 'Sílabo guardado correctamente.')
            return JsonResponse({
                'success': True, 
                'silabo_id': silabo.id,
                'redirect_url': reverse('success_view')
            })
        else:
            errors = {field: error[0] for field, error in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)
    
    # Caso de error: método no permitido
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def guardar_guia(request, silabo_id=None, asignacion_id=None, id=None):
    """
    Función para guardar guías de estudio independiente.
    Maneja la operación de agregar una guía de estudio independiente (método POST con JSON data).
    """
    print(f"Entrando a guardar_guia con silabo_id={silabo_id}")
    
    if request.method == 'POST':
        try:
            # Obtener los datos JSON del cuerpo de la solicitud
            data = json.loads(request.body)
            print(f"Datos recibidos: {data}")
            
            # Si no recibimos silabo_id como parámetro, intentamos obtenerlo de los datos
            if not silabo_id:
                silabo_id = data.get('silabo_id')
                print(f"Usando silabo_id de los datos del formulario: {silabo_id}")
            
            # Necesitamos un silabo_id válido
            if not silabo_id:
                error_msg = 'No se proporcionó un ID de sílabo válido'
                print(error_msg)
                return JsonResponse({'error': error_msg}, status=400)
            
            # Obtener el sílabo directamente por su ID
            try:
                silabo = Silabo.objects.get(id=silabo_id)
                print(f"Sílabo encontrado: {silabo}")
            except Silabo.DoesNotExist:
                error_msg = f'No se encontró el sílabo con ID {silabo_id}'
                print(error_msg)
                return JsonResponse({'error': error_msg}, status=404)
            except Exception as e:
                error_msg = f'Error al obtener el sílabo: {str(e)}'
                print(error_msg)
                return JsonResponse({'error': error_msg}, status=500)
            
            # Crear o actualizar la guía
            guia_id = data.get('guia_id')
            if guia_id:
                # Actualizar guía existente
                guia = get_object_or_404(Guia, id=guia_id)
            else:
                # Crear nueva guía
                guia = Guia()
            
            # Asignar los valores de los campos
            guia.silabo = silabo
            guia.numero_guia = data.get('numero_encuentro', silabo.encuentros)
            guia.numero_encuentro = data.get('numero_encuentro', silabo.encuentros)
            guia.fecha = data.get('fecha')
            guia.unidad = data.get('unidad')
            guia.nombre_de_la_unidad = data.get('nombre_de_la_unidad')
            
            # Tarea 1
            guia.tipo_objetivo_1 = data.get('tipo_objetivo_1')
            guia.objetivo_aprendizaje_1 = data.get('objetivo_aprendizaje_1')
            guia.contenido_tematico_1 = data.get('contenido_tematico_1')
            guia.actividad_aprendizaje_1 = data.get('actividad_aprendizaje_1')
            guia.tecnica_evaluacion_1 = data.get('tecnica_evaluacion_1')
            guia.tipo_evaluacion_1 = data.get('tipo_evaluacion_1')
            guia.instrumento_evaluacion_1 = data.get('instrumento_evaluacion_1')
            guia.criterios_evaluacion_1 = data.get('criterios_evaluacion_1')
            guia.agente_evaluador_1 = data.get('agente_evaluador_1')
            guia.tiempo_minutos_1 = data.get('tiempo_minutos_1')
            guia.recursos_didacticos_1 = data.get('recursos_didacticos_1')
            guia.periodo_tiempo_programado_1 = data.get('periodo_tiempo_programado_1')
            guia.puntaje_1 = data.get('puntaje_1')
            guia.fecha_entrega_1 = data.get('fecha_entrega_1')
            
            # Tarea 2
            guia.tipo_objetivo_2 = data.get('tipo_objetivo_2')
            guia.objetivo_aprendizaje_2 = data.get('objetivo_aprendizaje_2')
            guia.contenido_tematico_2 = data.get('contenido_tematico_2')
            guia.actividad_aprendizaje_2 = data.get('actividad_aprendizaje_2')
            guia.tecnica_evaluacion_2 = data.get('tecnica_evaluacion_2')
            guia.tipo_evaluacion_2 = data.get('tipo_evaluacion_2')
            guia.instrumento_evaluacion_2 = data.get('instrumento_evaluacion_2')
            guia.criterios_evaluacion_2 = data.get('criterios_evaluacion_2')
            guia.agente_evaluador_2 = data.get('agente_evaluador_2')
            guia.tiempo_minutos_2 = data.get('tiempo_minutos_2')
            guia.recursos_didacticos_2 = data.get('recursos_didacticos_2')
            guia.periodo_tiempo_programado_2 = data.get('periodo_tiempo_programado_2')
            guia.puntaje_2 = data.get('puntaje_2')
            guia.fecha_entrega_2 = data.get('fecha_entrega_2')
            
            # Tarea 3
            guia.tipo_objetivo_3 = data.get('tipo_objetivo_3')
            guia.objetivo_aprendizaje_3 = data.get('objetivo_aprendizaje_3')
            guia.contenido_tematico_3 = data.get('contenido_tematico_3')
            guia.actividad_aprendizaje_3 = data.get('actividad_aprendizaje_3')
            guia.tecnica_evaluacion_3 = data.get('tecnica_evaluacion_3')
            guia.tipo_evaluacion_3 = data.get('tipo_evaluacion_3')
            guia.instrumento_evaluacion_3 = data.get('instrumento_evaluacion_3')
            guia.criterios_evaluacion_3 = data.get('criterios_evaluacion_3')
            guia.agente_evaluador_3 = data.get('agente_evaluador_3')
            guia.tiempo_minutos_3 = data.get('tiempo_minutos_3')
            guia.recursos_didacticos_3 = data.get('recursos_didacticos_3')
            guia.periodo_tiempo_programado_3 = data.get('periodo_tiempo_programado_3')
            guia.puntaje_3 = data.get('puntaje_3')
            guia.fecha_entrega_3 = data.get('fecha_entrega_3')
            
            # Tarea 4
            guia.tipo_objetivo_4 = data.get('tipo_objetivo_4')
            guia.objetivo_aprendizaje_4 = data.get('objetivo_aprendizaje_4')
            guia.contenido_tematico_4 = data.get('contenido_tematico_4')
            guia.actividad_aprendizaje_4 = data.get('actividad_aprendizaje_4')
            guia.tecnica_evaluacion_4 = data.get('tecnica_evaluacion_4')
            guia.tipo_evaluacion_4 = data.get('tipo_evaluacion_4')
            guia.instrumento_evaluacion_4 = data.get('instrumento_evaluacion_4')
            guia.criterios_evaluacion_4 = data.get('criterios_evaluacion_4')
            guia.agente_evaluador_4 = data.get('agente_evaluador_4')
            guia.tiempo_minutos_4 = data.get('tiempo_minutos_4')
            guia.recursos_didacticos_4 = data.get('recursos_didacticos_4')
            guia.periodo_tiempo_programado_4 = data.get('periodo_tiempo_programado_4')
            guia.puntaje_4 = data.get('puntaje_4')
            guia.fecha_entrega_4 = data.get('fecha_entrega_4')
            
            # Guardar la guía
            guia.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Guía guardada correctamente',
                'guia_id': guia.id
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Formato JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # Caso de error: método no permitido
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def generar_silabo(request):
    """
    Función para generar un sílabo usando modelos de IA.
    """
    from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
    import json
    from django.db.models import Q
    from plan_de_estudio.models import AsignacionPlanEstudio, Silabo, PlanTematico

    if request.method == 'POST':
        # Obtener los datos del formulario
        encuentro = request.POST.get('encuentro')
        plan_id = request.POST.get('plan')
        # Obtener el modelo seleccionado del formulario
        modelo_seleccionado = request.POST.get('modelo', 'google')
        print("Imprimiendo el modelo selecionodao:::::::::::::::::: "+str(modelo_seleccionado))
        
        try:
            # Convertir a entero para asegurar que es un número válido
            encuentro = int(encuentro)
            if encuentro < 1 or encuentro > 12:
                return JsonResponse({'error': 'El número de encuentro debe estar entre 1 y 12'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'El número de encuentro debe ser un número válido'}, status=400)
            
        try:
            # Obtener la asignación del plan de estudio
            asignacion = AsignacionPlanEstudio.objects.get(id=plan_id)
            
            # Obtener el plan temático relacionado
            plan_tematico = PlanTematico.objects.filter(plan_estudio=asignacion.plan_de_estudio).first()
            if not plan_tematico:
                return JsonResponse({'error': 'No se encontró un plan temático para esta asignación'}, status=400)
                
            # Obtener los sílabos ya generados para esta asignación
            silabos_existentes = Silabo.objects.filter(asignacion_plan=asignacion).order_by('encuentros')
            
            # Convertir los sílabos existentes a un formato que podamos usar en el prompt
            silabos_previos = []
            for silabo in silabos_existentes:
                if silabo.encuentros < encuentro:  # Solo considerar los encuentros previos
                    silabo_dict = {
                        'encuentro': silabo.encuentros,
                        'unidad': silabo.unidad,
                        'nombre_de_la_unidad': silabo.nombre_de_la_unidad,
                        'contenido_tematico': silabo.contenido_tematico,
                        'objetivo_conceptual': silabo.objetivo_conceptual,
                        'objetivo_procedimental': silabo.objetivo_procedimental,
                        'objetivo_actitudinal': silabo.objetivo_actitudinal
                    }
                    silabos_previos.append(silabo_dict)
            
            # Verificar si ya existe un sílabo para este encuentro
            silabo_actual = Silabo.objects.filter(asignacion_plan=asignacion, encuentros=encuentro).first()
            if silabo_actual:
                return JsonResponse({'error': f'Ya existe un sílabo para el encuentro {encuentro}'}, status=400)
                
        except AsignacionPlanEstudio.DoesNotExist:
            return JsonResponse({'error': 'No se encontró el plan de estudio especificado'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error al obtener datos del plan: {str(e)}'}, status=400)
        
        # Ruta al archivo de datos JSON con la estructura
        json_filepath = os.path.join(settings.BASE_DIR, 'static', 'data', 'datos.json')

        try:
            with open(json_filepath, 'r', encoding='utf-8') as json_file:
                datos_estructura = json.load(json_file)
                
            # Obtener la estructura del primer encuentro como ejemplo
            primer_encuentro = datos_estructura.get('primer_encuentro', {})
            # Obtener las listas de opciones
            unidades = datos_estructura.get('unidades', [])
            ejes_transversales = datos_estructura.get('ejes_transversales', [])
            tipos_primer_momento = datos_estructura.get('tipos_primer_momento', [])
            tipos_segundo_momento_teoria = datos_estructura.get('tipos_segundo_momento_teoria', [])
            tipos_segundo_momento_practica = datos_estructura.get('tipos_segundo_momento_practica', [])
            tipos_tercer_momento = datos_estructura.get('tipos_tercer_momento', [])
            
        except Exception as e:
            return JsonResponse({'error': f"Error al cargar el archivo de estructura JSON: {str(e)}"}, status=400)

        # Crear el prompt completo
        prompt_completo = f"""
            Instrucciones: Crea un sílabo basado en la siguiente información y devuélvelo en formato JSON estructurado.

            Estás creando el sílabo para el encuentro {encuentro} de 12 encuentros.
            Plan de estudio: {str(asignacion.plan_de_estudio)}
            Asignatura: {asignacion.plan_de_estudio.asignatura.nombre}
            
            INFORMACIÓN DEL PLAN TEMÁTICO:
            Unidad: {plan_tematico.unidades}
            Nombre de la unidad: {plan_tematico.nombre_de_la_unidad}
            Objetivos específicos: {plan_tematico.objetivo_especificos}
            Plan analítico: {plan_tematico.plan_analitico}
            Recomendaciones metodológicas: {plan_tematico.recomendaciones_metodologicas}
            
            CONTENIDO TEMÁTICO COMPLETO:
            {plan_tematico.plan_analitico}
            
            {"SÍLABOS PREVIOS YA GENERADOS:" if silabos_previos else "Este es el primer encuentro, no hay sílabos previos."}
            {json.dumps(silabos_previos, indent=2, ensure_ascii=False) if silabos_previos else ""}

            Utiliza la siguiente estructura de datos y opciones disponibles:

            UNIDADES DISPONIBLES:
            {', '.join(unidades)}

            EJES TRANSVERSALES DISPONIBLES:
            {', '.join(ejes_transversales)}

            TIPOS DE PRIMER MOMENTO DIDÁCTICO:
            {', '.join(tipos_primer_momento)}

            TIPOS DE SEGUNDO MOMENTO DIDÁCTICO (TEORÍA):
            {', '.join(tipos_segundo_momento_teoria)}

            TIPOS DE SEGUNDO MOMENTO DIDÁCTICO (PRÁCTICA):
            {', '.join(tipos_segundo_momento_practica)}

            TIPOS DE TERCER MOMENTO DIDÁCTICO:
            {', '.join(tipos_tercer_momento)}

            EJEMPLO DE ESTRUCTURA (primer encuentro):
            ```
            {json.dumps(primer_encuentro, indent=2, ensure_ascii=False)}
            ```

            INSTRUCCIONES ESPECÍFICAS:
            1. Divide el contenido temático completo en 12 encuentros de manera coherente y progresiva.
            2. Para el encuentro {encuentro}, selecciona la parte correspondiente del contenido temático.
            3. NO repitas contenido que ya se ha cubierto en encuentros anteriores.
            4. Si es el primer encuentro, comienza con una introducción general.
            5. Si hay encuentros previos, continúa desde donde se quedaron.
            6. Asegúrate de que haya una progresión lógica entre los encuentros.
            7. Adapta los objetivos y actividades al contenido específico de este encuentro.
            8. Usa la misma estructura JSON que el ejemplo proporcionado.

            Devuelve los datos como un diccionario JSON con la misma estructura que el ejemplo anterior,
            pero adaptado al encuentro {encuentro} y al plan de estudio proporcionado.
            
            Asegúrate de que todos los campos tengan valores coherentes y apropiados para el encuentro {encuentro}.
            Respeta las opciones disponibles para los campos que tienen listas predefinidas.
        """
        print("1111111111111111111111111111111111111111111111111", prompt_completo)
        
        try:
            # Configurar parámetros específicos para el modelo seleccionado
            config = get_default_config(modelo_seleccionado)
            
            # Generar respuesta usando la función centralizada
            data = generar_respuesta_ai(prompt_completo, modelo_seleccionado, **config)
            
            # Devolver la respuesta
            return JsonResponse({'silabo_data': data})
            
        except Exception as e:
            error_msg = f'Error inesperado: {str(e)}'
            logging.error(error_msg)
            return JsonResponse({'error': error_msg}, status=500)
        
@login_required
def generar_estudio_independiente(request):
    """
    Vista para generar una guía de estudio utilizando IA.
    """
    from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
    import traceback
    import logging
    
    if request.method == 'POST':
        silabo_id = request.POST.get('silabo_id')
        asignacion_id = request.POST.get('asignacion_id')
        encuentro = int(request.POST.get('encuentro', 1))  # Por defecto, primer encuentro
        modelo_seleccionado = request.POST.get('modelo')
        
        print(f"Recibida solicitud para generar guía de estudio. Sílabo ID: {silabo_id}, Asignación ID: {asignacion_id}, Encuentro: {encuentro}, Modelo: {modelo_seleccionado}")
        
        # Log all POST parameters for debugging
        print(f"POST parameters: {request.POST}")

        try:
            # Obtener el sílabo actual
            silabo = None
            asignacion = None
            
            # 1. Primero intentar obtener por silabo_id directo
            if silabo_id and silabo_id != "null" and silabo_id != "":
                try:
                    silabo = Silabo.objects.get(id=silabo_id)
                    print(f"Sílabo encontrado por silabo_id {silabo_id}: {silabo}")
                    asignacion = silabo.asignacion_plan
                except Silabo.DoesNotExist:
                    print(f"No se encontró sílabo con ID {silabo_id}")
            
            # 2. Si no hay silabo pero sí hay asignacion_id, obtener la asignación
            if not silabo and asignacion_id and asignacion_id != "null" and asignacion_id != "":
                try:
                    asignacion = AsignacionPlanEstudio.objects.get(id=asignacion_id)
                    print(f"Asignación encontrada con ID {asignacion_id}: {asignacion}")
                    
                    # 3. Intentar encontrar sílabo por número de encuentro
                    silabo = Silabo.objects.filter(
                        asignacion_plan=asignacion,
                        encuentros=encuentro
                    ).first()
                    
                    if silabo:
                        print(f"Sílabo encontrado para el encuentro {encuentro}: {silabo}")
                    else:
                        print(f"No se encontró sílabo para el encuentro {encuentro}")
                        
                        # 4. Si no se encuentra por encuentro específico, buscar el último
                        silabo = Silabo.objects.filter(
                            asignacion_plan=asignacion
                        ).order_by('-encuentros').first()
                        
                        if silabo:
                            print(f"Se usará el último sílabo disponible: {silabo}")
                        else:
                            print(f"No se encontraron sílabos para la asignación {asignacion_id}")
                            return JsonResponse({'error': 'No hay sílabo disponible para esta asignación. Por favor, cree un sílabo primero.'}, status=400)
                            
                except AsignacionPlanEstudio.DoesNotExist:
                    print(f"No se encontró asignación con ID {asignacion_id}")
                    return JsonResponse({'error': f'No se encontró la asignación con ID {asignacion_id}'}, status=400)
            
            if not silabo:
                print("No se pudo encontrar un sílabo después de intentar todas las opciones")
                return JsonResponse({'error': 'No se pudo encontrar un sílabo para generar la guía.'}, status=400)
                
            if not asignacion:
                asignacion = silabo.asignacion_plan
            
            print(f"Usando asignación: {asignacion}, Sílabo: {silabo}")
            
            # Verificar si ya existe una guía para este sílabo
            guia_existente = Guia.objects.filter(silabo=silabo).first()
            if guia_existente:
                print(f"Ya existe una guía para el sílabo {silabo.id} (Encuentro {silabo.encuentros})")
                return JsonResponse({'error': f'Ya existe una guía para este sílabo (Encuentro {silabo.encuentros})'}, status=400)
            
            # Continuar con el resto del código...
            
            # Obtener guías anteriores para otros sílabos de la misma asignación
            guias_anteriores = Guia.objects.filter(
                silabo__asignacion_plan=asignacion,
                silabo__encuentros__lt=silabo.encuentros
            ).order_by('silabo__encuentros')
            
            # Ruta al archivo de datos JSON con la estructura de la guía
            json_filepath = os.path.join(settings.BASE_DIR, 'static', 'data', 'guia_ejemplo.json')

            with open(json_filepath, 'r', encoding='utf-8') as json_file:
                datos_estructura = json.load(json_file)
                
            # Obtener la estructura de ejemplo y las listas de opciones
            ejemplo_guia = datos_estructura.get('ejemplo_guia', {})
            tipos_objetivo = datos_estructura.get('tipos_objetivo', [])
            tecnicas_evaluacion = datos_estructura.get('tecnicas_evaluacion', [])
            tipos_evaluacion = datos_estructura.get('tipos_evaluacion', [])
            instrumentos_evaluacion = datos_estructura.get('instrumentos_evaluacion', [])
            agentes_evaluadores = datos_estructura.get('agentes_evaluadores', [])
            periodos_tiempo = datos_estructura.get('periodos_tiempo', [])
            
            # Convertir las guías anteriores a un formato que podamos usar en el prompt
            guias_previas = []
            for guia in guias_anteriores:
                guia_dict = {
                    'numero_encuentro': guia.numero_encuentro,
                    'fecha': guia.fecha.strftime('%Y-%m-%d') if guia.fecha else None,
                    'unidad': guia.unidad,
                    'nombre_de_la_unidad': guia.nombre_de_la_unidad,
                    # Tarea 1
                    'tipo_objetivo_1': guia.tipo_objetivo_1,
                    'objetivo_aprendizaje_1': guia.objetivo_aprendizaje_1,
                    'contenido_tematico_1': guia.contenido_tematico_1,
                    'actividad_aprendizaje_1': guia.actividad_aprendizaje_1,
                    'tecnica_evaluacion_1': guia.tecnica_evaluacion_1,
                    'tipo_evaluacion_1': guia.tipo_evaluacion_1,
                    'instrumento_evaluacion_1': guia.instrumento_evaluacion_1,
                    'criterios_evaluacion_1': guia.criterios_evaluacion_1,
                    'puntaje_1': guia.puntaje_1
                }
                guias_previas.append(guia_dict)
            
            # Crear el prompt completo
            prompt_completo = f"""
            Instrucciones: Crea una guía de estudio independiente basada en la siguiente información y devuélvela en formato JSON estructurado.

            INFORMACIÓN DEL SÍLABO ACTUAL (Encuentro {silabo.encuentros}):
            - Código: {silabo.codigo}
            - Unidad: {silabo.unidad}
            - Nombre de la unidad: {silabo.nombre_de_la_unidad}
            - Contenido temático: {silabo.contenido_tematico}
            - Objetivo conceptual: {silabo.objetivo_conceptual}
            - Objetivo procedimental: {silabo.objetivo_procedimental}
            - Objetivo actitudinal: {silabo.objetivo_actitudinal}
            - Eje transversal: {silabo.eje_transversal} - {silabo.detalle_eje_transversal}
            
            MOMENTOS DIDÁCTICOS DEL SÍLABO:
            - Primer momento: {silabo.tipo_primer_momento} - {silabo.detalle_primer_momento}
            - Segundo momento (teoría): {silabo.tipo_segundo_momento_claseteoria} - {silabo.clase_teorica}
            - Segundo momento (práctica): {silabo.tipo_segundo_momento_practica} - {silabo.clase_practica}
            - Tercer momento: {silabo.tipo_tercer_momento} - {silabo.detalle_tercer_momento}
            
            EVALUACIÓN DEL SÍLABO:
            - Actividad de aprendizaje: {silabo.actividad_aprendizaje}
            - Técnica de evaluación: {silabo.tecnica_evaluacion}
            - Tipo de evaluación: {silabo.tipo_evaluacion}
            - Instrumento de evaluación: {silabo.instrumento_evaluacion}
            - Criterios de evaluación: {silabo.criterios_evaluacion}
            - Puntaje: {silabo.puntaje}
            
            {"GUÍAS DE ESTUDIO PREVIAS:" if guias_previas else "Esta es la primera guía para esta asignación."}
            {json.dumps(guias_previas, indent=2, ensure_ascii=False) if guias_previas else ""}

            TIPOS DE OBJETIVO DISPONIBLES:
            {', '.join(tipos_objetivo)}

            TÉCNICAS DE EVALUACIÓN DISPONIBLES:
            {', '.join(tecnicas_evaluacion)}

            TIPOS DE EVALUACIÓN DISPONIBLES:
            {', '.join(tipos_evaluacion)}

            INSTRUMENTOS DE EVALUACIÓN DISPONIBLES:
            {', '.join(instrumentos_evaluacion)}

            AGENTES EVALUADORES DISPONIBLES:
            {', '.join(agentes_evaluadores)}

            PERIODOS DE TIEMPO DISPONIBLES:
            {', '.join(periodos_tiempo)}

            EJEMPLO DE ESTRUCTURA DE GUÍA:
            ```
            {json.dumps(ejemplo_guia, indent=2, ensure_ascii=False)}
            ```

            INSTRUCCIONES ESPECÍFICAS:
            1. Crea una guía de estudio independiente para el encuentro {silabo.encuentros} basada en el sílabo proporcionado.
            2. La guía debe tener 4 tareas diferentes que el estudiante debe realizar como trabajo independiente.
            3. Cada tarea debe estar relacionada con el contenido temático y los objetivos del sílabo.
            4. Las tareas deben ser progresivas y complementarias entre sí.
            5. Asigna fechas de entrega realistas (considera que la fecha actual es {datetime.datetime.now().strftime('%Y-%m-%d')}).
            6. Distribuye el puntaje total entre las 4 tareas (el total debe sumar 100 puntos).
            7. Utiliza diferentes tipos de objetivos, técnicas e instrumentos de evaluación para las tareas.
            8. NO repitas actividades que ya se hayan asignado en guías anteriores.
            9. Sigue exactamente la misma estructura JSON que el ejemplo proporcionado.

            Devuelve los datos como un diccionario JSON con la misma estructura que el ejemplo anterior,
            adaptado al sílabo actual (encuentro {silabo.encuentros}).
            
            Asegúrate de que todos los campos tengan valores coherentes y apropiados.
            Respeta las opciones disponibles para los campos que tienen listas predefinidas.
            """
            
            print("Prompt generado, enviando a la API...")
            logging.info("Prompt generado, enviando a la API...")
            
            # Configurar parámetros específicos para el modelo seleccionado
            config = get_default_config(modelo_seleccionado)
            
            # Generar respuesta usando la función centralizada
            data = generar_respuesta_ai(prompt_completo, modelo_seleccionado, **config)
            
            # Devolver la respuesta con la estructura que espera el frontend
            return JsonResponse({
                'success': True,
                'datos': data
            })
            
        except Silabo.DoesNotExist:
            return JsonResponse({'error': 'No se encontró el sílabo especificado'}, status=400)
        except Exception as e:
            error_message = f"Error inesperado: {str(e)}"
            logging.error(error_message)
            print(error_message)
            return JsonResponse({'error': error_message}, status=500)
   
@login_required
def cargar_guia(request, silabo_id):
    """
    Vista para cargar una guía específica de un sílabo mediante AJAX.
    """
    try:
        # Obtener el sílabo específico
        silabo = Silabo.objects.get(id=silabo_id)
        
        # Información de debugging inicial
        debug_info = {
            'silabo_id': silabo_id,
            'silabo_encuentro': silabo.encuentros,
            'asignatura': silabo.asignatura.asignatura if hasattr(silabo, 'asignatura') and silabo.asignatura else 'No asignada'
        }
        
        print(f"DEBUG INFO SILABO: {debug_info}")
        
        # Verificar cuántas guías hay asociadas a este sílabo
        guias_count = Guia.objects.filter(silabo_id=silabo_id).count()
        print(f"Cantidad de guías para el sílabo {silabo_id}: {guias_count}")
        
        if guias_count == 0:
            return render(request, 'plan_estudio_template/detalle_estudioindependiente.html', {
                'silabo': silabo,
                'mensaje_error': 'Este sílabo no tiene guía asociada.',
                'debug_info': debug_info
            })
        elif guias_count > 1:
            # Si hay múltiples guías, tomamos la específica para este encuentro
            # o la primera en su defecto
            print(f"Atención: Se encontraron {guias_count} guías para el sílabo {silabo_id}")
            guias = Guia.objects.filter(silabo_id=silabo_id).order_by('numero_guia')
            for g in guias:
                print(f"Guía ID: {g.id}, Número: {g.numero_guia}, Silabo: {g.silabo_id}")
            
            # Intentamos hacer coincidir la guía con el número de encuentro del sílabo
            try:
                guia = guias.filter(numero_guia=silabo.encuentros).first()
                if not guia:
                    guia = guias.first()  # Si no hay coincidencia, usamos la primera
            except Exception as e:
                print(f"Error al filtrar por encuentro: {str(e)}")
                guia = guias.first()
        else:
            # Si hay exactamente una guía
            guia = Guia.objects.get(silabo_id=silabo_id)
        
        # Información de debugging completa
        debug_info.update({
            'guia_id': guia.id if guia else None,
            'guia_numero': guia.numero_guia if guia else None,
            'total_guias': guias_count
        })
        
        print(f"DEBUG INFO COMPLETO: {debug_info}")
        
        return render(request, 'plan_estudio_template/detalle_estudioindependiente.html', {
            'silabo': silabo,
            'guia': guia,
            'debug_info': debug_info
        })
            
    except Silabo.DoesNotExist:
        return HttpResponse(f"Sílabo no encontrado (ID: {silabo_id})", status=404)
    except Exception as e:
        error_msg = f"Error al cargar la guía: {str(e)} (Sílabo ID: {silabo_id})"
        print(f"ERROR: {error_msg}")
        return HttpResponse(error_msg, status=500)