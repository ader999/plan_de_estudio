from django.contrib import admin
from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion

class CriterioInline(admin.TabularInline):
    model = CriterioEvaluacion
    extra = 1

class ParticipanteInline(admin.TabularInline):
    model = Participante
    extra = 1

class JuradoInline(admin.TabularInline):
    model = JuradoEvento
    extra = 1

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin', 'requiere_jurado', 'creado_por')
    list_filter = ('requiere_jurado', 'fecha_inicio', 'fecha_fin')
    search_fields = ('nombre', 'descripcion')
    inlines = [CriterioInline, ParticipanteInline, JuradoInline]

@admin.register(CriterioEvaluacion)
class CriterioEvaluacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'evento', 'puntaje_maximo')
    list_filter = ('evento',)
    search_fields = ('nombre', 'descripcion')

@admin.register(JuradoEvento)
class JuradoEventoAdmin(admin.ModelAdmin):
    list_display = ('evento', 'usuario')
    list_filter = ('evento', 'usuario')

@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'evento')
    list_filter = ('evento',)
    search_fields = ('nombre', 'descripcion', 'integrantes')

@admin.register(Evaluacion)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ('jurado', 'participante', 'criterio', 'puntaje', 'evaluado_en')
    list_filter = ('criterio__evento', 'jurado', 'criterio')
    search_fields = ('participante__nombre', 'jurado__username')
