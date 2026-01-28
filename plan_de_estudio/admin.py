from django.contrib import admin
from .models import Plan_de_estudio, Asignatura, Carrera, Silabo, Guia, AsignacionPlanEstudio, PlanTematico, ProgramaAsignatura2026
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django import forms
from django.contrib.admin import DateFieldListFilter, RelatedFieldListFilter, AllValuesFieldListFilter
from django.forms import DateInput
from import_export.admin import ExportMixin
from import_export import resources
from django.utils.html import format_html
from django.db.models import Count
from django.contrib.auth.models import User
from .document_generators import generar_excel_admin
from django.urls import path, reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from .email_utils import enviar_correos_plan_incompleto
from django.shortcuts import render, redirect
from .utils.gemini_parser import parse_curriculum_with_ai
import logging

logger = logging.getLogger(__name__)

admin.site.site_header = 'PLANEAUML'
admin.site.index_title = 'Bienbenidos al Panel de control del sitio'
admin.site.site_title = 'ADMIN'


class FiltrarClases(admin.ModelAdmin):
    list_per_page = 20
    search_fields = ('nombre',)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if not search_term:
            queryset = queryset.order_by('-id')[:10]
        return queryset, use_distinct

class PlanDeEstudioAdmin(ExportMixin, admin.ModelAdmin):  # Agrega ExportMixin aquí
    class CarreraFilter(admin.SimpleListFilter):
        title = 'Carrera'
        parameter_name = 'carrera'

        def lookups(self, request, model_admin):
            # Retornar todas las opciones de carrera disponibles
            return [(c.id, c.nombre) for c in Carrera.objects.all()]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(carrera__id=self.value())
            return queryset

    class PlanDeEstudioResource(resources.ModelResource):
        class Meta:
            model = Plan_de_estudio
            fields = ('carrera__nombre', 'año', 'trimestre', 'codigo', 'asignatura__nombre', 'horas_presenciales', 'horas_estudio_independiente','total_horas')

    list_per_page = 20  # Limitar a 20 elementos por página
    list_display = ('carrera', 'año', 'trimestre', 'asignatura', 'pr')  # Mostrar los campos
    list_filter = (CarreraFilter, 'año', 'trimestre')  # Filtros en el panel de administración, incluyendo 'carrera'
    autocomplete_fields = ['asignatura', 'pr', 'pc', 'cr']
    search_fields = ('asignatura__nombre', 'codigo') # Para permitir búsqueda en autocomplete
    resource_class = PlanDeEstudioResource
    
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if not search_term:
            # Mostrar los últimos 10 agregados por defecto si no hay término de búsqueda
            queryset = queryset.order_by('-id')[:10]
        return queryset, use_distinct
    readonly_fields = ('total_horas',)  # 'th' es solo lectura en el formulario

    fieldsets = (
        ('Datos Generales', {
            'fields': ('carrera', 'año', 'trimestre', 'codigo', 'asignatura', 'pr', 'pc', 'cr', 'horas_presenciales', 'horas_estudio_independiente')
        }),
        ('Documentos y Relaciones', {
            'fields': ('plan_tematico', 'plan_tematico_ref', 'documento_adjunto'),
            'classes': ('collapse',),
            'description': 'Documentos adjuntos y relaciones con plan temático'
        }),
    )

    def total_horas(self, obj):
        # Asegurarse de que hp y hti no sean None antes de sumar
        if obj.horas_presenciales is not None and obj.horas_estudio_independiente is not None:
            return obj.horas_presenciales + obj.horas_estudio_independiente
        return 0  # Si alguno es None, devolver 0 o cualquier valor predeterminado


class AsignaturaFilter(admin.SimpleListFilter):
    title = _('Asignatura')
    parameter_name = 'asignatura'

    def lookups(self, request, model_admin):
        # Obtener una lista de asignaturas únicas en los silabos
        asignaturas = Silabo.objects.values_list('asignacion_plan__plan_de_estudio__asignatura__id', 'asignacion_plan__plan_de_estudio__asignatura__nombre').distinct()
        return [(asignatura[0], asignatura[1]) for asignatura in asignaturas]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(asignacion_plan__plan_de_estudio__asignatura__id=value)
        return queryset


