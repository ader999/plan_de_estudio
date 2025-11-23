/**
 * guia_actualizar.js
 * Script para manejar la validación del formulario de actualización de la guía de estudio.
 * Adaptado de guia_guardar.js
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('actualizarGuiaForm');
    if (form) {
        form.addEventListener('submit', function(event) {
            // Prevenir el envío del formulario para realizar la validación primero
            event.preventDefault();

            if (validarFormulario()) {
                // Si la validación es exitosa, se procede con el envío
                const submitButton = document.getElementById('submitButton');
                const spinner = submitButton.querySelector('.spinner-border');
                const buttonText = submitButton.querySelector('.button-text');

                // Desactivar botón y mostrar spinner
                submitButton.disabled = true;
                if (spinner) spinner.classList.remove('d-none');
                if (buttonText) buttonText.textContent = 'Actualizando...';
                
                // Enviar el formulario
                form.submit();
            } else {
                // Opcional: Hacer scroll al primer campo con error
                const primerElementoInvalido = form.querySelector('.is-invalid');
                if (primerElementoInvalido) {
                    primerElementoInvalido.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });
                }
            }
        });
    }

    // Añadir listeners para actualizar la suma de puntajes en tiempo real
    const camposPuntaje = document.querySelectorAll('input[name^="puntaje_"]');
    camposPuntaje.forEach(campo => {
        campo.addEventListener('input', actualizarSumaPuntajes);
    });

    // Calcular la suma inicial al cargar la página
    actualizarSumaPuntajes();
});


/**
 * Validación principal del formulario
 */
