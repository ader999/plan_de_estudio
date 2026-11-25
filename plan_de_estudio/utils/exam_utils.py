"""
Utilidades centrales para Proyectos de Examen (Encuentros 4, 8 y 11):
- Estado de desbloqueo y bloqueo secuencial de sílabos
- Cálculo automático del puntaje restante del corte evaluativo (100 - acumulado)
- Estimación calibrada de páginas en la plantilla Word horizontal UML y validación anti-pereza
"""

import math
import re

from plan_de_estudio.models import (
    CORTE_POR_EVALUACION,
    ENCUENTROS_EXAMEN,
    ENCUENTRO_POR_EVALUACION,
    Guia,
    ProyectoExamen,
    Silabo,
    TOTAL_ENCUENTROS_SILABO,
    TOTAL_EXAMENES,
    obtener_max_encuentros_guia,
)
from plan_de_estudio.utils.curriculum_planner import (
    ENCUENTROS_POR_CORTE,
    PUNTAJE_MAX_POR_CORTE,
)

NUMEROS_ROMANOS_ITEMS = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
]

# Calibración real según tabla de plantilla_proyecto_examen.docx (11x8.5 in landscape, Arial 10pt)
# Anchos reales de columnas: 4443 / 4762 / 3745 / 1158 dxa (3.09 / 3.31 / 2.60 / 0.80 in)
CHARS_POR_LINEA_OBJETIVO = 42
CHARS_POR_LINEA_EJERCICIOS = 46
CHARS_POR_LINEA_RESPUESTAS = 36
CHARS_POR_LINEA_PUNTAJE = 11

LINEAS_UTILES_PAGINA_1 = 25.0
LINEAS_UTILES_PAGINA_SIGUIENTE = 38.0
LINEAS_FIRMA_FINAL = 3.0
LINEAS_PADDING_FILA = 1.5

MIN_PAGINAS_EXAMEN_EXCLUSIVO = 2.0  # Debe ser estrictamente > 2.0 páginas (mínimo 3 hojas)
MIN_CARACTERES_UTILES_EXAMEN = 1200
MIN_ITEMS_EXAMEN = 2
MIN_HOJAS_IA = 4
MAX_HOJAS_IA = 8


def _contar_lineas_texto(texto, chars_por_linea):
    """
    Cuenta líneas visuales reales tras ajuste de línea en la columna indicada.
    Colapsa saltos de línea vacíos consecutivos (máximo 1) para evitar inflación artificial.
    """
    if not texto:
        return 1
    limpio = str(texto).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not limpio:
        return 1
    # Evitar trucos de líneas vacías repetidas (máximo 1 salto vacío seguido)
    limpio = re.sub(r"\n{3,}", "\n\n", limpio)
    total = 0
    for linea in limpio.split("\n"):
        linea_trim = linea.strip()
        if not linea_trim:
            total += 0.6
        else:
            total += max(1, math.ceil(len(linea_trim) / max(1, chars_por_linea)))
    return max(1.0, float(total))