class UsuarioConSilabosFilter(admin.SimpleListFilter):
    title = 'Usuario'
    parameter_name = 'usuario_con_silabos'

    def lookups(self, request, model_admin):
        # Obtener usuarios que tienen sílabos
        usuarios_con_silabos = Silabo.objects.values_list('asignacion_plan__usuario', flat=True).distinct()
        return [(u.id, str(u)) for u in User.objects.filter(id__in=usuarios_con_silabos)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(asignacion_plan__usuario_id=self.value())
        return queryset


class FiltarSilabo(admin.ModelAdmin):
    list_display = ('encuentros',  'asignacion_plan', 'fecha')
    list_per_page = 20
    list_filter = (
        ('fecha', DateFieldListFilter),  # Utiliza el widget de fecha aquí
        ('asignacion_plan__plan_de_estudio__asignatura__nombre', admin.AllValuesFieldListFilter),  # Filtro por nombre de asignatura
        UsuarioConSilabosFilter,  # Filtro personalizado para usuarios con sílabos
        ('asignacion_plan__plan_de_estudio', RelatedFieldListFilter),  # Filtro para la asignación
    )
    readonly_fields = ('codigo', 'encuentros', 'fecha', 'guia', 'asignacion_plan')  # Campos que solo serán de lectura
    exclude = ()  # No excluir campos innecesarios

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'encuentros':
            kwargs['widget'] = forms.NumberInput(attrs={'min': '1', 'max': '10', 'step': '1'})
            kwargs['validators'] = [MinValueValidator(1), MaxValueValidator(10)]
        elif db_field.name == 'fecha':
            # Utiliza el widget de calendario AdminDateWidget para el campo de fecha.
            kwargs['widget'] = DateInput(attrs={'type': 'date'})
        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Filtra solo los usuarios que tienen sílabos creados
        return qs.filter(asignacion_plan__usuario__in=Silabo.objects.values('asignacion_plan__usuario').distinct())


class FiltrarGuia(admin.ModelAdmin):
    list_filter = ('silabo__codigo',)
    list_per_page = 20
    readonly_fields = ('silabo', 'numero_encuentro', 'fecha')  # Campos que solo serán de lectura

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AsignacionPlanEstudioAdmin(admin.ModelAdmin):
    change_list_template = 'admin/plan_de_estudio/asignacionplanestudio/change_list.html'
    # Añade 'exportar_excel_boton' a list_display
    list_display = ('usuario', 'plan_de_estudio','fecha_asignacion', 'progreso_silabos_guias', 'completado_icono', 'exportar_excel_boton')
    readonly_fields = ('silabos_creados', 'guias_creadas')
    autocomplete_fields = ['plan_de_estudio'] # Habilita buscador dinámico
    list_filter = ('plan_de_estudio__carrera', 'plan_de_estudio__año', 'plan_de_estudio__trimestre', 'usuario') # Añadir filtros útiles

    def completado_icono(self, obj):
        # Retorna True si silabos_creados es igual a 12
        # Ajusta el número 12 si el total esperado de sílabos es diferente
        total_esperado = 12 # O obtén esto dinámicamente si es variable
        return obj.silabos_creados >= total_esperado # Usar >= por si acaso
    completado_icono.boolean = True
    completado_icono.short_description = 'Completado'

    def progreso_silabos_guias(self, obj):
        return f"S:{obj.silabos_creados}, G:{obj.guias_creadas}"
    progreso_silabos_guias.short_description = 'Progreso (S/G)'

    # Método para generar el botón de exportar
    def exportar_excel_boton(self, obj):
        # Crea la URL para la vista de exportación específica para este objeto (obj)
        url = reverse('admin:plan_de_estudio_asignacionplanestudio_exportar_excel', args=[obj.pk])
        # Retorna el HTML del botón como un enlace
        return format_html('<a class="button" href="{}">Exportar Excel</a>', url)
    exportar_excel_boton.short_description = 'Exportar Sílabos/Guías' # Nombre de la columna
    exportar_excel_boton.allow_tags = True # Necesario para renderizar HTML (aunque format_html es preferido)

    # Método para añadir URLs personalizadas al admin de este modelo
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Define la URL que coincide con la usada en 'reverse' dentro de exportar_excel_boton
            path(
                '<int:asignacion_id>/exportar_excel/', # La URL que captura el ID
                self.admin_site.admin_view(generar_excel_admin), # Llama a la vista importada, protegida por admin
                name='plan_de_estudio_asignacionplanestudio_exportar_excel' # Nombre para usar en 'reverse'
            ),
            path(
                'enviar-recordatorios/',
                self.admin_site.admin_view(self.enviar_recordatorios_view),
                name='plan_de_estudio_asignacionplanestudio_enviar_recordatorios'
            ),
        ]
        # Añade las URLs personalizadas ANTES que las URLs por defecto
        return custom_urls + urls

    def enviar_recordatorios_view(self, request):
        try:
            cantidad = enviar_correos_plan_incompleto()
            self.message_user(request, f'Se enviaron {cantidad} recordatorios exitosamente.', level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f'Error al enviar recordatorios: {str(e)}', level=messages.ERROR)
        return HttpResponseRedirect("../")