function validarFormulario() {
    let formularioValido = true;
    const mensajesError = [];

    // Limpiar validaciones previas
    document.querySelectorAll('#actualizarGuiaForm .is-invalid').forEach(el => el.classList.remove('is-invalid'));
   document.querySelectorAll('#actualizarGuiaForm .is-invalid-parent').forEach(el => el.classList.remove('is-invalid-parent'));
   document.querySelectorAll('#actualizarGuiaForm .checkbox-group.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    // 1. Validar puntajes
    const puntaje1 = parseInt(document.getElementById('puntaje_1')?.value) || 0;
    const puntaje2 = parseInt(document.getElementById('puntaje_2')?.value) || 0;
    const puntaje3 = parseInt(document.getElementById('puntaje_3')?.value) || 0;
    const puntaje4 = parseInt(document.getElementById('puntaje_4')?.value) || 0;

    if (puntaje1 < 0 || puntaje2 < 0 || puntaje3 < 0 || puntaje4 < 0) {
        mensajesError.push("Los puntajes no pueden ser negativos.");
        if (puntaje1 < 0) document.getElementById('puntaje_1')?.classList.add('is-invalid');
        if (puntaje2 < 0) document.getElementById('puntaje_2')?.classList.add('is-invalid');
        if (puntaje3 < 0) document.getElementById('puntaje_3')?.classList.add('is-invalid');
        if (puntaje4 < 0) document.getElementById('puntaje_4')?.classList.add('is-invalid');
        formularioValido = false;
    }

    const sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;
    if (sumaPuntajes > 100) {
        mensajesError.push(`La suma de los puntajes no puede exceder 100. Suma actual: ${sumaPuntajes}.`);
        document.querySelectorAll('input[name^="puntaje_"]').forEach(el => el.classList.add('is-invalid'));
        formularioValido = false;
    }

    // 2. Validar campos requeridos (Generales y Tarea 1)
    const camposFaltantes = [];
    const camposRequeridos = [
        "fecha", "unidad", "nombre_de_la_unidad", "tipo_objetivo_1", "objetivo_aprendizaje_1",
        "contenido_tematico_1", "actividad_aprendizaje_1", "tecnica_evaluacion_1", "tipo_evaluacion_1",
        "instrumento_evaluacion_1", "criterios_evaluacion_1", "tiempo_minutos_1", "recursos_didacticos_1",
        "periodo_tiempo_programado_1", "puntaje_1", "fecha_entrega_1"
    ];

    camposRequeridos.forEach(id => {
        const campo = document.getElementById(id);
        if (campo && campo.value.trim() === '') {
            campo.classList.add('is-invalid');

            // Si el campo es un <select>, a menudo es mejor aplicar el estilo de error
            // a su contenedor padre para que sea visible.
            if (campo.tagName.toLowerCase() === 'select') {
                const parentDiv = campo.closest('.mb-3'); // Busca el div contenedor más cercano
                if (parentDiv) {
                    parentDiv.classList.add('is-invalid-parent'); // Usaremos una clase custom para no interferir con otros estilos
                }
            }

            const label = document.querySelector(`label[for='${id}']`);
            camposFaltantes.push(label ? label.textContent.trim() : id);
            formularioValido = false;
        }
    });
    
   // La validación para el campo de checkboxes 'agente_evaluador_1' ha sido omitida intencionadamente.
   // Se ha decidido delegar esta validación específica al backend (Django) para centralizar la lógica
   // y evitar complejidades en el script del lado del cliente. El backend se asegurará de que
   // al menos una opción sea seleccionada para los campos obligatorios.



    if (camposFaltantes.length > 0) {
        mensajesError.push(`Por favor, complete los siguientes campos obligatorios: ${camposFaltantes.join(', ')}.`);
    }

    // 3. Validar actividades opcionales (2, 3, 4)
    if (!validarActividadOpcional(2, mensajesError)) formularioValido = false;
    if (!validarActividadOpcional(3, mensajesError)) formularioValido = false;
    if (!validarActividadOpcional(4, mensajesError)) formularioValido = false;

    // Mostrar todos los errores juntos
    if (mensajesError.length > 0) {
        alert(mensajesError.join('\n\n'));
    }

    return formularioValido;
}

/**
 * Valida una actividad opcional (2, 3 o 4)
 */
function validarActividadOpcional(numActividad, mensajesError) {
    const camposIds = [
        `tipo_objetivo_${numActividad}`, `objetivo_aprendizaje_${numActividad}`, `contenido_tematico_${numActividad}`,
        `actividad_aprendizaje_${numActividad}`, `tecnica_evaluacion_${numActividad}`, `tipo_evaluacion_${numActividad}`,
        `instrumento_evaluacion_${numActividad}`, `criterios_evaluacion_${numActividad}`, `tiempo_minutos_${numActividad}`,
        `recursos_didacticos_${numActividad}`, `periodo_tiempo_programado_${numActividad}`, `puntaje_${numActividad}`,
        `fecha_entrega_${numActividad}`
    ];

    let algunCampoConInfo = false;
    let todosCamposLlenos = true;
    const camposVacios = [];

    camposIds.forEach(id => {
        const campo = document.getElementById(id);
        if (campo) {
            if (campo.value.trim() !== '') {
                algunCampoConInfo = true;
            } else {
                todosCamposLlenos = false;
                camposVacios.push(id);
            }
        }
    });

    // Se elimina la validación de 'agente_evaluador' del lado del cliente.
    // Esta validación ahora es responsabilidad exclusiva del backend.

    if (!algunCampoConInfo) {
        return true; // Actividad vacía es válida
    }

    if (algunCampoConInfo && !todosCamposLlenos) {
        mensajesError.push(`La Tarea ${numActividad} está incompleta. Por favor, complete todos sus campos o déjelos todos vacíos.`);
        camposVacios.forEach(id => {
            const campo = document.getElementById(id);
            if (campo) campo.classList.add('is-invalid');
        });
       // Se omite la validación visual de 'agente_evaluador' para las tareas opcionales en el cliente.
       // La lógica de que si la tarea está parcialmente completa, todos los campos deben ser llenados,
       // será manejada por el backend.
        return false;
    }

    return true;
}

/**
 * Actualiza la suma de puntajes en la UI
 */
function actualizarSumaPuntajes() {
    const puntaje1 = parseInt(document.getElementById('puntaje_1')?.value) || 0;
    const puntaje2 = parseInt(document.getElementById('puntaje_2')?.value) || 0;
    const puntaje3 = parseInt(document.getElementById('puntaje_3')?.value) || 0;
    const puntaje4 = parseInt(document.getElementById('puntaje_4')?.value) || 0;

    const suma = puntaje1 + puntaje2 + puntaje3 + puntaje4;

    const sumaPuntajesEl = document.getElementById('sumaPuntajes');
    if (sumaPuntajesEl) {
        sumaPuntajesEl.textContent = suma;
        if (suma > 100 || puntaje1 < 0 || puntaje2 < 0 || puntaje3 < 0 || puntaje4 < 0) {
            sumaPuntajesEl.classList.remove('text-success');
            sumaPuntajesEl.classList.add('text-danger');
        } else {
            sumaPuntajesEl.classList.remove('text-danger');
            sumaPuntajesEl.classList.add('text-success');
        }
    }
}