import datetime
from django.utils import timezone

from plan_de_estudio.ranking_utils import obtener_rango_ciclo_actual
from plan_de_estudio.trimestre_utils import obtener_rango_por_trimestre_lectivo


UNIDADES_ROMANOS = [
    "Unidad I",
    "Unidad II",
    "Unidad III",
    "Unidad IV",
    "Unidad V",
    "Unidad VI",
]

CORTES_ORDEN = [
    "I Corte Evaluativo",
    "II Corte Evaluativo",
    "III Corte Evaluativo",
]

ENCUENTROS_POR_CORTE = {
    "I Corte Evaluativo": [1, 2, 3, 4],
    "II Corte Evaluativo": [5, 6, 7, 8],
    "III Corte Evaluativo": [9, 10, 11],
}

PUNTAJE_MAX_POR_CORTE = 100
RESERVA_EXAMEN_CORTE = 50
TOTAL_ENCUENTROS = 11


def _recortar(texto, limite=140):
    limpio = " ".join(str(texto or "").split())
    if len(limpio) <= limite:
        return limpio
    return limpio[: max(0, limite - 3)].rstrip() + "..."


def obtener_corte_para_encuentro(encuentro):
    """Mapea un número de encuentro (1..11) al Corte Evaluativo institucional."""
    enc = int(encuentro)
    if enc <= 4:
        return "I Corte Evaluativo"
    if enc <= 8:
        return "II Corte Evaluativo"
    return "III Corte Evaluativo"


def reparto_hamilton(total, pesos, minimo_por_item=0):
    """
    Reparte `total` unidades enteras proporcionalmente a `pesos` mediante resto mayor,
    garantizando `minimo_por_item` por elemento cuando el total lo permite.
    """
    n = len(pesos)
    if n == 0:
        return []

    total = max(0, int(total))
    base_min = max(0, int(minimo_por_item))
    if total < n * base_min:
        # Fallback equitativo si el total no alcanza para dar base_min a todos
        q, r = divmod(total, n)
        return [q + (1 if i < r else 0) for i in range(n)]

    asignacion = [base_min] * n
    remanente = total - n * base_min
    if remanente == 0:
        return asignacion

    pesos_limpios = [max(0.0, float(p or 0.0)) for p in pesos]
    suma_pesos = sum(pesos_limpios)
    if suma_pesos <= 0:
        pesos_limpios = [1.0] * n
        suma_pesos = float(n)

    cuotas = [(remanente * p) / suma_pesos for p in pesos_limpios]
    enteros = [int(c) for c in cuotas]
    for i, val in enumerate(enteros):
        asignacion[i] += val

    faltante = remanente - sum(enteros)
    if faltante > 0:
        orden_restos = sorted(
            range(n),
            key=lambda i: (cuotas[i] - enteros[i], pesos_limpios[i], -i),
            reverse=True,
        )
        for i in orden_restos[:faltante]:
            asignacion[i] += 1

    return asignacion


def calcular_puntajes_por_corte(
    asignacion,
    exclude_silabo_id=None,
    exclude_guia_id=None,
    exclude_examen_id=None,
    incluir_examenes=True,
):
    """Suma los puntajes acumulados de Sílabos, Guías y (opcionalmente) Proyectos de Examen por Corte Evaluativo."""
    from plan_de_estudio.models import Guia, ProyectoExamen, Silabo

    scores = {corte: 0 for corte in CORTES_ORDEN}

    silabos = Silabo.objects.filter(asignacion_plan=asignacion)
    if exclude_silabo_id:
        silabos = silabos.exclude(id=exclude_silabo_id)
    for s in silabos:
        corte = (s.periodo_tiempo_programado or "").strip()
        if corte in scores and s.puntaje:
            scores[corte] += s.puntaje

    guias = Guia.objects.filter(silabo__asignacion_plan=asignacion)
    if exclude_guia_id:
        guias = guias.exclude(id=exclude_guia_id)
    for g in guias:
        for idx in range(1, 5):
            pts = getattr(g, f"puntaje_{idx}", None)
            corte = (getattr(g, f"periodo_tiempo_programado_{idx}", None) or "").strip()
            if pts and corte in scores:
                scores[corte] += pts

    if incluir_examenes:
        examenes = ProyectoExamen.objects.filter(asignacion_plan=asignacion)
        if exclude_examen_id:
            examenes = examenes.exclude(id=exclude_examen_id)
        for ex in examenes:
            corte = (ex.periodo_corte or "").strip()
            if corte in scores and ex.puntaje_total:
                scores[corte] += ex.puntaje_total

    return scores


