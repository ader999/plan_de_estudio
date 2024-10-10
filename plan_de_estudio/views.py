import json

from django.http import HttpResponse, request ,HttpResponseNotFound, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

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




def detalle_silabo(request):
    # Recupera todos los objetos Silabo
    silabos = Silabo.objects.all()
    return render(request, 'detalle_silabo.html', {'silabos': silabos})




@login_required
def inicio(request):
    nombre_de_usuario = request.user.username

    asignaciones = AsignacionPlanEstudio.objects.filter(usuario=request.user)

    return render(request,'inicio.html',{'usuario':nombre_de_usuario, 'asignaciones': asignaciones})

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
    return render(request, 'detalle_plandeclase.html')




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



def llenar_silabo(request, asignacion_id):
    asignacion = get_object_or_404(AsignacionPlanEstudio, id=asignacion_id)

    if request.method == 'POST':
        form = SilaboForm(request.POST)
        if form.is_valid():
            form.save()

            # Actualiza el campo completado de la asignación
            asignacion.completado = True
            asignacion.save()

            return redirect('success_view')
        else:
            print(form.errors)  # Para verificar si hay errores en el formulario
    else:
        form = SilaboForm(initial={
            'codigo': asignacion.plan_de_estudio.codigo,
            'carrera': asignacion.plan_de_estudio.carrera,
            'asignatura': asignacion.plan_de_estudio,
            'maestro': request.user
        })

    asignaturas = Asignatura.objects.all()

    return render(request, 'llenar_silabo.html', {'form': form, 'asignacion': asignacion, 'asignaturas': asignaturas})



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