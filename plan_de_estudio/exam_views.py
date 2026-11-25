"""
Vistas para el módulo de Proyecto de Examen (Evaluación 1 en E4, Evaluación 2 en E8, Evaluación 3 en E11):
- Formulario de creación y edición con ítems dinámicos, medidor en vivo de páginas (>2.0) y puntaje automático restante
- Generación asistida con IA (4 a 8 hojas configurables)
- Vista de detalle por asignación (accesible desde Ver Datos y pantalla de Éxito)
- Descarga de Word (.docx) basada en copia de la plantilla institucional UML
"""

import datetime
from decimal import Decimal
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .ai_generators import generar_respuesta_ai, get_default_config
from .documento_proyecto_examen import generar_documento_proyecto_examen
from .models import (
    AsignacionPlanEstudio,
    CORTE_POR_EVALUACION,
    ENCUENTRO_POR_EVALUACION,
    Guia,
    ModeloIAConfig,
    ProyectoExamen,
    Silabo,
)
from .trimestre_utils import parsear_trimestre_lectivo
from .utils.ai_normalizer import normalizar_respuesta_examen
from .utils.curriculum_planner import (
    ENCUENTROS_POR_CORTE,
    construir_mapa_maestro,
    extraer_contexto_asignatura,
)
from .utils.exam_utils import (
    MAX_HOJAS_IA,
    MIN_HOJAS_IA,
    MIN_PAGINAS_EXAMEN_EXCLUSIVO,
    calcular_puntaje_examen_disponible,
    obtener_estado_examenes_asignacion,
    validar_items_examen,
)

logger = logging.getLogger(__name__)


def _tiene_permiso_asignacion(user, asignacion):
    return bool(user and (user.is_staff or user.is_superuser or asignacion.usuario_id == user.id))


def _sincronizar_contadores_asignacion(asignacion):
    silabos_db = asignacion.silabo_set.count()
    guias_db = Guia.objects.filter(silabo__asignacion_plan=asignacion).count()
    examenes_db = ProyectoExamen.objects.filter(asignacion_plan=asignacion).count()
    campos = []
    if silabos_db > 0 and asignacion.silabos_creados != silabos_db:
        asignacion.silabos_creados = silabos_db
        campos.append("silabos_creados")
    if guias_db > 0 and asignacion.guias_creadas != guias_db:
        asignacion.guias_creadas = guias_db
        campos.append("guias_creadas")
    if examenes_db > 0 and asignacion.examenes_creados != examenes_db:
        asignacion.examenes_creados = examenes_db
        campos.append("examenes_creados")
    if campos:
        asignacion.save(update_fields=campos)


def _datos_defecto_encabezado(asignacion, numero_evaluacion):
    encuentro = ENCUENTRO_POR_EVALUACION[numero_evaluacion]
    silabo_hito = Silabo.objects.filter(
        asignacion_plan=asignacion, encuentros=encuentro
    ).first()
    fecha_def = silabo_hito.fecha if (silabo_hito and silabo_hito.fecha) else datetime.date.today()

    parsed = parsear_trimestre_lectivo(asignacion.trimestre_lectivo)
    if parsed:
        anio_lectivo, trim_lectivo = str(parsed[0]), str(parsed[1])
    else:
        anio_lectivo = str(fecha_def.year)
        trim_lectivo = asignacion.plan_de_estudio.trimestre or "I"

    return {
        "silabo_hito": silabo_hito,
        "fecha": fecha_def,
        "anio_lectivo": anio_lectivo,
        "trimestre": trim_lectivo,
        "carrera_texto": asignacion.plan_de_estudio.carrera.nombre,
    }


