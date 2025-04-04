/**
 * formulario_silabo.js
 * Script para manejar la funcionalidad del formulario de sílabo
 */

$(document).ready(function() {
    // Inspeccionar los IDs de los campos del formulario (para depuración)
    console.log('Inspeccionando IDs de los campos del formulario:');
    $('#form-guardar-silabo input, #form-guardar-silabo select, #form-guardar-silabo textarea').each(function() {
        console.log($(this).attr('id') + ': ' + $(this).attr('name'));
    });
    
    // Manejar el envío del formulario de generación de sílabo
    $('#silabo-form').on('submit', function(e) {
        e.preventDefault();
        
        // Mostrar spinner
        mostrarSpinner();
        
        // Deshabilitar el botón de generar
        $('#boton-generar').prop('disabled', true);
        
        // Crear un objeto FormData con los datos del formulario
        const formData = new FormData(this);
        
        // Realizar la solicitud AJAX
        $.ajax({
            url: $(this).attr('action'),
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                console.log('Respuesta recibida:', response);
                
                // Verificar si la respuesta contiene los datos del sílabo
                if (response.silabo_data) {
                    const silaboData = response.silabo_data;
                    
                    // Rellenar los campos del formulario con los datos recibidos
                    $('#id_codigo').val(silaboData.codigo || '');
                    $('#id_encuentros').val(silaboData.encuentros || '');
                    $('#id_fecha').val(silaboData.fecha || '');
                    $('#id_unidad').val(silaboData.unidad || '');
                    $('#id_nombre_de_la_unidad').val(silaboData.nombre_de_la_unidad || '');
                    $('#id_contenido_tematico').val(silaboData.contenido_tematico || '');
                    
                    $('#id_objetivo_conceptual').val(silaboData.objetivo_conceptual || '');
                    $('#id_objetivo_procedimental').val(silaboData.objetivo_procedimental || '');
                    $('#id_objetivo_actitudinal').val(silaboData.objetivo_actitudinal || '');
                    
                    $('#id_tipo_primer_momento').val(silaboData.tipo_primer_momento || '');
                    $('#id_detalle_primer_momento').val(silaboData.detalle_primer_momento || '');
                    $('#id_tiempo_primer_momento').val(silaboData.tiempo_primer_momento || '');
                    
                    $('#id_tipo_segundo_momento_claseteoria').val(silaboData.tipo_segundo_momento_claseteoria || '');
                    $('#id_clase_teorica').val(silaboData.clase_teorica || '');
                    $('#id_tipo_segundo_momento_practica').val(silaboData.tipo_segundo_momento_practica || '');
                    $('#id_clase_practica').val(silaboData.clase_practica || '');
                    $('#id_tiempo_segundo_momento').val(silaboData.tiempo_segundo_momento || '');
                    
                    $('#id_tipo_tercer_momento').val(silaboData.tipo_tercer_momento || '');
                    $('#id_detalle_tercer_momento').val(silaboData.detalle_tercer_momento || '');
                    $('#id_tiempo_tercer_momento').val(silaboData.tiempo_tercer_momento || '');
                    $('#id_recursos_segundo_momento').val(silaboData.recursos_segundo_momento || '');
                    
                    $('#id_eje_transversal').val(silaboData.eje_transversal || '');
                    $('#id_detalle_eje_transversal').val(silaboData.detalle_eje_transversal || '');
                    $('#id_actividad_aprendizaje').val(silaboData.actividad_aprendizaje || '');
                    $('#id_tecnica_evaluacion').val(silaboData.tecnica_evaluacion || '');
                    $('#id_tipo_evaluacion').val(silaboData.tipo_evaluacion || '');
                    $('#id_instrumento_evaluacion').val(silaboData.instrumento_evaluacion || '');
                    $('#id_agente_evaluador').val(silaboData.agente_evaluador || '');
                    $('#id_criterios_evaluacion').val(silaboData.criterios_evaluacion || '');
                    $('#id_puntaje').val(silaboData.puntaje || '');
                    $('#id_periodo_tiempo_programado').val(silaboData.periodo_tiempo_programado || '');
                    $('#id_tiempo_minutos').val(silaboData.tiempo_minutos || '');
                    
                    // Verificar si los valores se establecieron correctamente
                    console.log('Valores establecidos:');
                    console.log('objetivo_conceptual:', $('#id_objetivo_conceptual').val());
                    console.log('objetivo_procedimental:', $('#id_objetivo_procedimental').val());
                    console.log('objetivo_actitudinal:', $('#id_objetivo_actitudinal').val());

                    // Agregar logging específico para los campos problemáticos
                    console.log('--- Campos problemáticos ---');
                    console.log('JSON completo:', JSON.stringify(silaboData, null, 2));
                    console.log('tipo_segundo_momento_practica (valor en JSON):', silaboData.tipo_segundo_momento_practica);
                    console.log('¿Existe el elemento en DOM?', $('#id_tipo_segundo_momento_practica').length > 0 ? 'SÍ' : 'NO');
                    console.log('tipo_segundo_momento_practica (valor en formulario):', $('#id_tipo_segundo_momento_practica').val());
                    
                    console.log('recursos_segundo_momento (valor en JSON):', silaboData.recursos_segundo_momento);
                    console.log('¿Existe el elemento en DOM?', $('#id_recursos_segundo_momento').length > 0 ? 'SÍ' : 'NO');
                    console.log('recursos_segundo_momento (valor en formulario):', $('#id_recursos_segundo_momento').val());
                    
                    try {
                        // Asignar valores directamente utilizando el DOM para los campos problemáticos
                        if (silaboData.tipo_segundo_momento_practica) {
                            const practica = document.querySelector('#id_tipo_segundo_momento_practica');
                            if (practica) {
                                practica.value = silaboData.tipo_segundo_momento_practica;
                                console.log('Asignación directa a tipo_segundo_momento_practica:', silaboData.tipo_segundo_momento_practica);
                            }
                        }
                        
                        if (silaboData.recursos_segundo_momento) {
                            const recursos = document.querySelector('#id_recursos_segundo_momento');
                            if (recursos) {
                                recursos.value = silaboData.recursos_segundo_momento;
                                console.log('Asignación directa a recursos_segundo_momento:', silaboData.recursos_segundo_momento);
                            }
                        }
                        
                        console.log('Asignación directa realizada');
                        
                        // Trigger change event para que se apliquen los estilos
                        $('#id_tipo_segundo_momento_practica, #id_recursos_segundo_momento').trigger('change');
                    } catch (e) {
                        console.error('Error en asignación directa:', e);
                    }
                    
                    console.log('periodo_tiempo_programado (valor en JSON):', silaboData.periodo_tiempo_programado);
                    console.log('periodo_tiempo_programado (valor en formulario):', $('#id_periodo_tiempo_programado').val());
                    console.log('tiempo_minutos (valor en JSON):', silaboData.tiempo_minutos);
                    console.log('tiempo_minutos (valor en formulario):', $('#id_tiempo_minutos').val());
                    
                    // Resaltar los campos que han sido rellenados
                    highlightFilledFields();
                } else {
                    console.error('No se encontró silabo_data en la respuesta');
                }
            },
            error: function(xhr) {
                console.error('Error en la solicitud:', xhr.responseText);
                alert('Hubo un error al generar el sílabo. Por favor, intente nuevamente.');
            },
            complete: function() {
                // Restaurar el botón de generar y ocultar spinners
                $('#boton-generar').prop('disabled', false);
                $('.spinner').addClass('d-none');
                
                // Mostrar nuevamente el texto y el sparkle del botón
                $('#boton-generar .text, #boton-generar .sparkle').removeClass('d-none');
            }
        });
    });
    
    // Manejar el botón de guardar formularios
    $('#guardarFormularioBtn').on('click', function() {
        // Mostrar spinner de guardado
        $('#spinnerGuardar').removeClass('d-none');
        $(this).prop('disabled', true);
        
        // Guardar el formulario de sílabo
        guardarSilabo();
    });
    
    // Inicializar manejo de cambios en los campos
    initializeFieldChangeHandling();
});