def extraer_contexto_asignatura(plan_de_estudio):
    """
    Extrae el programa oficial completo de la asignatura soportando tanto
    ProgramaAsignatura2026 como PlanTematico (vía get_plan_tematico_efectivo,
    recorriendo todas las unidades 1..6).
    """
    from plan_de_estudio.models import ProgramaAsignatura2026

    programa_2026 = ProgramaAsignatura2026.objects.filter(
        plan_estudio=plan_de_estudio
    ).first()

    unidades = []
    if programa_2026:
        for i in range(1, 7):
            nombre = (getattr(programa_2026, f"unidad_{i}_nombre", "") or "").strip()
            contenido = (getattr(programa_2026, f"unidad_{i}_contenido", "") or "").strip()
            objetivos = (getattr(programa_2026, f"unidad_{i}_objetivos_especificos", "") or "").strip()
            if not (nombre or contenido or objetivos):
                continue
            unidades.append({
                "numero": i,
                "romano": UNIDADES_ROMANOS[i - 1],
                "nombre": nombre or UNIDADES_ROMANOS[i - 1],
                "horas_teoricas": int(getattr(programa_2026, f"unidad_{i}_horas_teoricas", 0) or 0),
                "horas_practicas": int(getattr(programa_2026, f"unidad_{i}_horas_practicas", 0) or 0),
                "horas_independientes": int(getattr(programa_2026, f"unidad_{i}_horas_independientes", 0) or 0),
                "objetivos": objetivos or "No especificado",
                "contenido": contenido or "No especificado",
                "mediacion": (getattr(programa_2026, f"unidad_{i}_mediacion", "") or "No especificado").strip(),
                "evaluacion": (getattr(programa_2026, f"unidad_{i}_evaluacion", "") or "No especificado").strip(),
                "eje_relacion": "",
            })

        generales = {
            "fuente": "Programa de Asignatura 2026",
            "fundamentacion": (programa_2026.fundamentacion or "").strip(),
            "relacion_unidades": (programa_2026.relacion_unidades or "").strip(),
            "objetivo_conceptual": (programa_2026.objetivo_conceptual or "").strip(),
            "objetivo_procedimental": (programa_2026.objetivo_procedimental or "").strip(),
            "objetivo_actitudinal": (programa_2026.objetivo_actitudinal or "").strip(),
            "ejes_transversales": (programa_2026.ejes_transversales or "").strip(),
            "bibliografia_basica": (programa_2026.bibliografia_basica or "").strip(),
            "bibliografia_complementaria": (programa_2026.bibliografia_complementaria or "").strip(),
            "webgrafia": (programa_2026.webgrafia or "").strip(),
        }
        plan_tematico = None
    else:
        plan_tematico = plan_de_estudio.get_plan_tematico_efectivo()
        if not plan_tematico:
            raise ValueError(
                "No se encontró información del programa (ni Programa 2026 ni Plan Temático)"
            )

        for i in range(1, 7):
            sufijo = "" if i == 1 else f"_{i}"
            nombre = (getattr(plan_tematico, f"nombre_de_la_unidad{sufijo}", "") or "").strip()
            contenido = (getattr(plan_tematico, f"plan_analitico{sufijo}", "") or "").strip()
            objetivos = (getattr(plan_tematico, f"objetivo_especificos{sufijo}", "") or "").strip()
            mediacion = (getattr(plan_tematico, f"recomendaciones_metodologicas{sufijo}", "") or "").strip()
            evaluacion = (getattr(plan_tematico, f"forma_de_evaluacion{sufijo}", "") or "").strip()
            eje_rel = (getattr(plan_tematico, f"relacion_eje_contenido_launidad{sufijo}", "") or "").strip()
            if not (nombre or contenido or objetivos):
                continue
            unidades.append({
                "numero": i,
                "romano": UNIDADES_ROMANOS[i - 1],
                "nombre": nombre or UNIDADES_ROMANOS[i - 1],
                "horas_teoricas": 0,
                "horas_practicas": 0,
                "horas_independientes": 0,
                "objetivos": objetivos or "No especificado",
                "contenido": contenido or "No especificado",
                "mediacion": mediacion or "No especificado",
                "evaluacion": evaluacion or "No especificado",
                "eje_relacion": eje_rel,
            })

        generales = {
            "fuente": "Plan Temático (2015-2025)",
            "fundamentacion": "",
            "relacion_unidades": "",
            "objetivo_conceptual": "",
            "objetivo_procedimental": "",
            "objetivo_actitudinal": "",
            "ejes_transversales": "",
            "bibliografia_basica": "",
            "bibliografia_complementaria": "",
            "webgrafia": "",
        }

    if not unidades:
        raise ValueError("El programa de asignatura no contiene unidades temáticas registradas.")

    return {
        "tiene_programa_2026": bool(programa_2026),
        "programa_2026": programa_2026,
        "plan_tematico": plan_tematico,
        "generales": generales,
        "unidades": unidades,
        "total_unidades": len(unidades),
    }


