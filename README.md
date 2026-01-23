# Sistema de Gestión de Planes de Estudio

Este es un sistema web desarrollado en **Django** diseñado para facilitar la gestión, creación, actualización y seguimiento de los planes de estudio y sílabos académicos.

## 📋 Descripción

El proyecto permite a los docentes y administradores gestionar la información académica de manera eficiente. Su objetivo principal es estandarizar y agilizar el proceso de diseño curricular, asegurando que los sílabos cumplan con los requisitos institucionales.

## 🚀 Características Principales

*   **Gestión de Sílabos:** Formularios completos para la creación y actualización de sílabos (`formulario_silabo.html`, `actualizar_silabo.html`).
*   **Validación de Datos:** Sistema de validación en tiempo real para asegurar la integridad de la información ingresada (validaciones en cliente y servidor).
*   **Notificaciones Automáticas:** Envío de correos electrónicos para recordatorios sobre la entrega o actualización de planes (`emails/recordatorio_plan.html`).
*   **Exportación de Documentos:** Capacidad para manejar plantillas (Excel/Word) para la generación de reportes oficiales.
*   **Interfaz Intuitiva:** Diseño web limpio y funcional.

## 🛠️ Tecnologías Utilizadas

*   **Backend:** Python, Django Framework.
*   **Frontend:** HTML5, CSS3, JavaScript (Validaciones personalizadas).
*   **Base de Datos:** SQLite (por defecto en desarrollo) / PostgreSQL (recomendado para producción).

## 🔧 Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <https://github.com/ader999/plan_de_estudio.git>
    cd plan_de_estudio
    ```

2.  **Crear y activar un entorno virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # En Linux/Mac
    # venv\Scripts\activate  # En Windows
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Realizar migraciones:**
    ```bash
    python manage.py migrate
    ```

5.  **Ejecutar el servidor de desarrollo:**
    ```bash
    python manage.py runserver
    ```

## 📚 Documentación

Para una guía detallada sobre la arquitectura, instalación y funcionamiento del sistema, consulta el manual técnico oficial:
👉 [Manual Técnico del Sistema](https://ajrepozitorio.codeader.com/post/13/)

## 📄 Licencia

Este proyecto se distribuye bajo una **Licencia MIT Modificada**.

> **NOTA IMPORTANTE:** El uso de este software es libre, incluso para fines comerciales, pero **requiere obligatoriamente la atribución al autor original** en la interfaz de usuario (sección de créditos), visible a no más de 3 niveles de profundidad.

Para más detalles legales y condiciones de uso, consulta el archivo [LICENCIA.md](./LICENCIA.md).

---
Desarrollado con ❤️ por [Ader Zeas/ader999]
