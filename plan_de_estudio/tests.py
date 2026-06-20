import datetime
import json
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from plan_de_estudio.models import (
    Asignatura, Carrera, Plan_de_estudio, AsignacionPlanEstudio, Silabo, Guia
)
from plan_de_estudio.forms import SilaboForm, ExportarAsignacionesForm


class AsignaturaModelTest(TestCase):
    def test_creacion_asignatura_exitosa(self):
        asignatura = Asignatura(nombre="Matemáticas I")
        asignatura.full_clean()
        asignatura.save()
        self.assertEqual(asignatura.nombre, "Matemáticas I")
        self.assertEqual(str(asignatura), "MATEMÁTICAS I")

    def test_asignatura_nombre_unico_case_insensitive(self):
        Asignatura.objects.create(nombre="Matemáticas I")
        asignatura_duplicada = Asignatura(nombre="matemáticas i")
        with self.assertRaises(ValidationError) as ctx:
            asignatura_duplicada.full_clean()
        self.assertIn('nombre', ctx.exception.message_dict)
        self.assertEqual(
            ctx.exception.message_dict['nombre'][0],
            'La asignatura con este nombre ya existe.'
        )


class PlanDeEstudioModelTest(TestCase):
    def setUp(self):
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas",
            codigo="IS01",
            cine_2011=123,
            cine_2013=456,
            area_formacion="Tecnologías de la información",
            area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Programación I")

    def test_creacion_plan_exitoso(self):
        plan = Plan_de_estudio(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            asignatura=self.asignatura,
            horas_presenciales=45,
            horas_estudio_independiente=30
        )
        plan.full_clean()
        plan.save()
        self.assertEqual(plan.codigo, "PLAN001")
        self.assertEqual(str(plan), f"{self.asignatura.nombre.upper()} - {self.carrera.nombre} - I")

    def test_plan_carrera_obligatoria(self):
        plan = Plan_de_estudio(
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            asignatura=self.asignatura,
            horas_presenciales=45,
            horas_estudio_independiente=30
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn('carrera', ctx.exception.message_dict)

    def test_plan_asignatura_obligatoria(self):
        plan = Plan_de_estudio(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            horas_presenciales=45,
            horas_estudio_independiente=30
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn('asignatura', ctx.exception.message_dict)

    def test_plan_duplicado_mismo_pensol_carrera_asignatura(self):
        Plan_de_estudio.objects.create(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            asignatura=self.asignatura,
            horas_presenciales=45,
            horas_estudio_independiente=30
        )
        plan_duplicado = Plan_de_estudio(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN002",
            asignatura=self.asignatura,
            horas_presenciales=45,
            horas_estudio_independiente=30
        )
        with self.assertRaises(ValidationError) as ctx:
            plan_duplicado.clean()
        self.assertIn(
            "No puedes insertar la misma asignatura en la misma carrera con el mismo Pensol dos veces.",
            ctx.exception.messages
        )

    def test_plan_horas_presenciales_invalida(self):
        plan = Plan_de_estudio(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            asignatura=self.asignatura,
            horas_presenciales=0,
            horas_estudio_independiente=30
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn(
            "Las horas **presenciales** deben ser un número entero mayor que cero y no estar vacías",
            ctx.exception.messages
        )

    def test_plan_horas_independiente_invalida(self):
        plan = Plan_de_estudio(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN001",
            asignatura=self.asignatura,
            horas_presenciales=40,
            horas_estudio_independiente=-5
        )
        with self.assertRaises(ValidationError) as ctx:
            plan.clean()
        self.assertIn(
            "Las horas de estudio independiente deben ser un número entero mayor que cero y no estar vacías",
            ctx.exception.messages
        )


class AsignacionPlanEstudioModelTest(TestCase):
    def setUp(self):
        # Mocking Classroom creation during tests to avoid thread issues
        self.patcher = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.mock_crear = self.patcher.start()

        self.usuario = User.objects.create_user(username="profesor", password="password")
        self.carrera = Carrera.objects.create(
            nombre="Medicina", codigo="MED01", cine_2011=11, cine_2013=22, area_formacion="Salud y servicios sociales ", area_disiplinaria=2
        )
        self.asignatura = Asignatura.objects.create(nombre="Anatomía")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera,
            año="I",
            trimestre="I",
            pensol="2018",
            codigo="PLAN_MED",
            asignatura=self.asignatura,
            horas_presenciales=60,
            horas_estudio_independiente=40
        )

    def tearDown(self):
        self.patcher.stop()

    def test_asignacion_valida(self):
        asignacion = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            bloque="Primer bloque - 8:00"
        )
        asignacion.clean()
        asignacion.save()
        self.assertEqual(str(asignacion), f"{self.usuario} - {self.plan}")

    def test_asignacion_plan_de_estudio_obligatorio(self):
        asignacion = AsignacionPlanEstudio(
            usuario=self.usuario,
            bloque="Primer bloque - 8:00"
        )
        with self.assertRaises(ValidationError) as ctx:
            asignacion.clean()
        self.assertIn('plan_de_estudio', ctx.exception.message_dict)

    def test_asignacion_duplicada_en_trimestre_actual(self):
        AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            bloque="Primer bloque - 8:00"
        )
        
        segunda_asignacion = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            bloque="Segundo bloque - 10:20"
        )
        
        with self.assertRaises(ValidationError) as ctx:
            segunda_asignacion.clean()
            
        self.assertIn(
            "Asignacion plan estudio con este Usuario y Plan de estudio ya existe en el trimestre actual.",
            ctx.exception.messages
        )