/**
 * Función para guardar el sílabo
 */
function guardarSilabo() {
    // Validar campos obligatorios
    if (!validarCamposObligatorios()) {
        resetearEstadoBotonGuardar();
        return false;
    }
    
    // Obtener el ID de asignación de la URL actual
    const currentUrl = window.location.pathname;
    const asignacionId = currentUrl.split('/').filter(Boolean).pop();
    
    const formData = new FormData(document.getElementById('form-guardar-silabo'));
    
    $.ajax({
        url: `/guardar_silabo/${asignacionId}/`,
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            console.log('Sílabo guardado:', response);
            
            // Guardar el ID del sílabo en un atributo data para usarlo más tarde
            if (response.silabo_id) {
                $('#form-guardar-silabo').data('silabo_id', response.silabo_id);
            }
            
            // Verificar si hay una URL de redirección
            if (response.redirect_url) {
                // Mostrar un mensaje breve antes de redirigir
                mostrarMensajeExito('Sílabo guardado con éxito. Redirigiendo...');
                
                // Esperar un breve momento antes de redirigir
                setTimeout(function() {
                    window.location.href = response.redirect_url;
                }, 1500);
                return;
            }
            
            mostrarMensajeExito('Sílabo guardado con éxito');
            resetearEstadoBotonGuardar();
        },
        error: function(xhr) {
            console.error('Error al guardar sílabo:', xhr.responseText);
            
            // Intentar parsear la respuesta JSON
            try {
                const errorResponse = JSON.parse(xhr.responseText);
                if (errorResponse.errors) {
                    // Mostrar errores del backend en los campos correspondientes
                    resaltarCamposConError(errorResponse.errors);
                    
                    // Mostrar mensaje de error detallado
                    mostrarMensajeError('Por favor, complete todos los campos obligatorios marcados en rojo.');
                } else {
                    alert('Error al guardar el sílabo. Por favor, intente nuevamente.');
                }
            } catch(e) {
                alert('Error al guardar el sílabo. Por favor, intente nuevamente.');
            }
            
            resetearEstadoBotonGuardar();
        }
    });
}