def _construir_contexto_corte_para_ia(asignacion, numero_evaluacion):
    corte = CORTE_POR_EVALUACION[numero_evaluacion]
    encuentros_corte = ENCUENTROS_POR_CORTE[corte]

    silabos = list(
        Silabo.objects.filter(
            asignacion_plan=asignacion, encuentros__in=encuentros_corte
        ).order_by("encuentros")
    )
    guias = list(
        Guia.objects.filter(
            silabo__asignacion_plan=asignacion,
            numero_encuentro__in=encuentros_corte,
        ).order_by("numero_encuentro")
    )

    lineas_corte = []
    for s in silabos:
        lineas_corte.append(
            f"- Encuentro {s.encuentros} ({s.unidad} — {s.nombre_de_la_unidad} | {s.fecha}):\n"
            f"  Contenido: {s.contenido_tematico}\n"
            f"  Objetivos: Conceptual={s.objetivo_conceptual}; Procedimental={s.objetivo_procedimental}; Actitudinal={s.objetivo_actitudinal}\n"
            f"  Teoría: {s.clase_teorica[:280]} | Práctica: {s.clase_practica[:280]}"
        )
    for g in guias:
        tareas = []
        for idx in range(1, 5):
            tema = getattr(g, f"contenido_tematico_{idx}", None)
            act = getattr(g, f"actividad_aprendizaje_{idx}", None)
            if tema or act:
                tareas.append(f"T{idx}: {tema or ''} ({act or ''})"[:180])
        if tareas:
            lineas_corte.append(f"  Guía E{g.numero_encuentro}: " + " | ".join(tareas))

    resumen_programa = ""
    try:
        ctx_info = extraer_contexto_asignatura(asignacion.plan_de_estudio)
        mapa = construir_mapa_maestro(ctx_info["unidades"])
        unidades_corte = []
        vistas = set()
        for enc in encuentros_corte:
            info_e = mapa["por_encuentro"].get(enc)
            if info_e and info_e["unidad_numero"] not in vistas:
                vistas.add(info_e["unidad_numero"])
                u = info_e["unidad_dict"]
                unidades_corte.append(
                    f"* {info_e['unidad_romano']} — {u['nombre']}:\n"
                    f"  Objetivos específicos: {u['objetivos'][:600]}\n"
                    f"  Contenido temático: {u['contenido'][:800]}"
                )
        resumen_programa = "\n".join(unidades_corte)
    except ValueError:
        resumen_programa = "Programa de asignatura no cargado; básese estrictamente en los sílabos y guías del corte."

    return {
        "corte": corte,
        "encuentros_corte": encuentros_corte,
        "resumen_silabos": "\n".join(lineas_corte) or "Sin sílabos detallados para este corte.",
        "resumen_programa": resumen_programa,
    }


@login_required
def ver_formulario_examen(request, asignacion_id):
    """Muestra el formulario para crear el Proyecto de Examen desbloqueado."""
    asignacion = get_object_or_404(
        AsignacionPlanEstudio.objects.select_related(
            "plan_de_estudio",
            "plan_de_estudio__asignatura",
            "plan_de_estudio__carrera",
            "usuario",
        ),
        id=asignacion_id,
    )
    if not _tiene_permiso_asignacion(request.user, asignacion):
        messages.error(request, "No tienes permiso para acceder a esta asignación.")
        return redirect("inicio")

    _sincronizar_contadores_asignacion(asignacion)
    estado = obtener_estado_examenes_asignacion(asignacion)

    eval_param = request.GET.get("evaluacion")
    num_eval = None
    if eval_param and str(eval_param).isdigit():
        cand = int(eval_param)
        if cand in (1, 2, 3):
            existente = ProyectoExamen.objects.filter(
                asignacion_plan=asignacion, numero_evaluacion=cand
            ).first()
            if existente:
                return redirect("actualizar_examen", examen_id=existente.id)
            enc_req = ENCUENTRO_POR_EVALUACION[cand]
            if estado["silabos_creados"] >= enc_req:
                num_eval = cand
            else:
                messages.warning(
                    request,
                    f"La Evaluación #{cand} (Encuentro {enc_req}) solo se activa al completar el sílabo del encuentro {enc_req}.",
                )
                return redirect("inicio")

    if num_eval is None:
        if not estado["puede_generar_examen"]:
            messages.warning(request, estado["razon_bloqueo_examen"])
            return redirect("inicio")
        num_eval = estado["siguiente_evaluacion"]

    puntaje_info = calcular_puntaje_examen_disponible(asignacion, num_eval)
    defaults = _datos_defecto_encabezado(asignacion, num_eval)
    plan_tematico = asignacion.plan_de_estudio.get_plan_tematico_efectivo()
    programa_2026 = asignacion.plan_de_estudio.programas_2026_asociados.first()
    mostrar_ia = bool(plan_tematico) or bool(programa_2026) or asignacion.silabo_set.exists()
    modelos_ia = ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by("orden", "id")

    context = {
        "modo_edicion": False,
        "examen": None,
        "asignacion": asignacion,
        "usuario": request.user.username,
        "numero_evaluacion": num_eval,
        "encuentro": ENCUENTRO_POR_EVALUACION[num_eval],
        "periodo_corte": CORTE_POR_EVALUACION[num_eval],
        "puntaje_info": puntaje_info,
        "fecha_inicial": defaults["fecha"].isoformat(),
        "anio_lectivo_inicial": defaults["anio_lectivo"],
        "trimestre_inicial": defaults["trimestre"],
        "carrera_inicial": defaults["carrera_texto"],
        "codigo_grupo_inicial": "",
        "modalidad_inicial": "Por encuentro",
        "tipo_examen_inicial": "De corte evaluativo",
        "municipio_inicial": "Municipio Jalapa",
        "items_iniciales_json": json.dumps([], ensure_ascii=False),
        "modalidad_choices": ProyectoExamen.MODALIDAD_CHOICES,
        "tipo_examen_choices": ProyectoExamen.TIPO_EXAMEN_CHOICES,
        "hojas_ia_opciones": list(range(MIN_HOJAS_IA, MAX_HOJAS_IA + 1)),
        "min_paginas_exclusivo": MIN_PAGINAS_EXAMEN_EXCLUSIVO,
        "mostrar_ia": mostrar_ia,
        "modelos_ia": modelos_ia,
    }
    return render(request, "formulario_examen.html", context)