class SilaboFormTest(TestCase):
    def setUp(self):
        self.patcher = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.mock_crear = self.patcher.start()

        self.carrera = Carrera.objects.create(
            nombre="Derecho", codigo="DER01", cine_2011=11, cine_2013=22, area_formacion="Administración de empresas y derecho", area_disiplinaria=3
        )
        self.asignatura = Asignatura.objects.create(nombre="Derecho Romano")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="I", trimestre="I", pensol="2018", codigo="PLAN_DER", asignatura=self.asignatura,
            horas_presenciales=45, horas_estudio_independiente=45
        )
        self.usuario = User.objects.create_user(username="maestro_derecho", password="pwd")
        self.asignacion = AsignacionPlanEstudio.objects.create(usuario=self.usuario, plan_de_estudio=self.plan)

        self.form_data_valido = {
            'codigo': 'PLAN_DER',
            'encuentros': 1,
            'fecha': '2026-06-20',
            'unidad': 'Unidad I',
            'nombre_de_la_unidad': 'Introducción al Derecho',
            'contenido_tematico': 'Orígenes del derecho y conceptos básicos.',
            'objetivo_conceptual': 'Comprender los conceptos conceptuales.',
            'objetivo_procedimental': 'Aplicar los procedimientos del derecho.',
            'objetivo_actitudinal': 'Valorar la justicia y la equidad.',
            'tipo_primer_momento': 'Evaluación diagnóstica',
            'detalle_primer_momento': 'Prueba inicial oral.',
            'tiempo_primer_momento': 15,
            'recursos_primer_momento': 'Pizarra y marcadores.',
            'tipo_segundo_momento_claseteoria': 'Conferencia',
            'clase_teorica': 'Explicación del origen histórico.',
            'tipo_segundo_momento_practica': 'Taller',
            'clase_practica': 'Análisis de textos antiguos.',
            'tiempo_segundo_momento_teorica': 45,
            'tiempo_segundo_momento_practica': 45,
            'recursos_segundo_momento': 'Material de lectura.',
            'tipo_tercer_momento': ['Orientación del estudio independiente'],
            'detalle_tercer_momento': 'Lectura complementaria.',
            'tiempo_tercer_momento': 15,
            'recursos_tercer_momento': 'Libro guía.',
            'eje_transversal': ['Cultura de paz'],
            'detalle_eje_transversal': 'Resolver conflictos de forma pacífica.',
            'actividad_aprendizaje': 'Ensayo corto.',
            'tecnica_evaluacion': ['Ensayo'],
            'tipo_evaluacion': ['Formativa'],
            'periodo_tiempo_programado': 'I Corte Evaluativo',
            'tiempo_minutos': 30,
            'agente_evaluador': ['Heteroevaluación'],
            'instrumento_evaluacion': 'Rúbrica',
            'criterios_evaluacion': 'Claridad y argumentación.',
            'puntaje': 10,
            'asignacion_plan': self.asignacion.id,
        }

    def tearDown(self):
        self.patcher.stop()

    def test_silabo_form_valido(self):
        form = SilaboForm(data=self.form_data_valido)
        self.assertTrue(form.is_valid(), form.errors.as_data())

    def test_silabo_form_invalido_encuentros_rango(self):
        data = self.form_data_valido.copy()
        data['encuentros'] = 12
        form = SilaboForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('encuentros', form.errors)

    def test_silabo_form_tiempo_negativo(self):
        data = self.form_data_valido.copy()
        data['tiempo_primer_momento'] = -5
        form = SilaboForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('tiempo_primer_momento', form.errors)