/**
 * Función para mostrar mensaje de éxito
 * @param {string} mensaje - Mensaje a mostrar en la alerta
 */
function mostrarMensajeExito(mensaje) {
    // Crear alerta de éxito
    const alertHTML = `
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <strong>¡Éxito!</strong> ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Insertar alerta antes del botón de guardar
    $(alertHTML).insertBefore('#guardarFormularioBtn').parent();
    
    // Desaparecer automáticamente después de 5 segundos
    setTimeout(function() {
        $('.alert-success').alert('close');
    }, 5000);
}

/**
 * Función para resetear el estado del botón de guardar
 */
function resetearEstadoBotonGuardar() {
    $('#spinnerGuardar').addClass('d-none');
    $('#guardarFormularioBtn').prop('disabled', false);
}

/**
 * Función para resaltar campos rellenados
 */
function highlightFilledFields() {
    $('.form-control, .form-select').each(function() {
        if ($(this).val() && $(this).val().trim() !== '') {
            $(this).addClass('border-success');
        }
    });
}

/**
 * Función para mostrar spinner durante la generación
 */
function mostrarSpinner() {
    // Mostrar los spinners quitando la clase d-none
    $('.spinner').removeClass('d-none');
    
    // Ocultar el texto y el sparkle del botón
    $('#boton-generar .text, #boton-generar .sparkle').addClass('d-none');
    
    return true;
}

/**
 * Función para inicializar el manejo de cambios en los campos
 */
function initializeFieldChangeHandling() {
    // Seleccionar todos los campos con la clase 'form-control' y 'form-select' SOLO en el formulario principal
    const fields = document.querySelectorAll('#form-guardar-silabo .form-control, #form-guardar-silabo .form-select');
    
    // Función para verificar si el valor contiene letras
    function containsLetters(value) {
        return /[a-zA-Z]/.test(value);
    }
    
    // Función para manejar el cambio de contenido
    function handleInputChange(event) {
        const field = event.target;
        
        // Verificar si el campo tiene contenido
        if (field.value && field.value.trim() !== '') {
            // Si contiene letras (no es solo números o caracteres especiales)
            if (containsLetters(field.value)) {
                field.classList.add('border-success');
                field.classList.remove('border-danger');
            }
        } else {
            field.classList.remove('border-success');
            field.classList.remove('border-danger');
        }
    }
    
    // Agregar eventos a los campos de texto y select
    fields.forEach(field => {
        // Manejar el evento 'input' para campos de texto
        if (field.tagName === 'INPUT' && field.type !== 'checkbox' && field.type !== 'radio') {
            field.addEventListener('input', handleInputChange);
        }
        // Manejar el evento 'change' para selects y textareas
        else if (field.tagName === 'SELECT' || field.tagName === 'TEXTAREA') {
            field.addEventListener('change', handleInputChange);
        }
        
        // Verificar el estado inicial
        if (field.value && field.value.trim() !== '') {
            if (containsLetters(field.value)) {
                field.classList.add('border-success');
            }
        }
    });
}

/**
 * Función para validar campos obligatorios antes de enviar el formulario
 * @returns {boolean} true si todos los campos obligatorios están completados, false en caso contrario
 */
function validarCamposObligatorios() {
    // Lista de campos obligatorios (IDs de los inputs/selects/textareas)
    const camposObligatorios = [
        // Información General
        'id_fecha',
        'id_unidad',
        'id_nombre_de_la_unidad',
        'id_contenido_tematico',
        
        // Objetivos
        'id_objetivo_conceptual',
        'id_objetivo_procedimental',
        'id_objetivo_actitudinal',
        
        // Primer momento didáctico
        'id_tipo_primer_momento',
        'id_detalle_primer_momento',
        'id_tiempo_primer_momento',
        'id_recursos_primer_momento',
        
        // Segundo momento didáctico
        'id_tipo_segundo_momento_claseteoria',
        'id_clase_teorica',
        'id_tipo_segundo_momento_practica',
        'id_clase_practica',
        'id_tiempo_segundo_momento',
        'id_recursos_segundo_momento',
        
        // Tercer momento didáctico
        'id_tipo_tercer_momento',
        'id_detalle_tercer_momento',
        'id_tiempo_tercer_momento',
        'id_recursos_tercer_momento',
        
        // Eje transversal
        'id_eje_transversal',
        'id_detalle_eje_transversal',
        
        // Evaluación
        'id_actividad_aprendizaje',
        'id_tecnica_evaluacion',
        'id_tipo_evaluacion',
        'id_instrumento_evaluacion',
        'id_agente_evaluador',
        'id_puntaje'
    ];
    
    let formValido = true;
    let primerCampoConError = null;
    
    // Eliminar mensajes de error anteriores
    $('.error-message').remove();
    $('.border-danger').removeClass('border-danger');
    
    // Validar cada campo obligatorio
    camposObligatorios.forEach(function(campoId) {
        const campo = $('#' + campoId);
        
        if (campo.length === 0) {
            console.warn('Campo no encontrado:', campoId);
            return;
        }
        
        // Verificar si el campo está vacío
        if (!campo.val() || campo.val().trim() === '') {
            formValido = false;
            
            // Marcar el campo con borde rojo
            campo.addClass('border-danger');
            
            // Agregar mensaje de error debajo del campo
            const errorMsg = $('<div class="error-message text-danger small mt-1">Este campo es obligatorio</div>');
            campo.after(errorMsg);
            
            // Guardar el primer campo con error para hacer scroll
            if (!primerCampoConError) {
                primerCampoConError = campo;
            }
        }
    });
    
    // Si hay errores, hacer scroll al primer campo con error
    if (!formValido && primerCampoConError) {
        $('html, body').animate({
            scrollTop: primerCampoConError.offset().top - 100
        }, 500);
        
        // Mostrar un mensaje general de error
        mostrarMensajeError('Por favor, complete todos los campos obligatorios marcados en rojo.');
    }
    
    return formValido;
}

/**
 * Función para resaltar campos con errores reportados por el backend
 * @param {Object} errores - Objeto con los errores del backend
 */
function resaltarCamposConError(errores) {
    // Mapeo de nombres de campos del backend a IDs en el formulario
    const mapeoNombreAId = {
        // Información General
        'fecha': 'id_fecha',
        'unidad': 'id_unidad',
        'nombre_de_la_unidad': 'id_nombre_de_la_unidad',
        'contenido_tematico': 'id_contenido_tematico',
        
        // Objetivos
        'objetivo_conceptual': 'id_objetivo_conceptual',
        'objetivo_procedimental': 'id_objetivo_procedimental',
        'objetivo_actitudinal': 'id_objetivo_actitudinal',
        
        // Primer momento didáctico
        'tipo_primer_momento': 'id_tipo_primer_momento',
        'detalle_primer_momento': 'id_detalle_primer_momento',
        'tiempo_primer_momento': 'id_tiempo_primer_momento',
        'recursos_primer_momento': 'id_recursos_primer_momento',
        
        // Segundo momento didáctico
        'tipo_segundo_momento_claseteoria': 'id_tipo_segundo_momento_claseteoria',
        'clase_teorica': 'id_clase_teorica',
        'tipo_segundo_momento_practica': 'id_tipo_segundo_momento_practica',
        'clase_practica': 'id_clase_practica',
        'tiempo_segundo_momento': 'id_tiempo_segundo_momento',
        'recursos_segundo_momento': 'id_recursos_segundo_momento',
        
        // Tercer momento didáctico
        'tipo_tercer_momento': 'id_tipo_tercer_momento',
        'detalle_tercer_momento': 'id_detalle_tercer_momento',
        'tiempo_tercer_momento': 'id_tiempo_tercer_momento',
        'recursos_tercer_momento': 'id_recursos_tercer_momento',
        
        // Eje transversal
        'eje_transversal': 'id_eje_transversal',
        'detalle_eje_transversal': 'id_detalle_eje_transversal',
        
        // Evaluación
        'actividad_aprendizaje': 'id_actividad_aprendizaje',
        'tecnica_evaluacion': 'id_tecnica_evaluacion',
        'tipo_evaluacion': 'id_tipo_evaluacion',
        'instrumento_evaluacion': 'id_instrumento_evaluacion',
        'agente_evaluador': 'id_agente_evaluador',
        'puntaje': 'id_puntaje'
    };
    
    // Eliminar mensajes de error anteriores
    $('.error-message').remove();
    $('.border-danger').removeClass('border-danger');
    
    let primerCampoConError = null;
    
    // Procesar cada error
    for (const [nombreCampo, mensajeError] of Object.entries(errores)) {
        // Obtener el ID del campo usando el mapeo
        const campoId = mapeoNombreAId[nombreCampo];
        
        if (!campoId) {
            console.warn('No se encontró mapeo para el campo:', nombreCampo);
            continue;
        }
        
        const campo = $('#' + campoId);
        
        if (campo.length === 0) {
            console.warn('Campo no encontrado:', campoId);
            continue;
        }
        
        // Marcar el campo con borde rojo
        campo.addClass('border-danger');
        
        // Agregar mensaje de error debajo del campo
        const errorMsg = $('<div class="error-message text-danger small mt-1">' + mensajeError + '</div>');
        campo.after(errorMsg);
        
        // Guardar el primer campo con error para hacer scroll
        if (!primerCampoConError) {
            primerCampoConError = campo;
        }
    }
    
    // Si hay errores, hacer scroll al primer campo con error
    if (primerCampoConError) {
        $('html, body').animate({
            scrollTop: primerCampoConError.offset().top - 100
        }, 500);
    }
}

/**
 * Función para mostrar mensaje de error
 * @param {string} mensaje - Mensaje a mostrar en la alerta
 */
function mostrarMensajeError(mensaje) {
    // Crear alerta de error
    const alertHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <strong>¡Error!</strong> ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Insertar alerta antes del botón de guardar
    $(alertHTML).insertBefore('#guardarFormularioBtn');
    
    // Desaparecer automáticamente después de 5 segundos
    setTimeout(function() {
        $('.alert-danger').alert('close');
    }, 5000);
}