class CompletadoFilter(admin.SimpleListFilter):
    title = 'Estado de Asignación'
    parameter_name = 'asignado'

    def lookups(self, request, model_admin):
        return (
            ('si', 'Asignados'),
            ('no', 'No Asignados'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'si':
            # Encuentra planes temáticos que están asignados a algún plan de estudio
            plan_tematicos_asignados = Plan_de_estudio.objects.filter(
                plan_tematico_ref__isnull=False
            ).values_list('plan_tematico_ref', flat=True)
            return queryset.filter(id__in=plan_tematicos_asignados)

        if self.value() == 'no':
            # Encuentra planes temáticos que no están asignados a ningún plan de estudio
            plan_tematicos_asignados = Plan_de_estudio.objects.filter(
                plan_tematico_ref__isnull=False
            ).values_list('plan_tematico_ref', flat=True)
            return queryset.exclude(id__in=plan_tematicos_asignados)


class PlanTematicoAdmin(admin.ModelAdmin):
    list_display = ('plan_estudio', 'unidades_completadas_count', 'planes_de_estudio_related', 'completado_icono')
    list_filter = (CompletadoFilter,)
    search_fields = ('plan_estudio__codigo', 'plan_estudio__asignatura__nombre')
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def unidades_completadas_count(self, obj):
        return obj.get_numero_unidades_completadas()
    unidades_completadas_count.short_description = 'Unidades Llenadas'

    def completado_icono(self, obj):
        # Verificamos si este PlanTematico está relacionado con algún Plan_de_estudio
        return Plan_de_estudio.objects.filter(plan_tematico_ref=obj).exists()

    completado_icono.boolean = True  # Indica que este es un campo booleano
    completado_icono.short_description = 'Asignado'

    def planes_de_estudio_related(self, obj):
        # Obtener todos los planes de estudio que referencian a este PlanTematico
        planes = Plan_de_estudio.objects.filter(plan_tematico_ref=obj)
        if planes.exists():
            return ", ".join([str(plan) for plan in planes])
        return "No asignado"

    planes_de_estudio_related.short_description = "Plan de Estudio"

    def get_queryset(self, request):
        # Ya no necesitamos anotar con conteos basados en la relación anterior
        return super().get_queryset(request)

class ProgramaAsignatura2026Admin(admin.ModelAdmin):
    list_display = ('plan_estudio',)
    search_fields = ('plan_estudio__codigo', 'plan_estudio__asignatura__nombre')
    autocomplete_fields = ['plan_estudio']
    
    fieldsets = (
        ('Información General', {
            'fields': (
                'plan_estudio',
                'fundamentacion',
                'relacion_unidades',
                'aportes_perfil',
                'valores',
                'ejes_transversales',
            )
        }),
        ('Objetivos Generales', {
            'fields': (
                'objetivo_conceptual',
                'objetivo_procedimental',
                'objetivo_actitudinal',
            )
        }),
        ('Unidad I', {
            'fields': (
                'unidad_1_nombre',
                ('unidad_1_horas_teoricas', 'unidad_1_horas_practicas', 'unidad_1_horas_independientes'),
                'unidad_1_objetivos_especificos',
                'unidad_1_contenido',
                'unidad_1_mediacion',
                'unidad_1_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Unidad II', {
            'fields': (
                'unidad_2_nombre',
                ('unidad_2_horas_teoricas', 'unidad_2_horas_practicas', 'unidad_2_horas_independientes'),
                'unidad_2_objetivos_especificos',
                'unidad_2_contenido',
                'unidad_2_mediacion',
                'unidad_2_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Unidad III', {
            'fields': (
                'unidad_3_nombre',
                ('unidad_3_horas_teoricas', 'unidad_3_horas_practicas', 'unidad_3_horas_independientes'),
                'unidad_3_objetivos_especificos',
                'unidad_3_contenido',
                'unidad_3_mediacion',
                'unidad_3_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Unidad IV', {
            'fields': (
                'unidad_4_nombre',
                ('unidad_4_horas_teoricas', 'unidad_4_horas_practicas', 'unidad_4_horas_independientes'),
                'unidad_4_objetivos_especificos',
                'unidad_4_contenido',
                'unidad_4_mediacion',
                'unidad_4_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Unidad V', {
            'fields': (
                'unidad_5_nombre',
                ('unidad_5_horas_teoricas', 'unidad_5_horas_practicas', 'unidad_5_horas_independientes'),
                'unidad_5_objetivos_especificos',
                'unidad_5_contenido',
                'unidad_5_mediacion',
                'unidad_5_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Unidad VI', {
            'fields': (
                'unidad_6_nombre',
                ('unidad_6_horas_teoricas', 'unidad_6_horas_practicas', 'unidad_6_horas_independientes'),
                'unidad_6_objetivos_especificos',
                'unidad_6_contenido',
                'unidad_6_mediacion',
                'unidad_6_evaluacion',
            ),
             'classes': ('collapse',),
        }),
        ('Bibliografía', {
            'fields': (
                'bibliografia_basica',
                'bibliografia_complementaria',
                'webgrafia',
            )
        }),
    )

    
    change_form_template = 'admin/plan_de_estudio/programaasignatura2026/change_form.html'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-docx/', self.admin_site.admin_view(self.import_docx_view), name='plan_de_estudio_programaasignatura2026_import_docx'),
        ]
        return custom_urls + urls

    def import_docx_view(self, request):
        if request.method == 'POST':
            docx_file = request.FILES.get('docx_file')
            if docx_file:
                try:
                    data = parse_curriculum_with_ai(docx_file)
                    request.session['imported_programa_data'] = data
                    messages.success(request, 'Documento procesado exitosamente por la IA. Verifique los datos.')
                except Exception as e:
                    logger.error(f"Error processing docx: {e}")
                    messages.error(request, f'Error al procesar el documento: {str(e)}')
            else:
                messages.error(request, 'Por favor, seleccione un archivo.')
            return redirect('admin:plan_de_estudio_programaasignatura2026_add')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Importar Programa desde Word',
            'opts': self.model._meta,
        }
        return render(request, 'admin/plan_de_estudio/programaasignatura2026/import_form.html', context)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        imported_data = request.session.pop('imported_programa_data', None)
        if imported_data:
            initial.update(imported_data)
        return initial


admin.site.register(Plan_de_estudio, PlanDeEstudioAdmin)
admin.site.register(Asignatura, FiltrarClases)
admin.site.register(Carrera)
admin.site.register(Silabo, FiltarSilabo)
admin.site.register(Guia, FiltrarGuia)
admin.site.register(AsignacionPlanEstudio, AsignacionPlanEstudioAdmin)
admin.site.register(PlanTematico, PlanTematicoAdmin)
admin.site.register(ProgramaAsignatura2026, ProgramaAsignatura2026Admin)
