"""
Generador de documento Word (.docx) para el Proyecto de Examen UML.
Siempre crea una copia en memoria de la plantilla oficial `docx_templates/plantilla_proyecto_examen.docx`,
preservando el logotipo institucional, márgenes horizontales, tipografía y bloque de firmas.
"""

import io
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from .template_utils import get_docx_template

# Anchos exactos (dxa) de la plantilla oficial UML (suma = 14108 dxa = 9.80 in)
COL_WIDTHS_DXA = (4443, 4762, 3745, 1158)


def _set_cell_width_dxa(cell, width_dxa):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn('w:tcW'):
            tcPr.remove(child)
    tcW = OxmlElement('w:tcW')
    tcW.set(qn('w:w'), str(width_dxa))
    tcW.set(qn('w:type'), 'dxa')
    tcPr.append(tcW)


def _set_cell_margins(cell, top=80, bottom=80, left=110, right=110):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn('w:tcMar'):
            tcPr.remove(child)
    tcMar = OxmlElement('w:tcMar')
    for side, val in (('top', top), ('bottom', bottom), ('left', left), ('right', right)):
        node = OxmlElement(f'w:{side}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def _set_cell_shading(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn('w:shd'):
            tcPr.remove(child)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)


def _habilitar_repeticion_encabezado(row):
    trPr = row._tr.get_or_add_trPr()
    for child in list(trPr):
        if child.tag == qn('w:tblHeader'):
            trPr.remove(child)
    tblHeader = OxmlElement('w:tblHeader')
    trPr.append(tblHeader)


def _reemplazar_runs_parrafo(paragraph, segmentos, font_name='Arial', font_size=10):
    """
    Reemplaza el texto de un párrafo con una lista de tuplas (texto, bold, underline)
    conservando la alineación y estilos del párrafo.
    """
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)
    for texto, is_bold, is_underline in segmentos:
        run = paragraph.add_run(texto)
        run.bold = bool(is_bold)
        run.underline = bool(is_underline)
        run.font.name = font_name
        run.font.size = Pt(font_size)


