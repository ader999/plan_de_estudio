# Bitácora de Documentación y Cambios - PLANEAUML

## [2026-11-18] Campo Explícito `trimestre_lectivo` en Asignaciones de Plan de Estudio
- **Modelo y Migración (`plan_de_estudio/trimestre_utils.py`, `plan_de_estudio/models.py`, `plan_de_estudio/migrations/0023_asignacionplanestudio_trimestre_lectivo.py`)**:
  - Se creó `trimestre_utils.py` con formato `AAAA-I/II/III/IV`, `validar_trimestre_lectivo()`, `obtener_rango_por_trimestre_lectivo()`, `formatear_trimestre_lectivo()` y `generar_opciones_trimestre_lectivo()`.
  - Se agregó `trimestre_lectivo` (visible, obligatorio, sin `default` en modelo/formulario) a `AsignacionPlanEstudio`, conservando intacto `fecha_asignacion` (`auto_now_add=True`).
  - Se eliminó la clasificación por rangos de `fecha_asignacion` en `AsignacionPlanEstudio.clean()`, validando duplicados por `(usuario, plan_de_estudio, trimestre_lectivo)`.
  - La migración `0023` crea la columna nullable, realiza backfill automático sobre los registros históricos usando su `fecha_asignacion` (`poblar_trimestre_lectivo_existente`) y aplica `NOT NULL`.
- **Admin y Formularios (`plan_de_estudio/forms.py`, `plan_de_estudio/admin.py`)**:
  - Se añadió `AsignacionPlanEstudioAdminForm` (selector obligatorio sin valor inicial al crear) y `TrimestreLectivoFilter` en `AsignacionPlanEstudioAdmin`, exponiendo `trimestre_lectivo_display` en `list_display` y `fecha_asignacion` en `readonly_fields`.
  - Se añadió filtro opcional `trimestre_lectivo` en `ExportarAsignacionesForm` y `exportar_asignaciones_view`.
- **Ranking, Planificador IA, Vistas y PWA (`plan_de_estudio/ranking_utils.py`, `plan_de_estudio/utils/curriculum_planner.py`, `plan_de_estudio/views.py`, `plantillas/*.html`, `plantillas/pwa/sw.js`)**:
  - `construir_ranking_docentes` filtra **Ciclo Actual** por `trimestre_lectivo` en lugar de rangos de `fecha_asignacion` y soporta filtro explícito `trimestre_lectivo`.
  - `calcular_tiempos_y_fechas()` calcula el ciclo y fechas semanales de los 11 encuentros a partir de `asignacion.trimestre_lectivo` (con respaldo a `fecha_asignacion` solo si falta).
  - Se muestra `trimestre_lectivo` junto a `fecha_asignacion` en `inicio.html`, `plan_estudio.html`, `ver_planeacion.html` y `ranking_docentes.html`, y se actualizó `SW_VERSION` a `planeauml-v12`.
- **Pruebas y Verificación (`plan_de_estudio/tests.py`)**:
  - Agregada `TrimestreLectivoAsignacionTest` y actualizadas `AsignacionPlanEstudioModelTest` y `RankingDocentesTest`. `manage.py check`, `makemigrations --check --dry-run` y suite completa (`87` pruebas) pasando (**OK**).

## [2026-11-17] Corrección de Timeout/Pantalla Sin Conexión en Admin (`ProgramaAsignatura2026`)
- **Diagnóstico en Producción (Railway)**:
  - Las trazas HTTP y de red mostraron que `GET /admin/plan_de_estudio/programaasignatura2026/` terminaba en `HTTP 499` exactamente a los `~12,000ms` porque: (1) `ProgramaAsignatura2026Admin` usaba el `list_per_page=100` por defecto; (2) al ser `plan_estudio` nullable (`null=True`), Django Admin omitía `select_related` automático causando ~3 consultas N+1 por fila (`Plan_de_estudio`, `Asignatura`, `Carrera`); (3) el `SELECT *` traía ~35 `TextField` extensos por fila (~893 KB desde PostgreSQL en `us-east4` vía proxy TCP hasta `us-west2`), elevando la respuesta a `~22s+`; y (4) `sw.js` abortaba rutas `BYPASS_PREFIXES` a los `12s` sirviendo `offline.html` ("Sin conexión o señal muy lenta"), mientras un único worker Gunicorn quedaba bloqueado.
- **Optimización de Consultas en Admin (`plan_de_estudio/admin.py`)**:
  - Se añadieron los helpers `_text_field_names()` e `_is_changelist_get()` y `PlanEstudioRelatedFilter`.
  - En `ProgramaAsignatura2026Admin`: `list_per_page = 20`, `list_select_related = ('plan_estudio', 'plan_estudio__asignatura', 'plan_estudio__carrera')` y `defer()` de los campos pesados en `GET` del changelist (manteniendo carga completa en `change` y acciones `POST` como `delete_selected`).
  - En `PlanTematicoAdmin`: `list_select_related`, `Prefetch('planes_de_estudio', ...)` hacia `_prefetched_planes_de_estudio` y `defer()` de `TextField` en changelist `GET`, eliminando la saturación N+1 (~167 consultas → ~8).
  - En `PlanDeEstudioAdmin`: `select_related('carrera', 'asignatura', 'pr')` en `get_queryset()` para acelerar listado y `/admin/autocomplete/`.
  - En `AsignacionPlanEstudioAdmin`, `FiltarSilabo` y `FiltrarGuia`: `list_per_page = 20` y `list_select_related` (más `PlanEstudioRelatedFilter` en `FiltarSilabo`).
- **Resiliencia PWA, Conexiones BD y Concurrencia (`plantillas/pwa/sw.js`, `plan_de_estudio/pwa_views.py`, `plan_de_estudio/settings.py`, `Procfile`)**:
  - `sw.js`: incremento a `SW_VERSION = 'planeauml-v11'`, retorno rápido a `/offline/` cuando `navigator.onLine === false` y timeout ampliado a `45000ms` en `isBypassPath()`.
  - `pwa_views.py`: `service_worker_view` y `offline_view` usan `render_to_string()` + `HttpResponse` logrando `0` consultas SQL por petición (evitando las consultas de `google_classroom_context` en `/sw.js`).
  - `settings.py` y `Procfile`: `CONN_MAX_AGE` (default `120`) + `CONN_HEALTH_CHECKS = True` para reducir handshakes TLS/TCP por petición, y `gunicorn --workers 3 --timeout 120`.
