"""
Generador de documento Word (.docx) para el Proyecto de Examen UML.
Siempre crea una copia en memoria de la plantilla oficial `docx_templates/plantilla_proyecto_examen.docx`,
preservando el logotipo institucional, márgenes horizontales, tipografía y bloque de firmas.
"""

import io
from pathlib import Path
import re
import zipfile

from django.conf import settings
from django.core.files.storage import default_storage
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

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


# ==============================================================================
# Generador de Examen Listo para Aplicar a Estudiantes (.docx)
# Formato vertical Carta, con logo UML, datos del estudiante en blanco (nombre y fecha),
# nombre del docente, asignatura, corte de evaluación, puntaje y SOLO los ejercicios
# (excluyendo objetivos y posibles respuestas).
# ==============================================================================

COLOR_NAVY = RGBColor(0x0F, 0x29, 0x4A)
COLOR_ACCENT = RGBColor(0x1E, 0x3A, 0x8A)
COLOR_TEXT = RGBColor(0x1E, 0x29, 0x3B)
COLOR_MUTED = RGBColor(0x47, 0x55, 0x69)

_RE_LINEA_NUMERADA = re.compile(r'^(\d+\s*[\.\)\-])\s*(.+)$')
_RE_LINEA_OPCION = re.compile(r'^([A-Ea-e]\s*[\.\)]|\(\s*[VvFf]?\s*\)|\[\s*\])\s+(.+)$')
_RE_LINEA_INSTRUCCION = re.compile(r'^(Instrucciones?|Indicaciones?)\s*:\s*(.*)$', re.IGNORECASE)


def _cargar_logo_uml_bytes():
    """
    Devuelve un BytesIO con el escudo oficial de la Universidad Martín Lutero (UML).
    Prioridad:
    1) docx_templates/logo_uml.png en storage (MinIO)
    2) docx_templates/logo_uml.png en el repositorio local
    3) Extracción directa de word/media/image1.png desde plantilla_proyecto_examen.docx
    """
    storage_path = 'docx_templates/logo_uml.png'
    if default_storage.exists(storage_path):
        try:
            with default_storage.open(storage_path, 'rb') as f:
                data = f.read()
                if data:
                    return io.BytesIO(data)
        except Exception:
            pass

    local_logo = Path(settings.BASE_DIR) / 'docx_templates' / 'logo_uml.png'
    if local_logo.exists():
        return io.BytesIO(local_logo.read_bytes())

    local_tpl = Path(settings.BASE_DIR) / 'docx_templates' / 'plantilla_proyecto_examen.docx'
    if local_tpl.exists():
        try:
            with zipfile.ZipFile(local_tpl, 'r') as zf:
                for member in zf.namelist():
                    if member.startswith('word/media/') and member.lower().endswith(('.png', '.jpg', '.jpeg')):
                        return io.BytesIO(zf.read(member))
        except Exception:
            pass
    return None


def _set_table_borders(table, color='CBD5E1', sz='4', val='single', inside_h=True, inside_v=True):
    tblPr = table._tbl.tblPr
    for child in list(tblPr):
        if child.tag == qn('w:tblBorders'):
            tblPr.remove(child)
    tblBorders = OxmlElement('w:tblBorders')
    sides = ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')
    for side in sides:
        el = OxmlElement(f'w:{side}')
        if (side == 'insideH' and not inside_h) or (side == 'insideV' and not inside_v):
            el.set(qn('w:val'), 'none')
        else:
            el.set(qn('w:val'), val)
            el.set(qn('w:sz'), str(sz))
            el.set(qn('w:space'), '0')
            el.set(qn('w:color'), color)
        tblBorders.append(el)
    tblPr.append(tblBorders)


def _set_table_no_borders(table):
    tblPr = table._tbl.tblPr
    for child in list(tblPr):
        if child.tag == qn('w:tblBorders'):
            tblPr.remove(child)
    tblBorders = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'none')
        tblBorders.append(el)
    tblPr.append(tblBorders)


