import json
import os
import re
from dotenv import load_dotenv
import logging
import datetime  # Añadido para usar datetime.now()
import traceback  # Añadido para mejor manejo de errores

from django.db.models.functions import Lower
from django.http import HttpResponse, request, HttpResponseNotFound, JsonResponse
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
import logging
from django.core.exceptions import ValidationError

# librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo, Guia, AsignacionPlanEstudio, Asignatura, Plan_de_estudio

from .forms import SilaboForm
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from django.urls import reverse
from django.core.files.storage import default_storage
# Importaciones para IA
import openai  # Importar openai directamente, sin la clase OpenAI
import google.generativeai as genai
import httpx
from .ai_generators import DateTimeEncoder  # Importar el encoder personalizado

# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_GENERATIVE_API_KEY"))


@login_required
def detalle_silabo(request, codigo=None):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name()

    # Obtener código desde URL o parámetros GET
    if not codigo:
        codigo = request.GET.get('codigo')

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones)

    # Si se especifica un código, filtrar solo por ese código
    if codigo:
        silabos = silabos.filter(asignacion_plan__plan_de_estudio__codigo=codigo)

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Usamos el código del plan de estudio como clave
        codigo_silabo = silabo.asignacion_plan.plan_de_estudio.codigo

        # Si el código no existe en el diccionario, lo creamos
        if codigo_silabo not in silabos_agrupados:
            silabos_agrupados[codigo_silabo] = []

        # Añadimos información útil al silabo para su uso en las plantillas
        silabo.asignatura = silabo.asignacion_plan.plan_de_estudio.asignatura
        silabo.carrera = silabo.asignacion_plan.plan_de_estudio.carrera
        silabo.plan_de_estudio = silabo.asignacion_plan.plan_de_estudio

        # Agregamos el sílabo a la lista correspondiente
        silabos_agrupados[codigo_silabo].append(silabo)

    # Para cada grupo de sílabos, añadimos información adicional
    for codigo_grupo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)

    # Obtener el año actual
    año_actual = datetime.datetime.now().year

    context = {"silabos_agrupados": silabos_agrupados, "usuario": nombre_de_usuario, "año_actual": año_actual}

    return render(request, "detalle_silabo_completo.html", context)


@login_required
def inicio(request):
    nombre_de_usuario = request.user.username
    # Ajusta el filtro al campo correspondiente en AsignacionPlanEstudio para el usuario
    asignaciones = AsignacionPlanEstudio.objects.filter(
        usuario__username=nombre_de_usuario
    )
    rango = range(1, 13)  # Crear el rango para pasarlo al template

    return render(
        request,
        "inicio.html",
        {"asignaciones": asignaciones, "rango": rango, "usuario": nombre_de_usuario},
    )


def acerca_de(request):
    nombre_de_usuario = request.user.username
    return render(request, "acerca_de.html", {"usuario": nombre_de_usuario})


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Inicio de sesión exitoso.")
            return redirect(
                "inicio"
            )  # Cambia 'profile' por la URL deseada después del inicio de sesión
        else:
            messages.error(
                request, " Credenciales incorrectas. Por favor, intenta de nuevo."
            )
    else:  # Si la solicitud es GET, muestra el formulario
        return render(request, "login.html")

    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect(
        "login"
    )  # Cambia 'login' por la URL de tu página de inicio de sesión


@login_required
def plan_estudio(request):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name()

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones)

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Usamos el código del plan de estudio como clave
        codigo = silabo.asignacion_plan.plan_de_estudio.codigo

        # Si el código no existe en el diccionario, lo creamos
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []

        # Añadimos información útil al silabo para su uso en las plantillas
        silabo.asignatura = silabo.asignacion_plan.plan_de_estudio.asignatura
        silabo.carrera = silabo.asignacion_plan.plan_de_estudio.carrera
        silabo.plan_de_estudio = silabo.asignacion_plan.plan_de_estudio

        # Agregamos el sílabo a la lista correspondiente
        silabos_agrupados[codigo].append(silabo)

    # Para cada grupo de sílabos, añadimos información adicional
    for codigo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)

    # Obtener el año actual
    año_actual = datetime.datetime.now().year

    context = {
        "silabos_agrupados": silabos_agrupados, 
        "usuario": nombre_de_usuario, 
        "año_actual": año_actual,
        "asignaciones": asignaciones
    }

    return render(request, "plan_estudio.html", context)


@login_required
def guia_autodidactica(request, codigo=None):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name()

    # Obtener código desde URL o parámetros GET
    if not codigo:
        codigo = request.GET.get('codigo')

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones)

    # Si se especifica un código, filtrar solo por ese código
    if codigo:
        silabos = silabos.filter(asignacion_plan__plan_de_estudio__codigo=codigo)

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Usamos el código del plan de estudio como clave
        codigo_silabo = silabo.asignacion_plan.plan_de_estudio.codigo

        # Si el código no existe en el diccionario, lo creamos
        if codigo_silabo not in silabos_agrupados:
            silabos_agrupados[codigo_silabo] = []

        # Añadimos información útil al silabo para su uso en las plantillas
        silabo.asignatura = silabo.asignacion_plan.plan_de_estudio.asignatura
        silabo.carrera = silabo.asignacion_plan.plan_de_estudio.carrera
        silabo.plan_de_estudio = silabo.asignacion_plan.plan_de_estudio

        # Agregamos el sílabo a la lista correspondiente
        silabos_agrupados[codigo_silabo].append(silabo)

    # Para cada grupo de sílabos, añadimos información adicional
    for codigo_grupo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)

    # Obtener el año actual
    año_actual = datetime.datetime.now().year

    context = {"silabos_agrupados": silabos_agrupados, "usuario": nombre_de_usuario, "año_actual": año_actual}

    return render(request, "guia_autodidactica_completa.html", context)


import datetime # Ensure datetime is imported