def construir_mapa_maestro(unidades, total_encuentros=TOTAL_ENCUENTROS):
    """
    Construye una distribución determinista de los 11 encuentros entre las unidades
    temáticas reales del programa, ponderando por horas presenciales cuando existen.
    """
    pesos = []
    for u in unidades:
        hp_ht = u["horas_teoricas"] + u["horas_practicas"]
        peso = hp_ht if hp_ht > 0 else (u["horas_independientes"] if u["horas_independientes"] > 0 else 1)
        pesos.append(peso)

    cuotas = reparto_hamilton(total_encuentros, pesos, minimo_por_item=1)
    por_encuentro = {}
    resumen_unidades = []

    enc_actual = 1
    for idx_pos, (u, sesiones) in enumerate(zip(unidades, cuotas)):
        inicio = enc_actual
        fin = enc_actual + sesiones - 1
        # Mapear por orden curricular (Unidad I..VI según posición en unidades reales)
        unidad_romano = UNIDADES_ROMANOS[min(idx_pos, len(UNIDADES_ROMANOS) - 1)]
        resumen_unidades.append({
            "unidad_numero": idx_pos + 1,
            "unidad_romano": unidad_romano,
            "unidad_nombre": u["nombre"],
            "encuentro_inicio": inicio,
            "encuentro_fin": fin,
            "sesiones": sesiones,
            "unidad_dict": u,
        })
        for s in range(1, sesiones + 1):
            e_num = inicio + s - 1
            por_encuentro[e_num] = {
                "encuentro": e_num,
                "unidad_numero": idx_pos + 1,
                "unidad_romano": unidad_romano,
                "unidad_nombre": u["nombre"],
                "sesion_en_unidad": s,
                "sesiones_unidad": sesiones,
                "encuentro_inicio_unidad": inicio,
                "encuentro_fin_unidad": fin,
                "corte": obtener_corte_para_encuentro(e_num),
                "unidad_dict": u,
            }
        enc_actual = fin + 1

    return {
        "por_encuentro": por_encuentro,
        "resumen_unidades": resumen_unidades,
    }


