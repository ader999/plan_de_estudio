import json

from django.http import HttpResponse, request ,HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings

#librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo ,Estudio_independiente, AsignacionPlanEstudio, Asignatura

from .forms import SilaboForm
from django.views.decorators.csrf import csrf_exempt

from openpyxl import load_workbook

from openpyxl.utils.dataframe import dataframe_to_rows
from io import BytesIO
import pandas as pd

from docx import Document
from docx.shared import Pt


import os
import google.generativeai as genai
from dotenv import load_dotenv
import re


# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))




def detalle_silabo(request):
    # Recupera todos los objetos Silabo
    silabos = Silabo.objects.all()
    return render(request, 'plan_estudio_template/detalle_silabo.html', {'silabos': silabos})




@login_required
def inicio(request):
    nombre_de_usuario = request.user.username
    asignaciones = AsignacionPlanEstudio.objects.all()
    rango = range(1, 13)  # Crear el rango para pasarlo al template

    return render(request, 'inicio.html', {'asignaciones': asignaciones, 'rango': rango,'usuario':nombre_de_usuario})

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
    estudio_independiente = {}
    for silabo in silabos:
        codigo = silabo.codigo
        if codigo not in silabos_agrupados:
            silabos_agrupados[codigo] = []
            estudio_independiente[codigo] = []  # Inicializar como una lista vacía
        silabos_agrupados[codigo].append(silabo)
        estudio_independiente[codigo].append(silabo.estudio_independiente)

    context = {
        'silabos_agrupados': silabos_agrupados,
        'estudios': estudio_independiente,
        'usuario': nombre_de_usuario
    }

    return render(request, 'plan_estudio.html', context)


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
                    ws.cell(row=row_num, column=3, value=silabo.objetivo_conceptual +' '+ silabo.objetivo_procedimental +' '+silabo.objetivo_actitudinal)
                    ws.cell(row=row_num, column=4, value=silabo.momento_didactico_primer)
                    ws.cell(row=row_num, column=5, value=silabo.unidad)
                    ws.cell(row=row_num, column=6, value=silabo.contenido_tematico)
                    ws.cell(row=row_num, column=7, value=silabo.forma_organizativa)
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

            # Agregar contenido al documento
            for silabo in silabos:
                document.add_heading(f'Sílabo {silabo.codigo}', level=1)

                # Agregar subtítulos en negrita seguidos de ":"
                document.add_paragraph().add_run('Encuentros:').bold = True
                document.add_paragraph(f'{silabo.encuentros}')

                document.add_paragraph().add_run('Fecha:').bold = True
                document.add_paragraph(f'{silabo.fecha}')

                document.add_paragraph().add_run('Unidad:').bold = True
                document.add_paragraph(f'{silabo.unidad}')

                document.add_paragraph().add_run('Objetivos:').bold = True
                document.add_paragraph(
                    f'{silabo.objetivo_conceptual}, {silabo.objetivo_actitudinal}, {silabo.objetivo_procedimental}')

                document.add_paragraph().add_run('Momentos Didácticos:').bold = True
                document.add_paragraph(
                    f'{silabo.momento_didactico_primer}, {silabo.momento_didactico_segundo}, {silabo.momento_didactico_tercer}')

                document.add_paragraph().add_run('Forma Organizativa:').bold = True
                document.add_paragraph(f'{silabo.forma_organizativa}')

                document.add_paragraph().add_run('Técnicas de Aprendizaje:').bold = True
                document.add_paragraph(f'{silabo.tecnicas_aprendizaje}')

                document.add_paragraph().add_run('Descripción Estrategia:').bold = True
                document.add_paragraph(f'{silabo.descripcion_estrategia}')

                document.add_paragraph().add_run('Eje Transversal:').bold = True
                document.add_paragraph(f'{silabo.eje_transversal}')

            # Guardar el documento en memoria
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = 'attachment; filename="silabo.docx"'
            document.save(response)

            return response

        except Exception as e:
            return JsonResponse({'error': f"Ocurrió un error al generar el documento Word: {e}"}, status=500)


@login_required
def llenar_silabo(request, asignacion_id):
    nombre_de_usuario = request.user.username
    asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)

    silabos_creados = asignacion.silabo_set.count()
    if request.method == 'POST':
        form = SilaboForm(request.POST)
        if form.is_valid():
            silabo = form.save(commit=False)  # No guardes todavía
            silabo.asignacion_plan = asignacion  # Asigna la relación
            silabo.save()  # Ahora guarda el sílabo

            # Actualiza el conteo de sílabos creados
            silabos_creados = asignacion.silabo_set.count()
            asignacion.silabos_creados = silabos_creados  # Actualiza el campo
            asignacion.save()  # Guarda la asignación actualizada


            return redirect('success_view')
        else:
            print(form.errors)  # Imprime errores del formulario para depuración
    else:
        form = SilaboForm(initial={
            'codigo': asignacion.plan_de_estudio.codigo,
            'carrera': asignacion.plan_de_estudio.carrera,
            'asignatura': asignacion.plan_de_estudio,
            'maestro': request.user,
            'encuentros':silabos_creados+1,
        })

    asignaturas = Asignatura.objects.all()
    # Obtener el número de sílabos creados para esta asignación

    return render(request, 'llenar_silabo.html', {
        'form': form,
        'asignacion': asignacion,
        'asignaturas': asignaturas,
        'usuario': nombre_de_usuario,
        'silabos_creados': silabos_creados  # Pasa el conteo a la plantilla
    })