@login_required
def secuencia_didactica(request, codigo=None):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name()
    print(f"[DEBUG] Secuencia Didáctica View - User: {usuario_autenticado.username}")

    # Obtener código desde URL o parámetros GET
    if not codigo:
        codigo = request.GET.get('codigo')
    print(f"[DEBUG] Secuencia Didáctica View - Plan Code (codigo): {codigo}")

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)
    print(f"[DEBUG] Secuencia Didáctica View - Found {asignaciones.count()} asignaciones for user {usuario_autenticado.username}")

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones).prefetch_related('guias')
    print(f"[DEBUG] Secuencia Didáctica View - Found {silabos.count()} silabos initially for user's asignaciones")

    # Si se especifica un código, filtrar solo por ese código
    if codigo:
        silabos = silabos.filter(asignacion_plan__plan_de_estudio__codigo=codigo)
        print(f"[DEBUG] Secuencia Didáctica View - Found {silabos.count()} silabos after filtering by codigo '{codigo}'")
    else:
        print("[DEBUG] Secuencia Didáctica View - No codigo provided, not filtering silabos by plan code.")

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Usamos el código del plan de estudio como clave
        codigo_silabo = silabo.asignacion_plan.plan_de_estudio.codigo

        # Si el código no existe en el diccionario, lo creamos
        if codigo_silabo not in silabos_agrupados:
            silabos_agrupados[codigo_silabo] = []

        # Añadimos información útil al silabo para su uso en las plantillas
        silabo.asignatura = silabo.asignacion_plan.plan_de_estudio.asignatura
        silabo.carrera = silabo.asignacion_plan.plan_de_estudio.carrera
        silabo.plan_de_estudio = silabo.asignacion_plan.plan_de_estudio

        # Agregamos el sílabo a la lista correspondiente
        silabos_agrupados[codigo_silabo].append(silabo)

    # Para cada grupo de sílabos, añadimos información adicional
    for codigo_grupo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)

    # Obtener el año actual
    año_actual = datetime.datetime.now().year

    context = {"silabos_agrupados": silabos_agrupados, "usuario": nombre_de_usuario, "año_actual": año_actual}

    print(f"[DEBUG] Secuencia Didáctica View - Final silabos_agrupados: {silabos_agrupados}")
    print(f"[DEBUG] Secuencia Didáctica View - Context being passed to template: {context}")

    return render(request, "secuencia_didactica_completa.html", context)


@login_required
def Plan_de_clase(request):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.username

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones).prefetch_related(
        "guia"
    )

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Usamos el código del plan de estudio como clave
        codigo = silabo.asignacion_plan.plan_de_estudio.codigo

        # Si el código no existe en el diccionario, lo creamos
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []

        # Añadimos información útil al silabo para su uso en las plantillas
        silabo.asignatura = silabo.asignacion_plan.plan_de_estudio.asignatura
        silabo.carrera = silabo.asignacion_plan.plan_de_estudio.carrera
        silabo.plan_de_estudio = silabo.asignacion_plan.plan_de_estudio

        # Agregar información de depuración
        print(
            f"Sílabo ID: {silabo.id}, Encuentro: {silabo.encuentros}, Guía asociada: {silabo.guia_id if hasattr(silabo, 'guia_id') else 'Ninguna'}"
        )

        # Agregamos el sílabo a la lista correspondiente
        silabos_agrupados[codigo].append(silabo)

    # Para cada grupo de sílabos, añadimos información adicional
    for codigo, grupo in silabos_agrupados.items():
        # Ordenar por número de encuentro
        grupo.sort(key=lambda s: s.encuentros)

    context = {"silabos_agrupados": silabos_agrupados, "usuario": nombre_de_usuario}

    return render(request, "plan_estudio_template/detalle_plandeclase.html", context)




@login_required
def generar_excel_original(request):
    from .document_generators import (
        generar_excel_original as generate_excel_original_file,
    )

    return generate_excel_original_file(request)


@login_required
def generar_docx(request):
    from .document_generators import generar_docx as generate_docx_file

    return generate_docx_file(request)


@login_required
def success_view(request):
    return render(
        request,
        "exito.html",
        {
            "message": "¡Gracias por llenar el formulario! Apreciamos el tiempo que has dedicado a completarlo.",
            "usuario": request.user.username,
        },
    )


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

        form = SilaboForm(
            initial={
                "codigo": asignacion.plan_de_estudio.codigo,
                "carrera": asignacion.plan_de_estudio.carrera,
                "asignatura": asignacion.plan_de_estudio,  # Asignar el plan de estudio como asignatura
                "maestro": request.user,
                "encuentros": silabos_creados + 1,
            }
        )

        asignaturas = Asignatura.objects.all()

        return render(
            request,
            "formulario_silabo.html",
            {
                "form": form,
                "asignacion": asignacion,
                "usuario": nombre_de_usuario,
                "silabos_creados": silabos_creados,
                "encuentro": silabos_creados + 1,
                "asignaturas": asignaturas,
            },
        )

    # Caso de error: falta asignacion_id
    return JsonResponse({"error": "Falta ID de asignación"}, status=400)


