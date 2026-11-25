"""
Utilidades de normalización y validación de respuestas de IA para Sílabos y Guías.
Garantiza compatibilidad estricta con los modelos de Django, MultiSelectField
y controles del frontend (<select>, checkboxes y validadores JS).
"""

import datetime
import re
import unicodedata

from plan_de_estudio.models import Guia, Silabo

SILABO_UNIDADES = [c[0] for c in Silabo.UNIDAD_LIST]
SILABO_TIPOS_PRIMER_MOMENTO = [c[0] for c in Silabo.TIPO_PRIMER_MOMENTO_LIST]
SILABO_TIPOS_SEGUNDO_TEORIA = [c[0] for c in Silabo.TIPO_SEGUNDO_MOMENTO_TEORIA_LIST]
SILABO_TIPOS_SEGUNDO_PRACTICA = [c[0] for c in Silabo.TIPO_SEGUNDO_MOMENTO_PRACTICA_LIST]
SILABO_TIPOS_TERCER_MOMENTO = [c[0] for c in Silabo.TIPO_TERCER_MOMENTO_LIST]
SILABO_EJES_TRANSVERSALES = [c[0] for c in Silabo.EJE_TRANSVERSAL_LIST]
SILABO_TECNICAS_EVALUACION = [c[0] for c in Silabo.TECNICA_EVALUACION_LIST]
SILABO_TIPOS_EVALUACION = [c[0] for c in Silabo.TIPO_EVALUACION_LIST]
SILABO_PERIODOS_TIEMPO = [c[0] for c in Silabo.PERIODO_TIEMPO_LIST]
SILABO_AGENTES_EVALUADORES = [c[0] for c in Silabo.AGENTE_EVALUADOR_LIST]
SILABO_INSTRUMENTOS_EVALUACION = [c[0] for c in Silabo.INSTRUMENTO_EVALUACION_LIST]
GUIA_TIPOS_OBJETIVO = [c[0] for c in Guia.TIPO_OBJETIVO_LIST]

ALIAS_INSTRUMENTO = {
    "lista de cotejo": "Listas de cotejo",
    "lista de chequeo": "Listas de cotejo",
    "listas de chequeo": "Listas de cotejo",
    "escala de valoracion": "Escalas de valoración",
    "escala valorativa": "Escalas de valoración",
    "rubrica": "Rúbrica",
    "rubrica analitica": "Rúbrica",
    "rubrica holistica": "Rúbrica",
    "cuestionario": "Prueba escrita",
    "examen": "Prueba escrita",
    "examen escrito": "Prueba escrita",
    "prueba": "Prueba escrita",
    "test": "Prueba escrita",
    "cuaderno": "Cuaderno del estudiante",
    "diario": "Diario de aprendizaje",
    "otro": "Otros",
}

ALIAS_TECNICA = {
    "exposicion": "Presentación oral",
    "exposicion oral": "Presentación oral",
    "exposiciones": "Presentación oral",
    "sustentacion": "Presentación oral",
    "defensa oral": "Presentación oral",
    "trabajo colaborativo": "Trabajo en grupo",
    "trabajo en equipo": "Trabajo en grupo",
    "trabajo en parejas": "Trabajo en grupo",
    "taller grupal": "Trabajo en grupo",
    "mapa conceptual": "Organizador gráfico",
    "mapa mental": "Organizador gráfico",
    "cuadro sinoptico": "Organizador gráfico",
    "diagrama": "Organizador gráfico",
    "participacion": "Observación",
    "observacion directa": "Observación",
    "cuestionario": "Preguntas",
    "preguntas y respuestas": "Preguntas",
    "interrogatorio": "Preguntas",
    "mesa redonda": "Debate",
    "foro": "Debate",
    "estudio de caso": "Otro",
    "resolucion de problemas": "Otro",
    "resolucion de ejercicios": "Otro",
    "practica de laboratorio": "Otro",
    "laboratorio": "Otro",
    "taller": "Otro",
}