def agregar_estudio_independiente(request):
    if request.method == 'POST':
        data = json.loads(request.body)

        # Obtener la asignatura
        asignatura = Asignatura.objects.get(id=data.get('asignatura'))

        # Crear el nuevo estudio independiente
        nuevo_estudio = Estudio_independiente.objects.create(
            asignatura=asignatura,
            numero=data.get('numero'),
            contenido=data.get('contenido'),
            tecnica_evaluacion=data.get('tecnica_evaluacion'),
            instrumento_evaluacion=data.get('instrumento_evaluacion'),
            orientacion=data.get('orientacion'),
            recursos_bibliograficos=data.get('recursos_bibliograficos'),
            enlace=data.get('enlace'),
            tiempo_estudio=data.get('tiempo_estudio'),
            fecha_entrega=data.get('fecha_entrega')
        )

        return JsonResponse({'success': True, 'id': nuevo_estudio.id, 'nombre': str(nuevo_estudio)})

    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=400)

def success_view(request):
    return render(request, 'exito.html', {
        'message': '¡Gracias por llenar el silabo! Apreciamos el tiempo que has dedicado a completarlo.'
    })




def guardar_silabo(request, asignacion_id):
    asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)
    nombre_de_usuario = request.user.username
    silabos_creados = asignacion.silabo_set.count()

    if request.method == 'POST':
        form = SilaboForm(request.POST)
        if form.is_valid():
            silabo = form.save(commit=False)  # No guardes todavía
            silabo.asignacion_plan = asignacion  # Asigna la relación
            silabo.save()  # Ahora guarda el sílabo

            # Actualiza el conteo de sílabos creados
            silabos_creados = asignacion.silabo_set.count()
            asignacion.silabos_creados = silabos_creados  # Actualiza el campo
            asignacion.save()  # Guarda la asignación actualizada

            messages.success(request, 'El sílabo ha sido creado correctamente.')
            return redirect('inicio')
        else:
            messages.error(request, 'Hubo un error al crear el sílabo. Por favor, revise los datos.')
    else:
        form = SilaboForm(initial={
            'codigo': asignacion.plan_de_estudio.codigo,
            'carrera': asignacion.plan_de_estudio.carrera,
            'asignatura': asignacion.plan_de_estudio,
            'maestro': request.user,
            'encuentros': silabos_creados + 1,
        })

    return render(request, 'generar_silabo.html', {
        'form': form,
        'asignacion': asignacion,
        'usuario': nombre_de_usuario,
        'silabos_creados': silabos_creados  # Pasa el conteo a la plantilla
    })



def generar_silabo(request):
    if request.method == 'POST':
        # Obtener el prompt del usuario desde el formulario
        prompt_usuario = request.POST.get('prompt_usuario', '')

        # Ruta al archivo de datos de ejemplo
        filepath = os.path.join(settings.BASE_DIR, 'static', 'data', 'datos_ejemplo.txt')
        print(f"Ruta del archivo: {filepath}")

        # Intentar leer el archivo con datos de ejemplo
        try:
            with open(filepath, 'r') as file:
                datos_ejemplo = file.read()
        except FileNotFoundError:
            return JsonResponse({'error': f"Error: El archivo '{filepath}' no se encuentra."}, status=400)

        # Crear el prompt completo que será enviado al modelo
        prompt_completo = f"""
            Instrucciones: Crea un sílabo basado en la siguiente información y devuélvelo en formato JSON estructurado.

            Datos de ejemplo (para tu referencia):

            {datos_ejemplo}

            Solicitud del usuario:
            {prompt_usuario}

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

            Asegúrate de devolver una salida en formato JSON con las claves y valores correspondientes a cada campo.
            """

        # Configuración del modelo generativo
        generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 1024
        }

        try:
            # Configurar y ejecutar el modelo para generar la respuesta
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro-002",
                generation_config=generation_config
            )
            chat_session = model.start_chat()
            response = chat_session.send_message(prompt_completo)

            # Obtener el texto generado
            silabo_generado = response.text.strip()  # Acceso correcto al contenido generado y eliminar espacios en blanco

            # Limpiar el formato si tiene las etiquetas ```json
            silabo_limpio = re.sub(r'```json|```', '', silabo_generado).strip()

            # Convertir el texto limpio a JSON
            try:
                silabo_data = json.loads(silabo_limpio)
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Error al formatear la respuesta como JSON.'}, status=500)

            # Enviar los datos generados a la vista
            return JsonResponse({'silabo_data': silabo_data})

        except Exception as e:
            return JsonResponse({'error': f"Error general: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)