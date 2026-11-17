import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.utils import timezone

from .models import AsignacionPlanEstudio, Carrera, Guia, TRIMESTRES_ROMANOS

ENCUENTROS_ESPERADOS = 11
ENTREGABLES_POR_ASIGNACION = ENCUENTROS_ESPERADOS * 2


def obtener_rango_ciclo_actual(fecha_ref=None):
    """
    Calcula las fechas de inicio y fin del trimestre/ciclo actual
    (Mar-May, Jun-Ago, Sep-Nov, Dic-Feb), alineado con AsignacionPlanEstudio.clean().
    """
    hoy = fecha_ref or timezone.localdate()
    mes = hoy.month
    year = hoy.year

    if 3 <= mes <= 5:
        return (
            datetime.date(year, 3, 1),
            datetime.date(year, 5, 31),
            f"Ciclo Mar – May {year} (Trimestre I)",
        )
    if 6 <= mes <= 8:
        return (
            datetime.date(year, 6, 1),
            datetime.date(year, 8, 31),
            f"Ciclo Jun – Ago {year} (Trimestre II)",
        )
    if 9 <= mes <= 11:
        return (
            datetime.date(year, 9, 1),
            datetime.date(year, 11, 30),
            f"Ciclo Sep – Nov {year} (Trimestre III)",
        )
    if mes == 12:
        fin = datetime.date(year + 1, 3, 1) - datetime.timedelta(days=1)
        return (
            datetime.date(year, 12, 1),
            fin,
            f"Ciclo Dic {year} – Feb {year + 1} (Trimestre IV)",
        )
    inicio = datetime.date(year - 1, 12, 1)
    fin = datetime.date(year, 3, 1) - datetime.timedelta(days=1)
    return (
        inicio,
        fin,
        f"Ciclo Dic {year - 1} – Feb {year} (Trimestre IV)",
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


def _calcular_metricas_asignacion(asignacion):
    silabos_db = getattr(asignacion, "silabos_db", None)
    if silabos_db is None:
        silabos_db = asignacion.silabo_set.count()
    guias_db = getattr(asignacion, "guias_db", None)
    if guias_db is None:
        guias_db = Guia.objects.filter(silabo__asignacion_plan=asignacion).count()

    silabos = min(silabos_db if silabos_db > 0 else max(asignacion.silabos_creados or 0, 0), ENCUENTROS_ESPERADOS)
    guias = min(guias_db if guias_db > 0 else max(asignacion.guias_creadas or 0, 0), ENCUENTROS_ESPERADOS)

    total_entregables = silabos + guias
    porcentaje = round((total_entregables / ENTREGABLES_POR_ASIGNACION) * 100, 1)
    porcentaje_silabos = round((silabos / ENCUENTROS_ESPERADOS) * 100, 1)
    porcentaje_guias = round((guias / ENCUENTROS_ESPERADOS) * 100, 1)
    completada = silabos >= ENCUENTROS_ESPERADOS and guias >= ENCUENTROS_ESPERADOS
    sin_iniciar = silabos == 0 and guias == 0
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
        "pensol": plan.pensol,
        "bloque": asignacion.bloque or "Sin bloque",
        "fecha_asignacion": asignacion.fecha_asignacion,
        "silabos": silabos,
        "guias": guias,
        "esperado_por_tipo": ENCUENTROS_ESPERADOS,
        "total_entregables": total_entregables,
        "esperado_total": ENTREGABLES_POR_ASIGNACION,
        "faltantes_silabos": ENCUENTROS_ESPERADOS - silabos,
        "faltantes_guias": ENCUENTROS_ESPERADOS - guias,
        "faltantes_total": ENTREGABLES_POR_ASIGNACION - total_entregables,
        "porcentaje": porcentaje,
        "porcentaje_silabos": porcentaje_silabos,
        "porcentaje_guias": porcentaje_guias,
        "completada": completada,
        "sin_iniciar": sin_iniciar,
        **clasificacion,
    }


def _agrupar_por_docente(asignaciones_qs):
    docentes_map = {}

    for asignacion in asignaciones_qs:
        usuario = asignacion.usuario
        uid = usuario.id
        metrica = _calcular_metricas_asignacion(asignacion)

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
        if asignacion.fecha_asignacion and (
            entry["ultima_fecha_asignacion"] is None
            or asignacion.fecha_asignacion > entry["ultima_fecha_asignacion"]
        ):
            entry["ultima_fecha_asignacion"] = asignacion.fecha_asignacion
        entry["asignaciones"].append(metrica)

    docentes_list = []
    for entry in docentes_map.values():
        total_asig = entry["total_asignaciones"]
        esperado_por_tipo = total_asig * ENCUENTROS_ESPERADOS
        esperado_entregables = total_asig * ENTREGABLES_POR_ASIGNACION
        total_entregables = entry["total_silabos"] + entry["total_guias"]

        porcentaje_general = (
            round((total_entregables / esperado_entregables) * 100, 1)
            if esperado_entregables > 0
            else 0.0
        )
        porcentaje_silabos = (
            round((entry["total_silabos"] / esperado_por_tipo) * 100, 1)
            if esperado_por_tipo > 0
            else 0.0
        )
        porcentaje_guias = (
            round((entry["total_guias"] / esperado_por_tipo) * 100, 1)
            if esperado_por_tipo > 0
            else 0.0
        )

        # Ordenar asignaturas mostrando primero las más atrasadas para facilitar seguimiento
        entry["asignaciones"].sort(key=lambda a: (a["porcentaje"], a["asignatura"]))
        entry.update({
            "asignaciones_pendientes": total_asig - entry["asignaciones_completadas"],
            "esperado_silabos": esperado_por_tipo,
            "esperado_guias": esperado_por_tipo,
            "total_entregables": total_entregables,
            "esperado_entregables": esperado_entregables,
            "faltantes_silabos": esperado_por_tipo - entry["total_silabos"],
            "faltantes_guias": esperado_por_tipo - entry["total_guias"],
            "faltantes_total": esperado_entregables - total_entregables,
            "porcentaje_general": porcentaje_general,
            "porcentaje_silabos": porcentaje_silabos,
            "porcentaje_guias": porcentaje_guias,
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
        )
    )

    inicio_ciclo, fin_ciclo, ciclo_nombre = obtener_rango_ciclo_actual(fecha_ref=fecha_ref)
    ciclo_qs = base_qs.filter(
        fecha_asignacion__date__gte=inicio_ciclo,
        fecha_asignacion__date__lte=fin_ciclo,
    )

    total_asignaciones_ciclo = ciclo_qs.count()
    total_asignaciones_historico = base_qs.count()

    alcance_normalizado = "todas" if alcance == "todas" else "actual"
    auto_fallback_todas = False
    if (
        not alcance_explicito
        and alcance_normalizado == "actual"
        and total_asignaciones_ciclo == 0
        and total_asignaciones_historico > 0
    ):
        alcance_normalizado = "todas"
        auto_fallback_todas = True

    qs = base_qs if alcance_normalizado == "todas" else ciclo_qs

    if carrera_id:
        qs = qs.filter(plan_de_estudio__carrera_id=carrera_id)
    if trimestre:
        qs = qs.filter(plan_de_estudio__trimestre=trimestre)

    docentes_scope = _agrupar_por_docente(qs)
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

    return {
        "alcance": alcance_normalizado,
        "auto_fallback_todas": auto_fallback_todas,
        "orden": orden_normalizado,
        "ciclo_nombre": ciclo_nombre,
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
        "carreras_disponibles": carreras_disponibles,
        "trimestres_disponibles": TRIMESTRES_ROMANOS,
    }
