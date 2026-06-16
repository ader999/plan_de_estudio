# Guía de Respaldos y Restauración de Base de Datos

Esta guía detalla cómo restaurar los dos tipos de respaldos generados por el sistema (según la disponibilidad de las herramientas del sistema en el servidor).

---

## Tipos de Respaldos Generados

El sistema creará automáticamente una de las siguientes copias de seguridad:
1. **Archivo `.dump` (Nativo de PostgreSQL):** Creado mediante `pg_dump` en formato binario comprimido personalizado. Es la mejor opción para bases de datos relacionales.
2. **Archivo `.json` (Serialización de Django):** Generado como fallback usando el comando nativo `dumpdata` de Django. Se utiliza cuando el comando del sistema `pg_dump` no está disponible.

---

## 1. Restaurar un Respaldo `.dump` (PostgreSQL Nativo)

Para restaurar un archivo `.dump` en tu base de datos de producción (en Railway u otro entorno), necesitarás la herramienta `pg_restore` de PostgreSQL (que se instala junto con el cliente de PostgreSQL).

### Paso 1: Obtener las credenciales de tu base de datos
Busca en tu panel de Railway o en tu archivo `.env` los valores de:
- `DB_HOST` (Servidor)
- `DB_PORT` (Puerto)
- `DB_USER` (Usuario, normalmente `postgres`)
- `DB_PASSWORD` (Contraseña)
- `DB_NAME` (Nombre de la base de datos, normalmente `railway`)

### Paso 2: Ejecutar el comando de restauración
Abre tu consola y ejecuta el siguiente comando reemplazando los valores y el nombre del archivo:

```bash
PGPASSWORD="TU_PASSWORD_AQUI" pg_restore -h TU_HOST_AQUI -p TU_PORT_AQUI -U TU_USER_AQUI -d TU_NAME_AQUI -c --no-owner --no-privileges NOMBRE_RESPALDO.dump
```

*Explicación de los parámetros adicionales:*
- `-c` (o `--clean`): Limpia (elimina) los objetos de la base de datos antes de crearlos. Evita errores por registros duplicados.
- `--no-owner`: No asigna los propietarios de las tablas del respaldo original (útil para Railway, donde el propietario del sistema local puede diferir).
- `--no-privileges`: Evita restaurar privilegios de acceso innecesarios o conflictivos.

---

## 2. Restaurar un Respaldo `.json` (Django loaddata)

Si el respaldo generado tiene extensión `.json`, se trata de una serialización nativa de Django. Para restaurarlo, no necesitas comandos externos de PostgreSQL, solo el CLI de Django.

### Paso 1: Asegurarse de que el servidor está conectado a la base de datos destino
La restauración cargará los datos directamente en la base de datos que esté configurada en el archivo `.env` activo de tu entorno local.

### Paso 2: Ejecutar loaddata
Ejecuta el siguiente comando en la raíz del proyecto para importar los datos:

```bash
venv/bin/python manage.py loaddata NOMBRE_RESPALDO.json
```

*Nota:* Si hay conflictos con tipos de contenidos (`contenttypes`) o permisos de usuario generados por Django de forma automática, podrías necesitar limpiar esas tablas del sistema antes de restaurar, o ejecutarlo en una base de datos vacía.

---

## Recomendaciones de Seguridad

> [!WARNING]
> La restauración de una base de datos sobrescribirá los datos actuales en las tablas restauradas. Realiza siempre una copia de seguridad del estado actual inmediatamente antes de intentar una restauración.