- **Pruebas y Verificación (`plan_de_estudio/tests.py`)**:
  - Se añadió `AdminChangelistPerformanceTest` (validando `<= 10` consultas en `programaasignatura2026` y `plantematico`, `defer()` de `fundamentacion`, soporte `plan_estudio=None`, búsqueda, edición, `delete_selected` y `autocomplete`) y verificación `assertNumQueries(0)` en `PwaAndTwaEndpointsTest`.
  - `manage.py check`, `makemigrations --check --dry-run`, `node --check` sobre `sw.js` renderizado y suite completa (`plan_de_estudio` + `eventos`: `83` pruebas) pasando (**OK**).

## [2026-11-17] Simplificación Visual de Tarjetas en Ranking Docente
- **Plantilla (`plantillas/ranking_docentes.html`)**:
  - Se eliminaron las barras secundarias de desglose de **Sílabos** y **Guías** dentro de cada tarjeta docente, conservando únicamente la barra de progreso general principal y manteniendo el botón **Ver asignaturas** alineado a la derecha para evitar sobrecarga visual (el detalle `Sílabos: X/11` y `Guías: Y/11` por asignatura continúa disponible al desplegar cada tarjeta).
- **PWA (`plantillas/pwa/sw.js`)**:
  - Se actualizó `SW_VERSION` a `planeauml-v10`.
- **Pruebas (`plan_de_estudio/tests.py`)**:
  - Se actualizó `RankingDocentesTest.test_filtros_vista_ranking_docentes` para validar que las tarjetas muestren el botón de asignaturas sin las barras secundarias eliminadas (`6` pruebas pasando, **OK**).

## [2026-11-17] Fase 3 - Flujos de Soporte, Visualización/Exportación DOCX Real y Endurecimiento para Producción
- **Flujo Secuencial de Guías (`plan_de_estudio/views.py`)**:
  - Se agregó `_obtener_silabo_pendiente_guia(asignacion)` para seleccionar el primer sílabo sin guía asociado (`guias__isnull=True, guia__isnull=True`) ordenado por encuentro, reemplazando las selecciones previas `.order_by("-encuentros").first()` y `silabos_creados + 1` que causaban desfases al adelantar sílabos o editar guías existentes.
  - En `ver_formulario_guia` se sincronizan `silabos_creados` y `guias_creadas` desde base de datos (`update_fields`), se redirige a `inicio` al completar las 11 guías, se expone `guias_creadas` en contexto y se informa si todos los sílabos creados ya tienen guía antes de pasar al siguiente encuentro pendiente.
  - En `guardar_guia` se reemplazó el incremento ciego `asignacion.guias_creadas += 1` por el recuento real `Guia.objects.filter(silabo__asignacion_plan=asignacion).count()` para evitar inflación al re-guardar actualizaciones.
  - En `generar_estudio_independiente` se bloquea el `encuentro` al sílabo seleccionado cuando llega `silabo_id`, se usa `_obtener_silabo_pendiente_guia(asignacion)` como respaldo y se protegió el caso legado donde `silabo.asignacion_plan` es `None` (y acceso seguro con `.get(encuentro)` sobre el mapa maestro).
- **Visualización Completa y Exportación DOCX (`plan_de_estudio/views.py`, `plan_de_estudio/documento_secuencia_didactica.py`)**:
  - En `ver_planeacion` se amplió `extract_tareas()` de `for i in (1, 2, 3)` a `for i in (1, 2, 3, 4)` para mostrar las 4 tareas de cada guía en pantalla.
  - En `documento_secuencia_didactica.py` se añadieron `_texto_campo()` y `_entero_texto()` (manejo seguro de `None`, `0` y `MultiSelectField`), se eliminaron todos los textos quemados del 2.º y 3.er momento didáctico reemplazándolos por los campos reales de `Silabo`, se unificaron las tareas `1..4` de `tabla_guia` en bucle y se corrigió la suma de tiempos/puntajes presenciales para evitar que un valor `None` ocultara silenciosamente la sección de guía autodidáctica.
- **Compatibilidad Frontend para Presupuestos Agotados (`static/js/guia_ia.js`, `static/js/silabo_ia.js`, `static/js/guia_guardar.js`, `static/js/guia_wizard.js`, `plantillas/pwa/sw.js`)**:
  - Se corrigió la coerción `0 || ""` al autocompletar campos numéricos (`puntaje`, `tiempo_minutos`, `puntaje_1..4`) para preservar `0` cuando un Corte Evaluativo alcanza `100/100` puntos.
  - Se ajustó la validación de actividades opcionales (`2..4`) en `guia_guardar.js` y `guia_wizard.js` permitiendo `puntaje_k >= 0` (manteniendo `tiempo_minutos_k > 0`) cuando la actividad tiene todos sus campos llenos, evitando falsos bloqueos de guardado sin afectar actividades omitidas (`""`).
  - Se actualizó `SW_VERSION` a `planeauml-v9`.
