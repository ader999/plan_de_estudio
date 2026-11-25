import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.utils import timezone

from .models import (
    AsignacionPlanEstudio,
    Carrera,
    Guia,
    ProyectoExamen,
    TOTAL_ENCUENTROS_SILABO,
    TOTAL_EXAMENES,
    TRIMESTRES_ROMANOS,
    obtener_max_encuentros_guia,
)
from .trimestre_utils import (
    clave_orden_trimestre_lectivo,
    formatear_trimestre_lectivo,
    obtener_rango_por_trimestre_lectivo,
    obtener_trimestre_lectivo_de_fecha,
    ordenar_codigos_trimestre_lectivo,
    parsear_trimestre_lectivo,
)

ENCUENTROS_ESPERADOS = TOTAL_ENCUENTROS_SILABO
ENCUENTROS_SILABO_ESPERADOS = TOTAL_ENCUENTROS_SILABO
EXAMENES_ESPERADOS = TOTAL_EXAMENES
ENTREGABLES_POR_ASIGNACION = ENCUENTROS_SILABO_ESPERADOS + 10 + EXAMENES_ESPERADOS


def obtener_metas_ranking():
    """Devuelve (esperado_silabos, esperado_guias, esperado_examenes, esperado_entregables_por_asignacion)."""
    esperado_silabos = ENCUENTROS_SILABO_ESPERADOS
    esperado_guias = obtener_max_encuentros_guia()
    esperado_examenes = EXAMENES_ESPERADOS
    return (
        esperado_silabos,
        esperado_guias,
        esperado_examenes,
        esperado_silabos + esperado_guias + esperado_examenes,
    )


def obtener_rango_ciclo_actual(fecha_ref=None):
    """
    Calcula las fechas de inicio y fin del trimestre/ciclo calendario
    (Mar-May, Jun-Ago, Sep-Nov, Dic-Feb).
    """
    return obtener_rango_por_trimestre_lectivo(
        obtener_trimestre_lectivo_de_fecha(fecha_ref)
    )


def _get_foto_perfil(usuario):
    try:
        return usuario.credenciales_google.foto_perfil or ""
    except (AttributeError, ObjectDoesNotExist):
        return ""


def _iniciales_usuario(nombre_completo, username):
    partes = [p for p in (nombre_completo or "").split() if p]
    if len(partes) >= 2:
        return f"{partes[0][0]}{partes[1][0]}".upper()
    if partes:
        return partes[0][:2].upper()
    return (username or "DO")[:2].upper()


def _clasificar_estado(porcentaje):
    if porcentaje >= 100.0:
        return {
            "estado": "cumplido",
            "estado_label": "Al día (100%)",
            "badge_class": "bg-success",
            "progress_class": "bg-success",
            "border_class": "border-success",
        }
    if porcentaje >= 75.0:
        return {
            "estado": "avanzado",
            "estado_label": "Avanzado",
            "badge_class": "bg-primary",
            "progress_class": "bg-primary",
            "border_class": "border-primary",
        }
    if porcentaje > 0.0:
        return {
            "estado": "rezagado",
            "estado_label": "Con pendientes",
            "badge_class": "bg-warning text-dark",
            "progress_class": "bg-warning",
            "border_class": "border-warning",
        }
    return {
        "estado": "sin_avance",
        "estado_label": "Sin avance (0%)",
        "badge_class": "bg-danger",
        "progress_class": "bg-danger",
        "border_class": "border-danger",
    }