def formatear_contexto_curricular(contexto_info, mapa, encuentro):
    """
    Genera una vista focalizada y compacta del currículo para mantener el prompt ligero:
    - Información general y bibliografía del curso
    - Mapa maestro E1..E11 con indicador de la unidad activa
    - Detalle completo de la unidad asignada al encuentro actual (y resumen breve del resto)
    """
    gen = contexto_info["generales"]
    enc_info = mapa["por_encuentro"][encuentro]
    unidad_activa_num = enc_info["unidad_numero"]

    partes = [f"FUENTE CURRICULAR: {gen['fuente']}"]
    if gen["fundamentacion"]:
        partes.append(f"FUNDAMENTACIÓN: {_recortar(gen['fundamentacion'], 450)}")
    if any([gen["objetivo_conceptual"], gen["objetivo_procedimental"], gen["objetivo_actitudinal"]]):
        partes.append(
            "OBJETIVOS GENERALES:\n"
            f"- Conceptual: {_recortar(gen['objetivo_conceptual'], 240)}\n"
            f"- Procedimental: {_recortar(gen['objetivo_procedimental'], 240)}\n"
            f"- Actitudinal: {_recortar(gen['objetivo_actitudinal'], 240)}"
        )
    if gen["ejes_transversales"]:
        partes.append(f"EJES TRANSVERSALES: {_recortar(gen['ejes_transversales'], 250)}")

    biblio = []
    if gen["bibliografia_basica"]:
        biblio.append(f"Básica: {_recortar(gen['bibliografia_basica'], 280)}")
    if gen["bibliografia_complementaria"]:
        biblio.append(f"Complementaria: {_recortar(gen['bibliografia_complementaria'], 220)}")
    if gen["webgrafia"]:
        biblio.append(f"Webgrafía: {_recortar(gen['webgrafia'], 220)}")
    if biblio:
        partes.append("BIBLIOGRAFÍA DE REFERENCIA:\n" + "\n".join(biblio))

    lineas_mapa = ["MAPA MAESTRO DE DISTRIBUCIÓN CURRICULAR (11 ENCUENTROS):"]
    for r in mapa["resumen_unidades"]:
        rango = (
            f"Encuentro {r['encuentro_inicio']}"
            if r["sesiones"] == 1
            else f"Encuentros {r['encuentro_inicio']}–{r['encuentro_fin']}"
        )
        marca = "  <-- ENCUENTRO ACTUAL" if r["unidad_numero"] == unidad_activa_num else ""
        lineas_mapa.append(
            f"- {r['unidad_romano']}: {r['unidad_nombre']} ({rango}, {r['sesiones']} sesiones){marca}"
        )
    partes.append("\n".join(lineas_mapa))

    partes.append(
        "ASIGNACIÓN OBLIGATORIA PARA ESTE ENCUENTRO:\n"
        f"- Encuentro {encuentro} de {TOTAL_ENCUENTROS} ({enc_info['corte']})\n"
        f"- Unidad asignada: {enc_info['unidad_romano']} — {enc_info['unidad_nombre']}\n"
        f"- Avance dentro de esta unidad: Sesión {enc_info['sesion_en_unidad']} de {enc_info['sesiones_unidad']} "
        f"(cubre la fracción {enc_info['sesion_en_unidad']}/{enc_info['sesiones_unidad']} progresiva del contenido sin repetir sesiones anteriores)."
    )

    bloques_unidades = ["DETALLE DE UNIDADES TEMÁTICAS:"]
    for r in mapa["resumen_unidades"]:
        u = r["unidad_dict"]
        hrs = ""
        if u["horas_teoricas"] or u["horas_practicas"] or u["horas_independientes"]:
            hrs = f" [HT: {u['horas_teoricas']}h | HP: {u['horas_practicas']}h | HI: {u['horas_independientes']}h]"
        if r["unidad_numero"] == unidad_activa_num:
            bloque = (
                f"\n>>> UNIDAD ACTIVA — {r['unidad_romano']}: {u['nombre']}{hrs} <<<\n"
                f"Objetivos Específicos: {u['objetivos']}\n"
                f"Contenido Temático: {u['contenido']}\n"
                f"Mediación / Metodología: {u['mediacion']}\n"
                f"Evaluación sugerida: {u['evaluacion']}"
            )
            if u["eje_relacion"]:
                bloque += f"\nRelación eje-contenido: {u['eje_relacion']}"
            bloques_unidades.append(bloque)
        else:
            bloques_unidades.append(
                f"- {r['unidad_romano']}: {u['nombre']}{hrs} | Temas clave: {_recortar(u['contenido'], 220)}"
            )

    partes.append("\n".join(bloques_unidades))
    return "\n\n".join(partes)