- **Pruebas y Verificación E2E para Producción (`plan_de_estudio/tests.py`)**:
  - Se añadió `Fase3FlujosYDocumentoTest` (4 pruebas: flujo con sílabos adelantados, re-guardado idempotente, `ver_planeacion` con Tarea #4, exportación DOCX sin placeholders y `silabo.asignacion_plan=None`).
  - Verificación pre-despliegue: `makemigrations --check --dry-run` (sin migraciones pendientes), `collectstatic --dry-run` (`201` archivos), análisis AST Python 3.11 (`0` errores), `node --check` en los 4 JS modificados (`OK`), `manage.py check` (`0` problemas) y suite completa (`plan_de_estudio` + `eventos`: `81` pruebas pasando en `DJANGO_TESTING=1`, **OK**).
  - Verificación E2E en vivo (`DJANGO_TESTING=1`, `gemini-4-hydrogen`, señales Classroom simuladas) completada para `ProgramaAsignatura2026` (`p2026_13`, E1–11 secuenciales) y `PlanTematico` legado (`pt_4`, 3 sílabos adelantados + resto E4–11): `44/44` guardados `HTTP 200`, Cortes `100/100/100` (`300` total) en ambos planes, `24.0h/24h` presenciales y `70.0h/70h` (`p2026_13`) / `48.0h/48h` (`pt_4`) independientes, `11/11` tarjetas con **Tarea #4** en `ver_planeacion` y DOCX global (`89,009` bytes, `176` tablas, `22` secciones de guía, `0` placeholders).

## [2026-11-17] Fase 2 - Lógica Curricular, Presupuestos de Cortes Evaluativos, Soporte Multi-Unidad PlanTematico e Historial Compacto
- **Motor Curricular Compartido (`plan_de_estudio/utils/curriculum_planner.py`)**:
  - Se centralizó `extraer_contexto_asignatura()` para `ProgramaAsignatura2026` (con carga `HT/HP/HI` y bibliografía) y para `PlanTematico` legado usando `plan_de_estudio.get_plan_tematico_efectivo()` (soportando enlace directo `plan_tematico_ref` e inverso `plantematicos_asociados`) recorriendo todas las unidades `1..6` (`""`, `_2`..`_6`) en lugar de limitarse a Unidad I y `total_unidades = 4`.
  - Se implementó `construir_mapa_maestro()` mediante reparto proporcional Hamilton (`reparto_hamilton`) ponderado por horas por unidad para distribuir los 11 encuentros sin omitir unidades, y `formatear_contexto_curricular()` para focalizar cada prompt en la unidad activa.
  - Se implementó `calcular_puntajes_por_corte()` y `calcular_corte_y_presupuesto()` respetando el límite institucional de **100 puntos por Corte Evaluativo** combinado entre sílabos y guías (`I`: E1–E4, `II`: E5–E8, `III`: E9–E11; total 300 pts), delegando `views.get_previous_scores()` al helper único.
  - Se implementó `calcular_tiempos_y_fechas()` para alinear las 11 fechas semanalmente dentro del ciclo calendario del trimestre (`obtener_rango_ciclo_actual`), repartir `horas_presenciales` y `horas_estudio_independiente` del `Plan_de_estudio` y limitar las entregas de la guía al intervalo entre encuentros (`<= fecha_encuentro` en E11).
  - Se implementó `construir_historial_compacto()` incluyendo todas las 4 tareas de guías previas (en lugar de solo `*_1`) en formato resumido para evitar duplicación aula/hogar y reducir la longitud de los prompts.
- **Normalización y Generación (`plan_de_estudio/utils/ai_normalizer.py`, `plan_de_estudio/views.py`)**:
  - Se ampliaron `normalizar_respuesta_silabo()` y `normalizar_respuesta_guia()` para aplicar presupuestos de corte (`corte_forzado`, `forzar_corte`, `presupuesto_objetivo`, `presupuesto_max`, `forzar_exacto`), unidad oficial asignada, calibración horaria (`minutos_clase_objetivo`, `minutos_totales_objetivo`), ajuste de fechas semanales y ventana `fecha_entrega_min..max` en cierre E11.
  - Se refactorizaron `generar_silabo` y `generar_estudio_independiente` eliminando el código duplicado y la instrucción errónea de 100 puntos por guía individual, incorporando diferenciación aula/hogar, variedad de técnicas y regla de cierre E11.
- **Pruebas y Simulación en Vivo (`plan_de_estudio/tests.py`)**:
  - Se actualizó `test_generar_y_guardar_silabo_y_guia_directo_sin_400` al presupuesto por corte y se añadió `CurriculumPlannerFase2Test`.
  - `DJANGO_TESTING=1 manage.py check` (0 problemas) y `manage.py test plan_de_estudio eventos` (77 pruebas pasando, **OK**).
  - En simulación en vivo aislada (`DJANGO_TESTING=1`) con `gemini-4-hydrogen`: `PlanTematico` avanzó `Unidad I -> Unidad II -> Unidad III` en E1/E5/E9; los 11 encuentros de `ProgramaAsignatura2026` cerraron `22/22` guardados (`HTTP 200`), cortes exactos `{'I': 100, 'II': 100, 'III': 100}` (`300` total), `24.00h / 24h` presenciales (`1,440` min), `70.00h / 70h` independientes (`4,200` min), entregas E11 `<= 2026-11-14` y prompt máximo en E11 reducido a `23,247` chars (sílabo) / `25,034` chars (guía) con todas las tareas T1..T4 previas.

## [2026-11-17] Fase 1 - Corrección de Contrato JSON, Normalización de Opciones IA y Compatibilidad Frontend
- **Estructura Base (`static/data/datos.json`)**:
  - Se reemplazó `tiempo_segundo_momento` por `tiempo_segundo_momento_teorica` y `tiempo_segundo_momento_practica` en `campos_silabo`, `estructura_silabo` y `primer_encuentro`, alineando el ejemplo del prompt con `Silabo` y `SilaboForm`.
  - Se estandarizaron los campos múltiples de `primer_encuentro` (`tipo_tercer_momento`, `eje_transversal`, `tecnica_evaluacion`, `tipo_evaluacion`, `agente_evaluador`) en formato de arreglo JSON.
- **Normalización Estricta (`plan_de_estudio/utils/ai_normalizer.py`)**:
  - Se creó el módulo `ai_normalizer.py` con `normalizar_respuesta_silabo()` y `normalizar_respuesta_guia()` para mapear variantes/tildes/plurales hacia los `choices` exactos de `Silabo` y `Guia` (ej. `"Lista de cotejo"` → `"Listas de cotejo"`, `"Diagnóstica y Formativa"` → `["Diagnóstica", "Formativa"]`), respetar `max_choices=2`, proteger `codigo` y `encuentros`/`numero_encuentro`, aplanar tareas anidadas (`tarea_1..4`), validar enteros/fechas ISO y acotar la suma de puntajes de cada guía a `<= 100`.
- **Generación y Extracción JSON (`plan_de_estudio/ai_generators.py`, `plan_de_estudio/views.py`)**:
  - En `ai_generators.py` se incorporó `_extraer_objeto_json` con decodificación balanceada y `ast.literal_eval`, modo `tipo_respuesta='silabo'|'guia'` en `procesar_respuesta_ai` y `generar_respuesta_ai` para activar `response_mime_type='application/json'` en Google Gemini y omitir la inyección de las 14 llaves heredadas obsoletas (manteniendo compatibilidad cuando `tipo_respuesta=None`), además de actualizar el fallback de DeepSeek.
  - En `views.py` (`generar_silabo` y `generar_estudio_independiente`), se agregaron al prompt de sílabos las listas faltantes (`TECNICA_EVALUACION_LIST`, `TIPO_EVALUACION_LIST`, `INSTRUMENTO_EVALUACION_LIST`, `AGENTE_EVALUADOR_LIST`, `PERIODO_TIEMPO_LIST`), se validaron parámetros numéricos y se aplicó `normalizar_respuesta_silabo` / `normalizar_respuesta_guia`.
- **Frontend y PWA (`static/js/silabo_ia.js`, `static/js/guia_ia.js`, `plantillas/pwa/sw.js`)**:
  - En `silabo_ia.js` se protegió `#id_codigo` y `#id_encuentros` para no sobrescribir los valores del servidor, se añadió respaldo para `tiempo_segundo_momento` legado, `timeout: 120000` y soporte de coincidencia sin acentos ni mayúsculas y división de opciones combinadas en `setCheckboxMultiple`.
  - En `guia_ia.js` se hizo `marcarAgentesEvaluadores` insensible a mayúsculas/acentos y se normalizaron arreglos en `criterios_evaluacion` y `recursos_didacticos`.
  - Se incrementó `SW_VERSION` a `planeauml-v8`.
- **Pruebas y Verificación (`plan_de_estudio/tests.py`)**:
  - Se agregó `AINormalizerAndContratoFase1Test`. `node --check`, `manage.py check`, `manage.py test plan_de_estudio` (50 pruebas) y `manage.py test eventos` (25 pruebas) pasando (**OK**); prueba en vivo de Encuentro 1 con `gemini-4-hydrogen` completó `generar_silabo` → `guardar_silabo` (`HTTP 200`, 0 incidencias JS, 35 llaves) y `generar_estudio_independiente` → `guardar_guia` (`HTTP 200`, 0 incidencias JS, 60 llaves).

## [2026-11-17] Sección de Ranking de Cumplimiento Docente
- **Modelo y Migración (`plan_de_estudio/models.py`, `plan_de_estudio/migrations/0022_configuracionsistema_mostrar_ranking_docentes.py`)**:
  - Se agregó `mostrar_ranking_docentes` (`default=True`) a `ConfiguracionSistema` para permitir desde el panel administrativo alternar la visibilidad del ranking para docentes vs solo administradores.
- **Lógica de Cálculo y Agregación (`plan_de_estudio/ranking_utils.py`)**:
  - Se implementó `obtener_rango_ciclo_actual` (alineado con los trimestres calendario Mar–May, Jun–Ago, Sep–Nov, Dic–Feb) y `construir_ranking_docentes`.
  - Consolida en una sola consulta con `Count(..., distinct=True)` las entregas por docente (`11` sílabos + `11` guías = `22` entregables por asignación), calcula porcentaje global, porcentaje por tipo, asignaciones completas y pendientes, asigna el puesto canónico (`1..N`) y genera listas destacadas de **Mayor Cumplimiento** y **Prioridad de Seguimiento**.
  - Soporta dos alcances temporales (`Ciclo Actual` y `Todas las Asignaciones`, con respaldo automático al histórico cuando el ciclo actual aún no tiene asignaciones y no se forzó el parámetro), ordenamiento (`Mayor Cumplimiento` y `Rezagados Primero`), búsqueda por docente/asignatura y filtros por carrera, trimestre del plan y estado.
- **Vista, Ruta y Plantillas (`plan_de_estudio/views.py`, `plan_de_estudio/urls.py`, `plantillas/ranking_docentes.html`, `plantillas/base.html`, `plantillas/inicio.html`)**:
  - Se creó la ruta `/ranking-docentes/` (`ranking_docentes`) protegida con `@login_required` y validada contra `ConfiguracionSistema.mostrar_ranking_docentes` (los administradores siempre conservan acceso).
  - Se diseñó `plantillas/ranking_docentes.html` con tarjetas KPI, cuadro de honor, prioridad de seguimiento, filtros responsivos y desglose colapsable por asignatura con enlace directo a `ver_planeacion`.
  - Se añadió el enlace **Ranking Docente** en el menú principal (`plantillas/base.html`) y acceso rápido en `plantillas/inicio.html`.
- **Panel Admin (`plan_de_estudio/admin.py`, `plantillas/admin/plan_de_estudio/copiaseguridad/change_list.html`, `plantillas/admin/plan_de_estudio/asignacionplanestudio/change_list.html`)**:
  - Se refactorizó el cambio de banderas de `ConfiguracionSistema` en `_toggle_config_boolean` y se añadió la ruta `toggle-ranking-docentes/` (`toggle_ranking_docentes_view`) junto con la fila **Ranking de Cumplimiento Docente** en **Copias de Seguridad / Configuración** y acceso directo desde **Asignaciones**.
- **PWA (`plantillas/pwa/sw.js`)**: Se actualizó `SW_VERSION` a `planeauml-v7`.
- **Pruebas (`plan_de_estudio/tests.py`)**: Se agregó `RankingDocentesTest` (6 pruebas). Suite completa pasando (**OK**).

## [2026-11-16] Wizard Mobile-First de 5 Pasos y Borrador Local en Guía de Estudio Independiente
- **Plantillas (`plantillas/formulario_estudio_independiente.html`, `plantillas/partials/guia_actividad_campos.html`)**:
  - Se reorganizó el formulario extenso de creación de guías en un **wizard de 5 pasos** optimizado para móviles: `1. Base e IA` (asistente IA + información general), `2. Primera Actividad (Obligatoria)`, `3. Segunda Actividad (Opcional, sola)`, `4. Tercera y Cuarta Actividad (Opcionales, juntas en acordeones colapsables independientes)` y `5. Revisión, Puntajes y Guardado`.
  - Se extrajo el bloque reutilizable de 14 campos por actividad a `plantillas/partials/guia_actividad_campos.html` (usando `custom_filters.get_attribute`), limpiando los espacios iniciales heredados en todos los `<textarea>` y el bloque `<style>`/`@media` mal cerrado al final de la plantilla.
  - Se aplicaron las mejoras ya validadas en móvil: cabecera del wizard en flujo normal (`overflow: visible !important` en tarjeta raíz, sin `position: sticky`), barra inferior fija en móvil con `width: auto !important` en botones compactos, chips táctiles para `agente_evaluador_1..4[]`, presets rápidos de tiempo (`30m`–`120m`), `inputmode="numeric"`, desglose de puntajes/tiempos e icono simple (`fa-check-circle`) en el resumen del Paso 5.
- **Lógica de Wizard y Persistencia en Navegador (`static/js/guia_wizard.js`)**:
  - Implementado `window.GuiaWizard` con `localStorage` por usuario, asignación y encuentro (`planeauml_guia_draft_v1_<usuario>_<asignacion>_<encuentro>`), sin escritura al backend hasta el envío final.
  - Añadidos acordeones colapsables en Paso 4, detección de actividades opcionales omitidas vs parciales, botón de limpieza rápida por actividad opcional (`Limpiar`), restauración automática de borrador con banner `#draft-restored-banner` y botón **Empezar de cero** (`#btn-descartar-borrador`).
- **Validación, Guardado e IA (`static/js/guia_guardar.js`, `static/js/guia_ia.js`)**:
  - Agregada validación por paso (`validarPasoFormulario`), alertas inline en Bootstrap sin `alert()` bloqueantes, salto automático al paso y acordeón del primer campo con error (`goToStepForElement`) y refactorización en bucle para tareas opcionales 2–4 en `recopilarDatosFormulario()` y `aplicarDatosActividad()`.
  - `guardarFormulario()` elimina el borrador local (`window.GuiaWizard.clearDraft()`) únicamente tras confirmación exitosa del backend; `guia_ia.js` sincroniza métricas, acordiones y borrador mediante `window.GuiaWizard.onAfterAiAutofill()`.
- **PWA (`plantillas/pwa/sw.js`)**: Actualizado `SW_VERSION` a `planeauml-v6`.
- **Pruebas (`plan_de_estudio/tests.py`)**: Agregado `test_formulario_guia_renderiza_wizard_5_pasos_y_borrador_local` en `SilaboFormularioYGeneracionTest`. `node --check`, `manage.py check` y suite completa (66 pruebas) pasando (**OK**).

## [2026-11-15] Corrección de Solapamiento de Cabecera sobre Títulos de Paso en Wizard de Sílabos
- **Diagnóstico**: La regla global `.card { overflow: hidden; }` en `static/css/base.css` convertía a `.card.shadow-lg` en contenedor con scroll interno oculto; combinada con `position: sticky` en `.wizard-sticky-header` y `scrollIntoView` en pestañas, desplazaba el contenido verticalmente ocultando parcialmente el encabezado del paso actual (`card-header`, p. ej. *Primer Momento Didáctico*).
- **Plantilla y CSS (`plantillas/formulario_silabo.html`)**:
  - Se fijó `#silabo-wizard-root .card.shadow-lg { overflow: visible !important; }` para eliminar el scroll interno oculto.
  - Se pasó `.wizard-sticky-header` a flujo normal (`position: relative; z-index: 1;`) para evitar que flote sobre títulos o campos al desplazarse.
- **Lógica de Scroll (`static/js/silabo_wizard.js`)**:
  - Se reemplazó `scrollIntoView` de las pestañas por desplazamiento horizontal exclusivo (`scrollTo`/`scrollLeft`) dentro de `.wizard-tabs-scroll`.
  - `goToStep` calcula la altura dinámica de `#main-navbar` al desplazar hacia la cabecera del paso.
- **PWA (`plantillas/pwa/sw.js`)**: Actualizado `SW_VERSION` a `planeauml-v5`.

## [2026-11-15] Wizard Mobile-First de 6 Pasos y Borrador Local en Generación de Sílabos
- **Plantilla (`plantillas/formulario_silabo.html`)**:
  - Se dividió el formulario extenso de generación de sílabos en un **wizard interactivo de 6 pasos**: `1. Base, IA y Objetivos` (fusión de datos generales, asistente IA y objetivos), `2. 1er Momento (Entrada)`, `3. 2do Momento (Desarrollo)`, `4. 3er Momento (Salida) y Ejes Transversales`, `5. Evaluación Dinámica` y `6. Revisión y Guardado`.
  - Se añadió cabecera sticky con barra de progreso, contador de pasos, tiempo total en vivo y pestañas horizontales desplazables, además de una barra inferior fija en dispositivos móviles (`@media (max-width: 767.98px)`) para navegación cómoda con una sola mano.
  - Se convirtieron los grupos de checkboxes múltiples (`tipo_tercer_momento`, `eje_transversal`, `tecnica_evaluacion`, `tipo_evaluacion`, `agente_evaluador`) en **chips táctiles** con contador (`X / 2`), se agregaron botones rápidos de minutos (`10m`–`60m`), `inputmode="numeric"` y un resumen interactivo en el Paso 6.
- **Lógica de Wizard y Persistencia en Navegador (`static/js/silabo_wizard.js`)**:
  - Implementada la navegación por pasos, estado de completitud por sección, auto-ajuste de `textarea` y guardado automático del progreso en `localStorage` bajo clave única por usuario, asignación y encuentro (`planeauml_silabo_draft_v1_<usuario>_<asignacion>_<encuentro>`), sin tocar el backend ni la base de datos.
  - Agregada restauración automática del borrador al reabrir el formulario y botón **Empezar de cero** (`#btn-descartar-borrador`) para descartarlo manualmente.
- **Validación, Guardado e IA (`static/js/silabo_validar.js`, `static/js/silabo_guardar.js`, `static/js/silabo_ia.js`)**:
  - `validarCamposObligatorios(stepNumber)` valida solo el paso actual al avanzar con **Siguiente** y todo el formulario al intentar guardar; tanto la validación frontal como `resaltarCamposConError` redirigen automáticamente al paso donde exista un error.
  - `guardarSilabo` elimina el borrador de `localStorage` únicamente tras confirmación exitosa del backend.
  - `silabo_ia.js` invoca `SilaboWizard.onAfterAiAutofill()` tras autocompletar para actualizar chips, alturas, estado de pasos y guardar el avance local.
- **PWA (`plantillas/pwa/sw.js`)**: Actualizado `SW_VERSION` a `planeauml-v4`.
- **Pruebas (`plan_de_estudio/tests.py`)**: Agregado `test_formulario_silabo_renderiza_wizard_6_pasos_y_borrador_local` en `SilaboFormularioYGeneracionTest`. Suite completa: 65 pruebas pasando (**OK**) y `manage.py check` sin incidencias.

## [2026-11-14] Opción en Configuración para Activar/Desactivar Descarga de Planes Temáticos para Docentes
- **Panel Admin (`plan_de_estudio/admin.py`, `plantillas/admin/plan_de_estudio/copiaseguridad/change_list.html`)**:
  - Se integró `ConfiguracionSistema.get_solo()` en `CopiaSeguridadAdmin.changelist_view` y se añadió la ruta `toggle-descarga-plan-tematico/` (`toggle_descarga_plan_tematico_view`).
  - En la tabla **Lista de Herramientas y Acciones** de **Copias de Seguridad / Configuración** se agregó la fila **Descarga de Plan Temático (Docentes)** con indicador de estado (`Habilitada` / `Desactivada`) y botón de acción (`Desactivar` / `Activar`).
- **Panel de Docentes (`plantillas/inicio.html`)**:
  - Se condicionó la visualización del botón y enlace de descarga **Plan Temático** (y el aviso cuando no hay plan asignado) en las pestañas **Pendientes** y **Archivados** al valor de `config_sistema.permitir_descarga_plan_tematico` (inyectado globalmente por `google_classroom_context`).
- **Pruebas (`plan_de_estudio/tests.py`)**:
  - Se agregó `ConfiguracionPlanTematicoDescargaTest` validando el toggle desde el admin, restricción de permisos para docentes y visibilidad/ocultamiento del enlace en `/`. Suite completa: 39 pruebas pasando (**OK**).

## [2026-11-14] Corrección de Alertas Silenciosas al Generar Sílabo y Control de Encuentro 1–11
- **Diagnóstico**: Al presionar el botón **Generar** en `plantillas/formulario_silabo.html` cuando ocurría un error (por ejemplo, al quedar el formulario en `Encuentro (12)` y ser rechazado con HTTP 400 por `generar_silabo`, o ante cualquier error de IA/red), `mostrarMensajeError` en `static/js/silabo_guardar.js` intentaba insertar la alerta en `$("#form-guardar-silabo .card-footer")`, un selector inexistente en `formulario_silabo.html`, ocultando completamente el error y dando la apariencia de que el botón no hacía nada.
- **Alertas y Manejo de Errores (`plantillas/formulario_silabo.html`, `static/js/silabo_guardar.js`, `static/js/silabo_ia.js`)**:
  - Se agregaron `#silabo-alert-container` (junto al botón **Generar**) y `#guardar-alert-container` (junto al botón **Guardar Formularios**).
  - Se actualizó `obtenerContenedorAlertaSilabo`, `mostrarMensajeExito` y `mostrarMensajeError` para resolver contenedores válidos sin fallar silenciosamente y sanitizar el texto mediante `.text(...)`.
  - En `silabo_ia.js` se extrae el mensaje real del servidor (`xhr.responseJSON.error` / `xhr.responseText`), se maneja sesión/CSRF (`403`), fallos de red (`status 0`) y respuestas sin `silabo_data`, y se muestra confirmación al autocompletar.
- **Control de Encuentros 1–11 y Sincronización (`plan_de_estudio/views.py`, `plantillas/inicio.html`, `plantillas/pwa/sw.js`)**:
  - `ver_formulario_silabo` sincroniza `asignacion.silabos_creados` con `asignacion.silabo_set.count()`, determina el próximo encuentro faltante en el rango `1..11` y redirige a `inicio` con mensaje de advertencia si los 11 sílabos ya existen (evitando llegar a `Encuentro (12)`).
  - `guardar_silabo` recalcula `asignacion.silabos_creados = asignacion.silabo_set.count()` y `generar_silabo` captura `(ValueError, TypeError)` al validar `encuentro`.
  - Se endurecieron los enlaces deshabilitados de `plantillas/inicio.html` (`aria-disabled="true"`, `href="#"`) y se actualizó `SW_VERSION` a `planeauml-v3` en `plantillas/pwa/sw.js`.
- **Pruebas (`plan_de_estudio/tests.py`)**: Se agregó `SilaboFormularioYGeneracionTest` (36 pruebas pasando).

## [2026-11-14] Corrección de Contraste en Card de Descarga APK (`plantillas/tutoriales.html`)
- Se reemplazó el gradiente oscuro heredado (`rgba(15, 23, 42, 0.65)`) de la tarjeta de descarga APK en el **Centro de Recursos** por una superficie clara (`#ffffff` a `#eff6ff`) con borde y acento lateral corporativo (`var(--corp-primary)`), alineada con el tema claro activo en `static/css/base.css`.
- Se ajustaron los colores de título (`var(--text-primary)`), texto descriptivo (`var(--text-secondary)`), metadatos (`var(--text-muted)`), etiquetas `<code>` e íconos para garantizar alto contraste y legibilidad.

## [2026-11-14] Compilación Automática de APK en Cada Push, Actualización Obligatoria en TWA y Centro de Recursos
- **CI/CD Android TWA (`.github/workflows/build-apk.yml`, `twa/`)**:
  - Se añadió la configuración base `twa/twa-manifest.json` y `twa/package.json` (`@bubblewrap/cli`) junto con el workflow `Build and Release Android APK` disparado en cada `push` a `main`.
  - Se configuraron los secretos de firma en GitHub (`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASS`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASS`) usando el mismo keystore (`com.planeauml.pwa`) para permitir actualizaciones sobre la APK instalada sin desinstalar y mantener válido `assetlinks.json`.
  - En cada compilación se incrementa automáticamente `appVersionCode` (`GITHUB_RUN_NUMBER + 1`), se inyecta `startUrl` con `/?source=twa&apk_version=<VERSION_CODE>`, se verifica la firma con `apksigner` y se publica en GitHub Releases (`latest`) los artefactos `PLANEAUML.apk`, `PLANEAUML.aab` y `app-version.json`.
- **Actualización Obligatoria en APK (`plan_de_estudio/pwa_views.py`, `plantillas/pwa/body.html`, `plantillas/pwa/sw.js`)**:
  - Nuevos endpoints `/app/version.json` (`app_version_view`, caché TTL de 60s contra GitHub Releases con respaldo por variables de entorno) y `/app/descargar-apk/` (`app_download_view`).
  - Se incrementó `SW_VERSION` a `planeauml-v2` y se excluyó `/app/` del caché del Service Worker.
  - En `plantillas/pwa/body.html` se detecta cuando la app se ejecuta dentro de la APK TWA (`?source=twa&apk_version=...` o `referrer` `android-app://com.planeauml.pwa`) y, si existe una compilación superior disponible, se muestra una pantalla bloqueante no cerrable para descargar e instalar la nueva APK; el acceso desde navegador web normal permanece libre.
- **Sección "Centro de Recursos" (`plantillas/base.html`, `plantillas/tutoriales.html`, `plan_de_estudio/urls.py`, `plan_de_estudio/views.py`)**:
  - Se renombró la entrada de menú y página `Tutoriales` a **Centro de Recursos** (`/centro-de-recursos/`, manteniendo redirección desde `/tutoriales/`).
  - Se integró una tarjeta destacada para descargar la última APK oficial de PLANEAUML con versión, paquete y tamaño cuando esté disponible.

## [2026-11-14] Soporte PWA, Service Worker Tolerante a Redes Lentas y Endpoint TWA (`assetlinks.json`)
- **Iconos PWA**: Generados `static/img/pwa-icon-192.png`, `static/img/pwa-icon-512.png` y `static/img/pwa-icon-512-maskable.png` a partir de `static/img/logouml.png`.
- **Vistas y Rutas PWA/TWA (`plan_de_estudio/pwa_views.py`, `plan_de_estudio/urls.py`)**:
  - `/manifest.json` (`manifest_view`): Manifiesto Web App con `display: standalone`, colores corporativos e iconos 192/512/maskable.
  - `/sw.js` (`service_worker_view`): Service Worker en raíz (`Service-Worker-Allowed: /`, `no-cache`).
  - `/offline/` (`offline_view`): Vista autónoma de respaldo sin dependencias externas (`plantillas/pwa/offline.html`).
  - `/.well-known/assetlinks.json` (`assetlinks_view`): Verificación Digital Asset Links configurable mediante `ANDROID_PACKAGE_NAME` y `ANDROID_ASSETLINKS_SHA256`.
- **Resiliencia en Malas Conexiones (`plantillas/pwa/sw.js`)**:
  - Caché `Stale-While-Revalidate` para `/static/` y `Cache-First` para CDNs externos (Bootstrap, FontAwesome, jQuery, Google Fonts) para eliminar bloqueos de renderizado.
  - Estrategia `Network-First` con timeout (`4.5s` si hay copia en caché, `12s` en primera visita) y respaldo automático en caché o `/offline/` para vistas de lectura, excluyendo rutas sensibles (`/admin/`, `/login/`, `/google/`, `/oauth2callback/`, `/api/`, descargas y generación IA) y limpiando caché de páginas al cerrar sesión (`/logout/`).
- **Integración Global (`plantillas/pwa/head.html`, `plantillas/pwa/body.html`)**:
  - Incluido en `plantillas/base.html` y `plantillas/eventos/base_eventos.html` con barra superior de progreso de navegación, indicador de modo sin conexión y registro automático del Service Worker.
- **Pruebas (`plan_de_estudio/tests.py`)**: Agregada la clase `PwaAndTwaEndpointsTest` validando manifiesto, Service Worker, vista offline, `assetlinks.json` e integración en plantillas base.

## [2026-11-14] Proveedores Personalizados de IA (`ProveedorIA`) y Mejoras Visuales en Admin
- **Modelo y Migración**: Se agregó el modelo `ProveedorIA` (`nombre`, `formato_api` con soporte para OpenAI-compatible, Google Gemini y Anthropic, y `base_url` con método `base_url_normalizada()`) y se vinculó mediante `proveedor_custom` a `ModeloIAConfig` (migración `0021_proveedoria_alter_modeloiaconfig_proveedor_and_more`).
- **Panel Admin (`Copias de Seguridad / Configuración`)**:
  - Se añadió formulario desplegable (`+ Agregar nuevo proveedor personalizado`) y opción `+ Agregar nuevo proveedor personalizado...` directamente dentro del selector `Proveedor de IA *`.
  - Se añadieron endpoints `guardar-proveedor-ia/` y `eliminar-proveedor-ia/<id>/` en `CopiaSeguridadAdmin` y soporte de `custom:<id>` en `consultar-modelos-ia/` y `guardar-modelo-ia/`.
  - Se corrigió el recorte vertical de texto en los `<select>` del formulario en modo oscuro (`height: auto; min-height: 36px; line-height: 1.4; padding: 7px 10px;`).
- **Generación y Extracción**: `ai_generators.py` (`listar_modelos_disponibles`, `generar_texto_crudo_ai`, `get_default_config`, `generar_respuesta_ai`) y `utils/gemini_parser.py` (`parse_curriculum_with_ai`) resuelven ahora el `base_url` y `formato_api` de proveedores personalizados.
- **Pruebas**: Ampliada la suite en `plan_de_estudio/tests.py` para cubrir creación, consulta de modelos, guardado de modelos, despacho de generación y eliminación de `ProveedorIA`.

## [2026-11-14] Gestión Dinámica de Proveedores, Keys y Modelos de IA en Copias de Seguridad / Configuración

### Contexto
Se requería administrar desde la sección **Copias de Seguridad / Configuración** del panel administrativo los proveedores de IA, sus claves API y los modelos disponibles tanto para la lista mostrada a los docentes (Sílabo y Guía de Estudio Independiente) como para la extracción de texto en **Programas de asignatura 2026** (`.docx`), manteniendo compatibilidad con la configuración previa basada en variables de entorno (`.env`).

### Cambios Realizados
- **`plan_de_estudio/models.py` y migración `0020_modeloiaconfig.py`**:
  - Se creó el modelo `ModeloIAConfig` para almacenar `proveedor` (`google`, `openai`, `deepseek`, `groq`, `openrouter`, `anthropic`), `api_key`, `modelo_id`, `nombre_mostrar`, `disponible_docentes`, `usar_para_extraccion` (único por defecto mediante `save()`) y `activo`, junto con la propiedad `api_key_enmascarada`.
- **`plan_de_estudio/ai_generators.py`**:
  - Se añadió `listar_modelos_disponibles(proveedor, api_key)` para consultar en vivo los modelos disponibles de cada proveedor.
  - Se añadieron `resolver_config_modelo`, `generar_texto_crudo_ai` y soporte para Anthropic/Groq/OpenRouter además de Google Gemini, OpenAI y DeepSeek con claves dinámicas, preservando los identificadores legados (`google`, `openai`, `deepseek`) y variables `.env` como fallback.
- **`plan_de_estudio/utils/gemini_parser.py`**:
  - Se actualizó `parse_curriculum_with_ai(docx_file, modelo_config_id=None)` para usar el modelo seleccionado en la importación o el modelo configurado por defecto (`usar_para_extraccion=True`), manteniendo el fallback a `.env`.
- **`plan_de_estudio/admin.py` y plantillas de administración**:
  - En `CopiaSeguridadAdmin` y `plantillas/admin/plan_de_estudio/copiaseguridad/change_list.html` se agregó el formulario de proveedor/key/consulta dinámica de modelos, el selector rápido del modelo extractor para **Programas de asignatura 2026**, la tabla de modelos configurados con acciones (visibilidad para docentes, extractor 2026, activar/desactivar, eliminar) y la vista previa de modelos visibles para docentes.
  - En `ProgramaAsignatura2026Admin.import_docx_view` y `plantillas/admin/plan_de_estudio/programaasignatura2026/import_form.html` se agregó el selector del modelo de IA para extraer texto desde `.docx`.
- **`plan_de_estudio/views.py` y plantillas de docentes**:
  - `ver_formulario_silabo` y `ver_formulario_guia` envían `modelos_ia` activos y habilitados para docentes a `formulario_silabo.html` y `formulario_estudio_independiente.html`, con respaldo automático a las opciones legadas si no hay registros configurados.
- **`Procfile`**:
  - Se añadió `python manage.py migrate --noinput &&` previo al arranque de `gunicorn` para aplicar automáticamente las migraciones pendientes en producción (Railway).

---

## [2026-11-07] Corrección de SyntaxError en `context_processors.py`

### Contexto del Problema
Al acceder a la página principal (`/` o `planeauml.codeader.com`), el servidor arrojaba un error `SyntaxError at /: invalid character '…' (U+2026) (context_processors.py, line 14)` durante la ejecución de `plan_de_estudio.views.inicio`.
La línea 14 de `context_processors.py` había quedado truncada con el carácter suspensivo (`credenciales = Creden…`), impidiendo que Django pudiera compilar el módulo de procesadores de contexto.

### Cambios Realizados
- **`plan_de_estudio/context_processors.py`**:
  - Se completó la función `google_classroom_context(request)` restaurando la recuperación de `CredencialesGoogle` (`credenciales = CredencialesGoogle.objects.get(usuario=request.user)`).
  - Se integró de manera segura la obtención de `config_sistema` (`ConfiguracionSistema.get_solo()`) con manejo de excepciones preventivo.

### Verificación
- Se ejecutó `python -m py_compile plan_de_estudio/context_processors.py` y `python -m compileall` sin errores de sintaxis.
- Se verificó `manage.py check` (0 incidencias).
- Se comprobó mediante el cliente de pruebas de Django la respuesta HTTP 200 en `/` (con sesión de usuario) y la redirección correspondiente para usuarios anónimos.
- Se ejecutó la suite completa de pruebas unitarias (`manage.py test`): 45 pruebas exitosas (**OK**).

---

## [2026-11-07] Corrección de Encuentros (Estandarización a 11) y Optimización de Márgenes Móviles

### Contexto del Problema
1. **Conteo y Paginación de Encuentros:**
   - En la vista de detalle de sílabo (`detalle_silabo_completo.html`), la asignatura "COMUNICACION, EDUCACION Y PROMOCION DE LA SALUD" (Código `E1842`, Asignación ID 275) mostraba "12 encuentros disponibles" y una paginación que llegaba hasta el encuentro 12, a pesar de que el estándar académico del sistema se estandarizó previamente a 11 encuentros.
   - En la base de datos se detectó un registro duplicado (Sílabo ID 517, clon idéntico del Sílabo ID 516 del Encuentro 11) y un desajuste de numeración en el Sílabo ID 469 (marcado con encuentro 4 en lugar de 5).
2. **Márgenes y Experiencia de Lectura en Móviles:**
   - En dispositivos móviles, la combinación de paddings anidados (`#page-content`, `.main-page-container`, y `.post-article`) consumía más de 80px de espacio horizontal innecesario, dejando márgenes laterales excesivos y comprimiendo el texto de los sílabos y guías, dificultando la lectura.

### Cambios Realizados

#### 1. Backend (`plan_de_estudio/views.py`)
- Se aseguró que las vistas `detalle_silabo`, `guia_autodidactica` y `secuencia_didactica` limiten cualquier grupo de sílabos a un máximo de 11 encuentros (`grupo[:11]`), blindando la interfaz ante posibles duplicados en la base de datos.

#### 2. Limpieza de Base de Datos (Asignación ID 275 - E1842)
- Se eliminó el sílabo duplicado ID 517 (encuentro 11 sin guías asociadas).
- Se corrigió el sílabo ID 469 ajustando su valor a `encuentros = 5`, dejando la secuencia completa del 1 al 11.
- Se actualizó el contador `silabos_creados` de la asignación a 11.

#### 3. Optimización de Plantillas HTML
- En `plantillas/detalle_silabo_completo.html`, `plantillas/guia_autodidactica_completa.html` y `plantillas/secuencia_didactica_completa.html`:
  - Se eliminó la clase redundante `.container` dentro del contenedor `#page-content`, evitando anidamientos con doble gutter de Bootstrap.

#### 4. Estilos y Responsive Design en Móviles (CSS)
- `static/css/base.css`:
  - Se añadió la regla `@media (max-width: 767.98px)` con selector `#page-content:has(.blog-post-style), #page-content:has(.main-page-container)` reduciendo el padding lateral a 3px para maximizar el ancho útil de lectura en pantallas pequeñas.
- `static/css/shared_styles.css`:
  - Se añadió `@media (max-width: 767.98px)` anulando el padding horizontal de `.main-page-container` en móviles.
- `static/css/blog_style.css`:
  - Reducción del padding horizontal en `.post-article` a `0.85rem` en pantallas `<= 767.98px`.
  - Ajuste de márgenes laterales a `2px` para mantener los bordes de la tarjeta visibles y aprovechar al máximo el ancho de la pantalla móvil.
  - Ajuste de jerarquía tipográfica (`h1`, `h2`, `lead`, `.momentos-grid`) para lectura fluida y sin saltos de línea bruscos.
