from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from openpyxl import load_workbook
from docx import Document
from .models import Guia, Silabo

@login_required
def generar_excel(request):
    print("Me estoy ejecutando")
    if request.method == 'POST':
        # Obtén el ID del sílabo del formulario
        silabo_id = request.POST.get('codigoSilabo')
        print(f"ID de sílabo recibido: {silabo_id}")
        print(f"Usuario actual: {request.user.username}")

        if silabo_id:
            try:
                # Si se proporcionó un ID de sílabo, busca el sílabo directamente
                print(f"Buscando sílabo con ID={silabo_id} y usuario={request.user.username}")
                silabo = Silabo.objects.get(id=silabo_id, asignacion_plan__usuario=request.user)
                print(f"Sílabo encontrado: ID={silabo.id}, Código={silabo.codigo}")

                # Generamos el Excel para este sílabo
                print(f"Generando Excel para el sílabo ID={silabo.id}")

                # Ruta a la plantilla de Excel en tu proyecto
                template_path = 'excel_templates/plantilla.xlsx'

                # Carga la plantilla de Excel
                wb = load_workbook(template_path)

                # Selecciona una hoja de cálculo (worksheet) si es necesario
                ws = wb.active  # O selecciona una hoja específica

                # Inserta los datos en las celdas correspondientes
                row_num = 11  # Fila en la que se insertarán los datos

                # Datos del sílabo - Usando la función safe_write_cell
                safe_write_cell(ws, 5, 2, silabo.asignacion_plan.usuario.username)
                safe_write_cell(ws, 6, 2, silabo.asignacion_plan.plan_de_estudio.asignatura.nombre)
                safe_write_cell(ws, 7, 2, silabo.asignacion_plan.plan_de_estudio.carrera.nombre)
                safe_write_cell(ws, 5, 4, silabo.asignacion_plan.plan_de_estudio.codigo)
                safe_write_cell(ws, 6, 4, silabo.asignacion_plan.plan_de_estudio.año)
                safe_write_cell(ws, 7, 4, silabo.asignacion_plan.plan_de_estudio.trimestre)
                safe_write_cell(ws, 5, 6, silabo.fecha.year)
                safe_write_cell(ws, 6, 6, silabo.asignacion_plan.plan_de_estudio.hp + silabo.asignacion_plan.plan_de_estudio.hti)
                safe_write_cell(ws, 7, 6, silabo.asignacion_plan.plan_de_estudio.pr.nombre if silabo.asignacion_plan.plan_de_estudio.pr else "N/A")
                safe_write_cell(ws, 5, 8, silabo.asignacion_plan.plan_de_estudio.pc.nombre if silabo.asignacion_plan.plan_de_estudio.pc else "N/A")
                safe_write_cell(ws, 6, 8, silabo.asignacion_plan.plan_de_estudio.cr.nombre if silabo.asignacion_plan.plan_de_estudio.cr else "N/A")
                safe_write_cell(ws, row_num, 1, silabo.encuentros)
                safe_write_cell(ws, row_num, 2, silabo.fecha)
                safe_write_cell(ws, row_num, 3, silabo.objetivo_conceptual)
                safe_write_cell(ws, row_num, 4, silabo.objetivo_procedimental)
                safe_write_cell(ws, row_num, 5, silabo.objetivo_actitudinal)
                safe_write_cell(ws, row_num, 6, silabo.detalle_primer_momento)
                safe_write_cell(ws, row_num, 7, silabo.clase_teorica)
                safe_write_cell(ws, row_num, 8, silabo.detalle_tercer_momento)
                safe_write_cell(ws, row_num, 9, silabo.unidad)
                safe_write_cell(ws, row_num, 10, silabo.contenido_tematico)
                safe_write_cell(ws, row_num, 11, silabo.tipo_primer_momento)
                safe_write_cell(ws, row_num, 12, silabo.tiempo_primer_momento)
                safe_write_cell(ws, row_num, 13, silabo.tecnica_evaluacion)
                safe_write_cell(ws, row_num, 14, silabo.instrumento_evaluacion)
                safe_write_cell(ws, row_num, 15, silabo.eje_transversal)
                safe_write_cell(ws, row_num, 16, silabo.tiempo_primer_momento)

                # Verificar si el sílabo tiene una guía asociada
                if hasattr(silabo, 'guia') and silabo.guia is not None:
                    try:
                        safe_write_cell(ws, row_num+16, 1, silabo.guia.numero_guia if hasattr(silabo.guia, 'numero_guia') else silabo.encuentros)
                        safe_write_cell(ws, row_num+16, 2, silabo.guia.fecha if hasattr(silabo.guia, 'fecha') else silabo.fecha)
                        safe_write_cell(ws, row_num+16, 3, silabo.guia.unidad if hasattr(silabo.guia, 'unidad') else silabo.unidad)
                        safe_write_cell(ws, row_num+16, 5, silabo.guia.objetivo_procedimental)
                        safe_write_cell(ws, row_num+16, 6, silabo.guia.objetivo_conceptual)
                        safe_write_cell(ws, row_num+16, 7, silabo.guia.objetivo_actitudinal)
                        safe_write_cell(ws, row_num+16, 8, silabo.guia.contenido_tematico)
                        safe_write_cell(ws, row_num+16, 9, silabo.guia.actividades if hasattr(silabo.guia, 'actividades') else "")
                        safe_write_cell(ws, row_num+16, 10, silabo.guia.instrumento_cuaderno if hasattr(silabo.guia, 'instrumento_cuaderno') else "")
                        safe_write_cell(ws, row_num+16, 11, silabo.guia.instrumento_organizador if hasattr(silabo.guia, 'instrumento_organizador') else "")
                        safe_write_cell(ws, row_num+16, 12, silabo.guia.instrumento_diario if hasattr(silabo.guia, 'instrumento_diario') else "")
                        safe_write_cell(ws, row_num+16, 13, silabo.guia.instrumento_prueba if hasattr(silabo.guia, 'instrumento_prueba') else "")
                        safe_write_cell(ws, row_num+16, 14, silabo.guia.criterios_evaluacion)
                        safe_write_cell(ws, row_num+16, 15, silabo.guia.tiempo_minutos)
                        safe_write_cell(ws, row_num+16, 16, silabo.guia.recursos_primer_momento if hasattr(silabo.guia, 'recursos_primer_momento') else "")
                        safe_write_cell(ws, row_num+16, 17, silabo.guia.puntaje)
                        safe_write_cell(ws, row_num+16, 18, silabo.guia.evaluacion_sumativa if hasattr(silabo.guia, 'evaluacion_sumativa') else "")
                        safe_write_cell(ws, row_num+16, 19, silabo.guia.fecha_entrega if hasattr(silabo.guia, 'fecha_entrega') else "")

                    except Exception as e:
                        # Si hay un error al acceder a los datos de la guía, simplemente continuamos
                        print(f"Error al procesar la guía del sílabo {silabo.id}: {str(e)}")

                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/ms-excel')
                response['Content-Disposition'] = f'attachment; filename=silabo_{silabo.codigo}.xlsx'
                wb.save(response)

                return response

            except Silabo.DoesNotExist:
                print(f"Error: No se encontró el sílabo con ID {silabo_id}")
            except Exception as e:
                print(f"Error al generar el Excel: {str(e)}")

    # Si no se proporcionó un ID de sílabo o no se encontró, redirige a la página principal
    from django.shortcuts import redirect
    return redirect('plan_de_estudio')


