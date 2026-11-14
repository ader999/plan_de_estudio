# Bitácora de Documentación y Cambios - PLANEAUML

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