def calcular_corte_y_presupuesto(
    asignacion,
    encuentro,
    es_guia=False,
    max_guias=None,
    reservar_examen=True,
):
    """
    Calcula el Corte Evaluativo correspondiente al encuentro y el presupuesto de puntos
    disponible (regla institucional: Sílabos + Guías + Proyecto de Examen = 100 pts por Corte).
    Cuando `reservar_examen=True` y aún no existe Proyecto de Examen para el corte, reserva
    `RESERVA_EXAMEN_CORTE` (50 pts) para el examen de modo que los sílabos y guías generados
    con IA sumen 50 pts acumulados y dejen automáticamente 50 pts disponibles para el examen.
    """
    from plan_de_estudio.models import Guia, ProyectoExamen, Silabo, obtener_max_encuentros_guia

    max_guias_efectivo = (
        obtener_max_encuentros_guia()
        if max_guias is None
        else max(1, min(TOTAL_ENCUENTROS, int(max_guias)))
    )
    corte = obtener_corte_para_encuentro(encuentro)
    encuentros_corte = ENCUENTROS_POR_CORTE[corte]
    encuentros_guias_corte = [e for e in encuentros_corte if e <= max_guias_efectivo]
    scores = calcular_puntajes_por_corte(asignacion, incluir_examenes=True)
    usado_corte = scores.get(corte, 0)

    examen_existe = ProyectoExamen.objects.filter(
        asignacion_plan=asignacion, periodo_corte=corte
    ).exists()
    reserva = RESERVA_EXAMEN_CORTE if (reservar_examen and not examen_existe) else 0
    techo_acumulado = max(0, PUNTAJE_MAX_POR_CORTE - reserva)
    saldo_corte = max(0, techo_acumulado - usado_corte)

    silabos_existentes = set(
        Silabo.objects.filter(
            asignacion_plan=asignacion, encuentros__in=encuentros_corte
        ).values_list("encuentros", flat=True)
    )
    guias_cubiertas = set()
    for g in Guia.objects.filter(silabo__asignacion_plan=asignacion).select_related("silabo"):
        enc_g = g.numero_encuentro if g.numero_encuentro in encuentros_guias_corte else g.silabo.encuentros
        if enc_g in encuentros_guias_corte:
            guias_cubiertas.add(enc_g)

    silabos_pendientes = [e for e in encuentros_corte if e not in silabos_existentes]
    guias_pendientes = [e for e in encuentros_guias_corte if e not in guias_cubiertas]

    if not es_guia and encuentro not in silabos_pendientes:
        silabos_pendientes.append(encuentro)
    if es_guia and encuentro in encuentros_guias_corte and encuentro not in guias_pendientes:
        guias_pendientes.append(encuentro)

    otros_s = max(0, len(silabos_pendientes) - (0 if es_guia else 1))
    otros_g = max(0, len(guias_pendientes) - (1 if es_guia else 0))
    es_ultimo_en_corte = (otros_s == 0 and otros_g == 0)

    peso_silabo = 1.0
    peso_guia = 2.5
    peso_actual = peso_guia if es_guia else peso_silabo
    peso_total = peso_silabo * len(silabos_pendientes) + peso_guia * len(guias_pendientes)

    if saldo_corte <= 0:
        objetivo = 0
        maximo = 0
    elif es_ultimo_en_corte:
        objetivo = saldo_corte
        maximo = saldo_corte
    else:
        objetivo_bruto = round((saldo_corte * peso_actual) / max(peso_total, peso_actual))
        reserva_minima = otros_s * 2 + otros_g * 5
        techo_con_reserva = max(0, saldo_corte - reserva_minima)
        if techo_con_reserva == 0:
            techo_con_reserva = max(0, saldo_corte - (otros_s + otros_g))

        objetivo = min(saldo_corte, max(1, min(objetivo_bruto, techo_con_reserva or saldo_corte)))
        holgura = 4 if es_guia else 2
        maximo = min(saldo_corte, max(objetivo, min(objetivo + holgura, techo_con_reserva or objetivo)))

    return {
        "corte": corte,
        "encuentros_corte": encuentros_corte,
        "encuentros_guias_corte": encuentros_guias_corte,
        "max_guias": max_guias_efectivo,
        "usado_corte": usado_corte,
        "saldo_corte": saldo_corte,
        "presupuesto_objetivo": objetivo,
        "presupuesto_max": maximo,
        "es_ultimo_en_corte": es_ultimo_en_corte,
        "scores_todos_cortes": scores,
    }


