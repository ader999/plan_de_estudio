import datetime
import json
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from django.utils import timezone
from plan_de_estudio.models import (
    Asignatura, Carrera, Plan_de_estudio, AsignacionPlanEstudio, Silabo, Guia, ProyectoExamen,
    ModeloIAConfig, ProveedorIA, ProgramaAsignatura2026, PlanTematico, ConfiguracionSistema
)
from plan_de_estudio.forms import (
    SilaboForm, ExportarAsignacionesForm, AsignacionPlanEstudioAdminForm
)
from plan_de_estudio.ranking_utils import construir_ranking_docentes, obtener_rango_ciclo_actual
from plan_de_estudio.trimestre_utils import obtener_trimestre_lectivo_de_fecha


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
        self.assertEqual(
            str(plan),
            f"{self.asignatura.nombre.upper()} - {self.carrera.nombre} - I - Pensol 2018",
        )

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
            trimestre_lectivo="2026-IV",
            bloque="Primer bloque - 8:00"
        )
        asignacion.full_clean()
        asignacion.save()
        self.assertEqual(str(asignacion), f"{self.usuario} - {self.plan}")
        self.assertIsNotNone(asignacion.fecha_asignacion)
        self.assertEqual(asignacion.trimestre_lectivo_display, "2026 - Trimestre IV")

    def test_asignacion_plan_de_estudio_obligatorio(self):
        asignacion = AsignacionPlanEstudio(
            usuario=self.usuario,
            trimestre_lectivo="2026-IV",
            bloque="Primer bloque - 8:00"
        )
        with self.assertRaises(ValidationError) as ctx:
            asignacion.clean()
        self.assertIn('plan_de_estudio', ctx.exception.message_dict)

    def test_asignacion_trimestre_lectivo_obligatorio_y_formato(self):
        sin_trimestre = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            bloque="Primer bloque - 8:00"
        )
        with self.assertRaises(ValidationError) as ctx:
            sin_trimestre.clean()
        self.assertIn('trimestre_lectivo', ctx.exception.message_dict)

        formato_invalido = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo="2026-V",
        )
        with self.assertRaises(ValidationError) as ctx_fmt:
            formato_invalido.clean()
        self.assertIn('trimestre_lectivo', ctx_fmt.exception.message_dict)

    def test_asignacion_duplicada_en_mismo_trimestre_lectivo_y_permitida_en_otro(self):
        AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo="2026-III",
            bloque="Primer bloque - 8:00"
        )

        duplicada_mismo_trimestre = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo="2026-III",
            bloque="Segundo bloque - 10:20"
        )
        with self.assertRaises(ValidationError) as ctx:
            duplicada_mismo_trimestre.clean()

        self.assertIn(
            "Asignacion plan estudio con este Usuario y Plan de estudio ya existe en el trimestre lectivo seleccionado.",
            ctx.exception.messages
        )

        # Misma asignatura y docente en el siguiente trimestre lectivo (creado hoy mismo) debe permitirse
        proximo_trimestre = AsignacionPlanEstudio(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo="2026-IV",
            bloque="Segundo bloque - 10:20"
        )
        proximo_trimestre.full_clean()
        proximo_trimestre.save()
        self.assertEqual(AsignacionPlanEstudio.objects.count(), 2)


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
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )

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
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        
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


class ModeloIAConfigAndAdminTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_crear.start()

        self.admin_user = User.objects.create_superuser(
            username="admin_ia", email="admin@example.com", password="adminpassword"
        )
        self.docente_user = User.objects.create_user(
            username="docente_ia", password="docentepassword"
        )
        self.carrera = Carrera.objects.create(
            nombre="Sistemas", codigo="SIS01", cine_2011=1, cine_2013=2,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Inteligencia Artificial")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="I", trimestre="I", pensol="2026",
            codigo="PLAN_IA", asignatura=self.asignatura,
            horas_presenciales=45, horas_estudio_independiente=45
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_user, plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        self.programa_2026 = ProgramaAsignatura2026.objects.create(
            plan_estudio=self.plan,
            fundamentacion="Fund",
            relacion_unidades="Rel",
            aportes_perfil="Aportes",
            valores="Valores",
            ejes_transversales="Ejes",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
        )

    def tearDown(self):
        self.patcher_crear.stop()

    def test_modelo_ia_config_unicidad_extraccion_y_mascara(self):
        m1 = ModeloIAConfig.objects.create(
            proveedor="google",
            modelo_id="gemini-2.5-flash",
            api_key="AIzaSySecretKey1234567890",
            usar_para_extraccion=True,
        )
        self.assertEqual(m1.nombre_mostrar, "Google Gemini - gemini-2.5-flash")
        self.assertEqual(m1.api_key_enmascarada, "AIza••••••••7890")
        self.assertTrue(m1.usar_para_extraccion)

        m2 = ModeloIAConfig.objects.create(
            proveedor="openai",
            modelo_id="gpt-4o-mini",
            api_key="sk-proj-abc123456789xyz",
            usar_para_extraccion=True,
        )
        m1.refresh_from_db()
        self.assertFalse(m1.usar_para_extraccion)
        self.assertTrue(m2.usar_para_extraccion)

    def test_admin_copia_seguridad_endpoints_y_ocultamiento_key(self):
        client = Client()
        client.login(username="admin_ia", password="adminpassword")

        # Guardar nuevo modelo desde el formulario de Copias de Seguridad / Configuración
        guardar_url = reverse('admin:plan_de_estudio_copiaseguridad_guardar_modelo_ia')
        resp = client.post(guardar_url, {
            'proveedor': 'deepseek',
            'api_key': 'sk-deepseek-super-secret-9999',
            'modelo_id': 'deepseek-chat',
            'nombre_mostrar': 'DeepSeek Chat Institucional',
            'disponible_docentes': 'on',
            'usar_para_extraccion': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        modelo = ModeloIAConfig.objects.get(modelo_id='deepseek-chat')
        self.assertTrue(modelo.disponible_docentes)
        self.assertTrue(modelo.usar_para_extraccion)

        # Verificar que el changelist muestra el modelo pero NO expone la API key completa
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        page = client.get(changelist_url)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode('utf-8')
        self.assertIn('DeepSeek Chat Institucional', html)
        self.assertNotIn('sk-deepseek-super-secret-9999', html)

        # Toggle docentes
        accion_url = reverse('admin:plan_de_estudio_copiaseguridad_accion_modelo_ia', args=[modelo.id])
        client.post(accion_url, {'accion': 'toggle_docentes'})
        modelo.refresh_from_db()
        self.assertFalse(modelo.disponible_docentes)

        # Configurar extracción 2026 a env_default
        extr_url = reverse('admin:plan_de_estudio_copiaseguridad_configurar_extraccion_2026')
        client.post(extr_url, {'modelo_extraccion_id': 'env_default'})
        modelo.refresh_from_db()
        self.assertFalse(modelo.usar_para_extraccion)

        # Consultar modelos disponibles (mockeado)
        consultar_url = reverse('admin:plan_de_estudio_copiaseguridad_consultar_modelos_ia')
        with patch('plan_de_estudio.admin.listar_modelos_disponibles', return_value=[
            {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash'}
        ]):
            resp_json = client.post(
                consultar_url,
                data=json.dumps({'proveedor': 'google', 'api_key': 'AIzaTest'}),
                content_type='application/json'
            )
            self.assertEqual(resp_json.status_code, 200)
            payload = resp_json.json()
            self.assertTrue(payload['success'])
            self.assertEqual(payload['modelos'][0]['id'], 'gemini-2.5-flash')

    def test_docente_ve_modelos_configurados_y_no_inactivos(self):
        m_visible = ModeloIAConfig.objects.create(
            proveedor="openai",
            modelo_id="gpt-4o-mini",
            nombre_mostrar="OpenAI GPT-4o Mini Institucional",
            api_key="sk-test-visible-1234",
            disponible_docentes=True,
            activo=True,
        )
        m_oculto = ModeloIAConfig.objects.create(
            proveedor="google",
            modelo_id="gemini-pro-oculto",
            nombre_mostrar="Modelo Solo Extracción",
            api_key="AIzaTestOculto1234",
            disponible_docentes=False,
            activo=True,
        )

        client = Client()
        client.login(username="docente_ia", password="docentepassword")

        resp_silabo = client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp_silabo.status_code, 200)
        html_silabo = resp_silabo.content.decode('utf-8')
        self.assertIn(f'value="{m_visible.id}"', html_silabo)
        self.assertIn("OpenAI GPT-4o Mini Institucional", html_silabo)
        self.assertNotIn("Modelo Solo Extracción", html_silabo)
        self.assertNotIn("sk-test-visible-1234", html_silabo)

        resp_guia = client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_guia.status_code, 200)
        html_guia = resp_guia.content.decode('utf-8')
        self.assertIn(f'value="{m_visible.id}"', html_guia)
        self.assertIn("OpenAI GPT-4o Mini Institucional", html_guia)
        self.assertNotIn("Modelo Solo Extracción", html_guia)

    def test_generar_respuesta_ai_con_modelo_db_y_legado(self):
        from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config

        m_cfg = ModeloIAConfig.objects.create(
            proveedor="openai",
            modelo_id="gpt-4.1-mini",
            api_key="sk-custom-key-9876",
            disponible_docentes=True,
            activo=True,
        )
        default_cfg = get_default_config(str(m_cfg.id))
        self.assertEqual(default_cfg["model"], "gpt-4.1-mini")

        fake_json = json.dumps({"descripcion": "Prueba OK", "actividades": ["A1"], "recursos": ["R1"]})
        with patch('plan_de_estudio.ai_generators.usar_modelo_openai', return_value=fake_json) as mock_openai:
            result = generar_respuesta_ai("Hola", modelo_seleccionado=str(m_cfg.id), **default_cfg)
            self.assertEqual(result["descripcion"], "Prueba OK")
            mock_openai.assert_called_once()
            _, kwargs = mock_openai.call_args
            self.assertEqual(kwargs["model"], "gpt-4.1-mini")
            self.assertEqual(kwargs["api_key"], "sk-custom-key-9876")

        # Compatibilidad con identificador legado 'google'
        with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=fake_json) as mock_google:
            result_legacy = generar_respuesta_ai("Hola", modelo_seleccionado="google")
            self.assertEqual(result_legacy["descripcion"], "Prueba OK")
            mock_google.assert_called_once()

    def test_programa_2026_import_selecciona_y_usa_modelo_extraccion(self):
        import io
        import docx
        from plan_de_estudio.utils.gemini_parser import parse_curriculum_with_ai

        m_extr = ModeloIAConfig.objects.create(
            proveedor="deepseek",
            modelo_id="deepseek-chat",
            nombre_mostrar="DeepSeek Extractor 2026",
            api_key="sk-ds-extractor-4321",
            disponible_docentes=False,
            usar_para_extraccion=True,
            activo=True,
        )

        client = Client()
        client.login(username="admin_ia", password="adminpassword")
        import_url = reverse('admin:plan_de_estudio_programaasignatura2026_import_docx')
        resp_get = client.get(import_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn("DeepSeek Extractor 2026", resp_get.content.decode('utf-8'))

        # Crear archivo .docx mínimo en memoria
        doc_io = io.BytesIO()
        doc = docx.Document()
        doc.add_paragraph("FUNDAMENTACIÓN: Curso de prueba.")
        doc.save(doc_io)
        doc_io.seek(0)

        with patch('plan_de_estudio.ai_generators.generar_texto_crudo_ai', return_value='{"fundamentacion": "Curso de prueba."}') as mock_raw:
            parsed = parse_curriculum_with_ai(doc_io)
            self.assertEqual(parsed.get("fundamentacion"), "Curso de prueba.")
            mock_raw.assert_called_once()
            _, kwargs = mock_raw.call_args
            self.assertEqual(kwargs["proveedor"], "deepseek")
            self.assertEqual(kwargs["modelo_id"], "deepseek-chat")
            self.assertEqual(kwargs["api_key"], "sk-ds-extractor-4321")

    def test_admin_puede_crear_usar_y_eliminar_proveedor_personalizado(self):
        from django.contrib.auth.models import User

        admin_user = User.objects.create_superuser('admin_custom_prov', 'admin_cp@test.com', 'pass12345')
        client = Client()
        client.force_login(admin_user)

        resp_crear = client.post(
            reverse('admin:plan_de_estudio_copiaseguridad_guardar_proveedor_ia'),
            {
                'nombre_proveedor': 'Mi Ollama Local',
                'formato_api': 'openai_compatible',
                'base_url': 'http://localhost:11434/v1/chat/completions',
            },
        )
        self.assertEqual(resp_crear.status_code, 302)
        prov = ProveedorIA.objects.get(nombre='Mi Ollama Local')
        self.assertEqual(prov.formato_api, 'openai_compatible')
        self.assertEqual(prov.base_url_normalizada, 'http://localhost:11434/v1')

        with patch('plan_de_estudio.admin.listar_modelos_disponibles', return_value=[
            {'id': 'llama3.1:8b', 'name': 'llama3.1:8b'}
        ]) as mock_list:
            resp_list = client.post(
                reverse('admin:plan_de_estudio_copiaseguridad_consultar_modelos_ia'),
                data=json.dumps({'proveedor': f'custom:{prov.id}', 'api_key': 'sk-local-123'}),
                content_type='application/json',
            )
            self.assertEqual(resp_list.status_code, 200)
            self.assertEqual(resp_list.json()['modelos'][0]['id'], 'llama3.1:8b')
            mock_list.assert_called_once_with(
                'custom',
                'sk-local-123',
                base_url='http://localhost:11434/v1',
                formato_api='openai_compatible',
            )

        resp_save_model = client.post(
            reverse('admin:plan_de_estudio_copiaseguridad_guardar_modelo_ia'),
            {
                'proveedor': f'custom:{prov.id}',
                'api_key': 'sk-local-123',
                'modelo_id': 'llama3.1:8b',
                'nombre_mostrar': 'Ollama - Llama 3.1',
                'disponible_docentes': 'on',
            },
        )
        self.assertEqual(resp_save_model.status_code, 302)
        modelo = ModeloIAConfig.objects.get(modelo_id='llama3.1:8b')
        self.assertEqual(modelo.proveedor, 'custom')
        self.assertEqual(modelo.proveedor_custom_id, prov.id)
        self.assertEqual(modelo.proveedor_display_nombre, 'Mi Ollama Local')

        from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
        default_cfg = get_default_config(str(modelo.id))
        with patch('plan_de_estudio.ai_generators.usar_modelo_openai', return_value='{"descripcion": "Ollama OK"}') as mock_openai:
            out = generar_respuesta_ai('Hola', modelo_seleccionado=str(modelo.id), **default_cfg)
            self.assertEqual(out['descripcion'], 'Ollama OK')
            mock_openai.assert_called_once()
            _, kw = mock_openai.call_args
            self.assertEqual(kw['base_url'], 'http://localhost:11434/v1')
            self.assertEqual(kw['model'], 'llama3.1:8b')
            self.assertEqual(kw['api_key'], 'sk-local-123')

        resp_del = client.post(
            reverse('admin:plan_de_estudio_copiaseguridad_eliminar_proveedor_ia', args=[prov.id])
        )
        self.assertEqual(resp_del.status_code, 302)
        self.assertFalse(ProveedorIA.objects.filter(id=prov.id).exists())


class PwaAndTwaEndpointsTest(TestCase):
    def test_manifest_json_valido(self):
        resp = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/manifest+json', resp['Content-Type'])
        data = resp.json()
        self.assertEqual(data['short_name'], 'PLANEAUML')
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['start_url'], '/?source=pwa')
        sizes = {icon['sizes'] for icon in data['icons']}
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)

    def test_service_worker_cabeceras_y_contenido(self):
        with self.assertNumQueries(0):
            resp = self.client.get(reverse('pwa_sw'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/javascript', resp['Content-Type'])
        self.assertEqual(resp['Service-Worker-Allowed'], '/')
        self.assertIn('no-cache', resp['Cache-Control'])
        body = resp.content.decode('utf-8')
        self.assertIn("const OFFLINE_URL = \"/offline/\"", body)
        self.assertIn('fetchWithTimeout', body)
        self.assertIn("fetchWithTimeout(request, 45000)", body)

    def test_offline_page_disponible(self):
        with self.assertNumQueries(0):
            resp = self.client.get(reverse('pwa_offline'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sin conexión')

    def test_assetlinks_vacio_y_configurado(self):
        import os
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ANDROID_ASSETLINKS_SHA256', None)
            resp_empty = self.client.get(reverse('pwa_assetlinks'))
            self.assertEqual(resp_empty.status_code, 200)
            self.assertEqual(resp_empty.json(), [])

        with patch.dict(
            os.environ,
            {
                'ANDROID_PACKAGE_NAME': 'com.planeauml.app',
                'ANDROID_ASSETLINKS_SHA256': 'AA:BB:CC:DD',
            },
        ):
            resp_cfg = self.client.get(reverse('pwa_assetlinks'))
            self.assertEqual(resp_cfg.status_code, 200)
            data = resp_cfg.json()
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['target']['package_name'], 'com.planeauml.app')
            self.assertEqual(data[0]['target']['sha256_cert_fingerprints'], ['AA:BB:CC:DD'])

    def test_plantillas_base_incluyen_manifest_y_sw(self):
        resp = self.client.get(reverse('login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/manifest.json')
        self.assertContains(resp, '/sw.js')
        self.assertContains(resp, 'Centro de Recursos')
        self.assertContains(resp, 'pwa-force-update-overlay')

    def test_app_version_y_descarga_apk_desde_metadata_remota(self):
        import os
        from urllib.error import URLError
        from plan_de_estudio import pwa_views

        pwa_views.clear_apk_metadata_cache()
        fake_payload = {
            'version_code': 7,
            'version_name': '1.0.7',
            'package_id': 'com.planeauml.pwa',
            'mandatory': True,
            'release_tag': 'v1.0.7',
            'commit_sha': 'abc1234',
            'apk_size_bytes': 2621440,
            'download_url': 'https://example.org/releases/v1.0.7/PLANEAUML.apk',
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fake_payload).encode('utf-8')
        mock_response.__enter__.return_value = mock_response

        with patch('plan_de_estudio.pwa_views.urlopen', return_value=mock_response):
            resp = self.client.get(reverse('app_version'))
            self.assertEqual(resp.status_code, 200)
            self.assertIn('no-cache', resp['Cache-Control'])
            data = resp.json()
            self.assertTrue(data['available'])
            self.assertEqual(data['latest_version_code'], 7)
            self.assertEqual(data['latest_version_name'], '1.0.7')
            self.assertEqual(data['apk_size_mb'], 2.5)
            self.assertEqual(data['download_url'], '/app/descargar-apk/')

            dl_resp = self.client.get(reverse('app_download_apk'))
            self.assertEqual(dl_resp.status_code, 302)
            self.assertEqual(
                dl_resp['Location'],
                'https://example.org/releases/v1.0.7/PLANEAUML.apk',
            )
            dl_head_resp = self.client.head(reverse('app_download_apk'))
            self.assertEqual(dl_head_resp.status_code, 302)

        pwa_views.clear_apk_metadata_cache()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('APK_MIN_VERSION_CODE', None)
            with patch('plan_de_estudio.pwa_views.urlopen', side_effect=URLError('offline')):
                fallback_resp = self.client.get(reverse('app_version'))
                self.assertEqual(fallback_resp.status_code, 200)
                fallback_data = fallback_resp.json()
                self.assertFalse(fallback_data['available'])
                self.assertEqual(fallback_data['latest_version_code'], 1)

    def test_centro_de_recursos_y_redireccion_tutoriales(self):
        from plan_de_estudio import pwa_views

        pwa_views.clear_apk_metadata_cache()
        fake_payload = {
            'version_code': 4,
            'version_name': '1.0.4',
            'download_url': 'https://example.org/PLANEAUML.apk',
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(fake_payload).encode('utf-8')
        mock_response.__enter__.return_value = mock_response

        with patch('plan_de_estudio.pwa_views.urlopen', return_value=mock_response):
            resp = self.client.get(reverse('tutoriales'))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'Centro de Recursos')
            self.assertContains(resp, 'Descargar APK')
            self.assertContains(resp, reverse('app_download_apk'))
            self.assertContains(resp, 'v1.0.4')

        legacy = self.client.get('/tutoriales/')
        self.assertEqual(legacy.status_code, 302)
        self.assertEqual(legacy['Location'], reverse('tutoriales'))


class SilaboFormularioYGeneracionTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="docente_silabo", password="testpassword")
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas", codigo="IS01", cine_2011=111, cine_2013=222,
            area_formacion="Tecnología", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Implementación de Bases de Datos II")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="I", pensol="2018", codigo="BD201",
            asignatura=self.asignatura, horas_presenciales=45, horas_estudio_independiente=45
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        self.client = Client()
        self.client.login(username="docente_silabo", password="testpassword")

    def _crear_silabo(self, encuentro):
        return Silabo.objects.create(
            codigo="BD201",
            encuentros=encuentro,
            fecha=datetime.date(2026, 6, 20),
            unidad="Unidad I",
            nombre_de_la_unidad="Unidad de prueba",
            contenido_tematico="Contenido de prueba",
            objetivo_conceptual="Conceptual",
            objetivo_procedimental="Procedimental",
            objetivo_actitudinal="Actitudinal",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Detalle",
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
            asignacion_plan=self.asignacion,
        )

    def test_formulario_incluye_contenedores_alerta_y_calcula_encuentro_faltante(self):
        self._crear_silabo(1)
        self._crear_silabo(3)

        resp = self.client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="silabo-alert-container"')
        self.assertContains(resp, 'id="guardar-alert-container"')
        self.assertContains(resp, 'Encuentro (2)')

    def test_ver_formulario_silabo_redirige_si_ya_hay_11_encuentros(self):
        for enc in range(1, 12):
            self._crear_silabo(enc)
        # Simular contador desincronizado en BD
        self.asignacion.silabos_creados = 10
        self.asignacion.save()

        resp = self.client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], reverse('inicio'))
        self.asignacion.refresh_from_db()
        self.assertEqual(self.asignacion.silabos_creados, 11)

    def test_generar_silabo_valida_rango_y_tipo_encuentro(self):
        resp_12 = self.client.post(reverse('generar_silabo'), {
            'encuentro': '12',
            'plan': str(self.asignacion.id),
            'modelo_select': 'google',
        })
        self.assertEqual(resp_12.status_code, 400)
        self.assertIn('entre 1 y 11', resp_12.json()['error'])

        resp_none = self.client.post(reverse('generar_silabo'), {
            'plan': str(self.asignacion.id),
            'modelo_select': 'google',
        })
        self.assertEqual(resp_none.status_code, 400)
        self.assertIn('número válido', resp_none.json()['error'])

    def test_formulario_silabo_renderiza_wizard_6_pasos_y_borrador_local(self):
        resp = self.client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="silabo-wizard-root"')
        self.assertContains(resp, f'data-asignacion-id="{self.asignacion.id}"')
        self.assertContains(resp, 'data-encuentro="1"')
        for step in range(1, 7):
            self.assertContains(resp, f'class="wizard-step')
            self.assertContains(resp, f'data-step="{step}"')
        self.assertContains(resp, 'silabo_wizard.js')
        self.assertContains(resp, 'id="wizardPrevBtn"')
        self.assertContains(resp, 'id="wizardNextBtn"')
        self.assertContains(resp, 'id="guardarFormularioBtn"')
        self.assertContains(resp, 'id="btn-descartar-borrador"')

    def test_formulario_guia_renderiza_wizard_5_pasos_y_borrador_local(self):
        self._crear_silabo(1)
        resp = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        self.assertContains(resp, 'id="guia-wizard-root"')
        self.assertContains(resp, 'data-usuario="docente_silabo"')
        self.assertContains(resp, f'data-asignacion-id="{self.asignacion.id}"')
        self.assertContains(resp, 'data-encuentro="1"')

        for step in range(1, 6):
            self.assertIn(f'data-step="{step}"', html)
        self.assertNotIn('<div class="wizard-step d-none" data-step="6">', html)

        # Paso 3 contiene únicamente la 2da actividad; Paso 4 agrupa 3ra y 4ta juntas
        step3_marker = '<div class="wizard-step d-none" data-step="3">'
        step4_marker = '<div class="wizard-step d-none" data-step="4">'
        step5_marker = '<div class="wizard-step d-none" data-step="5">'
        idx3 = html.index(step3_marker)
        idx4 = html.index(step4_marker)
        idx5 = html.index(step5_marker)

        step3_html = html[idx3:idx4]
        step4_html = html[idx4:idx5]
        step5_html = html[idx5:]

        self.assertIn('id="activity-card-2"', step3_html)
        self.assertNotIn('id="activity-card-3"', step3_html)
        self.assertIn('id="activity-card-3"', step4_html)
        self.assertIn('id="activity-card-4"', step4_html)
        self.assertIn('fa-check-circle', step5_html)
        self.assertNotIn('fa-check-double', step5_html)

        # Verificar campos renderizados de actividades 1..4 y controles del wizard
        for n in range(1, 5):
            self.assertIn(f'id="tipo_objetivo_{n}"', html)
            self.assertIn(f'id="fecha_entrega_{n}"', html)
            self.assertIn(f'name="agente_evaluador_{n}[]"', html)
        self.assertIn('guia_wizard.js', html)
        self.assertIn('guia_guardar.js', html)
        self.assertIn('guia_ia.js', html)
        self.assertIn('id="wizardPrevBtn"', html)
        self.assertIn('id="wizardNextBtn"', html)
        self.assertIn('id="guardarFormularioBtn"', html)
        self.assertIn('id="btn-descartar-borrador"', html)
        self.assertIn('data-clear-activity="3"', html)
        self.assertIn('data-toggle-activity="4"', html)


class ConfiguracionPlanTematicoDescargaTest(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_media)
        self.override.enable()
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_crear.start()

        self.admin_user = User.objects.create_superuser(
            username="admin_cfg", email="admin_cfg@example.com", password="adminpassword"
        )
        self.docente_user = User.objects.create_user(
            username="docente_cfg", password="docentepassword"
        )
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería Civil", codigo="IC01", cine_2011=111, cine_2013=222,
            area_formacion="Tecnología", area_disiplinaria=1
        )
        self.asig_pendiente = Asignatura.objects.create(nombre="Estructuras I")
        self.asig_completada = Asignatura.objects.create(nombre="Estructuras II")

        self.plan_pendiente = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="I", pensol="2026", codigo="EST101",
            asignatura=self.asig_pendiente, horas_presenciales=40, horas_estudio_independiente=40,
            plan_tematico=SimpleUploadedFile("plan_pendiente.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
        )
        self.plan_completado = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="IV", trimestre="I", pensol="2026", codigo="EST201",
            asignatura=self.asig_completada, horas_presenciales=40, horas_estudio_independiente=40,
            plan_tematico=SimpleUploadedFile("plan_completado.pdf", b"%PDF-1.4 dummy", content_type="application/pdf"),
        )

        self.asig_p = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_user, plan_de_estudio=self.plan_pendiente,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(), silabos_creados=0
        )
        self.asig_c = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_user, plan_de_estudio=self.plan_completado,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(), silabos_creados=11
        )

    def tearDown(self):
        self.patcher_crear.stop()
        self.override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_admin_toggle_descarga_plan_tematico(self):
        config = ConfiguracionSistema.get_solo()
        self.assertTrue(config.permitir_descarga_plan_tematico)

        client = Client()
        client.login(username="admin_cfg", password="adminpassword")

        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        toggle_url = reverse('admin:plan_de_estudio_copiaseguridad_toggle_descarga_plan_tematico')

        resp = client.get(changelist_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Descarga de Plan Temático (Docentes)")
        self.assertContains(resp, "Habilitada")
        self.assertContains(resp, "Desactivar")

        # Desactivar descarga
        resp_off = client.post(toggle_url, {'accion': 'desactivar'})
        self.assertEqual(resp_off.status_code, 302)
        config.refresh_from_db()
        self.assertFalse(config.permitir_descarga_plan_tematico)

        resp = client.get(changelist_url)
        self.assertContains(resp, "Desactivada")
        self.assertContains(resp, "Activar")

        # Reactivar descarga
        resp_on = client.post(toggle_url, {'accion': 'activar'})
        self.assertEqual(resp_on.status_code, 302)
        config.refresh_from_db()
        self.assertTrue(config.permitir_descarga_plan_tematico)

    def test_docente_no_puede_modificar_configuracion(self):
        client = Client()
        client.login(username="docente_cfg", password="docentepassword")
        toggle_url = reverse('admin:plan_de_estudio_copiaseguridad_toggle_descarga_plan_tematico')
        resp = client.post(toggle_url, {'accion': 'desactivar'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/admin/login/', resp['Location'])
        self.assertTrue(ConfiguracionSistema.get_solo().permitir_descarga_plan_tematico)

    def test_docente_inicio_muestra_u_oculta_descarga_plan_tematico(self):
        client = Client()
        client.login(username="docente_cfg", password="docentepassword")

        # Habilitada por defecto: se muestran ambos botones (pendientes y archivados)
        resp_habilitado = client.get(reverse('inicio'))
        self.assertEqual(resp_habilitado.status_code, 200)
        html_hab = resp_habilitado.content.decode('utf-8')
        self.assertIn(self.plan_pendiente.plan_tematico.url, html_hab)
        self.assertIn(self.plan_completado.plan_tematico.url, html_hab)
        self.assertIn("Plan Temático", html_hab)

        # Desactivada: no se renderizan los enlaces ni el texto de plan temático
        config = ConfiguracionSistema.get_solo()
        config.permitir_descarga_plan_tematico = False
        config.save()

        resp_deshabilitado = client.get(reverse('inicio'))
        self.assertEqual(resp_deshabilitado.status_code, 200)
        html_des = resp_deshabilitado.content.decode('utf-8')
        self.assertNotIn(self.plan_pendiente.plan_tematico.url, html_des)
        self.assertNotIn(self.plan_completado.plan_tematico.url, html_des)
        self.assertNotIn("Plan Temático", html_des)
        self.assertNotIn("No se ha asignado un plan temático.", html_des)


class RankingDocentesTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_crear.start()

        self.admin_user = User.objects.create_superuser(
            username="admin_rank", email="admin_rank@example.com", password="adminpassword",
            first_name="Coord", last_name="Admin"
        )
        self.docente_top = User.objects.create_user(
            username="ana_gomez", password="docpassword",
            first_name="Ana", last_name="Gómez"
        )
        self.docente_medio = User.objects.create_user(
            username="carlos_ruiz", password="docpassword",
            first_name="Carlos", last_name="Ruiz"
        )
        self.docente_cero = User.objects.create_user(
            username="luis_mora", password="docpassword",
            first_name="Luis", last_name="Mora"
        )

        self.carrera_sis = Carrera.objects.create(
            nombre="Ingeniería en Sistemas", codigo="SIS01", cine_2011=101, cine_2013=201,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.carrera_der = Carrera.objects.create(
            nombre="Derecho", codigo="DER01", cine_2011=102, cine_2013=202,
            area_formacion="Administración de empresas y derecho", area_disiplinaria=2
        )

        self.asig_1 = Asignatura.objects.create(nombre="Algoritmos")
        self.asig_2 = Asignatura.objects.create(nombre="Bases de Datos")
        self.asig_3 = Asignatura.objects.create(nombre="Derecho Penal")
        self.asig_4 = Asignatura.objects.create(nombre="Arquitectura Web")

        self.plan_1 = Plan_de_estudio.objects.create(
            carrera=self.carrera_sis, año="I", trimestre="I", pensol="2026", codigo="ALG101",
            asignatura=self.asig_1, horas_presenciales=40, horas_estudio_independiente=40
        )
        self.plan_2 = Plan_de_estudio.objects.create(
            carrera=self.carrera_sis, año="II", trimestre="II", pensol="2026", codigo="BDD201",
            asignatura=self.asig_2, horas_presenciales=40, horas_estudio_independiente=40
        )
        self.plan_3 = Plan_de_estudio.objects.create(
            carrera=self.carrera_der, año="I", trimestre="III", pensol="2026", codigo="DER301",
            asignatura=self.asig_3, horas_presenciales=40, horas_estudio_independiente=40
        )
        self.plan_4 = Plan_de_estudio.objects.create(
            carrera=self.carrera_sis, año="III", trimestre="IV", pensol="2018", codigo="WEB401",
            asignatura=self.asig_4, horas_presenciales=40, horas_estudio_independiente=40
        )

        # Ana: 100% completo (11 sílabos + 10/11 guías + 3 proyectos de examen)
        ciclo_actual = obtener_trimestre_lectivo_de_fecha()
        self.asig_ana = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_top, plan_de_estudio=self.plan_1,
            trimestre_lectivo=ciclo_actual,
            bloque="Primer bloque - 8:00", silabos_creados=11, guias_creadas=11, examenes_creados=3
        )

        # Carlos: 2 asignaciones -> en plan_2 tiene 2 sílabos reales y 1 guía real en BD; en plan_4 tiene 0/0
        self.asig_carlos_1 = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_medio, plan_de_estudio=self.plan_2,
            trimestre_lectivo=ciclo_actual,
            bloque="Segundo bloque - 10:20", silabos_creados=2, guias_creadas=1
        )
        for enc in (1, 2):
            sil = Silabo.objects.create(
                codigo=self.plan_2.codigo,
                encuentros=enc,
                fecha=datetime.date(2026, 11, enc),
                unidad="Unidad I",
                nombre_de_la_unidad="Intro",
                contenido_tematico="Contenido",
                objetivo_conceptual="Obj C",
                objetivo_procedimental="Obj P",
                objetivo_actitudinal="Obj A",
                tipo_primer_momento="Evaluación diagnóstica",
                detalle_primer_momento="Det 1",
                tiempo_primer_momento=15,
                recursos_primer_momento="Pizarra",
                tipo_segundo_momento_claseteoria="Conferencia",
                clase_teorica="Teoría",
                tipo_segundo_momento_practica="Taller",
                clase_practica="Práctica",
                tiempo_segundo_momento_teorica=30,
                tiempo_segundo_momento_practica=30,
                recursos_segundo_momento="Proyector",
                tipo_tercer_momento=["Orientación del estudio independiente"],
                detalle_tercer_momento="Det 3",
                tiempo_tercer_momento=15,
                recursos_tercer_momento="Guía",
                eje_transversal=["Investigación"],
                detalle_eje_transversal="Eje",
                asignacion_plan=self.asig_carlos_1,
            )
            if enc == 1:
                Guia.objects.create(
                    silabo=sil,
                    numero_encuentro=1,
                    fecha=datetime.date(2026, 11, 1),
                    unidad="Unidad I",
                    nombre_de_la_unidad="Intro",
                    tipo_objetivo_1="Conceptual",
                    objetivo_aprendizaje_1="Obj",
                    contenido_tematico_1="Cont",
                    actividad_aprendizaje_1="Act",
                    tecnica_evaluacion_1="Observación",
                    tipo_evaluacion_1="Formativa",
                    instrumento_evaluacion_1="Rúbrica",
                    criterios_evaluacion_1="Crit",
                    agente_evaluador_1=["Heteroevaluación"],
                    tiempo_minutos_1=45,
                    recursos_didacticos_1="PDF",
                    periodo_tiempo_programado_1="I Corte Evaluativo",
                    puntaje_1=10,
                    fecha_entrega_1=datetime.date(2026, 11, 5),
                )

        self.asig_carlos_2 = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_medio, plan_de_estudio=self.plan_4,
            trimestre_lectivo=ciclo_actual,
            bloque="Tercer bloque - 12:20", silabos_creados=0, guias_creadas=0
        )

        # Luis: 0% sin avance
        self.asig_luis = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_cero, plan_de_estudio=self.plan_3,
            trimestre_lectivo=ciclo_actual,
            bloque="Cuarto bloque - 2:30", silabos_creados=0, guias_creadas=0
        )

    def tearDown(self):
        self.patcher_crear.stop()

    def test_usuario_anonimo_redirigido_a_login(self):
        client = Client()
        resp = client.get(reverse('ranking_docentes'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_calculo_ranking_por_docente_y_ordenamiento(self):
        data_mayor = construir_ranking_docentes(alcance='actual', orden='mayor', alcance_explicito=True)
        docentes = data_mayor['docentes']
        self.assertEqual(len(docentes), 3)

        # Orden esperado mayor a menor (11 sílabos + 10 guías + 3 exámenes = 24 entregables por asignación):
        # Ana (100.0%, compatible incluso con 11 guías legadas), Carlos (3/48 = 6.2%), Luis (0.0%)
        self.assertEqual(docentes[0]['username'], 'ana_gomez')
        self.assertEqual(docentes[0]['puesto'], 1)
        self.assertEqual(docentes[0]['porcentaje_general'], 100.0)
        self.assertEqual(docentes[0]['total_silabos'], 11)
        self.assertEqual(docentes[0]['total_guias'], 10)
        self.assertEqual(docentes[0]['total_examenes'], 3)
        self.assertEqual(docentes[0]['esperado_entregables'], 24)
        self.assertEqual(docentes[0]['estado'], 'cumplido')

        self.assertEqual(docentes[1]['username'], 'carlos_ruiz')
        self.assertEqual(docentes[1]['puesto'], 2)
        self.assertEqual(docentes[1]['total_silabos'], 2)
        self.assertEqual(docentes[1]['total_guias'], 1)
        self.assertEqual(docentes[1]['total_entregables'], 3)
        self.assertEqual(docentes[1]['esperado_entregables'], 48)
        self.assertEqual(docentes[1]['porcentaje_general'], 6.2)
        self.assertEqual(docentes[1]['estado'], 'rezagado')

        self.assertEqual(docentes[2]['username'], 'luis_mora')
        self.assertEqual(docentes[2]['puesto'], 3)
        self.assertEqual(docentes[2]['porcentaje_general'], 0.0)
        self.assertEqual(docentes[2]['estado'], 'sin_avance')

        # Orden rezagados primero: Luis (#3), Carlos (#2), Ana (#1)
        data_menor = construir_ranking_docentes(alcance='actual', orden='menor', alcance_explicito=True)
        docentes_menor = data_menor['docentes']
        self.assertEqual([d['username'] for d in docentes_menor], ['luis_mora', 'carlos_ruiz', 'ana_gomez'])
        self.assertEqual([d['puesto'] for d in docentes_menor], [3, 2, 1])

        # Verificar KPIs globales
        self.assertEqual(data_mayor['resumen']['total_docentes'], 3)
        self.assertEqual(data_mayor['resumen']['docentes_cumplidos'], 1)
        self.assertEqual(data_mayor['resumen']['docentes_con_pendientes'], 2)
        self.assertEqual(data_mayor['resumen']['docentes_sin_avance'], 1)

    def test_alcance_ciclo_actual_y_todas_las_asignaciones(self):
        # Mover la asignación de Luis a otro trimestre lectivo manteniendo su fecha_asignacion actual
        # para comprobar que el ciclo actual ya NO depende de rangos de fecha_asignacion
        AsignacionPlanEstudio.objects.filter(pk=self.asig_luis.pk).update(trimestre_lectivo="2025-I")

        data_actual = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual(data_actual['total_asignaciones_ciclo'], 3)
        self.assertEqual(data_actual['total_asignaciones_historico'], 4)
        self.assertEqual([d['username'] for d in data_actual['docentes']], ['ana_gomez', 'carlos_ruiz'])

        data_todas = construir_ranking_docentes(alcance='todas', alcance_explicito=True)
        self.assertEqual([d['username'] for d in data_todas['docentes']], ['ana_gomez', 'carlos_ruiz', 'luis_mora'])

        # Filtro explícito por trimestre_lectivo encuentra a Luis en 2025-I
        data_2025 = construir_ranking_docentes(trimestre_lectivo="2025-I")
        self.assertEqual([d['username'] for d in data_2025['docentes']], ['luis_mora'])

        # Si ninguna asignación pertenece al trimestre lectivo actual y no hay parámetro explícito, hace fallback a 'todas'
        AsignacionPlanEstudio.objects.all().update(trimestre_lectivo="2025-I")
        data_auto = construir_ranking_docentes(alcance='actual', alcance_explicito=False)
        self.assertEqual(data_auto['alcance'], 'todas')
        self.assertTrue(data_auto['auto_fallback_todas'])
        self.assertEqual(len(data_auto['docentes']), 3)

        # Con alcance explícito 'actual', respeta el filtro estricto aunque quede vacío
        data_estricto = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual(data_estricto['alcance'], 'actual')
        self.assertFalse(data_estricto['auto_fallback_todas'])
        self.assertEqual(len(data_estricto['docentes']), 0)

    def test_filtros_vista_ranking_docentes(self):
        client = Client()
        client.login(username="carlos_ruiz", password="docpassword")
        url = reverse('ranking_docentes')

        # Vista principal muestra los 3 docentes y el badge "Tú" para carlos_ruiz
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn("Ranking de Cumplimiento Docente", html)
        self.assertIn("Ana Gómez", html)
        self.assertIn("Carlos Ruiz", html)
        self.assertIn("Luis Mora", html)
        self.assertIn("Tú", html)
        self.assertIn("Ver asignaturas", html)
        self.assertIn('class="highlight-main"', html)
        self.assertIn('class="highlight-text"', html)
        self.assertIn('class="highlight-name"', html)
        self.assertIn('highlight-score', html)
        self.assertNotIn("min-width-0", html)
        self.assertNotIn("text-truncate", html)
        self.assertNotIn("fa-file-signature text-primary", html)
        self.assertNotIn("fa-book-reader text-info", html)

        # Filtro por estado=sin_avance -> solo Luis Mora con puesto #3
        resp_sin = client.get(url, {'estado': 'sin_avance'})
        self.assertEqual(resp_sin.status_code, 200)
        self.assertEqual(len(resp_sin.context['docentes']), 1)
        self.assertEqual(resp_sin.context['docentes'][0]['username'], 'luis_mora')
        self.assertEqual(resp_sin.context['docentes'][0]['puesto'], 3)

        # Filtro por carrera Derecho -> solo Luis Mora
        resp_der = client.get(url, {'carrera': self.carrera_der.id})
        self.assertEqual(resp_der.status_code, 200)
        self.assertEqual([d['username'] for d in resp_der.context['docentes']], ['luis_mora'])

        # Búsqueda por asignatura
        resp_q = client.get(url, {'q': 'Algoritmos'})
        self.assertEqual(resp_q.status_code, 200)
        self.assertEqual([d['username'] for d in resp_q.context['docentes']], ['ana_gomez'])

        # Filtro por trimestre del plan
        resp_trim = client.get(url, {'trimestre': 'II'})
        self.assertEqual(resp_trim.status_code, 200)
        self.assertEqual([d['username'] for d in resp_trim.context['docentes']], ['carlos_ruiz'])

    def test_rangos_ciclo_actual(self):
        self.assertEqual(
            obtener_rango_ciclo_actual(datetime.date(2026, 4, 15))[:2],
            (datetime.date(2026, 3, 1), datetime.date(2026, 5, 31))
        )
        self.assertEqual(
            obtener_rango_ciclo_actual(datetime.date(2026, 7, 1))[:2],
            (datetime.date(2026, 6, 1), datetime.date(2026, 8, 31))
        )
        self.assertEqual(
            obtener_rango_ciclo_actual(datetime.date(2026, 11, 17))[:2],
            (datetime.date(2026, 9, 1), datetime.date(2026, 11, 30))
        )
        self.assertEqual(
            obtener_rango_ciclo_actual(datetime.date(2026, 12, 10))[:2],
            (datetime.date(2026, 12, 1), datetime.date(2027, 2, 28))
        )
        self.assertEqual(
            obtener_rango_ciclo_actual(datetime.date(2024, 1, 20))[:2],
            (datetime.date(2023, 12, 1), datetime.date(2024, 2, 29))
        )

    def test_ranking_trimestre_lectivo_futuro_multi_ciclo_y_ui_filtros(self):
        # Crear una asignación para Ana en un trimestre lectivo futuro (con fecha_asignacion actual)
        # y un histórico de Luis en 2025-I para verificar orden cronológico, ciclos_futuros y UI.
        hoy = timezone.localdate()
        futuro_codigo = f"{hoy.year + 1}-I"
        asig_futuro = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_top,
            plan_de_estudio=self.plan_4,
            trimestre_lectivo=futuro_codigo,
            bloque="Primer bloque - 8:00",
        )
        sil_futuro = Silabo.objects.create(
            codigo=self.plan_4.codigo,
            encuentros=1,
            fecha=datetime.date(hoy.year + 1, 3, 7),
            unidad="Unidad I",
            nombre_de_la_unidad="Intro Futuro",
            contenido_tematico="Contenido",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Det 1",
            tiempo_primer_momento=15,
            recursos_primer_momento="Pizarra",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Teoría",
            tipo_segundo_momento_practica="Taller",
            clase_practica="Práctica",
            tiempo_segundo_momento_teorica=30,
            tiempo_segundo_momento_practica=30,
            recursos_segundo_momento="Proyector",
            tipo_tercer_momento=["Orientación del estudio independiente"],
            detalle_tercer_momento="Det 3",
            tiempo_tercer_momento=15,
            recursos_tercer_momento="Guía",
            eje_transversal=["Investigación"],
            detalle_eje_transversal="Eje",
            asignacion_plan=asig_futuro,
        )
        Guia.objects.create(
            silabo=sil_futuro,
            numero_encuentro=1,
            fecha=datetime.date(hoy.year + 1, 3, 7),
            unidad="Unidad I",
            nombre_de_la_unidad="Intro Futuro",
            tipo_objetivo_1="Conceptual",
            objetivo_aprendizaje_1="Obj",
            contenido_tematico_1="Cont",
            actividad_aprendizaje_1="Act",
            tecnica_evaluacion_1="Observación",
            tipo_evaluacion_1="Formativa",
            instrumento_evaluacion_1="Rúbrica",
            criterios_evaluacion_1="Crit",
            agente_evaluador_1=["Heteroevaluación"],
            tiempo_minutos_1=45,
            recursos_didacticos_1="PDF",
            periodo_tiempo_programado_1="I Corte Evaluativo",
            puntaje_1=10,
            fecha_entrega_1=datetime.date(hoy.year + 1, 3, 12),
        )
        AsignacionPlanEstudio.objects.create(
            usuario=self.docente_cero,
            plan_de_estudio=self.plan_1,
            trimestre_lectivo="2025-I",
            bloque="Segundo bloque - 10:20",
        )

        # Verificar ciclos_futuros, conteos y orden cronológico descendente de opciones disponibles
        data_actual = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual([c['codigo'] for c in data_actual['ciclos_futuros']], [futuro_codigo])
        self.assertEqual(data_actual['ciclos_futuros'][0]['total'], 1)
        codes_disp = [code for code, _ in data_actual['trimestres_lectivos_disponibles']]
        self.assertEqual(codes_disp[0], futuro_codigo)
        self.assertEqual(codes_disp[-1], '2025-I')

        # En alcance actual NO se contamina con la asignación futura aunque se haya creado hoy
        ana_actual = next(d for d in data_actual['docentes'] if d['username'] == 'ana_gomez')
        self.assertEqual(ana_actual['total_asignaciones'], 1)

        # Vista HTTP filtrada por trimestre_lectivo futuro: no deja activo 'Ciclo Actual' y calcula métricas exactas
        client = Client()
        client.login(username="ana_gomez", password="docpassword")
        url = reverse('ranking_docentes')
        resp_fut = client.get(url, {'trimestre_lectivo': futuro_codigo})
        self.assertEqual(resp_fut.status_code, 200)
        self.assertEqual(len(resp_fut.context['docentes']), 1)
        ana_fut = resp_fut.context['docentes'][0]
        self.assertEqual(ana_fut['total_asignaciones'], 1)
        self.assertEqual(ana_fut['total_silabos'], 1)
        self.assertEqual(ana_fut['total_guias'], 1)
        self.assertEqual(ana_fut['porcentaje_general'], 8.3)
        html_fut = resp_fut.content.decode('utf-8')
        self.assertIn(f"{hoy.year + 1} - Trimestre I", html_fut)
        self.assertNotIn('class="btn pill-switch-btn active">\n                <i class="fas fa-calendar-check">', html_fut)

        # Al combinar filtro de trimestre_lectivo futuro con estado sin coincidencias, muestra estado vacío de filtros (no ciclo vacío)
        resp_vacio = client.get(url, {'trimestre_lectivo': futuro_codigo, 'estado': 'cumplido'})
        self.assertEqual(resp_vacio.status_code, 200)
        html_vacio = resp_vacio.content.decode('utf-8')
        self.assertIn("Limpiar filtros", html_vacio)
        self.assertNotIn("No hay asignaciones registradas dentro de", html_vacio)

        # Cuando la fecha de referencia entra al ciclo futuro, ese ciclo deja de ser futuro y pasa a Ciclo Actual
        data_en_futuro = construir_ranking_docentes(
            alcance='actual',
            alcance_explicito=True,
            fecha_ref=datetime.date(hoy.year + 1, 3, 15),
        )
        self.assertEqual(data_en_futuro['ciclo_codigo_actual'], futuro_codigo)
        self.assertEqual(data_en_futuro['ciclos_futuros'], [])
        self.assertEqual(data_en_futuro['total_asignaciones_ciclo'], 1)

    def test_visibilidad_toggle_admin_y_acceso(self):
        ranking_url = reverse('ranking_docentes')
        toggle_url = reverse('admin:plan_de_estudio_copiaseguridad_toggle_ranking_docentes')

        docente_client = Client()
        docente_client.login(username="ana_gomez", password="docpassword")

        # Docente no puede modificar el toggle de admin
        resp_forbidden = docente_client.post(toggle_url, {'accion': 'desactivar'})
        self.assertEqual(resp_forbidden.status_code, 302)
        self.assertIn('/admin/login/', resp_forbidden['Location'])
        self.assertTrue(ConfiguracionSistema.get_solo().mostrar_ranking_docentes)

        # Con visibilidad activa, el enlace aparece en inicio y accede al ranking
        resp_inicio_on = docente_client.get(reverse('inicio'))
        self.assertContains(resp_inicio_on, "Ranking Docente")
        self.assertEqual(docente_client.get(ranking_url).status_code, 200)

        # Admin desactiva visibilidad para docentes
        admin_client = Client()
        admin_client.login(username="admin_rank", password="adminpassword")
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')
        resp_cfg_on = admin_client.get(changelist_url)
        self.assertContains(resp_cfg_on, "Ranking de Cumplimiento Docente")
        self.assertContains(resp_cfg_on, "Visible para docentes")

        resp_off = admin_client.post(toggle_url, {'accion': 'desactivar'})
        self.assertEqual(resp_off.status_code, 302)
        self.assertFalse(ConfiguracionSistema.get_solo().mostrar_ranking_docentes)

        resp_cfg_off = admin_client.get(changelist_url)
        self.assertContains(resp_cfg_off, "Solo administradores")

        # Docente ya no ve el enlace ni puede entrar al ranking (redirige a inicio)
        resp_inicio_off = docente_client.get(reverse('inicio'))
        self.assertNotContains(resp_inicio_off, ranking_url)
        resp_blocked = docente_client.get(ranking_url)
        self.assertEqual(resp_blocked.status_code, 302)
        self.assertEqual(resp_blocked['Location'], reverse('inicio'))

        # Admin sigue pudiendo acceder al ranking
        resp_admin_rank = admin_client.get(ranking_url)
        self.assertEqual(resp_admin_rank.status_code, 200)
        self.assertContains(resp_admin_rank, "Modo solo administradores")

        # Admin reactiva visibilidad
        admin_client.post(toggle_url, {'accion': 'activar'})
        self.assertTrue(ConfiguracionSistema.get_solo().mostrar_ranking_docentes)
        self.assertEqual(docente_client.get(ranking_url).status_code, 200)


class AINormalizerAndContratoFase1Test(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.patcher_crear.start()
        self.patcher_subir.start()

        self.usuario = User.objects.create_user(username="docente_f1", password="pwd")
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas F1", codigo="ISF1", cine_2011=111, cine_2013=222,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Bases de Datos F1")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="I", pensol="2026",
            codigo="IS1826", asignatura=self.asignatura,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        self.programa = ProgramaAsignatura2026.objects.create(
            plan_estudio=self.plan,
            fundamentacion="Fundamentación BD",
            relacion_unidades="4 unidades",
            aportes_perfil="Perfil",
            valores="Valores",
            ejes_transversales="Tecnología",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
            unidad_1_nombre="Modelo Relacional",
            unidad_1_horas_teoricas=2,
            unidad_1_horas_practicas=2,
            unidad_1_horas_independientes=10,
            unidad_1_objetivos_especificos="Analizar modelo relacional",
            unidad_1_contenido="1. Modelo relacional y SQL.",
            unidad_1_mediacion="Exposición y taller.",
            unidad_1_evaluacion="Rúbrica.",
        )
        self.client = Client()
        self.client.login(username="docente_f1", password="pwd")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def test_procesar_respuesta_ai_sin_ruido_legado_en_silabo_y_guia(self):
        from plan_de_estudio.ai_generators import procesar_respuesta_ai

        raw = """```json
        {"codigo": "IS1826", "unidad": "Unidad I", "nombre_de_la_unidad": "What's new"}
        ```"""
        data = procesar_respuesta_ai(raw, tipo_respuesta="silabo")
        self.assertEqual(data["codigo"], "IS1826")
        self.assertEqual(data["nombre_de_la_unidad"], "What's new")
        self.assertNotIn("instrumento_cuaderno", data)
        self.assertNotIn("evaluacion_sumativa", data)
        self.assertNotIn("tiempo_estimado", data)

        with self.assertRaises(ValueError):
            procesar_respuesta_ai("Texto libre sin JSON", tipo_respuesta="silabo")

    def test_normalizar_respuesta_silabo_repara_aliases_y_tiempo_segundo_momento(self):
        from plan_de_estudio.utils.ai_normalizer import normalizar_respuesta_silabo

        raw_ai = {
            "codigo": "IBD-INVENTADO",
            "encuentros": 99,
            "fecha": "2026-11-17",
            "unidad": "Unidad 1",
            "nombre_de_la_unidad": "Modelo Relacional",
            "contenido_tematico": "Esquema relacional",
            "objetivo_conceptual": "Comprender",
            "objetivo_procedimental": "Aplicar",
            "objetivo_actitudinal": "Valorar",
            "tipo_primer_momento": "Evaluación diagnostica",
            "detalle_primer_momento": "Diagnóstico",
            "tiempo_primer_momento": "15 min",
            "recursos_primer_momento": "Pizarra",
            "tipo_segundo_momento_claseteoria": "conferencia",
            "clase_teorica": "Exposición",
            "tipo_segundo_momento_practica": "taller",
            "clase_practica": "Práctica",
            "tiempo_segundo_momento": 65,
            "recursos_segundo_momento": "PC",
            "tipo_tercer_momento": "Orientación del estudio independiente, Realimentación del aprendizaje",
            "detalle_tercer_momento": "Cierre",
            "tiempo_tercer_momento": 10,
            "recursos_tercer_momento": "Guía",
            "eje_transversal": "Tecnología de la información y comunicación",
            "detalle_eje_transversal": "Uso de SGBD",
            "actividad_aprendizaje": "Análisis grupal",
            "tecnica_evaluacion": "Participación en clases de manera objetiva",
            "tipo_evaluacion": "Diagnóstica y Formativa",
            "periodo_tiempo_programado": "Primer corte",
            "tiempo_minutos": 25,
            "agente_evaluador": ["Heteroevaluación"],
            "instrumento_evaluacion": "Lista de cotejo",
            "criterios_evaluacion": ["Claridad", "Precisión"],
            "puntaje": 10,
        }
        norm = normalizar_respuesta_silabo(raw_ai, plan_codigo="IS1826", encuentro=1)
        self.assertEqual(norm["codigo"], "IS1826")
        self.assertEqual(norm["encuentros"], 1)
        self.assertEqual(norm["unidad"], "Unidad I")
        self.assertEqual(norm["tiempo_primer_momento"], 15)
        self.assertEqual(norm["tiempo_segundo_momento_teorica"], 32)
        self.assertEqual(norm["tiempo_segundo_momento_practica"], 33)
        self.assertEqual(norm["eje_transversal"], ["Tecnología de la información y comunicación"])
        self.assertEqual(norm["tipo_tercer_momento"], ["Orientación del estudio independiente", "Realimentación del aprendizaje"])
        self.assertEqual(norm["tecnica_evaluacion"], ["Observación"])
        self.assertEqual(norm["tipo_evaluacion"], ["Diagnóstica", "Formativa"])
        self.assertEqual(norm["instrumento_evaluacion"], "Listas de cotejo")
        self.assertEqual(norm["periodo_tiempo_programado"], "I Corte Evaluativo")
        self.assertEqual(norm["criterios_evaluacion"], "Claridad\nPrecisión")

    def test_generar_y_guardar_silabo_y_guia_directo_sin_400(self):
        fake_silabo_ai = json.dumps({
            "codigo": "FALSO-999",
            "encuentros": 1,
            "fecha": "2026-11-17",
            "unidad": "Unidad I",
            "nombre_de_la_unidad": "Modelo Relacional",
            "contenido_tematico": "1. Modelo relacional",
            "objetivo_conceptual": "Analizar",
            "objetivo_procedimental": "Diseñar",
            "objetivo_actitudinal": "Valorar",
            "tipo_primer_momento": "Presentación de asignatura",
            "detalle_primer_momento": "Encuadre",
            "tiempo_primer_momento": 15,
            "recursos_primer_momento": "Diapositivas",
            "tipo_segundo_momento_claseteoria": "Conferencia",
            "clase_teorica": "Exposición del tema",
            "tiempo_segundo_momento_teorica": 45,
            "tipo_segundo_momento_practica": "Taller",
            "clase_practica": "Taller práctico",
            "tiempo_segundo_momento_practica": 45,
            "recursos_segundo_momento": "Computadora",
            "tipo_tercer_momento": ["Orientación del estudio independiente"],
            "detalle_tercer_momento": "Orientación final",
            "tiempo_tercer_momento": 15,
            "recursos_tercer_momento": "Guía",
            "eje_transversal": ["Tecnología de la información y comunicación"],
            "detalle_eje_transversal": "Uso de SQL",
            "actividad_aprendizaje": "Ejercicio en clase",
            "tecnica_evaluacion": "Resolución de problemas",
            "tipo_evaluacion": "Diagnóstica y Formativa",
            "periodo_tiempo_programado": "I Corte Evaluativo",
            "tiempo_minutos": 20,
            "agente_evaluador": ["Heteroevaluación"],
            "instrumento_evaluacion": "Lista de cotejo",
            "criterios_evaluacion": "Criterio 1",
            "puntaje": 10,
        })

        with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=fake_silabo_ai) as mock_google:
            resp_gen = self.client.post(reverse('generar_silabo'), {
                'encuentro': '1',
                'plan': str(self.asignacion.id),
                'modelo_select': 'google',
            })
            self.assertEqual(resp_gen.status_code, 200)
            prompt_usado = mock_google.call_args[0][0]
            cfg_usado = mock_google.call_args[0][1]
            self.assertIn("TÉCNICAS DE EVALUACIÓN DISPONIBLES", prompt_usado)
            self.assertIn("INSTRUMENTOS DE EVALUACIÓN DISPONIBLES", prompt_usado)
            self.assertIn("tiempo_segundo_momento_teorica", prompt_usado)
            self.assertEqual(cfg_usado.get("response_mime_type"), "application/json")

            silabo_data = resp_gen.json()["silabo_data"]
            self.assertEqual(silabo_data["codigo"], "IS1826")
            self.assertEqual(silabo_data["instrumento_evaluacion"], "Listas de cotejo")
            self.assertEqual(silabo_data["tipo_evaluacion"], ["Diagnóstica", "Formativa"])

        resp_save = self.client.post(
            reverse('guardar_silabo', args=[self.asignacion.id]),
            data=silabo_data,
        )
        self.assertEqual(resp_save.status_code, 200, resp_save.content.decode('utf-8'))
        silabo_id = resp_save.json()["silabo_id"]

        fake_guia_ai = json.dumps({
            "numero_encuentro": 1,
            "fecha": "2026-11-17",
            "unidad": "Unidad I",
            "nombre_de_la_unidad": "Modelo Relacional",
            "tarea_1": {
                "tipo_objetivo": "Conceptual",
                "objetivo_aprendizaje": "Obj 1",
                "contenido_tematico": "Tema 1",
                "actividad_aprendizaje": "Act 1",
                "tecnica_evaluacion": "Mapa conceptual",
                "tipo_evaluacion": "Formativa",
                "instrumento_evaluacion": "Lista de cotejo",
                "criterios_evaluacion": ["C1", "C2"],
                "agente_evaluador": "heteroevaluacion",
                "tiempo_minutos": 60,
                "recursos_didacticos": "Libro",
                "periodo_tiempo_programado": "I Corte Evaluativo",
                "puntaje": 70,
                "fecha_entrega": "2026-11-20",
            },
            "tarea_2": {
                "tipo_objetivo": "Procedimental",
                "objetivo_aprendizaje": "Obj 2",
                "contenido_tematico": "Tema 2",
                "actividad_aprendizaje": "Act 2",
                "tecnica_evaluacion": "Proyecto",
                "tipo_evaluacion": "Sumativa",
                "instrumento_evaluacion": "Rúbrica",
                "criterios_evaluacion": "C3",
                "agente_evaluador": ["Coevaluación"],
                "tiempo_minutos": 90,
                "recursos_didacticos": "SQL",
                "periodo_tiempo_programado": "I Corte Evaluativo",
                "puntaje": 60,
                "fecha_entrega": "2026-11-22",
            },
        })
        with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=fake_guia_ai):
            resp_g_gen = self.client.post(reverse('generar_estudio_independiente'), {
                'silabo_id': str(silabo_id),
                'encuentro': '1',
                'modelo': 'google',
                'numero_actividades': '2',
            })
            self.assertEqual(resp_g_gen.status_code, 200)
            guia_datos = resp_g_gen.json()["datos"]
            self.assertEqual(guia_datos["tecnica_evaluacion_1"], "Organizador gráfico")
            self.assertEqual(guia_datos["instrumento_evaluacion_1"], "Listas de cotejo")
            self.assertEqual(guia_datos["agente_evaluador_1"], ["Heteroevaluación"])
            total_guia = guia_datos["puntaje_1"] + guia_datos["puntaje_2"]
            self.assertGreater(total_guia, 0)
            self.assertLessEqual(total_guia, 25)
            self.assertLess(silabo_data["puntaje"] + total_guia, 100)
            self.assertNotIn("tipo_objetivo_3", guia_datos)

        resp_g_save = self.client.post(
            reverse('guardar_guia', args=[silabo_id]),
            data=json.dumps(guia_datos),
            content_type="application/json",
        )
        self.assertEqual(resp_g_save.status_code, 200, resp_g_save.content.decode('utf-8'))


