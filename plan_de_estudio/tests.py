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
    Asignatura, Carrera, Plan_de_estudio, AsignacionPlanEstudio, Silabo, Guia,
    ModeloIAConfig, ProveedorIA, ProgramaAsignatura2026, PlanTematico, ConfiguracionSistema
)
from plan_de_estudio.forms import SilaboForm, ExportarAsignacionesForm
from plan_de_estudio.ranking_utils import construir_ranking_docentes, obtener_rango_ciclo_actual


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
        resp = self.client.get(reverse('pwa_sw'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/javascript', resp['Content-Type'])
        self.assertEqual(resp['Service-Worker-Allowed'], '/')
        self.assertIn('no-cache', resp['Cache-Control'])
        body = resp.content.decode('utf-8')
        self.assertIn("const OFFLINE_URL = \"/offline/\"", body)
        self.assertIn('fetchWithTimeout', body)

    def test_offline_page_disponible(self):
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
        self.asignacion = AsignacionPlanEstudio.objects.create(usuario=self.usuario, plan_de_estudio=self.plan)
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
            usuario=self.docente_user, plan_de_estudio=self.plan_pendiente, silabos_creados=0
        )
        self.asig_c = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_user, plan_de_estudio=self.plan_completado, silabos_creados=11
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

        # Ana: 100% completo (11 sílabos + 11 guías)
        self.asig_ana = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_top, plan_de_estudio=self.plan_1,
            bloque="Primer bloque - 8:00", silabos_creados=11, guias_creadas=11
        )

        # Carlos: 2 asignaciones -> en plan_2 tiene 2 sílabos reales y 1 guía real en BD; en plan_4 tiene 0/0
        self.asig_carlos_1 = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_medio, plan_de_estudio=self.plan_2,
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
            bloque="Tercer bloque - 12:20", silabos_creados=0, guias_creadas=0
        )

        # Luis: 0% sin avance
        self.asig_luis = AsignacionPlanEstudio.objects.create(
            usuario=self.docente_cero, plan_de_estudio=self.plan_3,
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

        # Orden esperado mayor a menor: Ana (100.0%), Carlos (3/44 = 6.8%), Luis (0.0%)
        self.assertEqual(docentes[0]['username'], 'ana_gomez')
        self.assertEqual(docentes[0]['puesto'], 1)
        self.assertEqual(docentes[0]['porcentaje_general'], 100.0)
        self.assertEqual(docentes[0]['estado'], 'cumplido')

        self.assertEqual(docentes[1]['username'], 'carlos_ruiz')
        self.assertEqual(docentes[1]['puesto'], 2)
        self.assertEqual(docentes[1]['total_silabos'], 2)
        self.assertEqual(docentes[1]['total_guias'], 1)
        self.assertEqual(docentes[1]['total_entregables'], 3)
        self.assertEqual(docentes[1]['esperado_entregables'], 44)
        self.assertEqual(docentes[1]['porcentaje_general'], 6.8)
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
        # Mover la asignación de Luis a un año anterior fuera del ciclo actual
        fecha_historica = timezone.now() - datetime.timedelta(days=400)
        AsignacionPlanEstudio.objects.filter(pk=self.asig_luis.pk).update(fecha_asignacion=fecha_historica)

        data_actual = construir_ranking_docentes(alcance='actual', alcance_explicito=True)
        self.assertEqual(data_actual['total_asignaciones_ciclo'], 3)
        self.assertEqual(data_actual['total_asignaciones_historico'], 4)
        self.assertEqual([d['username'] for d in data_actual['docentes']], ['ana_gomez', 'carlos_ruiz'])

        data_todas = construir_ranking_docentes(alcance='todas', alcance_explicito=True)
        self.assertEqual([d['username'] for d in data_todas['docentes']], ['ana_gomez', 'carlos_ruiz', 'luis_mora'])

        # Si ninguna asignación está en el ciclo actual y no hay parámetro explícito, hace fallback a 'todas'
        AsignacionPlanEstudio.objects.all().update(fecha_asignacion=fecha_historica)
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
            usuario=self.usuario, plan_de_estudio=self.plan
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
            usuario=self.usuario, plan_de_estudio=self.plan_prog
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

        # 1. Validar regla institucional: exactamente 100 pts por Corte Evaluativo (300 total)
        cortes = calcular_puntajes_por_corte(self.asignacion_prog)
        self.assertEqual(cortes["I Corte Evaluativo"], 100)
        self.assertEqual(cortes["II Corte Evaluativo"], 100)
        self.assertEqual(cortes["III Corte Evaluativo"], 100)

        # 2. Validar cobertura de todas las unidades del programa, horas y progresión semanal de fechas
        silabos = list(Silabo.objects.filter(asignacion_plan=self.asignacion_prog).order_by("encuentros"))
        guias = list(Guia.objects.filter(silabo__asignacion_plan=self.asignacion_prog).order_by("numero_encuentro"))
        self.assertEqual(len(silabos), 11)
        self.assertEqual(len(guias), 11)

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

        # 3. En Encuentro 11 no puede haber fechas de entrega posteriores al cierre
        g11 = guias[-1]
        s11 = silabos[-1]
        for n in range(1, 5):
            fecha_ent = getattr(g11, f"fecha_entrega_{n}")
            self.assertLessEqual(fecha_ent, s11.fecha)

        # 4. El prompt en E11 incluye todas las tareas T1..T4 de guías previas y se mantiene compacto
        self.assertIn("TareaAutonoma E1 T4", prompts_silabo[11])
        self.assertIn("TareaAutonoma E10 T4", prompts_guia[11])
        self.assertLess(len(prompts_silabo[11]), 20000)
        self.assertLess(len(prompts_guia[11]), 20000)


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
            usuario=self.usuario, plan_de_estudio=self.plan
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