def estimar_paginas_examen(items):
    """
    Estima la cantidad de páginas que ocupará el Proyecto de Examen en la plantilla
    Word horizontal UML (11x8.5 in, Arial 10pt) y valida el requisito mínimo (> 2.0 páginas).
    """
    if not isinstance(items, list) or not items:
        return {
            "paginas_estimadas": 0.0,
            "hojas_estimadas": 0,
            "total_lineas": 0.0,
            "caracteres_utiles": 0,
            "items_validos": 0,
            "cumple_minimo": False,
            "motivo_rechazo": (
                "Debe incluir al menos 2 apartados completos que superen las 2 páginas "
                "(mínimo 3 hojas). No se permiten proyectos de examen de 1 o 2 páginas."
            ),
        }

    total_lineas = 0.0
    caracteres_utiles = 0
    items_validos = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        obj = str(item.get("objetivo") or "").strip()
        ejer = str(item.get("ejercicios") or "").strip()
        resp = str(item.get("posibles_respuestas") or "").strip()
        det_pts = str(item.get("detalle_puntaje") or f"{item.get('puntaje', '')} pts").strip()

        if obj and ejer and resp:
            items_validos += 1

        # Contar caracteres significativos (sin colapsar a solo guiones/espacios)
        for campo in (obj, ejer, resp):
            sin_espacios = re.sub(r"[\s_.\-]+", "", campo)
            caracteres_utiles += len(sin_espacios)

        l_obj = _contar_lineas_texto(obj, CHARS_POR_LINEA_OBJETIVO)
        l_ejer = _contar_lineas_texto(ejer, CHARS_POR_LINEA_EJERCICIOS)
        l_resp = _contar_lineas_texto(resp, CHARS_POR_LINEA_RESPUESTAS)
        l_pts = _contar_lineas_texto(det_pts, CHARS_POR_LINEA_PUNTAJE)
        total_lineas += max(l_obj, l_ejer, l_resp, l_pts) + LINEAS_PADDING_FILA

    total_lineas_con_firma = total_lineas + LINEAS_FIRMA_FINAL
    if total_lineas_con_firma <= LINEAS_UTILES_PAGINA_1:
        paginas = total_lineas_con_firma / LINEAS_UTILES_PAGINA_1
    else:
        paginas = 1.0 + (total_lineas_con_firma - LINEAS_UTILES_PAGINA_1) / LINEAS_UTILES_PAGINA_SIGUIENTE

    paginas = round(paginas, 1)
    hojas = max(1, math.ceil(paginas))

    motivo = ""
    cumple = True
    if items_validos < MIN_ITEMS_EXAMEN:
        cumple = False
        motivo = (
            f"Debe registrar al menos {MIN_ITEMS_EXAMEN} apartados completos "
            "(Objetivo, Ejercicios Propuestos y Posibles Respuestas)."
        )
    elif paginas <= MIN_PAGINAS_EXAMEN_EXCLUSIVO:
        cumple = False
        motivo = (
            f"El proyecto de examen tiene una extensión estimada de {paginas:.1f} página(s). "
            "Los exámenes de 1 o 2 páginas están bloqueados: debe superar las 2 páginas "
            "(mínimo 3 hojas) con contenido académico suficiente."
        )
    elif caracteres_utiles < MIN_CARACTERES_UTILES_EXAMEN:
        cumple = False
        motivo = (
            f"El contenido real del examen es demasiado breve ({caracteres_utiles} caracteres efectivos; "
            f"mínimo requerido: {MIN_CARACTERES_UTILES_EXAMEN}). Desarrolle ejercicios y respuestas completas "
            "sin rellenar con líneas vacías o guiones."
        )

    return {
        "paginas_estimadas": paginas,
        "hojas_estimadas": hojas,
        "total_lineas": round(total_lineas_con_firma, 1),
        "caracteres_utiles": caracteres_utiles,
        "items_validos": items_validos,
        "cumple_minimo": cumple,
        "motivo_rechazo": motivo,
    }


def normalizar_items_examen_entrada(raw_items):
    """Limpia y normaliza una lista de ítems recibidos desde el formulario o la IA."""
    if not isinstance(raw_items, list):
        return []
    limpios = []
    for idx, item in enumerate(raw_items):
        if not isinstance(item, dict):
            continue
        objetivo = str(item.get("objetivo") or "").strip()
        ejercicios = str(item.get("ejercicios") or "").strip()
        respuestas = str(item.get("posibles_respuestas") or "").strip()
        detalle_puntaje = str(item.get("detalle_puntaje") or "").strip()
        raw_pts = item.get("puntaje", 0)
        try:
            puntaje = int(round(float(raw_pts)))
        except (ValueError, TypeError):
            puntaje = 0

        if not (objetivo or ejercicios or respuestas or puntaje):
            continue

        numero = str(item.get("numero") or "").strip()
        if not numero:
            numero = NUMEROS_ROMANOS_ITEMS[idx] if idx < len(NUMEROS_ROMANOS_ITEMS) else str(idx + 1)

        if not detalle_puntaje and puntaje > 0:
            detalle_puntaje = f"{puntaje} pts"

        limpios.append({
            "numero": numero,
            "objetivo": objetivo,
            "ejercicios": ejercicios,
            "posibles_respuestas": respuestas,
            "puntaje": max(0, puntaje),
            "detalle_puntaje": detalle_puntaje,
        })
    return limpios