class CurriculumPlannerFase2Test(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.patcher_crear.start()
        self.patcher_subir.start()

        self.usuario = User.objects.create_user(username="docente_f2", password="pwd")
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas F2", codigo="ISF2", cine_2011=111, cine_2013=222,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asig_prog = Asignatura.objects.create(nombre="Bases de Datos II F2")
        self.plan_prog = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="II", pensol="2026",
            codigo="IS2826", asignatura=self.asig_prog,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        self.asignacion_prog = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan_prog,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        self.programa = ProgramaAsignatura2026.objects.create(
            plan_estudio=self.plan_prog,
            fundamentacion="Fundamentación BD II",
            relacion_unidades="3 unidades progresivas",
            aportes_perfil="Perfil",
            valores="Valores",
            ejes_transversales="Tecnología",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
            unidad_1_nombre="Normalización Avanzada",
            unidad_1_horas_teoricas=4,
            unidad_1_horas_practicas=6,
            unidad_1_horas_independientes=25,
            unidad_1_objetivos_especificos="Aplicar formas normales",
            unidad_1_contenido="1FN, 2FN, 3FN, FNBC.",
            unidad_2_nombre="Optimización de Consultas",
            unidad_2_horas_teoricas=4,
            unidad_2_horas_practicas=6,
            unidad_2_horas_independientes=25,
            unidad_2_objetivos_especificos="Optimizar índices",
            unidad_2_contenido="Índices B-Tree, planes de ejecución.",
            unidad_3_nombre="Transacciones y Concurrencia",
            unidad_3_horas_teoricas=2,
            unidad_3_horas_practicas=2,
            unidad_3_horas_independientes=20,
            unidad_3_objetivos_especificos="Controlar concurrencia",
            unidad_3_contenido="ACID, bloqueos, recuperación.",
        )

        self.client = Client()
        self.client.login(username="docente_f2", password="pwd")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def test_plan_tematico_multitud_y_ambas_relaciones(self):
        from plan_de_estudio.utils.curriculum_planner import (
            construir_mapa_maestro,
            extraer_contexto_asignatura,
        )

        # Caso A: PlanTematico enlazado vía relación inversa plantematicos_asociados (4 unidades)
        asig_inv = Asignatura.objects.create(nombre="Ingeniería Software Legado")
        plan_inv = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="II", trimestre="I", pensol="2018",
            codigo="ISL2018", asignatura=asig_inv,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        PlanTematico.objects.create(
            plan_estudio=plan_inv,
            unidades="Primera unidad", nombre_de_la_unidad="Requisitos",
            objetivo_especificos="Obj 1", plan_analitico="Elicitación e historias",
            recomendaciones_metodologicas="Met 1", forma_de_evaluacion="Ev 1",
            relacion_eje_contenido_launidad="Eje 1",
            unidades_2="Segunda unidad", nombre_de_la_unidad_2="Diseño UML",
            objetivo_especificos_2="Obj 2", plan_analitico_2="Diagramas de clases y secuencia",
            unidades_3="Tercera unidad", nombre_de_la_unidad_3="Pruebas de Software",
            objetivo_especificos_3="Obj 3", plan_analitico_3="Pruebas unitarias e integración",
            unidades_4="Cuarta unidad", nombre_de_la_unidad_4="Mantenimiento",
            objetivo_especificos_4="Obj 4", plan_analitico_4="Refactorización y CI/CD",
        )
        ctx_inv = extraer_contexto_asignatura(plan_inv)
        self.assertEqual(ctx_inv["total_unidades"], 4)
        mapa_inv = construir_mapa_maestro(ctx_inv["unidades"])
        self.assertEqual(mapa_inv["por_encuentro"][1]["unidad_romano"], "Unidad I")
        self.assertEqual(mapa_inv["por_encuentro"][9]["unidad_romano"], "Unidad III")
        self.assertEqual(mapa_inv["por_encuentro"][11]["unidad_romano"], "Unidad IV")

        # Caso B: PlanTematico enlazado vía FK directa plan_tematico_ref (5 unidades)
        pt_directo = PlanTematico.objects.create(
            unidades="Primera unidad", nombre_de_la_unidad="Unidad Base 1",
            objetivo_especificos="O1", plan_analitico="C1",
            recomendaciones_metodologicas="M1", forma_de_evaluacion="E1",
            relacion_eje_contenido_launidad="R1",
            unidades_2="Segunda unidad", nombre_de_la_unidad_2="Unidad Base 2", plan_analitico_2="C2",
            unidades_3="Tercera unidad", nombre_de_la_unidad_3="Unidad Base 3", plan_analitico_3="C3",
            unidades_4="Cuarta unidad", nombre_de_la_unidad_4="Unidad Base 4", plan_analitico_4="C4",
            unidades_5="Quinta unidad", nombre_de_la_unidad_5="Unidad Base 5", plan_analitico_5="C5",
        )
        asig_dir = Asignatura.objects.create(nombre="Redes Legado")
        plan_dir = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="I", pensol="2018",
            codigo="RED2018", asignatura=asig_dir,
            plan_tematico_ref=pt_directo,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        ctx_dir = extraer_contexto_asignatura(plan_dir)
        self.assertEqual(ctx_dir["total_unidades"], 5)
        mapa_dir = construir_mapa_maestro(ctx_dir["unidades"])
        self.assertEqual(mapa_dir["por_encuentro"][11]["unidad_romano"], "Unidad V")

    def test_11_encuentros_respetan_100_pts_por_corte_horas_fechas_y_prompt_compacto(self):
        from plan_de_estudio.utils.curriculum_planner import calcular_puntajes_por_corte

        prompts_silabo = {}
        prompts_guia = {}

        for enc in range(1, 12):
            # IA deliberadamente infla puntajes, fechas fuera de rango y tiempos cortos
            fake_silabo = json.dumps({
                "codigo": "MALO",
                "encuentros": enc,
                "fecha": "2024-01-01",
                "unidad": "Unidad I",
                "nombre_de_la_unidad": "Equivocada",
                "contenido_tematico": f"Contenido único encuentro {enc}",
                "objetivo_conceptual": f"OC {enc}",
                "objetivo_procedimental": f"OP {enc}",
                "objetivo_actitudinal": f"OA {enc}",
                "tipo_primer_momento": "Valoración del trabajo independiente",
                "detalle_primer_momento": f"Inicio {enc}",
                "tiempo_primer_momento": 10,
                "recursos_primer_momento": "Pizarra",
                "tipo_segundo_momento_claseteoria": "Conferencia",
                "clase_teorica": f"Teoría {enc}",
                "tiempo_segundo_momento_teorica": 25,
                "tipo_segundo_momento_practica": "Taller",
                "clase_practica": f"Práctica {enc}",
                "tiempo_segundo_momento_practica": 30,
                "recursos_segundo_momento": "SQL",
                "tipo_tercer_momento": ["Orientación del estudio independiente"],
                "detalle_tercer_momento": f"Cierre {enc}",
                "tiempo_tercer_momento": 10,
                "recursos_tercer_momento": "Guía",
                "eje_transversal": ["Tecnología de la información y comunicación"],
                "detalle_eje_transversal": "Uso de BD",
                "actividad_aprendizaje": f"Actividad presencial exclusiva {enc}",
                "tecnica_evaluacion": ["Estudio de casos"],
                "tipo_evaluacion": ["Formativa"],
                "periodo_tiempo_programado": "III Corte Evaluativo",
                "tiempo_minutos": 20,
                "agente_evaluador": ["Heteroevaluación"],
                "instrumento_evaluacion": "Rúbrica",
                "criterios_evaluacion": "Precisión",
                "puntaje": 45,
            })

            def _fake_guia_json(num):
                return json.dumps({
                    "numero_encuentro": num,
                    "fecha": "2024-02-01",
                    "unidad": "Unidad I",
                    "nombre_de_la_unidad": "Equivocada",
                    **{
                        f"tarea_{t}": {
                            "tipo_objetivo": "Conceptual" if t % 2 else "Procedimental",
                            "objetivo_aprendizaje": f"Obj G{num}-T{t}",
                            "contenido_tematico": f"TemaGuia E{num} T{t}",
                            "actividad_aprendizaje": f"TareaAutonoma E{num} T{t}",
                            "tecnica_evaluacion": "Resolución de problemas",
                            "tipo_evaluacion": "Sumativa",
                            "instrumento_evaluacion": "Rúbrica",
                            "criterios_evaluacion": "Criterio",
                            "agente_evaluador": ["Heteroevaluación"],
                            "tiempo_minutos": 30,
                            "recursos_didacticos": "Manual",
                            "periodo_tiempo_programado": "I Corte Evaluativo",
                            "puntaje": 25,
                            "fecha_entrega": "2030-05-01",
                        }
                        for t in range(1, 5)
                    },
                })

            with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=fake_silabo) as m_s:
                r_s_gen = self.client.post(reverse('generar_silabo'), {
                    'encuentro': str(enc),
                    'plan': str(self.asignacion_prog.id),
                    'modelo_select': 'google',
                })
                self.assertEqual(r_s_gen.status_code, 200, r_s_gen.content.decode('utf-8'))
                prompts_silabo[enc] = m_s.call_args[0][0]
                s_data = r_s_gen.json()["silabo_data"]

            r_s_save = self.client.post(reverse('guardar_silabo', args=[self.asignacion_prog.id]), data=s_data)
            self.assertEqual(r_s_save.status_code, 200, r_s_save.content.decode('utf-8'))
            silabo_id = r_s_save.json()["silabo_id"]

            if enc <= 10:
                with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=_fake_guia_json(enc)) as m_g:
                    r_g_gen = self.client.post(reverse('generar_estudio_independiente'), {
                        'silabo_id': str(silabo_id),
                        'encuentro': str(enc),
                        'modelo': 'google',
                        'numero_actividades': '4',
                    })
                    self.assertEqual(r_g_gen.status_code, 200, r_g_gen.content.decode('utf-8'))
                    prompts_guia[enc] = m_g.call_args[0][0]
                    g_data = r_g_gen.json()["datos"]

                r_g_save = self.client.post(
                    reverse('guardar_guia', args=[silabo_id]),
                    data=json.dumps(g_data),
                    content_type="application/json",
                )
                self.assertEqual(r_g_save.status_code, 200, r_g_save.content.decode('utf-8'))
            else:
                # Por defecto (encuentro 11 de la guía desactivado), el backend rechaza generar o guardar guía 11
                r_g11_gen = self.client.post(reverse('generar_estudio_independiente'), {
                    'silabo_id': str(silabo_id),
                    'encuentro': '11',
                    'modelo': 'google',
                    'numero_actividades': '4',
                })
                self.assertEqual(r_g11_gen.status_code, 400)
                r_g11_save = self.client.post(
                    reverse('guardar_guia', args=[silabo_id]),
                    data=json.dumps({
                        "numero_encuentro": 11,
                        "fecha": s_data["fecha"],
                        "unidad": s_data["unidad"],
                        "nombre_de_la_unidad": s_data["nombre_de_la_unidad"],
                    }),
                    content_type="application/json",
                )
                self.assertEqual(r_g11_save.status_code, 400)

            # En encuentros de examen (4, 8 y 11) se crea el Proyecto de Examen para completar los 100 pts del corte y desbloquear el siguiente sílabo
            if enc in (4, 8, 11):
                num_eval = {4: 1, 8: 2, 11: 3}[enc]
                from plan_de_estudio.utils.exam_utils import calcular_puntaje_examen_disponible
                info_ex = calcular_puntaje_examen_disponible(self.asignacion_prog, num_eval)
                pts_rest = info_ex["puntaje_disponible"]
                self.assertGreater(pts_rest, 0)
                p1 = pts_rest // 2
                p2 = pts_rest - p1
                texto_largo = " ".join(
                    f"Ejercicio analítico detallado {k} sobre los contenidos del corte {num_eval} con contexto práctico y requerimientos técnicos completos."
                    for k in range(1, 22)
                )
                resp_ex = self.client.post(
                    reverse('guardar_examen', args=[self.asignacion_prog.id]),
                    data=json.dumps({
                        "numero_evaluacion": num_eval,
                        "fecha": s_data["fecha"],
                        "anio_lectivo": "2026",
                        "trimestre": "III",
                        "carrera_texto": "Ingeniería de Sistemas F2",
                        "modalidad": "Por encuentro",
                        "tipo_examen": "De corte evaluativo",
                        "items": [
                            {
                                "numero": "I",
                                "objetivo": f"Analizar y aplicar los fundamentos del corte {num_eval}.",
                                "ejercicios": f"I. Estudio de caso y resolución práctica.\n{texto_largo}",
                                "posibles_respuestas": f"I. Clave de solución completa.\n{texto_largo}",
                                "puntaje": p1,
                                "detalle_puntaje": f"{p1} pts",
                            },
                            {
                                "numero": "II",
                                "objetivo": f"Evaluar diseños y soluciones integrales del corte {num_eval}.",
                                "ejercicios": f"II. Desarrollo técnico argumentado.\n{texto_largo}",
                                "posibles_respuestas": f"II. Solución esperada y criterios.\n{texto_largo}",
                                "puntaje": p2,
                                "detalle_puntaje": f"{p2} pts",
                            },
                        ],
                    }),
                    content_type="application/json",
                )
                self.assertEqual(resp_ex.status_code, 200, resp_ex.content.decode('utf-8'))

        # 1. Validar regla institucional: exactamente 100 pts por Corte Evaluativo (300 total)
        #    divididos en 11 sílabos + 10 guías (50 acumulado) + 3 exámenes (50 examen) = 100 por corte
        cortes = calcular_puntajes_por_corte(self.asignacion_prog)
        self.assertEqual(cortes["I Corte Evaluativo"], 100)
        self.assertEqual(cortes["II Corte Evaluativo"], 100)
        self.assertEqual(cortes["III Corte Evaluativo"], 100)

        # 2. Validar cobertura de todas las unidades del programa, horas (11 sílabos / 10 guías) y progresión semanal
        silabos = list(Silabo.objects.filter(asignacion_plan=self.asignacion_prog).order_by("encuentros"))
        guias = list(Guia.objects.filter(silabo__asignacion_plan=self.asignacion_prog).order_by("numero_encuentro"))
        self.assertEqual(len(silabos), 11)
        self.assertEqual(len(guias), 10)

        unidades_usadas = [s.unidad for s in silabos]
        self.assertIn("Unidad I", unidades_usadas)
        self.assertIn("Unidad II", unidades_usadas)
        self.assertIn("Unidad III", unidades_usadas)
        self.assertEqual(silabos[-1].unidad, "Unidad III")

        total_min_clase = sum(
            s.tiempo_primer_momento + s.tiempo_segundo_momento_teorica + s.tiempo_segundo_momento_practica + s.tiempo_tercer_momento
            for s in silabos
        )
        self.assertAlmostEqual(total_min_clase, 24 * 60, delta=30)

        total_min_indep = sum(
            (g.tiempo_minutos_1 or 0) + (g.tiempo_minutos_2 or 0) + (g.tiempo_minutos_3 or 0) + (g.tiempo_minutos_4 or 0)
            for g in guias
        )
        self.assertAlmostEqual(total_min_indep, 70 * 60, delta=45)

        for idx in range(1, len(silabos)):
            self.assertEqual((silabos[idx].fecha - silabos[idx - 1].fecha).days, 7)

        # 3. En Encuentro 10 (última guía) las fechas de entrega ocurren antes del último encuentro (E11),
        #    y en Encuentro 11 el sílabo cierra con Realimentación sin orientar tarea/estudio independiente
        g10 = guias[-1]
        s11 = silabos[-1]
        for n in range(1, 5):
            fecha_ent = getattr(g10, f"fecha_entrega_{n}")
            self.assertLessEqual(fecha_ent, s11.fecha)
        self.assertEqual(list(s11.tipo_tercer_momento), ["Realimentación del aprendizaje"])

        # 4. Los prompts reflejan 10 guías / 11 sílabos, incluyen tareas previas T1..T4 y se mantienen compactos
        self.assertIn("TareaAutonoma E1 T4", prompts_silabo[11])
        self.assertIn("TareaAutonoma E10 T4", prompts_silabo[11])
        self.assertIn("SIN GUÍA DE ESTUDIO INDEPENDIENTE", prompts_silabo[11])
        self.assertIn("10 guías", prompts_guia[10])
        self.assertIn("TareaAutonoma E9 T4", prompts_guia[10])
        self.assertLess(len(prompts_silabo[11]), 20000)
        self.assertLess(len(prompts_guia[10]), 20000)