@login_required
def actualizar_examen(request, examen_id):
    """Muestra el formulario para editar un Proyecto de Examen ya creado."""
    examen = get_object_or_404(
        ProyectoExamen.objects.select_related(
            "asignacion_plan",
            "asignacion_plan__plan_de_estudio",
            "asignacion_plan__plan_de_estudio__asignatura",
            "asignacion_plan__plan_de_estudio__carrera",
            "asignacion_plan__usuario",
        ),
        id=examen_id,
    )
    asignacion = examen.asignacion_plan
    if not _tiene_permiso_asignacion(request.user, asignacion):
        messages.error(request, "No tienes permiso para editar este proyecto de examen.")
        return redirect("inicio")

    puntaje_info = calcular_puntaje_examen_disponible(asignacion, examen.numero_evaluacion)
    plan_tematico = asignacion.plan_de_estudio.get_plan_tematico_efectivo()
    programa_2026 = asignacion.plan_de_estudio.programas_2026_asociados.first()
    mostrar_ia = bool(plan_tematico) or bool(programa_2026) or asignacion.silabo_set.exists()
    modelos_ia = ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by("orden", "id")

    context = {
        "modo_edicion": True,
        "examen": examen,
        "asignacion": asignacion,
        "usuario": request.user.username,
        "numero_evaluacion": examen.numero_evaluacion,
        "encuentro": examen.encuentro,
        "periodo_corte": examen.periodo_corte,
        "puntaje_info": puntaje_info,
        "fecha_inicial": examen.fecha.isoformat() if examen.fecha else datetime.date.today().isoformat(),
        "anio_lectivo_inicial": examen.anio_lectivo,
        "trimestre_inicial": examen.trimestre,
        "carrera_inicial": examen.carrera_texto or asignacion.plan_de_estudio.carrera.nombre,
        "codigo_grupo_inicial": examen.codigo_grupo,
        "modalidad_inicial": examen.modalidad,
        "tipo_examen_inicial": examen.tipo_examen,
        "municipio_inicial": examen.municipio or "Municipio Jalapa",
        "items_iniciales_json": json.dumps(examen.items_json or [], ensure_ascii=False),
        "modalidad_choices": ProyectoExamen.MODALIDAD_CHOICES,
        "tipo_examen_choices": ProyectoExamen.TIPO_EXAMEN_CHOICES,
        "hojas_ia_opciones": list(range(MIN_HOJAS_IA, MAX_HOJAS_IA + 1)),
        "min_paginas_exclusivo": MIN_PAGINAS_EXAMEN_EXCLUSIVO,
        "mostrar_ia": mostrar_ia,
        "modelos_ia": modelos_ia,
    }
    return render(request, "formulario_examen.html", context)