def _set_cell_borders(cell, **borders):
    """
    Configura bordes individuales de celda.
    Cada argumento opcional (top, bottom, left, right) recibe dict: {'val': 'single', 'sz': '12', 'color': '1E3A8A'}.
    """
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn('w:tcBorders'):
            tcPr.remove(child)
    tcBorders = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        spec = borders.get(side)
        if spec is None:
            continue
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), spec.get('val', 'single'))
        if spec.get('val', 'single') != 'none':
            el.set(qn('w:sz'), str(spec.get('sz', '4')))
            el.set(qn('w:space'), '0')
            el.set(qn('w:color'), spec.get('color', 'CBD5E1'))
        tcBorders.append(el)
    tcPr.append(tcBorders)


def _set_table_fixed_layout(table, col_widths_dxa):
    tblPr = table._tbl.tblPr
    for child in list(tblPr):
        if child.tag in (qn('w:tblW'), qn('w:tblLayout')):
            tblPr.remove(child)
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), str(sum(col_widths_dxa)))
    tblW.set(qn('w:type'), 'dxa')
    tblPr.append(tblW)

    tblLayout = OxmlElement('w:tblLayout')
    tblLayout.set(qn('w:type'), 'fixed')
    tblPr.append(tblLayout)

    tblGrid = table._tbl.tblGrid
    if tblGrid is not None:
        table._tbl.remove(tblGrid)
    new_grid = OxmlElement('w:tblGrid')
    for w in col_widths_dxa:
        gridCol = OxmlElement('w:gridCol')
        gridCol.set(qn('w:w'), str(w))
        new_grid.append(gridCol)
    tblPr.addnext(new_grid)


def _agregar_campo_xml(paragraph, field_name, font_name='Arial', font_size=8.5, color=COLOR_MUTED):
    """Inserta un campo dinámico de Word (como PAGE o NUMPAGES) en un párrafo."""
    run = paragraph.add_run()
    run.font.name = font_name
    run.font.size = Pt(font_size)
    if color:
        run.font.color.rgb = color

    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = f' {field_name} '
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')

    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)


def _separar_encabezado_ejercicio(numero, ejercicios_texto):
    """
    Extrae un título de apartado limpio si la primera línea del bloque de ejercicios
    funciona como encabezado del apartado, evitando duplicar el numeral romano (ej. 'I. I. ...').
    Devuelve (titulo_apartado, lineas_cuerpo).
    """
    raw_lines = str(ejercicios_texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # Eliminar líneas en blanco iniciales y finales
    while raw_lines and not raw_lines[0].strip():
        raw_lines.pop(0)
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()

    if not raw_lines:
        return f"APARTADO {numero}", []

    primera = raw_lines[0].strip()
    num_esc = re.escape(str(numero).strip())
    match_num = re.match(rf'^{num_esc}\s*[\.\)\-:]\s*(.+)$', primera, flags=re.IGNORECASE)
    if match_num:
        titulo_limpio = match_num.group(1).strip()
        # Si la primera línea es un encabezado razonable y hay cuerpo debajo
        if len(titulo_limpio) <= 150 and len(raw_lines) > 1:
            return f"{numero}. {titulo_limpio}", raw_lines[1:]
        return f"{numero}. {titulo_limpio}", raw_lines[1:]

    # Si no empieza por número de pregunta ni por 'Instrucciones:' y es una línea corta de título
    if (
        len(raw_lines) > 1
        and len(primera) <= 120
        and not _RE_LINEA_NUMERADA.match(primera)
        and not _RE_LINEA_INSTRUCCION.match(primera)
        and not _RE_LINEA_OPCION.match(primera)
    ):
        return f"{numero}. {primera}", raw_lines[1:]

    return f"APARTADO {numero}", raw_lines


def _agregar_parrafo_borde_inferior(doc, color='1E3A8A', sz='12', space_before=2, space_after=8):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), str(sz))
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), color)
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def _escribir_campo_ficha(cell, etiqueta, valor, bold_valor=False, underline_valor=False, font_size=10):
    cell.text = ""
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.15

    r_lbl = p.add_run(etiqueta)
    r_lbl.bold = True
    r_lbl.font.name = 'Arial'
    r_lbl.font.size = Pt(font_size)
    r_lbl.font.color.rgb = COLOR_NAVY

    r_val = p.add_run(valor)
    r_val.bold = bold_valor
    r_val.underline = underline_valor
    r_val.font.name = 'Arial'
    r_val.font.size = Pt(font_size)
    r_val.font.color.rgb = COLOR_TEXT


