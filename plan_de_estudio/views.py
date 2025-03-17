import json
import os
import re
from dotenv import load_dotenv
import logging

from django.db.models.functions import Lower
from django.http import HttpResponse, request ,HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
import logging

#librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo, Guia, AsignacionPlanEstudio, Asignatura, Plan_de_estudio

from .forms import SilaboForm
from django.views.decorators.csrf import csrf_exempt

from openpyxl import load_workbook
from django.db.models import Count

from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
from docx import Document
from docx.shared import Pt

# Importaciones para IA
import openai  # Importar openai directamente, sin la clase OpenAI
import google.generativeai as genai
import httpx

# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_GENERATIVE_API_KEY"))

@login_required
def detalle_silabo(request):
    # Recupera todos los objetos Silabo
    silabos = Silabo.objects.all()
    return render(request, 'plan_estudio_template/detalle_silabo.html', {'silabos': silabos})



@login_required
def inicio(request):
    nombre_de_usuario = request.user.username
    # Ajusta el filtro al campo correspondiente en AsignacionPlanEstudio para el usuario
    asignaciones = AsignacionPlanEstudio.objects.filter(usuario__username=nombre_de_usuario)
    rango = range(1, 13)  # Crear el rango para pasarlo al template

    return render(request, 'inicio.html', {'asignaciones': asignaciones, 'rango': rango, 'usuario': nombre_de_usuario})



def acerca_de(request):
    nombre_de_usuario = request.user.username
    return  render(request, 'acerca_de.html',{'usuario':nombre_de_usuario})


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Inicio de sesión exitoso.')
            return redirect('inicio')  # Cambia 'profile' por la URL deseada después del inicio de sesión
        else:
            messages.error(request, 'Credenciales incorrectas. Por favor, intenta de nuevo.')
    else:  # Si la solicitud es GET, muestra el formulario
        return render(request, 'login.html')

    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')  # Cambia 'login' por la URL de tu página de inicio de sesión



@login_required
def plan_estudio(request):
    # Obtiene el usuario autenticado
    usuario_autenticado = request.user
    nombre_de_usuario = request.user.username
    # Filtra los silabos del maestro autenticado
    silabos = Silabo.objects.filter(maestro=usuario_autenticado)

    # Crear un diccionario para agrupar los silabos por código
    silabos_agrupados = {}
    for silabo in silabos:
        codigo = silabo.codigo
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []
        silabos_agrupados[codigo].append(silabo)

    context = {
        'silabos_agrupados': silabos_agrupados,
        'usuario': nombre_de_usuario
    }

    return render(request, 'plan_estudio.html', context)


