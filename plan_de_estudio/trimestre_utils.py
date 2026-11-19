import datetime
import re

from django.core.exceptions import ValidationError
from django.utils import timezone

TRIMESTRES_LECTIVOS_ORDEN = ('I', 'II', 'III', 'IV')

TRIMESTRE_LECTIVO_RE = re.compile(r'^(\d{4})-(I|II|III|IV)$')

TRIMESTRE_LECTIVO_MESES = {
    'I': 'Mar – May',
    'II': 'Jun – Ago',
    'III': 'Sep – Nov',
    'IV': 'Dic – Feb',
}


def parsear_trimestre_lectivo(codigo):
    """
    Valida y descompone un código de trimestre lectivo ('AAAA-I/II/III/IV').
    Retorna (anio, trimestre) o None si el formato es inválido.
    """
    if not codigo:
        return None
    match = TRIMESTRE_LECTIVO_RE.match(str(codigo).strip())
    if not match:
        return None
    anio = int(match.group(1))
    if anio < 2000 or anio > 2100:
        return None
    return anio, match.group(2)


def validar_trimestre_lectivo(value):
    """Validador de modelo/formulario para el campo trimestre_lectivo."""
    if not parsear_trimestre_lectivo(value):
        raise ValidationError(
            "Seleccione un trimestre lectivo válido (ej. 2026-IV)."
        )


def obtener_trimestre_lectivo_de_fecha(fecha=None):
    """
    Convierte una fecha de referencia al código de trimestre lectivo calendario
    ('AAAA-I', 'AAAA-II', 'AAAA-III' o 'AAAA-IV').
    """
    if fecha is None:
        ref = timezone.localdate()
    elif isinstance(fecha, datetime.datetime):
        ref = timezone.localtime(fecha).date() if timezone.is_aware(fecha) else fecha.date()
    else:
        ref = fecha

    mes = ref.month
    year = ref.year

    if 3 <= mes <= 5:
        return f"{year}-I"
    if 6 <= mes <= 8:
        return f"{year}-II"
    if 9 <= mes <= 11:
        return f"{year}-III"
    if mes == 12:
        return f"{year}-IV"
    return f"{year - 1}-IV"


def obtener_rango_por_trimestre_lectivo(codigo):
    """
    Dado un código de trimestre lectivo ('AAAA-I/II/III/IV'), retorna
    (fecha_inicio, fecha_fin, ciclo_nombre).
    """
    parsed = parsear_trimestre_lectivo(codigo)
    if not parsed:
        parsed = parsear_trimestre_lectivo(obtener_trimestre_lectivo_de_fecha())

    year, trim = parsed
    if trim == 'I':
        return (
            datetime.date(year, 3, 1),
            datetime.date(year, 5, 31),
            f"Ciclo Mar – May {year} (Trimestre I)",
        )
    if trim == 'II':
        return (
            datetime.date(year, 6, 1),
            datetime.date(year, 8, 31),
            f"Ciclo Jun – Ago {year} (Trimestre II)",
        )
    if trim == 'III':
        return (
            datetime.date(year, 9, 1),
            datetime.date(year, 11, 30),
            f"Ciclo Sep – Nov {year} (Trimestre III)",
        )
    fin = datetime.date(year + 1, 3, 1) - datetime.timedelta(days=1)
    return (
        datetime.date(year, 12, 1),
        fin,
        f"Ciclo Dic {year} – Feb {year + 1} (Trimestre IV)",
    )


def formatear_trimestre_lectivo(codigo, detallado=False):
    """Formatea un código 'AAAA-T' para visualización en admin y plantillas."""
    parsed = parsear_trimestre_lectivo(codigo)
    if not parsed:
        return str(codigo or "")
    year, trim = parsed
    if not detallado:
        return f"{year} - Trimestre {trim}"
    if trim == 'IV':
        return f"{year} - Trimestre IV (Dic {year} – Feb {year + 1})"
    return f"{year} - Trimestre {trim} ({TRIMESTRE_LECTIVO_MESES[trim]} {year})"


def clave_orden_trimestre_lectivo(codigo):
    """Retorna tupla (anio, indice_trimestre) para orden cronológico consistente."""
    parsed = parsear_trimestre_lectivo(codigo)
    if not parsed:
        return (0, -1)
    year, trim = parsed
    return (year, TRIMESTRES_LECTIVOS_ORDEN.index(trim))


def ordenar_codigos_trimestre_lectivo(codigos, descendente=False):
    """Filtra códigos válidos, elimina duplicados y ordena cronológicamente."""
    validos = {
        str(c).strip()
        for c in codigos
        if c and parsear_trimestre_lectivo(c)
    }
    return sorted(validos, key=clave_orden_trimestre_lectivo, reverse=descendente)


def generar_opciones_trimestre_lectivo(
    anio_inicio=2024,
    anios_futuros=2,
    incluir_vacio=True,
    etiqueta_vacio="---------",
    detallado=True,
    extra_values=None,
):
    """
    Genera opciones ordenadas de trimestres lectivos para formularios y filtros.
    """
    anio_max = timezone.localdate().year + anios_futuros
    codigos = [
        f"{anio}-{trim}"
        for anio in range(anio_inicio, anio_max + 1)
        for trim in TRIMESTRES_LECTIVOS_ORDEN
    ]

    if extra_values:
        codigos = ordenar_codigos_trimestre_lectivo([*codigos, *extra_values])

    opciones = [
        (codigo, formatear_trimestre_lectivo(codigo, detallado=detallado))
        for codigo in codigos
    ]
    if incluir_vacio:
        opciones.insert(0, ("", etiqueta_vacio))
    return opciones