@login_required
def ver_formulario_guia(request, asignacion_id=None, id=None, silabo_id=None):
    """
    Función para mostrar el formulario de guía de estudio independiente.
    Maneja la operación de mostrar el formulario para crear una guía.
    """
    print(
        f"Entrando a ver_formulario_guia con asignacion_id={asignacion_id}, id={id}, silabo_id={silabo_id}"
    )

    if asignacion_id or id:
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)
        nombre_de_usuario = request.user.username
        silabos_creados = asignacion.silabo_set.count()

        print(
            f"Asignación encontrada: {asignacion}, Sílabos creados: {silabos_creados}"
        )

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
                asignacion_plan=asignacion, encuentros=silabos_creados + 1
            ).first()
            if silabo:
                print(
                    f"Sílabo encontrado para el encuentro {silabos_creados + 1}: {silabo}"
                )
            else:
                print(f"No se encontró sílabo para el encuentro {silabos_creados + 1}")

        # Si todavía no tenemos sílabo, intentar obtener el último
        if not silabo and silabos_creados > 0:
            silabo = (
                Silabo.objects.filter(asignacion_plan=asignacion)
                .order_by("-encuentros")
                .first()
            )
            if silabo:
                print(f"Último sílabo encontrado: {silabo}")
            else:
                print("No se encontró ningún sílabo para esta asignación")

        # Si aún no hay sílabo, verificar si necesitamos crear uno
        if not silabo:
            print(
                "No se encontró ningún sílabo. Se pasará 'silabo=None' a la plantilla."
            )
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

        return render(
            request,
            "formulario_estudio_independiente.html",
            {
                "asignacion": asignacion,
                "silabo": silabo,  # Pasar el sílabo a la plantilla
                "usuario": nombre_de_usuario,
                "silabos_creados": silabos_creados,
                "encuentro": silabo.encuentros if silabo else silabos_creados + 1,
                "guias": guias,
                "unidad_choices": unidad_choices,
                "tecnica_evaluacion_choices": tecnica_evaluacion_choices,
                "tipo_evaluacion_choices": tipo_evaluacion_choices,
                "instrumento_evaluacion_choices": instrumento_evaluacion_choices,
                "agente_evaluador_choices": agente_evaluador_choices,
                "periodo_tiempo_choices": periodo_tiempo_choices,
                "tipo_objetivo_choices": tipo_objetivo_choices,
            },
        )

    # Caso de error: falta asignacion_id
    return JsonResponse({"error": "Falta ID de asignación"}, status=400)


@login_required
def guardar_silabo(request, asignacion_id=None, id=None):
    """
    Función para guardar sílabos.
    Maneja la operación de guardar un nuevo sílabo (método POST con form data).
    """
    if request.method == "POST":
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)

        # Procesar el formulario de sílabo
        form = SilaboForm(request.POST)
        if form.is_valid():
            silabo = form.save(commit=False)
            silabo.asignacion_plan = (
                asignacion  # Corregido: asignacion_plan en lugar de asignacion
            )
            silabo.save()

            # Incrementar contador de sílabos creados
            asignacion.silabos_creados += 1
            asignacion.save()

            messages.success(request, "Sílabo guardado correctamente.")
            return JsonResponse(
                {
                    "success": True,
                    "silabo_id": silabo.id,
                    "redirect_url": reverse("success_view"),
                }
            )
        else:
            errors = {field: error[0] for field, error in form.errors.items()}
            return JsonResponse({"success": False, "errors": errors}, status=400)

    # Caso de error: método no permitido
    return JsonResponse({"error": "Método no permitido"}, status=405)