# Helper function to safely write to cells, avoiding merged cell errors
def safe_write_cell(ws, row, col, value):
    """
    Safely writes a value to a cell, checking if it's a merged cell first.
    If it's a merged cell, writes to the master cell of the merge range.

    Args:
        ws: Worksheet object
        row: Row number (1-based)
        col: Column number (1-based)
        value: Value to write
    """
    # Get the cell
    cell = ws.cell(row=row, column=col)

    # Try to set the value directly
    try:
        cell.value = value
    except AttributeError:
        # If this fails, the cell might be part of a merged range
        print(f"Cell at row={row}, col={col} appears to be a merged cell. Trying to find the master cell.")

        # Find all merged ranges
        for merged_range in ws.merged_cells.ranges:
            # Check if the cell is in this range
            if cell.coordinate in merged_range:
                # Get the top-left cell (master cell) of the merged range
                master_cell = ws.cell(row=merged_range.min_row, column=merged_range.min_col)
                print(f"Writing to master cell at {master_cell.coordinate} instead")
                master_cell.value = value
                return

        # If we get here, the cell is not in any merged range, something else is wrong
        print(f"Failed to write to cell at row={row}, col={col}. Cell is not in any merged range.")

@login_required
def generar_excel_original(request):
    """
    Función para generar un archivo Excel basado en los datos de un sílabo.
    """
    if request.method == 'POST':
        # Obtén el ID del sílabo del formulario
        silabo_id = request.POST.get('codigoSilabo')
        print(f"ID de sílabo recibido: {silabo_id}")
        print(f"Usuario actual: {request.user.username}")

        if not silabo_id:
            return JsonResponse({'error': 'El ID de sílabo no se proporcionó.'}, status=400)

        try:
            # Si se proporcionó un ID de sílabo, busca el sílabo directamente
            print(f"Buscando sílabo con ID={silabo_id} y usuario={request.user.username}")
            silabo = Silabo.objects.get(id=silabo_id, asignacion_plan__usuario=request.user)
            print(f"Sílabo encontrado: ID={silabo.id}, Código={silabo.codigo}")

            # Generamos el Excel para este sílabo
            print(f"Generando Excel para el sílabo ID={silabo.id}")

            # Ruta a la plantilla de Excel en tu proyecto
            template_path = 'excel_templates/plantilla_original.xlsx'

            # Carga la plantilla de Excel
            wb = load_workbook(template_path)

            # Selecciona una hoja de cálculo (worksheet) si es necesario
            ws = wb.active  # O selecciona una hoja específica

            # Datos generales del sílabo que solo se escriben una vez
            safe_write_cell(ws, 7, 4, silabo.asignacion_plan.usuario.first_name + " " + silabo.asignacion_plan.usuario.last_name)
            safe_write_cell(ws, 5, 10, silabo.asignacion_plan.plan_de_estudio.codigo)
            safe_write_cell(ws, 5, 11, silabo.asignacion_plan.plan_de_estudio.año)
            safe_write_cell(ws, 5, 12, silabo.asignacion_plan.plan_de_estudio.trimestre)
            safe_write_cell(ws, 5, 9, silabo.asignacion_plan.plan_de_estudio.asignatura.nombre)
            safe_write_cell(ws, 5, 6, silabo.asignacion_plan.plan_de_estudio.carrera.nombre)
            safe_write_cell(ws, 5, 3, silabo.asignacion_plan.plan_de_estudio.carrera.codigo)


            safe_write_cell(ws, 7, 10, silabo.asignacion_plan.plan_de_estudio.pr.nombre if silabo.asignacion_plan.plan_de_estudio.pr else "N/A")
            safe_write_cell(ws, 7, 11, silabo.asignacion_plan.plan_de_estudio.pc.nombre if silabo.asignacion_plan.plan_de_estudio.pc else "N/A")
            safe_write_cell(ws, 7, 12, silabo.asignacion_plan.plan_de_estudio.cr.nombre if silabo.asignacion_plan.plan_de_estudio.cr else "N/A")

            # Buscar todos los sílabos relacionados con la misma asignación de plan de estudio, ordenados por número de encuentro
            try:
                silabos_relacionados = Silabo.objects.filter(
                    asignacion_plan=silabo.asignacion_plan
                ).order_by('encuentros')

                print(f"Se encontraron {silabos_relacionados.count()} sílabos relacionados")

                # Definir la distancia en filas entre cada bloque de datos
                rows_per_block = 46
                rows_per_block_guia = 46

                # Iterar sobre cada sílabo y escribir sus datos con el offset apropiado
                for i, silabo_actual in enumerate(silabos_relacionados):
                    if i >= 11:  # Limitar a 11 sílabos máximo como solicitado
                        break

                    print(f"Procesando sílabo {i+1}: Encuentro {silabo_actual.encuentros}")

                    # Calcular el offset de filas para este sílabo
                    row_num = i * rows_per_block

                    # Escribir datos específicos del sílabo con el offset correspondiente
                    safe_write_cell(ws, 11+row_num, 3, silabo_actual.unidad+" " + silabo_actual.nombre_de_la_unidad)

                    safe_write_cell(ws, 12+row_num, 6, silabo_actual.objetivo_conceptual)
                    safe_write_cell(ws, 13+row_num, 6, silabo_actual.objetivo_procedimental)
                    safe_write_cell(ws, 18+row_num, 6, silabo_actual.objetivo_actitudinal)
                    safe_write_cell(ws, 11+row_num, 7, silabo_actual.contenido_tematico)

                    safe_write_cell(ws, 12+row_num, 8, silabo_actual.tipo_primer_momento)
                    safe_write_cell(ws, 12+row_num, 9, silabo_actual.detalle_primer_momento)
                    safe_write_cell(ws, 12+row_num, 10, silabo_actual.tiempo_primer_momento)
                    safe_write_cell(ws, 12+row_num, 11, silabo_actual.recursos_primer_momento)

                    safe_write_cell(ws, 15+row_num, 8, silabo_actual.tipo_segundo_momento_claseteoria)
                    safe_write_cell(ws, 14+row_num, 9, silabo_actual.clase_teorica)
                    safe_write_cell(ws, 17+row_num, 8, silabo_actual.tipo_segundo_momento_practica)
                    safe_write_cell(ws, 16+row_num, 9, silabo_actual.clase_practica)
                    safe_write_cell(ws, 14+row_num, 10, silabo_actual.tiempo_segundo_momento_teorica)
                    safe_write_cell(ws, 15+row_num, 10, silabo_actual.tiempo_segundo_momento_practica)
                    safe_write_cell(ws, 14+row_num, 11, silabo_actual.recursos_segundo_momento)

                    safe_write_cell(ws, 19+row_num, 8, silabo_actual.tipo_tercer_momento[0] +", "+ silabo_actual.tipo_tercer_momento[1])
                    safe_write_cell(ws, 19+row_num, 9, silabo_actual.detalle_tercer_momento)
                    safe_write_cell(ws, 19+row_num, 10, silabo_actual.tiempo_tercer_momento)
                    safe_write_cell(ws, 19+row_num, 11, silabo_actual.recursos_tercer_momento)

                    safe_write_cell(ws, 11+row_num, 12, silabo_actual.eje_transversal[0] +", "+ silabo_actual.eje_transversal[1])
                    safe_write_cell(ws, 12+row_num, 12, silabo_actual.detalle_eje_transversal)

                    #evaluacion dinamica
                    safe_write_cell(ws, 12+row_num, 14, silabo_actual.actividad_aprendizaje)
                    safe_write_cell(ws, 13+row_num, 14, silabo_actual.tecnica_evaluacion[0] + ", " + silabo_actual.tecnica_evaluacion[1])
                    safe_write_cell(ws, 14+row_num, 14, silabo_actual.tipo_evaluacion[0] + ", " + silabo_actual.tipo_evaluacion[1])
                    safe_write_cell(ws, 15+row_num, 14, silabo_actual.periodo_tiempo_programado)
                    safe_write_cell(ws, 16+row_num, 14, silabo_actual.tiempo_minutos)
                    safe_write_cell(ws, 17+row_num, 14, silabo_actual.agente_evaluador[0] + ", " + silabo_actual.agente_evaluador[1])
                    safe_write_cell(ws, 18+row_num, 14, silabo_actual.instrumento_evaluacion)
                    safe_write_cell(ws, 19+row_num, 14, silabo_actual.criterios_evaluacion)
                    safe_write_cell(ws, 20+row_num, 14, silabo_actual.puntaje)

                    # Datos de la guía de estudio independiente (si existe)
                    if hasattr(silabo_actual, 'guia') and silabo_actual.guia is not None:
                        guia = silabo_actual.guia  # Accedemos a la instancia de guía
                        try:
                            if i == 1:
                                row_num_guia = 0

                            row_num_guia = i * rows_per_block_guia

                            safe_write_cell(ws, 23+row_num_guia, 2, guia.fecha if hasattr(guia, 'fecha') else "")
                            safe_write_cell(ws, 23+row_num_guia, 3, f"{guia.unidad} {guia.nombre_de_la_unidad}" if hasattr(guia, 'unidad') and hasattr(guia, 'nombre_de_la_unidad') else "")

                            safe_write_cell(ws, 23+row_num_guia, 4, guia.tipo_objetivo_1 if hasattr(guia, 'tipo_objetivo_1') else "")
                            safe_write_cell(ws, 24+row_num_guia, 6, guia.objetivo_aprendizaje_1 if hasattr(guia, 'objetivo_aprendizaje_1') else "")
                            safe_write_cell(ws, 24+row_num_guia, 7, guia.contenido_tematico_1 if hasattr(guia, 'contenido_tematico_1') else "")
                            safe_write_cell(ws, 23+row_num_guia, 9, guia.actividad_aprendizaje_1)
                            safe_write_cell(ws, 25+row_num_guia, 9, guia.tecnica_evaluacion_1)
                            safe_write_cell(ws, 26+row_num_guia, 9, guia.tipo_evaluacion_1)
                            safe_write_cell(ws, 27+row_num_guia, 9, guia.instrumento_evaluacion_1)
                            safe_write_cell(ws, 28+row_num_guia, 9, guia.criterios_evaluacion_1)
                            safe_write_cell(ws, 29+row_num_guia, 9, guia.agente_evaluador_1[0] +", " + guia.agente_evaluador_1[1])
                            safe_write_cell(ws, 23+row_num_guia, 10, guia.tiempo_minutos_1)
                            safe_write_cell(ws, 23+row_num_guia, 11, guia.recursos_didacticos_1)
                            safe_write_cell(ws, 23+row_num_guia, 13, guia.periodo_tiempo_programado_1)
                            safe_write_cell(ws, 24+row_num_guia, 13, guia.puntaje_1)
                            safe_write_cell(ws, 25+row_num_guia, 14, guia.fecha_entrega_1)

                            safe_write_cell(ws, 31+row_num_guia, 4, guia.tipo_objetivo_2 if hasattr(guia, 'tipo_objetivo_2') else "")
                            safe_write_cell(ws, 31+row_num_guia, 6, guia.objetivo_aprendizaje_2 if hasattr(guia, 'objetivo_aprendizaje_2') else "")
                            safe_write_cell(ws, 31+row_num_guia, 7, guia.contenido_tematico_2 if hasattr(guia, 'contenido_tematico_2') else "")
                            safe_write_cell(ws, 31+row_num_guia, 9, guia.actividad_aprendizaje_2)
                            safe_write_cell(ws, 33+row_num_guia, 9, guia.tecnica_evaluacion_2)
                            safe_write_cell(ws, 34+row_num_guia, 9, guia.tipo_evaluacion_2)
                            safe_write_cell(ws, 35+row_num_guia, 9, guia.instrumento_evaluacion_2)
                            safe_write_cell(ws, 36+row_num_guia, 9, guia.criterios_evaluacion_2)
                            safe_write_cell(ws, 37+row_num_guia, 9, guia.agente_evaluador_2[0] +", " + guia.agente_evaluador_2[1])
                            safe_write_cell(ws, 31+row_num_guia, 10, guia.tiempo_minutos_2)
                            safe_write_cell(ws, 31+row_num_guia, 11, guia.recursos_didacticos_2)
                            safe_write_cell(ws, 31+row_num_guia, 13, guia.periodo_tiempo_programado_2)
                            safe_write_cell(ws, 32+row_num_guia, 13, guia.puntaje_2)
                            safe_write_cell(ws, 33+row_num_guia, 14, guia.fecha_entrega_2)

                            safe_write_cell(ws, 39+row_num_guia, 4, guia.tipo_objetivo_3 if hasattr(guia, 'tipo_objetivo_3') else "")
                            safe_write_cell(ws, 39+row_num_guia, 6, guia.objetivo_aprendizaje_3 if hasattr(guia, 'objetivo_aprendizaje_3') else "")
                            safe_write_cell(ws, 39+row_num_guia, 7, guia.contenido_tematico_3 if hasattr(guia, 'contenido_tematico_3') else "")
                            safe_write_cell(ws, 39+row_num_guia, 9, guia.actividad_aprendizaje_3)
                            safe_write_cell(ws, 41+row_num_guia, 9, guia.tecnica_evaluacion_3)
                            safe_write_cell(ws, 42+row_num_guia, 9, guia.tipo_evaluacion_3)
                            safe_write_cell(ws, 43+row_num_guia, 9, guia.instrumento_evaluacion_3)
                            safe_write_cell(ws, 44+row_num_guia, 9, guia.criterios_evaluacion_3)
                            safe_write_cell(ws, 45+row_num_guia, 9, guia.agente_evaluador_3[0] +", " + guia.agente_evaluador_3[1])
                            safe_write_cell(ws, 39+row_num_guia, 10, guia.tiempo_minutos_3)
                            safe_write_cell(ws, 39+row_num_guia, 11, guia.recursos_didacticos_3)
                            safe_write_cell(ws, 39+row_num_guia, 13, guia.periodo_tiempo_programado_3)
                            safe_write_cell(ws, 40+row_num_guia, 13, guia.puntaje_3)
                            safe_write_cell(ws, 41+row_num_guia, 14, guia.fecha_entrega_3)

                            safe_write_cell(ws, 47+row_num_guia, 4, guia.tipo_objetivo_4 if hasattr(guia, 'tipo_objetivo_1') else "")
                            safe_write_cell(ws, 47+row_num_guia, 6, guia.objetivo_aprendizaje_4 if hasattr(guia, 'objetivo_aprendizaje_1') else "")
                            safe_write_cell(ws, 47+row_num_guia, 7, guia.contenido_tematico_4 if hasattr(guia, 'contenido_tematico_1') else "")
                            safe_write_cell(ws, 47+row_num_guia, 9, guia.actividad_aprendizaje_4)
                            safe_write_cell(ws, 49+row_num_guia, 9, guia.tecnica_evaluacion_4)
                            safe_write_cell(ws, 50+row_num_guia, 9, guia.tipo_evaluacion_4)
                            safe_write_cell(ws, 51+row_num_guia, 9, guia.instrumento_evaluacion_4)
                            safe_write_cell(ws, 52+row_num_guia, 9, guia.criterios_evaluacion_4)
                            safe_write_cell(ws, 53+row_num_guia, 9, guia.agente_evaluador_4[0] + ", "+ guia.agente_evaluador_4[1])
                            safe_write_cell(ws, 47+row_num_guia, 10, guia.tiempo_minutos_4)
                            safe_write_cell(ws, 47+row_num_guia, 11, guia.recursos_didacticos_4)
                            safe_write_cell(ws, 47+row_num_guia, 13, guia.periodo_tiempo_programado_4)
                            safe_write_cell(ws, 48+row_num_guia, 13, guia.puntaje_4)
                            safe_write_cell(ws, 49+row_num_guia, 14, guia.fecha_entrega_4)




                            # Podemos agregar más campos si es necesario
                            print(f"Guía procesada correctamente para el sílabo {silabo_actual.encuentros}")
                        except Exception as e:
                            print(f"Error al procesar la guía: {str(e)}")
                            # Continuamos con el siguiente sílabo sin interrumpir el proceso
                print("Generando respuesta con el archivo Excel...")
                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename=silabo_{silabo.codigo}.xlsx'
                wb.save(response)
                print("Archivo Excel generado correctamente")
                return response

            except Exception as e:
                print(f"Error específico durante la generación del Excel: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return JsonResponse({'error': f'Error al generar el Excel: {str(e)}'}, status=500)

        except Silabo.DoesNotExist:
            print(f"Error: No se encontró el sílabo con ID {silabo_id}")
            return JsonResponse({'error': f'No se encontró el sílabo con ID {silabo_id}'}, status=404)
        except Exception as e:
            print(f"Error general al generar el Excel: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'error': f'Error al generar el Excel: {str(e)}'}, status=500)

    # Si no se proporcionó un ID de sílabo o no se encontró, redirige a la página principal
    from django.shortcuts import redirect
    return redirect('plan_de_estudio')


@login_required
def generar_docx(request):
    if request.method == 'POST':
        silabo_id = request.POST.get('codigoSilabo', '')
        print(f"ID de sílabo recibido para Word: {silabo_id}")
        print(f"Usuario actual: {request.user.username}")

        if not silabo_id:
            return JsonResponse({'error': 'El ID de sílabo no se proporcionó.'}, status=400)

        try:
            # Si se proporcionó un ID de sílabo, busca el sílabo directamente
            print(f"Buscando sílabo con ID={silabo_id} y usuario={request.user.username}")
            silabo = Silabo.objects.get(id=silabo_id, asignacion_plan__usuario=request.user)
            print(f"Sílabo encontrado: ID={silabo.id}, Código={silabo.codigo}")

            # Generamos el Word para este sílabo
            print(f"Generando Word para el sílabo ID={silabo.id}")

            # Crear un nuevo documento de Word
            doc = Document()

            # Añadir título
            doc.add_heading(f'Sílabo de {silabo.asignacion_plan.plan_de_estudio.asignatura.nombre}', 0)

            # Información general
            doc.add_heading('Información General', level=1)
            doc.add_paragraph(f'Profesor: {silabo.asignacion_plan.usuario.username}')
            doc.add_paragraph(f'Carrera: {silabo.asignacion_plan.plan_de_estudio.carrera.nombre}')
            doc.add_paragraph(f'Año: {silabo.asignacion_plan.plan_de_estudio.año}')
            doc.add_paragraph(f'Trimestre: {silabo.asignacion_plan.plan_de_estudio.trimestre}')
            doc.add_paragraph(f'Código: {silabo.codigo}')
            doc.add_paragraph(f'Encuentro: {silabo.encuentros}')
            doc.add_paragraph(f'Fecha: {silabo.fecha}')

            # Objetivos
            doc.add_heading('Objetivos', level=1)
            doc.add_paragraph(f'Conceptual: {silabo.objetivo_conceptual}')
            doc.add_paragraph(f'Procedimental: {silabo.objetivo_procedimental}')
            doc.add_paragraph(f'Actitudinal: {silabo.objetivo_actitudinal}')

            # Contenido
            doc.add_heading('Contenido Temático', level=1)
            doc.add_paragraph(f'Unidad: {silabo.unidad}')
            doc.add_paragraph(f'Nombre de la Unidad: {silabo.nombre_de_la_unidad}')
            doc.add_paragraph(f'Contenido: {silabo.contenido_tematico}')

            # Momentos Didácticos
            doc.add_heading('Momentos Didácticos', level=1)

            table = doc.add_table(rows=12, cols=2)
            table.style = 'Table Grid'

            cells = table.rows[0].cells
            cells[0].text = 'Campo'
            cells[1].text = 'Descripción'

            cells = table.rows[1].cells
            cells[0].text = 'Primer Momento'
            cells[1].text = silabo.detalle_primer_momento

            cells = table.rows[2].cells
            cells[0].text = 'Clase Teórica'
            cells[1].text = silabo.clase_teorica

            cells = table.rows[3].cells
            cells[0].text = 'Clase Práctica'
            cells[1].text = silabo.clase_practica

            cells = table.rows[4].cells
            cells[0].text = 'Tercer Momento'
            cells[1].text = silabo.detalle_tercer_momento

            cells = table.rows[5].cells
            cells[0].text = 'Contenido Temático'
            cells[1].text = silabo.contenido_tematico

            # Agregar información de la guía si existe
            if hasattr(silabo, 'guia') and silabo.guia is not None:
                doc.add_heading('Guía de Estudio Independiente', level=1)
                doc.add_paragraph(f'Unidad: {silabo.guia.unidad}')
                doc.add_paragraph(f'Contenido Temático: {silabo.guia.contenido_tematico}')
                doc.add_paragraph(f'Objetivo Conceptual: {silabo.guia.objetivo_conceptual}')
                doc.add_paragraph(f'Objetivo Procedimental: {silabo.guia.objetivo_procedimental}')
                doc.add_paragraph(f'Objetivo Actitudinal: {silabo.guia.objetivo_actitudinal}')
                doc.add_paragraph(f'Tiempo en Minutos: {silabo.guia.tiempo_minutos}')
                doc.add_paragraph(f'Puntaje: {silabo.guia.puntaje}')
                doc.add_paragraph(f'Criterios de Evaluación: {silabo.guia.criterios_evaluacion}')

            # Guardar el documento en memoria
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename=silabo_{silabo.codigo}.docx'

            # Guardar el documento en el objeto response
            doc.save(response)

            return response

        except Silabo.DoesNotExist:
            return JsonResponse({'error': f'No se encontró el sílabo con ID {silabo_id} para este usuario.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error al generar el documento Word: {str(e)}'}, status=500)

    # Si no es una petición POST, redirige a la página principal
    from django.shortcuts import redirect
    return redirect('plan_de_estudio')