def _calcular_metricas_asignacion(
    asignacion,
    esperado_silabos=None,
    esperado_guias=None,
    esperado_examenes=None,
):
    if esperado_silabos is None or esperado_guias is None or esperado_examenes is None:
        meta_s, meta_g, meta_e, _ = obtener_metas_ranking()
        if esperado_silabos is None:
            esperado_silabos = meta_s
        if esperado_guias is None:
            esperado_guias = meta_g
        if esperado_examenes is None:
            esperado_examenes = meta_e

    esperado_total = esperado_silabos + esperado_guias + esperado_examenes

    silabos_db = getattr(asignacion, "silabos_db", None)
    if silabos_db is None:
        silabos_db = asignacion.silabo_set.count()
    guias_db = getattr(asignacion, "guias_db", None)
    if guias_db is None:
        guias_db = Guia.objects.filter(silabo__asignacion_plan=asignacion).count()
    examenes_db = getattr(asignacion, "examenes_db", None)
    if examenes_db is None:
        examenes_db = ProyectoExamen.objects.filter(asignacion_plan=asignacion).count()

    silabos = min(silabos_db if silabos_db > 0 else max(asignacion.silabos_creados or 0, 0), esperado_silabos)
    guias = min(guias_db if guias_db > 0 else max(asignacion.guias_creadas or 0, 0), esperado_guias)
    examenes = min(examenes_db if examenes_db > 0 else max(asignacion.examenes_creados or 0, 0), esperado_examenes)

    total_entregables = silabos + guias + examenes
    porcentaje = round((total_entregables / esperado_total) * 100, 1) if esperado_total > 0 else 0.0
    porcentaje_silabos = round((silabos / esperado_silabos) * 100, 1) if esperado_silabos > 0 else 0.0
    porcentaje_guias = round((guias / esperado_guias) * 100, 1) if esperado_guias > 0 else 0.0
    porcentaje_examenes = round((examenes / esperado_examenes) * 100, 1) if esperado_examenes > 0 else 0.0
    completada = (
        silabos >= esperado_silabos
        and guias >= esperado_guias
        and examenes >= esperado_examenes
    )
    sin_iniciar = silabos == 0 and guias == 0 and examenes == 0
    clasificacion = _clasificar_estado(porcentaje)

    plan = asignacion.plan_de_estudio
    return {
        "id": asignacion.id,
        "asignatura": plan.asignatura.nombre.upper(),
        "codigo": plan.codigo,
        "carrera": plan.carrera.nombre,
        "carrera_id": plan.carrera_id,
        "anio": plan.año,
        "trimestre": plan.trimestre,
        "trimestre_lectivo": asignacion.trimestre_lectivo,
        "trimestre_lectivo_display": asignacion.trimestre_lectivo_display,
        "pensol": plan.pensol,
        "bloque": asignacion.bloque or "Sin bloque",
        "fecha_asignacion": asignacion.fecha_asignacion,
        "silabos": silabos,
        "guias": guias,
        "examenes": examenes,
        "esperado_silabos": esperado_silabos,
        "esperado_guias": esperado_guias,
        "esperado_examenes": esperado_examenes,
        "esperado_por_tipo": esperado_silabos,
        "total_entregables": total_entregables,
        "esperado_total": esperado_total,
        "faltantes_silabos": max(0, esperado_silabos - silabos),
        "faltantes_guias": max(0, esperado_guias - guias),
        "faltantes_examenes": max(0, esperado_examenes - examenes),
        "faltantes_total": max(0, esperado_total - total_entregables),
        "porcentaje": porcentaje,
        "porcentaje_silabos": porcentaje_silabos,
        "porcentaje_guias": porcentaje_guias,
        "porcentaje_examenes": porcentaje_examenes,
        "completada": completada,
        "sin_iniciar": sin_iniciar,
        **clasificacion,
    }