def generar_documento_examen_estudiante(proyecto_examen):
    """
    Genera el documento Word (.docx) del examen listo para imprimir y aplicar a los estudiantes.
    Incluye:
    - Escudo oficial de la Universidad Martín Lutero (UML)
    - Nombre del corte de evaluación al que pertenece el examen
    - Campo en blanco para el nombre completo del estudiante
    - Campo de fecha en blanco para que lo llene el estudiante
    - Nombre del docente, asignatura, carrera, trimestre/año lectivo y puntaje total
    - Únicamente los apartados de ejercicios y su puntaje (NUNCA incluye objetivos ni posibles respuestas).
    """
    doc = Document()

    # Configuración de página Carta vertical (8.5 x 11 in), ancho útil = 7.20 in = 10368 dxa
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.55)
    section.bottom_margin = Inches(0.60)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    section.footer_distance = Inches(0.30)

    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Arial'
    style_normal.font.size = Pt(10.5)
    style_normal.font.color.rgb = COLOR_TEXT

    asignacion = proyecto_examen.asignacion_plan
    plan = asignacion.plan_de_estudio
    usuario = asignacion.usuario

    docente_nombre = (usuario.get_full_name() or usuario.username or "").strip()
    asignatura_nombre = plan.asignatura.nombre
    codigo_asignatura = (plan.codigo or "").strip()
    carrera_txt = (proyecto_examen.carrera_texto or "").strip() or plan.carrera.nombre
    municipio = (proyecto_examen.municipio or "Municipio Jalapa").strip()
    corte_nombre = proyecto_examen.periodo_corte
    codigo_grupo = (proyecto_examen.codigo_grupo or "").strip()
    puntaje_total = proyecto_examen.puntaje_total

    # Pie de página con asignatura, corte y numeración "Página X de Y"
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fp.paragraph_format.space_before = Pt(4)
    pPr = fp._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    top_bdr = OxmlElement('w:top')
    top_bdr.set(qn('w:val'), 'single')
    top_bdr.set(qn('w:sz'), '4')
    top_bdr.set(qn('w:space'), '4')
    top_bdr.set(qn('w:color'), 'CBD5E1')
    pBdr.append(top_bdr)
    pPr.append(pBdr)

    r_foot_info = fp.add_run(f"UML · {asignatura_nombre} — {corte_nombre}    |    Página ")
    r_foot_info.font.name = 'Arial'
    r_foot_info.font.size = Pt(8.5)
    r_foot_info.font.color.rgb = COLOR_MUTED
    _agregar_campo_xml(fp, 'PAGE')
    r_foot_de = fp.add_run(" de ")
    r_foot_de.font.name = 'Arial'
    r_foot_de.font.size = Pt(8.5)
    r_foot_de.font.color.rgb = COLOR_MUTED
    _agregar_campo_xml(fp, 'NUMPAGES')

    # 1. ENCABEZADO INSTITUCIONAL (Logo UML + Títulos + Caja de Puntaje/Nota)
    header_widths = (1650, 6868, 1850)  # Suma = 10368 dxa
    hdr_table = doc.add_table(rows=1, cols=3)
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_no_borders(hdr_table)
    _set_table_fixed_layout(hdr_table, header_widths)

    # Columna 0: Logo UML
    cell_logo = hdr_table.rows[0].cells[0]
    _set_cell_width_dxa(cell_logo, header_widths[0])
    _set_cell_margins(cell_logo, top=40, bottom=40, left=20, right=60)
    cell_logo.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p_logo = cell_logo.paragraphs[0]
    p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(0)
    logo_stream = _cargar_logo_uml_bytes()
    if logo_stream is not None:
        p_logo.add_run().add_picture(logo_stream, width=Inches(0.95))
    else:
        r_fallback = p_logo.add_run("UML")
        r_fallback.bold = True
        r_fallback.font.size = Pt(18)
        r_fallback.font.color.rgb = COLOR_NAVY

    # Columna 1: Título institucional y Corte de Evaluación
    cell_title = hdr_table.rows[0].cells[1]
    _set_cell_width_dxa(cell_title, header_widths[1])
    _set_cell_margins(cell_title, top=30, bottom=30, left=60, right=60)
    cell_title.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    p_univ = cell_title.paragraphs[0]
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.paragraph_format.space_before = Pt(0)
    p_univ.paragraph_format.space_after = Pt(1)
    r_univ = p_univ.add_run("UNIVERSIDAD MARTÍN LUTERO")
    r_univ.bold = True
    r_univ.font.name = 'Cambria'
    r_univ.font.size = Pt(14.5)
    r_univ.font.color.rgb = COLOR_NAVY

    p_mun = cell_title.add_paragraph()
    p_mun.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_mun.paragraph_format.space_before = Pt(0)
    p_mun.paragraph_format.space_after = Pt(3)
    r_mun = p_mun.add_run(municipio)
    r_mun.font.name = 'Arial'
    r_mun.font.size = Pt(9.5)
    r_mun.font.color.rgb = COLOR_MUTED

    p_corte = cell_title.add_paragraph()
    p_corte.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_corte.paragraph_format.space_before = Pt(2)
    p_corte.paragraph_format.space_after = Pt(1)
    r_corte = p_corte.add_run(f"EXAMEN — {corte_nombre.upper()}")
    r_corte.bold = True
    r_corte.font.name = 'Arial'
    r_corte.font.size = Pt(12)
    r_corte.font.color.rgb = COLOR_ACCENT

    p_sub = cell_title.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(0)
    r_sub = p_sub.add_run(f"Evaluación #{proyecto_examen.numero_evaluacion} · {proyecto_examen.tipo_examen}")
    r_sub.font.name = 'Arial'
    r_sub.font.size = Pt(9)
    r_sub.font.color.rgb = COLOR_MUTED

    # Columna 2: Recuadro de Puntaje Total y Nota
    cell_score = hdr_table.rows[0].cells[2]
    _set_cell_width_dxa(cell_score, header_widths[2])
    _set_cell_margins(cell_score, top=60, bottom=60, left=60, right=60)
    _set_cell_shading(cell_score, "F8FAFC")
    _set_cell_borders(
        cell_score,
        top={'val': 'single', 'sz': '8', 'color': '1E3A8A'},
        bottom={'val': 'single', 'sz': '8', 'color': '1E3A8A'},
        left={'val': 'single', 'sz': '8', 'color': '1E3A8A'},
        right={'val': 'single', 'sz': '8', 'color': '1E3A8A'},
    )
    cell_score.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    p_val_lbl = cell_score.paragraphs[0]
    p_val_lbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_val_lbl.paragraph_format.space_before = Pt(0)
    p_val_lbl.paragraph_format.space_after = Pt(1)
    r_vl = p_val_lbl.add_run("VALOR TOTAL")
    r_vl.bold = True
    r_vl.font.name = 'Arial'
    r_vl.font.size = Pt(8)
    r_vl.font.color.rgb = COLOR_MUTED

    p_val_num = cell_score.add_paragraph()
    p_val_num.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_val_num.paragraph_format.space_before = Pt(0)
    p_val_num.paragraph_format.space_after = Pt(4)
    r_vn = p_val_num.add_run(f"{puntaje_total} pts")
    r_vn.bold = True
    r_vn.font.name = 'Arial'
    r_vn.font.size = Pt(12.5)
    r_vn.font.color.rgb = COLOR_ACCENT

    p_nota = cell_score.add_paragraph()
    p_nota.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_nota.paragraph_format.space_before = Pt(0)
    p_nota.paragraph_format.space_after = Pt(0)
    r_nota = p_nota.add_run("Nota: ________")
    r_nota.bold = True
    r_nota.font.name = 'Arial'
    r_nota.font.size = Pt(9.5)
    r_nota.font.color.rgb = COLOR_TEXT

    _agregar_parrafo_borde_inferior(doc, color='1E3A8A', sz='12', space_before=2, space_after=6)

    # 2. FICHA DE DATOS GENERALES DEL ESTUDIANTE Y LA ASIGNATURA
    info_widths = (5668, 4700)  # Suma = 10368 dxa
    info_table = doc.add_table(rows=4, cols=2)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_borders(info_table, color='CBD5E1', sz='4', val='single', inside_h=True, inside_v=True)
    _set_table_fixed_layout(info_table, info_widths)

    # Fila 0: Nombre completo del estudiante (en blanco para llenar a mano en la misma línea)
    cell_est = info_table.rows[0].cells[0].merge(info_table.rows[0].cells[1])
    _set_cell_width_dxa(cell_est, sum(info_widths))
    _set_cell_margins(cell_est, top=90, bottom=90, left=110, right=110)
    _set_cell_shading(cell_est, "FFFFFF")
    _escribir_campo_ficha(
        cell_est,
        "Nombre completo del estudiante: ",
        "_____________________________________________",
        bold_valor=False,
        font_size=10,
    )

    # Fila 1: Asignatura | Fecha (en blanco para que la llene el estudiante)
    asig_display = f"{asignatura_nombre} ({codigo_asignatura})" if codigo_asignatura else asignatura_nombre
    c10, c11 = info_table.rows[1].cells[0], info_table.rows[1].cells[1]
    _set_cell_width_dxa(c10, info_widths[0])
    _set_cell_width_dxa(c11, info_widths[1])
    _set_cell_margins(c10, top=70, bottom=70, left=110, right=100)
    _set_cell_margins(c11, top=70, bottom=70, left=110, right=100)
    _set_cell_shading(c10, "F8FAFC")
    _set_cell_shading(c11, "FFFFFF")
    _escribir_campo_ficha(c10, "Asignatura: ", asig_display, bold_valor=True, font_size=9.5)
    _escribir_campo_ficha(c11, "Fecha: ", "_____ / _____ / ________", bold_valor=False, font_size=9.5)

    # Fila 2: Docente | Carrera
    c20, c21 = info_table.rows[2].cells[0], info_table.rows[2].cells[1]
    _set_cell_width_dxa(c20, info_widths[0])
    _set_cell_width_dxa(c21, info_widths[1])
    _set_cell_margins(c20, top=70, bottom=70, left=110, right=100)
    _set_cell_margins(c21, top=70, bottom=70, left=110, right=100)
    _set_cell_shading(c20, "F8FAFC")
    _set_cell_shading(c21, "F8FAFC")
    _escribir_campo_ficha(c20, "Docente: ", docente_nombre, bold_valor=False, font_size=9.5)
    _escribir_campo_ficha(c21, "Carrera: ", carrera_txt, bold_valor=False, font_size=9.5)

    # Fila 3: Corte de evaluación | Trimestre / Año lectivo (y Grupo si existe)
    periodo_extra = f"Trim. {proyecto_examen.trimestre} — {proyecto_examen.anio_lectivo}"
    if codigo_grupo:
        periodo_extra += f" · Grupo: {codigo_grupo}"
    c30, c31 = info_table.rows[3].cells[0], info_table.rows[3].cells[1]
    _set_cell_width_dxa(c30, info_widths[0])
    _set_cell_width_dxa(c31, info_widths[1])
    _set_cell_margins(c30, top=70, bottom=70, left=110, right=100)
    _set_cell_margins(c31, top=70, bottom=70, left=110, right=100)
    _set_cell_shading(c30, "F8FAFC")
    _set_cell_shading(c31, "F8FAFC")
    _escribir_campo_ficha(
        c30,
        "Corte de evaluación: ",
        f"{corte_nombre} (Evaluación #{proyecto_examen.numero_evaluacion})",
        bold_valor=True,
        font_size=9.5,
    )
    _escribir_campo_ficha(c31, "Período: ", periodo_extra, bold_valor=False, font_size=9.5)

    # 3. INDICACIONES GENERALES
    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(0)
    p_sp.paragraph_format.space_after = Pt(4)

    ind_table = doc.add_table(rows=1, cols=1)
    ind_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _set_table_no_borders(ind_table)
    _set_table_fixed_layout(ind_table, (10368,))
    ind_cell = ind_table.rows[0].cells[0]
    _set_cell_width_dxa(ind_cell, 10368)
    _set_cell_margins(ind_cell, top=75, bottom=75, left=130, right=110)
    _set_cell_shading(ind_cell, "F1F5F9")
    _set_cell_borders(
        ind_cell,
        top={'val': 'single', 'sz': '4', 'color': 'E2E8F0'},
        bottom={'val': 'single', 'sz': '4', 'color': 'E2E8F0'},
        right={'val': 'single', 'sz': '4', 'color': 'E2E8F0'},
        left={'val': 'single', 'sz': '18', 'color': '1E3A8A'},
    )
    p_ind = ind_cell.paragraphs[0]
    p_ind.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_ind.paragraph_format.space_before = Pt(0)
    p_ind.paragraph_format.space_after = Pt(0)
    p_ind.paragraph_format.line_spacing = 1.15
    r_ind_lbl = p_ind.add_run("Indicaciones generales: ")
    r_ind_lbl.bold = True
    r_ind_lbl.font.name = 'Arial'
    r_ind_lbl.font.size = Pt(9.5)
    r_ind_lbl.font.color.rgb = COLOR_NAVY
    r_ind_txt = p_ind.add_run(
        "Lea detenidamente cada apartado antes de responder. Escriba con letra clara y ordenada "
        "utilizando lapicero azul o negro. Trabaje de manera individual cuidando su ortografía y "
        f"presentación. Valor total del examen: {puntaje_total} puntos."
    )
    r_ind_txt.italic = True
    r_ind_txt.font.name = 'Arial'
    r_ind_txt.font.size = Pt(9.5)
    r_ind_txt.font.color.rgb = COLOR_TEXT

    # 4. APARTADOS DEL EXAMEN (SOLO EJERCICIOS Y PUNTAJE — SIN OBJETIVOS NI RESPUESTAS)
    items = proyecto_examen.items_json or []
    sec_widths = (8168, 2200)  # Suma = 10368 dxa

    for idx, item in enumerate(items, start=1):
        num = str(item.get("numero") or idx).strip()
        ejercicios = str(item.get("ejercicios") or "").strip()
        puntaje = item.get("puntaje", 0)
        detalle_puntaje = str(item.get("detalle_puntaje") or "").strip()

        titulo_sec, lineas_cuerpo = _separar_encabezado_ejercicio(num, ejercicios)

        # Espacio antes del apartado
        p_gap = doc.add_paragraph()
        p_gap.paragraph_format.space_before = Pt(0)
        p_gap.paragraph_format.space_after = Pt(6)

        # Barra de encabezado del apartado
        sec_table = doc.add_table(rows=1, cols=2)
        sec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        _set_table_no_borders(sec_table)
        _set_table_fixed_layout(sec_table, sec_widths)

        sc_left, sc_right = sec_table.rows[0].cells[0], sec_table.rows[0].cells[1]
        _set_cell_width_dxa(sc_left, sec_widths[0])
        _set_cell_width_dxa(sc_right, sec_widths[1])
        _set_cell_margins(sc_left, top=65, bottom=65, left=120, right=80)
        _set_cell_margins(sc_right, top=65, bottom=65, left=80, right=110)
        _set_cell_shading(sc_left, "E8EEF5")
        _set_cell_shading(sc_right, "E8EEF5")
        _set_cell_borders(
            sc_left,
            left={'val': 'single', 'sz': '18', 'color': '1E3A8A'},
            bottom={'val': 'single', 'sz': '6', 'color': 'CBD5E1'},
            top={'val': 'single', 'sz': '4', 'color': 'CBD5E1'},
        )
        _set_cell_borders(
            sc_right,
            right={'val': 'single', 'sz': '4', 'color': 'CBD5E1'},
            bottom={'val': 'single', 'sz': '6', 'color': 'CBD5E1'},
            top={'val': 'single', 'sz': '4', 'color': 'CBD5E1'},
        )
        sc_left.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        sc_right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        p_sec_t = sc_left.paragraphs[0]
        p_sec_t.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_sec_t.paragraph_format.space_before = Pt(0)
        p_sec_t.paragraph_format.space_after = Pt(0)
        p_sec_t.paragraph_format.keep_with_next = True
        r_st = p_sec_t.add_run(titulo_sec)
        r_st.bold = True
        r_st.font.name = 'Arial'
        r_st.font.size = Pt(10.5)
        r_st.font.color.rgb = COLOR_NAVY

        p_sec_p = sc_right.paragraphs[0]
        p_sec_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_sec_p.paragraph_format.space_before = Pt(0)
        p_sec_p.paragraph_format.space_after = Pt(0)
        p_sec_p.paragraph_format.keep_with_next = True
        r_sp = p_sec_p.add_run(f"Valor: {puntaje} pts")
        r_sp.bold = True
        r_sp.font.name = 'Arial'
        r_sp.font.size = Pt(10)
        r_sp.font.color.rgb = COLOR_ACCENT

        # Si hay detalle de puntaje más descriptivo que solo "X pts", mostrarlo sutilmente debajo del valor
        if detalle_puntaje and detalle_puntaje.lower().strip() not in (f"{puntaje} pts", f"{puntaje} puntos", str(puntaje)):
            p_sec_det = sc_right.add_paragraph()
            p_sec_det.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p_sec_det.paragraph_format.space_before = Pt(1)
            p_sec_det.paragraph_format.space_after = Pt(0)
            p_sec_det.paragraph_format.keep_with_next = True
            r_sd = p_sec_det.add_run(detalle_puntaje)
            r_sd.italic = True
            r_sd.font.name = 'Arial'
            r_sd.font.size = Pt(8)
            r_sd.font.color.rgb = COLOR_MUTED

        # Cuerpo de los ejercicios del apartado
        linea_vacia_previa = False
        for linea_raw in lineas_cuerpo:
            linea = linea_raw.strip()
            if not linea:
                if not linea_vacia_previa:
                    p_blank = doc.add_paragraph()
                    p_blank.paragraph_format.space_before = Pt(0)
                    p_blank.paragraph_format.space_after = Pt(3)
                    linea_vacia_previa = True
                continue
            linea_vacia_previa = False

            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15

            m_inst = _RE_LINEA_INSTRUCCION.match(linea)
            m_num = _RE_LINEA_NUMERADA.match(linea)
            m_opc = _RE_LINEA_OPCION.match(linea)

            if m_inst:
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)
                r1 = p.add_run(f"{m_inst.group(1)}: ")
                r1.bold = True
                r1.font.name = 'Arial'
                r1.font.size = Pt(10)
                r1.font.color.rgb = COLOR_NAVY
                r2 = p.add_run(m_inst.group(2))
                r2.italic = True
                r2.font.name = 'Arial'
                r2.font.size = Pt(10)
                r2.font.color.rgb = COLOR_TEXT
            elif m_num:
                p.paragraph_format.left_indent = Inches(0.15)
                p.paragraph_format.space_before = Pt(5)
                p.paragraph_format.space_after = Pt(3)
                r1 = p.add_run(f"{m_num.group(1)} ")
                r1.bold = True
                r1.font.name = 'Arial'
                r1.font.size = Pt(10.5)
                r1.font.color.rgb = COLOR_NAVY
                r2 = p.add_run(m_num.group(2))
                r2.font.name = 'Arial'
                r2.font.size = Pt(10.5)
                r2.font.color.rgb = COLOR_TEXT
            elif m_opc:
                p.paragraph_format.left_indent = Inches(0.38)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(2)
                r1 = p.add_run(f"{m_opc.group(1)} ")
                r1.bold = True
                r1.font.name = 'Arial'
                r1.font.size = Pt(10)
                r1.font.color.rgb = COLOR_TEXT
                r2 = p.add_run(m_opc.group(2))
                r2.font.name = 'Arial'
                r2.font.size = Pt(10)
                r2.font.color.rgb = COLOR_TEXT
            else:
                p.paragraph_format.left_indent = Inches(0.08)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(3)
                r = p.add_run(linea)
                r.font.name = 'Arial'
                r.font.size = Pt(10.5)
                r.font.color.rgb = COLOR_TEXT

    # 5. CIERRE DEL EXAMEN
    _agregar_parrafo_borde_inferior(doc, color='CBD5E1', sz='6', space_before=12, space_after=6)
    p_fin = doc.add_paragraph()
    p_fin.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fin.paragraph_format.space_before = Pt(2)
    p_fin.paragraph_format.space_after = Pt(0)
    r_fin = p_fin.add_run(
        f"— Fin del examen ({corte_nombre}) · Valor total: {puntaje_total} puntos —"
    )
    r_fin.italic = True
    r_fin.font.name = 'Arial'
    r_fin.font.size = Pt(9.5)
    r_fin.font.color.rgb = COLOR_MUTED

    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output
