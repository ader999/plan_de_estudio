# Bitácora de Documentación y Cambios - PLANEAUML

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