@login_required
def Plan_de_clase(request):
    return render(request, 'plan_estudio_template/detalle_plandeclase.html')




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
                    ws.cell(row=6, column=2, value=silabo.maestro.username)
                    ws.cell(row=7, column=2, value=silabo.asignatura.asignatura.nombre)
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

                    ws.cell(row=row_num, column=17, value=silabo.estudio_independiente.numero)
                    ws.cell(row=row_num, column=18, value=silabo.estudio_independiente.contenido)
                    ws.cell(row=row_num, column=19, value=silabo.estudio_independiente.tecnica_evaluacion)
                    ws.cell(row=row_num, column=20, value=silabo.estudio_independiente.orientacion)
                    ws.cell(row=row_num, column=21, value=silabo.estudio_independiente.recursos_bibliograficos)
                    ws.cell(row=row_num, column=22, value=silabo.estudio_independiente.enlace)
                    ws.cell(row=row_num, column=23, value=silabo.estudio_independiente.tiempo_estudio)
                    ws.cell(row=row_num, column=24, value=silabo.estudio_independiente.fecha_entrega)


                    # Agrega los datos para otros campos aquí
                    row_num += 1  # Avanza a la siguiente fila

                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/ms-excel')
                response['Content-Disposition'] = 'attachment; filename=archivo_generado.xlsx'
                wb.save(response)

                return response

    # Si no se proporcionó un código de sílabo o no se encontraron sílabos, redirige a la página principal
    return redirect('plan_de_estudio')  # Reemplaza 'pagina_principal' con la URL de tu elección




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
                    ws.cell(row=23 + row_num, column=6, value=silabo.estudio_independiente.contenido)
                    ws.cell(row=23 + row_num, column=8, value=silabo.estudio_independiente.instrumento_evaluacion)
                    ws.cell(row=23 + row_num, column=10, value=silabo.estudio_independiente.tiempo_estudio)
                    ws.cell(row=23 + row_num, column=11, value=silabo.estudio_independiente.recursos_bibliograficos)
                    """
                    ws.cell(row=row_num, column=1, value=silabo.encuentros)
                    ws.cell(row=row_num, column=2, value=silabo.fecha)
                    
                    
                    
                    
                    ws.cell(row=row_num, column=11, value=silabo.forma_organizativa)
                    
                    ws.cell(row=row_num, column=13, value=silabo.tecnicas_aprendizaje)
                    ws.cell(row=row_num, column=14, value=silabo.descripcion_estrategia)
                    ws.cell(row=row_num, column=15, value=silabo.eje_transversal)
                    ws.cell(row=row_num, column=16, value=silabo.hp)"""
                    # Agrega los datos para otros campos aquí
                    row_num += 23  # Avanza a la siguiente fila

                # Guarda el archivo Excel en memoria
                response = HttpResponse(content_type='application/ms-excel')
                response['Content-Disposition'] = 'attachment; filename=archivo_generado.xlsx'
                wb.save(response)

                return response

    # Si no se proporcionó un código de sílabo o no se encontraron sílabos, redirige a la página principal
    return redirect('plan_de_estudio')  # Reemplaza 'pagina_principal' con la URL de tu elección




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

                # Agregar información del sílabo
                document.add_paragraph().add_run('Maestro: ').bold = True
                document.add_paragraph(silabo.maestro.username)

                document.add_paragraph().add_run('Asignatura: ').bold = True
                document.add_paragraph(silabo.asignatura.asignatura.nombre)

                document.add_paragraph().add_run('Encuentros: ').bold = True
                document.add_paragraph(str(silabo.encuentros))

                document.add_paragraph().add_run('Fecha: ').bold = True
                document.add_paragraph(str(silabo.fecha))

                document.add_paragraph().add_run('Unidad: ').bold = True
                document.add_paragraph(silabo.unidad)

                document.add_paragraph().add_run('Objetivos: ').bold = True
                document.add_paragraph(
                    f"Conceptual: {silabo.objetivo_conceptual}, "
                    f"Procedimental: {silabo.objetivo_procedimental}, "
                    f"Actitudinal: {silabo.objetivo_actitudinal}"
                )

                document.add_paragraph().add_run('Momentos Didácticos: ').bold = True
                document.add_paragraph(
                    f"Primer Momento: {silabo.momento_didactico_primer}, "
                    f"Segundo Momento: {silabo.momento_didactico_segundo}, "
                    f"Tercer Momento: {silabo.momento_didactico_tercer}"
                )

                document.add_paragraph().add_run('Contenido Temático: ').bold = True
                document.add_paragraph(silabo.contenido_tematico)

                document.add_paragraph().add_run('Forma Organizativa: ').bold = True
                document.add_paragraph(silabo.forma_organizativa)

                document.add_paragraph().add_run('Tiempo: ').bold = True
                document.add_paragraph(str(silabo.tiempo))

                document.add_paragraph().add_run('Técnicas de Aprendizaje: ').bold = True
                document.add_paragraph(silabo.tecnicas_aprendizaje)

                document.add_paragraph().add_run('Descripción Estrategia: ').bold = True
                document.add_paragraph(silabo.descripcion_estrategia)

                document.add_paragraph().add_run('Eje Transversal: ').bold = True
                document.add_paragraph(silabo.eje_transversal)

                document.add_paragraph().add_run('Horas Prácticas: ').bold = True
                document.add_paragraph(str(silabo.hp))

                # Separador para cada sílabo
                document.add_page_break()

            # Preparar el archivo para descargar
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = 'attachment; filename="silabo_generado.docx"'
            document.save(response)

            return response

        except Exception as e:
            return JsonResponse({'error': f"Ocurrió un error al generar el documento Word: {e}"}, status=500)

    return redirect('plan_de_estudio')


def obtener_estudios_independientes(asignacion_id):
        # Paso 1: Obtener la asignación del plan de estudio
        asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)

        # Paso 2: Obtener el plan de estudio relacionado con la asignación
        plan_de_estudio = asignacion.plan_de_estudio

        # Paso 3: Obtener la asignatura del plan de estudio
        asignatura_nombre = plan_de_estudio.asignatura.nombre

        # Imprime la asignatura encontrada para depuración
        print("Asignatura encontrada:", asignatura_nombre)

        # Paso 4: Filtrar las guías que estén relacionadas con sílabos de esta asignatura
        # Nota: Ajustamos el filtro según la estructura actual del modelo
        guias = Guia.objects.filter(
            silabo__asignacion_plan__plan_de_estudio__asignatura__nombre=asignatura_nombre
        ).distinct()

        # Imprime las guías encontradas para depuración
        print("Guías encontradas:", guias)

        return guias




@login_required
def success_view(request):
    return render(request, 'exito.html', {
        'message': '¡Gracias por llenar el silabo! Apreciamos el tiempo que has dedicado a completarlo.',
        'usuario': request.user.username,
    })