class ExportarAsignacionesFormTest(TestCase):
    def setUp(self):
        self.carrera1 = Carrera.objects.create(
            nombre="Carrera A", codigo="CA01", cine_2011=1, cine_2013=2, area_formacion="Educación", area_disiplinaria=1
        )
        self.carrera2 = Carrera.objects.create(
            nombre="Carrera B", codigo="CB02", cine_2011=3, cine_2013=4, area_formacion="Educación", area_disiplinaria=1
        )

    def test_form_valido(self):
        form = ExportarAsignacionesForm(data={
            'trimestre': 'I',
            'carreras': [self.carrera1.id, self.carrera2.id],
            'años': ['I', 'II']
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_invalido_campos_vacios(self):
        form = ExportarAsignacionesForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('trimestre', form.errors)
        self.assertIn('carreras', form.errors)
        self.assertIn('años', form.errors)


class ViewsValidationTest(TestCase):
    def setUp(self):
        # Mocks para evitar llamadas a la API de Google Classroom y bloqueos de DB en hilos
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.mock_crear = self.patcher_crear.start()
        self.mock_subir = self.patcher_subir.start()

        self.usuario = User.objects.create_user(username="profesor_test", password="testpassword")
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería Industrial", codigo="II01", cine_2011=111, cine_2013=222, area_formacion="Artes y Humanidades", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Física I")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="I", trimestre="I", pensol="2018", codigo="PLAN_FIS", asignatura=self.asignatura,
            horas_presenciales=45, horas_estudio_independiente=45
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(usuario=self.usuario, plan_de_estudio=self.plan)
        
        self.silabo = Silabo.objects.create(
            codigo="PLAN_FIS",
            encuentros=1,
            fecha=datetime.date(2026, 6, 20),
            unidad="Unidad I",
            nombre_de_la_unidad="Unidad de prueba",
            contenido_tematico="Contenido de prueba",
            objetivo_conceptual="Prueba conceptual",
            objetivo_procedimental="Prueba procedimental",
            objetivo_actitudinal="Prueba actitudinal",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Prueba",
            tiempo_primer_momento=10,
            recursos_primer_momento="Libro",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Clase teorica",
            tipo_segundo_momento_practica="Taller",
            clase_practica="Clase practica",
            tiempo_segundo_momento_teorica=30,
            tiempo_segundo_momento_practica=30,
            recursos_segundo_momento="Pizarra",
            tipo_tercer_momento=["Orientación del estudio independiente"],
            detalle_tercer_momento="Detalle",
            tiempo_tercer_momento=10,
            recursos_tercer_momento="Web",
            eje_transversal=["Cultura de paz"],
            detalle_eje_transversal="Detalle eje",
            actividad_aprendizaje="Actividad",
            tecnica_evaluacion=["Ensayo"],
            tipo_evaluacion=["Formativa"],
            periodo_tiempo_programado="I Corte Evaluativo",
            tiempo_minutos=30,
            agente_evaluador=["Heteroevaluación"],
            instrumento_evaluacion="Rúbrica",
            criterios_evaluacion="Criterios",
            puntaje=10,
            asignacion_plan=self.asignacion
        )

        self.client = Client()
        self.client.login(username="profesor_test", password="testpassword")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def test_guardar_silabo_valido(self):
        url = reverse('guardar_silabo', kwargs={'asignacion_id': self.asignacion.id})
        form_data = {
            'codigo': 'PLAN_FIS',
            'encuentros': 2,
            'fecha': '2026-06-21',
            'unidad': 'Unidad I',
            'nombre_de_la_unidad': 'Movimiento en una dimensión',
            'contenido_tematico': 'Cinemática básica.',
            'objetivo_conceptual': 'Concepto de aceleración.',
            'objetivo_procedimental': 'Resolver problemas de velocidad.',
            'objetivo_actitudinal': 'Apreciar la exactitud física.',
            'tipo_primer_momento': 'Evaluación diagnóstica',
            'detalle_primer_momento': 'Diagnóstico oral',
            'tiempo_primer_momento': 10,
            'recursos_primer_momento': 'Marcadores',
            'tipo_segundo_momento_claseteoria': 'Conferencia',
            'clase_teorica': 'Conceptos de cinemática',
            'tipo_segundo_momento_practica': 'Taller',
            'clase_practica': 'Resolución de problemas',
            'tiempo_segundo_momento_teorica': 40,
            'tiempo_segundo_momento_practica': 40,
            'recursos_segundo_momento': 'Pizarra',
            'tipo_tercer_momento': ['Orientación del estudio independiente'],
            'detalle_tercer_momento': 'Lectura obligatoria',
            'tiempo_tercer_momento': 10,
            'recursos_tercer_momento': 'Libro guía',
            'eje_transversal': ['Fe cristiana'],
            'detalle_eje_transversal': 'Eje de valores',
            'actividad_aprendizaje': 'Taller práctico',
            'tecnica_evaluacion': ['Debate'],
            'tipo_evaluacion': ['Sumativa'],
            'periodo_tiempo_programado': 'I Corte Evaluativo',
            'tiempo_minutos': 20,
            'agente_evaluador': ['Heteroevaluación'],
            'instrumento_evaluacion': 'Listas de cotejo',
            'criterios_evaluacion': 'Criterios de evaluación',
            'puntaje': 15,
        }
        response = self.client.post(url, data=form_data)
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        self.assertTrue(resp_json['success'])
        self.assertIn('silabo_id', resp_json)

    def test_guardar_silabo_invalido(self):
        url = reverse('guardar_silabo', kwargs={'asignacion_id': self.asignacion.id})
        form_data = {
            'codigo': 'PLAN_FIS',
            'encuentros': 2,
        }
        response = self.client.post(url, data=form_data)
        self.assertEqual(response.status_code, 400)
        resp_json = response.json()
        self.assertFalse(resp_json['success'])
        self.assertIn('errors', resp_json)

    def test_guardar_guia_valido(self):
        url = reverse('guardar_guia', kwargs={'silabo_id': self.silabo.id})
        guia_data = {
            "numero_encuentro": 1,
            "fecha": "2026-06-25",
            "unidad": "Unidad I",
            "nombre_de_la_unidad": "Unidad de prueba",
            "tipo_objetivo_1": "Conceptual",
            "objetivo_aprendizaje_1": "Objetivo de la guía",
            "contenido_tematico_1": "Contenido de la guía",
            "actividad_aprendizaje_1": "Actividad autónoma",
            "tecnica_evaluacion_1": "Trabajo en grupo",
            "tipo_evaluacion_1": "Formativa",
            "instrumento_evaluacion_1": "Listas de cotejo",
            "criterios_evaluacion_1": "Criterios guía",
            "agente_evaluador_1": ["Coevaluación"],
            "tiempo_minutos_1": 45,
            "recursos_didacticos_1": "Videos interactivos",
            "periodo_tiempo_programado_1": "I Corte Evaluativo",
            "puntaje_1": 15,
            "fecha_entrega_1": "2026-06-30"
        }
        response = self.client.post(
            url, 
            data=json.dumps(guia_data), 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        resp_json = response.json()
        self.assertTrue(resp_json['success'])
        self.assertIn('guia_id', resp_json)

    def test_guardar_guia_invalido(self):
        url = reverse('guardar_guia', kwargs={'silabo_id': self.silabo.id})
        guia_data = {
            "numero_encuentro": 1,
            "fecha": "2026-06-25",
            "unidad": "Unidad I",
            "nombre_de_la_unidad": "Unidad de prueba",
            "tipo_objetivo_1": "Conceptual",
            "objetivo_aprendizaje_1": "Objetivo de la guía",
            "contenido_tematico_1": "Contenido de la guía",
            "actividad_aprendizaje_1": "Actividad autónoma",
            "tecnica_evaluacion_1": "Trabajo en grupo",
            "tipo_evaluacion_1": "Formativa",
            "instrumento_evaluacion_1": "Listas de cotejo",
            "criterios_evaluacion_1": "Criterios guía",
            "agente_evaluador_1": ["Coevaluación"],
            "tiempo_minutos_1": -10,  # INVÁLIDO (debe ser >= 1)
            "recursos_didacticos_1": "Videos interactivos",
            "periodo_tiempo_programado_1": "I Corte Evaluativo",
            "puntaje_1": 15,
            "fecha_entrega_1": "2026-06-30"
        }
        response = self.client.post(
            url, 
            data=json.dumps(guia_data), 
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        resp_json = response.json()
        self.assertFalse(resp_json['success'])
        self.assertIn('errors', resp_json)
        self.assertIn('tiempo_minutos_1', resp_json['errors'])