@login_required
def guardar_examen(request, asignacion_id):
    """Guarda (crea o actualiza) un Proyecto de Examen validando desbloqueo, puntaje exacto y > 2 páginas."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
    if not _tiene_permiso_asignacion(request.user, asignacion):
        return JsonResponse({"success": False, "error": "Sin permisos sobre esta asignación."}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Formato JSON inválido."}, status=400)

    _sincronizar_contadores_asignacion(asignacion)

    try:
        num_eval = int(data.get("numero_evaluacion"))
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "Número de evaluación inválido (debe ser 1, 2 o 3)."}, status=400)

    if num_eval not in (1, 2, 3):
        return JsonResponse({"success": False, "error": "Número de evaluación inválido (debe ser 1, 2 o 3)."}, status=400)

    enc_hito = ENCUENTRO_POR_EVALUACION[num_eval]
    corte = CORTE_POR_EVALUACION[num_eval]

    examen_id = data.get("examen_id")
    if examen_id:
        examen = get_object_or_404(ProyectoExamen, id=examen_id, asignacion_plan=asignacion)
        num_eval = examen.numero_evaluacion
        enc_hito = examen.encuentro
        corte = examen.periodo_corte
    else:
        examen = ProyectoExamen.objects.filter(
            asignacion_plan=asignacion, numero_evaluacion=num_eval
        ).first()
        if examen is None:
            silabos_count = max(asignacion.silabos_creados or 0, asignacion.silabo_set.count())
            if silabos_count < enc_hito:
                return JsonResponse(
                    {
                        "success": False,
                        "error": (
                            f"El Proyecto de Examen #{num_eval} solo se habilita después de completar "
                            f"el sílabo del encuentro {enc_hito} (sílabos actuales: {silabos_count})."
                        ),
                    },
                    status=400,
                )

    puntaje_info = calcular_puntaje_examen_disponible(asignacion, num_eval)
    puntaje_requerido = puntaje_info["puntaje_disponible"]
    if puntaje_info["bloqueado_por_puntaje"]:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"No quedan puntos disponibles en {corte} (acumulado actual: "
                    f"{puntaje_info['acumulado_total']}/100 pts entre sílabos y guías). "
                    "Corrija primero los puntajes de sus sílabos o guías de este corte."
                ),
            },
            status=400,
        )

    es_valido, items_limpios, errores, estimacion = validar_items_examen(
        data.get("items"), puntaje_requerido
    )
    if not es_valido:
        return JsonResponse(
            {
                "success": False,
                "error": " ".join(errores),
                "errors": errores,
                "estimacion": estimacion,
            },
            status=400,
        )

    fecha_raw = str(data.get("fecha") or "").strip()
    try:
        fecha_obj = datetime.date.fromisoformat(fecha_raw[:10])
    except ValueError:
        return JsonResponse({"success": False, "error": "La fecha del examen no es válida."}, status=400)

    modalidad = str(data.get("modalidad") or "Por encuentro").strip()
    if modalidad not in dict(ProyectoExamen.MODALIDAD_CHOICES):
        modalidad = "Por encuentro"

    tipo_examen = str(data.get("tipo_examen") or "De corte evaluativo").strip()
    if tipo_examen not in dict(ProyectoExamen.TIPO_EXAMEN_CHOICES):
        tipo_examen = "De corte evaluativo"

    hojas_ia_raw = data.get("hojas_objetivo_ia")
    hojas_ia = None
    if hojas_ia_raw not in (None, "", 0, "0"):
        try:
            h_val = int(hojas_ia_raw)
            if MIN_HOJAS_IA <= h_val <= MAX_HOJAS_IA:
                hojas_ia = h_val
        except (ValueError, TypeError):
            hojas_ia = None

    defaults = _datos_defecto_encabezado(asignacion, num_eval)
    if examen is None:
        examen = ProyectoExamen(
            asignacion_plan=asignacion,
            numero_evaluacion=num_eval,
            encuentro=enc_hito,
            periodo_corte=corte,
        )

    examen.silabo = defaults["silabo_hito"]
    examen.fecha = fecha_obj
    examen.anio_lectivo = str(data.get("anio_lectivo") or defaults["anio_lectivo"]).strip()[:20]
    examen.trimestre = str(data.get("trimestre") or defaults["trimestre"]).strip()[:20]
    examen.codigo_grupo = str(data.get("codigo_grupo") or "").strip()[:100]
    examen.carrera_texto = str(data.get("carrera_texto") or defaults["carrera_texto"]).strip()[:255]
    examen.modalidad = modalidad
    examen.tipo_examen = tipo_examen
    examen.municipio = str(data.get("municipio") or "Municipio Jalapa").strip()[:100]
    examen.items_json = items_limpios
    examen.puntaje_total = sum(it["puntaje"] for it in items_limpios)
    examen.paginas_estimadas = min(
        Decimal("99.9"), Decimal(f"{float(estimacion['paginas_estimadas']):.1f}")
    )
    if hojas_ia is not None:
        examen.hojas_objetivo_ia = hojas_ia

    examen.full_clean()
    examen.save()

    asignacion.examenes_creados = ProyectoExamen.objects.filter(asignacion_plan=asignacion).count()
    asignacion.save(update_fields=["examenes_creados"])

    success_url = f"{reverse('success_view')}?examen_id={examen.id}"
    download_url = reverse("descargar_proyecto_examen", args=[examen.id])

    return JsonResponse(
        {
            "success": True,
            "message": f"Proyecto de Examen #{examen.numero_evaluacion} guardado correctamente.",
            "examen_id": examen.id,
            "puntaje_total": examen.puntaje_total,
            "paginas_estimadas": float(examen.paginas_estimadas),
            "redirect_url": success_url,
            "download_url": download_url,
        }
    )


@login_required
def generar_proyecto_examen(request):
    """Genera el contenido completo del Proyecto de Examen usando IA calibrado entre 4 y 8 hojas."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Método no permitido"}, status=405)

    asignacion_id = request.POST.get("asignacion_id")
    numero_eval_raw = request.POST.get("numero_evaluacion")
    modelo_seleccionado = request.POST.get("modelo_select", "google")
    hojas_raw = request.POST.get("numero_hojas", str(MIN_HOJAS_IA))

    try:
        num_eval = int(numero_eval_raw)
        if num_eval not in (1, 2, 3):
            raise ValueError()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Número de evaluación inválido (1, 2 o 3)."}, status=400)

    try:
        numero_hojas = int(hojas_raw)
    except (ValueError, TypeError):
        return JsonResponse({"error": f"La cantidad de hojas debe estar entre {MIN_HOJAS_IA} y {MAX_HOJAS_IA}."}, status=400)

    if numero_hojas < MIN_HOJAS_IA or numero_hojas > MAX_HOJAS_IA:
        return JsonResponse(
            {"error": f"La IA solo genera proyectos de examen entre {MIN_HOJAS_IA} y {MAX_HOJAS_IA} hojas."},
            status=400,
        )

    asignacion = get_object_or_404(
        AsignacionPlanEstudio.objects.select_related(
            "plan_de_estudio",
            "plan_de_estudio__asignatura",
            "plan_de_estudio__carrera",
        ),
        id=asignacion_id,
    )
    if not _tiene_permiso_asignacion(request.user, asignacion):
        return JsonResponse({"error": "Sin permisos sobre esta asignación."}, status=403)

    enc_hito = ENCUENTRO_POR_EVALUACION[num_eval]
    silabos_count = max(asignacion.silabos_creados or 0, asignacion.silabo_set.count())
    if silabos_count < enc_hito and not ProyectoExamen.objects.filter(
        asignacion_plan=asignacion, numero_evaluacion=num_eval
    ).exists():
        return JsonResponse(
            {"error": f"Debe completar primero el sílabo del encuentro {enc_hito} para generar este examen."},
            status=400,
        )

    puntaje_info = calcular_puntaje_examen_disponible(asignacion, num_eval)
    puntaje_objetivo = puntaje_info["puntaje_disponible"]
    if puntaje_info["bloqueado_por_puntaje"]:
        return JsonResponse(
            {
                "error": (
                    f"No hay puntos disponibles en {puntaje_info['corte']} "
                    f"(acumulado actual: {puntaje_info['acumulado_total']}/100 pts). "
                    "Corrija primero los puntajes de sus sílabos o guías para liberar puntaje al examen."
                )
            },
            status=400,
        )

    contexto_corte = _construir_contexto_corte_para_ia(asignacion, num_eval)
    defaults = _datos_defecto_encabezado(asignacion, num_eval)

    # Calibración de densidad por cantidad de hojas horizontales (4 a 8 hojas)
    apartados_objetivo = min(10, max(5, numero_hojas + 1))
    lineas_meta = int(25 + (numero_hojas - 1) * 38)
    palabras_minimas = int(numero_hojas * 340)

    prompt_completo = f"""
Instrucciones: Eres un catedrático universitario especialista en evaluación educativa de la Universidad Martín Lutero (UML).
Debes diseñar el **PROYECTO DE EXAMEN** completo y riguroso para la Evaluación #{num_eval} ({contexto_corte['corte']}, Encuentro {enc_hito}) y devolverlo ÚNICAMENTE como un objeto JSON válido.

DATOS DE LA ASIGNATURA:
- Asignatura: {asignacion.plan_de_estudio.asignatura.nombre} ({asignacion.plan_de_estudio.codigo})
- Carrera: {asignacion.plan_de_estudio.carrera.nombre}
- Año/Trimestre del plan: {asignacion.plan_de_estudio.año} / {asignacion.plan_de_estudio.trimestre}
- Trimestre lectivo: {asignacion.trimestre_lectivo_display}
- Evaluación: #{num_eval} — {contexto_corte['corte']} (Encuentro {enc_hito})
- Fecha sugerida: {defaults['fecha'].isoformat()}

REGLAS OBLIGATORIAS DE PUNTAJE Y EXTENSIÓN ({numero_hojas} HOJAS):
1. PUNTAJE TOTAL EXACTO: La suma de `"puntaje"` de todos los apartados DEBE ser EXACTAMENTE **{puntaje_objetivo} puntos** (acumulado previo en sílabos+guías: {puntaje_info['acumulado_total']}/100 pts).
2. EXTENSIÓN OBLIGATORIA DE **{numero_hojas} HOJAS** EN FORMATO HORIZONTAL:
   - Diseña exactamente **{apartados_objetivo} apartados variados** (I, II, III, IV, ...), alcanzando al menos **{palabras_minimas} palabras reales** (~{lineas_meta} líneas de tabla) entre objetivos, ejercicios propuestos detallados y posibles respuestas completas.
   - NO redactes exámenes cortos ni superficiales. Cada apartado debe contener múltiples sub-ítems numerados (1, 2, 3, 4...), escenarios aplicados, casos prácticos contextualizados, problemas paso a paso, análisis crítico, cuadros comparativos, selección múltiple con justificación, verdadero/falso justificado o desarrollo argumentativo profundo.
   - En `"posibles_respuestas"` incluye la clave de respuesta completa, desarrollada y verificable (criterios detallados, cálculos paso a paso, respuestas exactas para cada sub-ítem; evita poner únicamente "Criterios propios" sin explicar los elementos mínimos que debe demostrar el estudiante).
3. COHERENCIA CURRICULAR ESTRICTA: Evalúa ÚNICAMENTE los contenidos y objetivos cubiertos en los encuentros {contexto_corte['encuentros_corte']} del {contexto_corte['corte']}.

PROGRAMA DE ASIGNATURA (UNIDADES DEL CORTE):
{contexto_corte['resumen_programa']}

SÍLABOS Y GUÍAS IMPARTIDOS EN EL {contexto_corte['corte'].upper()}:
{contexto_corte['resumen_silabos']}

FORMATO JSON EXACTO REQUERIDO:
{{
  "fecha": "{defaults['fecha'].isoformat()}",
  "anio_lectivo": "{defaults['anio_lectivo']}",
  "trimestre": "{defaults['trimestre']}",
  "items": [
    {{
      "numero": "I",
      "objetivo": "Objetivo de evaluación específico y medible alineado al corte.",
      "ejercicios": "I. [Tipo de ejercicio: Análisis de caso / Resolución de problemas / Selección múltiple / etc.]\\nInstrucciones claras para el estudiante...\\n1. Sub-ejercicio detallado...\\n2. Sub-ejercicio detallado...\\n3. Sub-ejercicio detallado...",
      "posibles_respuestas": "I. Solución modelo y criterios de calificación:\\n1. Respuesta completa esperada...\\n2. Respuesta completa esperada...\\n3. Respuesta completa esperada...",
      "puntaje": 10,
      "detalle_puntaje": "2 c/u = 10 pts"
    }}
  ]
}}

Devuelve únicamente el JSON válido sin texto adicional fuera del JSON.
"""

    try:
        config = get_default_config(modelo_seleccionado)
        # Asegurar suficiente presupuesto de tokens para exámenes extensos de 4-8 hojas
        if "max_output_tokens" in config:
            config["max_output_tokens"] = max(14000, config["max_output_tokens"])
        if "max_tokens" in config:
            config["max_tokens"] = max(12000, config["max_tokens"])

        raw_data = generar_respuesta_ai(
            prompt_completo,
            modelo_seleccionado,
            tipo_respuesta="examen",
            **config,
        )
        datos_norm = normalizar_respuesta_examen(
            raw_data,
            puntaje_objetivo=puntaje_objetivo,
            numero_hojas=numero_hojas,
            fecha_default=defaults["fecha"].isoformat(),
            anio_lectivo_default=defaults["anio_lectivo"],
            trimestre_default=defaults["trimestre"],
        )
        return JsonResponse(
            {
                "success": True,
                "datos": datos_norm,
                "estimacion": datos_norm["estimacion"],
            }
        )
    except Exception as e:
        logger.exception("Error al generar Proyecto de Examen con IA")
        return JsonResponse({"error": f"Error al generar el proyecto de examen: {str(e)}"}, status=500)