@login_required
def gestionar_silabo_y_guia(request, asignacion_id=None, id=None):
    """
    Función unificada para gestionar tanto sílabos como guías de estudio independiente.
    Maneja dos operaciones:
    1. Guardar un nuevo sílabo (método GET y POST con form data)
    2. Agregar una guía de estudio independiente (método POST con JSON data)
    """
    print(f"gestionar_silabo_y_guia llamada con asignacion_id={asignacion_id}, id={id}, método={request.method}")
    
    # Caso 1: Guardar guía de estudio y sílabo (POST con JSON)
    if request.method == 'POST' and request.content_type == 'application/json':
        try:
            # Decodificar los datos JSON
            data = json.loads(request.body)
            print(f"Datos JSON recibidos: {data}")
            
            # Obtener el ID de asignación
            asignacion_id = data.get('asignacion_id')
            if not asignacion_id:
                return JsonResponse({'error': 'No se proporcionó un ID de asignación válido'}, status=400)
                
            print(f"Procesando datos para asignacion_id={asignacion_id}")
            
            # Obtener la asignación
            try:
                asignacion = AsignacionPlanEstudio.objects.get(id=asignacion_id)
                print(f"Asignación encontrada: {asignacion}")
            except AsignacionPlanEstudio.DoesNotExist:
                return JsonResponse({'error': f'No se encontró la asignación con ID {asignacion_id}'}, status=404)
            
            # Procesar los datos del sílabo si están presentes
            silabo_data = data.get('silabo_data', {})
            print(f"Datos del sílabo: {silabo_data}")
            
            # Obtener el silabo actual o crear uno nuevo
            silabo = None
            if id:  # Si se está editando un sílabo existente
                silabo = get_object_or_404(Silabo, id=id)
            else:
                # Buscar si ya existe un sílabo para esta asignación
                silabo = Silabo.objects.filter(asignacion_plan=asignacion).order_by('-encuentros').first()
                
            # Si no existe un sílabo o tenemos datos para crear/actualizar uno
            if not silabo or silabo_data:
                # Si tenemos datos del sílabo, creamos o actualizamos
                if silabo_data:
                    # Crear un formulario con los datos recibidos
                    if silabo:
                        # Actualizar el sílabo existente
                        form = SilaboForm(silabo_data, instance=silabo)
                    else:
                        # Crear un nuevo sílabo
                        form = SilaboForm(silabo_data)
                    
                    if form.is_valid():
                        silabo = form.save(commit=False)
                        silabo.asignacion_plan = asignacion
                        silabo.maestro = request.user
                        silabo.save()
                        print(f"Sílabo guardado correctamente: {silabo.id}")
                    else:
                        print(f"Errores en el formulario del sílabo: {form.errors}")
                        return JsonResponse({'error': 'Datos del sílabo inválidos', 'form_errors': form.errors}, status=400)
                elif not silabo:
                    # Si no hay sílabo y no tenemos datos, creamos uno con valores predeterminados
                    try:
                        silabo = Silabo.objects.create(
                            codigo=asignacion.plan_de_estudio.codigo,
                            carrera=asignacion.plan_de_estudio.carrera,
                            asignatura=asignacion.plan_de_estudio,
                            maestro=request.user,
                            encuentros=1,
                            fecha=data.get('fecha'),
                            objetivo_conceptual="Objetivo conceptual generado automáticamente",
                            objetivo_procedimental="Objetivo procedimental generado automáticamente",
                            objetivo_actitudinal="Objetivo actitudinal generado automáticamente",
                            momento_didactico_primer="Primer momento didáctico generado automáticamente",
                            momento_didactico_segundo="Segundo momento didáctico generado automáticamente",
                            momento_didactico_tercer="Tercer momento didáctico generado automáticamente",
                            unidad=data.get('unidad', 'Unidad I'),
                            detalle_unidad="Detalle de unidad generado automáticamente",
                            contenido_tematico=data.get('contenido_tematico', 'Contenido temático generado automáticamente'),
                            forma_organizativa="Conferencia",
                            tiempo="60",
                            tecnicas_aprendizaje="Trabajo colaborativo",
                            descripcion_estrategia="Estrategia generada automáticamente",
                            eje_transversal="Investigación",
                            hp="2",
                            asignacion_plan=asignacion
                        )
                        print(f"Sílabo creado automáticamente: {silabo.id}")
                    except Exception as e:
                        print(f"Error al crear el sílabo: {e}")
                        return JsonResponse({'error': f'Error al crear el sílabo: {str(e)}'}, status=400)
            
            # Convertir el tiempo estimado a un float para el campo tiempo_minutos
            try:
                tiempo_minutos = float(data.get('tiempo_minutos', 60.0))
            except (ValueError, TypeError):
                tiempo_minutos = 60.0  # Valor predeterminado si hay un error
                
            # Convertir el puntaje a float si existe
            try:
                puntaje = float(data.get('puntaje')) if data.get('puntaje') else None
            except (ValueError, TypeError):
                puntaje = None
            
            # Mapear los datos recibidos a los campos del modelo Guia
            try:
                # Primero guardamos el sílabo sin asociarlo a una guía
                silabo.guia = None  # Aseguramos que no haya una guía asociada inicialmente
                silabo.save()
                
                # Ahora creamos la guía con referencia al sílabo
                guia = Guia.objects.create(
                    silabo=silabo,  # Asociamos la guía al sílabo
                    numero_guia=int(data.get('numero_guia', 1)),
                    fecha=data.get('fecha'),
                    unidad=data.get('unidad', silabo.unidad),
                    objetivo_conceptual=data.get('objetivo_conceptual', ''),
                    objetivo_procedimental=data.get('objetivo_procedimental', ''),
                    objetivo_actitudinal=data.get('objetivo_actitudinal', ''),
                    contenido_tematico=data.get('contenido_tematico', ''),
                    actividades=data.get('actividades', ''),
                    instrumento_cuaderno=data.get('instrumento_cuaderno', ''),
                    instrumento_organizador=data.get('instrumento_organizador', ''),
                    instrumento_diario=data.get('instrumento_diario', ''),
                    instrumento_prueba=data.get('instrumento_prueba', ''),
                    criterios_evaluacion=data.get('criterios_evaluacion', ''),
                    tiempo_minutos=tiempo_minutos,
                    recursos=data.get('recursos', ''),
                    puntaje=puntaje,
                    evaluacion_sumativa=data.get('evaluacion_sumativa', ''),
                    fecha_entrega=data.get('fecha_entrega')
                )
                print(f"Guía creada correctamente: {guia.id}")
                
                # Ahora actualizamos el sílabo para referenciar esta guía
                silabo.guia = guia
                silabo.save()
                print(f"Sílabo actualizado con referencia a la guía")
                
                # Redirigir a la vista de éxito en lugar de devolver una respuesta JSON
                return redirect('success_view')
                
            except Exception as e:
                print(f"Error al crear la guía: {e}")
                return JsonResponse({'error': f'Error al crear la guía: {str(e)}'}, status=400)
        except json.JSONDecodeError as e:
            print(f"Error al decodificar JSON: {e}")
            return JsonResponse({'error': f'Error al decodificar JSON: {str(e)}'}, status=400)
        except Exception as e:
            print(f"Error general: {e}")
            return JsonResponse({'error': f'Error general: {str(e)}'}, status=500)
    
    # Caso 2: Guardar sílabo (GET o POST con form data)
    elif asignacion_id or id:
        if asignacion_id:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        else:
            asignacion = get_object_or_404(AsignacionPlanEstudio, id=id)
        nombre_de_usuario = request.user.username
        silabos_creados = asignacion.silabo_set.count()

        if request.method == 'POST':
            form = SilaboForm(request.POST)
            if form.is_valid():
                # Guardar el sílabo
                silabo = form.save(commit=False)
                silabo.asignacion_plan = asignacion
                silabo.asignatura = asignacion.plan_de_estudio  # Aseguramos que se asigne la asignatura
                silabo.save()

                # Actualiza el conteo de sílabos creados
                silabos_creados = asignacion.silabo_set.count()
                asignacion.silabos_creados = silabos_creados
                asignacion.save()

                # Verificar si también se enviaron datos para la guía
                if 'objetivo_conceptual_guia' in request.POST:
                    # Primero guardamos el sílabo sin asociarlo a una guía
                    silabo.guia = None
                    silabo.save()
                    
                    # Crear una guía asociada al sílabo
                    guia = Guia.objects.create(
                        silabo=silabo,  # Asociamos la guía al sílabo
                        numero_guia=1,  # Valor por defecto o ajustar según necesidad
                        fecha=silabo.fecha,  # Usar la misma fecha del sílabo
                        unidad=silabo.unidad,  # Usar la misma unidad del sílabo
                        objetivo_conceptual=request.POST.get('objetivo_conceptual_guia', ''),
                        objetivo_procedimental=request.POST.get('objetivo_procedimental_guia', ''),
                        objetivo_actitudinal=request.POST.get('objetivo_actitudinal_guia', ''),
                        contenido_tematico=request.POST.get('contenido_tematico_guia', silabo.contenido_tematico),
                        actividades=request.POST.get('actividades', ''),
                        instrumento_cuaderno=request.POST.get('instrumento_cuaderno', ''),
                        instrumento_organizador=request.POST.get('instrumento_organizador', ''),
                        instrumento_diario=request.POST.get('instrumento_diario', ''),
                        instrumento_prueba=request.POST.get('instrumento_prueba', ''),
                        criterios_evaluacion=request.POST.get('criterios_evaluacion', ''),
                        tiempo_minutos=float(request.POST.get('tiempo_minutos', 60.0)),
                        recursos=request.POST.get('recursos', ''),
                        evaluacion_sumativa=request.POST.get('evaluacion_sumativa', ''),
                        fecha_entrega=request.POST.get('fecha_entrega', silabo.fecha)
                    )
                    
                    # Actualizar el sílabo para referenciar esta guía
                    silabo.guia = guia
                    silabo.save()

                messages.success(request, 'El sílabo ha sido creado correctamente.')
                return redirect('success_view')
            else:
                messages.error(request, 'Hubo un error al crear el sílabo. Por favor, revise los datos.')
        else:
            form = SilaboForm(initial={
                'codigo': asignacion.plan_de_estudio.codigo,
                'carrera': asignacion.plan_de_estudio.carrera,
                'asignatura': asignacion.plan_de_estudio,  # Asignar el plan de estudio como asignatura
                'maestro': request.user,
                'encuentros': silabos_creados + 1,
            })
            guias = obtener_estudios_independientes(asignacion.id)
            form.fields['guia'].queryset = guias

        asignaturas = Asignatura.objects.all()

        return render(request, 'generar_silabo.html', {
            'form': form,
            'asignacion': asignacion,
            'usuario': nombre_de_usuario,
            'silabos_creados': silabos_creados,
            'encuentro': silabos_creados + 1,
            'asignaturas': asignaturas,
        })
    
    # Caso de error: método no permitido o falta asignacion_id
    return JsonResponse({'error': 'Método no permitido o falta ID de asignación'}, status=405)


