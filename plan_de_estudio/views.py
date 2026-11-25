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
from .models import (
    Silabo,
    Guia,
    AsignacionPlanEstudio,
    Asignatura,
    Plan_de_estudio,
    ModeloIAConfig,
    ConfiguracionSistema,
    TOTAL_ENCUENTROS_SILABO,
    TRIMESTRES_ROMANOS,
    obtener_max_encuentros_guia,
)
from .ranking_utils import construir_ranking_docentes
from .trimestre_utils import parsear_trimestre_lectivo

from .forms import SilaboForm
from . import pwa_views
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from django.urls import reverse
from django.core.files.storage import default_storage
# Importaciones para IA
import openai  # Importar openai directamente, sin la clase OpenAI
from google import genai
import httpx
from .ai_generators import DateTimeEncoder  # Importar el encoder personalizado

# Cargar variables de entorno
load_dotenv()
# La configuración de API se maneja localmente en cada servicio mediante genai.Client()


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
        # Limitar a un máximo de 11 encuentros según el estándar académico
        silabos_agrupados[codigo_grupo] = grupo[:11]

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
    ).order_by('-id')
    max_guias = obtener_max_encuentros_guia()
    rango = range(1, TOTAL_ENCUENTROS_SILABO + 1)  # 1..11 para sílabos
    rango_guias = range(1, max_guias + 1)  # 1..10 por defecto (o 1..11 si se restaura)

    asignaciones_pendientes = [
        a for a in asignaciones
        if a.silabos_creados < TOTAL_ENCUENTROS_SILABO or a.guias_creadas < max_guias
    ]
    asignaciones_completadas = [
        a for a in asignaciones
        if a.silabos_creados >= TOTAL_ENCUENTROS_SILABO and a.guias_creadas >= max_guias
    ]

    return render(
        request,
        "inicio.html",
        {
            "asignaciones": asignaciones,
            "asignaciones_pendientes": asignaciones_pendientes,
            "asignaciones_completadas": asignaciones_completadas,
            "rango": rango,
            "rango_guias": rango_guias,
            "max_guias": max_guias,
            "usuario": nombre_de_usuario
        },
    )



def acerca_de(request):
    nombre_de_usuario = request.user.username
    return render(request, "acerca_de.html", {"usuario": nombre_de_usuario})


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
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

    # Primero obtenemos las asignaciones del usuario autenticado, ordenadas por fecha de asignación desc (los últimos asignados primero)
    # Solo consideramos las asignaciones que tengan al menos un sílabo creado (para mantener el comportamiento original de la vista de datos)
    asignaciones_list = AsignacionPlanEstudio.objects.filter(
        usuario=usuario_autenticado
    ).annotate(
        num_silabos=Count('silabo_set')
    ).filter(
        num_silabos__gt=0
    ).order_by('-fecha_asignacion')

    # Paginación: 5 asignaciones por página
    from django.core.paginator import Paginator
    paginator = Paginator(asignaciones_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Obtener el año actual
    año_actual = datetime.datetime.now().year

    context = {
        "page_obj": page_obj,
        "usuario": nombre_de_usuario,
        "año_actual": año_actual,
        "max_guias": obtener_max_encuentros_guia(),
    }

    return render(request, "plan_estudio.html", context)


@login_required
def guia_autodidactica(request, codigo=None):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.get_full_name()
    max_guias = obtener_max_encuentros_guia()

    # Obtener código desde URL o parámetros GET
    if not codigo:
        codigo = request.GET.get('codigo')

    # Primero obtenemos las asignaciones del usuario autenticado
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=usuario_autenticado)

    # Luego obtenemos los silabos relacionados con esas asignaciones
    silabos = Silabo.objects.filter(asignacion_plan__in=asignaciones).prefetch_related('guias')

    # Si se especifica un código, filtrar solo por ese código
    if codigo:
        silabos = silabos.filter(asignacion_plan__plan_de_estudio__codigo=codigo)

    # Crear un diccionario para agrupar los silabos por código de plan de estudio
    silabos_agrupados = {}

    for silabo in silabos:
        # Si el sílabo no tiene asignación de plan o plan de estudio, continuamos al siguiente
        if not silabo.asignacion_plan or not silabo.asignacion_plan.plan_de_estudio:
            continue

        # Omitir encuentros que no requieren guía (ej. E11) salvo que ya exista guía histórica
        if silabo.encuentros > max_guias and not silabo.guia_id and not silabo.guias.exists():
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
        # Limitar a un máximo de 11 encuentros según el estándar académico
        silabos_agrupados[codigo_grupo] = grupo[:11]

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
        # Limitar a un máximo de 11 encuentros según el estándar académico
        silabos_agrupados[codigo_grupo] = grupo[:11]

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


def get_previous_scores(asignacion, exclude_silabo_id=None, exclude_guia_id=None):
    from plan_de_estudio.utils.curriculum_planner import calcular_puntajes_por_corte

    return calcular_puntajes_por_corte(
        asignacion,
        exclude_silabo_id=exclude_silabo_id,
        exclude_guia_id=exclude_guia_id,
    )


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
        if asignacion.silabos_creados != silabos_creados:
            asignacion.silabos_creados = silabos_creados
            asignacion.save(update_fields=["silabos_creados"])

        encuentros_existentes = set(
            asignacion.silabo_set.values_list("encuentros", flat=True)
        )
        proximo_encuentro = next(
            (n for n in range(1, 12) if n not in encuentros_existentes),
            None,
        )
        if proximo_encuentro is None:
            messages.warning(
                request,
                f"Ya se han completado los 11 sílabos para {asignacion.plan_de_estudio}.",
            )
            return redirect("inicio")

        form = SilaboForm(
            initial={
                "codigo": asignacion.plan_de_estudio.codigo,
                "carrera": asignacion.plan_de_estudio.carrera,
                "asignatura": asignacion.plan_de_estudio,  # Asignar el plan de estudio como asignatura
                "maestro": request.user,
                "encuentros": proximo_encuentro,
            }
        )

        asignaturas = Asignatura.objects.all()

        # Obtener el plan temático efectivo o el programa 2026 asociado
        plan_tematico = asignacion.plan_de_estudio.get_plan_tematico_efectivo()
        programa_2026 = asignacion.plan_de_estudio.programas_2026_asociados.first()
        mostrar_ia = bool(plan_tematico) or bool(programa_2026)

        previous_scores = get_previous_scores(asignacion)
        modelos_ia = ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by('orden', 'id')

        return render(
            request,
            "formulario_silabo.html",
            {
                "form": form,
                "asignacion": asignacion,
                "usuario": nombre_de_usuario,
                "silabos_creados": silabos_creados,
                "encuentro": proximo_encuentro,
                "asignaturas": asignaturas,
                "mostrar_ia": mostrar_ia,
                "modelos_ia": modelos_ia,
                "previous_scores": previous_scores,
                "previous_scores_json": json.dumps(previous_scores),
            },
        )

    # Caso de error: falta asignacion_id
    return JsonResponse({"error": "Falta ID de asignación"}, status=400)


