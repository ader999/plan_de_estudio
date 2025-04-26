from django.contrib import admin
from .models import Plan_de_estudio, Asignatura, Carrera, Silabo, Guia, AsignacionPlanEstudio, PlanTematico
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

admin.site.site_header = 'PLANEAUML'
admin.site.index_title = 'Bienbenidos al Panel de control del sitio'
admin.site.site_title = 'ADMIN'


class FiltrarClases(admin.ModelAdmin):
    list_per_page = 20
    search_fields = ('nombre',)

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
    resource_class = PlanDeEstudioResource
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
    list_filter = (
        ('fecha', DateFieldListFilter),  # Utiliza el widget de fecha aquí
        ('asignacion_plan__plan_de_estudio__asignatura__nombre', admin.AllValuesFieldListFilter),  # Filtro por nombre de asignatura
        UsuarioConSilabosFilter,  # Filtro personalizado para usuarios con sílabos
        ('asignacion_plan__plan_de_estudio', RelatedFieldListFilter),  # Filtro para la asignación
    )

    exclude = ()  # No excluir campos innecesarios

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


class AsignacionPlanEstudioAdmin(admin.ModelAdmin):
    # Añade 'exportar_excel_boton' a list_display
    list_display = ('usuario', 'plan_de_estudio','fecha_asignacion', 'completado_icono', 'exportar_excel_boton')
    readonly_fields = ('silabos_creados', 'guias_creadas')
    list_filter = ('plan_de_estudio__carrera', 'plan_de_estudio__año', 'plan_de_estudio__trimestre', 'usuario') # Añadir filtros útiles

    def completado_icono(self, obj):
        # Retorna True si silabos_creados es igual a 12
        # Ajusta el número 12 si el total esperado de sílabos es diferente
        total_esperado = 12 # O obtén esto dinámicamente si es variable
        return obj.silabos_creados >= total_esperado # Usar >= por si acaso
    completado_icono.boolean = True
    completado_icono.short_description = 'Completado'

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
            )
        ]
        # Añade las URLs personalizadas ANTES que las URLs por defecto
        return custom_urls + urls


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
    list_display = ('nombre_de_la_unidad', 'unidades', 'planes_de_estudio_related', 'completado_icono')
    list_filter = (CompletadoFilter,)
    search_fields = ('nombre_de_la_unidad',)

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


admin.site.register(Plan_de_estudio, PlanDeEstudioAdmin)
admin.site.register(Asignatura, FiltrarClases)
admin.site.register(Carrera)
admin.site.register(Silabo, FiltarSilabo)
admin.site.register(Guia, FiltrarGuia)
admin.site.register(AsignacionPlanEstudio, AsignacionPlanEstudioAdmin)
admin.site.register(PlanTematico, PlanTematicoAdmin)
