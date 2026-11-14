from django.contrib import admin
from .models import (
    Plan_de_estudio, Asignatura, Carrera, Silabo, Guia,
    AsignacionPlanEstudio, PlanTematico, ProgramaAsignatura2026,
    CopiaSeguridad, ModeloIAConfig
)
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
from django.shortcuts import render, redirect, get_object_or_404
from .utils.gemini_parser import parse_curriculum_with_ai
from .ai_generators import listar_modelos_disponibles
import json
import logging
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q

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
            fields = ('carrera__nombre', 'pensol', 'año', 'trimestre', 'codigo', 'asignatura__nombre', 'horas_presenciales', 'horas_estudio_independiente','total_horas')

    list_per_page = 20  # Limitar a 20 elementos por página
    list_display = ('carrera', 'pensol', 'año', 'trimestre', 'asignatura', 'pr')  # Mostrar los campos
    list_filter = (CarreraFilter, 'pensol', 'año', 'trimestre')  # Filtros en el panel de administración, incluyendo 'carrera'
    autocomplete_fields = ['asignatura', 'pr', 'pc', 'cr']
    search_fields = ('asignatura__nombre', 'codigo') # Para permitir búsqueda en autocomplete
    resource_class = PlanDeEstudioResource
    
    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if not search_term:
            # Mostrar los últimos 10 agregados por defecto si no hay término de búsqueda
            queryset = queryset.order_by('-id')
        return queryset, use_distinct
    readonly_fields = ('total_horas',)  # 'th' es solo lectura en el formulario

    fieldsets = (
        ('Datos Generales', {
            'fields': ('carrera', 'pensol', 'año', 'trimestre', 'codigo', 'asignatura', 'pr', 'pc', 'cr', 'horas_presenciales', 'horas_estudio_independiente')
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
            kwargs['widget'] = forms.NumberInput(attrs={'min': '1', 'max': '11', 'step': '1'})
            kwargs['validators'] = [MinValueValidator(1), MaxValueValidator(11)]
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
    list_display = ('usuario', 'plan_de_estudio', 'bloque', 'fecha_asignacion', 'progreso_silabos_guias', 'completado_icono', 'exportar_excel_boton')
    readonly_fields = ('silabos_creados', 'guias_creadas', 'curso_classroom_id', 'curso_classroom_url')
    autocomplete_fields = ['plan_de_estudio', 'usuario'] # Habilita buscador dinámico
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name') # Habilita buscador por usuario
    search_help_text = "Busque por nombre de usuario, nombre o apellido"
    list_filter = ('plan_de_estudio__carrera', 'plan_de_estudio__pensol', 'plan_de_estudio__año', 'plan_de_estudio__trimestre', 'bloque') # Añadir filtros útiles

    def completado_icono(self, obj):
        # Retorna True si silabos_creados es igual a 11
        # Ajusta el número 11 si el total esperado de sílabos es diferente
        total_esperado = 11 # O obtén esto dinámicamente si es variable
        return obj.silabos_creados >= total_esperado # Usar >= por si acaso
    completado_icono.boolean = True
    completado_icono.short_description = 'Completado'

    def progreso_silabos_guias(self, obj):
        return f"S:{obj.silabos_creados}, G:{obj.guias_creadas}"
    progreso_silabos_guias.short_description = 'Progreso (S/G)'

    # Método para generar el botón de exportar y ver planeación
    def exportar_excel_boton(self, obj):
        url_excel = reverse('admin:plan_de_estudio_asignacionplanestudio_exportar_excel', args=[obj.pk])
        url_planeacion = reverse('ver_planeacion', args=[obj.pk])
        return format_html(
            '<div style="display:flex; flex-direction:column; gap:5px; min-width:110px;">'
            '<a class="button" href="{}" style="text-align:center; padding:4px 8px; font-weight:600;">Exportar Excel</a>'
            '<a class="button" href="{}" style="text-align:center; padding:4px 8px; font-weight:600; background:#198754; color:white; border-color:#198754;">Ver Planeación</a>'
            '</div>',
            url_excel, url_planeacion
        )
    exportar_excel_boton.short_description = 'Acciones' # Nombre de la columna
    exportar_excel_boton.allow_tags = True # Necesario para renderizar HTML

    # Método para añadir URLs personalizadas al admin de este modelo
    def get_urls(self):
        from . import views
        urls = super().get_urls()
        custom_urls = [
            # Define la URL que coincide con la usada en 'reverse' dentro de exportar_excel_boton
            path(
                '<int:asignacion_id>/exportar_excel/', # La URL que captura el ID
                self.admin_site.admin_view(generar_excel_admin), # Llama a la vista importada, protegida por admin
                name='plan_de_estudio_asignacionplanestudio_exportar_excel' # Nombre para usar en 'reverse'
            ),
            path(
                '<int:asignacion_id>/ver_planeacion/',
                self.admin_site.admin_view(views.ver_planeacion),
                name='plan_de_estudio_asignacionplanestudio_ver_planeacion'
            ),
            path(
                'enviar-recordatorios/',
                self.admin_site.admin_view(self.enviar_recordatorios_view),
                name='plan_de_estudio_asignacionplanestudio_enviar_recordatorios'
            ),
            path(
                'exportar-asignaciones/',
                self.admin_site.admin_view(self.exportar_asignaciones_view),
                name='plan_de_estudio_asignacionplanestudio_exportar_asignaciones'
            ),
            path(
                'user-search/',
                self.admin_site.admin_view(self.user_search_view),
                name='plan_de_estudio_asignacionplanestudio_user_search'
            ),
        ]
        # Añade las URLs personalizadas ANTES que las URLs por defecto
        return custom_urls + urls

    def user_search_view(self, request):
        term = request.GET.get('term', '')
        users = User.objects.filter(
            Q(username__icontains=term) | 
            Q(first_name__icontains=term) | 
            Q(last_name__icontains=term)
        )[:20] # Limit to 20 results
        
        results = [
            {
                'id': user.id, 
                'text': f"({user.username}) {user.first_name} {user.last_name}"
            } 
            for user in users
        ]
        return JsonResponse({'results': results})

    def exportar_asignaciones_view(self, request):
        from .forms import ExportarAsignacionesForm
        from .export_asignaciones import generar_excel_asignaciones_multiples, generar_word_asignaciones_multiples
        
        if request.method == 'POST':
            form = ExportarAsignacionesForm(request.POST)
            if form.is_valid():
                import datetime
                from django.utils import timezone
                trimestre = form.cleaned_data['trimestre']
                carreras = form.cleaned_data['carreras']
                años = form.cleaned_data['años']
                
                # Automatic date calculation based on trimester
                current_year = timezone.now().year
                if trimestre == 'I':
                    fecha_inicio = datetime.date(current_year, 3, 1)
                elif trimestre == 'II':
                    fecha_inicio = datetime.date(current_year, 6, 1)
                elif trimestre == 'III':
                    fecha_inicio = datetime.date(current_year, 9, 1)
                else: # IV
                    fecha_inicio = datetime.date(current_year, 12, 1)

                queryset = AsignacionPlanEstudio.objects.filter(
                    plan_de_estudio__trimestre=trimestre,
                    plan_de_estudio__carrera__in=carreras,
                    plan_de_estudio__año__in=años
                ).select_related('plan_de_estudio__carrera', 'plan_de_estudio__asignatura', 'usuario') \
                 .order_by('plan_de_estudio__carrera__nombre', 'plan_de_estudio__año')

                if 'export_excel' in request.POST:
                    return generar_excel_asignaciones_multiples(queryset, fecha_inicio)
                elif 'export_word' in request.POST:
                    return generar_word_asignaciones_multiples(queryset, fecha_inicio)
            else:
                print("Formulario Invalido:", form.errors)
        else:
            form = ExportarAsignacionesForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Exportar Asignaciones',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/plan_de_estudio/asignacionplanestudio/exportar_form.html', context)


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
            modelo_ia_id = request.POST.get('modelo_ia_id')
            if docx_file:
                try:
                    data = parse_curriculum_with_ai(docx_file, modelo_config_id=modelo_ia_id)
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
            'modelos_ia': ModeloIAConfig.objects.filter(activo=True).order_by('orden', 'id'),
            'modelo_extraccion': ModeloIAConfig.objects.filter(activo=True, usar_para_extraccion=True).first(),
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

from .models import CredencialesGoogle
@admin.register(CredencialesGoogle)
class CredencialesGoogleAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'foto_perfil')
    search_fields = ('usuario__username', 'usuario__email')
    readonly_fields = ('token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes', 'foto_perfil')


@admin.register(CopiaSeguridad)
class CopiaSeguridadAdmin(admin.ModelAdmin):
    change_list_template = 'admin/plan_de_estudio/copiaseguridad/change_list.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'modelos_ia': ModeloIAConfig.objects.all().order_by('orden', 'id'),
            'modelos_docentes': ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by('orden', 'id'),
            'modelo_extraccion': ModeloIAConfig.objects.filter(activo=True, usar_para_extraccion=True).first(),
            'proveedores_ia': ModeloIAConfig.PROVEEDOR_CHOICES,
        })
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('backup-db/', self.admin_site.admin_view(self.backup_db_view), name='plan_de_estudio_copiaseguridad_backup_db'),
            path('descargar-backup/', self.admin_site.admin_view(self.descargar_backup_view), name='plan_de_estudio_copiaseguridad_descargar_backup'),
            path('ver-guia/', self.admin_site.admin_view(self.ver_guia_view), name='plan_de_estudio_copiaseguridad_ver_guia'),
            path('consultar-modelos-ia/', self.admin_site.admin_view(self.consultar_modelos_ia_view), name='plan_de_estudio_copiaseguridad_consultar_modelos_ia'),
            path('guardar-modelo-ia/', self.admin_site.admin_view(self.guardar_modelo_ia_view), name='plan_de_estudio_copiaseguridad_guardar_modelo_ia'),
            path('accion-modelo-ia/<int:modelo_id>/', self.admin_site.admin_view(self.accion_modelo_ia_view), name='plan_de_estudio_copiaseguridad_accion_modelo_ia'),
            path('configurar-extraccion-2026/', self.admin_site.admin_view(self.configurar_extraccion_2026_view), name='plan_de_estudio_copiaseguridad_configurar_extraccion_2026'),
        ]
        return custom_urls + urls

    def consultar_modelos_ia_view(self, request):
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
        if not self.has_view_permission(request):
            return JsonResponse({'success': False, 'error': 'Sin permisos suficientes'}, status=403)
        try:
            if request.content_type and 'application/json' in request.content_type:
                payload = json.loads(request.body or '{}')
            else:
                payload = request.POST
            proveedor = (payload.get('proveedor') or '').strip()
            api_key = (payload.get('api_key') or '').strip()
            if not proveedor:
                return JsonResponse({'success': False, 'error': 'Seleccione un proveedor de IA.'}, status=400)
            modelos = listar_modelos_disponibles(proveedor, api_key)
            return JsonResponse({'success': True, 'modelos': modelos})
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error consultando modelos de IA: {e}")
            return JsonResponse({'success': False, 'error': f'No se pudieron obtener los modelos: {str(e)}'}, status=400)

    def guardar_modelo_ia_view(self, request):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        proveedor = (request.POST.get('proveedor') or '').strip()
        api_key = (request.POST.get('api_key') or '').strip()
        modelo_id = (request.POST.get('modelo_id') or '').strip()
        modelo_id_custom = (request.POST.get('modelo_id_custom') or '').strip()
        nombre_mostrar = (request.POST.get('nombre_mostrar') or '').strip()
        disponible_docentes = request.POST.get('disponible_docentes') == 'on'
        usar_para_extraccion = request.POST.get('usar_para_extraccion') == 'on'

        if modelo_id == '__custom__':
            modelo_id = modelo_id_custom

        valid_proveedores = {code for code, _ in ModeloIAConfig.PROVEEDOR_CHOICES}
        if proveedor not in valid_proveedores:
            self.message_user(request, "Seleccione un proveedor de IA válido.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        if not api_key:
            self.message_user(request, "Debe ingresar la Key de IA.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        if not modelo_id:
            self.message_user(request, "Debe seleccionar o escribir un modelo de IA.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        modelo_obj = ModeloIAConfig.objects.create(
            proveedor=proveedor,
            api_key=api_key,
            modelo_id=modelo_id,
            nombre_mostrar=nombre_mostrar,
            disponible_docentes=disponible_docentes,
            usar_para_extraccion=usar_para_extraccion,
            activo=True,
        )
        self.message_user(
            request,
            f"Modelo '{modelo_obj.nombre_mostrar}' guardado correctamente.",
            level=messages.SUCCESS
        )
        return HttpResponseRedirect(changelist_url)

    def accion_modelo_ia_view(self, request, modelo_id):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        modelo = get_object_or_404(ModeloIAConfig, pk=modelo_id)
        accion = request.POST.get('accion')

        if accion == 'toggle_docentes':
            modelo.disponible_docentes = not modelo.disponible_docentes
            modelo.save()
            estado = "visible" if modelo.disponible_docentes else "oculto"
            self.message_user(request, f"El modelo '{modelo.nombre_mostrar}' ahora está {estado} para docentes.", level=messages.SUCCESS)
        elif accion == 'set_extraccion':
            modelo.activo = True
            modelo.usar_para_extraccion = True
            modelo.save()
            self.message_user(request, f"'{modelo.nombre_mostrar}' establecido para extraer texto en Programas de asignatura 2026.", level=messages.SUCCESS)
        elif accion == 'toggle_activo':
            modelo.activo = not modelo.activo
            modelo.save()
            estado = "activado" if modelo.activo else "desactivado"
            self.message_user(request, f"Modelo '{modelo.nombre_mostrar}' {estado}.", level=messages.SUCCESS)
        elif accion == 'eliminar':
            nombre = modelo.nombre_mostrar
            modelo.delete()
            self.message_user(request, f"Modelo '{nombre}' eliminado.", level=messages.SUCCESS)

        return HttpResponseRedirect(changelist_url)

    def configurar_extraccion_2026_view(self, request):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        modelo_extraccion_id = (request.POST.get('modelo_extraccion_id') or '').strip()
        if modelo_extraccion_id == 'env_default' or not modelo_extraccion_id:
            ModeloIAConfig.objects.filter(usar_para_extraccion=True).update(usar_para_extraccion=False)
            self.message_user(request, "Programas de asignatura 2026 usará el modelo predeterminado del entorno (.env - Gemini).", level=messages.SUCCESS)
        else:
            modelo = get_object_or_404(ModeloIAConfig, pk=modelo_extraccion_id)
            modelo.activo = True
            modelo.usar_para_extraccion = True
            modelo.save()
            self.message_user(request, f"Modelo de extracción para Programas 2026 actualizado a '{modelo.nombre_mostrar}'.", level=messages.SUCCESS)

        return HttpResponseRedirect(changelist_url)

    def backup_db_view(self, request):
        from .utils.db_backup import run_backup
        try:
            filepath, filename, _ = run_backup(send_email=False)
            msg = f"Copia de seguridad creada y guardada en MinIO correctamente: {filename}."
            self.message_user(request, msg, level=messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Error al generar la copia de seguridad: {str(e)}", level=messages.ERROR)
        return HttpResponseRedirect("../")

    def descargar_backup_view(self, request):
        from .utils.db_backup import run_backup
        from django.http import FileResponse
        try:
            filepath, filename, _ = run_backup(send_email=False)
            response = FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)
            return response
        except Exception as e:
            self.message_user(request, f"Error al descargar la copia de seguridad: {str(e)}", level=messages.ERROR)
            return HttpResponseRedirect("../")

    def ver_guia_view(self, request):
        return render(request, 'admin/plan_de_estudio/copiaseguridad/guia_backup.html', {
            **self.admin_site.each_context(request),
            'title': 'Guía de Restauración de Base de Datos',
        })