@login_required
def guardar_guia(request, silabo_id=None, asignacion_id=None, id=None):
    """
    Función para guardar guías de estudio independiente.
    Maneja la operación de agregar una guía de estudio independiente (método POST con JSON data).
    """
    print(f"Entrando a guardar_guia con silabo_id={silabo_id}")

    if request.method == "POST":
        try:
            # Obtener los datos JSON del cuerpo de la solicitud
            data = json.loads(request.body)
            print(f"Datos recibidos: {data}")

            # Si no recibimos silabo_id como parámetro, intentamos obtenerlo de los datos
            if not silabo_id:
                silabo_id = data.get("silabo_id")
                print(f"Usando silabo_id de los datos del formulario: {silabo_id}")

            # Necesitamos un silabo_id válido
            if not silabo_id:
                error_msg = "No se proporcionó un ID de sílabo válido"
                print(error_msg)
                return JsonResponse({"error": error_msg}, status=400)

            # Obtener el sílabo directamente por su ID
            try:
                silabo = Silabo.objects.get(id=silabo_id)
                print(f"Sílabo encontrado: {silabo}")

                # Verificar si ya existe una guía para este sílabo
                # (asegurando la relación uno a uno)
                existing_guia = Guia.objects.filter(silabo=silabo).first()
                if existing_guia and not data.get("guia_id"):
                    # Si ya existe una guía y estamos intentando crear una nueva (no actualizar),
                    # actualicemos la existente en lugar de crear una nueva
                    guia = existing_guia
                    print(
                        f"Ya existe una guía para este sílabo (ID: {guia.id}). Se actualizará esta en lugar de crear una nueva."
                    )
                else:
                    # Crear o actualizar la guía
                    guia_id = data.get("guia_id")
                    if guia_id:
                        # Actualizar guía existente
                        guia = get_object_or_404(Guia, id=guia_id)
                    else:
                        # Crear nueva guía
                        guia = Guia()

                # Asignar los valores de los campos
                guia.silabo = silabo
                guia.numero_guia = data.get("numero_encuentro", silabo.encuentros)
                guia.numero_encuentro = data.get("numero_encuentro", silabo.encuentros)
                guia.fecha = data.get("fecha")
                guia.unidad = data.get("unidad")
                guia.nombre_de_la_unidad = data.get("nombre_de_la_unidad")

                # Tarea 1
                guia.tipo_objetivo_1 = data.get("tipo_objetivo_1")
                guia.objetivo_aprendizaje_1 = data.get("objetivo_aprendizaje_1")
                guia.contenido_tematico_1 = data.get("contenido_tematico_1")
                guia.actividad_aprendizaje_1 = data.get("actividad_aprendizaje_1")
                guia.tecnica_evaluacion_1 = data.get("tecnica_evaluacion_1")
                guia.tipo_evaluacion_1 = data.get("tipo_evaluacion_1")
                guia.instrumento_evaluacion_1 = data.get("instrumento_evaluacion_1")
                guia.criterios_evaluacion_1 = data.get("criterios_evaluacion_1")
                guia.agente_evaluador_1 = data.get("agente_evaluador_1")
                guia.tiempo_minutos_1 = data.get("tiempo_minutos_1")
                guia.recursos_didacticos_1 = data.get("recursos_didacticos_1")
                guia.periodo_tiempo_programado_1 = data.get(
                    "periodo_tiempo_programado_1"
                )
                guia.puntaje_1 = data.get("puntaje_1")
                guia.fecha_entrega_1 = data.get("fecha_entrega_1")

                # Tarea 2
                guia.tipo_objetivo_2 = data.get("tipo_objetivo_2")
                guia.objetivo_aprendizaje_2 = data.get("objetivo_aprendizaje_2")
                guia.contenido_tematico_2 = data.get("contenido_tematico_2")
                guia.actividad_aprendizaje_2 = data.get("actividad_aprendizaje_2")
                guia.tecnica_evaluacion_2 = data.get("tecnica_evaluacion_2")
                guia.tipo_evaluacion_2 = data.get("tipo_evaluacion_2")
                guia.instrumento_evaluacion_2 = data.get("instrumento_evaluacion_2")
                guia.criterios_evaluacion_2 = data.get("criterios_evaluacion_2")
                guia.agente_evaluador_2 = data.get("agente_evaluador_2")
                guia.tiempo_minutos_2 = data.get("tiempo_minutos_2")
                guia.recursos_didacticos_2 = data.get("recursos_didacticos_2")
                guia.periodo_tiempo_programado_2 = data.get(
                    "periodo_tiempo_programado_2"
                )
                guia.puntaje_2 = data.get("puntaje_2")
                guia.fecha_entrega_2 = data.get("fecha_entrega_2")

                # Tarea 3
                guia.tipo_objetivo_3 = data.get("tipo_objetivo_3")
                guia.objetivo_aprendizaje_3 = data.get("objetivo_aprendizaje_3")
                guia.contenido_tematico_3 = data.get("contenido_tematico_3")
                guia.actividad_aprendizaje_3 = data.get("actividad_aprendizaje_3")
                guia.tecnica_evaluacion_3 = data.get("tecnica_evaluacion_3")
                guia.tipo_evaluacion_3 = data.get("tipo_evaluacion_3")
                guia.instrumento_evaluacion_3 = data.get("instrumento_evaluacion_3")
                guia.criterios_evaluacion_3 = data.get("criterios_evaluacion_3")
                guia.agente_evaluador_3 = data.get("agente_evaluador_3")
                guia.tiempo_minutos_3 = data.get("tiempo_minutos_3")
                guia.recursos_didacticos_3 = data.get("recursos_didacticos_3")
                guia.periodo_tiempo_programado_3 = data.get(
                    "periodo_tiempo_programado_3"
                )
                guia.puntaje_3 = data.get("puntaje_3")
                guia.fecha_entrega_3 = data.get("fecha_entrega_3")

                # Tarea 4
                guia.tipo_objetivo_4 = data.get("tipo_objetivo_4")
                guia.objetivo_aprendizaje_4 = data.get("objetivo_aprendizaje_4")
                guia.contenido_tematico_4 = data.get("contenido_tematico_4")
                guia.actividad_aprendizaje_4 = data.get("actividad_aprendizaje_4")
                guia.tecnica_evaluacion_4 = data.get("tecnica_evaluacion_4")
                guia.tipo_evaluacion_4 = data.get("tipo_evaluacion_4")
                guia.instrumento_evaluacion_4 = data.get("instrumento_evaluacion_4")
                guia.criterios_evaluacion_4 = data.get("criterios_evaluacion_4")
                guia.agente_evaluador_4 = data.get("agente_evaluador_4")
                guia.tiempo_minutos_4 = data.get("tiempo_minutos_4")
                guia.recursos_didacticos_4 = data.get("recursos_didacticos_4")
                guia.periodo_tiempo_programado_4 = data.get(
                    "periodo_tiempo_programado_4"
                )
                guia.puntaje_4 = data.get("puntaje_4")
                guia.fecha_entrega_4 = data.get("fecha_entrega_4")

                # Guardar la guía
                guia.save()

                # Actualizar también el sílabo para establecer la relación bilateral
                silabo.guia = guia
                silabo.save()

                # Incrementar contador de guías creadas en la asignación
                asignacion = silabo.asignacion_plan
                asignacion.guias_creadas += 1
                asignacion.save()

                # Verificar que la relación con el sílabo se haya establecido correctamente
                silabo_actualizado = Silabo.objects.get(id=silabo_id)
                guias_count = silabo_actualizado.guias.count()

                print(
                    f"Guía guardada con éxito. ID: {guia.id}, Sílabo ID: {silabo_id}, Total guías asociadas: {guias_count}"
                )
                print(
                    f"Relación bilateral establecida: Sílabo {silabo.id} apunta a Guía {guia.id}"
                )

                # Generar URL para redirección a la página de éxito
                success_url = reverse("success_view")

                return JsonResponse(
                    {
                        "success": True,
                        "message": "Guía guardada correctamente",
                        "guia_id": guia.id,
                        "silabo_id": silabo_id,
                        "total_guias": guias_count,
                        "redirect_url": success_url,
                    }
                )

            except json.JSONDecodeError:
                return JsonResponse({"error": "Formato JSON inválido"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # Caso de error: método no permitido
    return JsonResponse({"error": "Método no permitido"}, status=405)


def get_matching_guia(silabo_id, encuentro_numero):
    """
    Función auxiliar para encontrar la guía correspondiente a un encuentro específico
    de un sílabo, considerando varios métodos de coincidencia.

    Args:
        silabo_id: ID del sílabo
        encuentro_numero: Número de encuentro a buscar

    Returns:
        Objeto Guia que coincide con el encuentro, o la primera guía si no hay coincidencia
    """
    from django.db.models import Value, IntegerField

    # Obtener todas las guías de este sílabo
    guias = Guia.objects.filter(silabo_id=silabo_id).order_by("numero_encuentro")

    if not guias.exists():
        print(f"No hay guías para el sílabo {silabo_id}")
        return None

    # Imprimir detalles para diagnóstico
    print(f"DEBUG: Buscando guía para sílabo {silabo_id}, encuentro {encuentro_numero}")
    print(f"DEBUG: Tipo de dato del encuentro: {type(encuentro_numero)}")

    # Convertir encuentro_numero a texto para comparaciones uniformes
    encuentro_str = str(encuentro_numero).strip()
    print(f"DEBUG: Encuentro convertido a texto: '{encuentro_str}'")

    # 1. Método 1: Coincidencia directa
    guia_match = guias.filter(numero_encuentro=encuentro_numero).first()
    if guia_match:
        print(f"DEBUG: Encontrada coincidencia DIRECTA - Guía ID: {guia_match.id}")
        return guia_match

    # 2. Método 2: Coincidencia de cadena
    for guia in guias:
        guia_str = str(guia.numero_encuentro).strip()
        print(f"DEBUG: Comparando '{guia_str}' con '{encuentro_str}'")
        if guia_str == encuentro_str:
            print(f"DEBUG: Encontrada coincidencia por STRING - Guía ID: {guia.id}")
            return guia

    # 3. Método 3: Coincidencia numérica (por si hay problemas de tipo)
    try:
        encuentro_int = int(encuentro_str)
        for guia in guias:
            try:
                guia_int = int(str(guia.numero_encuentro).strip())
                if guia_int == encuentro_int:
                    print(
                        f"DEBUG: Encontrada coincidencia NUMÉRICA - Guía ID: {guia.id}"
                    )
                    return guia
            except ValueError:
                pass
    except ValueError:
        pass

    # 4. Fallback: Devolver la primera guía disponible
    guia_fallback = guias.first()
    print(
        f"DEBUG: Sin coincidencia. Usando primera guía (ID: {guia_fallback.id}) como fallback"
    )



@login_required
def generar_silabo(request):
    """
    Función para generar un sílabo usando modelos de IA.
    """
    from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
    import json
    from django.db.models import Q
    from plan_de_estudio.models import AsignacionPlanEstudio, Silabo, PlanTematico

    if request.method == "POST":
        # Obtener los datos del formulario
        encuentro = request.POST.get("encuentro")
        plan_id = request.POST.get("plan")
        # Obtener el modelo seleccionado del formulario
        modelo_seleccionado = request.POST.get("modelo_select", "google")
        print(
            "Imprimiendo el modelo selecionodao:::::::::::::::::: "
            + str(modelo_seleccionado)
        )

        try:
            # Convertir a entero para asegurar que es un número válido
            encuentro = int(encuentro)
            if encuentro < 1 or encuentro > 12:
                return JsonResponse(
                    {"error": "El número de encuentro debe estar entre 1 y 12"},
                    status=400,
                )
        except ValueError:
            return JsonResponse(
                {"error": "El número de encuentro debe ser un número válido"},
                status=400,
            )

        try:
            # Obtener la asignación del plan de estudio
            asignacion = AsignacionPlanEstudio.objects.get(id=plan_id)

            # Obtener el plan temático relacionado
            plan_tematico = PlanTematico.objects.filter(
                plan_estudio=asignacion.plan_de_estudio
            ).first()
            if not plan_tematico:
                return JsonResponse(
                    {"error": "No se encontró un plan temático para esta asignación"},
                    status=400,
                )

            # Obtener los sílabos ya generados para esta asignación
            silabos_existentes = Silabo.objects.filter(
                asignacion_plan=asignacion
            ).order_by("encuentros")

            # Convertir los sílabos existentes a un formato que podamos usar en el prompt
            silabos_previos = []
            for silabo in silabos_existentes:
                if (
                    silabo.encuentros < encuentro
                ):  # Solo considerar los encuentros previos
                    silabo_dict = {
                        "encuentro": silabo.encuentros,
                        "unidad": silabo.unidad,
                        "nombre_de_la_unidad": silabo.nombre_de_la_unidad,
                        "contenido_tematico": silabo.contenido_tematico,
                        "objetivo_conceptual": silabo.objetivo_conceptual,
                        "objetivo_procedimental": silabo.objetivo_procedimental,
                        "objetivo_actitudinal": silabo.objetivo_actitudinal,
                    }
                    silabos_previos.append(silabo_dict)

            # Verificar si ya existe un sílabo para este encuentro
            silabo_actual = Silabo.objects.filter(
                asignacion_plan=asignacion, encuentros=encuentro
            ).first()
            if silabo_actual:
                return JsonResponse(
                    {"error": f"Ya existe un sílabo para el encuentro {encuentro}"},
                    status=400,
                )

        except AsignacionPlanEstudio.DoesNotExist:
            return JsonResponse(
                {"error": "No se encontró el plan de estudio especificado"}, status=400
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Error al obtener datos del plan: {str(e)}"}, status=400
            )

        # Ruta al archivo de datos JSON con la estructura
        json_filepath = os.path.join(settings.BASE_DIR, "static", "data", "datos.json")

        try:
            with open(json_filepath, "r", encoding="utf-8") as json_file:
                datos_estructura = json.load(json_file)

            # Obtener la estructura del primer encuentro como ejemplo
            primer_encuentro = datos_estructura.get("primer_encuentro", {})
            # Obtener las listas de opciones
            unidades = datos_estructura.get("unidades", [])
            ejes_transversales = datos_estructura.get("ejes_transversales", [])
            tipos_primer_momento = datos_estructura.get("tipos_primer_momento", [])
            tipos_segundo_momento_teoria = datos_estructura.get(
                "tipos_segundo_momento_teoria", []
            )
            tipos_segundo_momento_practica = datos_estructura.get(
                "tipos_segundo_momento_practica", []
            )
            tipos_tercer_momento = datos_estructura.get("tipos_tercer_momento", [])

        except Exception as e:
            return JsonResponse(
                {"error": f"Error al cargar el archivo de estructura JSON: {str(e)}"},
                status=400,
            )

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

        try:
            # Configurar parámetros específicos para el modelo seleccionado
            config = get_default_config(modelo_seleccionado)

            # Generar respuesta usando la función centralizada
            data = generar_respuesta_ai(prompt_completo, modelo_seleccionado, **config)

            # Devolver la respuesta
            return JsonResponse({"silabo_data": data})

        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logging.error(error_msg)
            return JsonResponse({"error": error_msg}, status=500)


@login_required
def generar_estudio_independiente(request):
    """
    Vista para generar una guía de estudio utilizando IA.
    """
    from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
    import traceback
    import logging

    if request.method == "POST":
        silabo_id = request.POST.get("silabo_id")
        asignacion_id = request.POST.get("asignacion_id")
        encuentro = int(
            request.POST.get("encuentro", 1)
        )  # Por defecto, primer encuentro
        modelo_seleccionado = request.POST.get("modelo")

        print(
            f"Recibida solicitud para generar guía de estudio. Sílabo ID: {silabo_id}, Asignación ID: {asignacion_id}, Encuentro: {encuentro}, Modelo: {modelo_seleccionado}"
        )

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
            if (
                not silabo
                and asignacion_id
                and asignacion_id != "null"
                and asignacion_id != ""
            ):
                try:
                    asignacion = AsignacionPlanEstudio.objects.get(id=asignacion_id)
                    print(f"Asignación encontrada con ID {asignacion_id}: {asignacion}")

                    # 3. Intentar encontrar sílabo por número de encuentro
                    silabo = Silabo.objects.filter(
                        asignacion_plan=asignacion, encuentros=encuentro
                    ).first()

                    if silabo:
                        print(
                            f"Sílabo encontrado para el encuentro {encuentro}: {silabo}"
                        )
                    else:
                        print(f"No se encontró sílabo para el encuentro {encuentro}")

                        # 4. Si no se encuentra por encuentro específico, buscar el último
                        silabo = (
                            Silabo.objects.filter(asignacion_plan=asignacion)
                            .order_by("-encuentros")
                            .first()
                        )

                        if silabo:
                            print(f"Se usará el último sílabo disponible: {silabo}")
                        else:
                            print(
                                f"No se encontraron sílabos para la asignación {asignacion_id}"
                            )
                            return JsonResponse(
                                {
                                    "error": "No hay sílabo disponible para esta asignación. Por favor, cree un sílabo primero."
                                },
                                status=400,
                            )

                except AsignacionPlanEstudio.DoesNotExist:
                    print(f"No se encontró asignación con ID {asignacion_id}")
                    return JsonResponse(
                        {
                            "error": f"No se encontró la asignación con ID {asignacion_id}"
                        },
                        status=400,
                    )

            if not silabo:
                print(
                    "No se pudo encontrar un sílabo después de intentar todas las opciones"
                )
                return JsonResponse(
                    {"error": "No se pudo encontrar un sílabo para generar la guía."},
                    status=400,
                )

            if not asignacion:
                asignacion = silabo.asignacion_plan

            print(f"Usando asignación: {asignacion}, Sílabo: {silabo}")

            # Verificar si ya existe una guía para este sílabo
            guia_existente = Guia.objects.filter(silabo=silabo).first()
            if guia_existente:
                print(
                    f"Ya existe una guía para el sílabo {silabo.id} (Encuentro {silabo.encuentros})"
                )
                return JsonResponse(
                    {
                        "error": f"Ya existe una guía para este sílabo (Encuentro {silabo.encuentros})"
                    },
                    status=400,
                )

            # Continuar con el resto del código...

            # Obtener guías anteriores para otros sílabos de la misma asignación
            guias_anteriores = Guia.objects.filter(
                silabo__asignacion_plan=asignacion,
                silabo__encuentros__lt=silabo.encuentros,
            ).order_by("silabo__encuentros")

            # Ruta al archivo de datos JSON con la estructura de la guía
            json_filepath = os.path.join(
                settings.BASE_DIR, "static", "data", "guia_ejemplo.json"
            )

            with open(json_filepath, "r", encoding="utf-8") as json_file:
                datos_estructura = json.load(json_file)

            # Obtener la estructura de ejemplo y las listas de opciones
            ejemplo_guia = datos_estructura.get("ejemplo_guia", {})
            tipos_objetivo = datos_estructura.get("tipos_objetivo", [])
            tecnicas_evaluacion = datos_estructura.get("tecnicas_evaluacion", [])
            tipos_evaluacion = datos_estructura.get("tipos_evaluacion", [])
            instrumentos_evaluacion = datos_estructura.get(
                "instrumentos_evaluacion", []
            )
            agentes_evaluadores = datos_estructura.get("agentes_evaluadores", [])
            periodos_tiempo = datos_estructura.get("periodos_tiempo", [])

            # Convertir las guías anteriores a un formato que podamos usar en el prompt
            guias_previas = []
            for guia in guias_anteriores:
                guia_dict = {
                    "numero_encuentro": guia.numero_encuentro,
                    "fecha": guia.fecha.strftime("%Y-%m-%d") if guia.fecha else None,
                    "unidad": guia.unidad,
                    "nombre_de_la_unidad": guia.nombre_de_la_unidad,
                    # Tarea 1
                    "tipo_objetivo_1": guia.tipo_objetivo_1,
                    "objetivo_aprendizaje_1": guia.objetivo_aprendizaje_1,
                    "contenido_tematico_1": guia.contenido_tematico_1,
                    "actividad_aprendizaje_1": guia.actividad_aprendizaje_1,
                    "tecnica_evaluacion_1": guia.tecnica_evaluacion_1,
                    "tipo_evaluacion_1": guia.tipo_evaluacion_1,
                    "instrumento_evaluacion_1": guia.instrumento_evaluacion_1,
                    "criterios_evaluacion_1": guia.criterios_evaluacion_1,
                    "puntaje_1": guia.puntaje_1,
                    "fecha_entrega_1": guia.fecha_entrega_1,
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
            {json.dumps(guias_previas, indent=2, ensure_ascii=False, cls=DateTimeEncoder) if guias_previas else ""}

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
            {json.dumps(ejemplo_guia, indent=2, ensure_ascii=False, cls=DateTimeEncoder)}
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
            return JsonResponse({"success": True, "datos": data})

        except Silabo.DoesNotExist:
            return JsonResponse(
                {"error": "No se encontró el sílabo especificado"}, status=400
            )
        except Exception as e:
            error_message = f"Error inesperado: {str(e)}"
            logging.error(error_message)
            print(error_message)
            return JsonResponse({"error": error_message}, status=500)


@login_required
def cargar_guia(request, silabo_id):
    """
    Vista para cargar una guía específica de un sílabo mediante AJAX.
    """
    try:
        silabo = Silabo.objects.get(id=silabo_id)
        template_name = (
            "plan_estudio_template/tabla_actividades.html"
            if request.GET.get("only_table", False)
            else "plan_estudio_template/detalle_estudioindependiente.html"
        )

        debug_info = {
            "silabo_id": silabo_id,
            "silabo_encuentros": silabo.encuentros,
            "silabo_codigo": silabo.codigo if hasattr(silabo, "codigo") else "No tiene código",
            "asignatura": silabo.asignacion_plan.asignatura.nombre if hasattr(silabo, "asignacion_plan") and hasattr(silabo.asignacion_plan, "asignatura") else "No asignada",
            "request_type": "Solo tabla" if request.GET.get("only_table", False) else "Completo",
            "template_usado": template_name,
        }
        print(f"DEBUG SILABO: {debug_info}")

        guias_count = Guia.objects.filter(silabo_id=silabo_id).count()
        print(f"Total de guías para el sílabo {silabo_id}: {guias_count}")

        context = {
            "silabo": silabo,
            "debug_info": debug_info,
            "codigo": silabo.codigo if hasattr(silabo, "codigo") else "",
        }

        if guias_count == 0:
            print(f"No se encontraron guías para el sílabo {silabo_id}")
            context["mensaje_error"] = "Este sílabo no tiene guía asociada."
            html_content = render_to_string(template_name, context, request=request)
            return JsonResponse({"success": True, "html": html_content})

        guia = get_matching_guia(silabo_id, silabo.encuentros)

        if guia:
            print(f"Guía encontrada - ID: {guia.id}, Encuentro: {guia.numero_encuentro}")
        else:
            print(f"No se encontró ninguna guía específica para el sílabo {silabo_id}, pero existen guías.")
            # Si se quiere un mensaje específico en este caso:
            # context["mensaje_info"] = "No se encontró una guía para este encuentro específico."

        debug_info.update({
            "guia_id": guia.id if guia else None,
            "guia_numero_encuentro": guia.numero_encuentro if guia else None,
            "total_guias": guias_count,
        })
        context["guia"] = guia
        context["debug_info"] = debug_info # Actualizar debug_info en el contexto

        print(f"DEBUG FINAL: {debug_info}")
        html_content = render_to_string(template_name, context, request=request)
        return JsonResponse({"success": True, "html": html_content})

    except Silabo.DoesNotExist:
        print(f"Sílabo no encontrado: ID={silabo_id}")
        return JsonResponse({"success": False, "message": f"Sílabo no encontrado (ID: {silabo_id})"}, status=404)
    except Exception as e:
        error_msg = f"Error al cargar la guía: {str(e)} (Sílabo ID: {silabo_id})"
        print(f"ERROR: {error_msg}")
        return JsonResponse({"success": False, "message": error_msg}, status=500)


@login_required
def descargar_secuencia_didactica(request):
    """
    Vista para descargar la secuencia didáctica en formato documento.
    Genera un documento DOCX que incluye todos los encuentros de la secuencia didáctica.
    """
    from .documento_secuencia_didactica import generar_documento_secuencia_didactica
    
    # Obtener el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name() or request.user.username
    
    # Obtener las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)
    print(f"[DEBUG] Secuencia Didáctica View - Found {asignaciones.count()} asignaciones for user {usuario_autenticado.username}")

    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones)
    print(f"[DEBUG] Secuencia Didáctica View - Found {silabos.count()} silabos initially for user's asignaciones")
    
    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}
    
    for silabo in silabos:
        # Obtener el código del plan de estudio
        codigo = silabo.asignacion_plan.plan_de_estudio.codigo
        
        # Si el código no está en el diccionario, crear una lista vacía
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []
        
        # Agregar el sílabo a la lista correspondiente
        silabos_agrupados[codigo].append(silabo)
    
    # Obtener el año actual
    año_actual = datetime.datetime.now().year
    
    # Generar el documento
    output = generar_documento_secuencia_didactica(silabos_agrupados, nombre_de_usuario, año_actual)
    
    # Crear la respuesta HTTP con el documento
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = 'attachment; filename=secuencia_didactica.docx'
    
    return response


@login_required
def actualizar_silabo(request, silabo_id):
    """
    Vista para actualizar un sílabo existente de forma manual,
    sin usar un ModelForm de forms.py.
    """
    # Obtener la instancia del sílabo que se va a editar
    silabo = get_object_or_404(Silabo, id=silabo_id)

    # Lógica para manejar el envío del formulario (petición POST)
    if request.method == 'POST':
        try:
            # --- Actualizar cada campo del objeto 'silabo' con los datos de request.POST ---

            # Sección 1: Información General
            silabo.fecha = request.POST.get('fecha')
            silabo.unidad = request.POST.get('unidad')
            silabo.nombre_de_la_unidad = request.POST.get('nombre_de_la_unidad')
            silabo.contenido_tematico = request.POST.get('contenido_tematico')

            # Sección 2: Objetivos
            silabo.objetivo_conceptual = request.POST.get('objetivo_conceptual')
            silabo.objetivo_procedimental = request.POST.get('objetivo_procedimental')
            silabo.objetivo_actitudinal = request.POST.get('objetivo_actitudinal')

            # Sección 3: Fases del Acto Mental
            # Primer Momento
            silabo.tipo_primer_momento = request.POST.get('tipo_primer_momento')
            silabo.detalle_primer_momento = request.POST.get('detalle_primer_momento')
            silabo.tiempo_primer_momento = request.POST.get('tiempo_primer_momento')
            silabo.recursos_primer_momento = request.POST.get('recursos_primer_momento')
            # Segundo Momento
            silabo.tipo_segundo_momento_claseteoria = request.POST.get('tipo_segundo_momento_claseteoria')
            silabo.clase_teorica = request.POST.get('clase_teorica')
            silabo.tipo_segundo_momento_practica = request.POST.get('tipo_segundo_momento_practica')
            silabo.clase_practica = request.POST.get('clase_practica')
            silabo.tiempo_segundo_momento_teorica = request.POST.get('tiempo_segundo_momento_teorica')
            silabo.tiempo_segundo_momento_practica = request.POST.get('tiempo_segundo_momento_practica')
            silabo.recursos_segundo_momento = request.POST.get('recursos_segundo_momento')
            # Tercer Momento (Campo MultiSelect)
            silabo.tipo_tercer_momento = request.POST.getlist('tipo_tercer_momento')
            silabo.detalle_tercer_momento = request.POST.get('detalle_tercer_momento')
            silabo.tiempo_tercer_momento = request.POST.get('tiempo_tercer_momento')
            silabo.recursos_tercer_momento = request.POST.get('recursos_tercer_momento')
            # Ejes Transversales (Campo MultiSelect)
            silabo.eje_transversal = request.POST.getlist('eje_transversal')
            silabo.detalle_eje_transversal = request.POST.get('detalle_eje_transversal')

            # Sección 4: Evaluación Dinámica
            silabo.actividad_aprendizaje = request.POST.get('actividad_aprendizaje')
            silabo.tecnica_evaluacion = request.POST.getlist('tecnica_evaluacion')
            silabo.tipo_evaluacion = request.POST.getlist('tipo_evaluacion')
            silabo.periodo_tiempo_programado = request.POST.get('periodo_tiempo_programado')
            silabo.tiempo_minutos = request.POST.get('tiempo_minutos')
            silabo.agente_evaluador = request.POST.getlist('agente_evaluador')
            silabo.instrumento_evaluacion = request.POST.get('instrumento_evaluacion')
            silabo.criterios_evaluacion = request.POST.get('criterios_evaluacion')
            silabo.puntaje = request.POST.get('puntaje')

            # Es una buena práctica ejecutar la validación del modelo manualmente
            silabo.full_clean()
            silabo.save()

            messages.success(request, '¡El sílabo ha sido actualizado correctamente!')
            # Cambia 'lista_silabos' por el nombre de la URL a la que quieres redirigir
            return redirect('plan_de_estudio')

        except ValidationError as e:
            # Si la validación del modelo falla, mostramos los errores
            messages.error(request, 'Error de validación. Por favor, revise los campos.')
            # El contexto se pasará al final para volver a renderizar el formulario
            pass  # Permite que el código continúe hasta el render final

    # Contexto para peticiones GET o si falla la validación en POST
    context = {
        'silabo': silabo,  # La instancia del sílabo para poblar los campos
        'asignacion': silabo.asignacion_plan,
        'encuentro': silabo.encuentros,
        # Pasamos las listas de opciones para construir los <select> y checkboxes en la plantilla
        'UNIDAD_LIST': Silabo.UNIDAD_LIST,
        'TIPO_PRIMER_MOMENTO_LIST': Silabo.TIPO_PRIMER_MOMENTO_LIST,
        'TIPO_SEGUNDO_MOMENTO_TEORIA_LIST': Silabo.TIPO_SEGUNDO_MOMENTO_TEORIA_LIST,
        'TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST': Silabo.TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST,
        'TIPO_TERCER_MOMENTO_LIST': Silabo.TIPO_TERCER_MOMENTO_LIST,
        'EJE_TRANSVERSAL_LIST': Silabo.EJE_TRANSVERSAL_LIST,
        'TECNICA_EVALUACION_LIST': Silabo.TECNICA_EVALUACION_LIST,
        'TIPO_EVALUACION_LIST': Silabo.TIPO_EVALUACION_LIST,
        'PERIODO_TIEMPO_LIST': Silabo.PERIODO_TIEMPO_LIST,
        'AGENTE_EVALUADOR_LIST': Silabo.AGENTE_EVALUADOR_LIST,
        'INSTRUMENTO_EVALUACION_LIST': Silabo.INSTRUMENTO_EVALUACION_LIST,
    }

    return render(request, 'actualizar_silabo.html', context)


def vista_tutoriales(request):
    """
    Renderiza la página de tutoriales, obteniendo la URL para el video
    'tutoriales/tutorial.mp4' desde MinIO y la asigna a ambos reproductores.
    """
    # Ruta del único video de tutorial en tu bucket de MinIO
    tutorial_video_path = 'tutoriales/tutorial.mp4'

    video_url = None

    try:
        # Primero, verificamos si el archivo de video realmente existe en MinIO
        if default_storage.exists(tutorial_video_path):
            # Si existe, generamos su URL. Como tienes 'PRESIGNED' activado,
            # será una URL temporal y segura.
            video_url = default_storage.url(tutorial_video_path)
        else:
            # Si el archivo no se encuentra, imprimimos una advertencia en la consola del servidor.
            # Esto es útil para depuración.
            print(f"ADVERTENCIA: El video tutorial en la ruta '{tutorial_video_path}' no fue encontrado en MinIO.")

    except Exception as e:
        # Capturamos cualquier otro error de conexión con MinIO
        print(f"ERROR: No se pudo obtener la URL del video desde MinIO. Detalle: {e}")

    # Creamos el contexto para la plantilla.
    # Asignamos la misma URL a las dos variables que la plantilla espera.
    # De esta forma, no necesitas modificar la plantilla HTML.
    contexto = {
        'silabo_video_url': video_url,
        'guia_video_url': video_url,
    }

    return render(request, 'tutoriales.html', contexto)