def validar_items_examen(raw_items, puntaje_requerido):
    """
    Valida los ítems del Proyecto de Examen:
    1. Todos los apartados tienen objetivo, ejercicios, posibles respuestas y puntaje > 0.
    2. La suma de puntajes coincide EXACTAMENTE con `puntaje_requerido` (100 - acumulado del corte).
    3. La extensión estimada supera las 2.0 páginas (bloquea exámenes de 1–2 páginas).
    """
    items = normalizar_items_examen_entrada(raw_items)
    errores = []

    if puntaje_requerido <= 0:
        errores.append(
            "No hay puntaje disponible en este corte evaluativo (ya se alcanzó o superó el límite de 100 pts "
            "entre sílabos y guías). Debe corregir los puntajes de sus sílabos o guías de este corte primero."
        )
        return False, items, errores, estimar_paginas_examen(items)

    if len(items) < MIN_ITEMS_EXAMEN:
        errores.append(
            f"Debe incluir al menos {MIN_ITEMS_EXAMEN} apartados (I, II, ...) en el proyecto de examen."
        )

    suma_puntajes = 0
    for idx, it in enumerate(items, start=1):
        if not it["objetivo"]:
            errores.append(f"El apartado #{idx} ({it['numero']}) requiere un Objetivo.")
        if not it["ejercicios"]:
            errores.append(f"El apartado #{idx} ({it['numero']}) requiere Ejercicios Propuestos.")
        if not it["posibles_respuestas"]:
            errores.append(f"El apartado #{idx} ({it['numero']}) requiere Posibles Respuestas.")
        if it["puntaje"] <= 0:
            errores.append(f"El apartado #{idx} ({it['numero']}) debe tener un puntaje mayor a 0.")
        suma_puntajes += it["puntaje"]

    if suma_puntajes != puntaje_requerido:
        diferencia = puntaje_requerido - suma_puntajes
        if diferencia > 0:
            errores.append(
                f"La suma de puntajes de los apartados es {suma_puntajes} pts, pero debe ser exactamente "
                f"{puntaje_requerido} pts para completar los 100 pts del corte (faltan {diferencia} pts)."
            )
        else:
            errores.append(
                f"La suma de puntajes de los apartados es {suma_puntajes} pts, pero debe ser exactamente "
                f"{puntaje_requerido} pts para completar los 100 pts del corte (excede por {abs(diferencia)} pts)."
            )

    est = estimar_paginas_examen(items)
    if not est["cumple_minimo"]:
        errores.append(est["motivo_rechazo"])

    return len(errores) == 0, items, errores, est


def calcular_puntaje_examen_disponible(asignacion, numero_evaluacion):
    """
    Calcula el desglose exacto de puntos acumulados en Sílabos y Guías para el corte
    correspondiente a `numero_evaluacion` (1, 2 o 3) y el puntaje automático restante
    para completar los 100 puntos del corte.
    """
    num_eval = int(numero_evaluacion)
    corte = CORTE_POR_EVALUACION[num_eval]
    encuentro_hito = ENCUENTRO_POR_EVALUACION[num_eval]
    encuentros_corte = ENCUENTROS_POR_CORTE[corte]

    silabos = Silabo.objects.filter(asignacion_plan=asignacion).order_by("encuentros")
    detalle_silabos = []
    acumulado_silabos = 0
    for s in silabos:
        corte_s = (s.periodo_tiempo_programado or "").strip()
        if corte_s == corte and s.puntaje:
            acumulado_silabos += int(s.puntaje)
            detalle_silabos.append({
                "id": s.id,
                "encuentro": s.encuentros,
                "puntaje": int(s.puntaje),
                "unidad": s.unidad,
            })
        elif s.encuentros in encuentros_corte:
            detalle_silabos.append({
                "id": s.id,
                "encuentro": s.encuentros,
                "puntaje": int(s.puntaje or 0) if corte_s == corte else 0,
                "unidad": s.unidad,
            })

    guias = Guia.objects.filter(silabo__asignacion_plan=asignacion).select_related("silabo").order_by("numero_encuentro")
    detalle_guias = []
    acumulado_guias = 0
    for g in guias:
        pts_guia_corte = 0
        for idx in range(1, 5):
            pts = getattr(g, f"puntaje_{idx}", None)
            corte_t = (getattr(g, f"periodo_tiempo_programado_{idx}", None) or "").strip()
            if pts and corte_t == corte:
                pts_guia_corte += int(pts)
        enc_g = g.numero_encuentro or (g.silabo.encuentros if g.silabo_id else 0)
        if pts_guia_corte > 0 or enc_g in encuentros_corte:
            acumulado_guias += pts_guia_corte
            detalle_guias.append({
                "id": g.id,
                "encuentro": enc_g,
                "puntaje": pts_guia_corte,
            })

    acumulado_total = acumulado_silabos + acumulado_guias
    puntaje_disponible = PUNTAJE_MAX_POR_CORTE - acumulado_total
    exceso = max(0, acumulado_total - PUNTAJE_MAX_POR_CORTE)

    return {
        "numero_evaluacion": num_eval,
        "encuentro": encuentro_hito,
        "corte": corte,
        "encuentros_corte": encuentros_corte,
        "acumulado_silabos": acumulado_silabos,
        "acumulado_guias": acumulado_guias,
        "acumulado_total": acumulado_total,
        "puntaje_disponible": max(0, puntaje_disponible),
        "puntaje_raw_restante": puntaje_disponible,
        "exceso": exceso,
        "bloqueado_por_puntaje": puntaje_disponible <= 0,
        "detalle_silabos": detalle_silabos,
        "detalle_guias": detalle_guias,
    }