class Fase3FlujosYDocumentoTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.patcher_crear.start()
        self.patcher_subir.start()

        self.usuario = User.objects.create_user(username="docente_f3", password="pwd")
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería Sistemas F3", codigo="ISF3", cine_2011=111, cine_2013=222,
            area_formacion="Tecnologías", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Arquitectura Software F3")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="III", trimestre="II", pensol="2026",
            codigo="AS3026", asignatura=self.asignatura,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.usuario,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
        )
        self.client = Client()
        self.client.login(username="docente_f3", password="pwd")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def _crear_silabo(self, encuentro, puntaje=10, tiempo_minutos=15, **extra):
        defaults = dict(
            codigo=self.plan.codigo,
            asignacion_plan=self.asignacion,
            encuentros=encuentro,
            fecha=datetime.date(2026, 9, 5) + datetime.timedelta(days=7 * (encuentro - 1)),
            unidad="Unidad I",
            nombre_de_la_unidad="Fundamentos Arquitectónicos",
            contenido_tematico=f"Contenido real encuentro {encuentro}",
            objetivo_conceptual="Objetivo conceptual real",
            objetivo_procedimental="Objetivo procedimental real",
            objetivo_actitudinal="Objetivo actitudinal real",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Activación de conocimientos previos",
            tiempo_primer_momento=15,
            recursos_primer_momento="Pizarra acrílica",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Exposición dialogada real",
            tipo_segundo_momento_practica="Laboratorio",
            clase_practica="Práctica real de laboratorio sobre índices B-Tree F3",
            tiempo_segundo_momento_teorica=47,
            tiempo_segundo_momento_practica=38,
            recursos_segundo_momento="IDE Python, Dataset Real F3",
            tipo_tercer_momento=["Orientación del estudio independiente"],
            detalle_tercer_momento="Síntesis real de cierre F3",
            tiempo_tercer_momento=19,
            recursos_tercer_momento="Rúbrica digital y guía F3",
            eje_transversal=["Tecnología de la información y comunicación"],
            detalle_eje_transversal="Uso de herramientas libres",
            actividad_aprendizaje="Taller evaluativo presencial",
            tecnica_evaluacion=["Ensayo"],
            tipo_evaluacion=["Formativa"],
            periodo_tiempo_programado="I Corte Evaluativo",
            tiempo_minutos=tiempo_minutos,
            agente_evaluador=["Heteroevaluación"],
            instrumento_evaluacion="Rúbrica",
            criterios_evaluacion="Claridad y precisión técnica",
            puntaje=puntaje,
        )
        defaults.update(extra)
        return Silabo.objects.create(**defaults)

    def _payload_guia(self, encuentro):
        return {
            "numero_encuentro": encuentro,
            "fecha": (datetime.date(2026, 9, 5) + datetime.timedelta(days=7 * (encuentro - 1))).isoformat(),
            "unidad": "Unidad I",
            "nombre_de_la_unidad": "Fundamentos Arquitectónicos",
            "tipo_objetivo_1": "Conceptual",
            "objetivo_aprendizaje_1": "Obj T1",
            "contenido_tematico_1": "Tema T1",
            "actividad_aprendizaje_1": "Actividad T1",
            "tecnica_evaluacion_1": "Trabajo en grupo",
            "tipo_evaluacion_1": "Formativa",
            "instrumento_evaluacion_1": "Rúbrica",
            "criterios_evaluacion_1": "Criterio T1",
            "agente_evaluador_1": ["Heteroevaluación"],
            "tiempo_minutos_1": 90,
            "recursos_didacticos_1": "Manual F3",
            "periodo_tiempo_programado_1": "I Corte Evaluativo",
            "puntaje_1": 5,
            "fecha_entrega_1": "2026-09-11",
            "tipo_objetivo_2": "Procedimental",
            "objetivo_aprendizaje_2": "Obj T2",
            "contenido_tematico_2": "Tema T2",
            "actividad_aprendizaje_2": "Actividad T2",
            "tecnica_evaluacion_2": "Proyecto",
            "tipo_evaluacion_2": "Sumativa",
            "instrumento_evaluacion_2": "Listas de cotejo",
            "criterios_evaluacion_2": "Criterio T2",
            "agente_evaluador_2": ["Coevaluación"],
            "tiempo_minutos_2": 90,
            "recursos_didacticos_2": "Repositorio F3",
            "periodo_tiempo_programado_2": "I Corte Evaluativo",
            "puntaje_2": 5,
            "fecha_entrega_2": "2026-09-11",
            "tipo_objetivo_3": "Procedimental",
            "objetivo_aprendizaje_3": "Obj T3",
            "contenido_tematico_3": "Tema T3",
            "actividad_aprendizaje_3": "Actividad T3",
            "tecnica_evaluacion_3": "Ensayo",
            "tipo_evaluacion_3": "Formativa",
            "instrumento_evaluacion_3": "Escalas de valoración",
            "criterios_evaluacion_3": "Criterio T3",
            "agente_evaluador_3": ["Heteroevaluación"],
            "tiempo_minutos_3": 90,
            "recursos_didacticos_3": "Artículo F3",
            "periodo_tiempo_programado_3": "I Corte Evaluativo",
            "puntaje_3": 5,
            "fecha_entrega_3": "2026-09-11",
            "tipo_objetivo_4": "Actitudinal",
            "objetivo_aprendizaje_4": "Obj Unico T4",
            "contenido_tematico_4": "Tema T4",
            "actividad_aprendizaje_4": "Actividad Unica T4 Fase3",
            "tecnica_evaluacion_4": "Debate",
            "tipo_evaluacion_4": "Formativa",
            "instrumento_evaluacion_4": "Portafolio",
            "criterios_evaluacion_4": "Criterio T4",
            "agente_evaluador_4": ["Autoevaluación"],
            "tiempo_minutos_4": 110,
            "recursos_didacticos_4": "Video análisis F3",
            "periodo_tiempo_programado_4": "I Corte Evaluativo",
            "puntaje_4": 5,
            "fecha_entrega_4": "2026-09-11",
        }

    def test_ver_formulario_guia_encuentro_pendiente_y_guardar_guia_sync(self):
        # El docente crea 3 sílabos por adelantado antes de redactar sus guías
        s1 = self._crear_silabo(1)
        s2 = self._crear_silabo(2)
        s3 = self._crear_silabo(3)

        # Al abrir el formulario de guía debe seleccionar E1 (no E3 ni E4)
        resp_1 = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_1.status_code, 200)
        html_1 = resp_1.content.decode('utf-8')
        self.assertIn('data-encuentro="1"', html_1)
        self.assertIn(f'data-silabo-id="{s1.id}"', html_1)

        # Guardar guía para s1 sincroniza guias_creadas=1
        save_1 = self.client.post(
            reverse('guardar_guia', args=[s1.id]),
            data=json.dumps(self._payload_guia(1)),
            content_type="application/json",
        )
        self.assertEqual(save_1.status_code, 200)
        self.asignacion.refresh_from_db()
        self.assertEqual(self.asignacion.guias_creadas, 1)

        # Siguiente apertura debe apuntar exactamente a E2
        resp_2 = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_2.status_code, 200)
        html_2 = resp_2.content.decode('utf-8')
        self.assertIn('data-encuentro="2"', html_2)
        self.assertIn(f'data-silabo-id="{s2.id}"', html_2)

        # Guardar s2 y luego re-guardar actualización sobre s2 NO debe inflar guias_creadas
        save_2 = self.client.post(
            reverse('guardar_guia', args=[s2.id]),
            data=json.dumps(self._payload_guia(2)),
            content_type="application/json",
        )
        self.assertEqual(save_2.status_code, 200)
        resave_2 = self.client.post(
            reverse('guardar_guia', args=[s2.id]),
            data=json.dumps(self._payload_guia(2)),
            content_type="application/json",
        )
        self.assertEqual(resave_2.status_code, 200)
        self.asignacion.refresh_from_db()
        self.assertEqual(self.asignacion.guias_creadas, 2)

        # Siguiente apertura debe apuntar a E3
        resp_3 = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_3.status_code, 200)
        html_3 = resp_3.content.decode('utf-8')
        self.assertIn('data-encuentro="3"', html_3)
        self.assertIn(f'data-silabo-id="{s3.id}"', html_3)

        # Cuando todos los sílabos creados ya tienen guía y aún faltan encuentros (<11),
        # no debe reutilizar s3 (evita sobrescribir E3)
        self.client.post(
            reverse('guardar_guia', args=[s3.id]),
            data=json.dumps(self._payload_guia(3)),
            content_type="application/json",
        )
        resp_4 = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_4.status_code, 200)
        html_4 = resp_4.content.decode('utf-8')
        self.assertIn('data-encuentro="4"', html_4)
        self.assertIn('data-silabo-id=""', html_4)

        # Al completar los 11 encuentros, ver_formulario_guia redirige a inicio
        for enc in range(4, 12):
            sx = self._crear_silabo(enc)
            self.client.post(
                reverse('guardar_guia', args=[sx.id]),
                data=json.dumps(self._payload_guia(enc)),
                content_type="application/json",
            )
        resp_done = self.client.get(reverse('ver_formulario_guia', args=[self.asignacion.id]))
        self.assertEqual(resp_done.status_code, 302)

    def test_ver_planeacion_incluye_cuarta_tarea(self):
        s1 = self._crear_silabo(1)
        save_resp = self.client.post(
            reverse('guardar_guia', args=[s1.id]),
            data=json.dumps(self._payload_guia(1)),
            content_type="application/json",
        )
        self.assertEqual(save_resp.status_code, 200)

        resp = self.client.get(reverse('ver_planeacion', args=[self.asignacion.id]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn("4 Tarea(s) Registrada(s)", html)
        self.assertIn("Tarea #4", html)
        self.assertIn("Obj Unico T4", html)
        self.assertIn("Actividad Unica T4 Fase3", html)

    def test_documento_secuencia_didactica_usa_datos_reales_y_sin_placeholders(self):
        from io import BytesIO
        from docx import Document

        s1 = self._crear_silabo(1, puntaje=10, tiempo_minutos=15)
        s2 = self._crear_silabo(2, puntaje=None, tiempo_minutos=None)

        for sil in (s1, s2):
            save_resp = self.client.post(
                reverse('guardar_guia', args=[sil.id]),
                data=json.dumps(self._payload_guia(sil.encuentros)),
                content_type="application/json",
            )
            self.assertEqual(save_resp.status_code, 200)

        resp = self.client.get(reverse('descargar_secuencia_didactica'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            resp['Content-Type'],
        )

        doc = Document(BytesIO(resp.content))
        all_texts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    all_texts.append(cell.text)
                    for nested in cell.tables:
                        for nrow in nested.rows:
                            for ncell in nrow.cells:
                                all_texts.append(ncell.text)
        joined = "\n".join(all_texts)

        # Verificar campos reales de segundo y tercer momento del Sílabo
        self.assertIn("IDE Python, Dataset Real F3", joined)
        self.assertIn("47", joined)
        self.assertIn("Clases prácticas - Laboratorio", joined)
        self.assertIn("Práctica real de laboratorio sobre índices B-Tree F3", joined)
        self.assertIn("38", joined)
        self.assertIn("Orientación del estudio independiente", joined)
        self.assertIn("Síntesis real de cierre F3", joined)
        self.assertIn("Rúbrica digital y guía F3", joined)
        self.assertIn("19", joined)

        # Verificar que las 4 tareas y el resumen con puntaje=None se rendericen
        self.assertIn("Actividad Unica T4 Fase3", joined)
        self.assertIn("RESUMEN DE HORAS Y PUNTAJES", joined)

        # Verificar eliminación de los placeholders fijos heredados
        self.assertNotIn("Computadora, guía, video", joined)
        self.assertNotIn("Trabajo en grupos: ejercicios prácticos sobre arquitecturas.", joined)
        self.assertNotIn("Realimentación y orientación", joined)
        self.assertNotIn("Resumen del tema, aclaración de dudas, tareas para autoestudio.", joined)

    def test_generar_estudio_independiente_con_silabo_sin_asignacion_no_falla(self):
        silabo_huerfano = Silabo.objects.create(
            codigo="HUERF-01",
            asignacion_plan=None,
            encuentros=2,
            fecha=datetime.date(2026, 9, 12),
            unidad="Unidad I",
            nombre_de_la_unidad="Unidad Legada Huérfana",
            contenido_tematico="Contenido legado sin asignacion_plan",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Detalle 1",
            tiempo_primer_momento=15,
            recursos_primer_momento="Pizarra",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Teoría",
            tipo_segundo_momento_practica="Taller",
            clase_practica="Práctica",
            tiempo_segundo_momento_teorica=45,
            tiempo_segundo_momento_practica=45,
            recursos_segundo_momento="Proyector",
            tipo_tercer_momento=["Orientación del estudio independiente"],
            detalle_tercer_momento="Detalle 3",
            tiempo_tercer_momento=15,
            recursos_tercer_momento="Guía",
            eje_transversal=["Tecnología de la información y comunicación"],
            detalle_eje_transversal="Eje",
            actividad_aprendizaje="Actividad",
            tecnica_evaluacion=["Ensayo"],
            tipo_evaluacion=["Formativa"],
            periodo_tiempo_programado="I Corte Evaluativo",
            tiempo_minutos=15,
            agente_evaluador=["Heteroevaluación"],
            instrumento_evaluacion="Rúbrica",
            criterios_evaluacion="Criterios",
            puntaje=10,
        )
        fake_ai_payload = self._payload_guia(2)
        with patch("plan_de_estudio.ai_generators.generar_respuesta_ai", return_value=fake_ai_payload):
            resp = self.client.post(
                reverse("generar_estudio_independiente"),
                {
                    "silabo_id": str(silabo_huerfano.id),
                    "encuentro": "2",
                    "modelo": "google",
                    "numero_actividades": "4",
                },
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["datos"]["numero_encuentro"], 2)
        self.assertEqual(body["datos"]["unidad"], "Unidad I")


class AdminChangelistPerformanceTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_crear.start()
        self.admin_user = User.objects.create_superuser(
            username="admin_perf", email="admin_perf@example.com", password="adminpassword"
        )
        ConfiguracionSistema.get_solo()
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas Perf", codigo="ISP01", cine_2011=1, cine_2013=2,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        for i in range(25):
            asig = Asignatura.objects.create(nombre=f"Asignatura Perf {i}")
            plan = Plan_de_estudio.objects.create(
                carrera=self.carrera, año="I", trimestre="I", pensol="2026",
                codigo=f"PERF-{i:02d}", asignatura=asig,
                horas_presenciales=24, horas_estudio_independiente=48
            )
            ProgramaAsignatura2026.objects.create(
                plan_estudio=plan,
                fundamentacion="F" * 1000,
                relacion_unidades="R" * 500,
                aportes_perfil="A",
                valores="V",
                ejes_transversales="E",
                objetivo_conceptual="OC",
                objetivo_procedimental="OP",
                objetivo_actitudinal="OA",
            )
            pt = PlanTematico.objects.create(
                plan_estudio=plan,
                unidades="Primera unidad",
                nombre_de_la_unidad=f"Unidad Perf {i}",
                objetivo_especificos="O" * 500,
                plan_analitico="P" * 500,
                recomendaciones_metodologicas="M" * 500,
                forma_de_evaluacion="E" * 500,
                relacion_eje_contenido_launidad="R" * 500,
            )
            plan.plan_tematico_ref = pt
            plan.save()

        self.programa_sin_plan = ProgramaAsignatura2026.objects.create(
            plan_estudio=None,
            fundamentacion="Sin plan",
            relacion_unidades="R",
            aportes_perfil="A",
            valores="V",
            ejes_transversales="E",
            objetivo_conceptual="OC",
            objetivo_procedimental="OP",
            objetivo_actitudinal="OA",
        )

    def tearDown(self):
        self.patcher_crear.stop()

    def test_programa_2026_changelist_paginacion_sin_n_plus_1_y_acciones_crud(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = Client()
        client.login(username="admin_perf", password="adminpassword")
        changelist_url = reverse('admin:plan_de_estudio_programaasignatura2026_changelist')

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(changelist_url)

        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(ctx), 10)
        select_queries = [
            q["sql"] for q in ctx
            if "FROM \"plan_de_estudio_programaasignatura2026\"" in q["sql"] and "COUNT" not in q["sql"]
        ]
        self.assertEqual(len(select_queries), 1)
        self.assertNotIn("fundamentacion", select_queries[0])
        self.assertContains(resp, "Asignatura Perf 24".upper())
        self.assertContains(resp, "None - Programa 2026")
        self.assertContains(resp, "26 Programas de asignatura 2026")

        resp_search = client.get(f"{changelist_url}?q=PERF-05")
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, "Asignatura Perf 5".upper())

        change_url = reverse('admin:plan_de_estudio_programaasignatura2026_change', args=[self.programa_sin_plan.pk])
        resp_change = client.get(change_url)
        self.assertEqual(resp_change.status_code, 200)
        self.assertContains(resp_change, "Sin plan")

        resp_del_confirm = client.post(changelist_url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.programa_sin_plan.pk)],
        })
        self.assertEqual(resp_del_confirm.status_code, 200)
        resp_del_exec = client.post(changelist_url, {
            'action': 'delete_selected',
            '_selected_action': [str(self.programa_sin_plan.pk)],
            'post': 'yes',
        })
        self.assertEqual(resp_del_exec.status_code, 302)
        self.assertFalse(ProgramaAsignatura2026.objects.filter(pk=self.programa_sin_plan.pk).exists())

    def test_plantematico_y_autocomplete_sin_n_plus_1(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        client = Client()
        client.login(username="admin_perf", password="adminpassword")

        with CaptureQueriesContext(connection) as ctx_pt:
            resp_pt = client.get(reverse('admin:plan_de_estudio_plantematico_changelist'))
        self.assertEqual(resp_pt.status_code, 200)
        self.assertLessEqual(len(ctx_pt), 10)
        self.assertContains(resp_pt, "ASIGNATURA PERF 24")

        autocomplete_url = reverse('admin:autocomplete')
        with CaptureQueriesContext(connection) as ctx_ac:
            resp_ac = client.get(autocomplete_url, {
                'app_label': 'plan_de_estudio',
                'model_name': 'programaasignatura2026',
                'field_name': 'plan_estudio',
            })
        self.assertEqual(resp_ac.status_code, 200)
        self.assertLessEqual(len(ctx_ac), 6)

    def test_autocomplete_asignacion_plan_muestra_y_filtra_por_pensol(self):
        carrera_farmacia = Carrera.objects.create(
            nombre="Licenciatura en farmacia", codigo="FAR01", cine_2011=1, cine_2013=2,
            area_formacion="Salud y servicios sociales ", area_disiplinaria=1
        )
        asig_bioes = Asignatura.objects.create(nombre="Bioestadística")
        plan_2018 = Plan_de_estudio.objects.create(
            carrera=carrera_farmacia, año="II", trimestre="I", pensol="2018",
            codigo="FAR-BIO-18", asignatura=asig_bioes,
            horas_presenciales=24, horas_estudio_independiente=48
        )
        plan_2026 = Plan_de_estudio.objects.create(
            carrera=carrera_farmacia, año="I", trimestre="I", pensol="2026",
            codigo="FAR-BIO-26", asignatura=asig_bioes,
            horas_presenciales=24, horas_estudio_independiente=48
        )

        client = Client()
        client.login(username="admin_perf", password="adminpassword")
        autocomplete_url = reverse('admin:autocomplete')

        # Búsqueda por nombre muestra ambos planes diferenciados por Pensol
        resp_ambos = client.get(autocomplete_url, {
            'app_label': 'plan_de_estudio',
            'model_name': 'asignacionplanestudio',
            'field_name': 'plan_de_estudio',
            'term': 'bioes',
        })
        self.assertEqual(resp_ambos.status_code, 200)
        results_ambos = resp_ambos.json()['results']
        textos = {r['id']: r['text'] for r in results_ambos}
        self.assertIn(str(plan_2018.pk), textos)
        self.assertIn(str(plan_2026.pk), textos)
        self.assertEqual(
            textos[str(plan_2018.pk)],
            "BIOESTADÍSTICA - Licenciatura en farmacia - II - Pensol 2018",
        )
        self.assertEqual(
            textos[str(plan_2026.pk)],
            "BIOESTADÍSTICA - Licenciatura en farmacia - I - Pensol 2026",
        )

        # Búsqueda combinada con pensol filtra exactamente al pensol indicado
        resp_2026 = client.get(autocomplete_url, {
            'app_label': 'plan_de_estudio',
            'model_name': 'asignacionplanestudio',
            'field_name': 'plan_de_estudio',
            'term': 'bioes 2026',
        })
        self.assertEqual(resp_2026.status_code, 200)
        results_2026 = resp_2026.json()['results']
        self.assertEqual([r['id'] for r in results_2026], [str(plan_2026.pk)])

        resp_2018 = client.get(autocomplete_url, {
            'app_label': 'plan_de_estudio',
            'model_name': 'asignacionplanestudio',
            'field_name': 'plan_de_estudio',
            'term': 'bioes farmacia 2018',
        })
        self.assertEqual(resp_2018.status_code, 200)
        results_2018 = resp_2018.json()['results']
        self.assertEqual([r['id'] for r in results_2018], [str(plan_2018.pk)])

    def test_programa_2026_changelist_filtros_necesarios(self):
        carrera_farmacia = Carrera.objects.create(
            nombre="Licenciatura en Farmacia Filtro", codigo="FARF01", cine_2011=1, cine_2013=2,
            area_formacion="Salud y servicios sociales ", area_disiplinaria=1
        )
        asig_farma = Asignatura.objects.create(nombre="Farmacología Filtro")
        plan_farma_2018 = Plan_de_estudio.objects.create(
            carrera=carrera_farmacia, año="III", trimestre="IV", pensol="2018",
            codigo="FARF-304", asignatura=asig_farma,
            horas_presenciales=24, horas_estudio_independiente=48
        )
        ProgramaAsignatura2026.objects.create(
            plan_estudio=plan_farma_2018,
            fundamentacion="F",
            relacion_unidades="R",
            aportes_perfil="A",
            valores="V",
            ejes_transversales="E",
            objetivo_conceptual="OC",
            objetivo_procedimental="OP",
            objetivo_actitudinal="OA",
        )

        client = Client()
        client.login(username="admin_perf", password="adminpassword")
        changelist_url = reverse('admin:plan_de_estudio_programaasignatura2026_changelist')

        # 1. Filtro por Carrera
        resp_carrera = client.get(changelist_url, {'carrera': str(carrera_farmacia.pk)})
        self.assertEqual(resp_carrera.status_code, 200)
        self.assertContains(resp_carrera, "FARMACOLOGÍA FILTRO")
        self.assertNotContains(resp_carrera, "ASIGNATURA PERF 0")
        self.assertContains(resp_carrera, "1 Programa de asignatura 2026")

        # 2. Filtro por Pensol
        resp_pensol = client.get(changelist_url, {'plan_estudio__pensol__exact': '2018'})
        self.assertEqual(resp_pensol.status_code, 200)
        self.assertContains(resp_pensol, "FARMACOLOGÍA FILTRO")
        self.assertContains(resp_pensol, "1 Programa de asignatura 2026")

        # 3. Filtro por Año
        resp_anio = client.get(changelist_url, {'plan_estudio__año__exact': 'III'})
        self.assertEqual(resp_anio.status_code, 200)
        self.assertContains(resp_anio, "FARMACOLOGÍA FILTRO")
        self.assertContains(resp_anio, "1 Programa de asignatura 2026")

        # 4. Filtro por Trimestre
        resp_trim = client.get(changelist_url, {'plan_estudio__trimestre__exact': 'IV'})
        self.assertEqual(resp_trim.status_code, 200)
        self.assertContains(resp_trim, "FARMACOLOGÍA FILTRO")
        self.assertContains(resp_trim, "1 Programa de asignatura 2026")

        # 5. Filtro por Estado de asociación (sin plan / con plan)
        resp_sin_plan = client.get(changelist_url, {'plan_asociado': 'no'})
        self.assertEqual(resp_sin_plan.status_code, 200)
        self.assertContains(resp_sin_plan, "None - Programa 2026")
        self.assertContains(resp_sin_plan, "1 Programa de asignatura 2026")

        resp_con_plan = client.get(changelist_url, {'plan_asociado': 'si'})
        self.assertEqual(resp_con_plan.status_code, 200)
        self.assertNotContains(resp_con_plan, "None - Programa 2026")
        self.assertContains(resp_con_plan, "26 Programas de asignatura 2026")

        # 6. Filtro combinado (Carrera + Pensol + Año + Trimestre) y búsqueda por carrera/pensol
        resp_combo = client.get(changelist_url, {
            'carrera': str(carrera_farmacia.pk),
            'plan_estudio__pensol__exact': '2018',
            'plan_estudio__año__exact': 'III',
            'plan_estudio__trimestre__exact': 'IV',
        })
        self.assertEqual(resp_combo.status_code, 200)
        self.assertContains(resp_combo, "FARMACOLOGÍA FILTRO")
        self.assertContains(resp_combo, "1 Programa de asignatura 2026")

        resp_search_carrera = client.get(changelist_url, {'q': 'Farmacia Filtro 2018'})
        self.assertEqual(resp_search_carrera.status_code, 200)
        self.assertContains(resp_search_carrera, "FARMACOLOGÍA FILTRO")

        # 7. Parámetro inválido en filtro de carrera no produce error 500
        resp_invalid = client.get(changelist_url, {'carrera': 'invalido'})
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertContains(resp_invalid, "0 Programas de asignatura 2026")

    def test_plan_de_estudio_changelist_paginacion_30_y_descarga_documentos(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        tmp_media = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=tmp_media):
                # Creamos 10 planes adicionales (total 35) para verificar paginación de 30 en 30
                extra_planes = []
                for idx in range(25, 35):
                    asig = Asignatura.objects.create(nombre=f"Asignatura Extra {idx}")
                    extra_planes.append(
                        Plan_de_estudio.objects.create(
                            carrera=self.carrera, año="II", trimestre="II", pensol="2026",
                            codigo=f"PERF-{idx:02d}", asignatura=asig,
                            horas_presenciales=24, horas_estudio_independiente=48,
                        )
                    )

                # Plan con ambos documentos (reciente -> aparece en página 1)
                plan_ambos = extra_planes[-1]
                plan_ambos.plan_tematico.save(
                    "programa_ambos.docx",
                    SimpleUploadedFile("programa_ambos.docx", b"contenido-plan-tematico", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    save=False,
                )
                plan_ambos.documento_adjunto.save(
                    "anexo_ambos.pdf",
                    SimpleUploadedFile("anexo_ambos.pdf", b"%PDF-1.4 contenido-adjunto", content_type="application/pdf"),
                    save=False,
                )
                plan_ambos.save()

                # Plan solo con plan temático
                plan_solo_pt = extra_planes[-2]
                plan_solo_pt.plan_tematico.save(
                    "solo_plan.pdf",
                    SimpleUploadedFile("solo_plan.pdf", b"%PDF-1.4 solo-pt", content_type="application/pdf"),
                    save=True,
                )

                # Plan sin documentos
                plan_sin_docs = extra_planes[-3]

                client = Client()
                client.login(username="admin_perf", password="adminpassword")
                changelist_url = reverse('admin:plan_de_estudio_plan_de_estudio_changelist')

                with CaptureQueriesContext(connection) as ctx:
                    resp_p1 = client.get(changelist_url)
                self.assertEqual(resp_p1.status_code, 200)
                self.assertLessEqual(len(ctx), 10)
                # Verifica 30 elementos por página (35 totales -> 30 en p1, 5 en p2)
                self.assertEqual(resp_p1.context['cl'].list_per_page, 30)
                self.assertEqual(len(resp_p1.context['cl'].result_list), 30)
                self.assertContains(resp_p1, 'data-actions-icnt="30"')
                self.assertContains(resp_p1, "35 Planes de estudio")

                url_descarga_pt = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_ambos.pk, 'plan_tematico'],
                )
                url_descarga_adj = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_ambos.pk, 'documento_adjunto'],
                )
                url_solo_pt = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_solo_pt.pk, 'plan_tematico'],
                )
                url_solo_adj_inexistente = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_solo_pt.pk, 'documento_adjunto'],
                )
                url_sin_docs = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_sin_docs.pk, 'plan_tematico'],
                )

                self.assertContains(resp_p1, url_descarga_pt)
                self.assertContains(resp_p1, url_descarga_adj)
                self.assertContains(resp_p1, url_solo_pt)
                self.assertNotContains(resp_p1, url_solo_adj_inexistente)
                self.assertNotContains(resp_p1, url_sin_docs)

                # Página 2 debe mostrar los 5 restantes
                resp_p2 = client.get(changelist_url, {'p': '2'})
                self.assertEqual(resp_p2.status_code, 200)
                self.assertEqual(len(resp_p2.context['cl'].result_list), 5)

                # Descarga directa del Plan temático
                resp_pt = client.get(url_descarga_pt)
                self.assertEqual(resp_pt.status_code, 200)
                self.assertIn('attachment;', resp_pt['Content-Disposition'])
                self.assertIn('programa_ambos', resp_pt['Content-Disposition'])
                self.assertEqual(b''.join(resp_pt.streaming_content), b'contenido-plan-tematico')
                resp_pt.close()

                # Descarga directa del Documento adjunto
                resp_adj = client.get(url_descarga_adj)
                self.assertEqual(resp_adj.status_code, 200)
                self.assertIn('attachment;', resp_adj['Content-Disposition'])
                self.assertIn('anexo_ambos', resp_adj['Content-Disposition'])
                self.assertEqual(b''.join(resp_adj.streaming_content), b'%PDF-1.4 contenido-adjunto')
                resp_adj.close()

                # Tipo de documento inválido retorna 404
                url_invalido = reverse(
                    'admin:plan_de_estudio_plan_de_estudio_descargar_documento',
                    args=[plan_ambos.pk, 'otro_campo'],
                )
                self.assertEqual(client.get(url_invalido).status_code, 404)

                # Plan sin archivo cargado redirige con advertencia al changelist
                resp_vacio = client.get(url_sin_docs, follow=True)
                self.assertEqual(resp_vacio.status_code, 200)
                self.assertContains(resp_vacio, "no tiene un plan temático cargado")

                # Archivo faltante en almacenamiento redirige con error limpio (sin 500)
                plan_solo_pt.plan_tematico.storage.delete(plan_solo_pt.plan_tematico.name)
                resp_missing = client.get(url_solo_pt, follow=True)
                self.assertEqual(resp_missing.status_code, 200)
                self.assertContains(resp_missing, "No se pudo descargar el archivo")

                # Usuario sin permisos de admin no puede descargar
                docente = User.objects.create_user(username="docente_sin_perm", password="pwd")
                anon_client = Client()
                anon_client.login(username="docente_sin_perm", password="pwd")
                resp_unauth = anon_client.get(url_descarga_pt)
                self.assertEqual(resp_unauth.status_code, 302)
                self.assertIn('/admin/login/', resp_unauth['Location'])
        finally:
            shutil.rmtree(tmp_media, ignore_errors=True)


class TrimestreLectivoAsignacionTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_crear.start()
        self.admin_user = User.objects.create_superuser(
            username="admin_trim", email="admin_trim@example.com", password="adminpassword"
        )
        self.docente = User.objects.create_user(
            username="docente_trim", first_name="Elena", last_name="Vega", password="docpassword"
        )
        ConfiguracionSistema.get_solo()
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería en Computación", codigo="IC01", cine_2011=1, cine_2013=2,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Compiladores")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="IV", trimestre="IV", pensol="2026",
            codigo="COMP401", asignatura=self.asignatura,
            horas_presenciales=24, horas_estudio_independiente=48
        )

    def tearDown(self):
        self.patcher_crear.stop()

    def test_admin_add_muestra_y_exige_trimestre_lectivo_sin_borrar_fecha(self):
        client = Client()
        client.login(username="admin_trim", password="adminpassword")
        add_url = reverse('admin:plan_de_estudio_asignacionplanestudio_add')

        resp_get = client.get(add_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, 'name="trimestre_lectivo"')
        self.assertContains(resp_get, "Trimestre lectivo")

        # Enviar sin trimestre_lectivo debe fallar y no guardar
        resp_invalid = client.post(add_url, {
            'usuario': str(self.docente.pk),
            'plan_de_estudio': str(self.plan.pk),
            'trimestre_lectivo': '',
            'bloque': 'Primer bloque - 8:00',
        })
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertContains(resp_invalid, "Este campo es requerido.")
        self.assertEqual(AsignacionPlanEstudio.objects.count(), 0)

        # Enviar con trimestre_lectivo explícito (próximo trimestre 2026-IV) debe guardar correctamente
        resp_ok = client.post(add_url, {
            'usuario': str(self.docente.pk),
            'plan_de_estudio': str(self.plan.pk),
            'trimestre_lectivo': '2026-IV',
            'bloque': 'Primer bloque - 8:00',
        })
        self.assertEqual(resp_ok.status_code, 302)
        asig = AsignacionPlanEstudio.objects.get()
        self.assertEqual(asig.trimestre_lectivo, '2026-IV')
        self.assertIsNotNone(asig.fecha_asignacion)

        # Listado del admin muestra columna y filtro por trimestre lectivo
        changelist_url = reverse('admin:plan_de_estudio_asignacionplanestudio_changelist')
        resp_list = client.get(f"{changelist_url}?trimestre_lectivo=2026-IV")
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, "2026 - Trimestre IV")
        self.assertContains(resp_list, "COMPILADORES")

        # Vista de cambio muestra tanto trimestre_lectivo editable como fecha_asignacion (solo lectura)
        change_url = reverse('admin:plan_de_estudio_asignacionplanestudio_change', args=[asig.pk])
        resp_change = client.get(change_url)
        self.assertEqual(resp_change.status_code, 200)
        self.assertContains(resp_change, "Fecha asignacion")

    def test_curriculum_planner_y_vistas_docente_usan_trimestre_lectivo(self):
        from plan_de_estudio.utils.curriculum_planner import calcular_tiempos_y_fechas

        asig = AsignacionPlanEstudio.objects.create(
            usuario=self.docente,
            plan_de_estudio=self.plan,
            trimestre_lectivo="2026-IV",
            bloque="Primer bloque - 8:00",
        )
        # Aunque fecha_asignacion sea hoy (noviembre 2026), el planificador usa 2026-IV (Dic 2026 - Feb 2027)
        tiempos = calcular_tiempos_y_fechas(asig, encuentro=1)
        self.assertEqual(tiempos["fecha_encuentro"], "2026-12-05")
        self.assertIn("Ciclo Dic 2026 – Feb 2027", tiempos["ciclo_nombre"])

        # En inicio del docente se muestra el trimestre lectivo y se conserva fecha_asignacion
        doc_client = Client()
        doc_client.login(username="docente_trim", password="docpassword")
        resp_inicio = doc_client.get(reverse('inicio'))
        self.assertEqual(resp_inicio.status_code, 200)
        self.assertContains(resp_inicio, "2026 - Trimestre IV")
        self.assertContains(resp_inicio, "Asignado el:")

        # Filtro por trimestre_lectivo en ranking docente
        resp_rank = doc_client.get(reverse('ranking_docentes'), {'trimestre_lectivo': '2026-IV'})
        self.assertEqual(resp_rank.status_code, 200)
        self.assertContains(resp_rank, "2026 - Trimestre IV")
        self.assertContains(resp_rank, "Elena Vega")

    def test_exportar_form_y_backfill_migracion(self):
        import importlib
        mig_0023 = importlib.import_module(
            'plan_de_estudio.migrations.0023_asignacionplanestudio_trimestre_lectivo'
        )
        self.assertEqual(mig_0023._codigo_desde_fecha(datetime.date(2026, 4, 10) if False else timezone.make_aware(datetime.datetime(2026, 4, 10, 10, 0))), "2026-I")
        self.assertEqual(mig_0023._codigo_desde_fecha(timezone.make_aware(datetime.datetime(2026, 7, 10, 10, 0))), "2026-II")
        self.assertEqual(mig_0023._codigo_desde_fecha(timezone.make_aware(datetime.datetime(2026, 11, 18, 10, 0))), "2026-III")
        self.assertEqual(mig_0023._codigo_desde_fecha(timezone.make_aware(datetime.datetime(2026, 12, 1, 10, 0))), "2026-IV")
        self.assertEqual(mig_0023._codigo_desde_fecha(timezone.make_aware(datetime.datetime(2026, 1, 15, 10, 0))), "2025-IV")

        form = ExportarAsignacionesForm(data={
            'trimestre_lectivo': '2026-IV',
            'trimestre': 'IV',
            'carreras': [self.carrera.id],
            'años': ['IV'],
        })
        self.assertTrue(form.is_valid(), form.errors)


