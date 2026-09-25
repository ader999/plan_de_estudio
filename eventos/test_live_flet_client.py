from django.test import LiveServerTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import sys
import os

# Asegurar que el path incluye la raíz para importar UMLRanking
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from UMLRanking.api_client import APIClient


class LiveFletClientTestCase(LiveServerTestCase):
    def setUp(self):
        self.client = APIClient(self.live_server_url)

        # Crear usuarios
        self.admin_user = User.objects.create_user(
            username="admin_tester",
            password="secure_password_123",
            first_name="Admin",
            last_name="Tester",
            is_superuser=True
        )
        self.jurado_user = User.objects.create_user(
            username="jurado_tester",
            password="secure_password_123",
            first_name="Jurado",
            last_name="Evaluador"
        )

    def test_full_flet_workflow_against_live_backend(self):
        # 1. Login con APIClient de Flet
        login_res = self.client.login("admin_tester", "secure_password_123")
        self.assertTrue(login_res["success"])
        self.assertIsNotNone(self.client.token)
        self.assertEqual(self.client.user["username"], "admin_tester")

        # 2. Consultar perfil 'me'
        me_res = self.client.get_me()
        self.assertTrue(me_res["success"])
        self.assertEqual(me_res["data"]["username"], "admin_tester")

        # 3. Crear nuevo evento desde Flet
        ahora = timezone.now()
        evento_payload = {
            "nombre": "Concurso Nacional de Robótica 2026",
            "descripcion": "Competencia interuniversitaria de robótica móvil",
            "fecha_inicio": (ahora - timedelta(hours=1)).isoformat(),
            "fecha_fin": (ahora + timedelta(hours=5)).isoformat(),
            "requiere_jurado": True
        }
        create_res = self.client.create_evento(evento_payload)
        self.assertTrue(create_res["success"])
        evento_id = create_res["data"]["id"]
        self.assertEqual(create_res["data"]["nombre"], "Concurso Nacional de Robótica 2026")

        # 4. Listar eventos y verificar filtros
        eventos = self.client.get_eventos(status="activos")
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0]["id"], evento_id)
        self.assertTrue(eventos[0]["esta_activo"])

        # 5. Agregar criterios de evaluación
        crit1_res = self.client.add_criterio(evento_id, {
            "nombre": "Diseño Mecánico",
            "descripcion": "Estructura y robustez",
            "puntaje_maximo": 40
        })
        self.assertTrue(crit1_res["success"])
        crit1_id = crit1_res["data"]["id"]

        crit2_res = self.client.add_criterio(evento_id, {
            "nombre": "Algoritmo y Control",
            "descripcion": "Precisión y navegación autónoma",
            "puntaje_maximo": 60
        })
        self.assertTrue(crit2_res["success"])
        crit2_id = crit2_res["data"]["id"]

        # 6. Agregar participantes
        part1_res = self.client.add_participante(evento_id, {
            "nombre": "Robot Rover Alpha",
            "descripcion": "Rover con LiDAR y cámara RGB-D",
            "integrantes": "Lucía Morales, Jorge Ramos"
        })
        self.assertTrue(part1_res["success"])
        part1_id = part1_res["data"]["id"]

        part2_res = self.client.add_participante(evento_id, {
            "nombre": "Dron Avispa X",
            "descripcion": "Cuadricóptero de reconocimiento",
            "integrantes": "David Mendoza"
        })
        self.assertTrue(part2_res["success"])
        part2_id = part2_res["data"]["id"]

        # 7. Asignar jurado
        jurado_add_res = self.client.add_jurado(evento_id, self.jurado_user.id)
        self.assertTrue(jurado_add_res["success"])

        # 8. Consultar detalle del evento
        detalle_res = self.client.get_evento(evento_id)
        self.assertTrue(detalle_res["success"])
        det = detalle_res["data"]
        self.assertEqual(len(det["criterios"]), 2)
        self.assertEqual(len(det["participantes"]), 2)
        self.assertEqual(len(det["jurados"]), 1)
        self.assertEqual(det["total_criterios_score"], 100)

        # 9. Iniciar sesión como Jurado
        jurado_client = APIClient(self.live_server_url)
        jur_login = jurado_client.login("jurado_tester", "secure_password_123")
        self.assertTrue(jur_login["success"])

        # 10. Consultar lista a evaluar
        eval_list_res = jurado_client.get_evaluar_lista(evento_id)
        self.assertTrue(eval_list_res["success"])
        self.assertEqual(len(eval_list_res["data"]["participantes"]), 2)

        # 11. Evaluar participante 1 (Rover Alpha) -> 35 + 50 = 85 pts
        eval_p1_res = jurado_client.submit_evaluacion(evento_id, part1_id, [
            {"criterio_id": crit1_id, "puntaje": 35},
            {"criterio_id": crit2_id, "puntaje": 50},
        ])
        self.assertTrue(eval_p1_res["success"])

        # 12. Evaluar participante 2 (Dron Avispa) -> 40 + 55 = 95 pts
        eval_p2_res = jurado_client.submit_evaluacion(evento_id, part2_id, [
            {"criterio_id": crit1_id, "puntaje": 40},
            {"criterio_id": crit2_id, "puntaje": 55},
        ])
        self.assertTrue(eval_p2_res["success"])

        # 13. Consultar resultados desde el cliente administrador (modo previsualización)
        resultados_res = self.client.get_resultados(evento_id)
        self.assertTrue(resultados_res["success"])
        res_data = resultados_res["data"]
        self.assertTrue(res_data["es_previsualizacion"])
        self.assertEqual(len(res_data["resultados"]), 2)

        # Ganador Dron Avispa X (Puesto 1, 95 pts)
        self.assertEqual(res_data["podio"]["primero"]["participante"]["id"], part2_id)
        self.assertEqual(res_data["podio"]["primero"]["puntaje_promedio"], 95.0)

        # Segundo Puesto Rover Alpha (Puesto 2, 85 pts)
        self.assertEqual(res_data["podio"]["segundo"]["participante"]["id"], part1_id)
        self.assertEqual(res_data["podio"]["segundo"]["puntaje_promedio"], 85.0)

        # 14. Logout
        logout_res = self.client.logout()
        self.assertTrue(logout_res["success"])
        self.assertIsNone(self.client.token)