@login_required
def detalle_examenes(request, asignacion_id):
    """Vista dedicada para explorar, editar y descargar los 3 Proyectos de Examen de una asignación."""
    asignacion = get_object_or_404(
        AsignacionPlanEstudio.objects.select_related(
            "plan_de_estudio",
            "plan_de_estudio__asignatura",
            "plan_de_estudio__carrera",
            "usuario",
        ),
        id=asignacion_id,
    )
    if not _tiene_permiso_asignacion(request.user, asignacion):
        messages.error(request, "No tienes permiso para ver los exámenes de esta asignación.")
        return redirect("inicio")

    _sincronizar_contadores_asignacion(asignacion)
    examenes = list(
        ProyectoExamen.objects.filter(asignacion_plan=asignacion).order_by("numero_evaluacion")
    )
    examenes_map = {ex.numero_evaluacion: ex for ex in examenes}
    estado = obtener_estado_examenes_asignacion(asignacion, examenes_por_eval=examenes_map)

    slots = []
    for num_eval, enc_hito in ((1, 4), (2, 8), (3, 11)):
        ex = examenes_map.get(num_eval)
        puntaje_info = calcular_puntaje_examen_disponible(asignacion, num_eval)
        slots.append({
            "numero_evaluacion": num_eval,
            "encuentro": enc_hito,
            "corte": CORTE_POR_EVALUACION[num_eval],
            "examen": ex,
            "desbloqueado": estado["silabos_creados"] >= enc_hito,
            "puntaje_info": puntaje_info,
        })

    return render(
        request,
        "detalle_examenes.html",
        {
            "asignacion": asignacion,
            "usuario": request.user.get_full_name() or request.user.username,
            "slots": slots,
            "estado_examenes": estado,
        },
    )


@login_required
def descargar_proyecto_examen(request, examen_id):
    """Genera una copia de la plantilla oficial UML con los datos del examen y la envía como descarga .docx."""
    examen = get_object_or_404(
        ProyectoExamen.objects.select_related(
            "asignacion_plan",
            "asignacion_plan__plan_de_estudio",
            "asignacion_plan__plan_de_estudio__asignatura",
            "asignacion_plan__plan_de_estudio__carrera",
            "asignacion_plan__usuario",
        ),
        id=examen_id,
    )
    if not _tiene_permiso_asignacion(request.user, examen.asignacion_plan):
        return HttpResponse("No tienes permiso para descargar este documento.", status=403)

    output = generar_documento_proyecto_examen(examen)
    asig_limpia = "".join(
        c if (c.isalnum() or c in ("_", "-")) else "_"
        for c in examen.asignacion_plan.plan_de_estudio.asignatura.nombre
    ).strip("_")
    filename = f"Proyecto_Examen_Eval{examen.numero_evaluacion}_{asig_limpia}.docx"

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