class DesactivacionUltimoEncuentroGuiaTest(TestCase):
    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.patcher_crear.start()
        self.patcher_subir.start()

        self.admin_user = User.objects.create_superuser(
            username="admin_g10", email="admin_g10@example.com", password="adminpassword"
        )
        self.docente = User.objects.create_user(
            username="docente_g10", email="docente_g10@example.com", password="docpassword",
            first_name="Marta", last_name="Solís"
        )
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería de Sistemas G10", codigo="ISG10", cine_2011=111, cine_2013=222,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asig = Asignatura.objects.create(nombre="Ingeniería Web II")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="V", trimestre="IV", pensol="2026",
            codigo="IS1844", asignatura=self.asig,
            horas_presenciales=24, horas_estudio_independiente=70,
        )
        self.programa = ProgramaAsignatura2026.objects.create(
            plan_estudio=self.plan,
            fundamentacion="Fundamentación Web II",
            relacion_unidades="3 unidades",
            aportes_perfil="Perfil",
            valores="Valores",
            ejes_transversales="Tecnología",
            objetivo_conceptual="Obj C",
            objetivo_procedimental="Obj P",
            objetivo_actitudinal="Obj A",
            unidad_1_nombre="APIs REST",
            unidad_1_horas_teoricas=4,
            unidad_1_horas_practicas=4,
            unidad_1_horas_independientes=24,
            unidad_1_objetivos_especificos="Diseñar APIs",
            unidad_1_contenido="REST, JSON, autenticación",
            unidad_2_nombre="Frontend Moderno",
            unidad_2_horas_teoricas=4,
            unidad_2_horas_practicas=4,
            unidad_2_horas_independientes=24,
            unidad_2_objetivos_especificos="Construir SPA",
            unidad_2_contenido="Componentes, estado, enrutamiento",
            unidad_3_nombre="Despliegue y Seguridad",
            unidad_3_horas_teoricas=4,
            unidad_3_horas_practicas=4,
            unidad_3_horas_independientes=22,
            unidad_3_objetivos_especificos="Desplegar en producción",
            unidad_3_contenido="CI/CD, HTTPS, OWASP",
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.docente,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
            bloque="Primer bloque - 8:00",
        )
        self.doc_client = Client()
        self.doc_client.login(username="docente_g10", password="docpassword")
        self.admin_client = Client()
        self.admin_client.login(username="admin_g10", password="adminpassword")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def _crear_silabo(self, enc, puntaje=10):
        corte = "I Corte Evaluativo" if enc <= 4 else ("II Corte Evaluativo" if enc <= 8 else "III Corte Evaluativo")
        return Silabo.objects.create(
            codigo=self.plan.codigo,
            asignacion_plan=self.asignacion,
            encuentros=enc,
            fecha=datetime.date(2026, 9, 5) + datetime.timedelta(days=7 * (enc - 1)),
            unidad="Unidad I",
            nombre_de_la_unidad="APIs REST",
            contenido_tematico=f"Tema {enc}",
            objetivo_conceptual="OC",
            objetivo_procedimental="OP",
            objetivo_actitudinal="OA",
            tipo_primer_momento="Evaluación diagnóstica",
            detalle_primer_momento="Inicio",
            tiempo_primer_momento=15,
            recursos_primer_momento="Pizarra",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Teoría",
            tipo_segundo_momento_practica="Taller",
            clase_practica="Práctica",
            tiempo_segundo_momento_teorica=45,
            tiempo_segundo_momento_practica=55,
            recursos_segundo_momento="Proyector",
            tipo_tercer_momento=["Realimentación del aprendizaje"],
            detalle_tercer_momento="Cierre",
            tiempo_tercer_momento=15,
            recursos_tercer_momento="Rúbrica",
            eje_transversal=["Tecnología de la información y comunicación"],
            detalle_eje_transversal="TIC",
            actividad_aprendizaje="Taller",
            tecnica_evaluacion=["Observación"],
            tipo_evaluacion=["Formativa"],
            periodo_tiempo_programado=corte,
            tiempo_minutos=20,
            agente_evaluador=["Heteroevaluación"],
            instrumento_evaluacion="Rúbrica",
            criterios_evaluacion="Precisión",
            puntaje=puntaje,
        )

    def _crear_guia(self, silabo, enc, puntaje=15, tiempo=420):
        corte = "I Corte Evaluativo" if enc <= 4 else ("II Corte Evaluativo" if enc <= 8 else "III Corte Evaluativo")
        guia = Guia.objects.create(
            silabo=silabo,
            numero_encuentro=enc,
            fecha=silabo.fecha,
            unidad=silabo.unidad,
            nombre_de_la_unidad=silabo.nombre_de_la_unidad,
            tipo_objetivo_1="Conceptual",
            objetivo_aprendizaje_1=f"Obj guía {enc}",
            contenido_tematico_1=f"Tema guía {enc}",
            actividad_aprendizaje_1=f"Actividad guía {enc}",
            tecnica_evaluacion_1="Proyecto",
            tipo_evaluacion_1="Sumativa",
            instrumento_evaluacion_1="Rúbrica",
            criterios_evaluacion_1="Criterio",
            agente_evaluador_1=["Heteroevaluación"],
            tiempo_minutos_1=tiempo,
            recursos_didacticos_1="Manual",
            periodo_tiempo_programado_1=corte,
            puntaje_1=puntaje,
            fecha_entrega_1=silabo.fecha + datetime.timedelta(days=5 if enc < 11 else 0),
        )
        silabo.guia = guia
        silabo.save(update_fields=["guia"])
        return guia

    def test_toggle_admin_y_permisos_ultimo_encuentro_guia(self):
        config = ConfiguracionSistema.get_solo()
        self.assertFalse(config.habilitar_ultimo_encuentro_guia)
        self.assertEqual(config.max_encuentros_guia, 10)

        toggle_url = reverse('admin:plan_de_estudio_copiaseguridad_toggle_ultimo_encuentro_guia')
        changelist_url = reverse('admin:plan_de_estudio_copiaseguridad_changelist')

        # Docente no puede modificar el ajuste
        resp_doc = self.doc_client.post(toggle_url, {'accion': 'activar'})
        self.assertEqual(resp_doc.status_code, 302)
        self.assertIn('/admin/login/', resp_doc['Location'])
        self.assertFalse(ConfiguracionSistema.get_solo().habilitar_ultimo_encuentro_guia)

        # Admin visualiza estado desactivado (10 guías) y puede restaurar (11 guías) y volver a desactivar
        resp_list = self.admin_client.get(changelist_url)
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, "Guía del Último Encuentro (Encuentro 11)")
        self.assertContains(resp_list, "Desactivada (10 guías)")

        resp_on = self.admin_client.post(toggle_url, {'accion': 'activar'})
        self.assertEqual(resp_on.status_code, 302)
        config.refresh_from_db()
        self.assertTrue(config.habilitar_ultimo_encuentro_guia)
        self.assertEqual(config.max_encuentros_guia, 11)

        resp_list_on = self.admin_client.get(changelist_url)
        self.assertContains(resp_list_on, "Habilitada (11 guías)")

        resp_off = self.admin_client.post(toggle_url, {'accion': 'desactivar'})
        self.assertEqual(resp_off.status_code, 302)
        config.refresh_from_db()
        self.assertFalse(config.habilitar_ultimo_encuentro_guia)
        self.assertEqual(config.max_encuentros_guia, 10)

    def test_inicio_flujo_10_guias_11_silabos_y_restauracion(self):
        # Con 5 sílabos y 5 guías: pendiente, muestra 1..11 para sílabo y 1..10 para guía
        self.asignacion.silabos_creados = 5
        self.asignacion.guias_creadas = 5
        self.asignacion.save()
        resp_mid = self.doc_client.get(reverse('inicio'))
        self.assertEqual(resp_mid.status_code, 200)
        self.assertEqual(list(resp_mid.context['rango']), list(range(1, 12)))
        self.assertEqual(list(resp_mid.context['rango_guias']), list(range(1, 11)))
        self.assertEqual(len(resp_mid.context['asignaciones_pendientes']), 1)
        self.assertEqual(len(resp_mid.context['asignaciones_completadas']), 0)

        # Con 10 sílabos, 10 guías y 2 exámenes (E4 y E8): sigue pendiente por Sílabo 11 y Examen 3,
        # botón Generar Guía deshabilitado (10 guías completadas) y Sílabo 11 habilitado
        self.asignacion.silabos_creados = 10
        self.asignacion.guias_creadas = 10
        self.asignacion.examenes_creados = 2
        self.asignacion.save()
        resp_10 = self.doc_client.get(reverse('inicio'))
        self.assertEqual(len(resp_10.context['asignaciones_pendientes']), 1)
        self.assertContains(resp_10, "Ya se han completado las 10 guías")
        self.assertContains(resp_10, reverse('ver_formulario_silabo', args=[self.asignacion.id]))

        # Con 11 sílabos, 10 guías y 3 exámenes: pasa a Archivados / Completado sin botones de generación
        self.asignacion.silabos_creados = 11
        self.asignacion.guias_creadas = 10
        self.asignacion.examenes_creados = 3
        self.asignacion.save()
        resp_done = self.doc_client.get(reverse('inicio'))
        self.assertEqual(len(resp_done.context['asignaciones_pendientes']), 0)
        self.assertEqual(len(resp_done.context['asignaciones_completadas']), 1)
        self.assertNotContains(resp_done, "Generar Guía")

        # Si el administrador restaura el Encuentro 11 de la guía, vuelve a requerir la guía 11
        cfg = ConfiguracionSistema.get_solo()
        cfg.habilitar_ultimo_encuentro_guia = True
        cfg.save()
        resp_restored = self.doc_client.get(reverse('inicio'))
        self.assertEqual(list(resp_restored.context['rango_guias']), list(range(1, 12)))
        self.assertEqual(len(resp_restored.context['asignaciones_pendientes']), 1)
        self.assertContains(resp_restored, "Generar Guía")

    def test_ver_planeacion_guia_autodidactica_ranking_compatibilidad_historica_y_correos(self):
        from plan_de_estudio.email_utils import enviar_correos_plan_incompleto

        silabos = [self._crear_silabo(enc) for enc in range(1, 12)]
        for enc in range(1, 11):
            self._crear_guia(silabos[enc - 1], enc)
        for num_eval, enc_ex, corte_ex in ((1, 4, "I Corte Evaluativo"), (2, 8, "II Corte Evaluativo"), (3, 11, "III Corte Evaluativo")):
            ProyectoExamen.objects.create(
                asignacion_plan=self.asignacion,
                silabo=silabos[enc_ex - 1],
                numero_evaluacion=num_eval,
                encuentro=enc_ex,
                periodo_corte=corte_ex,
                fecha=silabos[enc_ex - 1].fecha,
                anio_lectivo="2026",
                trimestre="III",
                carrera_texto=self.carrera.nombre,
                items_json=[{"numero": "I", "objetivo": "Obj", "ejercicios": "Ej", "posibles_respuestas": "Resp", "puntaje": 50, "detalle_puntaje": "50 pts"}],
                puntaje_total=50,
                paginas_estimadas=3.2,
            )
        self.asignacion.silabos_creados = 11
        self.asignacion.guias_creadas = 10
        self.asignacion.examenes_creados = 3
        self.asignacion.save()

        # 1. ver_formulario_guia redirige a inicio y generar_estudio_independiente rechaza silabo 11
        self.assertEqual(self.doc_client.get(reverse('ver_formulario_guia', args=[self.asignacion.id])).status_code, 302)
        resp_g11_ia = self.doc_client.post(reverse('generar_estudio_independiente'), {
            'silabo_id': str(silabos[10].id),
            'encuentro': '1',
            'modelo': 'google',
            'numero_actividades': '4',
        })
        self.assertEqual(resp_g11_ia.status_code, 400)

        # 2. ver_planeacion muestra E11 como completo sin guía ("Cierre sin guía") y con Examen Presente
        resp_vp = self.doc_client.get(reverse('ver_planeacion', args=[self.asignacion.id]))
        self.assertEqual(resp_vp.status_code, 200)
        enc11 = resp_vp.context['encuentros_list'][10]
        self.assertTrue(enc11['completo'])
        self.assertFalse(enc11['requiere_guia'])
        self.assertContains(resp_vp, "Cierre sin guía")
        self.assertContains(resp_vp, "10/10")

        # 3. guia_autodidactica solo lista los 10 encuentros con guía
        resp_ga = self.doc_client.get(reverse('guia_autodidactica'), {'codigo': self.plan.codigo})
        self.assertEqual(resp_ga.status_code, 200)
        self.assertEqual(len(resp_ga.context['silabos_agrupados'][self.plan.codigo]), 10)

        # 4. Ranking marca 100.0% (24/24) con 11 sílabos, 10 guías y 3 exámenes
        rank = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual(rank['esperado_silabos'], 11)
        self.assertEqual(rank['esperado_guias'], 10)
        self.assertEqual(rank['esperado_examenes'], 3)
        doc_rank = rank['docentes'][0]
        self.assertEqual(doc_rank['porcentaje_general'], 100.0)
        self.assertEqual(doc_rank['total_entregables'], 24)
        self.assertEqual(doc_rank['esperado_entregables'], 24)
        self.assertEqual(doc_rank['estado'], 'cumplido')

        # 5. Recordatorios por correo NO marcan como incompleta una asignación 11/10
        with patch('plan_de_estudio.email_utils.resend.api_key', 're_test_key'), \
             patch('plan_de_estudio.email_utils.resend.Emails.send', return_value={'id': 'msg_1'}) as mock_send, \
             patch('plan_de_estudio.email_utils.time.sleep'):
            enviados_10 = enviar_correos_plan_incompleto()
            self.assertEqual(enviados_10, 0)
            self.assertEqual(mock_send.call_count, 0)

        # 6. Compatibilidad histórica: si una asignación antigua tiene guía en Encuentro 11,
        #    sigue mostrándose en ver_planeacion, guia_autodidactica y ranking sin superar 100%
        guia_11 = self._crear_guia(silabos[10], 11)
        self.asignacion.guias_creadas = 11
        self.asignacion.save()

        resp_vp_hist = self.doc_client.get(reverse('ver_planeacion', args=[self.asignacion.id]))
        self.assertTrue(resp_vp_hist.context['encuentros_list'][10]['tiene_guia'])
        self.assertTrue(resp_vp_hist.context['encuentros_list'][10]['completo'])
        self.assertContains(resp_vp_hist, "Actividad guía 11")

        resp_ga_hist = self.doc_client.get(reverse('guia_autodidactica'), {'codigo': self.plan.codigo})
        self.assertEqual(len(resp_ga_hist.context['silabos_agrupados'][self.plan.codigo]), 11)

        rank_hist = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual(rank_hist['docentes'][0]['porcentaje_general'], 100.0)
        self.assertEqual(rank_hist['docentes'][0]['faltantes_guias'], 0)

        # La guía histórica 11 sigue pudiendo editarse vía actualizar_guia
        resp_edit = self.doc_client.get(reverse('actualizar_guia', args=[guia_11.id]))
        self.assertEqual(resp_edit.status_code, 200)

    def test_ia_restaurar_encuentro_11_divide_notas_y_tiempos_en_11_guias(self):
        from plan_de_estudio.utils.curriculum_planner import (
            calcular_corte_y_presupuesto,
            calcular_tiempos_y_fechas,
        )

        # Con 10 guías (por defecto): 70h = 4200 min / 10 = 420 min por guía
        tiempos_10 = calcular_tiempos_y_fechas(self.asignacion, encuentro=1)
        self.assertEqual(tiempos_10['max_guias'], 10)
        self.assertEqual(tiempos_10['min_indep_objetivo'], 420)

        # Al restaurar temporalmente Encuentro 11 sin guías previas: 70h = 4200 min / 11 ≈ 382 min por guía
        cfg = ConfiguracionSistema.get_solo()
        cfg.habilitar_ultimo_encuentro_guia = True
        cfg.save()
        tiempos_11_inicio = calcular_tiempos_y_fechas(self.asignacion, encuentro=1)
        self.assertEqual(tiempos_11_inicio['max_guias'], 11)
        self.assertEqual(tiempos_11_inicio['min_indep_objetivo'], 382)

        # Volver a desactivar (10 guías) y crear S9, G9, S10, G10 (total 35 pts acumulados en III Corte, reservando 50 pts para Examen 3):
        # S11 cierra exactamente el acumulado del III Corte (15 pts -> 50 acumulado + 50 examen = 100)
        cfg.habilitar_ultimo_encuentro_guia = False
        cfg.save()
        s9 = self._crear_silabo(9, puntaje=5)
        self._crear_guia(s9, 9, puntaje=12)
        s10 = self._crear_silabo(10, puntaje=6)
        self._crear_guia(s10, 10, puntaje=12)

        pres_s11_sin_g11 = calcular_corte_y_presupuesto(self.asignacion, encuentro=11, es_guia=False)
        self.assertTrue(pres_s11_sin_g11['es_ultimo_en_corte'])
        self.assertEqual(pres_s11_sin_g11['presupuesto_objetivo'], 15)
        self.assertEqual(pres_s11_sin_g11['presupuesto_max'], 15)

        # Al restaurar Encuentro 11 de la guía con G9 y G10 ya creadas (840 min):
        # remanente 3360 min / 9 guías restantes = 373 min, y S11 reserva puntos para G11
        cfg.habilitar_ultimo_encuentro_guia = True
        cfg.save()

        tiempos_11 = calcular_tiempos_y_fechas(self.asignacion, encuentro=1)
        self.assertEqual(tiempos_11['max_guias'], 11)
        self.assertEqual(tiempos_11['min_indep_objetivo'], 373)

        pres_s11_con_g11 = calcular_corte_y_presupuesto(self.asignacion, encuentro=11, es_guia=False)
        self.assertFalse(pres_s11_con_g11['es_ultimo_en_corte'])
        self.assertLess(pres_s11_con_g11['presupuesto_objetivo'], 15)


