from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from openpyxl import load_workbook
from docx import Document
from .models import Silabo

@login_required
def generar_excel(request):
    print("Me estoy ejecutando")
    if request.method == 'POST':
        # Obtén el código de sílabo del formulario
        codigo_silabo = request.POST.get('codigoSilabo')

        if codigo_silabo:
            # Si se proporcionó un código de sílabo, realiza la búsqueda
            silabos = Silabo.objects.filter(codigo=codigo_silabo, maestro=request.user)

            if silabos.exists():
                # Si se encontraron sílabos, continúa con la lógica para generar el archivo Excel
                # ...

                # Ruta a la plantilla de Excel en tu proyecto
                template_path = 'excel_templates/plantilla.xlsx'

                # Carga la plantilla de Excel
                wb = load_workbook(template_path)

                # Selecciona una hoja de cálculo (worksheet) si es necesario
                ws = wb.active  # O selecciona una hoja específica

                # Inserta los datos en las celdas correspondientes
                row_num = 11  # Fila en la que se insertarán los datos

                for silabo in silabos:
                    ws.cell(row=5, column=2, value=silabo.maestro.username)
                    ws.cell(row=6, column=2, value=silabo.asignatura.asignatura.nombre)
                    ws.cell(row=7, column=2, value=silabo.asignacion_plan.plan_de_estudio.carrera.nombre)
                    ws.cell(row=5, column=4, value=silabo.asignacion_plan.plan_de_estudio.codigo)
                    ws.cell(row=6, column=4, value=silabo.asignacion_plan.plan_de_estudio.año)
                    ws.cell(row=7, column=4, value=silabo.asignacion_plan.plan_de_estudio.trimestre)
                    ws.cell(row=5, column=6, value=silabo.fecha.year)  # Extraemos el año de la fecha del 
                    ws.cell(row=6, column=6, value=silabo.asignacion_plan.plan_de_estudio.hp + silabo.asignacion_plan.plan_de_estudio.hti)  # Extraemos el mes de la fecha del
                    ws.cell(row=7, column=6, value=silabo.asignacion_plan.plan_de_estudio.pr.nombre if silabo.asignacion_plan.plan_de_estudio.pr else "N/A")
                    ws.cell(row=5, column=8, value=silabo.asignacion_plan.plan_de_estudio.pc.nombre if silabo.asignacion_plan.plan_de_estudio.pc else "N/A")
                    ws.cell(row=6, column=8, value=silabo.asignacion_plan.plan_de_estudio.cr.nombre if silabo.asignacion_plan.plan_de_estudio.cr else "N/A")
                    ws.cell(row=row_num, column=1, value=silabo.encuentros)
                    ws.cell(row=row_num, column=2, value=silabo.fecha)
                    ws.cell(row=row_num, column=3, value=silabo.objetivo_conceptual)
                    ws.cell(row=row_num, column=4, value=silabo.objetivo_procedimental)
                    ws.cell(row=row_num, column=5, value=silabo.objetivo_actitudinal)
                    ws.cell(row=row_num, column=6, value=silabo.momento_didactico_primer)
                    ws.cell(row=row_num, column=7, value=silabo.momento_didactico_segundo)
                    ws.cell(row=row_num, column=8, value=silabo.momento_didactico_tercer)
                    ws.cell(row=row_num, column=9, value=silabo.unidad)
                    ws.cell(row=row_num, column=10, value=silabo.contenido_tematico)
                    ws.cell(row=row_num, column=11, value=silabo.forma_organizativa)
                    ws.cell(row=row_num, column=12, value=silabo.tiempo)
                    ws.cell(row=row_num, column=13, value=silabo.tecnicas_aprendizaje)
                    ws.cell(row=row_num, column=14, value=silabo.descripcion_estrategia)
                    ws.cell(row=row_num, column=15, value=silabo.eje_transversal)
                    ws.cell(row=row_num, column=16, value=silabo.hp)

                    # Verificar si el sílabo tiene una guía asociada
                    if hasattr(silabo, 'guia') and silabo.guia is not None:
                        try:
                            ws.cell(row=row_num+16, column=1, value=silabo.guia.numero_guia)
                            ws.cell(row=row_num+16, column=2, value=silabo.guia.fecha)
                            ws.cell(row=row_num+16, column=3, value=silabo.guia.unidad)
                            #ws.cell(row=row_num+16, column=4, value=silabo.guia.nombre_de_la_unidad)
                            ws.cell(row=row_num+16, column=5, value=silabo.guia.objetivo_procedimental)
                            ws.cell(row=row_num+16, column=6, value=silabo.guia.objetivo_conceptual)
                            ws.cell(row=row_num+16, column=7, value=silabo.guia.objetivo_actitudinal)
                            ws.cell(row=row_num+16, column=8, value=silabo.guia.contenido_tematico)
                            ws.cell(row=row_num+16, column=9, value=silabo.guia.actividades)
                            ws.cell(row=row_num+16, column=10, value=silabo.guia.instrumento_cuaderno)
                            ws.cell(row=row_num+16, column=11, value=silabo.guia.instrumento_organizador)
                            ws.cell(row=row_num+16, column=12, value=silabo.guia.instrumento_diario)
                            ws.cell(row=row_num+16, column=13, value=silabo.guia.instrumento_prueba)
                            ws.cell(row=row_num+16, column=14, value=silabo.guia.criterios_evaluacion)
                            ws.cell(row=row_num+16, column=15, value=silabo.guia.tiempo_minutos)
                            ws.cell(row=row_num+16, column=16, value=silabo.guia.recursos)
                            ws.cell(row=row_num+16, column=17, value=silabo.guia.puntaje)
                            ws.cell(row=row_num+16, column=18, value=silabo.guia.evaluacion_sumativa)
                            ws.cell(row=row_num+16, column=19, value=silabo.guia.fecha_entrega)

                        except Exception as e:
                            # Si hay un error al acceder a los datos de la guía, simplemente continuamos
                            print(f"Error al procesar la guía del sílabo {silabo.id}: {str(e)}")

                    # Agrega los datos para otros campos aquí
                    row_num += 1  # Avanza a la siguiente fila

                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/ms-excel')
                response['Content-Disposition'] = 'attachment; filename=archivo_generado.xlsx'
                wb.save(response)

                return response

    # Si no se proporcionó un código de sílabo o no se encontraron sílabos, redirige a la página principal
    from django.shortcuts import redirect
    return redirect('plan_de_estudio')