def obtener_estado_examenes_asignacion(asignacion, max_guias=None, examenes_por_eval=None):
    """
    Calcula el estado completo de avance, desbloqueo y bloqueo secuencial
    de Sílabos, Guías y Proyectos de Examen para una AsignacionPlanEstudio.

    Reglas:
    - Exámenes corresponden a los encuentros 4 (Eval 1), 8 (Eval 2) y 11 (Eval 3).
    - Un examen se desbloquea en cuanto `silabos_creados >= encuentro_hito`.
    - Mientras un examen de encuentro 4 u 8 esté pendiente después de completar ese sílabo,
      se bloquea la creación del siguiente sílabo (ej. no permite Sílabo 5 sin Examen 1).
    - La asignación pasa a Completada/Archivada solo cuando cumple:
      11 sílabos + max_guias guías + 3 proyectos de examen.
    """
    if max_guias is None:
        max_guias = obtener_max_encuentros_guia()

    silabos_creados = max(0, int(asignacion.silabos_creados or 0))
    guias_creadas = max(0, int(asignacion.guias_creadas or 0))

    if examenes_por_eval is None:
        examenes_qs = ProyectoExamen.objects.filter(asignacion_plan=asignacion).only(
            "id", "numero_evaluacion", "encuentro", "puntaje_total", "paginas_estimadas"
        )
        examenes_por_eval = {e.numero_evaluacion: e for e in examenes_qs}

    if examenes_por_eval:
        examenes_hechos = set(examenes_por_eval.keys())
        examenes_creados = len(examenes_hechos)
    else:
        examenes_creados = min(TOTAL_EXAMENES, max(0, int(asignacion.examenes_creados or 0)))
        examenes_hechos = set(range(1, examenes_creados + 1))

    hitos = [(1, 4), (2, 8), (3, 11)]
    siguiente_evaluacion = None
    siguiente_encuentro_examen = None
    puede_generar_examen = False
    razon_bloqueo_examen = ""

    for num_eval, enc_hito in hitos:
        if num_eval not in examenes_hechos:
            siguiente_evaluacion = num_eval
            siguiente_encuentro_examen = enc_hito
            if silabos_creados >= enc_hito:
                puede_generar_examen = True
            else:
                razon_bloqueo_examen = (
                    f"Disponible al completar el sílabo del encuentro {enc_hito} "
                    f"(Evaluación #{num_eval} - {CORTE_POR_EVALUACION[num_eval]})"
                )
            break

    if siguiente_evaluacion is None:
        razon_bloqueo_examen = "Ya se han completado los 3 proyectos de examen"

    # Verificar si un examen pendiente bloquea el avance al siguiente sílabo
    examen_bloquea_silabo = False
    examen_pendiente_bloqueo = None
    razon_bloqueo_silabo_por_examen = ""
    for num_eval, enc_hito in ((1, 4), (2, 8)):
        if silabos_creados >= enc_hito and num_eval not in examenes_hechos:
            examen_bloquea_silabo = True
            examen_pendiente_bloqueo = (num_eval, enc_hito)
            razon_bloqueo_silabo_por_examen = (
                f"Debe completar el Proyecto de Examen #{num_eval} (Encuentro {enc_hito}) "
                f"antes de continuar con el sílabo {enc_hito + 1}"
            )
            break

    silabo_bloqueado_por_guia = (
        silabos_creados > guias_creadas
        and silabos_creados > 0
        and guias_creadas < max_guias
    )
    silabo_deshabilitado = (
        silabos_creados >= TOTAL_ENCUENTROS_SILABO
        or silabo_bloqueado_por_guia
        or examen_bloquea_silabo
    )
    if silabos_creados >= TOTAL_ENCUENTROS_SILABO:
        razon_bloqueo_silabo = "Ya se han completado los 11 sílabos"
    elif examen_bloquea_silabo:
        razon_bloqueo_silabo = razon_bloqueo_silabo_por_examen
    elif silabo_bloqueado_por_guia:
        razon_bloqueo_silabo = "Debe crear la guía del sílabo anterior antes de continuar"
    else:
        razon_bloqueo_silabo = ""

    indicadores_examen = []
    for num_eval, enc_hito in hitos:
        exam_obj = examenes_por_eval.get(num_eval)
        completado = num_eval in examenes_hechos
        desbloqueado = (not completado) and (silabos_creados >= enc_hito) and (siguiente_evaluacion == num_eval)
        indicadores_examen.append({
            "numero_evaluacion": num_eval,
            "encuentro": enc_hito,
            "corte": CORTE_POR_EVALUACION[num_eval],
            "completado": completado,
            "desbloqueado": desbloqueado,
            "examen_id": exam_obj.id if exam_obj else None,
            "puntaje_total": exam_obj.puntaje_total if exam_obj else None,
        })

    esta_completada = (
        silabos_creados >= TOTAL_ENCUENTROS_SILABO
        and guias_creadas >= max_guias
        and examenes_creados >= TOTAL_EXAMENES
    )

    return {
        "silabos_creados": silabos_creados,
        "guias_creadas": guias_creadas,
        "examenes_creados": examenes_creados,
        "examenes_hechos": examenes_hechos,
        "siguiente_evaluacion": siguiente_evaluacion,
        "siguiente_encuentro_examen": siguiente_encuentro_examen,
        "puede_generar_examen": puede_generar_examen,
        "razon_bloqueo_examen": razon_bloqueo_examen,
        "examen_bloquea_silabo": examen_bloquea_silabo,
        "examen_pendiente_bloqueo": examen_pendiente_bloqueo,
        "razon_bloqueo_silabo_por_examen": razon_bloqueo_silabo_por_examen,
        "silabo_deshabilitado": silabo_deshabilitado,
        "razon_bloqueo_silabo": razon_bloqueo_silabo,
        "indicadores_examen": indicadores_examen,
        "esta_completada": esta_completada,
    }


def verificar_examen_bloqueando_encuentro(asignacion, proximo_encuentro):
    """
    Retorna `(num_eval, enc_hito)` si existe un Proyecto de Examen previo obligatorio
    que impide crear/guardar el sílabo `proximo_encuentro`. Retorna `None` si puede avanzar.
    """
    enc = int(proximo_encuentro)
    examenes_hechos = set(
        ProyectoExamen.objects.filter(asignacion_plan=asignacion).values_list(
            "numero_evaluacion", flat=True
        )
    )
    if not examenes_hechos and (asignacion.examenes_creados or 0) > 0:
        examenes_hechos = set(range(1, min(TOTAL_EXAMENES, int(asignacion.examenes_creados)) + 1))

    for num_eval, enc_hito in ((1, 4), (2, 8)):
        if enc > enc_hito and num_eval not in examenes_hechos:
            return (num_eval, enc_hito)
    return None