class ProyectoExamenModuloTest(TestCase):
    """Pruebas integrales del módulo Proyecto de Examen (E4, E8, E11), bloqueo secuencial, puntaje automático, >2 páginas, IA 4-8 hojas y DOCX."""

    def setUp(self):
        self.patcher_crear = patch('plan_de_estudio.signals.crear_clase_e_invitar_maestro')
        self.patcher_subir = patch('plan_de_estudio.services.google_classroom.subir_tareas_desde_guia')
        self.mock_crear = self.patcher_crear.start()
        self.mock_subir = self.patcher_subir.start()

        self.docente = User.objects.create_user(
            username="docente_ex", password="docpassword",
            first_name="Elena", last_name="Vargas", email="elena@uml.edu.ni"
        )
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería en Sistemas EX", codigo="ISEX01",
            cine_2011=11, cine_2013=22,
            area_formacion="Tecnologías de la información", area_disiplinaria=1
        )
        self.asignatura = Asignatura.objects.create(nombre="Geografía Económica EX")
        self.plan = Plan_de_estudio.objects.create(
            carrera=self.carrera, año="II", trimestre="II", pensol="2026",
            codigo="GEOX201", asignatura=self.asignatura,
            horas_presenciales=24, horas_estudio_independiente=70
        )
        self.programa = ProgramaAsignatura2026.objects.create(
            plan_estudio=self.plan,
            fundamentacion="Estudio económico y territorial.",
            relacion_unidades="Secuencia progresiva.",
            aportes_perfil="Análisis regional.",
            valores="Ética.",
            ejes_transversales="Medio ambiente.",
            objetivo_conceptual="Comprender la geografía económica.",
            objetivo_procedimental="Analizar indicadores productivos.",
            objetivo_actitudinal="Valorar el desarrollo sostenible.",
            unidad_1_nombre="Sectores Productivos",
            unidad_1_horas_teoricas=4, unidad_1_horas_practicas=4, unidad_1_horas_independientes=24,
            unidad_1_objetivos_especificos="Analizar sectores primario, secundario y terciario.",
            unidad_1_contenido="Agricultura, ganadería, industria y servicios.",
            unidad_2_nombre="Infraestructura y Comercio",
            unidad_2_horas_teoricas=4, unidad_2_horas_practicas=4, unidad_2_horas_independientes=24,
            unidad_2_objetivos_especificos="Evaluar redes de transporte y comercio.",
            unidad_2_contenido="Puertos, carreteras, exportaciones.",
            unidad_3_nombre="Desarrollo Regional Sostenible",
            unidad_3_horas_teoricas=4, unidad_3_horas_practicas=4, unidad_3_horas_independientes=22,
            unidad_3_objetivos_especificos="Proponer estrategias territoriales.",
            unidad_3_contenido="Ordenamiento territorial y sostenibilidad.",
        )
        self.asignacion = AsignacionPlanEstudio.objects.create(
            usuario=self.docente,
            plan_de_estudio=self.plan,
            trimestre_lectivo=obtener_trimestre_lectivo_de_fecha(),
            bloque="Primer bloque - 8:00",
        )
        self.client = Client()
        self.client.login(username="docente_ex", password="docpassword")

    def tearDown(self):
        self.patcher_crear.stop()
        self.patcher_subir.stop()

    def _crear_silabo(self, enc, puntaje=5):
        corte = "I Corte Evaluativo" if enc <= 4 else ("II Corte Evaluativo" if enc <= 8 else "III Corte Evaluativo")
        s = Silabo.objects.create(
            codigo=self.plan.codigo,
            encuentros=enc,
            fecha=datetime.date(2026, 6, 1) + datetime.timedelta(days=7 * (enc - 1)),
            unidad="Unidad I" if enc <= 4 else ("Unidad II" if enc <= 8 else "Unidad III"),
            nombre_de_la_unidad=f"Unidad encuentro {enc}",
            contenido_tematico=f"Contenido temático del encuentro {enc}",
            objetivo_conceptual=f"OC {enc}",
            objetivo_procedimental=f"OP {enc}",
            objetivo_actitudinal=f"OA {enc}",
            tipo_primer_momento="Realimentación del aprendizaje",
            detalle_primer_momento="Inicio",
            tiempo_primer_momento=15,
            recursos_primer_momento="Pizarra",
            tipo_segundo_momento_claseteoria="Conferencia",
            clase_teorica="Teoría",
            tipo_segundo_momento_practica="Taller",
            clase_practica="Práctica",
            tiempo_segundo_momento_teorica=45,
            tiempo_segundo_momento_practica=45,
            recursos_segundo_momento="Proyector",
            tipo_tercer_momento=["Realimentación del aprendizaje"],
            detalle_tercer_momento="Cierre",
            tiempo_tercer_momento=15,
            recursos_tercer_momento="Guía",
            eje_transversal=["Medio ambiente"],
            detalle_eje_transversal="Eje",
            actividad_aprendizaje=f"Actividad aula {enc}",
            tecnica_evaluacion=["Ensayo"],
            tipo_evaluacion=["Formativa"],
            periodo_tiempo_programado=corte,
            tiempo_minutos=20,
            agente_evaluador=["Heteroevaluación"],
            instrumento_evaluacion="Rúbrica",
            criterios_evaluacion="Criterio",
            puntaje=puntaje,
            asignacion_plan=self.asignacion,
        )
        self.asignacion.silabos_creados = self.asignacion.silabo_set.count()
        self.asignacion.save(update_fields=["silabos_creados"])
        return s

    def _crear_guia(self, silabo, enc, puntaje=10):
        corte = "I Corte Evaluativo" if enc <= 4 else ("II Corte Evaluativo" if enc <= 8 else "III Corte Evaluativo")
        g = Guia.objects.create(
            silabo=silabo,
            numero_encuentro=enc,
            fecha=silabo.fecha,
            unidad=silabo.unidad,
            nombre_de_la_unidad=silabo.nombre_de_la_unidad,
            tipo_objetivo_1="Conceptual",
            objetivo_aprendizaje_1=f"Obj guía {enc}",
            contenido_tematico_1=f"Tema guía {enc}",
            actividad_aprendizaje_1=f"Actividad guía {enc}",
            tecnica_evaluacion_1="Ensayo",
            tipo_evaluacion_1="Sumativa",
            instrumento_evaluacion_1="Rúbrica",
            criterios_evaluacion_1="Claridad",
            agente_evaluador_1=["Heteroevaluación"],
            tiempo_minutos_1=120,
            recursos_didacticos_1="Manual",
            periodo_tiempo_programado_1=corte,
            puntaje_1=puntaje,
            fecha_entrega_1=silabo.fecha + datetime.timedelta(days=5),
        )
        silabo.guia = g
        silabo.save(update_fields=["guia"])
        self.asignacion.guias_creadas = Guia.objects.filter(silabo__asignacion_plan=self.asignacion).count()
        self.asignacion.save(update_fields=["guias_creadas"])
        return g

    def _items_validos_mas_de_2_paginas(self, puntaje_total):
        bloque = "\n".join(
            f"{k}. Analice detenidamente el caso territorial #{k} considerando producción agrícola, cadena de suministro, infraestructura vial e impacto económico en la región norte de Nicaragua."
            for k in range(1, 14)
        )
        clave = "\n".join(
            f"{k}. El estudiante debe identificar al menos tres factores estructurales del caso #{k}, sustentar cuantitativamente la productividad y proponer dos medidas de mejora viables."
            for k in range(1, 14)
        )
        p1 = puntaje_total // 2
        p2 = puntaje_total - p1
        return [
            {
                "numero": "I",
                "objetivo": "Analizar críticamente la estructura productiva regional y sus indicadores económicos fundamentales.",
                "ejercicios": f"I. Análisis de casos productivos aplicados.\n{bloque}",
                "posibles_respuestas": f"I. Solución modelo detallada.\n{clave}",
                "puntaje": p1,
                "detalle_puntaje": f"{p1} pts",
            },
            {
                "numero": "II",
                "objetivo": "Diseñar propuestas técnicas de desarrollo económico local integrando criterios de sostenibilidad.",
                "ejercicios": f"II. Resolución de problemas y evaluación comparativa.\n{bloque}",
                "posibles_respuestas": f"II. Criterios y respuestas esperadas.\n{clave}",
                "puntaje": p2,
                "detalle_puntaje": f"{p2} pts",
            },
        ]

    def test_activacion_en_encuentro_4_bloqueo_silabo_5_y_puntaje_automatico(self):
        # Con 3 sílabos: botón de examen bloqueado y vista redirige a inicio
        for enc in range(1, 4):
            s = self._crear_silabo(enc, puntaje=5)
            self._crear_guia(s, enc, puntaje=10)

        resp_inicio_3 = self.client.get(reverse('inicio'))
        self.assertEqual(resp_inicio_3.status_code, 200)
        asig_ctx = resp_inicio_3.context['asignaciones_pendientes'][0]
        self.assertFalse(asig_ctx.estado_examenes['puede_generar_examen'])
        self.assertFalse(asig_ctx.estado_examenes['examen_bloquea_silabo'])
        self.assertEqual(
            self.client.get(reverse('ver_formulario_examen', args=[self.asignacion.id])).status_code,
            302,
        )

        # Al completar Sílabo 4 (y Guía 4): acumulado I Corte = 4*5 + 4*10 = 60 pts -> examen automático = 40 pts
        s4 = self._crear_silabo(4, puntaje=5)
        self._crear_guia(s4, 4, puntaje=10)

        resp_inicio_4 = self.client.get(reverse('inicio'))
        asig_ctx4 = resp_inicio_4.context['asignaciones_pendientes'][0]
        self.assertTrue(asig_ctx4.estado_examenes['puede_generar_examen'])
        self.assertEqual(asig_ctx4.estado_examenes['siguiente_evaluacion'], 1)
        self.assertTrue(asig_ctx4.estado_examenes['examen_bloquea_silabo'])
        self.assertTrue(asig_ctx4.estado_examenes['silabo_deshabilitado'])

        # Sílabo 5 bloqueado tanto en formulario GET como en guardar_silabo POST hasta hacer Examen 1
        resp_s5_get = self.client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp_s5_get.status_code, 302)

        resp_form_ex = self.client.get(reverse('ver_formulario_examen', args=[self.asignacion.id]))
        self.assertEqual(resp_form_ex.status_code, 200)
        self.assertEqual(resp_form_ex.context['puntaje_info']['acumulado_total'], 60)
        self.assertEqual(resp_form_ex.context['puntaje_info']['puntaje_disponible'], 40)

        # Rechaza guardar examen de 1 página (bloqueo anti-pereza)
        resp_corto = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "anio_lectivo": "2026",
                "trimestre": "II",
                "carrera_texto": self.carrera.nombre,
                "modalidad": "Por encuentro",
                "tipo_examen": "De corte evaluativo",
                "items": [
                    {"numero": "I", "objetivo": "Obj 1", "ejercicios": "Pregunta 1", "posibles_respuestas": "Resp 1", "puntaje": 20},
                    {"numero": "II", "objetivo": "Obj 2", "ejercicios": "Pregunta 2", "posibles_respuestas": "Resp 2", "puntaje": 20},
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_corto.status_code, 400)
        self.assertIn("2 páginas", resp_corto.json()["error"])

        # Rechaza intento de inflar páginas con saltos de línea vacíos
        resp_trampa = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "anio_lectivo": "2026",
                "trimestre": "II",
                "carrera_texto": self.carrera.nombre,
                "items": [
                    {"numero": "I", "objetivo": "Obj", "ejercicios": "A" + ("\n" * 150) + "B", "posibles_respuestas": "C", "puntaje": 20},
                    {"numero": "II", "objetivo": "Obj 2", "ejercicios": "D" + ("\n" * 150) + "E", "posibles_respuestas": "F", "puntaje": 20},
                ],
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_trampa.status_code, 400)

        # Rechaza puntaje distinto al restante exacto (40 pts)
        resp_pts_mal = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "anio_lectivo": "2026",
                "trimestre": "II",
                "carrera_texto": self.carrera.nombre,
                "items": self._items_validos_mas_de_2_paginas(30),
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_pts_mal.status_code, 400)
        self.assertIn("40 pts", resp_pts_mal.json()["error"])

        # Guarda examen válido (>2 páginas y exactamente 40 pts) -> redirige a success_view?examen_id=...
        resp_ok = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "anio_lectivo": "2026",
                "trimestre": "II",
                "codigo_grupo": "IS-II-A",
                "carrera_texto": self.carrera.nombre,
                "modalidad": "Por encuentro",
                "tipo_examen": "De corte evaluativo",
                "items": self._items_validos_mas_de_2_paginas(40),
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_ok.status_code, 200, resp_ok.content.decode('utf-8'))
        payload_ok = resp_ok.json()
        examen_id = payload_ok["examen_id"]
        self.assertIn(f"examen_id={examen_id}", payload_ok["redirect_url"])
        self.assertGreater(payload_ok["paginas_estimadas"], 2.0)

        # Pantalla de éxito muestra el botón directo para descargar Word (.docx)
        resp_exito = self.client.get(payload_ok["redirect_url"])
        self.assertEqual(resp_exito.status_code, 200)
        self.assertContains(resp_exito, reverse('descargar_proyecto_examen', args=[examen_id]))
        self.assertContains(resp_exito, "Descargar Proyecto de Examen (.docx)")

        # Tarjeta de Ver datos (plan_estudio) muestra Exámenes y enlace directo de descarga
        resp_datos = self.client.get(reverse('plan_de_estudio'))
        self.assertEqual(resp_datos.status_code, 200)
        self.assertContains(resp_datos, "1/3 Exámenes")
        self.assertContains(resp_datos, reverse('detalle_examenes', args=[self.asignacion.id]))
        self.assertContains(resp_datos, reverse('descargar_proyecto_examen', args=[examen_id]))

        # Ahora Sílabo 5 queda desbloqueado
        resp_s5_ok = self.client.get(reverse('ver_formulario_silabo', args=[self.asignacion.id]))
        self.assertEqual(resp_s5_ok.status_code, 200)
        self.assertEqual(resp_s5_ok.context['encuentro'], 5)

    def test_bloqueo_cuando_docente_sobre_acumula_100_pts_en_corte(self):
        # Docente acumula 100 pts en I Corte (4*10 sílabos + 4*15 guías = 100 pts) -> 0 pts disponibles para Examen 1
        for enc in range(1, 5):
            s = self._crear_silabo(enc, puntaje=10)
            self._crear_guia(s, enc, puntaje=15)

        resp_form = self.client.get(reverse('ver_formulario_examen', args=[self.asignacion.id]))
        self.assertEqual(resp_form.status_code, 200)
        self.assertTrue(resp_form.context['puntaje_info']['bloqueado_por_puntaje'])
        self.assertEqual(resp_form.context['puntaje_info']['puntaje_disponible'], 0)
        self.assertContains(resp_form, "No quedan puntos disponibles para este Proyecto de Examen")

        # Tanto guardar como generar con IA deben rechazar con HTTP 400
        resp_ia = self.client.post(reverse('generar_proyecto_examen'), {
            'asignacion_id': str(self.asignacion.id),
            'numero_evaluacion': '1',
            'numero_hojas': '4',
            'modelo_select': 'google',
        })
        self.assertEqual(resp_ia.status_code, 400)

        resp_save = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "items": self._items_validos_mas_de_2_paginas(10),
            }),
            content_type="application/json",
        )
        self.assertEqual(resp_save.status_code, 400)

    def test_ia_rango_hojas_4_a_8_y_descarga_docx_sin_modificar_plantilla(self):
        import hashlib
        import io
        from pathlib import Path
        from django.conf import settings
        from docx import Document

        for enc in range(1, 5):
            s = self._crear_silabo(enc, puntaje=5)
            self._crear_guia(s, enc, puntaje=8)
        # Acumulado = 4*5 + 4*8 = 52 pts -> examen automático = 48 pts

        # Rechaza < 4 hojas y > 8 hojas en IA
        for hojas_bad in ('1', '2', '3', '9'):
            r_bad = self.client.post(reverse('generar_proyecto_examen'), {
                'asignacion_id': str(self.asignacion.id),
                'numero_evaluacion': '1',
                'numero_hojas': hojas_bad,
                'modelo_select': 'google',
            })
            self.assertEqual(r_bad.status_code, 400)

        # Genera con 6 hojas: normaliza suma exacta = 48 pts aunque la IA proponga otros puntajes
        fake_ai_json = json.dumps({
            "fecha": "2026-06-22",
            "anio_lectivo": "2026",
            "trimestre": "II",
            "items": self._items_validos_mas_de_2_paginas(90),  # IA infla a 90 -> normalizador ajusta a 48 exactos
        })
        with patch('plan_de_estudio.ai_generators.usar_modelo_google', return_value=fake_ai_json) as mock_ai:
            r_ia = self.client.post(reverse('generar_proyecto_examen'), {
                'asignacion_id': str(self.asignacion.id),
                'numero_evaluacion': '1',
                'numero_hojas': '6',
                'modelo_select': 'google',
            })
            self.assertEqual(r_ia.status_code, 200, r_ia.content.decode('utf-8'))
            self.assertIn("6 HOJAS", mock_ai.call_args[0][0])
            datos = r_ia.json()["datos"]
            self.assertEqual(datos["puntaje_total"], 48)
            self.assertEqual(sum(it["puntaje"] for it in datos["items"]), 48)
            self.assertEqual(datos["hojas_objetivo_ia"], 6)

        # Guardar y descargar .docx verificando que la plantilla original NO se altera
        r_save = self.client.post(
            reverse('guardar_examen', args=[self.asignacion.id]),
            data=json.dumps({
                "numero_evaluacion": 1,
                "fecha": "2026-06-22",
                "anio_lectivo": "2026",
                "trimestre": "II",
                "codigo_grupo": "GEOX-G1",
                "carrera_texto": self.carrera.nombre,
                "modalidad": "Por encuentro",
                "tipo_examen": "De corte evaluativo",
                "hojas_objetivo_ia": 6,
                "items": datos["items"],
            }),
            content_type="application/json",
        )
        self.assertEqual(r_save.status_code, 200, r_save.content.decode('utf-8'))
        examen_id = r_save.json()["examen_id"]

        tpl_path = Path(settings.BASE_DIR) / 'docx_templates' / 'plantilla_proyecto_examen.docx'
        sha_antes = hashlib.sha256(tpl_path.read_bytes()).hexdigest()

        r_docx = self.client.get(reverse('descargar_proyecto_examen', args=[examen_id]))
        self.assertEqual(r_docx.status_code, 200)
        self.assertEqual(
            r_docx['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

        sha_despues = hashlib.sha256(tpl_path.read_bytes()).hexdigest()
        self.assertEqual(sha_antes, sha_despues)

        # Inspeccionar contenido del Word generado
        doc = Document(io.BytesIO(r_docx.content))
        texto_parrafos = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("UNIVERSIDAD MARTÍN LUTERO", texto_parrafos)
        self.assertIn("Geografía Económica EX", texto_parrafos)
        self.assertIn("Elena Vargas", texto_parrafos)
        self.assertIn("GEOX-G1", texto_parrafos)
        self.assertEqual(len(doc.tables), 1)
        tabla = doc.tables[0]
        # Encabezado + 2 apartados + fila TOTAL = 4 filas
        self.assertEqual(len(tabla.rows), 4)
        self.assertIn("48 pts", tabla.rows[-1].cells[3].text)
        # Verificar que el logo embebido en P[0] sigue presente en el documento
        self.assertIn("drawing", doc.paragraphs[0]._p.xml)