def calcular_tiempos_y_fechas(
    asignacion,
    encuentro,
    unidad_info=None,
    silabo=None,
    numero_actividades=4,
    max_guias=None,
):
    """
    Calcula fechas semanales coherentes con el ciclo del trimestre, metas de minutos
    presenciales (11 sílabos) e independientes (10 guías por defecto o 11 si se restaura)
    según Plan_de_estudio, y ventana de fechas de entrega.
    """
    from plan_de_estudio.models import Guia, Silabo, obtener_max_encuentros_guia

    max_guias_efectivo = (
        obtener_max_encuentros_guia()
        if max_guias is None
        else max(1, min(TOTAL_ENCUENTROS, int(max_guias)))
    )
    plan = asignacion.plan_de_estudio
    trimestre_lectivo = getattr(asignacion, "trimestre_lectivo", None)
    if trimestre_lectivo:
        inicio_ciclo, fin_ciclo, ciclo_nombre = obtener_rango_por_trimestre_lectivo(
            trimestre_lectivo
        )
    else:
        fecha_ref = (
            asignacion.fecha_asignacion.date()
            if getattr(asignacion, "fecha_asignacion", None)
            else timezone.localdate()
        )
        inicio_ciclo, fin_ciclo, ciclo_nombre = obtener_rango_ciclo_actual(fecha_ref=fecha_ref)

    silabo_anterior = (
        Silabo.objects.filter(asignacion_plan=asignacion, encuentros__lt=encuentro)
        .order_by("-encuentros")
        .first()
    )
    silabo_siguiente = (
        Silabo.objects.filter(asignacion_plan=asignacion, encuentros__gt=encuentro)
        .order_by("encuentros")
        .first()
    )

    if silabo and getattr(silabo, "encuentros", None) == encuentro and getattr(silabo, "fecha", None):
        fecha_encuentro = silabo.fecha
    elif silabo_anterior and silabo_anterior.fecha:
        fecha_encuentro = silabo_anterior.fecha + datetime.timedelta(
            days=7 * (encuentro - silabo_anterior.encuentros)
        )
    elif silabo_siguiente and silabo_siguiente.fecha:
        fecha_encuentro = silabo_siguiente.fecha - datetime.timedelta(
            days=7 * (silabo_siguiente.encuentros - encuentro)
        )
    else:
        primer_sabado = inicio_ciclo + datetime.timedelta(days=(5 - inicio_ciclo.weekday()) % 7)
        fecha_encuentro = primer_sabado + datetime.timedelta(days=7 * (encuentro - 1))

    if encuentro < TOTAL_ENCUENTROS:
        fecha_entrega_min = fecha_encuentro + datetime.timedelta(days=1)
        fecha_entrega_max = fecha_encuentro + datetime.timedelta(days=6)
    else:
        fecha_entrega_min = fecha_encuentro - datetime.timedelta(days=5)
        fecha_entrega_max = fecha_encuentro

    # Horas presenciales (Plan_de_estudio): siempre distribuidas en los 11 sílabos
    total_presenciales_min = max(60, int(plan.horas_presenciales or 24) * 60)
    silabos_otros = Silabo.objects.filter(asignacion_plan=asignacion).exclude(encuentros=encuentro)
    usado_presenciales_min = sum(
        (s.tiempo_primer_momento or 0)
        + (s.tiempo_segundo_momento_teorica or 0)
        + (s.tiempo_segundo_momento_practica or 0)
        + (s.tiempo_tercer_momento or 0)
        for s in silabos_otros
    )
    restantes_silabos = max(1, TOTAL_ENCUENTROS - silabos_otros.count())
    restante_presencial = max(60, total_presenciales_min - usado_presenciales_min)
    min_clase_objetivo = max(60, min(240, round(restante_presencial / restantes_silabos)))

    t1_sug = 15 if min_clase_objetivo >= 95 else 10
    t3_sug = 15 if min_clase_objetivo >= 95 else 10
    t2_total = max(30, min_clase_objetivo - t1_sug - t3_sug)
    if unidad_info and (unidad_info.get("horas_teoricas", 0) + unidad_info.get("horas_practicas", 0)) > 0:
        ht = unidad_info["horas_teoricas"]
        hp = unidad_info["horas_practicas"]
        ratio_t = max(0.25, min(0.75, ht / (ht + hp)))
    else:
        ratio_t = 0.45
    t2_teo_sug = max(10, round(t2_total * ratio_t))
    t2_pra_sug = max(10, t2_total - t2_teo_sug)

    # Horas de estudio independiente (Plan_de_estudio): distribuidas en max_guias_efectivo (10 por defecto, 11 si se restaura)
    total_indep_min = max(60, int(plan.horas_estudio_independiente or 70) * 60)
    guias_otras = Guia.objects.filter(
        silabo__asignacion_plan=asignacion,
        numero_encuentro__lte=max_guias_efectivo,
    ).exclude(numero_encuentro=encuentro)
    usado_indep_min = sum(
        sum(int(getattr(g, f"tiempo_minutos_{i}", 0) or 0) for i in range(1, 5))
        for g in guias_otras
    )
    restantes_guias = max(1, max_guias_efectivo - guias_otras.count())
    restante_indep = max(60, total_indep_min - usado_indep_min)
    min_indep_objetivo = max(60, min(720, round(restante_indep / restantes_guias)))

    return {
        "ciclo_nombre": ciclo_nombre,
        "inicio_ciclo": inicio_ciclo.isoformat(),
        "fin_ciclo": fin_ciclo.isoformat(),
        "fecha_encuentro": fecha_encuentro.isoformat(),
        "fecha_entrega_min": fecha_entrega_min.isoformat(),
        "fecha_entrega_max": fecha_entrega_max.isoformat(),
        "max_guias": max_guias_efectivo,
        "horas_presenciales_plan": int(plan.horas_presenciales or 24),
        "horas_independientes_plan": int(plan.horas_estudio_independiente or 70),
        "usado_presenciales_min": usado_presenciales_min,
        "min_clase_objetivo": min_clase_objetivo,
        "t1_sugerido": t1_sug,
        "t2_teorica_sugerido": t2_teo_sug,
        "t2_practica_sugerido": t2_pra_sug,
        "t3_sugerido": t3_sug,
        "usado_indep_min": usado_indep_min,
        "min_indep_objetivo": min_indep_objetivo,
        "min_por_tarea_aprox": max(15, round(min_indep_objetivo / max(1, int(numero_actividades or 4)))),
    }