ALIAS_PERIODO = {
    "1 corte": "I Corte Evaluativo",
    "primer corte": "I Corte Evaluativo",
    "i corte": "I Corte Evaluativo",
    "2 corte": "II Corte Evaluativo",
    "segundo corte": "II Corte Evaluativo",
    "ii corte": "II Corte Evaluativo",
    "3 corte": "III Corte Evaluativo",
    "tercer corte": "III Corte Evaluativo",
    "iii corte": "III Corte Evaluativo",
}

ALIAS_UNIDAD = {
    "1": "Unidad I",
    "unidad 1": "Unidad I",
    "primera unidad": "Unidad I",
    "2": "Unidad II",
    "unidad 2": "Unidad II",
    "segunda unidad": "Unidad II",
    "3": "Unidad III",
    "unidad 3": "Unidad III",
    "tercera unidad": "Unidad III",
    "4": "Unidad IV",
    "unidad 4": "Unidad IV",
    "cuarta unidad": "Unidad IV",
    "5": "Unidad V",
    "unidad 5": "Unidad V",
    "quinta unidad": "Unidad V",
    "6": "Unidad VI",
    "unidad 6": "Unidad VI",
    "sexta unidad": "Unidad VI",
}

ALIAS_EJE = {
    "tic": "Tecnología de la información y comunicación",
    "tics": "Tecnología de la información y comunicación",
    "tecnologia": "Tecnología de la información y comunicación",
    "tecnologias de la informacion": "Tecnología de la información y comunicación",
    "medio ambiente y ecologia": "Medio ambiente",
    "medioambiente y ecologia": "Medio ambiente",
    "ecologia": "Medio ambiente",
    "paz con fe": "Cultura de paz",
    "emprendimiento": "Emprendimiento e innovación",
}