@login_required
def generar_excel_original(request):
    print("Me estoy ejecutando")
    if request.method == 'POST':
        # Obtén el código de sílabo del formulario
        codigo_silabo = request.POST.get('codigoSilabo')

        if codigo_silabo:
            # Si se proporcionó un código de sílabo, realiza la búsqueda
            silabos = Silabo.objects.filter(codigo=codigo_silabo, maestro=request.user)

            if silabos.exists():
                # Si se encontraron sílabos, continúa con la lógica para generar el archivo Excel
                # ...

                # Ruta a la plantilla de Excel en tu proyecto
                template_path = 'excel_templates/plantilla_original.xlsx'

                # Carga la plantilla de Excel
                wb = load_workbook(template_path)

                # Selecciona una hoja de cálculo (worksheet) si es necesario
                ws = wb.active  # O selecciona una hoja específica

                # Inserta los datos en las celdas correspondientes
                row_num = 0  # Fila en la que se insertarán los datos

                for silabo in silabos:

                    ws.cell(row=7, column=3, value=silabo.maestro.username)
                    ws.cell(row=5, column=9, value=silabo.asignatura.asignatura.nombre)
                    ws.cell(row=5, column=4, value=silabo.carrera.nombre)
                    ws.cell(row=5, column=13, value=silabo.asignacion_plan.plan_de_estudio.trimestre)
                    ws.cell(row=7, column=10,
                            value=silabo.asignacion_plan.plan_de_estudio.pr.nombre if silabo.asignacion_plan.plan_de_estudio.pr else "N/A")
                    ws.cell(row=7, column=12,
                            value=silabo.asignacion_plan.plan_de_estudio.pc.nombre if silabo.asignacion_plan.plan_de_estudio.pc else "N/A")
                    ws.cell(row=7, column=13,
                            value=silabo.asignacion_plan.plan_de_estudio.cr.nombre if silabo.asignacion_plan.plan_de_estudio.cr else "N/A")

                    ws.cell(row=12+row_num, column=3, value=silabo.unidad)
                    ws.cell(row=13+ row_num, column=3, value=silabo.unidad)
                    ws.cell(row=18+row_num, column=3, value=silabo.unidad)

                    ws.cell(row=11+row_num, column=4, value=silabo.detalle_unidad)
                    ws.cell(row=13+row_num, column=4, value=silabo.detalle_unidad)
                    ws.cell(row=18+row_num, column=4, value=silabo.detalle_unidad)

                    ws.cell(row=11+row_num, column=6, value=silabo.objetivo_conceptual)
                    ws.cell(row=13+row_num, column=6, value=silabo.objetivo_procedimental)
                    ws.cell(row=18+row_num, column=6, value=silabo.objetivo_actitudinal)
                    ws.cell(row=11+row_num, column=7, value=silabo.contenido_tematico)

                    ws.cell(row=12+row_num, column=9, value=silabo.momento_didactico_primer)
                    ws.cell(row=14+row_num, column=9, value=silabo.momento_didactico_segundo)
                    ws.cell(row=19+row_num, column=9, value=silabo.momento_didactico_tercer)

                    ws.cell(row=12+row_num, column=10, value=silabo.tiempo)


                    #Estudio independiente
                    ws.cell(row=23 + row_num, column=3, value=silabo.unidad)
                    ws.cell(row=23 + row_num, column=6, value=silabo.guia.contenido_tematico)
                    ws.cell(row=23 + row_num, column=8, value=silabo.guia.criterios_evaluacion)
                    ws.cell(row=23 + row_num, column=10, value=silabo.guia.tiempo_minutos)
                    ws.cell(row=23 + row_num, column=11, value=silabo.guia.recursos)
                    ws.cell(row=23 + row_num, column=12, value=silabo.guia.puntaje)
                    ws.cell(row=23 + row_num, column=13, value=silabo.guia.evaluacion_sumativa)
                    ws.cell(row=23 + row_num, column=14, value=silabo.guia.objetivo_conceptual)
                    ws.cell(row=23 + row_num, column=15, value=silabo.guia.objetivo_procedimental)
                    ws.cell(row=23 + row_num, column=16, value=silabo.guia.objetivo_actitudinal)
                    ws.cell(row=23 + row_num, column=17, value=silabo.guia.instrumento_cuaderno)
                    ws.cell(row=23 + row_num, column=18, value=silabo.guia.instrumento_organizador)
                    ws.cell(row=23 + row_num, column=19, value=silabo.guia.instrumento_diario)
                    ws.cell(row=23 + row_num, column=20, value=silabo.guia.instrumento_prueba)
                    ws.cell(row=23 + row_num, column=21, value=silabo.guia.fecha_entrega)

                    # Agrega los datos para otros campos aquí
                    row_num += 23  # Avanza a la siguiente fila

                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/ms-excel')
                response['Content-Disposition'] = 'attachment; filename=archivo_generado.xlsx'
                wb.save(response)

                return response

    # Si no se proporcionó un código de sílabo o no se encontraron sílabos, redirige a la página principal
    from django.shortcuts import redirect
    return redirect('plan_de_estudio')


