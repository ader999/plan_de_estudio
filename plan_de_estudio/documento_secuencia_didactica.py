from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from django.http import HttpResponse
from io import BytesIO
from .models import Silabo, AsignacionPlanEstudio, Guia
from django.utils import timezone
import datetime

def _texto_campo(valor, default="—"):
    """Convierte valores simples o MultiSelectField a texto seguro para python-docx."""
    if valor is None or valor == "":
        return default
    if isinstance(valor, (list, tuple)):
        unido = ", ".join(str(v) for v in valor if v not in (None, ""))
        return unido if unido else default
    texto = str(valor)
    return texto if texto else default


def _entero_texto(valor, default="—"):
    """Formatea un valor numérico entero evitando confusiones con 0."""
    return str(valor) if valor is not None else default


def generar_documento_secuencia_didactica(silabos_agrupados, usuario, año_actual=None):
    """
    Genera un documento Word con la secuencia didáctica para todos los encuentros.
    
    Args:
        silabos_agrupados: Diccionario con silabos agrupados por código
        usuario: Nombre del usuario
        año_actual: Año actual (opcional)
        
    Returns:
        BytesIO: Buffer con el documento generado
    """
    # Crear un nuevo documento
    doc = Document()
    
    # Establecer márgenes de página
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)
    
    # Título del documento
    titulo = doc.add_heading('UNIVERSIDAD MARTÍN LUTERO', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitulo = doc.add_heading('SECUENCIA DIDÁCTICA', 1)
    subtitulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Si no se proporciona el año actual, usar el año actual
    if año_actual is None:
        año_actual = datetime.datetime.now().year
    
    # Procesar cada grupo de sílabos
    for codigo, silabos_grupo in silabos_agrupados.items():
        # Ordenar los sílabos por número de encuentro
        silabos_grupo.sort(key=lambda s: s.encuentros)
        
        # Información de la asignatura
        if silabos_grupo:
            primer_silabo = silabos_grupo[0]
            
            # Añadir sección de la asignatura
            doc.add_heading(f'Asignatura: {primer_silabo.asignacion_plan.plan_de_estudio.asignatura}', 2)
            doc.add_paragraph(f'Código: {primer_silabo.asignacion_plan.plan_de_estudio.codigo}')
            doc.add_paragraph(f'Carrera: {primer_silabo.asignacion_plan.plan_de_estudio.carrera.nombre}')
            doc.add_paragraph(f'Año académico: {primer_silabo.asignacion_plan.plan_de_estudio.año}')
            doc.add_paragraph(f'Trimestre: {primer_silabo.asignacion_plan.plan_de_estudio.trimestre}')
            doc.add_paragraph(f'Mediador: {usuario}')
            doc.add_paragraph(f'Año Lectivo: {año_actual}')
            
            # Procesar cada sílabo (encuentro) del grupo
            for silabo in silabos_grupo:
                # Añadir salto de página entre encuentros
                if silabo != silabos_grupo[0]:
                    doc.add_page_break()
                
                # Título del encuentro
                doc.add_heading(f'ENCUENTRO {silabo.encuentros}', 2).alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Datos generales
                p = doc.add_heading('DATOS GENERALES', 3)
                
                # Tabla de datos generales
                tabla_datos = doc.add_table(rows=5, cols=2)
                tabla_datos.style = 'Table Grid'
                
                # Rellenar la tabla de datos generales
                tabla_datos.cell(0, 0).text = 'N° de guía:'
                tabla_datos.cell(0, 1).text = str(silabo.encuentros)
                tabla_datos.cell(1, 0).text = 'Fecha:'
                tabla_datos.cell(1, 1).text = silabo.fecha.strftime('%d/%m/%Y')
                tabla_datos.cell(2, 0).text = 'Sede:'
                tabla_datos.cell(2, 1).text = 'Jalapa'
                tabla_datos.cell(3, 0).text = 'Unidad:'
                tabla_datos.cell(3, 1).text = f'{silabo.unidad}. {silabo.nombre_de_la_unidad}'
                tabla_datos.cell(4, 0).text = 'Trimestre:'
                tabla_datos.cell(4, 1).text = silabo.asignacion_plan.plan_de_estudio.trimestre
                
                # Centrar título de unidad
                doc.add_heading('NOMBRE DE LA UNIDAD', 3).alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Tabla de nombre de unidad
                tabla_unidad = doc.add_table(rows=1, cols=1)
                tabla_unidad.style = 'Table Grid'
                tabla_unidad.cell(0, 0).text = f'{silabo.unidad}. {silabo.nombre_de_la_unidad}'
                set_cell_text_center(tabla_unidad.cell(0, 0))
                
                # Objetivos de la unidad
                doc.add_heading('OBJETIVOS DE LA UNIDAD', 3)
                
                tabla_objetivos = doc.add_table(rows=3, cols=2)
                tabla_objetivos.style = 'Table Grid'
                tabla_objetivos.cell(0, 0).text = 'Conceptual'
                tabla_objetivos.cell(0, 1).text = silabo.objetivo_conceptual
                tabla_objetivos.cell(1, 0).text = 'Procedimental'
                tabla_objetivos.cell(1, 1).text = silabo.objetivo_procedimental
                tabla_objetivos.cell(2, 0).text = 'Actitudinal'
                tabla_objetivos.cell(2, 1).text = silabo.objetivo_actitudinal
                
                # Establecer ancho de la primera columna
                for row in tabla_objetivos.rows:
                    row.cells[0].width = Inches(1.5)
                
                # Mediación Pedagógica
                doc.add_heading('MEDIACIÓN PEDAGÓGICA', 3).alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                tabla_mediacion = doc.add_table(rows=7, cols=6)
                tabla_mediacion.style = 'Table Grid'
                
                # Cabecera
                encabezados = ['Contenido temático', 'Fases', 'Forma organizativa', 
                               'Descripción de la forma organizativa', 'Recursos didácticos', 'Tiempo']
                
                for i, encabezado in enumerate(encabezados):
                    tabla_mediacion.cell(0, i).text = encabezado
                    set_cell_bold(tabla_mediacion.cell(0, i))
                
                # Contenido de la tabla
                # Contenido temático ocupa 6 filas
                tabla_mediacion.cell(1, 0).merge(tabla_mediacion.cell(6, 0))
                tabla_mediacion.cell(1, 0).text = silabo.contenido_tematico
                
                # Primer momento
                tabla_mediacion.cell(1, 1).merge(tabla_mediacion.cell(2, 1))
                set_cell_text_with_line_break(tabla_mediacion.cell(1, 1), "Primer momento", "(Entrada)")
                set_cell_bold(tabla_mediacion.cell(1, 1))
                
                tabla_mediacion.cell(1, 2).text = _texto_campo(silabo.tipo_primer_momento)
                tabla_mediacion.cell(1, 3).text = _texto_campo(silabo.detalle_primer_momento)
                tabla_mediacion.cell(1, 4).text = _texto_campo(silabo.recursos_primer_momento)
                tabla_mediacion.cell(1, 5).text = _entero_texto(silabo.tiempo_primer_momento)
                
                # Espacio en blanco para la segunda fila del primer momento
                for i in range(2, 6):
                    tabla_mediacion.cell(2, i).text = "—"
                
                # Segundo momento
                tabla_mediacion.cell(3, 1).merge(tabla_mediacion.cell(4, 1))
                set_cell_text_with_line_break(tabla_mediacion.cell(3, 1), "Segundo momento", "(Elaboración)")
                set_cell_bold(tabla_mediacion.cell(3, 1))
                
                tabla_mediacion.cell(3, 2).text = (
                    f"Clases teóricas - {_texto_campo(silabo.tipo_segundo_momento_claseteoria)}"
                )
                tabla_mediacion.cell(3, 3).text = _texto_campo(silabo.clase_teorica)
                tabla_mediacion.cell(3, 4).merge(tabla_mediacion.cell(4, 4))
                tabla_mediacion.cell(3, 4).text = _texto_campo(silabo.recursos_segundo_momento)
                tabla_mediacion.cell(3, 5).text = _entero_texto(silabo.tiempo_segundo_momento_teorica)
                
                tabla_mediacion.cell(4, 2).text = (
                    f"Clases prácticas - {_texto_campo(silabo.tipo_segundo_momento_practica)}"
                )
                tabla_mediacion.cell(4, 3).text = _texto_campo(silabo.clase_practica)
                tabla_mediacion.cell(4, 5).text = _entero_texto(silabo.tiempo_segundo_momento_practica)
                
                # Espacio en blanco para la fila 5
                for i in range(1, 6):
                    tabla_mediacion.cell(5, i).text = "—"
                
                # Tercer momento
                tabla_mediacion.cell(6, 1).text = "Tercer momento\n(Salida)"
                set_cell_bold(tabla_mediacion.cell(6, 1))
                tabla_mediacion.cell(6, 2).text = _texto_campo(silabo.tipo_tercer_momento)
                tabla_mediacion.cell(6, 3).text = _texto_campo(silabo.detalle_tercer_momento)
                tabla_mediacion.cell(6, 4).text = _texto_campo(silabo.recursos_tercer_momento)
                tabla_mediacion.cell(6, 5).text = _entero_texto(silabo.tiempo_tercer_momento)
                
                # Ajustar anchos de columna
                set_column_width(tabla_mediacion, 0, 2.0)  # Contenido temático
                set_column_width(tabla_mediacion, 1, 1.5)  # Fases
                set_column_width(tabla_mediacion, 2, 1.5)  # Forma organizativa
                set_column_width(tabla_mediacion, 3, 3.0)  # Descripción
                set_column_width(tabla_mediacion, 4, 1.5)  # Recursos
                set_column_width(tabla_mediacion, 5, 1.0)  # Tiempo
                
                # Orientaciones de las actividades de aprendizaje
                doc.add_heading('ORIENTACIONES DE LAS ACTIVIDADES DE APRENDIZAJE', 3)
                
                tabla_actividades = doc.add_table(rows=2, cols=4)
                tabla_actividades.style = 'Table Grid'
                
                # Cabecera de tabla de actividades
                encabezados = ['Descripción de la actividad de Aprendizaje', 'Evaluación de la actividad de Aprendizaje', 
                               'Período', 'Tiempo en minutos']
                
                for i, encabezado in enumerate(encabezados):
                    tabla_actividades.cell(0, i).text = encabezado
                    set_cell_bold(tabla_actividades.cell(0, i))
                
                # Datos de la actividad
                actividad_aprendizaje = _texto_campo(silabo.actividad_aprendizaje, default="Sin datos")
                tabla_actividades.cell(1, 0).text = actividad_aprendizaje
                
                # Evaluación
                texto_evaluacion = (
                    f"Tipo de Evaluación\n{_texto_campo(silabo.tipo_evaluacion, default='Sin datos')}\n\n"
                    f"Instrumento de evaluación\n{_texto_campo(silabo.instrumento_evaluacion, default='Sin datos')}"
                )
                tabla_actividades.cell(1, 1).text = texto_evaluacion
                
                # Período
                texto_periodo = (
                    f"{_texto_campo(silabo.periodo_tiempo_programado, default='Sin datos')}\n\n"
                    f"Técnica evaluación\n{_texto_campo(silabo.tecnica_evaluacion, default='Sin datos')}"
                )
                tabla_actividades.cell(1, 2).text = texto_periodo
                
                # Tiempo
                texto_tiempo = (
                    f"{_entero_texto(silabo.tiempo_minutos, default='Sin datos')}\n\n"
                    f"Puntaje\n{_entero_texto(silabo.puntaje, default='Sin datos')}"
                )
                tabla_actividades.cell(1, 3).text = texto_tiempo
                
                # Añadir sección de Eje transversal
                doc.add_heading('EJE TRANSVERSAL', 3)
                
                tabla_eje = doc.add_table(rows=2, cols=2)
                tabla_eje.style = 'Table Grid'
                
                # Cabecera de tabla de eje transversal
                tabla_eje.cell(0, 0).text = 'Eje transversal'
                tabla_eje.cell(0, 1).text = 'Detalle eje transversal'
                set_cell_bold(tabla_eje.cell(0, 0))
                set_cell_bold(tabla_eje.cell(0, 1))
                
                # Datos del eje transversal
                tabla_eje.cell(1, 0).text = _texto_campo(getattr(silabo, 'eje_transversal', None), default="Sin datos")
                tabla_eje.cell(1, 1).text = _texto_campo(getattr(silabo, 'detalle_eje_transversal', None), default="Sin datos")
                
                # Añadir GUÍA AUTODIDÁCTICA DE APRENDIZAJE si existe una guía asociada
                try:
                    # Intentar obtener la guía asociada al sílabo
                    guias = Guia.objects.filter(silabo=silabo)
                    
                    if guias.exists():
                        guia = guias.first()
                        
                        doc.add_heading('GUÍA AUTODIDÁCTICA DE APRENDIZAJE', 3).alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        # Tabla de actividades de la guía
                        tabla_guia = doc.add_table(rows=5, cols=7)
                        tabla_guia.style = 'Table Grid'
                        
                        # Cabecera
                        encabezados_guia = ['N°', 'Nombre de la unidad', 'Objetivo de aprendizaje', 'Contenido temático', 
                                          'Actividad de aprendizaje', 'Evaluación', 'Tiempo']
                        
                        for i, encabezado in enumerate(encabezados_guia):
                            tabla_guia.cell(0, i).text = encabezado
                            set_cell_bold(tabla_guia.cell(0, i))
                        
                        # Actividades 1-4 (1 obligatoria, 2-4 opcionales) y acumulación de totales
                        tiempo_total = 0
                        puntaje_total = 0
                        unidad_guia_txt = _texto_campo(getattr(guia, 'nombre_de_la_unidad', None))

                        for idx in range(1, 5):
                            act = getattr(guia, f'actividad_aprendizaje_{idx}', None)
                            if idx == 1 or act:
                                tipo_obj = _texto_campo(getattr(guia, f'tipo_objetivo_{idx}', None), default="")
                                obj = _texto_campo(getattr(guia, f'objetivo_aprendizaje_{idx}', None), default="")
                                tabla_guia.cell(idx, 0).text = str(idx)
                                tabla_guia.cell(idx, 1).text = unidad_guia_txt
                                tabla_guia.cell(idx, 2).text = f"{tipo_obj}: {obj}".strip(": ") or "—"
                                tabla_guia.cell(idx, 3).text = _texto_campo(getattr(guia, f'contenido_tematico_{idx}', None))
                                tabla_guia.cell(idx, 4).text = _texto_campo(act)
                                eval_text = (
                                    f"Tipo: {_texto_campo(getattr(guia, f'tipo_evaluacion_{idx}', None))}\n"
                                    f"Instrumento: {_texto_campo(getattr(guia, f'instrumento_evaluacion_{idx}', None))}\n"
                                    f"Recursos: {_texto_campo(getattr(guia, f'recursos_didacticos_{idx}', None))}"
                                )
                                tabla_guia.cell(idx, 5).text = eval_text
                                tiempo_val = getattr(guia, f'tiempo_minutos_{idx}', None)
                                puntaje_val = getattr(guia, f'puntaje_{idx}', None)
                                tabla_guia.cell(idx, 6).text = (
                                    f"{_entero_texto(tiempo_val)}\nPuntaje: {_entero_texto(puntaje_val)}"
                                )
                            else:
                                for col in range(7):
                                    tabla_guia.cell(idx, col).text = "—"

                            tiempo_total += getattr(guia, f'tiempo_minutos_{idx}', None) or 0
                            puntaje_total += getattr(guia, f'puntaje_{idx}', None) or 0
                            
                        # Resumen de horas y puntajes
                        doc.add_heading('RESUMEN DE HORAS Y PUNTAJES', 3)
                        
                        # Crear contenedor con dos columnas
                        tabla_container = doc.add_table(rows=1, cols=2)
                        tabla_container.style = 'Table Grid'
                        celda_izquierda = tabla_container.cell(0, 0)
                        celda_derecha = tabla_container.cell(0, 1)
                        
                        # Tabla izquierda para las horas
                        tabla_horas = celda_izquierda.add_table(rows=3, cols=2)
                        tabla_horas.style = 'Table Grid'
                        
                        # Cabeceras de horas
                        tabla_horas.cell(0, 0).text = 'Horas presenciales:'
                        tabla_horas.cell(1, 0).text = 'Horas de estudio independiente:'
                        tabla_horas.cell(2, 0).text = 'Total de horas:'
                        set_cell_bold(tabla_horas.cell(2, 0))
                        
                        # Calcular minutos presenciales
                        minutos_presenciales = (
                            (getattr(silabo, 'tiempo_primer_momento', None) or 0)
                            + (getattr(silabo, 'tiempo_segundo_momento_teorica', None) or 0)
                            + (getattr(silabo, 'tiempo_segundo_momento_practica', None) or 0)
                            + (getattr(silabo, 'tiempo_tercer_momento', None) or 0)
                            + (getattr(silabo, 'tiempo_minutos', None) or 0)
                        )
                        
                        # Calcular horas presenciales
                        horas_presenciales = round(minutos_presenciales / 60, 2)
                        tabla_horas.cell(0, 1).text = f"{horas_presenciales}"
                        
                        # Calcular horas de estudio independiente
                        minutos_independientes = tiempo_total
                        horas_independientes = round(minutos_independientes / 60, 2)
                        tabla_horas.cell(1, 1).text = f"{horas_independientes}"
                        
                        # Total de horas
                        horas_totales = round((minutos_presenciales + minutos_independientes) / 60, 2)
                        tabla_horas.cell(2, 1).text = f"{horas_totales}"
                        
                        # Tabla derecha para los puntajes
                        tabla_puntajes = celda_derecha.add_table(rows=3, cols=2)
                        tabla_puntajes.style = 'Table Grid'
                        
                        # Cabeceras de puntajes
                        tabla_puntajes.cell(0, 0).text = 'Puntaje en actividad de aprendizaje presencial:'
                        tabla_puntajes.cell(1, 0).text = 'Puntaje en estudio independiente:'
                        tabla_puntajes.cell(2, 0).text = 'Puntaje Total:'
                        set_cell_bold(tabla_puntajes.cell(2, 0))
                        
                        # Puntaje presencial
                        puntaje_presencial_raw = getattr(silabo, 'puntaje', None)
                        puntaje_presencial = puntaje_presencial_raw or 0
                        tabla_puntajes.cell(0, 1).text = _entero_texto(puntaje_presencial_raw, default="Sin datos")
                        
                        # Puntaje de estudio independiente
                        puntaje_independiente = puntaje_total
                        tabla_puntajes.cell(1, 1).text = str(puntaje_independiente) if puntaje_independiente is not None else "Sin datos"
                        
                        # Puntaje total
                        puntaje_total_completo = puntaje_presencial + puntaje_independiente
                        tabla_puntajes.cell(2, 1).text = str(puntaje_total_completo)
                except Exception as e:
                    # Si hay un error al intentar agregar la guía, simplemente omitir esta sección
                    print(f"Error al intentar agregar la guía autodidáctica: {str(e)}")
    
    # Guardar documento en BytesIO
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    
    return output

def set_cell_bold(cell):
    """Establece el texto de una celda como negrita."""
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

def set_cell_text_center(cell):
    """Centra el texto de una celda."""
    for paragraph in cell.paragraphs:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

def set_cell_text_with_line_break(cell, text1, text2):
    """Establece el texto de una celda con salto de línea y formato."""
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    run1 = paragraph.add_run(text1)
    run1.bold = True
    
    paragraph.add_run("\n")
    paragraph.add_run(text2)

def set_column_width(table, column_index, width_inches):
    """Establece el ancho de una columna en pulgadas."""
    for cell in table.columns[column_index].cells:
        cell.width = Inches(width_inches)
