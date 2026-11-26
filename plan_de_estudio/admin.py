from django.contrib import admin
from .models import (
    Plan_de_estudio, Asignatura, Carrera, Silabo, Guia, ProyectoExamen,
    AsignacionPlanEstudio, PlanTematico, ProgramaAsignatura2026,
    CopiaSeguridad, ModeloIAConfig, ProveedorIA, ConfiguracionSistema,
    TOTAL_ENCUENTROS_SILABO, TOTAL_EXAMENES, obtener_max_encuentros_guia,
)
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django import forms
from django.contrib.admin import DateFieldListFilter, RelatedFieldListFilter, AllValuesFieldListFilter
from django.forms import DateInput
from import_export.admin import ExportMixin
from import_export import resources
from django.utils.html import format_html, format_html_join
from django.db.models import Count, Prefetch, Q, TextField
from django.contrib.auth.models import User
from .document_generators import generar_excel_admin
from django.urls import path, reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from .email_utils import enviar_correos_plan_incompleto
from django.shortcuts import render, redirect, get_object_or_404
from .utils.gemini_parser import parse_curriculum_with_ai
from .ai_generators import listar_modelos_disponibles
from .forms import AsignacionPlanEstudioAdminForm
from .trimestre_utils import (
    formatear_trimestre_lectivo,
    obtener_rango_por_trimestre_lectivo,
    ordenar_codigos_trimestre_lectivo,
)
import json
import logging
import os
from django.http import FileResponse, Http404, JsonResponse, HttpResponseForbidden

logger = logging.getLogger(__name__)


def _text_field_names(model):
    """Devuelve los nombres de campos TextField concretos de un modelo para diferirlos en changelists."""
    return tuple(
        field.name
        for field in model._meta.concrete_fields
        if isinstance(field, TextField)
    )


def _is_changelist_get(request, url_name):
    """Indica si la petición actual corresponde a un GET del changelist indicado."""
    resolved = getattr(request, 'resolver_match', None)
    return (
        request.method == 'GET'
        and resolved is not None
        and resolved.url_name == url_name
    )