def construir_historial_compacto(asignacion, encontro_limite):
    """
    Construye un resumen compacto de encuentros anteriores (< encontro_limite),
    incluyendo sílabos y TODAS las 4 tareas de cada guía previa, además de las
    técnicas e instrumentos recientes para evitar monotonía y duplicación aula/hogar.
    """
    from plan_de_estudio.models import Guia, Silabo

    silabos = list(
        Silabo.objects.filter(asignacion_plan=asignacion, encuentros__lt=encontro_limite)
        .prefetch_related("guias")
        .order_by("encuentros")
    )
    guias_extra = {
        g.numero_encuentro: g
        for g in Guia.objects.filter(
            silabo__asignacion_plan=asignacion,
            numero_encuentro__lt=encontro_limite,
        ).order_by("numero_encuentro")
    }

    if not silabos and not guias_extra:
        return {
            "tiene_historial": False,
            "resumen_texto": "Ningún encuentro previo registrado todavía.",
            "tecnicas_clase_recientes": [],
            "tecnicas_guia_recientes": [],
        }

    lineas = []
    tecnicas_clase_recientes = []
    tecnicas_guia_recientes = []
    silabos_por_enc = {s.encuentros: s for s in silabos}
    todos_encuentros = sorted(set(silabos_por_enc.keys()) | set(guias_extra.keys()))

    for enc in todos_encuentros:
        s = silabos_por_enc.get(enc)
        guia = None
        if s is not None:
            guia = s.guias.first()
        if guia is None:
            guia = guias_extra.get(enc)

        if s is not None:
            tec_s = ", ".join(s.tecnica_evaluacion) if isinstance(s.tecnica_evaluacion, (list, tuple)) else str(s.tecnica_evaluacion or "")
            if tec_s:
                tecnicas_clase_recientes.append(f"E{enc}: {tec_s} / {s.instrumento_evaluacion}")
            lineas.append(
                f"E{enc} [{s.unidad} — {_recortar(s.nombre_de_la_unidad, 45)} | {s.fecha}]: "
                f"Tema='{_recortar(s.contenido_tematico, 130)}' | "
                f"Clase=({s.tipo_segundo_momento_claseteoria} + {s.tipo_segundo_momento_practica}) | "
                f"ActividadAula='{_recortar(s.actividad_aprendizaje, 100)}' | "
                f"Eval={tec_s}/{s.instrumento_evaluacion} ({s.puntaje}pts)"
            )

        if guia is not None:
            tareas_txt = []
            for t in range(1, 5):
                act = getattr(guia, f"actividad_aprendizaje_{t}", None)
                tema = getattr(guia, f"contenido_tematico_{t}", None)
                if not (act or tema):
                    continue
                tec_t = getattr(guia, f"tecnica_evaluacion_{t}", "") or ""
                inst_t = getattr(guia, f"instrumento_evaluacion_{t}", "") or ""
                pts_t = getattr(guia, f"puntaje_{t}", 0) or 0
                if tec_t:
                    tecnicas_guia_recientes.append(f"E{enc}-T{t}: {tec_t}/{inst_t}")
                tareas_txt.append(
                    f"T{t}[{_recortar(tema, 55)} -> {_recortar(act, 65)} | {tec_t}/{inst_t}, {pts_t}pts]"
                )
            if tareas_txt:
                lineas.append(f"   Guía E{enc}: " + "; ".join(tareas_txt))

    return {
        "tiene_historial": True,
        "resumen_texto": "\n".join(lineas),
        "tecnicas_clase_recientes": tecnicas_clase_recientes[-4:],
        "tecnicas_guia_recientes": tecnicas_guia_recientes[-6:],
    }