def _escribir_texto_celda(cell, texto, bold_primera_linea=False, align=WD_ALIGN_PARAGRAPH.LEFT, font_size=9.5):
    cell.text = ""
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    lineas = str(texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for idx, linea in enumerate(lineas):
        p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.12
        run = p.add_run(linea)
        run.font.name = 'Arial'
        run.font.size = Pt(font_size)
        if bold_primera_linea and idx == 0:
            run.bold = True


def _marca(condicion):
    return "  X  " if condicion else "_____"


def generar_documento_proyecto_examen(proyecto_examen):
    """
    Genera una copia llenada de la plantilla oficial del Proyecto de Examen UML
    y devuelve un `io.BytesIO` listo para enviarse como descarga HTTP.
    """
    doc = get_docx_template('plantilla_proyecto_examen.docx')

    asignacion = proyecto_examen.asignacion_plan
    plan = asignacion.plan_de_estudio
    usuario = asignacion.usuario

    facilitador = (usuario.get_full_name() or usuario.username or "").strip()
    asignatura_nombre = plan.asignatura.nombre
    codigo_asignatura = plan.codigo or ""
    codigo_grupo = (proyecto_examen.codigo_grupo or "").strip() or "_________"
    carrera_txt = (proyecto_examen.carrera_texto or "").strip() or plan.carrera.nombre
    horas_presenciales = int(plan.horas_presenciales or 0)
    horas_independientes = int(plan.horas_estudio_independiente or 0)
    total_horas = horas_presenciales + horas_independientes

    fecha = proyecto_examen.fecha
    dia_str = f"{fecha.day:02d}" if fecha else "____"
    mes_str = f"{fecha.month:02d}" if fecha else "____"
    anio_str = f"{fecha.year}" if fecha else "______"

    municipio = (proyecto_examen.municipio or "Municipio Jalapa").strip()

    # P[0]: UNIVERSIDAD MARTÍN LUTERO + logo flotante -> NO modificar para preservar el logo intacto
    # P[1]: Municipio Jalapa
    if len(doc.paragraphs) > 1 and municipio and municipio != doc.paragraphs[1].text.strip():
        _reemplazar_runs_parrafo(doc.paragraphs[1], [(municipio, False, False)], font_name='Cambria', font_size=16)

    # P[2]: PROYECTO DE EXAMEN -> intacto
    # P[3]: Fecha, No. de evaluación, Año lectivo, Trimestre
    if len(doc.paragraphs) > 3:
        _reemplazar_runs_parrafo(doc.paragraphs[3], [
            ("Fecha: ", True, False),
            (f" {dia_str} / {mes_str} / {anio_str} ", False, True),
            (".\t\t", False, False),
            ("No. de evaluación: ", True, False),
            (f"  {proyecto_examen.numero_evaluacion}  ", False, True),
            ("\t\t", False, False),
            ("Año lectivo: ", True, False),
            (f"  {proyecto_examen.anio_lectivo}  ", False, True),
            ("\t", False, False),
            ("Trimestre: ", True, False),
            (f"  {proyecto_examen.trimestre}  ", False, True),
        ])

    # P[4]: Nombre de la asignatura, Código de asignatura, Código de grupo
    if len(doc.paragraphs) > 4:
        _reemplazar_runs_parrafo(doc.paragraphs[4], [
            ("Nombre de la asignatura: ", True, False),
            (f" {asignatura_nombre} ", False, True),
            ("   ", False, False),
            ("Código de asignatura: ", True, False),
            (f" {codigo_asignatura} ", False, True),
            ("\t", False, False),
            ("Código de grupo: ", True, False),
            (f" {codigo_grupo} ", False, True),
        ])

    # P[5]: Carrera, Modalidad
    es_regular = proyecto_examen.modalidad == 'Regular'
    es_encuentro = proyecto_examen.modalidad == 'Por encuentro'
    if len(doc.paragraphs) > 5:
        _reemplazar_runs_parrafo(doc.paragraphs[5], [
            ("Carrera: ", True, False),
            (f" {carrera_txt} ", False, True),
            ("\t  ", False, False),
            ("Modalidad: ", True, False),
            ("Regular ", False, False),
            (_marca(es_regular), es_regular, True),
            ("      Por encuentro: ", False, False),
            (_marca(es_encuentro), es_encuentro, True),
        ])

    # P[6]: Horas
    if len(doc.paragraphs) > 6:
        _reemplazar_runs_parrafo(doc.paragraphs[6], [
            ("No. Total de hrs: ", True, False),
            (f"  {total_horas}  ", False, True),
            ("\t", False, False),
            ("Hras presenciales: ", True, False),
            (f"  {horas_presenciales}  ", False, True),
            ("   ", False, False),
            ("Hrs de trab. Indep: ", True, False),
            (f"  {horas_independientes}  ", False, True),
        ])

    # P[7]: Facilitador y Tipo de examen (línea 1)
    tipo = proyecto_examen.tipo_examen
    if len(doc.paragraphs) > 7:
        _reemplazar_runs_parrafo(doc.paragraphs[7], [
            ("Facilitador: ", True, False),
            (f" {facilitador} ", False, True),
            ("\t", False, False),
            ("Tipo de examen: ", True, False),
            ("De corte evaluativo ", False, False),
            (_marca(tipo == 'De corte evaluativo'), tipo == 'De corte evaluativo', True),
            ("     Reprogramación ", False, False),
            (_marca(tipo == 'Reprogramación'), tipo == 'Reprogramación', True),
        ])

    # P[8]: Tipo de examen (línea 2)
    if len(doc.paragraphs) > 8:
        _reemplazar_runs_parrafo(doc.paragraphs[8], [
            ("Especial ", False, False),
            (_marca(tipo == 'Especial'), tipo == 'Especial', True),
            ("     Suficiencia: ", False, False),
            (_marca(tipo == 'Suficiencia'), tipo == 'Suficiencia', True),
            (f"     ({proyecto_examen.periodo_corte} — Encuentro {proyecto_examen.encuentro})", True, False),
        ])

    # Eliminar tablas sobrantes vacías de la plantilla original (Table[1]+)
    while len(doc.tables) > 1:
        extra_tbl = doc.tables[-1]._tbl
        extra_tbl.getparent().remove(extra_tbl)

    # Poblar Table[0] conservando su encabezado oficial y repitiéndolo automáticamente en cada página
    table = doc.tables[0]
    _habilitar_repeticion_encabezado(table.rows[0])
    for col_idx, cell in enumerate(table.rows[0].cells):
        _set_cell_width_dxa(cell, COL_WIDTHS_DXA[col_idx])
        _set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        _set_cell_shading(cell, "E8EEF5")

    # Eliminar filas placeholder (1, 2, 3)
    while len(table.rows) > 1:
        tr = table.rows[-1]._tr
        table._tbl.remove(tr)

    items = proyecto_examen.items_json or []
    for idx, item in enumerate(items, start=1):
        row = table.add_row()
        num = str(item.get("numero") or idx).strip()
        objetivo = str(item.get("objetivo") or "").strip()
        ejercicios = str(item.get("ejercicios") or "").strip()
        respuestas = str(item.get("posibles_respuestas") or "").strip()
        puntaje = item.get("puntaje", 0)
        detalle_puntaje = str(item.get("detalle_puntaje") or "").strip()
        if detalle_puntaje and str(puntaje) not in detalle_puntaje:
            texto_puntaje = f"{detalle_puntaje}\n({puntaje} pts)"
        elif detalle_puntaje:
            texto_puntaje = detalle_puntaje
        else:
            texto_puntaje = f"{puntaje} pts"

        # Prefijar con el número romano si aún no empieza por él
        prefijo = f"{num}. "
        txt_obj = objetivo if objetivo.startswith(prefijo) or objetivo.startswith(f"{num})") else f"{prefijo}{objetivo}"
        txt_ejer = ejercicios if ejercicios.startswith(prefijo) or ejercicios.startswith(f"{num})") else f"{prefijo}{ejercicios}"
        txt_resp = respuestas if respuestas.startswith(prefijo) or respuestas.startswith(f"{num})") else f"{prefijo}{respuestas}"

        valores = [
            (txt_obj, False, WD_ALIGN_PARAGRAPH.LEFT),
            (txt_ejer, False, WD_ALIGN_PARAGRAPH.LEFT),
            (txt_resp, False, WD_ALIGN_PARAGRAPH.LEFT),
            (texto_puntaje, True, WD_ALIGN_PARAGRAPH.CENTER),
        ]
        for col_idx, (val, is_bold_first, align) in enumerate(valores):
            cell = row.cells[col_idx]
            _set_cell_width_dxa(cell, COL_WIDTHS_DXA[col_idx])
            _set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            _escribir_texto_celda(cell, val, bold_primera_linea=is_bold_first, align=align, font_size=9.5)

    # Fila final de TOTAL
    total_row = table.add_row()
    merged = total_row.cells[0].merge(total_row.cells[2])
    _set_cell_width_dxa(merged, sum(COL_WIDTHS_DXA[:3]))
    _set_cell_margins(merged, top=80, bottom=80, left=100, right=100)
    _set_cell_shading(merged, "F1F5F9")
    _escribir_texto_celda(
        merged,
        f"TOTAL PUNTAJE — {proyecto_examen.periodo_corte.upper()}",
        bold_primera_linea=True,
        align=WD_ALIGN_PARAGRAPH.RIGHT,
        font_size=10,
    )

    total_cell = total_row.cells[3]
    _set_cell_width_dxa(total_cell, COL_WIDTHS_DXA[3])
    _set_cell_margins(total_cell, top=80, bottom=80, left=80, right=80)
    _set_cell_shading(total_cell, "F1F5F9")
    _escribir_texto_celda(
        total_cell,
        f"{proyecto_examen.puntaje_total} pts",
        bold_primera_linea=True,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        font_size=10,
    )

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output