def _agrupar_por_docente(
    asignaciones_qs,
    esperado_silabos=None,
    esperado_guias=None,
    esperado_examenes=None,
):
    if esperado_silabos is None or esperado_guias is None or esperado_examenes is None:
        meta_s, meta_g, meta_e, _ = obtener_metas_ranking()
        if esperado_silabos is None:
            esperado_silabos = meta_s
        if esperado_guias is None:
            esperado_guias = meta_g
        if esperado_examenes is None:
            esperado_examenes = meta_e

    esperado_por_asignacion = esperado_silabos + esperado_guias + esperado_examenes
    docentes_map = {}

    for asignacion in asignaciones_qs:
        usuario = asignacion.usuario
        uid = usuario.id
        metrica = _calcular_metricas_asignacion(
            asignacion,
            esperado_silabos=esperado_silabos,
            esperado_guias=esperado_guias,
            esperado_examenes=esperado_examenes,
        )

        if uid not in docentes_map:
            nombre_completo = f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username
            docentes_map[uid] = {
                "docente": usuario,
                "docente_id": uid,
                "nombre_completo": nombre_completo,
                "username": usuario.username,
                "iniciales": _iniciales_usuario(nombre_completo, usuario.username),
                "foto_perfil": _get_foto_perfil(usuario),
                "total_asignaciones": 0,
                "asignaciones_completadas": 0,
                "asignaciones_en_progreso": 0,
                "asignaciones_sin_iniciar": 0,
                "total_silabos": 0,
                "total_guias": 0,
                "total_examenes": 0,
                "ultima_fecha_asignacion": asignacion.fecha_asignacion,
                "asignaciones": [],
            }

        entry = docentes_map[uid]
        entry["total_asignaciones"] += 1
        if metrica["completada"]:
            entry["asignaciones_completadas"] += 1
        elif metrica["sin_iniciar"]:
            entry["asignaciones_sin_iniciar"] += 1
        else:
            entry["asignaciones_en_progreso"] += 1

        entry["total_silabos"] += metrica["silabos"]
        entry["total_guias"] += metrica["guias"]
        entry["total_examenes"] += metrica["examenes"]
        if asignacion.fecha_asignacion and (
            entry["ultima_fecha_asignacion"] is None
            or asignacion.fecha_asignacion > entry["ultima_fecha_asignacion"]
        ):
            entry["ultima_fecha_asignacion"] = asignacion.fecha_asignacion
        entry["asignaciones"].append(metrica)

    docentes_list = []
    for entry in docentes_map.values():
        total_asig = entry["total_asignaciones"]
        esperado_silabos_total = total_asig * esperado_silabos
        esperado_guias_total = total_asig * esperado_guias
        esperado_examenes_total = total_asig * esperado_examenes
        esperado_entregables = total_asig * esperado_por_asignacion
        total_entregables = entry["total_silabos"] + entry["total_guias"] + entry["total_examenes"]

        porcentaje_general = (
            round((total_entregables / esperado_entregables) * 100, 1)
            if esperado_entregables > 0
            else 0.0
        )
        porcentaje_silabos = (
            round((entry["total_silabos"] / esperado_silabos_total) * 100, 1)
            if esperado_silabos_total > 0
            else 0.0
        )
        porcentaje_guias = (
            round((entry["total_guias"] / esperado_guias_total) * 100, 1)
            if esperado_guias_total > 0
            else 0.0
        )
        porcentaje_examenes = (
            round((entry["total_examenes"] / esperado_examenes_total) * 100, 1)
            if esperado_examenes_total > 0
            else 0.0
        )

        # Ordenar asignaturas mostrando primero las más atrasadas para facilitar seguimiento
        entry["asignaciones"].sort(
            key=lambda a: (a["porcentaje"], a["asignatura"], a["trimestre_lectivo"], a["id"])
        )
        entry.update({
            "asignaciones_pendientes": total_asig - entry["asignaciones_completadas"],
            "esperado_silabos": esperado_silabos_total,
            "esperado_guias": esperado_guias_total,
            "esperado_examenes": esperado_examenes_total,
            "total_entregables": total_entregables,
            "esperado_entregables": esperado_entregables,
            "faltantes_silabos": max(0, esperado_silabos_total - entry["total_silabos"]),
            "faltantes_guias": max(0, esperado_guias_total - entry["total_guias"]),
            "faltantes_examenes": max(0, esperado_examenes_total - entry["total_examenes"]),
            "faltantes_total": max(0, esperado_entregables - total_entregables),
            "porcentaje_general": porcentaje_general,
            "porcentaje_silabos": porcentaje_silabos,
            "porcentaje_guias": porcentaje_guias,
            "porcentaje_examenes": porcentaje_examenes,
            **_clasificar_estado(porcentaje_general),
        })
        docentes_list.append(entry)

    return docentes_list


def _coincide_busqueda(docente_entry, query):
    q = (query or "").strip().lower()
    if not q:
        return True
    if q in docente_entry["nombre_completo"].lower() or q in docente_entry["username"].lower():
        return True
    return any(
        q in a["asignatura"].lower() or q in a["codigo"].lower() or q in a["carrera"].lower()
        for a in docente_entry["asignaciones"]
    )


