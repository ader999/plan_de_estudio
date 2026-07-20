import json
import logging
import time
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.auth.models import User
from plan_de_estudio.models import (
    AsignacionPlanEstudio, Plan_de_estudio, Carrera, Asignatura,
    ProgramaAsignatura2026, Silabo, Guia
)
from plan_de_estudio.ai_generators import generar_respuesta_ai, get_default_config
from plan_de_estudio.views import generar_silabo, generar_estudio_independiente

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Prueba secuencial de la generación por IA con Gemini de 11 encuentros de Sílabos y Guías'

    def add_arguments(self, parser):
        parser.add_argument('--plan_id', type=int, help='ID de la asignación del plan de estudio (opcional)')
        parser.add_argument('--clean', action='store_true', help='Elimina sílabos y guías existentes de la asignación antes de probar')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== INICIANDO PRUEBA DE IA (11 ENCUENTROS - GEMINI) ==='))
        
        plan_id = options.get('plan_id')
        clean = options.get('clean')

        # Buscar o crear una asignación para pruebas
        if plan_id:
            try:
                asignacion = AsignacionPlanEstudio.objects.get(id=plan_id)
            except AsignacionPlanEstudio.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'No se encontró la Asignación con ID {plan_id}'))
                return
        else:
            asignacion = AsignacionPlanEstudio.objects.first()
            if not asignacion:
                self.stderr.write(self.style.ERROR('No hay Asignaciones en la base de datos para probar.'))
                return

        self.stdout.write(f'Usando Asignación ID={asignacion.id}: {asignacion}')

        # Asegurar un usuario para las peticiones mockeadas
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            user = User.objects.create_user(username='test_user', password='password123')

        if clean:
            self.stdout.write('Limpiando Sílabos y Guías previas...')
            Silabo.objects.filter(asignacion_plan=asignacion).delete()

        factory = RequestFactory()
        
        reporte_encuentros = []

        for enc in range(1, 12):
            self.stdout.write(self.style.WARNING(f'\n--- Procesando Encuentro {enc} de 11 ---'))
            inicio_enc = time.time()
            
            res_silabo = {'encuentro': enc, 'silabo_ok': False, 'guia_ok': False, 'errores': []}
            
            # 1. Generar Sílabo
            request_silabo = factory.post('/generar-silabo/', {
                'encuentro': str(enc),
                'plan': str(asignacion.id),
                'modelo_select': 'google'
            })
            request_silabo.user = user

            try:
                response = generar_silabo(request_silabo)
                if response.status_code == 200:
                    data = json.loads(response.content)
                    silabo_data = data.get('silabo_data', {})
                    self.stdout.write(self.style.SUCCESS(f'[Encuentro {enc}] Sílabo generado correctamente por Gemini.'))
                    self.stdout.write(f"  Unidad: {silabo_data.get('unidad')} - {silabo_data.get('nombre_de_la_unidad')}")
                    self.stdout.write(f"  Contenido: {silabo_data.get('contenido_tematico', '')[:100]}...")
                    
                    # Guardar Sílabo en la base de datos
                    silabo_obj, created = Silabo.objects.update_or_create(
                        asignacion_plan=asignacion,
                        encuentros=enc,
                        defaults={
                            'codigo': silabo_data.get('codigo', f'ENC-{enc}'),
                            'fecha': silabo_data.get('fecha') or '2026-03-01',
                            'unidad': silabo_data.get('unidad', 'Unidad I'),
                            'nombre_de_la_unidad': silabo_data.get('nombre_de_la_unidad', ''),
                            'contenido_tematico': silabo_data.get('contenido_tematico', ''),
                            'objetivo_conceptual': silabo_data.get('objetivo_conceptual', ''),
                            'objetivo_procedimental': silabo_data.get('objetivo_procedimental', ''),
                            'objetivo_actitudinal': silabo_data.get('objetivo_actitudinal', ''),
                            'tipo_primer_momento': silabo_data.get('tipo_primer_momento', 'Evaluación diagnóstica'),
                            'detalle_primer_momento': silabo_data.get('detalle_primer_momento', ''),
                            'tiempo_primer_momento': silabo_data.get('tiempo_primer_momento', 20),
                            'recursos_primer_momento': silabo_data.get('recursos_primer_momento', ''),
                            'tipo_segundo_momento_claseteoria': silabo_data.get('tipo_segundo_momento_claseteoria') or silabo_data.get('tipo_segundo_momento_teorica', 'Conferencia'),
                            'clase_teorica': silabo_data.get('clase_teorica', ''),
                            'tipo_segundo_momento_practica': silabo_data.get('tipo_segundo_momento_practica', 'Taller'),
                            'clase_practica': silabo_data.get('clase_practica', ''),
                            'tiempo_segundo_momento_teorica': silabo_data.get('tiempo_segundo_momento_teorica', 45),
                            'tiempo_segundo_momento_practica': silabo_data.get('tiempo_segundo_momento_practica', 45),
                            'recursos_segundo_momento': silabo_data.get('recursos_segundo_momento', ''),
                            'tipo_tercer_momento': silabo_data.get('tipo_tercer_momento', 'Orientación del estudio independiente'),
                            'detalle_tercer_momento': silabo_data.get('detalle_tercer_momento', ''),
                            'tiempo_tercer_momento': silabo_data.get('tiempo_tercer_momento', 10),
                            'recursos_tercer_momento': silabo_data.get('recursos_tercer_momento', ''),
                            'eje_transversal': silabo_data.get('eje_transversal', 'Proyección social'),
                            'detalle_eje_transversal': silabo_data.get('detalle_eje_transversal', ''),
                            'actividad_aprendizaje': silabo_data.get('actividad_aprendizaje', ''),
                            'tecnica_evaluacion': silabo_data.get('tecnica_evaluacion', 'Observación'),
                            'tipo_evaluacion': silabo_data.get('tipo_evaluacion', 'Formativa'),
                            'periodo_tiempo_programado': silabo_data.get('periodo_tiempo_programado', 'I Corte Evaluativo'),
                            'tiempo_minutos': silabo_data.get('tiempo_minutos', 30),
                            'agente_evaluador': silabo_data.get('agente_evaluador', 'Heteroevaluación'),
                            'instrumento_evaluacion': silabo_data.get('instrumento_evaluacion', 'Rúbrica'),
                            'criterios_evaluacion': silabo_data.get('criterios_evaluacion', ''),
                            'puntaje': silabo_data.get('puntaje', 10),
                        }
                    )
                    res_silabo['silabo_ok'] = True
                    res_silabo['silabo_id'] = silabo_obj.id
                else:
                    err = f"Error status HTTP {response.status_code}: {response.content.decode('utf-8')}"
                    self.stderr.write(self.style.ERROR(f"[Encuentro {enc}] Sílabo falló: {err}"))
                    res_silabo['errores'].append(err)
                    continue

            except Exception as e:
                err = f"Excepción en Sílabo {enc}: {str(e)}"
                self.stderr.write(self.style.ERROR(err))
                res_silabo['errores'].append(err)
                continue

            # 2. Generar Guía de Estudio Independiente para este Sílabo
            request_guia = factory.post('/generar-estudio-independiente/', {
                'silabo_id': str(silabo_obj.id),
                'asignacion_id': str(asignacion.id),
                'encuentro': str(enc),
                'modelo': 'google',
                'numero_actividades': '4'
            })
            request_guia.user = user

            try:
                response_g = generar_estudio_independiente(request_guia)
                if response_g.status_code == 200:
                    data_g = json.loads(response_g.content)
                    guia_data = data_g.get('guia_data', {})
                    self.stdout.write(self.style.SUCCESS(f'[Encuentro {enc}] Guía generada correctamente por Gemini.'))
                    
                    # Guardar Guía en la DB
                    actividades = guia_data.get('actividades', [])
                    act_1 = actividades[0] if isinstance(actividades, list) and len(actividades) > 0 else "Lectura y síntesis del contenido"
                    act_2 = actividades[1] if isinstance(actividades, list) and len(actividades) > 1 else "Resolución de ejercicios prácticos"

                    guia_obj, g_created = Guia.objects.update_or_create(
                        silabo=silabo_obj,
                        defaults={
                            'numero_encuentro': enc,
                            'fecha': silabo_obj.fecha,
                            'unidad': silabo_obj.unidad,
                            'nombre_de_la_unidad': silabo_obj.nombre_de_la_unidad,
                            'tipo_objetivo_1': 'Conceptual',
                            'objetivo_aprendizaje_1': guia_data.get('objetivo_conceptual') or silabo_obj.objetivo_conceptual,
                            'contenido_tematico_1': silabo_obj.contenido_tematico,
                            'actividad_aprendizaje_1': act_1,
                            'tecnica_evaluacion_1': silabo_obj.tecnica_evaluacion or 'Observación',
                            'tipo_evaluacion_1': silabo_obj.tipo_evaluacion or 'Formativa',
                            'instrumento_evaluacion_1': silabo_obj.instrumento_evaluacion or 'Rúbrica',
                            'criterios_evaluacion_1': str(guia_data.get('criterios_evaluacion', '')),
                            'agente_evaluador_1': silabo_obj.agente_evaluador or 'Heteroevaluación',
                            'tiempo_minutos_1': 120,
                            'recursos_didacticos_1': str(guia_data.get('recursos', '')),
                            'periodo_tiempo_programado_1': silabo_obj.periodo_tiempo_programado or 'I Corte Evaluativo',
                            'puntaje_1': 10,
                            'fecha_entrega_1': silabo_obj.fecha,
                        }
                    )
                    res_silabo['guia_ok'] = True
                else:
                    err = f"Error status HTTP Guía {response_g.status_code}: {response_g.content.decode('utf-8')}"
                    self.stderr.write(self.style.ERROR(f"[Encuentro {enc}] Guía falló: {err}"))
                    res_silabo['errores'].append(err)

            except Exception as e:
                err = f"Excepción en Guía {enc}: {str(e)}"
                self.stderr.write(self.style.ERROR(err))
                res_silabo['errores'].append(err)

            duracion = round(time.time() - inicio_enc, 2)
            res_silabo['duracion_seg'] = duracion
            reporte_encuentros.append(res_silabo)

        # Resumen Final
        self.stdout.write(self.style.SUCCESS('\n================ RESUMEN DE LA PRUEBA (11 ENCUENTROS) ================'))
        exitosos_silabo = sum(1 for r in reporte_encuentros if r['silabo_ok'])
        exitosos_guia = sum(1 for r in reporte_encuentros if r['guia_ok'])
        
        self.stdout.write(f"Sílabos exitosos: {exitosos_silabo} / 11")
        self.stdout.write(f"Guías exitosas:   {exitosos_guia} / 11")
        
        for r in reporte_encuentros:
            status = "OK" if r['silabo_ok'] and r['guia_ok'] else "CON ERRORES"
            self.stdout.write(f"Encuentro {r['encuentro']}: {status} ({r.get('duracion_seg', 0)}s)")
            if r['errores']:
                for e in r['errores']:
                    self.stdout.write(f"   - Error: {e}")