@login_required
def generar_docx(request):
    if request.method == 'POST':
        codigo_silabo = request.POST.get('codigoSilabo', '')
        if not codigo_silabo:
            return JsonResponse({'error': 'El código de sílabo no se proporcionó.'}, status=400)

        usuario = request.user
        silabos = Silabo.objects.filter(codigo=codigo_silabo, maestro=usuario)

        if not silabos.exists():
            return JsonResponse({'error': 'No se encontraron sílabos para este usuario con el código especificado.'},
                                status=404)

        try:
            # Crear un documento Word
            document = Document()

            # Título principal del documento
            document.add_heading('Sílabo Generado', level=0)

            for silabo in silabos:
                # Encabezado para cada sílabo
                document.add_heading(f'Sílabo: {silabo.codigo}', level=1)

                # Información general
                document.add_paragraph().add_run('Información General').bold = True
                
                # Crear una tabla para la información general
                table = document.add_table(rows=7, cols=2)
                table.style = 'Table Grid'
                
                # Añadir datos a la tabla
                cells = table.rows[0].cells
                cells[0].text = 'Maestro'
                cells[1].text = silabo.maestro.username
                
                cells = table.rows[1].cells
                cells[0].text = 'Asignatura'
                cells[1].text = silabo.asignatura.asignatura.nombre
                
                cells = table.rows[2].cells
                cells[0].text = 'Carrera'
                cells[1].text = silabo.asignacion_plan.plan_de_estudio.carrera.nombre
                
                cells = table.rows[3].cells
                cells[0].text = 'Código Plan'
                cells[1].text = silabo.asignacion_plan.plan_de_estudio.codigo
                
                cells = table.rows[4].cells
                cells[0].text = 'Año'
                cells[1].text = str(silabo.asignacion_plan.plan_de_estudio.año)
                
                cells = table.rows[5].cells
                cells[0].text = 'Trimestre'
                cells[1].text = silabo.asignacion_plan.plan_de_estudio.trimestre
                
                cells = table.rows[6].cells
                cells[0].text = 'Horas Totales'
                cells[1].text = str(silabo.asignacion_plan.plan_de_estudio.hp + silabo.asignacion_plan.plan_de_estudio.hti)
                
                document.add_paragraph()  # Espacio

                # Detalles del sílabo
                document.add_heading('Detalles del Sílabo', level=2)
                
                # Crear una tabla para los detalles
                table = document.add_table(rows=12, cols=2)
                table.style = 'Table Grid'
                
                cells = table.rows[0].cells
                cells[0].text = 'Encuentros'
                cells[1].text = str(silabo.encuentros)
                
                cells = table.rows[1].cells
                cells[0].text = 'Fecha'
                cells[1].text = str(silabo.fecha)
                
                cells = table.rows[2].cells
                cells[0].text = 'Unidad'
                cells[1].text = silabo.unidad
                
                cells = table.rows[3].cells
                cells[0].text = 'Objetivo Conceptual'
                cells[1].text = silabo.objetivo_conceptual
                
                cells = table.rows[4].cells
                cells[0].text = 'Objetivo Procedimental'
                cells[1].text = silabo.objetivo_procedimental
                
                cells = table.rows[5].cells
                cells[0].text = 'Objetivo Actitudinal'
                cells[1].text = silabo.objetivo_actitudinal
                
                cells = table.rows[6].cells
                cells[0].text = 'Primer Momento Didáctico'
                cells[1].text = silabo.momento_didactico_primer
                
                cells = table.rows[7].cells
                cells[0].text = 'Segundo Momento Didáctico'
                cells[1].text = silabo.momento_didactico_segundo
                
                cells = table.rows[8].cells
                cells[0].text = 'Tercer Momento Didáctico'
                cells[1].text = silabo.momento_didactico_tercer
                
                cells = table.rows[9].cells
                cells[0].text = 'Contenido Temático'
                cells[1].text = silabo.contenido_tematico
                
                cells = table.rows[10].cells
                cells[0].text = 'Forma Organizativa'
                cells[1].text = silabo.forma_organizativa
                
                cells = table.rows[11].cells
                cells[0].text = 'Tiempo'
                cells[1].text = str(silabo.tiempo)
                
                document.add_paragraph()  # Espacio
                
                # Información adicional
                document.add_heading('Información Adicional', level=2)
                
                # Crear una tabla para la información adicional
                table = document.add_table(rows=4, cols=2)
                table.style = 'Table Grid'
                
                cells = table.rows[0].cells
                cells[0].text = 'Técnicas de Aprendizaje'
                cells[1].text = silabo.tecnicas_aprendizaje
                
                cells = table.rows[1].cells
                cells[0].text = 'Descripción Estrategia'
                cells[1].text = silabo.descripcion_estrategia
                
                cells = table.rows[2].cells
                cells[0].text = 'Eje Transversal'
                cells[1].text = silabo.eje_transversal
                
                cells = table.rows[3].cells
                cells[0].text = 'Horas Prácticas'
                cells[1].text = str(silabo.hp)
                
                # Verificar si el sílabo tiene una guía asociada
                if hasattr(silabo, 'guia') and silabo.guia is not None:
                    try:
                        document.add_page_break()
                        document.add_heading(f'Guía de Estudio Independiente: {silabo.codigo}', level=1)
                        
                        # Información general de la guía
                        document.add_heading('Información General de la Guía', level=2)
                        
                        # Crear una tabla para la información general de la guía
                        table = document.add_table(rows=4, cols=2)
                        table.style = 'Table Grid'
                        
                        cells = table.rows[0].cells
                        cells[0].text = 'Número de Guía'
                        cells[1].text = str(silabo.guia.numero_guia)
                        
                        cells = table.rows[1].cells
                        cells[0].text = 'Fecha'
                        cells[1].text = str(silabo.guia.fecha)
                        
                        cells = table.rows[2].cells
                        cells[0].text = 'Unidad'
                        cells[1].text = silabo.guia.unidad
                        
                        cells = table.rows[3].cells
                        cells[0].text = 'Contenido Temático'
                        cells[1].text = silabo.guia.contenido_tematico
                        
                        document.add_paragraph()  # Espacio
                        
                        # Objetivos de la guía
                        document.add_heading('Objetivos de la Guía', level=2)
                        
                        # Crear una tabla para los objetivos
                        table = document.add_table(rows=3, cols=2)
                        table.style = 'Table Grid'
                        
                        cells = table.rows[0].cells
                        cells[0].text = 'Objetivo Conceptual'
                        cells[1].text = silabo.guia.objetivo_conceptual
                        
                        cells = table.rows[1].cells
                        cells[0].text = 'Objetivo Procedimental'
                        cells[1].text = silabo.guia.objetivo_procedimental
                        
                        cells = table.rows[2].cells
                        cells[0].text = 'Objetivo Actitudinal'
                        cells[1].text = silabo.guia.objetivo_actitudinal
                        
                        document.add_paragraph()  # Espacio
                        
                        # Actividades y recursos
                        document.add_heading('Actividades y Recursos', level=2)
                        
                        # Crear una tabla para actividades y recursos
                        table = document.add_table(rows=3, cols=2)
                        table.style = 'Table Grid'
                        
                        cells = table.rows[0].cells
                        cells[0].text = 'Actividades'
                        cells[1].text = silabo.guia.actividades
                        
                        cells = table.rows[1].cells
                        cells[0].text = 'Recursos'
                        cells[1].text = silabo.guia.recursos
                        
                        cells = table.rows[2].cells
                        cells[0].text = 'Tiempo (minutos)'
                        cells[1].text = str(silabo.guia.tiempo_minutos)
                        
                        document.add_paragraph()  # Espacio
                        
                        # Evaluación
                        document.add_heading('Evaluación', level=2)
                        
                        # Crear una tabla para la evaluación
                        table = document.add_table(rows=7, cols=2)
                        table.style = 'Table Grid'
                        
                        cells = table.rows[0].cells
                        cells[0].text = 'Instrumento Cuaderno'
                        cells[1].text = silabo.guia.instrumento_cuaderno
                        
                        cells = table.rows[1].cells
                        cells[0].text = 'Instrumento Organizador'
                        cells[1].text = silabo.guia.instrumento_organizador
                        
                        cells = table.rows[2].cells
                        cells[0].text = 'Instrumento Diario'
                        cells[1].text = silabo.guia.instrumento_diario
                        
                        cells = table.rows[3].cells
                        cells[0].text = 'Instrumento Prueba'
                        cells[1].text = silabo.guia.instrumento_prueba
                        
                        cells = table.rows[4].cells
                        cells[0].text = 'Criterios de Evaluación'
                        cells[1].text = silabo.guia.criterios_evaluacion
                        
                        cells = table.rows[5].cells
                        cells[0].text = 'Puntaje'
                        cells[1].text = str(silabo.guia.puntaje)
                        
                        cells = table.rows[6].cells
                        cells[0].text = 'Evaluación Sumativa'
                        cells[1].text = silabo.guia.evaluacion_sumativa
                        
                        document.add_paragraph()  # Espacio
                        
                        # Fecha de entrega
                        document.add_heading('Fecha de Entrega', level=2)
                        document.add_paragraph(str(silabo.guia.fecha_entrega))
                        
                    except Exception as e:
                        # Si hay un error al acceder a los datos de la guía, agregar un mensaje de error
                        document.add_paragraph(f"Error al procesar la guía del sílabo {silabo.id}: {str(e)}")

                # Separador para cada sílabo
                document.add_page_break()

            # Preparar el archivo para descargar
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = 'attachment; filename="silabo_y_guia_generado.docx"'
            document.save(response)

            return response

        except Exception as e:
            return JsonResponse({'error': f"Ocurrió un error al generar el documento Word: {e}"}, status=500)

    from django.shortcuts import redirect
    return redirect('plan_de_estudio')
