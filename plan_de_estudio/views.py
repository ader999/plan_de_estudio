import json

from django.db.models.functions import Lower
from django.http import HttpResponse, request ,HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings

#librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo ,Estudio_independiente, AsignacionPlanEstudio, Asignatura, Plan_de_estudio

from .forms import SilaboForm
from django.views.decorators.csrf import csrf_exempt

from openpyxl import load_workbook
from django.db.models import Count

from openpyxl.utils.dataframe import dataframe_to_rows
from io import BytesIO
import pandas as pd

from docx import Document
from docx.shared import Pt


import os
import google.generativeai as genai
import openai

from dotenv import load_dotenv
import re


# Cargar variables de entorno
load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))



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
    return redirect('plan_de_estudio')  # Reemplaza 'pagina_principal' con la URL de tu


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

        # Paso 4: Filtrar los estudios independientes que tengan la misma asignatura
        estudios_independientes = Estudio_independiente.objects.filter(
            asignatura__nombre=asignatura_nombre
        )

        # Imprime los estudios independientes encontrados para depuración
        print("Estudios Independientes encontrados:", estudios_independientes)

        return estudios_independientes


@login_required
def llenar_silabo(request, asignacion_id):


    nombre_de_usuario = request.user.username
    asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)

    silabos_creados = asignacion.silabo_set.count()

    # Obtener el queryset de estudios independientes filtrados
    estudios_independientes = obtener_estudios_independientes(asignacion_id)

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
        # Inicializa el formulario con los valores correspondientes
        form = SilaboForm(initial={
            'codigo': asignacion.plan_de_estudio.codigo,
            'carrera': asignacion.plan_de_estudio.carrera,
            'asignatura': asignacion.plan_de_estudio,
            'maestro': request.user,
            'encuentros': silabos_creados + 1,
        })

    # Aquí estás asignando los estudios independientes para el formulario
    form.fields['estudio_independiente'].queryset = estudios_independientes

    asignaturas = Asignatura.objects.all()

    return render(request, 'llenar_silabo.html', {
        'form': form,
        'asignacion': asignacion,
        'asignaturas': asignaturas,
        'usuario': nombre_de_usuario,
        'silabos_creados': silabos_creados,
        'encuentro': silabos_creados + 1,
    })


@login_required
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

@login_required
def success_view(request):
    return render(request, 'exito.html', {
        'message': '¡Gracias por llenar el silabo! Apreciamos el tiempo que has dedicado a completarlo.',
        'usuario': request.user.username,
    })



@login_required
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
        estudios_independientes=  obtener_estudios_independientes(asignacion_id)
        form.fields['estudio_independiente'].queryset = estudios_independientes

    asignaturas = Asignatura.objects.all()

    return render(request, 'generar_silabo.html', {
        'form': form,
        'asignacion': asignacion,
        'usuario': nombre_de_usuario,
        'silabos_creados': silabos_creados,  # Pasa el conteo a la plantilla
        'encuentro': silabos_creados + 1,
        'asignaturas': asignaturas,
    })





@login_required
def generar_silabo(request):
    # Función para usar el modelo de Google
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
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en el archivo .env")

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
        # Inicializar cliente de OpenAI
        client = openai.Client(api_key=os.environ.get("OPENAI_API_KEY"))

        try:
            # Crear el mensaje con el modelo
            response = client.chat.completions.create(
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
            messages = response.choices[0].message.content.strip()
            print("-------------------------------------------------------------", messages)
            return messages

        except Exception as e:
            raise RuntimeError(f"Error al generar respuesta con OpenAI: {str(e)}")

    if request.method == 'POST':
        # Obtener los datos del formulario
        prompt_usuario = request.POST.get('prompt_usuario', '')
        encuentro = request.POST.get('encuentro')
        plan = request.POST.get('plan')
        modelo_seleccionado = request.POST.get('modelo_select')  # Por defecto usa Google
        #modelo_seleccionado = 'google'
        print("Imprimiendo el modelo selecionodao:::::::::::::::::: "+modelo_seleccionado)
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
                # Buscar el bloque JSON con una expresión regular
                match = re.search(r'\{.*\}', silabo_generado, re.DOTALL)
                if not match:
                    return JsonResponse({'error': 'No se encontró un bloque JSON válido en la respuesta.'}, status=500)

                silabo_json_text = match.group(0).strip()  # Extraer el JSON encontrado

                # Convertir el texto a un objeto JSON
                silabo_data = json.loads(silabo_json_text)
            except json.JSONDecodeError as e:
                return JsonResponse({'error': f'Error al decodificar JSON: {str(e)}'}, status=500)

            # Devolver el JSON como respuesta
            return JsonResponse({'silabo_data': silabo_data})

        except Exception as e:
            return JsonResponse({'error': f"Error general: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Método no permitido.'}, status=405)