# Bitácora de Documentación y Cambios - PLANEAUML

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
