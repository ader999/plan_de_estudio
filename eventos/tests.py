from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Avg

from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion

class EventoModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testadmin", password="password")
        
    def test_evento_properties(self):
        # Evento en curso/activo
        ahora = timezone.now()
        evento_activo = Evento.objects.create(
            nombre="Evento Activo",
            fecha_inicio=ahora - timedelta(hours=1),
            fecha_fin=ahora + timedelta(hours=1),
            creado_por=self.user
        )
        self.assertTrue(evento_activo.esta_activo)
        self.assertFalse(evento_activo.ha_finalizado)
        
        # Evento futuro (próximo)
        evento_futuro = Evento.objects.create(
            nombre="Evento Futuro",
            fecha_inicio=ahora + timedelta(hours=1),
            fecha_fin=ahora + timedelta(hours=2),
            creado_por=self.user
        )
        self.assertFalse(evento_futuro.esta_activo)
        self.assertFalse(evento_futuro.ha_finalizado)
        
        # Evento pasado (finalizado)
        evento_pasado = Evento.objects.create(
            nombre="Evento Pasado",
            fecha_inicio=ahora - timedelta(hours=2),
            fecha_fin=ahora - timedelta(hours=1),
            creado_por=self.user
        )
        self.assertFalse(evento_pasado.esta_activo)
        self.assertTrue(evento_pasado.ha_finalizado)

    def test_total_criterios_score(self):
        evento = Evento.objects.create(
            nombre="Evento con Criterios",
            fecha_inicio=timezone.now(),
            fecha_fin=timezone.now() + timedelta(days=1),
            creado_por=self.user
        )
        
        self.assertEqual(evento.total_criterios_score, 0)
        
        CriterioEvaluacion.objects.create(
            evento=evento,
            nombre="Creatividad",
            puntaje_maximo=30
        )
        CriterioEvaluacion.objects.create(
            evento=evento,
            nombre="Exposición",
            puntaje_maximo=20
        )
        
        # Debe sumar 50 puntos
        self.assertEqual(evento.total_criterios_score, 50)


class EvaluacionTestCase(TestCase):
    def setUp(self):
        self.creador = User.objects.create_user(username="creador", password="password")
        self.jurado1 = User.objects.create_user(username="jurado1", password="password")
        self.jurado2 = User.objects.create_user(username="jurado2", password="password")
        
        self.evento = Evento.objects.create(
            nombre="Feria de Ciencias",
            fecha_inicio=timezone.now() - timedelta(hours=1),
            fecha_fin=timezone.now() + timedelta(hours=1),
            creado_por=self.creador
        )
        
        self.criterio1 = CriterioEvaluacion.objects.create(
            evento=self.evento,
            nombre="Diseño",
            puntaje_maximo=10
        )
        self.criterio2 = CriterioEvaluacion.objects.create(
            evento=self.evento,
            nombre="Funcionalidad",
            puntaje_maximo=20
        )
        
        # Registrar jurados
        JuradoEvento.objects.create(evento=self.evento, usuario=self.jurado1)
        JuradoEvento.objects.create(evento=self.evento, usuario=self.jurado2)
        
        # Registrar participantes
        self.proyecto = Participante.objects.create(
            evento=self.evento,
            nombre="Robot Limpiador",
            integrantes="Pedro, Lucía"
        )

    def test_evaluacion_y_calculo_resultados(self):
        # Jurado 1 evalúa el proyecto
        Evaluacion.objects.create(
            jurado=self.jurado1,
            participante=self.proyecto,
            criterio=self.criterio1,
            puntaje=8
        )
        Evaluacion.objects.create(
            jurado=self.jurado1,
            participante=self.proyecto,
            criterio=self.criterio2,
            puntaje=15
        )
        # Total jurado 1 = 23 puntos (de 30 posibles)
        
        # Jurado 2 evalúa el proyecto
        Evaluacion.objects.create(
            jurado=self.jurado2,
            participante=self.proyecto,
            criterio=self.criterio1,
            puntaje=9
        )
        Evaluacion.objects.create(
            jurado=self.jurado2,
            participante=self.proyecto,
            criterio=self.criterio2,
            puntaje=18
        )
        # Total jurado 2 = 27 puntos (de 30 posibles)
        
        # Verificar promedio final
        evaluaciones = Evaluacion.objects.filter(participante=self.proyecto)
        self.assertEqual(evaluaciones.count(), 4)
        
        # Cálculo de promedio por jurado
        jurados_evaluadores = evaluaciones.values('jurado').annotate(total_score=Sum('puntaje'))
        self.assertEqual(jurados_evaluadores.count(), 2)
        
        scores = [item['total_score'] for item in jurados_evaluadores]
        self.assertIn(23, scores)
        self.assertIn(27, scores)
        
        promedio = sum(scores) / len(scores)
        self.assertEqual(promedio, 25.0)
