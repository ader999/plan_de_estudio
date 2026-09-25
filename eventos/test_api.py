from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from .models import Evento, CriterioEvaluacion, JuradoEvento, Participante, Evaluacion


class EventosAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.creador = User.objects.create_user(username="creador", password="password123", first_name="Carlos", last_name="Creador")
        self.jurado = User.objects.create_user(username="jurado", password="password123", first_name="Ana", last_name="Jurado")
        self.usuario_comun = User.objects.create_user(username="comun", password="password123", first_name="Luis", last_name="Comun")
        self.otro_usuario = User.objects.create_user(username="otro", password="password123", first_name="Mario", last_name="Otro")

        self.token_creador, _ = Token.objects.get_or_create(user=self.creador)
        self.token_jurado, _ = Token.objects.get_or_create(user=self.jurado)
        self.token_comun, _ = Token.objects.get_or_create(user=self.usuario_comun)

        ahora = timezone.now()
        # Evento Activo
        self.evento_activo = Evento.objects.create(
            nombre="Feria de Innovación 2026",
            descripcion="Feria de proyectos universitarios",
            fecha_inicio=ahora - timedelta(hours=2),
            fecha_fin=ahora + timedelta(hours=4),
            requiere_jurado=True,
            creado_por=self.creador
        )

        # Criterios
        self.criterio1 = CriterioEvaluacion.objects.create(
            evento=self.evento_activo,
            nombre="Innovación",
            descripcion="Nivel de novedad",
            puntaje_maximo=40
        )
        self.criterio2 = CriterioEvaluacion.objects.create(
            evento=self.evento_activo,
            nombre="Presentación",
            descripcion="Claridad al exponer",
            puntaje_maximo=60
        )

        # Participantes
        self.participante1 = Participante.objects.create(
            evento=self.evento_activo,
            nombre="Equipo Alfa",
            descripcion="Robot seguidor de línea",
            integrantes="Juan Perez, Maria Lopez"
        )
        self.participante2 = Participante.objects.create(
            evento=self.evento_activo,
            nombre="Equipo Beta",
            descripcion="App de reciclaje",
            integrantes="Pedro Ramirez"
        )

        # Asignar jurado
        JuradoEvento.objects.create(evento=self.evento_activo, usuario=self.jurado)

    # ------------------------------------------------------------------------
    # TESTS DE AUTENTICACIÓN
    # ------------------------------------------------------------------------
    def test_login_exitoso(self):
        response = self.client.post('/api/eventos/auth/login/', {
            'username': 'creador',
            'password': 'password123'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'creador')

    def test_login_fallido(self):
        response = self.client.post('/api/eventos/auth/login/', {
            'username': 'creador',
            'password': 'wrongpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        response = self.client.get('/api/eventos/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'creador')
        self.assertEqual(response.data['full_name'], 'Carlos Creador')

    def test_usuarios_disponibles(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        # Excluyendo jurados ya asignados al evento activo
        response = self.client.get(f'/api/eventos/auth/usuarios-disponibles/{self.evento_activo.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [u['username'] for u in response.data]
        self.assertNotIn('jurado', usernames)
        self.assertIn('otro', usernames)

    # ------------------------------------------------------------------------
    # TESTS DE EVENTOS CRUD
    # ------------------------------------------------------------------------
    def test_listar_eventos(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        response = self.client.get('/api/eventos/eventos/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 1)
        # Verificar campos calculados
        evento_data = next(e for e in response.data if e['id'] == self.evento_activo.id)
        self.assertTrue(evento_data['esta_activo'])
        self.assertFalse(evento_data['ha_finalizado'])
        self.assertEqual(evento_data['total_criterios_score'], 100)
        self.assertEqual(evento_data['participantes_count'], 2)
        self.assertEqual(evento_data['jurados_count'], 1)

    def test_filtrar_eventos_por_estado(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        # Activos
        res_activos = self.client.get('/api/eventos/eventos/?status=activos')
        self.assertEqual(res_activos.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_activos.data), 1)

        # Proximos
        res_proximos = self.client.get('/api/eventos/eventos/?status=proximos')
        self.assertEqual(res_proximos.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_proximos.data), 0)

    def test_crear_evento(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        ahora = timezone.now()
        payload = {
            'nombre': 'Hackathon Inteligencia Artificial',
            'descripcion': 'Competencia de desarrollo con LLMs',
            'fecha_inicio': (ahora + timedelta(days=1)).isoformat(),
            'fecha_fin': (ahora + timedelta(days=2)).isoformat(),
            'requiere_jurado': True
        }
        response = self.client.post('/api/eventos/eventos/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre'], 'Hackathon Inteligencia Artificial')
        self.assertEqual(Evento.objects.filter(nombre='Hackathon Inteligencia Artificial').count(), 1)

    def test_crear_evento_fechas_invalidas(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        ahora = timezone.now()
        payload = {
            'nombre': 'Evento Inválido',
            'fecha_inicio': (ahora + timedelta(days=2)).isoformat(),
            'fecha_fin': (ahora + timedelta(days=1)).isoformat(),
            'requiere_jurado': True
        }
        response = self.client.post('/api/eventos/eventos/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha_fin', response.data)

    def test_detalle_evento_con_anidados(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_jurado.key}')
        response = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['criterios']), 2)
        self.assertEqual(len(response.data['participantes']), 2)
        self.assertEqual(len(response.data['jurados']), 1)
        self.assertTrue(response.data['es_jurado'])
        self.assertFalse(response.data['es_administrador'])

    def test_permisos_editar_evento(self):
        # Usuario común no puede editar evento de otro
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        res_fail = self.client.patch(f'/api/eventos/eventos/{self.evento_activo.id}/', {'nombre': 'Hackeado'}, format='json')
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        # Creador sí puede editar
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        res_ok = self.client.patch(f'/api/eventos/eventos/{self.evento_activo.id}/', {'nombre': 'Nombre Actualizado'}, format='json')
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data['nombre'], 'Nombre Actualizado')

    def test_permisos_eliminar_evento(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        res_fail = self.client.delete(f'/api/eventos/eventos/{self.evento_activo.id}/')
        self.assertEqual(res_fail.status_code, status.HTTP_403_FORBIDDEN)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        res_ok = self.client.delete(f'/api/eventos/eventos/{self.evento_activo.id}/')
        self.assertEqual(res_ok.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Evento.objects.filter(id=self.evento_activo.id).exists())

    # ------------------------------------------------------------------------
    # TESTS DE CRITERIOS Y PARTICIPANTES
    # ------------------------------------------------------------------------
    def test_gestion_criterios(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        # Crear criterio
        res_create = self.client.post(f'/api/eventos/eventos/{self.evento_activo.id}/criterios/', {
            'nombre': 'Impacto Social',
            'descripcion': 'Beneficio a la comunidad',
            'puntaje_maximo': 25
        }, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        criterio_id = res_create.data['id']

        # Modificar criterio
        res_update = self.client.patch(f'/api/eventos/criterios/{criterio_id}/', {
            'puntaje_maximo': 30
        }, format='json')
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(res_update.data['puntaje_maximo'], 30)

        # Eliminar criterio
        res_delete = self.client.delete(f'/api/eventos/criterios/{criterio_id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_200_OK)
        self.assertFalse(CriterioEvaluacion.objects.filter(id=criterio_id).exists())

    def test_gestion_participantes(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        # Crear participante
        res_create = self.client.post(f'/api/eventos/eventos/{self.evento_activo.id}/participantes/', {
            'nombre': 'Equipo Gamma',
            'descripcion': 'Dron autónomo',
            'integrantes': 'Laura, Roberto'
        }, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        part_id = res_create.data['id']

        # Modificar participante
        res_update = self.client.patch(f'/api/eventos/participantes/{part_id}/', {
            'nombre': 'Equipo Gamma Pro'
        }, format='json')
        self.assertEqual(res_update.status_code, status.HTTP_200_OK)
        self.assertEqual(res_update.data['nombre'], 'Equipo Gamma Pro')

        # Eliminar participante
        res_delete = self.client.delete(f'/api/eventos/participantes/{part_id}/')
        self.assertEqual(res_delete.status_code, status.HTTP_200_OK)
        self.assertFalse(Participante.objects.filter(id=part_id).exists())

    # ------------------------------------------------------------------------
    # TESTS DE GESTIÓN DE JURADO
    # ------------------------------------------------------------------------
    def test_gestion_jurado(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        # Asignar a 'otro_usuario' como jurado
        res_add = self.client.post(f'/api/eventos/eventos/{self.evento_activo.id}/jurados/', {
            'usuario_id': self.otro_usuario.id
        }, format='json')
        self.assertEqual(res_add.status_code, status.HTTP_201_CREATED)
        jurado_rel_id = res_add.data['id']

        # Remover jurado
        res_remove = self.client.delete(f'/api/eventos/jurados/{jurado_rel_id}/')
        self.assertEqual(res_remove.status_code, status.HTTP_200_OK)
        self.assertFalse(JuradoEvento.objects.filter(id=jurado_rel_id).exists())

    # ------------------------------------------------------------------------
    # TESTS DE EVALUACIÓN
    # ------------------------------------------------------------------------
    def test_evaluar_participante_como_jurado(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_jurado.key}')

        # 1. Obtener lista a evaluar
        res_lista = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/')
        self.assertEqual(res_lista.status_code, status.HTTP_200_OK)
        # Inicialmente debe estar pendiente
        self.assertEqual(res_lista.data['participantes'][0]['estado_evaluacion'], 'Pendiente')

        # 2. Consultar formulario para participante1
        res_form = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/{self.participante1.id}/')
        self.assertEqual(res_form.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_form.data['criterios']), 2)

        # 3. Enviar evaluación válida
        payload = {
            'evaluaciones': [
                {'criterio_id': self.criterio1.id, 'puntaje': 35},
                {'criterio_id': self.criterio2.id, 'puntaje': 50}
            ]
        }
        res_eval = self.client.post(
            f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/{self.participante1.id}/',
            payload,
            format='json'
        )
        self.assertEqual(res_eval.status_code, status.HTTP_200_OK)

        # Verificar que se crearon los registros de evaluación
        evals = Evaluacion.objects.filter(jurado=self.jurado, participante=self.participante1)
        self.assertEqual(evals.count(), 2)
        score_total = sum(e.puntaje for e in evals)
        self.assertEqual(score_total, 85)

        # 4. Verificar que en la lista ahora aparece 'Completado'
        res_lista_despues = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/')
        part1_data = next(p for p in res_lista_despues.data['participantes'] if p['id'] == self.participante1.id)
        self.assertEqual(part1_data['estado_evaluacion'], 'Completado')

    def test_evaluar_puntaje_excedido_falla(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_jurado.key}')
        payload = {
            'evaluaciones': [
                {'criterio_id': self.criterio1.id, 'puntaje': 999},  # Max es 40
                {'criterio_id': self.criterio2.id, 'puntaje': 10}
            ]
        }
        res_eval = self.client.post(
            f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/{self.participante1.id}/',
            payload,
            format='json'
        )
        self.assertEqual(res_eval.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('errors', res_eval.data)

    def test_usuario_no_jurado_no_puede_evaluar(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        response = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/evaluar/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------------
    # TESTS DE RESULTADOS / TABLA DE POSICIONES
    # ------------------------------------------------------------------------
    def test_resultados_privados_mientras_evento_activo(self):
        # Usuario común no puede ver resultados mientras está activo
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        res_privado = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/resultados/')
        self.assertEqual(res_privado.status_code, status.HTTP_403_FORBIDDEN)

        # Creador sí puede ver previsualización
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_creador.key}')
        res_admin = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/resultados/')
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertTrue(res_admin.data['es_previsualizacion'])

    def test_resultados_calculados_en_evento_finalizado(self):
        # Finalizar el evento
        self.evento_activo.fecha_inicio = timezone.now() - timedelta(days=2)
        self.evento_activo.fecha_fin = timezone.now() - timedelta(days=1)
        self.evento_activo.save()

        # Calificar participante 1 (85 pts)
        Evaluacion.objects.create(jurado=self.jurado, participante=self.participante1, criterio=self.criterio1, puntaje=35)
        Evaluacion.objects.create(jurado=self.jurado, participante=self.participante1, criterio=self.criterio2, puntaje=50)

        # Calificar participante 2 (95 pts)
        Evaluacion.objects.create(jurado=self.jurado, participante=self.participante2, criterio=self.criterio1, puntaje=40)
        Evaluacion.objects.create(jurado=self.jurado, participante=self.participante2, criterio=self.criterio2, puntaje=55)

        # Usuario común ahora puede ver resultados
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_comun.key}')
        response = self.client.get(f'/api/eventos/eventos/{self.evento_activo.id}/resultados/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['es_previsualizacion'])

        resultados = response.data['resultados']
        self.assertEqual(len(resultados), 2)
        # Participante 2 en puesto 1 con 95 pts
        self.assertEqual(resultados[0]['participante']['id'], self.participante2.id)
        self.assertEqual(resultados[0]['puesto'], 1)
        self.assertEqual(resultados[0]['puntaje_promedio'], 95.0)

        # Participante 1 en puesto 2 con 85 pts
        self.assertEqual(resultados[1]['participante']['id'], self.participante1.id)
        self.assertEqual(resultados[1]['puesto'], 2)
        self.assertEqual(resultados[1]['puntaje_promedio'], 85.0)

        # Podio
        self.assertEqual(response.data['podio']['primero']['participante']['id'], self.participante2.id)
        self.assertEqual(response.data['podio']['segundo']['participante']['id'], self.participante1.id)
