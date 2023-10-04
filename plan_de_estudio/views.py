from django.http import HttpResponse, request ,HttpResponseNotFound
from django.shortcuts import render, redirect

#librerias para el login
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Silabo ,Estudio_independiente

from django.contrib.auth.models import User
#generar exel
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

from openpyxl import load_workbook

from openpyxl.utils.dataframe import dataframe_to_rows
from io import BytesIO
import pandas as pd




def detalle_silabo(request):
    # Recupera todos los objetos Silabo
    silabos = Silabo.objects.all()
    return render(request, 'detalle_silabo.html', {'silabos': silabos})


def silaboform(request):
    return render(request, 'formulario_silabo.html')

def inicio(request):
    return render(request,'inicio.html')

def acerca_de(request):
    return  render(request, 'acerca_de.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Inicio de sesión exitoso.')
            return redirect('plan_de_estudio')  # Cambia 'profile' por la URL deseada después del inicio de sesión
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
    print('estudio :', estudio_independiente)
    context = {
        'silabos_agrupados': silabos_agrupados,
        'estudios': estudio_independiente
    }

    return render(request, 'plan_estudio.html', context)

def Plan_de_clase(request):
    return render(request, 'detalle_plandeclase.html')


# def generar_excel(request):
#     # Recupera todos los objetos Silabo relacionados con el usuario logueado
#     silabos = Silabo.objects.filter(maestro=request.user)
#
#     # Crear un libro de Excel y una hoja de cálculo
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Sílabos"  # Establece el título de la hoja de cálculo
#
#     # Encabezados de columna en negrita
#     encabezados = ['ID', 'Carrera', 'Asignatura', 'Encuentros', 'Fecha', 'Objetivos', 'Momentos Didácticos', 'Unidad', 'Contenido Temático', 'Forma Organizativa', 'Tiempo', 'Técnicas de Aprendizaje', 'Descripción Estrategia', 'Eje Transversal', 'HP', 'Número', 'Contenido', 'Técnica de Evaluación', 'Instrumento de Evaluación', 'Orientación', 'Recursos Bibliográficos', 'Tiempo de Estudio', 'Total de Horas', 'Fecha de Entrega']
#     bold_font = Font(bold=True)  # Define un estilo de fuente en negrita
#
#     # Agregar encabezados a la hoja de cálculo
#     for col_num, encabezado in enumerate(encabezados, 2):
#         cell = ws.cell(row=2, column=col_num, value=encabezado)  # Los encabezados se agregan en la primera fila
#         cell.font = bold_font  # Aplica el estilo de fuente en negrita
#
#     # Agregar datos a la hoja de cálculo
#     row_num = 3  # Comienza en la segunda fila
#     for silabo in silabos:
#         ws.cell(row=row_num, column=2, value=silabo.id)
#         ws.cell(row=row_num, column=3, value=silabo.carrera.nombre)
#         ws.cell(row=row_num, column=4, value=silabo.asignatura.nombre)
#         ws.cell(row=row_num, column=5, value=silabo.encuentros)
#         ws.cell(row=row_num, column=6, value=silabo.fecha)
#         ws.cell(row=row_num, column=7, value=silabo.objetivos)
#         ws.cell(row=row_num, column=8, value=silabo.momentos_didacticos)
#         ws.cell(row=row_num, column=9, value=silabo.unidad)
#         ws.cell(row=row_num, column=10, value=silabo.contenido_tematico)
#         ws.cell(row=row_num, column=11, value=silabo.forma_organizativa)
#         ws.cell(row=row_num, column=12, value=silabo.tiempo)
#         ws.cell(row=row_num, column=13, value=silabo.tecnicas_aprendizaje)
#         ws.cell(row=row_num, column=14, value=silabo.descripcion_estrategia)
#         ws.cell(row=row_num, column=15, value=silabo.eje_transversal)
#         ws.cell(row=row_num, column=16, value=silabo.hp)
#         ws.cell(row=row_num, column=17, value=silabo.numero)
#         ws.cell(row=row_num, column=18, value=silabo.contenido)
#         ws.cell(row=row_num, column=19, value=silabo.tecnica_evaluacion)
#         ws.cell(row=row_num, column=20, value=silabo.instrumento_evaluacion)
#         ws.cell(row=row_num, column=21, value=silabo.orientacion)
#         ws.cell(row=row_num, column=22, value=silabo.recursos_bibliograficos)
#         ws.cell(row=row_num, column=23, value=silabo.tiempo_estudio)
#         ws.cell(row=row_num, column=24, value=silabo.total_horas)
#         ws.cell(row=row_num, column=25, value=silabo.fecha_entrega)
#         row_num += 1
#
#     # Crear una respuesta HTTP para descargar el archivo Excel
#     response = HttpResponse(content_type='application/ms-excel')
#     response['Content-Disposition'] = 'attachment; filename=silabos.xlsx'
#     wb.save(response)
#
#     return response


@login_required
def generar_excel(request):
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
def generar_pdf_silabo(request):
    from io import BytesIO
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from django.http import HttpResponse, JsonResponse
    from django.shortcuts import get_object_or_404
    from reportlab.lib.units import inch

    from .models import Silabo

    if request.method == 'POST':
        codigo_silabo = request.POST.get('codigoSilabo', '')  # Validación de entrada
        if not codigo_silabo:
            return JsonResponse({'error': 'El código de sílabo no se proporcionó.'}, status=400)

        usuario = request.user
        silabos = Silabo.objects.filter(codigo=codigo_silabo, maestro=usuario)

        if not silabos.exists():
            return JsonResponse({'error': 'No se encontraron sílabos para este usuario con el código especificado.'},
                                status=404)

        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

            elements = []

            # ... Configuración de título y otros elementos

            table_data = [
                ["No de Encuentros", "Fecha", "Unidad", "Objetivos de la Unidad",
                 "Momentos Didácticos",
                 "Forma Organizativa", "Técnicas de Aprendizaje",
                 "Descripción Estrategia", "Evaluación Formativa"]
            ]

            for silabo in silabos:
                table_data.append([
                    str(silabo.encuentros),
                    str(silabo.fecha),
                    str(silabo.unidad),
                    str(silabo.objetivo_conceptual) + ', ' + str(silabo.objetivo_actitudinal) + ', ' + str(
                        silabo.objetivo_procedimental),
                    str(silabo.momento_didactico_primer) + ', ' + (silabo.momento_didactico_segundo) + ', ' + str(
                        silabo.momento_didactico_tercer),
                    str(silabo.forma_organizativa),
                    str(silabo.tecnicas_aprendizaje),
                    str(silabo.descripcion_estrategia),
                    str(silabo.eje_transversal)
                ])

            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
            ])

            col_widths = [1.0 * inch, 1.0 * inch, 1.0 * inch, 1.5 * inch, 1.5 * inch, 1.0 * inch, 1.0 * inch,
                          1.5 * inch, 1.0 * inch]

            table = Table(table_data, colWidths=col_widths, style=style)
            elements.append(table)

            doc.build(elements)

            pdf = buffer.getvalue()
            buffer.close()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="silabo.pdf"'
            return response

        except Exception as e:
            return JsonResponse({'error': f"Ocurrió un error al generar el PDF: {e}"}, status=500)

        # Resto del código