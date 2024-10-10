from django.contrib import admin
from .models import Plan_de_estudio, Asignatura, Carrera, Silabo, Estudio_independiente, AsignacionPlanEstudio
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django import forms
from django.contrib.admin.filters import DateFieldListFilter
from django.forms import DateInput

admin.site.site_header = 'MAESTROS DEL FUTURO'
admin.site.index_title = 'Bienbenidos al Panel de control del sitio'
admin.site.site_title = 'ADMIN'


class FiltrarClases(admin.ModelAdmin):
    list_per_page = 20
    search_fields = ('nombre',)

class FiltarPlanDeEstudio(admin.ModelAdmin):
    list_per_page = 20
    list_display = ('carrera', 'año', 'trimestre','asignatura','pr','th')
    list_filter = ('carrera', 'año','trimestre')

class AsignaturaFilter(admin.SimpleListFilter):
    title = _('Asignatura')
    parameter_name = 'asignatura'

    def lookups(self, request, model_admin):
        # Obtener una lista de asignaturas únicas en los silabos
        asignaturas = Silabo.objects.values_list('asignatura__id', 'asignatura__nombre').distinct()
        return [(asignatura[0], asignatura[1]) for asignatura in asignaturas]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(asignatura__id=value)
        return queryset


class FiltarSilabo(admin.ModelAdmin):
    list_display = ('maestro', 'asignatura',)
    list_filter = (
        ('maestro', admin.RelatedOnlyFieldListFilter),
        ('asignatura', admin.RelatedOnlyFieldListFilter),
        ('codigo', admin.AllValuesFieldListFilter),
        ('fecha', admin.DateFieldListFilter),  # Utiliza el widget de fecha aquí
    )

    exclude = ('maestro',)  # Excluir el campo maestro del formulario
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'encuentros':
            kwargs['widget'] = forms.NumberInput(attrs={'min': '1', 'max': '10', 'step': '1'})
            kwargs['validators'] = [MinValueValidator(1), MaxValueValidator(10)]
        elif db_field.name == 'fecha':
            # Utiliza el widget de calendario AdminDateWidget para el campo de fecha.
            kwargs['widget'] = DateInput(attrs={'type': 'date'})
        return super().formfield_for_dbfield(db_field, **kwargs)



    def save_model(self, request, obj, form, change):
        # Establecer el maestro como el usuario que está logueado actualmente
        if not obj.maestro_id:
            obj.maestro = request.user
        obj.save()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Filtrar los silabos por el maestro que está logueado
        if request.user.is_superuser:
            return queryset
        else:
            return queryset.filter(maestro=request.user)

class FiltrarEstudioIndependiente(admin.ModelAdmin):
      list_filter = ('asignatura',)

class AsignacionPlanEstudioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plan_de_estudio', 'completado')




admin.site.register(Plan_de_estudio, FiltarPlanDeEstudio)
admin.site.register(Asignatura, FiltrarClases)
admin.site.register(Carrera)
admin.site.register(Silabo, FiltarSilabo)
admin.site.register(Estudio_independiente,FiltrarEstudioIndependiente)
admin.site.register(AsignacionPlanEstudio, AsignacionPlanEstudioAdmin)