@login_required
def generar_silabo(request):
    """
    Función para usar el modelo de Google
    """
    def usar_modelo_google(prompt_completo, generation_config):
        """
        Usa el modelo de Google para generar una respuesta basada en el prompt dado.

        Args:
            prompt_completo (str): Prompt que contiene las instrucciones y datos.
            generation_config (dict): Configuración para la generación del modelo.

        Returns:
            str: Respuesta generada por el modelo.
        """
        # Cargar la clave API desde .env
        load_dotenv()
        api_key = os.environ.get("GOOGLE_GENERATIVE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_GENERATIVE_API_KEY no está configurada en el archivo .env")

        try:
            # Configurar la API
            genai.configure(api_key=api_key)

            # Crear el modelo y sesión de chat
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro-latest",
                generation_config=generation_config
            )
            chat_session = model.start_chat()

            # Generar respuesta
            response = chat_session.send_message(prompt_completo)
            return response.text.strip()

        except genai.errors.GenerativeAIError as e:
            raise RuntimeError(f"Error en la API de Gemini: {e}")
        except Exception as e:
            raise RuntimeError(f"Error inesperado: {e}")


    def usar_modelo_openai(prompt_completo):
        """
        Función para interactuar con OpenAI usando el cliente de chat basado en el script compartido.
        """
        try:
            # Limpiar variables de entorno de proxy que podrían estar causando el error
            for key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
                if key in os.environ:
                    del os.environ[key]
            
            # Configurar API key para OpenAI 0.28
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
                
            # Configurar la API key directamente (estilo OpenAI 0.28)
            import openai
            openai.api_key = api_key
            
            # Crear el mensaje con el modelo usando la API antigua (0.28)
            completion = openai.ChatCompletion.create(
                model="gpt-4o-mini",  # Especifica el modelo deseado
                messages=[
                    {
                        "role": "system",
                        "content": "Asistente para crear sílabo y plan de clases."
                    },
                    {
                        "role": "user",
                        "content": prompt_completo
                    }
                ]
            )

            # Extraer el contenido del mensaje generado
            messages = completion.choices[0].message.content
            print("-------------------------------------------------------------", messages)
            return messages

        except Exception as e:
            print(f"Error detallado al usar OpenAI: {str(e)}")
            raise RuntimeError(f"Error al generar respuesta con OpenAI: {str(e)}")


    def generar_con_openai(prompt):
        """Función interna para generar texto con OpenAI"""
        try:
            # Limpiar variables de entorno de proxy que podrían estar causando el error
            for key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
               if key in os.environ:
                    del os.environ[key]
            
            # Configurar API key para OpenAI 0.28
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
                
            # Configurar la API key directamente (estilo OpenAI 0.28)
            import openai
            openai.api_key = api_key
            
            # Crear el mensaje con el modelo usando la API antigua (0.28)
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Especifica el modelo deseado
                messages=[
                    {
                        "role": "system",
                        "content": "Asistente para generar guías de estudio."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extraer el contenido del mensaje
            return completion.choices[0].message.content
        except Exception as e:
            logging.error(f"Error al generar con OpenAI: {str(e)}")
            return None

    if request.method == 'POST':
        # Obtener los datos del formulario
        encuentro = request.POST.get('encuentro')
        plan = request.POST.get('plan')
        # Obtener el modelo seleccionado del formulario
        modelo_seleccionado = request.POST.get('modelo_select')
        print("Imprimiendo el modelo selecionodao:::::::::::::::::: "+str(modelo_seleccionado))
        # Ruta al archivo de datos de ejemplo
        filepath = os.path.join(settings.BASE_DIR, 'static', 'data', 'datos_ejemplo.txt')

        try:
            with open(filepath, 'r') as file:
                datos_ejemplo = file.read()
        except FileNotFoundError:
            return JsonResponse({'error': f"Error: El archivo '{filepath}' no se encuentra."}, status=400)

        # Crear el prompt completo
        prompt_completo = f"""
            Instrucciones: Crea un sílabo basado en la siguiente información y devuélvelo en formato JSON estructurado.

            Datos de ejemplo (para tu referencia):

            {datos_ejemplo}

            el silabo que vas a crear espara el encuentro: {encuentro} de 12 encuentros
            Plan de estudio: {plan}

            Devuelve los datos como un diccionario JSON con las siguientes claves:
            - objetivo_conceptual
            - objetivo_procedimental
            - objetivo_actitudinal
            - momento_didactico_primer
            - momento_didactico_segundo
            - momento_didactico_tercer
            - unidad
            - detalle_unidad
            - contenido_tematico
            - forma_organizativa
            - tiempo
            - tecnicas_aprendizaje
            - descripcion_estrategia
            - eje_transversal
            - hp
            - estudio_independiente
        """
        print("1111111111111111111111111111111111111111111111111", prompt_completo)

        generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 1524
        }

        try:
            # Usar el modelo seleccionado
            if modelo_seleccionado == 'google':
                silabo_generado = usar_modelo_google(prompt_completo, generation_config)
            elif modelo_seleccionado == 'openai':
                silabo_generado = usar_modelo_openai(prompt_completo)
            else:
                return JsonResponse({'error': 'Modelo no válido seleccionado.'}, status=400)

            # Extraer contenido JSON de la respuesta generada
            try:
                # Agregar logging para diagnóstico
                logging.info(f"Respuesta AI recibida (primeros 500 caracteres): {silabo_generado[:500]}...")
                
                # Buscar el bloque JSON con una expresión regular más robusta
                # Busca tanto bloques de código markdown con JSON como JSON directo
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```|(\{.*\})', silabo_generado, re.DOTALL)
                
                if not match:
                    error_msg = 'No se encontró un bloque JSON válido en la respuesta.'
                    logging.error(f"{error_msg} Respuesta completa: {silabo_generado}")
                    return JsonResponse({'error': error_msg, 'respuesta_completa': silabo_generado[:1000]}, status=500)

                # Extraer el JSON encontrado - puede estar en grupo 1 (dentro de ```) o grupo 2 (JSON directo)
                if match.group(1):
                    silabo_json_text = match.group(1).strip()
                else:
                    silabo_json_text = match.group(2).strip()
                
                logging.info(f"JSON extraído: {silabo_json_text[:200]}...")
                
                # Limpiar cualquier carácter especial o formato
                silabo_json_text = re.sub(r'```json|```', '', silabo_json_text).strip()
                
                # Convertir el texto a un objeto JSON
                try:
                    silabo_data = json.loads(silabo_json_text)
                except json.JSONDecodeError as json_error:
                    # Intento de reparación de JSON si fallan las comillas
                    try:
                        # Reemplazar comillas simples por dobles si es necesario
                        fixed_json = silabo_json_text.replace("'", '"')
                        silabo_data = json.loads(fixed_json)
                        logging.info("JSON reparado exitosamente reemplazando comillas simples por dobles")
                    except json.JSONDecodeError:
                        # Re-lanzar la excepción original si la reparación no funcionó
                        raise json_error
                        
            except json.JSONDecodeError as e:
                error_msg = f'Error al decodificar JSON: {str(e)}'
                logging.error(f"{error_msg} - JSON texto: {silabo_json_text}")
                return JsonResponse({
                    'error': error_msg, 
                    'json_text': silabo_json_text[:500],
                    'respuesta_completa': silabo_generado[:500]
                }, status=500)
            
            # Devolver el JSON como respuesta
            return JsonResponse({'silabo_data': silabo_data})

        except Exception as e:
            print(e)
            return JsonResponse({'error': f"Error general: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)


@csrf_exempt
def generar_estudio_independiente(request):
    """
    Vista para generar una guía de estudio utilizando IA.
    """
    def generar_con_openai(prompt):
        """Función interna para generar texto con OpenAI"""
        try:
            # Limpiar variables de entorno de proxy que podrían estar causando el error
            for key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"]:
               if key in os.environ:
                    del os.environ[key]
            
            # Configurar API key para OpenAI 0.28
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
                
            # Configurar la API key directamente (estilo OpenAI 0.28)
            import openai
            openai.api_key = api_key
            
            # Crear el mensaje con el modelo usando la API antigua (0.28)
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Especifica el modelo deseado
                messages=[
                    {
                        "role": "system",
                        "content": "Asistente para generar guías de estudio."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extraer el contenido del mensaje
            return completion.choices[0].message.content
        except Exception as e:
            logging.error(f"Error al generar con OpenAI: {str(e)}")
            return None

    if request.method == 'POST':
        asignacion_id = request.POST.get('asignacion_id')
        modelo_seleccionado = request.POST.get('modelo_select', 'google')
        
        print(f"Recibida solicitud para generar guía de estudio. Asignación ID: {asignacion_id}, Modelo: {modelo_seleccionado}")

        # Obtener la asignación y datos relacionados
        asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
        plan_estudio = asignacion.plan_de_estudio
        
        # Buscar guías anteriores para usar como contexto principal
        guias_anteriores = Guia.objects.filter(
            silabo__asignacion_plan=asignacion
        ).order_by('numero_guia')
        
        # Obtener el sílabo actual solo para información complementaria
        silabo_actual = Silabo.objects.filter(
            asignacion_plan=asignacion
        ).order_by('-encuentros').first()
        
        # Construir contexto de guías anteriores
        contexto_guias = ""
        if guias_anteriores.exists():
            for idx, guia in enumerate(guias_anteriores):
                # Procesar actividades que pueden estar en formato JSON o texto
                actividades_str = "No especificado"
                if guia.actividades:
                    try:
                        if guia.actividades.startswith('['):
                            actividades_list = json.loads(guia.actividades)
                            actividades_str = ", ".join(actividades_list)
                        else:
                            actividades_str = guia.actividades
                    except:
                        actividades_str = guia.actividades
                
                # Procesar recursos que pueden estar en formato JSON o texto
                recursos_str = "No especificado"
                if guia.recursos:
                    try:
                        if guia.recursos.startswith('['):
                            recursos_list = json.loads(guia.recursos)
                            recursos_str = ", ".join(recursos_list)
                        else:
                            recursos_str = guia.recursos
                    except:
                        recursos_str = guia.recursos
                
                contexto_guias += f"""
                Guía {idx+1}:
                - Unidad: {guia.unidad}
                - Contenido temático: {guia.contenido_tematico or "No especificado"}
                - Actividades: {actividades_str}
                - Recursos: {recursos_str}
                - Tiempo estimado: {guia.tiempo_minutos or "No especificado"} minutos
                - Puntaje: {guia.puntaje or "No especificado"}
                - Evaluación sumativa: {guia.evaluacion_sumativa or "No especificado"}
                - Objetivos: 
                  * Conceptual: {guia.objetivo_conceptual or "No especificado"}
                  * Procedimental: {guia.objetivo_procedimental or "No especificado"}
                  * Actitudinal: {guia.objetivo_actitudinal or "No especificado"}
                - Instrumentos de evaluación:
                  * Cuaderno: {guia.instrumento_cuaderno or "No especificado"}
                  * Organizador gráfico: {guia.instrumento_organizador or "No especificado"}
                  * Diario de trabajo: {guia.instrumento_diario or "No especificado"}
                  * Prueba escrita: {guia.instrumento_prueba or "No especificado"}
                """
        
        # Determinar el número de la próxima guía
        numero_proxima_guia = guias_anteriores.count() + 1
        
        # Crear el prompt completo basado en la información disponible
        if not silabo_actual:
            # Si no hay sílabo, crear un prompt básico con información del plan de estudio
            prompt_completo = f"""
            Instrucciones: Genera una descripción detallada de una guía de estudio inicial (Guía #{numero_proxima_guia}) basada en la siguiente información.
            
            Datos del Plan de Estudio:
            - Asignatura: {plan_estudio.asignatura.nombre}
            - Carrera: {plan_estudio.carrera.nombre}
            - Código: {plan_estudio.codigo}
            - Horas Prácticas (HP): {plan_estudio.hp}
            - Horas de Trabajo Independiente (HTI): {plan_estudio.hti}
            
            {f"Contexto de guías anteriores:\n{contexto_guias}" if contexto_guias else "Esta será la primera guía para esta asignación."}
            """
        else:
            # Si hay sílabo, incluir su información
            prompt_completo = f"""
            Instrucciones: Genera una descripción detallada de una guía de estudio (Guía #{numero_proxima_guia}) basada en la siguiente información.
            
            Datos del Sílabo:
            - Asignatura: {plan_estudio.asignatura.nombre}
            - Carrera: {plan_estudio.carrera.nombre}
            - Código: {plan_estudio.codigo}
            - Encuentro actual: {silabo_actual.encuentros} de 12
            - Horas Prácticas (HP): {plan_estudio.hp}
            - Horas de Trabajo Independiente (HTI): {plan_estudio.hti}
            - Unidad actual: {silabo_actual.unidad}
            - Contenido temático: {silabo_actual.contenido_tematico}
            
            {f"Contexto de guías anteriores:\n{contexto_guias}" if contexto_guias else "Esta será la primera guía para esta asignación."}
            """
        
        # Añadir la estructura JSON esperada al prompt
        prompt_completo += """
        Por favor, genera una guía de estudio en formato JSON con la siguiente estructura:
        {
          "descripcion": "Una descripción detallada del contenido temático de la guía",
          "actividades": ["Actividad 1", "Actividad 2", "Actividad 3"],
          "recursos": ["Recurso 1", "Recurso 2", "Recurso 3"],
          "tiempo_estimado": "Tiempo estimado en minutos",
          "criterios_evaluacion": ["Criterio 1", "Criterio 2", "Criterio 3"],
          "puntaje": "Puntaje sugerido para esta guía (valor numérico)",
          "evaluacion_sumativa": "Descripción de la evaluación sumativa para esta guía",
          "objetivo_conceptual": "Descripción detallada del objetivo conceptual",
          "objetivo_procedimental": "Descripción detallada del objetivo procedimental",
          "objetivo_actitudinal": "Descripción detallada del objetivo actitudinal",
          "instrumento_cuaderno": "Descripción de cómo se utilizará el cuaderno del estudiante como instrumento de evaluación",
          "instrumento_organizador": "Descripción de cómo se utilizará el organizador gráfico como instrumento de evaluación",
          "instrumento_diario": "Descripción de cómo se utilizará el diario de trabajo como instrumento de evaluación",
          "instrumento_prueba": "Descripción de cómo se utilizará la prueba escrita como instrumento de evaluación"
        }
        
        Asegúrate de que el JSON sea válido y pueda ser parseado correctamente.
        """
        
        print("Prompt generado, enviando a la API...")
        
        # Generar respuesta según el modelo seleccionado
        respuesta_ai = None
        
        if modelo_seleccionado == 'openai':
            respuesta_ai = generar_con_openai(prompt_completo)
        else:  # google por defecto
            try:
                # Configurar el modelo
                generation_config = {
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                }
                
                model = genai.GenerativeModel(
                    model_name="gemini-pro",
                    generation_config=generation_config
                )
                
                # Generar respuesta
                response = model.generate_content(prompt_completo)
                respuesta_ai = response.text
                
            except Exception as e:
                error_msg = f'Error al generar con Google AI: {str(e)}'
                logging.error(error_msg)
                return JsonResponse({'error': error_msg}, status=500)
        
        if not respuesta_ai:
            return JsonResponse({'error': 'No se pudo generar una respuesta'}, status=500)
        
        print("Respuesta generada, procesando...")
        
        # Procesar la respuesta para extraer el JSON
        try:
            # Buscar el JSON en la respuesta
            json_match = re.search(r'\{.*\}', respuesta_ai, re.DOTALL)
            
            if json_match:
                # Si encontramos el JSON dentro de bloques de código, usar el grupo 1, de lo contrario usar el grupo 2
                json_str = json_match.group(0).strip()  # Extraer el JSON encontrado

                # Limpiar el string JSON
                json_str = re.sub(r'```json|```', '', json_str).strip()
                
                # Convertir el texto a un objeto JSON
                data = json.loads(json_str)
                
                # Asegurarse de que los campos esperados estén presentes
                expected_fields = ['descripcion', 'actividades', 'recursos', 'tiempo_estimado', 'criterios_evaluacion', 'puntaje', 'evaluacion_sumativa', 'objetivo_conceptual', 'objetivo_procedimental', 'objetivo_actitudinal', 'instrumento_cuaderno', 'instrumento_organizador', 'instrumento_diario', 'instrumento_prueba']
                for field in expected_fields:
                    if field not in data:
                        data[field] = "" if field != 'tiempo_estimado' else "60"
                    
                    # Asegurarse de que los campos de lista sean realmente listas
                    if field in ['actividades', 'recursos', 'criterios_evaluacion']:
                        if not isinstance(data[field], list):
                            if data[field]:  # Si no está vacío
                                data[field] = [data[field]]
                
                print("Datos procesados correctamente, enviando respuesta")
                return JsonResponse({'guia_data': data})
            else:
                error_msg = 'No se encontró un formato JSON válido en la respuesta'
                logging.error(error_msg)
                return JsonResponse({'error': error_msg}, status=500)
                
        except json.JSONDecodeError as e:
            error_msg = f'Error al decodificar JSON: {str(e)}'
            logging.error(error_msg)
            return JsonResponse({'error': error_msg}, status=500)
        except Exception as e:
            error_msg = f'Error al procesar la respuesta: {str(e)}'
            logging.error(error_msg)
            return JsonResponse({'error': error_msg}, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)