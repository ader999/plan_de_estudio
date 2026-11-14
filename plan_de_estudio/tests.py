import datetime
import json
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse

from plan_de_estudio.models import (
    Asignatura, Carrera, Plan_de_estudio, AsignacionPlanEstudio, Silabo, Guia,
    ModeloIAConfig, ProgramaAsignatura2026
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
            usuario=self.docente_user, plan_de_estudio=self.plan
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