def _normalizar_clave(texto):
    """Elimina tildes/diacríticos, pasa a minúsculas y colapsa espacios."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().lower()


def _a_texto(valor, separador="\n"):
    """Convierte listas o valores escalares a texto limpio."""
    if valor is None:
        return ""
    if isinstance(valor, list):
        partes = [str(item).strip() for item in valor if item is not None and str(item).strip()]
        return separador.join(partes)
    return str(valor).strip()


def _entero(valor, default, minimo=0, maximo=None):
    """Extrae un entero válido desde int, float o string numérico (ej. '30 min')."""
    num = None
    if isinstance(valor, bool):
        num = None
    elif isinstance(valor, (int, float)):
        num = int(round(valor))
    elif isinstance(valor, str):
        match = re.search(r"-?\d+", valor)
        if match:
            try:
                num = int(match.group(0))
            except ValueError:
                num = None
    if num is None:
        num = default
    if minimo is not None and num < minimo:
        num = minimo
    if maximo is not None and num > maximo:
        num = maximo
    return num


def _fecha_iso(valor, default):
    """Valida formato YYYY-MM-DD o devuelve la fecha por defecto."""
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, str):
        s = valor.strip()[:10]
        try:
            datetime.date.fromisoformat(s)
            return s
        except ValueError:
            pass
    return default


def _resolver_opcion(valor, opciones_validas, alias_map=None, default=None):
    """Mapea un valor a una de las opciones válidas del modelo."""
    if valor is None:
        return default
    raw = str(valor).strip()
    if not raw:
        return default
    if raw in opciones_validas:
        return raw

    norm_map = {_normalizar_clave(opt): opt for opt in opciones_validas}
    clave = _normalizar_clave(raw)
    if clave in norm_map:
        return norm_map[clave]

    if alias_map and clave in alias_map:
        mapped = alias_map[clave]
        if mapped in opciones_validas:
            return mapped

    # Coincidencia parcial por subcadena cuando una opción contiene o es contenida inequívocamente
    coincidencias = [
        opt for norm_opt, opt in norm_map.items()
        if norm_opt in clave or (len(clave) >= 5 and clave in norm_opt)
    ]
    if len(coincidencias) == 1:
        return coincidencias[0]

    if alias_map:
        for alias_k, alias_v in alias_map.items():
            if alias_k in clave and alias_v in opciones_validas:
                return alias_v

    return default


def _resolver_multiopcion(valor, opciones_validas, alias_map=None, max_choices=2, default=None):
    """Resuelve listas o textos combinados en una lista válida de hasta max_choices elementos."""
    if not valor:
        return [default] if default else []

    if isinstance(valor, list):
        candidatos = [str(v).strip() for v in valor if v is not None and str(v).strip()]
    else:
        texto = str(valor).strip()
        # Verificar primero el texto completo para no partir opciones con 'y'/'e' internos
        match_entero = _resolver_opcion(texto, opciones_validas, alias_map=alias_map, default=None)
        if match_entero:
            return [match_entero]
        candidatos = [
            p.strip()
            for p in re.split(r"\s*[,;/\n]\s*|\s+y\s+", texto, flags=re.IGNORECASE)
            if p and p.strip()
        ]

    resultado = []
    for cand in candidatos:
        resuelto = _resolver_opcion(cand, opciones_validas, alias_map=alias_map, default=None)
        if resuelto and resuelto not in resultado:
            resultado.append(resuelto)
        if len(resultado) >= max_choices:
            break

    if not resultado and default:
        return [default]
    return resultado


def _parse_fecha(valor):
    if isinstance(valor, datetime.date):
        return valor
    try:
        return datetime.date.fromisoformat(str(valor).strip()[:10])
    except (ValueError, TypeError):
        return None


def normalizar_respuesta_silabo(
    data,
    plan_codigo=None,
    encuentro=None,
    fecha_default=None,
    unidad_default=None,
    nombre_unidad_default=None,
    unidad_forzada=None,
    corte_forzado=None,
    puntaje_objetivo=None,
    puntaje_max=None,
    forzar_exacto=False,
    sin_guia_encuentro=False,
    minutos_clase_objetivo=None,
    fecha_objetivo=None,
):
    """
    Normaliza y valida el diccionario de respuesta de IA para un Sílabo.
    Garantiza que todos los campos requeridos, presupuestos de corte/horas y
    listas de selección coincidan con SilaboForm.
    """
    from plan_de_estudio.utils.curriculum_planner import reparto_hamilton

    out = dict(data or {})
    hoy_iso = fecha_objetivo or fecha_default or datetime.date.today().isoformat()

    if plan_codigo:
        out["codigo"] = str(plan_codigo).strip()
    elif out.get("codigo"):
        out["codigo"] = str(out["codigo"]).strip()[:20]

    if encuentro is not None:
        enc_num = _entero(encuentro, 1, minimo=1, maximo=11)
    else:
        enc_num = _entero(out.get("encuentros"), 1, minimo=1, maximo=11)
    out["encuentros"] = enc_num

    out["fecha"] = _fecha_iso(out.get("fecha"), hoy_iso)
    if fecha_objetivo:
        f_obj = _parse_fecha(fecha_objetivo)
        f_out = _parse_fecha(out["fecha"])
        if f_obj and (f_out is None or abs((f_out - f_obj).days) > 2):
            out["fecha"] = f_obj.isoformat()

    unidad_resuelta = _resolver_opcion(
        out.get("unidad"),
        SILABO_UNIDADES,
        ALIAS_UNIDAD,
        default=unidad_default or "Unidad I",
    )
    unidad_cambiada = False
    if unidad_forzada:
        u_obj = _resolver_opcion(unidad_forzada, SILABO_UNIDADES, ALIAS_UNIDAD, default=unidad_resuelta)
        unidad_cambiada = (unidad_resuelta != u_obj)
        out["unidad"] = u_obj
    else:
        out["unidad"] = unidad_resuelta

    campos_texto = [
        "nombre_de_la_unidad", "contenido_tematico",
        "objetivo_conceptual", "objetivo_procedimental", "objetivo_actitudinal",
        "detalle_primer_momento", "recursos_primer_momento",
        "clase_teorica", "clase_practica", "recursos_segundo_momento",
        "detalle_tercer_momento", "recursos_tercer_momento",
        "detalle_eje_transversal", "actividad_aprendizaje", "criterios_evaluacion",
    ]
    for campo in campos_texto:
        out[campo] = _a_texto(out.get(campo))

    if ((unidad_forzada or not out["nombre_de_la_unidad"] or unidad_cambiada) and nombre_unidad_default):
        out["nombre_de_la_unidad"] = str(nombre_unidad_default).strip()
    out["nombre_de_la_unidad"] = out["nombre_de_la_unidad"][:255]

    out["tipo_primer_momento"] = _resolver_opcion(
        out.get("tipo_primer_momento"),
        SILABO_TIPOS_PRIMER_MOMENTO,
        default="Presentación de asignatura" if enc_num == 1 else "Valoración del trabajo independiente",
    )
    out["tipo_segundo_momento_claseteoria"] = _resolver_opcion(
        out.get("tipo_segundo_momento_claseteoria") or out.get("tipo_segundo_momento_teorica"),
        SILABO_TIPOS_SEGUNDO_TEORIA,
        default="Conferencia",
    )
    out["tipo_segundo_momento_practica"] = _resolver_opcion(
        out.get("tipo_segundo_momento_practica"),
        SILABO_TIPOS_SEGUNDO_PRACTICA,
        default="Taller",
    )

    out["tiempo_primer_momento"] = _entero(out.get("tiempo_primer_momento"), 15, minimo=1)

    # Soporte para el campo legado 'tiempo_segundo_momento' si el modelo aún lo devuelve
    t2_teo = out.get("tiempo_segundo_momento_teorica")
    t2_pra = out.get("tiempo_segundo_momento_practica")
    if (t2_teo is None or str(t2_teo).strip() == "") and (t2_pra is None or str(t2_pra).strip() == ""):
        t2_total = _entero(out.get("tiempo_segundo_momento"), 60, minimo=2)
        out["tiempo_segundo_momento_teorica"] = max(1, t2_total // 2)
        out["tiempo_segundo_momento_practica"] = max(1, t2_total - out["tiempo_segundo_momento_teorica"])
    else:
        out["tiempo_segundo_momento_teorica"] = _entero(t2_teo, 30, minimo=1)
        out["tiempo_segundo_momento_practica"] = _entero(t2_pra, 30, minimo=1)

    out["tiempo_tercer_momento"] = _entero(out.get("tiempo_tercer_momento"), 15, minimo=1)

    if minutos_clase_objetivo is not None and int(minutos_clase_objetivo) > 0:
        meta_min = int(minutos_clase_objetivo)
        suma_m = (
            out["tiempo_primer_momento"]
            + out["tiempo_segundo_momento_teorica"]
            + out["tiempo_segundo_momento_practica"]
            + out["tiempo_tercer_momento"]
        )
        if abs(suma_m - meta_min) > max(15, int(0.15 * meta_min)):
            t1 = min(25, max(10, out["tiempo_primer_momento"])) if meta_min >= 60 else max(5, min(15, out["tiempo_primer_momento"]))
            t3 = min(25, max(10, out["tiempo_tercer_momento"])) if meta_min >= 60 else max(5, min(15, out["tiempo_tercer_momento"]))
            restante_t2 = max(2, meta_min - t1 - t3)
            t2t, t2p = reparto_hamilton(
                restante_t2,
                [max(1, out["tiempo_segundo_momento_teorica"]), max(1, out["tiempo_segundo_momento_practica"])],
                minimo_por_item=10 if restante_t2 >= 20 else 1,
            )
            out["tiempo_primer_momento"] = t1
            out["tiempo_segundo_momento_teorica"] = t2t
            out["tiempo_segundo_momento_practica"] = t2p
            out["tiempo_tercer_momento"] = t3

    out["tipo_tercer_momento"] = _resolver_multiopcion(
        out.get("tipo_tercer_momento"),
        SILABO_TIPOS_TERCER_MOMENTO,
        max_choices=2,
        default="Realimentación del aprendizaje" if sin_guia_encuentro else "Orientación del estudio independiente",
    )
    if sin_guia_encuentro:
        filtrados_m3 = [
            opt for opt in out["tipo_tercer_momento"]
            if opt != "Orientación del estudio independiente"
        ]
        out["tipo_tercer_momento"] = filtrados_m3 or ["Realimentación del aprendizaje"]
    out["eje_transversal"] = _resolver_multiopcion(
        out.get("eje_transversal"),
        SILABO_EJES_TRANSVERSALES,
        alias_map=ALIAS_EJE,
        max_choices=2,
        default="Tecnología de la información y comunicación",
    )

    corte_default = corte_forzado or (
        "I Corte Evaluativo" if enc_num <= 4
        else ("II Corte Evaluativo" if enc_num <= 8 else "III Corte Evaluativo")
    )
    out["tecnica_evaluacion"] = _resolver_multiopcion(
        out.get("tecnica_evaluacion"),
        SILABO_TECNICAS_EVALUACION,
        alias_map=ALIAS_TECNICA,
        max_choices=2,
        default="Otro",
    )
    out["tipo_evaluacion"] = _resolver_multiopcion(
        out.get("tipo_evaluacion"),
        SILABO_TIPOS_EVALUACION,
        max_choices=2,
        default="Formativa",
    )
    if corte_forzado:
        out["periodo_tiempo_programado"] = _resolver_opcion(
            corte_forzado,
            SILABO_PERIODOS_TIEMPO,
            alias_map=ALIAS_PERIODO,
            default=corte_default,
        )
    else:
        out["periodo_tiempo_programado"] = _resolver_opcion(
            out.get("periodo_tiempo_programado"),
            SILABO_PERIODOS_TIEMPO,
            alias_map=ALIAS_PERIODO,
            default=corte_default,
        )
    out["tiempo_minutos"] = _entero(out.get("tiempo_minutos"), 20, minimo=0)
    out["agente_evaluador"] = _resolver_multiopcion(
        out.get("agente_evaluador"),
        SILABO_AGENTES_EVALUADORES,
        max_choices=2,
        default="Heteroevaluación",
    )
    out["instrumento_evaluacion"] = _resolver_opcion(
        out.get("instrumento_evaluacion"),
        SILABO_INSTRUMENTOS_EVALUACION,
        alias_map=ALIAS_INSTRUMENTO,
        default="Rúbrica",
    )

    default_pts = int(puntaje_objetivo) if puntaje_objetivo is not None else 10
    puntaje_val = _entero(out.get("puntaje"), default_pts, minimo=0, maximo=100)
    if puntaje_max is not None:
        cap = max(0, int(puntaje_max))
        if cap == 0:
            puntaje_val = 0
        elif forzar_exacto and puntaje_objetivo is not None:
            puntaje_val = min(cap, max(0, int(puntaje_objetivo)))
        elif puntaje_val > cap:
            puntaje_val = min(cap, max(0, default_pts)) if puntaje_objetivo is not None else cap
        elif puntaje_val == 0 and puntaje_objetivo and int(puntaje_objetivo) > 0:
            puntaje_val = min(cap, int(puntaje_objetivo))
    elif forzar_exacto and puntaje_objetivo is not None:
        puntaje_val = max(0, min(100, int(puntaje_objetivo)))
    out["puntaje"] = puntaje_val

    return out


def _desanidar_tareas_guia(data):
    """Aplana posibles estructuras anidadas tipo {'tarea_1': {...}} en llaves planas *_1..*_4."""
    out = dict(data or {})
    for n in range(1, 5):
        bloque = out.get(f"tarea_{n}")
        if isinstance(bloque, dict):
            for k, v in bloque.items():
                clave_plana = k if k.endswith(f"_{n}") else f"{k}_{n}"
                out.setdefault(clave_plana, v)
    return out


def normalizar_respuesta_guia(
    data,
    numero_actividades=4,
    encuentro=None,
    unidad_default=None,
    nombre_unidad_default=None,
    fecha_default=None,
    corte_default=None,
    forzar_corte=False,
    presupuesto_objetivo=None,
    presupuesto_max=None,
    forzar_exacto=False,
    minutos_totales_objetivo=None,
    fecha_entrega_min=None,
    fecha_entrega_max=None,
    unidad_forzada=None,
    fecha_objetivo=None,
    max_encuentros=11,
):
    """
    Normaliza y valida el diccionario de respuesta de IA para una Guía de Estudio Independiente.
    Asegura opciones válidas por tarea, fechas ISO en rango, carga horaria y suma de puntajes
    respetando el presupuesto del Corte Evaluativo.
    """
    from plan_de_estudio.utils.curriculum_planner import reparto_hamilton

    out = _desanidar_tareas_guia(data)
    num_act = _entero(numero_actividades, 4, minimo=1, maximo=4)
    max_enc = _entero(max_encuentros, 11, minimo=1, maximo=11)
    enc_num = _entero(encuentro if encuentro is not None else out.get("numero_encuentro"), 1, minimo=1, maximo=max_enc)
    hoy_iso = fecha_objetivo or fecha_default or datetime.date.today().isoformat()

    out["numero_encuentro"] = enc_num
    out["fecha"] = _fecha_iso(out.get("fecha"), hoy_iso)
    if fecha_objetivo:
        f_obj = _parse_fecha(fecha_objetivo)
        f_out = _parse_fecha(out["fecha"])
        if f_obj and (f_out is None or abs((f_out - f_obj).days) > 2):
            out["fecha"] = f_obj.isoformat()

    unidad_resuelta = _resolver_opcion(
        out.get("unidad"),
        SILABO_UNIDADES,
        ALIAS_UNIDAD,
        default=unidad_default or "Unidad I",
    )
    unidad_cambiada = False
    if unidad_forzada:
        u_obj = _resolver_opcion(unidad_forzada, SILABO_UNIDADES, ALIAS_UNIDAD, default=unidad_resuelta)
        unidad_cambiada = (unidad_resuelta != u_obj)
        out["unidad"] = u_obj
    else:
        out["unidad"] = unidad_resuelta

    nombre_u = _a_texto(out.get("nombre_de_la_unidad"))
    if ((unidad_forzada or not nombre_u or unidad_cambiada) and nombre_unidad_default):
        nombre_u = str(nombre_unidad_default).strip()
    out["nombre_de_la_unidad"] = nombre_u[:255]

    default_corte = corte_default or (
        "I Corte Evaluativo" if enc_num <= 4
        else ("II Corte Evaluativo" if enc_num <= 8 else "III Corte Evaluativo")
    )
    fecha_base = _parse_fecha(out["fecha"]) or datetime.date.today()
    min_entrega_dt = _parse_fecha(fecha_entrega_min)
    max_entrega_dt = _parse_fecha(fecha_entrega_max)

    for n in range(1, num_act + 1):
        out[f"tipo_objetivo_{n}"] = _resolver_opcion(
            out.get(f"tipo_objetivo_{n}"),
            GUIA_TIPOS_OBJETIVO,
            default="Procedimental" if n % 2 == 0 else "Conceptual",
        )
        for campo_txt, sep in [
            ("objetivo_aprendizaje", "\n"),
            ("contenido_tematico", "\n"),
            ("actividad_aprendizaje", "\n"),
            ("criterios_evaluacion", "\n"),
            ("recursos_didacticos", ", "),
        ]:
            out[f"{campo_txt}_{n}"] = _a_texto(out.get(f"{campo_txt}_{n}"), separador=sep)

        out[f"tecnica_evaluacion_{n}"] = _resolver_opcion(
            out.get(f"tecnica_evaluacion_{n}"),
            SILABO_TECNICAS_EVALUACION,
            alias_map=ALIAS_TECNICA,
            default="Otro",
        )
        out[f"tipo_evaluacion_{n}"] = _resolver_opcion(
            out.get(f"tipo_evaluacion_{n}"),
            SILABO_TIPOS_EVALUACION,
            default="Formativa",
        )
        out[f"instrumento_evaluacion_{n}"] = _resolver_opcion(
            out.get(f"instrumento_evaluacion_{n}"),
            SILABO_INSTRUMENTOS_EVALUACION,
            alias_map=ALIAS_INSTRUMENTO,
            default="Rúbrica",
        )
        out[f"agente_evaluador_{n}"] = _resolver_multiopcion(
            out.get(f"agente_evaluador_{n}"),
            SILABO_AGENTES_EVALUADORES,
            max_choices=2,
            default="Heteroevaluación",
        )
        out[f"tiempo_minutos_{n}"] = _entero(out.get(f"tiempo_minutos_{n}"), 60, minimo=1)
        if forzar_corte:
            out[f"periodo_tiempo_programado_{n}"] = _resolver_opcion(
                default_corte,
                SILABO_PERIODOS_TIEMPO,
                alias_map=ALIAS_PERIODO,
                default=default_corte,
            )
        else:
            out[f"periodo_tiempo_programado_{n}"] = _resolver_opcion(
                out.get(f"periodo_tiempo_programado_{n}"),
                SILABO_PERIODOS_TIEMPO,
                alias_map=ALIAS_PERIODO,
                default=default_corte,
            )
        out[f"puntaje_{n}"] = _entero(out.get(f"puntaje_{n}"), 10, minimo=0, maximo=100)

        if min_entrega_dt and max_entrega_dt and max_entrega_dt >= min_entrega_dt:
            span = (max_entrega_dt - min_entrega_dt).days
            if enc_num == 11:
                offset = min(span, max(0, num_act - n))
                entrega_sug = max_entrega_dt - datetime.timedelta(days=offset)
            else:
                paso = round((span * n) / max(1, num_act))
                entrega_sug = min(max_entrega_dt, min_entrega_dt + datetime.timedelta(days=paso))
            entrega_default = entrega_sug.isoformat()
        else:
            entrega_sug = None
            entrega_default = (fecha_base + datetime.timedelta(days=min(7, n + 2))).isoformat()

        fecha_ent_iso = _fecha_iso(out.get(f"fecha_entrega_{n}"), entrega_default)
        fecha_ent_dt = _parse_fecha(fecha_ent_iso)
        if min_entrega_dt and (fecha_ent_dt is None or fecha_ent_dt < min_entrega_dt):
            fecha_ent_iso = entrega_default
        elif max_entrega_dt and (fecha_ent_dt is None or fecha_ent_dt > max_entrega_dt):
            fecha_ent_iso = entrega_default
        out[f"fecha_entrega_{n}"] = fecha_ent_iso

    # Limpiar posibles llaves de tareas opcionales que exceden numero_actividades
    prefijos_tarea = (
        "tipo_objetivo", "objetivo_aprendizaje", "contenido_tematico",
        "actividad_aprendizaje", "tecnica_evaluacion", "tipo_evaluacion",
        "instrumento_evaluacion", "criterios_evaluacion", "agente_evaluador",
        "tiempo_minutos", "recursos_didacticos", "periodo_tiempo_programado",
        "puntaje", "fecha_entrega",
    )
    for n in range(num_act + 1, 5):
        for pref in prefijos_tarea:
            out.pop(f"{pref}_{n}", None)

    # Calibrar carga horaria independiente cuando el total se desvía del plan de estudio
    if minutos_totales_objetivo is not None and int(minutos_totales_objetivo) > 0:
        meta_min = int(minutos_totales_objetivo)
        tiempos = [out.get(f"tiempo_minutos_{n}", 60) for n in range(1, num_act + 1)]
        suma_t = sum(tiempos)
        if abs(suma_t - meta_min) > max(20, int(0.15 * meta_min)):
            min_item = 15 if meta_min >= 15 * num_act else 1
            ajustados_t = reparto_hamilton(meta_min, [max(1, t) for t in tiempos], minimo_por_item=min_item)
            for n, val in enumerate(ajustados_t, start=1):
                out[f"tiempo_minutos_{n}"] = val

    # Garantizar el presupuesto de puntaje dentro del Corte Evaluativo (<= 100 acumulado)
    limite_max = 100 if presupuesto_max is None else max(0, int(presupuesto_max))
    puntajes = [out.get(f"puntaje_{n}", 0) for n in range(1, num_act + 1)]
    suma = sum(puntajes)

    if limite_max == 0:
        for n in range(1, num_act + 1):
            out[f"puntaje_{n}"] = 0
    elif (
        suma > limite_max
        or (forzar_exacto and presupuesto_objetivo is not None and suma != min(limite_max, int(presupuesto_objetivo)))
        or (suma == 0 and presupuesto_objetivo is not None and int(presupuesto_objetivo) > 0)
    ):
        target = min(limite_max, max(0, int(presupuesto_objetivo))) if presupuesto_objetivo is not None else limite_max
        pesos = puntajes if suma > 0 else [1] * num_act
        min_item = 1 if target >= num_act else 0
        ajustados = reparto_hamilton(target, pesos, minimo_por_item=min_item)
        for n, val in enumerate(ajustados, start=1):
            out[f"puntaje_{n}"] = val

    return out
