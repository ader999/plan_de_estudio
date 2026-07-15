from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, Sum

class Evento(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Evento")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    fecha_inicio = models.DateTimeField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateTimeField(verbose_name="Fecha de Cierre")
    requiere_jurado = models.BooleanField(default=True, verbose_name="¿Requiere Jurado?")
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name="eventos_creados")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    @property
    def esta_activo(self):
        ahora = timezone.now()
        return self.fecha_inicio <= ahora <= self.fecha_fin

    @property
    def ha_finalizado(self):
        return timezone.now() > self.fecha_fin

    @property
    def total_criterios_score(self):
        return self.criterios.aggregate(total=Sum('puntaje_maximo'))['total'] or 0

    def __str__(self):
        return self.nombre


class CriterioEvaluacion(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="criterios")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Criterio")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    puntaje_maximo = models.PositiveIntegerField(verbose_name="Puntaje Máximo")

    class Meta:
        verbose_name = 'Criterio de Evaluación'
        verbose_name_plural = 'Criterios de Evaluación'

    def __str__(self):
        return f"{self.nombre} ({self.puntaje_maximo} pts) - {self.evento.nombre}"


class JuradoEvento(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="jurados")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jurados_eventos")

    class Meta:
        unique_together = ('evento', 'usuario')
        verbose_name = 'Jurado de Evento'
        verbose_name_plural = 'Jurados de Eventos'

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} - {self.evento.nombre}"


class Participante(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="participantes")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Equipo o Proyecto")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    integrantes = models.TextField(blank=True, verbose_name="Integrantes (nombres separados por comas)")

    class Meta:
        verbose_name = 'Participante'
        verbose_name_plural = 'Participantes'

    def __str__(self):
        return f"{self.nombre} - {self.evento.nombre}"


class Evaluacion(models.Model):
    jurado = models.ForeignKey(User, on_delete=models.CASCADE, related_name="evaluaciones")
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="evaluaciones")
    criterio = models.ForeignKey(CriterioEvaluacion, on_delete=models.CASCADE, related_name="evaluaciones")
    puntaje = models.PositiveIntegerField(verbose_name="Puntaje")
    evaluado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('jurado', 'participante', 'criterio')
        verbose_name = 'Evaluación'
        verbose_name_plural = 'Evaluaciones'

    def __str__(self):
        return f"{self.jurado.username} -> {self.participante.nombre} ({self.criterio.nombre}: {self.puntaje})"