class PlanEstudioRelatedFilter(RelatedFieldListFilter):
    """Evita consultas N+1 al renderizar opciones de Plan_de_estudio en el filtro lateral del admin."""

    def field_choices(self, field, request, model_admin):
        ordering = self.field_admin_ordering(field, request, model_admin)
        qs = field.related_model._default_manager.select_related('asignatura', 'carrera')
        if ordering:
            qs = qs.order_by(*ordering)
        return [(obj.pk, str(obj)) for obj in qs]

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

    list_per_page = 30  # Mostrar 30 elementos seguidos por página
    list_display = ('carrera', 'pensol', 'año', 'trimestre', 'asignatura', 'pr', 'descargas_documentos')  # Mostrar los campos
    list_filter = (CarreraFilter, 'pensol', 'año', 'trimestre')  # Filtros en el panel de administración, incluyendo 'carrera'
    autocomplete_fields = ['asignatura', 'pr', 'pc', 'cr']
    search_fields = ('asignatura__nombre', 'codigo', 'carrera__nombre', 'pensol')  # Para permitir búsqueda en autocomplete
    resource_class = PlanDeEstudioResource

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('carrera', 'asignatura', 'pr')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:plan_id>/descargar/<str:tipo>/',
                self.admin_site.admin_view(self.descargar_documento_view),
                name='plan_de_estudio_plan_de_estudio_descargar_documento',
            ),
        ]
        return custom_urls + urls

    @admin.display(description='Descargas')
    def descargas_documentos(self, obj):
        botones = []
        base_style = (
            'display:inline-flex; align-items:center; gap:4px; '
            'padding:4px 8px; font-weight:600; white-space:nowrap; text-decoration:none;'
        )
        if obj.plan_tematico and obj.plan_tematico.name:
            url_plan = reverse(
                'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                args=[obj.pk, 'plan_tematico'],
            )
            botones.append((
                url_plan,
                f"Descargar Plan temático: {os.path.basename(obj.plan_tematico.name)}",
                base_style,
                '↓ Plan temático',
            ))
        if obj.documento_adjunto and obj.documento_adjunto.name:
            url_adjunto = reverse(
                'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                args=[obj.pk, 'documento_adjunto'],
            )
            botones.append((
                url_adjunto,
                f"Descargar Documento adjunto: {os.path.basename(obj.documento_adjunto.name)}",
                f"{base_style} background:#198754; color:#ffffff; border-color:#198754;",
                '↓ Doc. adjunto',
            ))
        if not botones:
            return format_html('<span style="color: var(--body-quiet-color, #888);">—</span>')
        enlaces = format_html_join(
            '',
            '<a class="button" href="{}" title="{}" style="{}">{}</a>',
            botones,
        )
        return format_html(
            '<div style="display:inline-flex; flex-wrap:wrap; gap:6px; align-items:center;">{}</div>',
            enlaces,
        )

    def descargar_documento_view(self, request, plan_id, tipo):
        if tipo not in ('plan_tematico', 'documento_adjunto'):
            raise Http404("Tipo de documento no válido.")
        plan = get_object_or_404(Plan_de_estudio, pk=plan_id)
        if not self.has_view_permission(request, plan):
            return HttpResponseForbidden()

        changelist_url = reverse('admin:plan_de_estudio_plan_de_estudio_changelist')
        archivo = getattr(plan, tipo, None)
        if not archivo or not archivo.name:
            etiqueta = 'plan temático' if tipo == 'plan_tematico' else 'documento adjunto'
            self.message_user(
                request,
                f"El plan de estudio '{plan}' no tiene un {etiqueta} cargado.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(changelist_url)

        nombre_archivo = os.path.basename(archivo.name)
        try:
            file_handle = archivo.open('rb')
            # Fuerza la apertura del archivo subyacente para capturar faltantes antes de responder.
            getattr(file_handle, 'file', None)
        except Exception as exc:
            logger.warning(
                "No se pudo descargar %s del Plan_de_estudio %s (%s): %s",
                tipo, plan.pk, archivo.name, exc,
            )
            self.message_user(
                request,
                f"No se pudo descargar el archivo '{nombre_archivo}'. Verifique que exista en el almacenamiento.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(changelist_url)

        return FileResponse(file_handle, as_attachment=True, filename=nombre_archivo)

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
    list_select_related = (
        'asignacion_plan',
        'asignacion_plan__usuario',
        'asignacion_plan__plan_de_estudio',
        'asignacion_plan__plan_de_estudio__asignatura',
        'asignacion_plan__plan_de_estudio__carrera',
    )
    list_filter = (
        ('fecha', DateFieldListFilter),  # Utiliza el widget de fecha aquí
        ('asignacion_plan__plan_de_estudio__asignatura__nombre', admin.AllValuesFieldListFilter),  # Filtro por nombre de asignatura
        UsuarioConSilabosFilter,  # Filtro personalizado para usuarios con sílabos
        ('asignacion_plan__plan_de_estudio', PlanEstudioRelatedFilter),  # Filtro para la asignación
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
        qs = super().get_queryset(request).select_related(*self.list_select_related)
        # Filtra solo los usuarios que tienen sílabos creados
        return qs.filter(asignacion_plan__usuario__in=Silabo.objects.values('asignacion_plan__usuario').distinct())


class FiltrarGuia(admin.ModelAdmin):
    list_filter = ('silabo__codigo',)
    list_per_page = 20
    list_select_related = ('silabo',)
    readonly_fields = ('silabo', 'numero_encuentro', 'fecha')  # Campos que solo serán de lectura

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class TrimestreLectivoFilter(admin.SimpleListFilter):
    """Permite filtrar asignaciones por su trimestre lectivo exacto."""
    title = 'Trimestre lectivo'
    parameter_name = 'trimestre_lectivo'

    def lookups(self, request, model_admin):
        codigos = ordenar_codigos_trimestre_lectivo(
            AsignacionPlanEstudio.objects.values_list('trimestre_lectivo', flat=True).distinct(),
            descendente=True,
        )
        return [
            (codigo, formatear_trimestre_lectivo(codigo, detallado=True))
            for codigo in codigos
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(trimestre_lectivo=self.value())
        return queryset


class AsignacionPlanEstudioAdmin(admin.ModelAdmin):
    form = AsignacionPlanEstudioAdminForm
    change_list_template = 'admin/plan_de_estudio/asignacionplanestudio/change_list.html'
    fields = (
        'usuario',
        'plan_de_estudio',
        'trimestre_lectivo',
        'bloque',
        'fecha_asignacion',
        'silabos_creados',
        'guias_creadas',
        'examenes_creados',
        'curso_classroom_id',
        'curso_classroom_url',
    )
    # Añade 'exportar_excel_boton' a list_display
    list_display = ('usuario', 'plan_de_estudio', 'trimestre_lectivo_display', 'bloque', 'fecha_asignacion', 'progreso_silabos_guias', 'completado_icono', 'exportar_excel_boton')
    list_per_page = 20
    list_select_related = (
        'usuario',
        'plan_de_estudio',
        'plan_de_estudio__asignatura',
        'plan_de_estudio__carrera',
    )
    readonly_fields = ('fecha_asignacion', 'silabos_creados', 'guias_creadas', 'examenes_creados', 'curso_classroom_id', 'curso_classroom_url')
    autocomplete_fields = ['plan_de_estudio', 'usuario'] # Habilita buscador dinámico
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name') # Habilita buscador por usuario
    search_help_text = "Busque por nombre de usuario, nombre o apellido"
    list_filter = (TrimestreLectivoFilter, 'plan_de_estudio__carrera', 'plan_de_estudio__pensol', 'plan_de_estudio__año', 'plan_de_estudio__trimestre', 'bloque') # Añadir filtros útiles

    def get_queryset(self, request):
        self._max_guias_cache = obtener_max_encuentros_guia()
        return super().get_queryset(request).select_related(*self.list_select_related)

    @admin.display(description='Trimestre lectivo', ordering='trimestre_lectivo')
    def trimestre_lectivo_display(self, obj):
        return obj.trimestre_lectivo_display

    def _get_max_guias(self):
        max_guias = getattr(self, '_max_guias_cache', None)
        return max_guias if max_guias is not None else obtener_max_encuentros_guia()

    def completado_icono(self, obj):
        return (
            obj.silabos_creados >= TOTAL_ENCUENTROS_SILABO
            and obj.guias_creadas >= self._get_max_guias()
            and obj.examenes_creados >= TOTAL_EXAMENES
        )
    completado_icono.boolean = True
    completado_icono.short_description = 'Completado'

    def progreso_silabos_guias(self, obj):
        return f"S:{obj.silabos_creados}/{TOTAL_ENCUENTROS_SILABO}, G:{obj.guias_creadas}/{self._get_max_guias()}, E:{obj.examenes_creados}/{TOTAL_EXAMENES}"
    progreso_silabos_guias.short_description = 'Progreso (S/G/E)'

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
                trimestre_lectivo = form.cleaned_data.get('trimestre_lectivo')
                trimestre = form.cleaned_data['trimestre']
                carreras = form.cleaned_data['carreras']
                años = form.cleaned_data['años']

                if trimestre_lectivo:
                    fecha_inicio = obtener_rango_por_trimestre_lectivo(trimestre_lectivo)[0]
                else:
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
                )
                if trimestre_lectivo:
                    queryset = queryset.filter(trimestre_lectivo=trimestre_lectivo)
                queryset = queryset.select_related('plan_de_estudio__carrera', 'plan_de_estudio__asignatura', 'usuario') \
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
    list_select_related = ('plan_estudio', 'plan_estudio__asignatura', 'plan_estudio__carrera')
    _CHANGELIST_DEFERRED_FIELDS = _text_field_names(PlanTematico)

    def has_add_permission(self, request):
        return False

    def unidades_completadas_count(self, obj):
        return obj.get_numero_unidades_completadas()
    unidades_completadas_count.short_description = 'Unidades Llenadas'

    def completado_icono(self, obj):
        # Verificamos si este PlanTematico está relacionado con algún Plan_de_estudio
        planes = getattr(obj, '_prefetched_planes_de_estudio', None)
        if planes is not None:
            return bool(planes)
        return Plan_de_estudio.objects.filter(plan_tematico_ref=obj).exists()

    completado_icono.boolean = True  # Indica que este es un campo booleano
    completado_icono.short_description = 'Asignado'

    def planes_de_estudio_related(self, obj):
        # Obtener todos los planes de estudio que referencian a este PlanTematico
        planes = getattr(obj, '_prefetched_planes_de_estudio', None)
        if planes is None:
            planes = list(
                Plan_de_estudio.objects.filter(plan_tematico_ref=obj).select_related('asignatura', 'carrera')
            )
        if planes:
            return ", ".join([str(plan) for plan in planes])
        return "No asignado"

    planes_de_estudio_related.short_description = "Plan de Estudio"

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(*self.list_select_related)
        if _is_changelist_get(request, 'plan_de_estudio_plantematico_changelist'):
            qs = qs.defer(*self._CHANGELIST_DEFERRED_FIELDS).prefetch_related(
                Prefetch(
                    'planes_de_estudio',
                    queryset=Plan_de_estudio.objects.select_related('asignatura', 'carrera'),
                    to_attr='_prefetched_planes_de_estudio',
                )
            )
        return qs


class Programa2026CarreraFilter(admin.SimpleListFilter):
    title = 'Carrera'
    parameter_name = 'carrera'

    def lookups(self, request, model_admin):
        return list(Carrera.objects.order_by('nombre').values_list('id', 'nombre'))

    def queryset(self, request, queryset):
        if self.value():
            try:
                carrera_id = int(self.value())
            except (TypeError, ValueError):
                return queryset.none()
            return queryset.filter(plan_estudio__carrera_id=carrera_id)
        return queryset


class Programa2026PlanAsociadoFilter(admin.SimpleListFilter):
    title = 'Estado de asociación'
    parameter_name = 'plan_asociado'

    def lookups(self, request, model_admin):
        return (
            ('si', 'Con plan de estudio'),
            ('no', 'Sin plan de estudio'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'si':
            return queryset.filter(plan_estudio__isnull=False)
        if self.value() == 'no':
            return queryset.filter(plan_estudio__isnull=True)
        return queryset


class ProgramaAsignatura2026Admin(admin.ModelAdmin):
    list_display = ('plan_estudio',)
    list_filter = (
        Programa2026CarreraFilter,
        'plan_estudio__pensol',
        'plan_estudio__año',
        'plan_estudio__trimestre',
        Programa2026PlanAsociadoFilter,
    )
    list_per_page = 20
    list_select_related = ('plan_estudio', 'plan_estudio__asignatura', 'plan_estudio__carrera')
    search_fields = (
        'plan_estudio__codigo',
        'plan_estudio__asignatura__nombre',
        'plan_estudio__carrera__nombre',
        'plan_estudio__pensol',
    )
    autocomplete_fields = ['plan_estudio']
    _CHANGELIST_DEFERRED_FIELDS = tuple(
        field.name
        for field in ProgramaAsignatura2026._meta.concrete_fields
        if field.name not in ('id', 'plan_estudio')
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related(*self.list_select_related)
        if _is_changelist_get(request, 'plan_de_estudio_programaasignatura2026_changelist'):
            qs = qs.defer(*self._CHANGELIST_DEFERRED_FIELDS)
        return qs
    
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
            'config_sistema': ConfiguracionSistema.get_solo(),
            'modelos_ia': ModeloIAConfig.objects.select_related('proveedor_custom').all().order_by('orden', 'id'),
            'modelos_docentes': ModeloIAConfig.objects.filter(activo=True, disponible_docentes=True).order_by('orden', 'id'),
            'modelo_extraccion': ModeloIAConfig.objects.filter(activo=True, usar_para_extraccion=True).first(),
            'proveedores_ia': [c for c in ModeloIAConfig.PROVEEDOR_CHOICES if c[0] != 'custom'],
            'proveedores_custom': ProveedorIA.objects.all().order_by('nombre'),
            'formatos_api': ProveedorIA.FORMATO_API_CHOICES,
        })
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('backup-db/', self.admin_site.admin_view(self.backup_db_view), name='plan_de_estudio_copiaseguridad_backup_db'),
            path('descargar-backup/', self.admin_site.admin_view(self.descargar_backup_view), name='plan_de_estudio_copiaseguridad_descargar_backup'),
            path('ver-guia/', self.admin_site.admin_view(self.ver_guia_view), name='plan_de_estudio_copiaseguridad_ver_guia'),
            path('toggle-descarga-plan-tematico/', self.admin_site.admin_view(self.toggle_descarga_plan_tematico_view), name='plan_de_estudio_copiaseguridad_toggle_descarga_plan_tematico'),
            path('toggle-ranking-docentes/', self.admin_site.admin_view(self.toggle_ranking_docentes_view), name='plan_de_estudio_copiaseguridad_toggle_ranking_docentes'),
            path('toggle-ultimo-encuentro-guia/', self.admin_site.admin_view(self.toggle_ultimo_encuentro_guia_view), name='plan_de_estudio_copiaseguridad_toggle_ultimo_encuentro_guia'),
            path('guardar-proveedor-ia/', self.admin_site.admin_view(self.guardar_proveedor_ia_view), name='plan_de_estudio_copiaseguridad_guardar_proveedor_ia'),
            path('eliminar-proveedor-ia/<int:proveedor_id>/', self.admin_site.admin_view(self.eliminar_proveedor_ia_view), name='plan_de_estudio_copiaseguridad_eliminar_proveedor_ia'),
            path('consultar-modelos-ia/', self.admin_site.admin_view(self.consultar_modelos_ia_view), name='plan_de_estudio_copiaseguridad_consultar_modelos_ia'),
            path('guardar-modelo-ia/', self.admin_site.admin_view(self.guardar_modelo_ia_view), name='plan_de_estudio_copiaseguridad_guardar_modelo_ia'),
            path('accion-modelo-ia/<int:modelo_id>/', self.admin_site.admin_view(self.accion_modelo_ia_view), name='plan_de_estudio_copiaseguridad_accion_modelo_ia'),
            path('configurar-extraccion-2026/', self.admin_site.admin_view(self.configurar_extraccion_2026_view), name='plan_de_estudio_copiaseguridad_configurar_extraccion_2026'),
        ]
        return custom_urls + urls

    def _toggle_config_boolean(self, request, field_name, msg_habilitado, msg_deshabilitado):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        config = ConfiguracionSistema.get_solo()
        accion = (request.POST.get('accion') or '').strip()
        if accion == 'activar':
            nuevo_valor = True
        elif accion == 'desactivar':
            nuevo_valor = False
        else:
            nuevo_valor = not getattr(config, field_name)
        setattr(config, field_name, nuevo_valor)
        config.save()

        self.message_user(
            request,
            msg_habilitado if nuevo_valor else msg_deshabilitado,
            level=messages.SUCCESS
        )
        return HttpResponseRedirect(changelist_url)

    def toggle_descarga_plan_tematico_view(self, request):
        """Habilita o desactiva la visualización y descarga de planes temáticos para docentes."""
        return self._toggle_config_boolean(
            request,
            'permitir_descarga_plan_tematico',
            "La descarga de planes temáticos por parte de los docentes ha sido habilitada.",
            "La descarga de planes temáticos por parte de los docentes ha sido desactivada.",
        )

    def toggle_ranking_docentes_view(self, request):
        """Habilita o restringe la visibilidad del Ranking Docente para usuarios no administradores."""
        return self._toggle_config_boolean(
            request,
            'mostrar_ranking_docentes',
            "El Ranking de Cumplimiento Docente ahora es visible para todos los usuarios con sesión iniciada.",
            "El Ranking de Cumplimiento Docente ha sido restringido únicamente a administradores.",
        )

    def toggle_ultimo_encuentro_guia_view(self, request):
        """Habilita o desactiva el último encuentro (Encuentro 11) de la Guía de Estudio Independiente."""
        return self._toggle_config_boolean(
            request,
            'habilitar_ultimo_encuentro_guia',
            "La guía del último encuentro (Encuentro 11) ha sido restaurada (11 sílabos y 11 guías requeridas).",
            "La guía del último encuentro (Encuentro 11) ha sido desactivada (11 sílabos y 10 guías requeridas).",
        )

    def guardar_proveedor_ia_view(self, request):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        nombre = (request.POST.get('nombre_proveedor') or '').strip()
        formato_api = (request.POST.get('formato_api') or 'openai_compatible').strip()
        base_url = (request.POST.get('base_url') or '').strip()

        if not nombre:
            self.message_user(request, "Debe ingresar el nombre del proveedor.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        valid_formatos = {code for code, _ in ProveedorIA.FORMATO_API_CHOICES}
        if formato_api not in valid_formatos:
            self.message_user(request, "Seleccione un formato de API válido.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        if formato_api == 'openai_compatible' and not base_url:
            self.message_user(request, "Debe ingresar la URL Base de la API para proveedores compatibles con OpenAI.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        if ProveedorIA.objects.filter(nombre__iexact=nombre).exists():
            self.message_user(request, f"Ya existe un proveedor llamado '{nombre}'.", level=messages.ERROR)
            return HttpResponseRedirect(changelist_url)

        prov = ProveedorIA.objects.create(
            nombre=nombre,
            formato_api=formato_api,
            base_url=base_url,
        )
        self.message_user(request, f"Proveedor '{prov.nombre}' agregado correctamente. Ahora puede seleccionarlo en el formulario de modelos.", level=messages.SUCCESS)
        return HttpResponseRedirect(changelist_url)

    def eliminar_proveedor_ia_view(self, request, proveedor_id):
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        if request.method != 'POST':
            return HttpResponseRedirect(changelist_url)
        if not self.has_view_permission(request):
            return HttpResponseForbidden()

        prov = get_object_or_404(ProveedorIA, pk=proveedor_id)
        nombre = prov.nombre
        prov.delete()
        self.message_user(request, f"Proveedor '{nombre}' eliminado.", level=messages.SUCCESS)
        return HttpResponseRedirect(changelist_url)

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
            if not proveedor or proveedor == '__new_provider__':
                return JsonResponse({'success': False, 'error': 'Seleccione un proveedor de IA.'}, status=400)

            base_url = None
            formato_api = None
            if proveedor.startswith('custom:'):
                prov_id = proveedor.split(':', 1)[1]
                if not prov_id.isdigit():
                    return JsonResponse({'success': False, 'error': 'Proveedor personalizado inválido.'}, status=400)
                prov_obj = ProveedorIA.objects.filter(pk=int(prov_id)).first()
                if not prov_obj:
                    return JsonResponse({'success': False, 'error': 'El proveedor personalizado no existe.'}, status=404)
                proveedor = 'custom'
                base_url = prov_obj.base_url_normalizada
                formato_api = prov_obj.formato_api

            modelos = listar_modelos_disponibles(proveedor, api_key, base_url=base_url, formato_api=formato_api)
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

        proveedor_raw = (request.POST.get('proveedor') or '').strip()
        api_key = (request.POST.get('api_key') or '').strip()
        modelo_id = (request.POST.get('modelo_id') or '').strip()
        modelo_id_custom = (request.POST.get('modelo_id_custom') or '').strip()
        nombre_mostrar = (request.POST.get('nombre_mostrar') or '').strip()
        disponible_docentes = request.POST.get('disponible_docentes') == 'on'
        usar_para_extraccion = request.POST.get('usar_para_extraccion') == 'on'

        if modelo_id == '__custom__':
            modelo_id = modelo_id_custom

        proveedor = proveedor_raw
        proveedor_custom = None
        if proveedor_raw.startswith('custom:'):
            prov_id = proveedor_raw.split(':', 1)[1]
            if not prov_id.isdigit():
                self.message_user(request, "Proveedor personalizado inválido.", level=messages.ERROR)
                return HttpResponseRedirect(changelist_url)
            proveedor_custom = ProveedorIA.objects.filter(pk=int(prov_id)).first()
            if not proveedor_custom:
                self.message_user(request, "El proveedor personalizado seleccionado no existe.", level=messages.ERROR)
                return HttpResponseRedirect(changelist_url)
            proveedor = 'custom'
        else:
            valid_proveedores = {code for code, _ in ModeloIAConfig.PROVEEDOR_CHOICES if code != 'custom'}
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
            proveedor_custom=proveedor_custom,
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


@admin.register(ProyectoExamen)
class ProyectoExamenAdmin(admin.ModelAdmin):
    list_display = (
        'asignacion_plan',
        'numero_evaluacion',
        'encuentro',
        'periodo_corte',
        'fecha',
        'puntaje_total',
        'paginas_estimadas',
        'acciones_examen',
    )
    list_filter = ('numero_evaluacion', 'periodo_corte', 'modalidad', 'tipo_examen')
    search_fields = (
        'asignacion_plan__usuario__username',
        'asignacion_plan__usuario__first_name',
        'asignacion_plan__usuario__last_name',
        'asignacion_plan__plan_de_estudio__asignatura__nombre',
        'asignacion_plan__plan_de_estudio__codigo',
    )
    list_select_related = (
        'asignacion_plan',
        'asignacion_plan__usuario',
        'asignacion_plan__plan_de_estudio',
        'asignacion_plan__plan_de_estudio__asignatura',
        'asignacion_plan__plan_de_estudio__carrera',
    )
    readonly_fields = ('creado_el', 'actualizado_el', 'paginas_estimadas')

    @admin.display(description='Acciones')
    def acciones_examen(self, obj):
        url_docx = reverse('descargar_proyecto_examen', args=[obj.pk])
        url_student = reverse('descargar_examen_estudiante', args=[obj.pk])
        url_edit = reverse('actualizar_examen', args=[obj.pk])
        return format_html(
            '<div style="display:inline-flex; flex-wrap:wrap; gap:6px; align-items:center;">'
            '<a class="button" href="{}" style="background:#198754; color:#fff; border-color:#198754; padding:4px 8px;" title="Formato oficial Proyecto de Examen UML">↓ Proyecto</a>'
            '<a class="button" href="{}" style="background:#2563eb; color:#fff; border-color:#2563eb; padding:4px 8px;" title="Examen listo para aplicar a los estudiantes">↓ Estudiantes</a>'
            '<a class="button" href="{}" style="padding:4px 8px;">Editar</a>'
            '</div>',
            url_docx,
            url_student,
            url_edit,
        )