def _obtener_silabo_pendiente_guia(asignacion, max_guias=None):
    """Retorna el primer sílabo habilitado (1..max_guias) sin guía asociada, ordenado por encuentro."""
    if max_guias is None:
        max_guias = obtener_max_encuentros_guia()
    return (
        Silabo.objects.filter(
            asignacion_plan=asignacion,
            encuentros__lte=max_guias,
            guias__isnull=True,
            guia__isnull=True,
        )
        .order_by("encuentros")
        .first()
    )


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
        max_guias = obtener_max_encuentros_guia()
        silabos_creados = asignacion.silabo_set.count()
        guias_creadas = Guia.objects.filter(silabo__asignacion_plan=asignacion).count()
        campos_sync = []
        if asignacion.silabos_creados != silabos_creados:
            asignacion.silabos_creados = silabos_creados
            campos_sync.append("silabos_creados")
        if asignacion.guias_creadas != guias_creadas:
            asignacion.guias_creadas = guias_creadas
            campos_sync.append("guias_creadas")
        if campos_sync:
            asignacion.save(update_fields=campos_sync)

        print(
            f"Asignación encontrada: {asignacion}, Sílabos creados: {silabos_creados}, Guías creadas: {guias_creadas}, Máx guías: {max_guias}"
        )

        # Obtener el sílabo correspondiente al encuentro pendiente
        silabo = None
        if silabo_id:
            try:
                silabo = Silabo.objects.get(id=silabo_id)
                print(f"Sílabo encontrado por silabo_id {silabo_id}: {silabo}")
                print(f"Sílabo ID: {silabo.id}")
            except Silabo.DoesNotExist:
                print(f"No se encontró sílabo con ID {silabo_id}")

        if silabo and silabo.encuentros > max_guias and not Guia.objects.filter(silabo=silabo).exists():
            messages.warning(
                request,
                f"El encuentro {silabo.encuentros} no requiere guía de estudio independiente (máximo actual: {max_guias} guías).",
            )
            return redirect("inicio")

        encuentro_guia = None
        if not silabo:
            if guias_creadas >= max_guias:
                messages.warning(
                    request,
                    f"Ya se han completado las {max_guias} guías de estudio para {asignacion.plan_de_estudio}.",
                )
                return redirect("inicio")

            # Buscar el primer sílabo habilitado (1..max_guias) que aún no tiene guía
            silabo = _obtener_silabo_pendiente_guia(asignacion, max_guias=max_guias)
            if silabo:
                encuentro_guia = silabo.encuentros
                print(
                    f"Sílabo pendiente encontrado para el encuentro {silabo.encuentros}: {silabo}"
                )
            else:
                encuentros_con_guia = set(
                    Guia.objects.filter(silabo__asignacion_plan=asignacion).values_list(
                        "silabo__encuentros", flat=True
                    )
                )
                encuentro_guia = next(
                    (n for n in range(1, max_guias + 1) if n not in encuentros_con_guia),
                    min(guias_creadas + 1, max_guias),
                )
                if silabos_creados > 0:
                    messages.info(
                        request,
                        f"Todos los sílabos creados ya tienen guía asociada. Cree primero el sílabo del encuentro {encuentro_guia}.",
                    )
                print(
                    "No se encontró ningún sílabo pendiente de guía. Se pasará 'silabo=None' a la plantilla."
                )
        else:
            encuentro_guia = silabo.encuentros

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

        # Obtener el plan temático efectivo o el programa 2026 asociado
        plan_tematico = asignacion.plan_de_estudio.get_plan_tematico_efectivo()
        programa_2026 = asignacion.plan_de_estudio.programas_2026_asociados.first()
        mostrar_ia = bool(plan_tematico) or bool(programa_2026)

        exclude_guia_id = None
        if silabo:
            existing_guia = Guia.objects.filter(silabo=silabo).first()
            if existing_guia:
                exclude_guia_id = existing_guia.id
        previous_scores = get_previous_scores(asignacion, exclude_guia_id=exclude_guia_id)
        modelos_ia = ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by('orden', 'id')

        return render(
            request,
            "formulario_estudio_independiente.html",
            {
                "asignacion": asignacion,
                "silabo": silabo,  # Pasar el sílabo a la plantilla
                "usuario": nombre_de_usuario,
                "silabos_creados": silabos_creados,
                "guias_creadas": guias_creadas,
                "max_guias": max_guias,
                "encuentro": encuentro_guia,
                "guias": guias,
                "unidad_choices": unidad_choices,
                "tecnica_evaluacion_choices": tecnica_evaluacion_choices,
                "tipo_evaluacion_choices": tipo_evaluacion_choices,
                "instrumento_evaluacion_choices": instrumento_evaluacion_choices,
                "agente_evaluador_choices": agente_evaluador_choices,
                "periodo_tiempo_choices": periodo_tiempo_choices,
                "tipo_objetivo_choices": tipo_objetivo_choices,
                "mostrar_ia": mostrar_ia,
                "modelos_ia": modelos_ia,
                "previous_scores": previous_scores,
                "previous_scores_json": json.dumps(previous_scores),
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

            # Sincronizar contador de sílabos creados
            asignacion.silabos_creados = asignacion.silabo_set.count()
            asignacion.save(update_fields=["silabos_creados"])

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

                max_guias = obtener_max_encuentros_guia()
                # Verificar si ya existe una guía para este sílabo
                # (asegurando la relación uno a uno)
                existing_guia = Guia.objects.filter(silabo=silabo).first()
                try:
                    numero_encuentro_req = int(data.get("numero_encuentro") or silabo.encuentros or 1)
                except (ValueError, TypeError):
                    numero_encuentro_req = silabo.encuentros

                if not existing_guia and not data.get("guia_id"):
                    if silabo.encuentros > max_guias or numero_encuentro_req > max_guias:
                        enc_invalido = max(silabo.encuentros or 0, numero_encuentro_req or 0)
                        return JsonResponse(
                            {
                                "success": False,
                                "error": f"El encuentro {enc_invalido} no requiere guía de estudio independiente. Solo se permiten guías para los encuentros 1 al {max_guias}.",
                            },
                            status=400,
                        )

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
                guia.full_clean()
                guia.save()

                # Actualizar también el sílabo para establecer la relación bilateral
                silabo.guia = guia
                silabo.save()

                # Sincronizar contador de guías creadas en la asignación desde BD
                asignacion = silabo.asignacion_plan
                if asignacion:
                    asignacion.guias_creadas = Guia.objects.filter(
                        silabo__asignacion_plan=asignacion
                    ).count()
                    asignacion.save(update_fields=["guias_creadas"])

                # Verificar que la relación con el sílabo se haya establecido correctamente
                silabo_actualizado = Silabo.objects.get(id=silabo_id)
                guias_count = silabo_actualizado.guias.count()

                print(
                    f"Guía guardada con éxito. ID: {guia.id}, Sílabo ID: {silabo_id}, Total guías asociadas: {guias_count}"
                )
                print(
                    f"Relación bilateral establecida: Sílabo {silabo.id} apunta a Guía {guia.id}"
                )

                # Subir tareas a Google Classroom de forma asíncrona
                import threading
                from .services.google_classroom import subir_tareas_desde_guia
                
                # Ejecutar en segundo plano para no bloquear la respuesta
                thread = threading.Thread(target=subir_tareas_desde_guia, args=(guia,))
                thread.start()

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
        except ValidationError as e:
            errors = {field: error[0] for field, error in e.message_dict.items()} if hasattr(e, 'message_dict') else {'__all__': e.messages[0]}
            error_msg = "; ".join([f"{field}: {'; '.join(msgs)}" for field, msgs in e.message_dict.items()]) if hasattr(e, 'message_dict') else str(e)
            return JsonResponse({"success": False, "errors": errors, "error": error_msg}, status=400)
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
    Función para generar un sílabo usando modelos de IA con coherencia curricular,
    presupuesto por Corte Evaluativo, carga horaria del plan y mapa maestro de 11 encuentros.
    """
    from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
    from plan_de_estudio.utils.ai_normalizer import normalizar_respuesta_silabo
    from plan_de_estudio.utils.curriculum_planner import (
        calcular_corte_y_presupuesto,
        calcular_tiempos_y_fechas,
        construir_historial_compacto,
        construir_mapa_maestro,
        extraer_contexto_asignatura,
        formatear_contexto_curricular,
    )
    import json
    from plan_de_estudio.models import AsignacionPlanEstudio, Silabo

    if request.method == "POST":
        encuentro = request.POST.get("encuentro")
        plan_id = request.POST.get("plan")
        modelo_seleccionado = request.POST.get("modelo_select", "google")
        print(
            "Imprimiendo el modelo selecionodao:::::::::::::::::: "
            + str(modelo_seleccionado)
        )

        try:
            encuentro = int(encuentro)
            if encuentro < 1 or encuentro > 11:
                return JsonResponse(
                    {"error": "El número de encuentro debe estar entre 1 y 11"},
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "El número de encuentro debe ser un número válido"},
                status=400,
            )

        try:
            asignacion = AsignacionPlanEstudio.objects.select_related(
                "plan_de_estudio", "plan_de_estudio__asignatura"
            ).get(id=plan_id)

            silabo_actual = Silabo.objects.filter(
                asignacion_plan=asignacion, encuentros=encuentro
            ).first()
            if silabo_actual:
                return JsonResponse(
                    {"error": f"Ya existe un sílabo para el encuentro {encuentro}"},
                    status=400,
                )

            try:
                contexto_info = extraer_contexto_asignatura(asignacion.plan_de_estudio)
            except ValueError as err:
                return JsonResponse({"error": str(err)}, status=400)

            max_guias = obtener_max_encuentros_guia()
            mapa = construir_mapa_maestro(contexto_info["unidades"])
            enc_plan = mapa["por_encuentro"][encuentro]
            presupuesto = calcular_corte_y_presupuesto(
                asignacion, encuentro, es_guia=False, max_guias=max_guias
            )
            tiempos = calcular_tiempos_y_fechas(
                asignacion,
                encuentro,
                unidad_info=enc_plan["unidad_dict"],
                max_guias=max_guias,
            )
            historial = construir_historial_compacto(asignacion, encuentro)
            contexto_curricular = formatear_contexto_curricular(
                contexto_info, mapa, encuentro
            )

        except AsignacionPlanEstudio.DoesNotExist:
            return JsonResponse(
                {"error": "No se encontró el plan de estudio especificado"}, status=400
            )
        except Exception as e:
            return JsonResponse(
                {"error": f"Error al obtener datos del plan: {str(e)}"}, status=400
            )

        json_filepath = os.path.join(settings.BASE_DIR, "static", "data", "datos.json")

        try:
            with open(json_filepath, "r", encoding="utf-8") as json_file:
                datos_estructura = json.load(json_file)

            primer_encuentro = datos_estructura.get("primer_encuentro", {})

            unidades = [u[0] for u in Silabo.UNIDAD_LIST]
            ejes_transversales = [e[0] for e in Silabo.EJE_TRANSVERSAL_LIST]
            tipos_primer_momento = [t[0] for t in Silabo.TIPO_PRIMER_MOMENTO_LIST]
            tipos_segundo_momento_teoria = [t[0] for t in Silabo.TIPO_SEGUNDO_MOMENTO_TEORIA_LIST]
            tipos_segundo_momento_practica = [t[0] for t in Silabo.TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST]
            tipos_tercer_momento = [t[0] for t in Silabo.TIPO_TERCER_MOMENTO_LIST]
            tecnicas_evaluacion = [t[0] for t in Silabo.TECNICA_EVALUACION_LIST]
            tipos_evaluacion = [t[0] for t in Silabo.TIPO_EVALUACION_LIST]
            instrumentos_evaluacion = [t[0] for t in Silabo.INSTRUMENTO_EVALUACION_LIST]
            agentes_evaluadores = [t[0] for t in Silabo.AGENTE_EVALUADOR_LIST]
            periodos_tiempo = [t[0] for t in Silabo.PERIODO_TIEMPO_LIST]

        except Exception as e:
            return JsonResponse(
                {"error": f"Error al cargar el archivo de estructura JSON: {str(e)}"},
                status=400,
            )

        sin_guia_este_encuentro = encuentro > max_guias
        nota_cierre = ""
        if encuentro == 11:
            if sin_guia_este_encuentro:
                nota_cierre = (
                    f"\nREGLA ESPECIAL DE CIERRE (ENCUENTRO 11 DE 11 — SIN GUÍA DE ESTUDIO INDEPENDIENTE): "
                    f"Este es el ÚLTIMO día de clase del trimestre ({tiempos['fecha_encuentro']}). "
                    f"NO se deja tarea ni guía de estudio independiente porque las {max_guias} guías cerraron en el Encuentro {max_guias} y hoy se cierra todo el acumulado del III Corte Evaluativo. "
                    "Realiza síntesis, integración final y evaluación final presencial dentro del mismo encuentro; en `tipo_tercer_momento` usa `[\"Realimentación del aprendizaje\"]` y NO orientes estudio independiente ni dejes exposiciones o entregas pendientes para después."
                )
            else:
                nota_cierre = (
                    f"\nREGLA ESPECIAL DE CIERRE (ENCUENTRO 11): Este es el ÚLTIMO encuentro del trimestre ({tiempos['fecha_encuentro']}). "
                    "Realiza síntesis e integración final en el aula y evaluación final dentro del mismo encuentro; NO dejes exposiciones ni defensas pendientes para semanas posteriores."
                )

        reglas_variedad = ""
        if historial["tecnicas_clase_recientes"]:
            reglas_variedad = (
                "\nDIVERSIFICACIÓN DIDÁCTICA OBLIGATORIA (evita repetir exactamente las técnicas/instrumentos recientes): "
                + "; ".join(historial["tecnicas_clase_recientes"])
            )

        prompt_completo = f"""
            Instrucciones: Crea el sílabo para el Encuentro {encuentro} de 11 y devuélvelo únicamente como un objeto JSON válido.

            Plan de estudio: {str(asignacion.plan_de_estudio)}
            Asignatura: {asignacion.plan_de_estudio.asignatura.nombre}
            Fecha del encuentro: {tiempos['fecha_encuentro']} ({tiempos['ciclo_nombre']})

            PRESUPUESTO EVALUATIVO Y CARGA HORARIA (OBLIGATORIO):
            - Corte Evaluativo obligatorio (`periodo_tiempo_programado`): "{presupuesto['corte']}"
            - Acumulado previo en {presupuesto['corte']} (sílabos + guías): {presupuesto['usado_corte']}/100 pts (saldo disponible: {presupuesto['saldo_corte']}/100 pts).
            - Puntaje asignado a este sílabo (`puntaje`): {presupuesto['presupuesto_objetivo']} puntos (máximo estricto permitido: {presupuesto['presupuesto_max']} puntos).
            - Duración del encuentro presencial (`tiempo_primer_momento + tiempo_segundo_momento_teorica + tiempo_segundo_momento_practica + tiempo_tercer_momento`): DEBE sumar ~{tiempos['min_clase_objetivo']} minutos (plan total: {tiempos['horas_presenciales_plan']}h en 11 encuentros; desglose sugerido: 1er momento {tiempos['t1_sugerido']} min, 2do momento teoría {tiempos['t2_teorica_sugerido']} min, 2do momento práctica {tiempos['t2_practica_sugerido']} min, 3er momento {tiempos['t3_sugerido']} min).{nota_cierre}

            {contexto_curricular}

            HISTORIAL COMPACTO DE ENCUENTROS ANTERIORES (TEMAS EN CLASE Y TAREAS EN GUÍAS — PROHIBIDO REPETIR):
            {historial['resumen_texto']}{reglas_variedad}

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

            TIPOS DE TERCER MOMENTO DIDÁCTICO (máximo 2 opciones en arreglo JSON):
            {', '.join(tipos_tercer_momento)}

            TÉCNICAS DE EVALUACIÓN DISPONIBLES (máximo 2 opciones exactas en arreglo JSON):
            {', '.join(tecnicas_evaluacion)}

            TIPOS DE EVALUACIÓN DISPONIBLES (máximo 2 opciones exactas en arreglo JSON):
            {', '.join(tipos_evaluacion)}

            INSTRUMENTOS DE EVALUACIÓN DISPONIBLES (1 opción exacta):
            {', '.join(instrumentos_evaluacion)}

            AGENTES EVALUADORES DISPONIBLES (máximo 2 opciones exactas en arreglo JSON):
            {', '.join(agentes_evaluadores)}

            PERIODOS DE TIEMPO DISPONIBLES (1 opción exacta):
            {', '.join(periodos_tiempo)}

            EJEMPLO DE ESTRUCTURA (primer encuentro):
            ```
            {json.dumps(primer_encuentro, indent=2, ensure_ascii=False)}
            ```

            INSTRUCCIONES ESPECÍFICAS:
            1. Respeta estrictamente la ASIGNACIÓN OBLIGATORIA: `"unidad": "{enc_plan['unidad_romano']}"`, `"nombre_de_la_unidad": "{enc_plan['unidad_nombre']}"`.
            2. Desarrolla únicamente la fracción {enc_plan['sesion_en_unidad']}/{enc_plan['sesiones_unidad']} correspondiente del contenido temático de esa unidad, dando continuidad lógica sin repetir contenidos ya impartidos.
            3. En `actividad_aprendizaje` (trabajo práctico presencial en aula), diseña una dinámica presencial DIFERENTE y complementaria a las tareas ya asignadas en las Guías de Estudio Independiente.
            4. Varía las técnicas didácticas (`tipo_segundo_momento_*`, `tecnica_evaluacion`, `instrumento_evaluacion`) y los ejes transversales respecto a encuentros previos cuando sea pedagógicamente pertinente.
            5. Usa exactamente `"codigo": "{asignacion.plan_de_estudio.codigo}"`, `"encuentros": {encuentro}`, `"fecha": "{tiempos['fecha_encuentro']}"`, `"periodo_tiempo_programado": "{presupuesto['corte']}"`, `"puntaje": {presupuesto['presupuesto_objetivo']}` (<= {presupuesto['presupuesto_max']}), y los dos campos enteros `"tiempo_segundo_momento_teorica"` y `"tiempo_segundo_momento_practica"`.
            6. En campos de selección múltiple (`tipo_tercer_momento`, `eje_transversal`, `tecnica_evaluacion`, `tipo_evaluacion`, `agente_evaluador`) devuelve un arreglo JSON con 1 o máximo 2 valores EXACTOS de las listas anteriores.
            7. Devuelve únicamente un objeto JSON válido con la misma estructura que el ejemplo proporcionado.
        """

        try:
            config = get_default_config(modelo_seleccionado)

            data = generar_respuesta_ai(
                prompt_completo,
                modelo_seleccionado,
                tipo_respuesta="silabo",
                **config,
            )
            data = normalizar_respuesta_silabo(
                data,
                plan_codigo=asignacion.plan_de_estudio.codigo,
                encuentro=encuentro,
                unidad_default=enc_plan["unidad_romano"],
                nombre_unidad_default=enc_plan["unidad_nombre"],
                unidad_forzada=enc_plan["unidad_romano"],
                corte_forzado=presupuesto["corte"],
                puntaje_objetivo=presupuesto["presupuesto_objetivo"],
                puntaje_max=presupuesto["presupuesto_max"],
                forzar_exacto=presupuesto["es_ultimo_en_corte"],
                sin_guia_encuentro=sin_guia_este_encuentro,
                minutos_clase_objetivo=tiempos["min_clase_objetivo"],
                fecha_objetivo=tiempos["fecha_encuentro"],
            )

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
        max_guias = obtener_max_encuentros_guia()
        try:
            encuentro = int(request.POST.get("encuentro", 1))
            if encuentro < 1 or encuentro > max_guias:
                return JsonResponse(
                    {
                        "error": f"El número de encuentro para la guía debe estar entre 1 y {max_guias}"
                    },
                    status=400,
                )
        except (ValueError, TypeError):
            return JsonResponse({"error": "El número de encuentro debe ser un número válido"}, status=400)
        modelo_seleccionado = request.POST.get("modelo")
        try:
            numero_actividades = int(request.POST.get("numero_actividades", 4))
            if numero_actividades < 1 or numero_actividades > 4:
                return JsonResponse({"error": "El número de actividades debe estar entre 1 y 4"}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({"error": "El número de actividades debe ser un número válido"}, status=400)

        print(
            f"Recibida solicitud para generar guía de estudio. Sílabo ID: {silabo_id}, Asignación ID: {asignacion_id}, Encuentro: {encuentro}, Modelo: {modelo_seleccionado}, Actividades: {numero_actividades}"
        )

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
                    if silabo.encuentros:
                        encuentro = silabo.encuentros
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

                        # 4. Si no se encuentra por encuentro específico, buscar el primer sílabo pendiente de guía
                        silabo = _obtener_silabo_pendiente_guia(asignacion, max_guias=max_guias)

                        if silabo:
                            encuentro = silabo.encuentros
                            print(f"Se usará el primer sílabo pendiente de guía: {silabo}")
                        else:
                            print(
                                f"No hay sílabos pendientes de guía para la asignación {asignacion_id}"
                            )
                            return JsonResponse(
                                {
                                    "error": f"No hay sílabo disponible sin guía para el encuentro {encuentro}. Por favor, cree un sílabo primero."
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

            if (silabo.encuentros and silabo.encuentros > max_guias) or encuentro > max_guias:
                enc_rechazado = max(silabo.encuentros or 0, encuentro or 0)
                return JsonResponse(
                    {
                        "error": f"El encuentro {enc_rechazado} no requiere guía de estudio independiente (máximo permitido: {max_guias} guías)."
                    },
                    status=400,
                )

            from plan_de_estudio.utils.ai_normalizer import normalizar_respuesta_guia
            from plan_de_estudio.utils.curriculum_planner import (
                calcular_corte_y_presupuesto,
                calcular_tiempos_y_fechas,
                construir_historial_compacto,
                construir_mapa_maestro,
                extraer_contexto_asignatura,
                formatear_contexto_curricular,
                obtener_corte_para_encuentro,
            )

            print(f"Usando asignación: {asignacion}, Sílabo: {silabo}")

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

            import datetime as _dt

            contexto_curricular = None
            enc_plan = None
            if asignacion:
                try:
                    contexto_info = extraer_contexto_asignatura(asignacion.plan_de_estudio)
                    mapa = construir_mapa_maestro(contexto_info["unidades"])
                    enc_plan = mapa["por_encuentro"].get(encuentro)
                    if enc_plan:
                        contexto_curricular = formatear_contexto_curricular(
                            contexto_info, mapa, encuentro
                        )
                except ValueError:
                    enc_plan = None

            if not enc_plan:
                enc_plan = {
                    "encuentro": encuentro,
                    "unidad_romano": silabo.unidad,
                    "unidad_nombre": silabo.nombre_de_la_unidad,
                    "sesion_en_unidad": 1,
                    "sesiones_unidad": 1,
                    "corte": obtener_corte_para_encuentro(encuentro),
                    "unidad_dict": {
                        "horas_teoricas": 0,
                        "horas_practicas": 0,
                        "horas_independientes": 0,
                    },
                }
                contexto_curricular = (
                    f"Unidad del Sílabo: {silabo.unidad} — {silabo.nombre_de_la_unidad}\n"
                    f"Contenido Temático: {silabo.contenido_tematico}"
                )

            if asignacion:
                presupuesto = calcular_corte_y_presupuesto(
                    asignacion, encuentro, es_guia=True, max_guias=max_guias
                )
                tiempos = calcular_tiempos_y_fechas(
                    asignacion,
                    encuentro,
                    unidad_info=enc_plan["unidad_dict"],
                    silabo=silabo,
                    numero_actividades=numero_actividades,
                    max_guias=max_guias,
                )
                historial = construir_historial_compacto(asignacion, encuentro)
                plan_str = str(asignacion.plan_de_estudio)
                asig_nombre = asignacion.plan_de_estudio.asignatura.nombre
            else:
                fecha_base = silabo.fecha or _dt.date.today()
                fecha_ent_min = fecha_base - _dt.timedelta(days=5) if encuentro == 11 else fecha_base + _dt.timedelta(days=1)
                fecha_ent_max = fecha_base if encuentro == 11 else fecha_base + _dt.timedelta(days=6)
                presupuesto = {
                    "corte": obtener_corte_para_encuentro(encuentro),
                    "usado_corte": 0,
                    "saldo_corte": 100,
                    "presupuesto_objetivo": 20,
                    "presupuesto_max": 100,
                    "es_ultimo_en_corte": False,
                }
                min_indep_fallback = round((70 * 60) / max_guias)
                tiempos = {
                    "ciclo_nombre": "Ciclo actual",
                    "fecha_encuentro": fecha_base.isoformat(),
                    "fecha_entrega_min": fecha_ent_min.isoformat(),
                    "fecha_entrega_max": fecha_ent_max.isoformat(),
                    "horas_independientes_plan": 70,
                    "min_indep_objetivo": min_indep_fallback,
                    "min_por_tarea_aprox": max(15, round(min_indep_fallback / max(1, numero_actividades))),
                }
                historial = {
                    "resumen_texto": "Ningún encuentro previo registrado.",
                    "tecnicas_guia_recientes": [],
                }
                plan_str = silabo.codigo or "Plan de estudio"
                asig_nombre = silabo.nombre_de_la_unidad or "Asignatura"

            json_filepath = os.path.join(
                settings.BASE_DIR, "static", "data", "guia_ejemplo.json"
            )
            with open(json_filepath, "r", encoding="utf-8") as json_file:
                datos_estructura = json.load(json_file)
            ejemplo_guia = datos_estructura.get("ejemplo_guia", {})

            tipos_objetivo = [t[0] for t in Guia.TIPO_OBJETIVO_LIST]
            tecnicas_evaluacion = [t[0] for t in Silabo.TECNICA_EVALUACION_LIST]
            tipos_evaluacion = [t[0] for t in Silabo.TIPO_EVALUACION_LIST]
            instrumentos_evaluacion = [t[0] for t in Silabo.INSTRUMENTO_EVALUACION_LIST]
            agentes_evaluadores = [t[0] for t in Silabo.AGENTE_EVALUADOR_LIST]
            periodos_tiempo = [t[0] for t in Silabo.PERIODO_TIEMPO_LIST]

            if silabo.encuentros == encuentro:
                info_silabo_actual = f"""
                SÍLABO PRESENCIAL DE ESTE ENCUENTRO ({silabo.encuentros}) — COMPLEMENTAR SIN REPETIR EN CASA:
                - Código: {silabo.codigo} | Fecha: {silabo.fecha}
                - Unidad y Tema en clase: {silabo.unidad} ({silabo.nombre_de_la_unidad}) — {silabo.contenido_tematico}
                - Objetivos en clase: C={silabo.objetivo_conceptual} | P={silabo.objetivo_procedimental} | A={silabo.objetivo_actitudinal}
                - Desarrollo en aula (no duplicar): Teoría ({silabo.tipo_segundo_momento_claseteoria}): {silabo.clase_teorica} | Práctica ({silabo.tipo_segundo_momento_practica}): {silabo.clase_practica}
                - Actividad realizada en aula (diferenciar): {silabo.actividad_aprendizaje} | Eval clase: {silabo.tecnica_evaluacion} / {silabo.instrumento_evaluacion} ({silabo.puntaje} pts)
                """
            else:
                info_silabo_actual = (
                    f"NOTA: Este documento corresponde al Encuentro {encuentro} "
                    f"(sílabo de referencia #{silabo.encuentros}); prioriza la ASIGNACIÓN OBLIGATORIA y el DETALLE DE LA UNIDAD ACTIVA."
                )

            nota_cierre = ""
            if encuentro == 11:
                nota_cierre = (
                    f"\nREGLA DE CIERRE DEL CURSO (ENCUENTRO 11 — {tiempos['fecha_encuentro']}): "
                    f"TODAS las tareas (fecha_entrega_1..{numero_actividades}) DEBEN entregarse entre {tiempos['fecha_entrega_min']} y {tiempos['fecha_entrega_max']}. "
                    "PROHIBIDO programar fechas de entrega, exposiciones o defensas posteriores al cierre del curso."
                )
            elif encuentro == max_guias and max_guias < TOTAL_ENCUENTROS_SILABO:
                nota_cierre = (
                    f"\nREGLA DE CIERRE DE ESTUDIO INDEPENDIENTE (GUÍA {encuentro} DE {max_guias}): "
                    f"Esta es la ÚLTIMA guía de estudio independiente del trimestre (el Encuentro {TOTAL_ENCUENTROS_SILABO} es el cierre presencial y NO lleva guía ni tarea). "
                    f"TODAS las tareas (fecha_entrega_1..{numero_actividades}) DEBEN entregarse entre {tiempos['fecha_entrega_min']} y {tiempos['fecha_entrega_max']}, antes del último día de clases."
                )

            reglas_variedad = ""
            if historial["tecnicas_guia_recientes"]:
                reglas_variedad = (
                    "\nVARIEDAD EVALUATIVA OBLIGATORIA (no repitas la misma técnica/instrumento en todas las tareas): "
                    + "; ".join(historial["tecnicas_guia_recientes"])
                )

            prompt_completo = f"""
            Instrucciones: Crea una guía de estudio independiente para el Encuentro {encuentro} de {max_guias} (sobre {TOTAL_ENCUENTROS_SILABO} encuentros presenciales) y devuélvela únicamente como un objeto JSON válido.

            Plan de estudio: {plan_str}
            Asignatura: {asig_nombre}
            Fecha del encuentro y guía (`fecha`): {tiempos['fecha_encuentro']} ({tiempos['ciclo_nombre']})

            PRESUPUESTO EVALUATIVO Y CARGA HORARIA (OBLIGATORIO):
            - Corte Evaluativo obligatorio (`periodo_tiempo_programado_1..{numero_actividades}`): "{presupuesto['corte']}"
            - Acumulado previo en {presupuesto['corte']} (sílabos + guías): {presupuesto['usado_corte']}/100 pts (saldo disponible: {presupuesto['saldo_corte']}/100 pts).
            - PRESUPUESTO TOTAL DE ESTA GUÍA (`puntaje_1 + ... + puntaje_{numero_actividades}`): DEBE sumar {presupuesto['presupuesto_objetivo']} puntos (máximo estricto permitido: {presupuesto['presupuesto_max']} puntos). NO asignes 100 puntos a la guía completa.
            - CARGA HORARIA INDEPENDIENTE (`tiempo_minutos_1 + ... + tiempo_minutos_{numero_actividades}`): DEBE sumar ~{tiempos['min_indep_objetivo']} minutos en total (~{tiempos['min_por_tarea_aprox']} min por tarea; plan total: {tiempos['horas_independientes_plan']}h distribuidas en {max_guias} guías de estudio independiente).
            - VENTANA DE ENTREGA (`fecha_entrega_1..{numero_actividades}`): entre {tiempos['fecha_entrega_min']} y {tiempos['fecha_entrega_max']}.{nota_cierre}

            {contexto_curricular}

            {info_silabo_actual}

            HISTORIAL COMPACTO DE ENCUENTROS Y GUÍAS PREVIAS (TODAS LAS TAREAS — PROHIBIDO REPETIR):
            {historial['resumen_texto']}{reglas_variedad}

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
            1. Genera EXACTAMENTE {numero_actividades} tareas de estudio independiente (del 1 al {numero_actividades}) en la unidad `"unidad": "{enc_plan['unidad_romano']}"`, `"nombre_de_la_unidad": "{enc_plan['unidad_nombre']}"`.
            2. Las tareas deben profundizar o aplicar desde casa/laboratorio la sesión {enc_plan['sesion_en_unidad']}/{enc_plan['sesiones_unidad']} de esta unidad, siendo DIFERENTES a la dinámica presencial del sílabo y a las tareas de guías previas.
            3. Asigna `"numero_encuentro": {encuentro}`, `"fecha": "{tiempos['fecha_encuentro']}"`, `"periodo_tiempo_programado_N": "{presupuesto['corte']}"`, fechas de entrega dentro de [{tiempos['fecha_entrega_min']} .. {tiempos['fecha_entrega_max']}], tiempos que sumen ~{tiempos['min_indep_objetivo']} minutos y puntajes que sumen {presupuesto['presupuesto_objetivo']} puntos (<= {presupuesto['presupuesto_max']}).
            4. Utiliza tipos de objetivo (`Conceptual`, `Procedimental`, `Actitudinal`), técnicas e instrumentos variados entre las {numero_actividades} tareas.
            5. Sigue exactamente la misma estructura JSON que el ejemplo proporcionado, incluyendo solo bloques/campos hasta `tarea_{numero_actividades}`.
            """

            print("Prompt generado, enviando a la API...")
            logging.info("Prompt generado, enviando a la API...")

            config = get_default_config(modelo_seleccionado)

            data = generar_respuesta_ai(
                prompt_completo,
                modelo_seleccionado,
                tipo_respuesta="guia",
                **config,
            )
            data = normalizar_respuesta_guia(
                data,
                numero_actividades=numero_actividades,
                encuentro=encuentro,
                unidad_default=enc_plan["unidad_romano"],
                nombre_unidad_default=enc_plan["unidad_nombre"],
                unidad_forzada=enc_plan["unidad_romano"],
                fecha_objetivo=tiempos["fecha_encuentro"],
                corte_default=presupuesto["corte"],
                forzar_corte=True,
                presupuesto_objetivo=presupuesto["presupuesto_objetivo"],
                presupuesto_max=presupuesto["presupuesto_max"],
                forzar_exacto=presupuesto["es_ultimo_en_corte"],
                minutos_totales_objetivo=tiempos["min_indep_objetivo"],
                fecha_entrega_min=tiempos["fecha_entrega_min"],
                fecha_entrega_max=tiempos["fecha_entrega_max"],
                max_encuentros=max_guias,
            )

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
            max_guias = obtener_max_encuentros_guia()
            if silabo.encuentros > max_guias:
                context["mensaje_error"] = (
                    f"El encuentro {silabo.encuentros} corresponde al cierre de curso y no requiere guía de estudio independiente."
                )
            else:
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
            if request.POST.get('sin_evaluacion_dinamica'):
                silabo.actividad_aprendizaje = "No se realizará evaluación en clase"
                silabo.tecnica_evaluacion = []
                silabo.tipo_evaluacion = []
                silabo.periodo_tiempo_programado = ""
                silabo.tiempo_minutos = 0
                silabo.agente_evaluador = []
                silabo.instrumento_evaluacion = ""
                silabo.criterios_evaluacion = "No se realizará evaluación en clase"
                silabo.puntaje = 0
            else:
                silabo.actividad_aprendizaje = request.POST.get('actividad_aprendizaje')
                silabo.tecnica_evaluacion = request.POST.getlist('tecnica_evaluacion')
                silabo.tipo_evaluacion = request.POST.getlist('tipo_evaluacion')
                silabo.periodo_tiempo_programado = request.POST.get('periodo_tiempo_programado')
                silabo.tiempo_minutos = request.POST.get('tiempo_minutos') or 0
                silabo.agente_evaluador = request.POST.getlist('agente_evaluador')
                silabo.instrumento_evaluacion = request.POST.get('instrumento_evaluacion')
                silabo.criterios_evaluacion = request.POST.get('criterios_evaluacion')
                silabo.puntaje = request.POST.get('puntaje') or 0

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

    previous_scores = get_previous_scores(silabo.asignacion_plan, exclude_silabo_id=silabo.id)

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
        'previous_scores': previous_scores,
        'previous_scores_json': json.dumps(previous_scores),
    }

    return render(request, 'actualizar_silabo.html', context)


def vista_tutoriales(request):
    """
    Renderiza la página de tutoriales, obteniendo las URLs para los videos
    desde MinIO.
    """
    # Definimos las rutas de los videos en el bucket de MinIO
    login_video_path = 'tutoriales/Iniciarsecion.mp4'
    general_tutorial_path = 'tutoriales/tutorial.mp4'

    login_video_url = None
    general_tutorial_url = None

    try:
        # Buscamos y obtenemos la URL del video de inicio de sesión
        if default_storage.exists(login_video_path):
            login_video_url = default_storage.url(login_video_path)
        else:
            print(f"ADVERTENCIA: El video '{login_video_path}' no fue encontrado en MinIO.")

        # Buscamos y obtenemos la URL del video general
        if default_storage.exists(general_tutorial_path):
            general_tutorial_url = default_storage.url(general_tutorial_path)
        else:
            print(f"ADVERTENCIA: El video '{general_tutorial_path}' no fue encontrado en MinIO.")

    except Exception as e:
        print(f"ERROR: No se pudo obtener la URL de los videos desde MinIO. Detalle: {e}")

    # Creamos el contexto para la plantilla con las URLs de ambos videos y la APK.
    # El video general se usará para las secciones de sílabo y guía.
    contexto = {
        'login_video_url': login_video_url,
        'silabo_video_url': general_tutorial_url,
        'guia_video_url': general_tutorial_url,
        'apk_info': pwa_views.get_latest_apk_metadata(),
    }

    return render(request, 'tutoriales.html', contexto)

@login_required
def actualizar_guia(request, guia_id):
    """
    Vista para actualizar una guía existente de forma manual.
    """
    guia = get_object_or_404(Guia, id=guia_id)
    silabo = guia.silabo

    if request.method == 'POST':
        try:
            # --- Actualizar cada campo del objeto 'guia' con los datos de request.POST ---
            
            # Información General (campos no editables: silabo, numero_encuentro)
            guia.fecha = request.POST.get('fecha')
            guia.unidad = request.POST.get('unidad')
            guia.nombre_de_la_unidad = request.POST.get('nombre_de_la_unidad')

            # Tarea 1
            guia.tipo_objetivo_1 = request.POST.get('tipo_objetivo_1')
            guia.objetivo_aprendizaje_1 = request.POST.get('objetivo_aprendizaje_1')
            guia.contenido_tematico_1 = request.POST.get('contenido_tematico_1')
            guia.actividad_aprendizaje_1 = request.POST.get('actividad_aprendizaje_1')
            guia.tecnica_evaluacion_1 = request.POST.get('tecnica_evaluacion_1')
            guia.tipo_evaluacion_1 = request.POST.get('tipo_evaluacion_1')
            guia.instrumento_evaluacion_1 = request.POST.get('instrumento_evaluacion_1')
            guia.criterios_evaluacion_1 = request.POST.get('criterios_evaluacion_1')
            guia.agente_evaluador_1 = request.POST.getlist('agente_evaluador_1')
            guia.tiempo_minutos_1 = request.POST.get('tiempo_minutos_1') or None
            guia.recursos_didacticos_1 = request.POST.get('recursos_didacticos_1')
            guia.periodo_tiempo_programado_1 = request.POST.get('periodo_tiempo_programado_1')
            guia.puntaje_1 = request.POST.get('puntaje_1') or None
            guia.fecha_entrega_1 = request.POST.get('fecha_entrega_1') or None

            # Tarea 2
            guia.tipo_objetivo_2 = request.POST.get('tipo_objetivo_2')
            guia.objetivo_aprendizaje_2 = request.POST.get('objetivo_aprendizaje_2')
            guia.contenido_tematico_2 = request.POST.get('contenido_tematico_2')
            guia.actividad_aprendizaje_2 = request.POST.get('actividad_aprendizaje_2')
            guia.tecnica_evaluacion_2 = request.POST.get('tecnica_evaluacion_2')
            guia.tipo_evaluacion_2 = request.POST.get('tipo_evaluacion_2')
            guia.instrumento_evaluacion_2 = request.POST.get('instrumento_evaluacion_2')
            guia.criterios_evaluacion_2 = request.POST.get('criterios_evaluacion_2')
            guia.agente_evaluador_2 = request.POST.getlist('agente_evaluador_2')
            guia.tiempo_minutos_2 = request.POST.get('tiempo_minutos_2') or None
            guia.recursos_didacticos_2 = request.POST.get('recursos_didacticos_2')
            guia.periodo_tiempo_programado_2 = request.POST.get('periodo_tiempo_programado_2')
            guia.puntaje_2 = request.POST.get('puntaje_2') or None
            guia.fecha_entrega_2 = request.POST.get('fecha_entrega_2') or None

            # Tarea 3
            guia.tipo_objetivo_3 = request.POST.get('tipo_objetivo_3')
            guia.objetivo_aprendizaje_3 = request.POST.get('objetivo_aprendizaje_3')
            guia.contenido_tematico_3 = request.POST.get('contenido_tematico_3')
            guia.actividad_aprendizaje_3 = request.POST.get('actividad_aprendizaje_3')
            guia.tecnica_evaluacion_3 = request.POST.get('tecnica_evaluacion_3')
            guia.tipo_evaluacion_3 = request.POST.get('tipo_evaluacion_3')
            guia.instrumento_evaluacion_3 = request.POST.get('instrumento_evaluacion_3')
            guia.criterios_evaluacion_3 = request.POST.get('criterios_evaluacion_3')
            guia.agente_evaluador_3 = request.POST.getlist('agente_evaluador_3')
            guia.tiempo_minutos_3 = request.POST.get('tiempo_minutos_3') or None
            guia.recursos_didacticos_3 = request.POST.get('recursos_didacticos_3')
            guia.periodo_tiempo_programado_3 = request.POST.get('periodo_tiempo_programado_3')
            guia.puntaje_3 = request.POST.get('puntaje_3') or None
            guia.fecha_entrega_3 = request.POST.get('fecha_entrega_3') or None

            # Tarea 4
            guia.tipo_objetivo_4 = request.POST.get('tipo_objetivo_4')
            guia.objetivo_aprendizaje_4 = request.POST.get('objetivo_aprendizaje_4')
            guia.contenido_tematico_4 = request.POST.get('contenido_tematico_4')
            guia.actividad_aprendizaje_4 = request.POST.get('actividad_aprendizaje_4')
            guia.tecnica_evaluacion_4 = request.POST.get('tecnica_evaluacion_4')
            guia.tipo_evaluacion_4 = request.POST.get('tipo_evaluacion_4')
            guia.instrumento_evaluacion_4 = request.POST.get('instrumento_evaluacion_4')
            guia.criterios_evaluacion_4 = request.POST.get('criterios_evaluacion_4')
            guia.agente_evaluador_4 = request.POST.getlist('agente_evaluador_4')
            guia.tiempo_minutos_4 = request.POST.get('tiempo_minutos_4') or None
            guia.recursos_didacticos_4 = request.POST.get('recursos_didacticos_4')
            guia.periodo_tiempo_programado_4 = request.POST.get('periodo_tiempo_programado_4')
            guia.puntaje_4 = request.POST.get('puntaje_4') or None
            guia.fecha_entrega_4 = request.POST.get('fecha_entrega_4') or None

            guia.full_clean()
            guia.save()

            messages.success(request, '¡La guía ha sido actualizada correctamente!')
            # Redirigir a la vista de detalle con el código del plan y un ancla al encuentro
            codigo_plan = guia.silabo.asignacion_plan.plan_de_estudio.codigo
            url_redirect = reverse('detalle_silabo_codigo', kwargs={'codigo': codigo_plan})
            # El ancla #guia-{{codigo}}-{{encuentro}} es manejado por el JS en el frontend para mostrar la página correcta
            return redirect(f'{url_redirect}?encuentro={guia.numero_encuentro}#guia-{codigo_plan}-{guia.numero_encuentro}')

        except ValidationError as e:
           # Capturamos los errores de validación del modelo
           error_dict = e.message_dict
           error_messages = []
           # Iteramos sobre los errores para crear mensajes más claros
           for field, errors in error_dict.items():
               # Obtenemos el nombre legible del campo desde el modelo
               field_verbose_name = Guia._meta.get_field(field).verbose_name
               # Creamos un mensaje de error específico
               error_messages.append(f"Error en el campo '{field_verbose_name}': {'; '.join(errors)}")
           
           # Unimos todos los mensajes de error en un solo mensaje para el usuario
           final_error_message = "Error de validación. " + " ".join(error_messages)
           messages.error(request, final_error_message)
           pass

    previous_scores = get_previous_scores(silabo.asignacion_plan, exclude_guia_id=guia.id)

    context = {
        'guia': guia,
        'silabo': silabo,
        'asignacion': silabo.asignacion_plan,
        'encuentro': silabo.encuentros,
        'UNIDAD_LIST': Silabo.UNIDAD_LIST,
        'TIPO_OBJETIVO_LIST': Guia.TIPO_OBJETIVO_LIST,
        'TECNICA_EVALUACION_LIST': Silabo.TECNICA_EVALUACION_LIST,
        'TIPO_EVALUACION_LIST': Silabo.TIPO_EVALUACION_LIST,
        'INSTRUMENTO_EVALUACION_LIST': Silabo.INSTRUMENTO_EVALUACION_LIST,
        'AGENTE_EVALUADOR_LIST': Silabo.AGENTE_EVALUADOR_LIST,
        'PERIODO_TIEMPO_LIST': Silabo.PERIODO_TIEMPO_LIST,
        'previous_scores': previous_scores,
        'previous_scores_json': json.dumps(previous_scores),
    }

    return render(request, 'actualizar_guia.html', context)
from django.contrib.auth import login as auth_login
from .services.google_classroom import iniciar_autorizacion, manejar_callback_google

def google_authorize_view(request):
    """Vista que redirige a Google para inicio de sesión y obtención de tokens"""
    url_autorizacion = iniciar_autorizacion(request)
    return redirect(url_autorizacion)

def google_oauth2callback_view(request):
    """La URL a la que Google enviará de regreso al usuario (Redirect URI)"""
    # Verificamos si Google retornó un error
    if 'error' in request.GET:
        messages.error(request, 'Autorización denegada o cancelada por el usuario.')
        return redirect('login' if not request.user.is_authenticated else 'admin:index')
        
    try:
        usuario, es_nuevo_login = manejar_callback_google(request)
        if usuario:
            if es_nuevo_login:
                auth_login(request, usuario)
                messages.success(request, '¡Has iniciado sesión con Google exitosamente!')
                return redirect('inicio')
            else:
                messages.success(request, '¡Tu cuenta de Google Classroom ha sido vinculada exitosamente!')
    except Exception as e:
        messages.error(request, f'{str(e)}')
        if not request.user.is_authenticated:
            return redirect('login')
        
    # Redirigimos de vuelta al admin de Django después del proceso de vinculación
    return redirect('admin:index')

def politicas_privacidad(request):
    """Renderiza la página de políticas de privacidad para la verificación de OAuth."""
    return render(request, 'privacidad.html')

def terminos_servicio(request):
    """Renderiza la página de Términos de Servicio para la verificación de OAuth."""
    return render(request, 'terminos.html')


@login_required
def ver_planeacion(request, asignacion_id):
    """
    Vista e interfaz intuitiva para visualizar toda la planeación (sílabos y guías por encuentro)
    asociada a una AsignacionPlanEstudio específica.
    """
    asignacion = get_object_or_404(AsignacionPlanEstudio, pk=asignacion_id)
    
    # Obtener sílabos asociados a la asignación, ordenados por número de encuentro
    silabos = Silabo.objects.filter(asignacion_plan=asignacion).order_by('encuentros')
    silabo_map = {s.encuentros: s for s in silabos}
    
    # Obtener guías asociadas a los sílabos de esta asignación
    guias = Guia.objects.filter(silabo__in=silabos)
    guia_map = {}
    for g in guias:
        if g.silabo_id and g.silabo:
            guia_map[g.silabo.encuentros] = g
        elif g.numero_encuentro:
            guia_map[g.numero_encuentro] = g

    def extract_tareas(guia):
        if not guia:
            return []
        tareas = []
        for i in (1, 2, 3, 4):
            obj = getattr(guia, f'objetivo_aprendizaje_{i}', None)
            act = getattr(guia, f'actividad_aprendizaje_{i}', None)
            cont = getattr(guia, f'contenido_tematico_{i}', None)
            if obj or act or cont:
                tareas.append({
                    'num': i,
                    'tipo_objetivo': getattr(guia, f'tipo_objetivo_{i}', '') or '',
                    'objetivo': obj or '',
                    'contenido': cont or '',
                    'actividad': act or '',
                    'tecnica': getattr(guia, f'tecnica_evaluacion_{i}', '') or '',
                    'tipo_evaluacion': getattr(guia, f'tipo_evaluacion_{i}', '') or '',
                    'instrumento': getattr(guia, f'instrumento_evaluacion_{i}', '') or '',
                    'criterios': getattr(guia, f'criterios_evaluacion_{i}', '') or '',
                    'agente': getattr(guia, f'agente_evaluador_{i}', '') or '',
                    'tiempo': getattr(guia, f'tiempo_minutos_{i}', None),
                    'recursos': getattr(guia, f'recursos_didacticos_{i}', '') or '',
                    'periodo': getattr(guia, f'periodo_tiempo_programado_{i}', '') or '',
                    'puntaje': getattr(guia, f'puntaje_{i}', None),
                    'fecha_entrega': getattr(guia, f'fecha_entrega_{i}', None),
                })
        return tareas

    encuentros_list = []
    max_guias = obtener_max_encuentros_guia()
    total_encuentros = TOTAL_ENCUENTROS_SILABO
    if silabos.exists():
        max_enc = max([s.encuentros for s in silabos] + [TOTAL_ENCUENTROS_SILABO])
        total_encuentros = max_enc

    for num in range(1, total_encuentros + 1):
        silabo_item = silabo_map.get(num)
        guia_item = guia_map.get(num)
        
        if not guia_item and silabo_item:
            g_qs = Guia.objects.filter(silabo=silabo_item)
            if g_qs.exists():
                guia_item = g_qs.first()
                
        tareas_list = extract_tareas(guia_item)
        tiene_silabo = silabo_item is not None
        tiene_guia = guia_item is not None and len(tareas_list) > 0
        requiere_guia = (num <= max_guias) or tiene_guia
        
        encuentros_list.append({
            'numero': num,
            'silabo': silabo_item,
            'guia': guia_item,
            'tareas': tareas_list,
            'tiene_silabo': tiene_silabo,
            'tiene_guia': tiene_guia,
            'requiere_guia': requiere_guia,
            'completo': tiene_silabo and (tiene_guia or not requiere_guia),
        })

    silabos_count = len([e for e in encuentros_list if e['tiene_silabo']])
    guias_count = len([e for e in encuentros_list if e['tiene_guia']])

    context = {
        'asignacion': asignacion,
        'encuentros_list': encuentros_list,
        'silabos_count': silabos_count,
        'guias_count': guias_count,
        'max_guias': max_guias,
        'total_encuentros': total_encuentros,
    }
    return render(request, 'ver_planeacion.html', context)


@login_required
def ranking_docentes(request):
    """
    Tablero de ranking y seguimiento de cumplimiento docente para sus asignaciones
    (sílabos y guías didácticas por encuentro).
    """
    config_sistema = ConfiguracionSistema.get_solo()
    ranking_visible_docentes = config_sistema.mostrar_ranking_docentes
    es_admin = request.user.is_staff or request.user.is_superuser

    if not ranking_visible_docentes and not es_admin:
        messages.warning(
            request,
            "La sección de Ranking Docente está habilitada únicamente para administradores en este momento.",
        )
        return redirect("inicio")

    alcance_param = request.GET.get("alcance", "").strip()
    alcance_explicito = alcance_param in ("actual", "todas")
    alcance = alcance_param if alcance_explicito else "actual"
    orden = request.GET.get("orden", "mayor").strip()

    carrera_raw = request.GET.get("carrera", "").strip()
    carrera_id = int(carrera_raw) if carrera_raw.isdigit() else None

    trimestre_raw = request.GET.get("trimestre", "").strip()
    valid_trimestres = {code for code, _ in TRIMESTRES_ROMANOS}
    trimestre = trimestre_raw if trimestre_raw in valid_trimestres else None

    trimestre_lectivo_raw = request.GET.get("trimestre_lectivo", "").strip()
    trimestre_lectivo = (
        trimestre_lectivo_raw if parsear_trimestre_lectivo(trimestre_lectivo_raw) else None
    )

    estado = request.GET.get("estado", "todos").strip()
    valid_estados = {"todos", "cumplido", "en_progreso", "pendientes", "sin_avance"}
    if estado not in valid_estados:
        estado = "todos"

    query = request.GET.get("q", "").strip()

    ranking_data = construir_ranking_docentes(
        alcance=alcance,
        orden=orden,
        carrera_id=carrera_id,
        trimestre=trimestre,
        trimestre_lectivo=trimestre_lectivo,
        estado=estado,
        query=query,
        alcance_explicito=alcance_explicito,
    )

    hay_filtros_activos = bool(
        query or carrera_id or trimestre or trimestre_lectivo or estado != "todos"
    )

    context = {
        **ranking_data,
        "usuario": request.user.get_full_name() or request.user.username,
        "es_admin": es_admin,
        "ranking_visible_docentes": ranking_visible_docentes,
        "filtro_carrera": str(carrera_id) if carrera_id else "",
        "filtro_trimestre": trimestre or "",
        "filtro_trimestre_lectivo": trimestre_lectivo or "",
        "filtro_estado": estado,
        "filtro_q": query,
        "hay_filtros_activos": hay_filtros_activos,
    }
    return render(request, "ranking_docentes.html", context)