def _coincide_estado(docente_entry, estado):
    if not estado or estado == "todos":
        return True
    if estado == "pendientes":
        return docente_entry["porcentaje_general"] < 100.0
    if estado == "en_progreso":
        return 0.0 < docente_entry["porcentaje_general"] < 100.0
    return docente_entry["estado"] == estado


def construir_ranking_docentes(
    alcance="actual",
    orden="mayor",
    carrera_id=None,
    trimestre=None,
    trimestre_lectivo=None,
    estado="todos",
    query="",
    fecha_ref=None,
    alcance_explicito=False,
):
    """
    Construye el ranking completo de progreso docente con métricas por docente,
    desglose por asignatura, KPIs globales, cuadro de honor y prioridad de seguimiento.
    """
    base_qs = (
        AsignacionPlanEstudio.objects.select_related(
            "usuario",
            "usuario__credenciales_google",
            "plan_de_estudio",
            "plan_de_estudio__carrera",
            "plan_de_estudio__asignatura",
        )
        .annotate(
            silabos_db=Count("silabo_set", distinct=True),
            guias_db=Count("silabo_set__guias", distinct=True),
            examenes_db=Count("examenes_set", distinct=True),
        )
    )

    ciclo_codigo_actual = obtener_trimestre_lectivo_de_fecha(fecha_ref)
    inicio_ciclo, fin_ciclo, ciclo_nombre = obtener_rango_por_trimestre_lectivo(
        ciclo_codigo_actual
    )

    conteos_lectivos = dict(
        AsignacionPlanEstudio.objects.values_list("trimestre_lectivo").annotate(total=Count("id"))
    )
    total_asignaciones_ciclo = conteos_lectivos.get(ciclo_codigo_actual, 0)
    total_asignaciones_historico = sum(conteos_lectivos.values())

    trimestre_lectivo_clean = (trimestre_lectivo or "").strip()
    trimestre_lectivo = (
        trimestre_lectivo_clean if parsear_trimestre_lectivo(trimestre_lectivo_clean) else None
    )

    alcance_normalizado = "todas" if alcance == "todas" else "actual"
    auto_fallback_todas = False
    if trimestre_lectivo:
        qs = base_qs.filter(trimestre_lectivo=trimestre_lectivo)
    else:
        if (
            not alcance_explicito
            and alcance_normalizado == "actual"
            and total_asignaciones_ciclo == 0
            and total_asignaciones_historico > 0
        ):
            alcance_normalizado = "todas"
            auto_fallback_todas = True

        qs = (
            base_qs
            if alcance_normalizado == "todas"
            else base_qs.filter(trimestre_lectivo=ciclo_codigo_actual)
        )

    if carrera_id:
        qs = qs.filter(plan_de_estudio__carrera_id=carrera_id)
    if trimestre:
        qs = qs.filter(plan_de_estudio__trimestre=trimestre)

    esperado_silabos, esperado_guias, esperado_examenes, esperado_por_asignacion = obtener_metas_ranking()
    docentes_scope = _agrupar_por_docente(
        qs,
        esperado_silabos=esperado_silabos,
        esperado_guias=esperado_guias,
        esperado_examenes=esperado_examenes,
    )
    # Orden canónico de ranking (mayor cumplimiento primero) para asignar puesto real 1..N
    docentes_scope.sort(
        key=lambda d: (
            -d["porcentaje_general"],
            -d["asignaciones_completadas"],
            -d["total_entregables"],
            d["nombre_completo"].lower(),
        )
    )
    total_docentes_scope = len(docentes_scope)
    for idx, entry in enumerate(docentes_scope, start=1):
        entry["puesto"] = idx
        entry["total_docentes_scope"] = total_docentes_scope

    # KPIs calculados sobre el alcance y filtros estructurales activos
    total_asignaciones_scope = sum(d["total_asignaciones"] for d in docentes_scope)
    total_entregables_scope = sum(d["total_entregables"] for d in docentes_scope)
    esperado_entregables_scope = sum(d["esperado_entregables"] for d in docentes_scope)
    cumplimiento_global = (
        round((total_entregables_scope / esperado_entregables_scope) * 100, 1)
        if esperado_entregables_scope > 0
        else 0.0
    )
    docentes_cumplidos = sum(1 for d in docentes_scope if d["estado"] == "cumplido")
    docentes_sin_avance = sum(1 for d in docentes_scope if d["estado"] == "sin_avance")
    docentes_con_pendientes = total_docentes_scope - docentes_cumplidos

    cuadro_honor = [d for d in docentes_scope if d["porcentaje_general"] > 0][:3]
    prioridad_seguimiento = sorted(
        [d for d in docentes_scope if d["porcentaje_general"] < 100.0],
        key=lambda d: (
            d["porcentaje_general"],
            -d["asignaciones_pendientes"],
            d["total_entregables"],
            d["nombre_completo"].lower(),
        ),
    )[:3]

    # Filtros de visualización (estado y búsqueda)
    docentes_filtrados = [
        d
        for d in docentes_scope
        if _coincide_estado(d, estado) and _coincide_busqueda(d, query)
    ]

    orden_normalizado = "menor" if orden == "menor" else "mayor"
    if orden_normalizado == "menor":
        docentes_filtrados.sort(
            key=lambda d: (
                d["porcentaje_general"],
                -d["asignaciones_pendientes"],
                d["total_entregables"],
                d["nombre_completo"].lower(),
            )
        )
    else:
        docentes_filtrados.sort(
            key=lambda d: (
                -d["porcentaje_general"],
                -d["asignaciones_completadas"],
                -d["total_entregables"],
                d["nombre_completo"].lower(),
            )
        )

    carreras_disponibles = Carrera.objects.filter(
        plan_de_estudio__asignacionplanestudio__isnull=False
    ).distinct().order_by("nombre")

    codigos_lectivos = ordenar_codigos_trimestre_lectivo(
        conteos_lectivos.keys(), descendente=True
    )
    trimestres_lectivos_disponibles = [
        (code, formatear_trimestre_lectivo(code, detallado=True))
        for code in codigos_lectivos
    ]

    clave_actual = clave_orden_trimestre_lectivo(ciclo_codigo_actual)
    ciclos_futuros = [
        {
            "codigo": code,
            "etiqueta": formatear_trimestre_lectivo(code),
            "nombre": formatear_trimestre_lectivo(code, detallado=True),
            "total": conteos_lectivos.get(code, 0),
        }
        for code in reversed(codigos_lectivos)
        if clave_orden_trimestre_lectivo(code) > clave_actual and conteos_lectivos.get(code, 0) > 0
    ]

    return {
        "alcance": alcance_normalizado,
        "auto_fallback_todas": auto_fallback_todas,
        "orden": orden_normalizado,
        "ciclo_nombre": ciclo_nombre,
        "ciclo_codigo_actual": ciclo_codigo_actual,
        "ciclo_filtrado_nombre": (
            formatear_trimestre_lectivo(trimestre_lectivo, detallado=True)
            if trimestre_lectivo
            else ""
        ),
        "ciclos_futuros": ciclos_futuros,
        "inicio_ciclo": inicio_ciclo,
        "fin_ciclo": fin_ciclo,
        "total_asignaciones_ciclo": total_asignaciones_ciclo,
        "total_asignaciones_historico": total_asignaciones_historico,
        "docentes": docentes_filtrados,
        "cuadro_honor": cuadro_honor,
        "prioridad_seguimiento": prioridad_seguimiento,
        "resumen": {
            "total_docentes": total_docentes_scope,
            "docentes_visibles": len(docentes_filtrados),
            "total_asignaciones": total_asignaciones_scope,
            "total_entregables": total_entregables_scope,
            "esperado_entregables": esperado_entregables_scope,
            "cumplimiento_global": cumplimiento_global,
            "docentes_cumplidos": docentes_cumplidos,
            "docentes_con_pendientes": docentes_con_pendientes,
            "docentes_sin_avance": docentes_sin_avance,
        },
        "esperado_silabos": esperado_silabos,
        "esperado_guias": esperado_guias,
        "esperado_examenes": esperado_examenes,
        "esperado_entregables_asignacion": esperado_por_asignacion,
        "carreras_disponibles": carreras_disponibles,
        "trimestres_disponibles": TRIMESTRES_ROMANOS,
        "trimestres_lectivos_disponibles": trimestres_lectivos_disponibles,
    }
