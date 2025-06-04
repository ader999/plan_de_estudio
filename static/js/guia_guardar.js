/**
 * guia_guardar.js
 * Script para manejar la funcionalidad de guardar y validar datos del formulario de estudio independiente
 */

// Variables globales
var currentSection = "estudioIndependiente";

/**
 * Funciones para controlar los spinners de guardado
 */
function mostrarSpinnerGuardar() {
  $("#spinnerGuardar").removeClass("d-none");
  $("#guardarFormularioBtn").prop("disabled", true);
}

function ocultarSpinnerGuardar() {
  $("#spinnerGuardar").addClass("d-none");
  $("#guardarFormularioBtn").prop("disabled", false);
}

/**
 * Validación del formulario
 */
function validarFormulario() {
  var formularioValido = true;
  var mensajesError = [];
  
  // Eliminar todas las clases is-invalid previas
  $("#formEstudioIndependiente .is-invalid").removeClass("is-invalid");
  
  // Validar que los puntajes sean válidos (positivos y suma <= 100)
  var puntaje1 = parseInt($("#puntaje_1").val()) || 0;
  var puntaje2 = parseInt($("#puntaje_2").val()) || 0;
  var puntaje3 = parseInt($("#puntaje_3").val()) || 0;
  var puntaje4 = parseInt($("#puntaje_4").val()) || 0;

  // Verificar que no haya puntajes negativos
  if (puntaje1 < 0 || puntaje2 < 0 || puntaje3 < 0 || puntaje4 < 0) {
    mensajesError.push("Los puntajes no pueden ser negativos. Por favor, ingrese valores mayores o iguales a 0.");
    
    // Marcar los campos con puntaje negativo
    if (puntaje1 < 0) $("#puntaje_1").addClass("is-invalid");
    if (puntaje2 < 0) $("#puntaje_2").addClass("is-invalid");
    if (puntaje3 < 0) $("#puntaje_3").addClass("is-invalid");
    if (puntaje4 < 0) $("#puntaje_4").addClass("is-invalid");
    
    formularioValido = false;
  }

  var sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;

  // Verificar que la suma no exceda 100
  if (sumaPuntajes > 100) {
    mensajesError.push("La suma de los puntajes no puede exceder 100 puntos. Actualmente suma: " + sumaPuntajes);
    
    // Marcar todos los campos de puntaje como inválidos
    $("#puntaje_1, #puntaje_2, #puntaje_3, #puntaje_4").addClass("is-invalid");
    
    formularioValido = false;
  }

  // Validar campos requeridos de la información general y primera actividad
  var camposFaltantes = [];
  
  // Campos generales requeridos
  var camposGeneralesRequeridos = [
    "fecha", "unidad", "nombre_de_la_unidad"
  ];
  
  // Campos requeridos de la primera actividad
  var camposActividad1 = [
    "tipo_objetivo_1", "objetivo_aprendizaje_1", "contenido_tematico_1", 
    "actividad_aprendizaje_1", "tiempo_minutos_1", "recursos_didacticos_1", 
    "periodo_tiempo_programado_1", "puntaje_1", "fecha_entrega_1",
    "tecnica_evaluacion_1", "instrumento_evaluacion_1", "criterios_evaluacion_1", "tipo_evaluacion_1"
  ];
  
  // Validar campos generales y de la primera actividad
  var camposRequeridos = camposGeneralesRequeridos.concat(camposActividad1);
  
  $.each(camposRequeridos, function(index, campoId) {
    var $campo = $("#" + campoId);
    if ($campo.length && $campo.val() === "") {
      // Marcar el campo como inválido
      $campo.addClass("is-invalid");
      
      // Obtener la etiqueta del campo para el mensaje de error
      var labelText = $("label[for='" + campoId + "']").text().trim();
      if (labelText) {
        camposFaltantes.push(labelText);
      }
      
      formularioValido = false;
    }
  });
  
  // Validar que se haya seleccionado al menos un agente evaluador para la primera actividad
  var agentesSeleccionados1 = $('input[name="agente_evaluador_1[]"]:checked').length;
  if (agentesSeleccionados1 === 0) {
    // Marcar los checkboxes como inválidos
    $('input[name="agente_evaluador_1[]"]').first().closest('.form-check').addClass('is-invalid');
    camposFaltantes.push("Agente Evaluador 1");
    formularioValido = false;
  }
  
  // Revisar las actividades opcionales (2, 3 y 4) para validar que si tienen información,
  // esté completa o limpiar los campos que no son textarea
  var actividad2Valida = validarActividadOpcional(2, mensajesError);
  var actividad3Valida = validarActividadOpcional(3, mensajesError);
  var actividad4Valida = validarActividadOpcional(4, mensajesError);
  
  if (!actividad2Valida || !actividad3Valida || !actividad4Valida) {
    formularioValido = false;
  }
  
  // Agregar mensaje de error para campos requeridos faltantes
  if (camposFaltantes.length > 0) {
    if (camposFaltantes.length <= 3) {
      mensajesError.push("Por favor complete los siguientes campos obligatorios: " + camposFaltantes.join(", "));
    } else {
      mensajesError.push("Por favor complete todos los campos obligatorios marcados en rojo.");
    }
  }
  
  // Mostrar los mensajes de error si hay alguno
  if (mensajesError.length > 0) {
    alert(mensajesError.join("\n\n"));
  }

  return formularioValido;
}

/**
 * Valida una actividad opcional y limpia los campos si es necesario
 */
function validarActividadOpcional(numeroActividad, mensajesError) {
  var camposActividad = [
    "tipo_objetivo_" + numeroActividad,
    "objetivo_aprendizaje_" + numeroActividad,
    "contenido_tematico_" + numeroActividad,
    "actividad_aprendizaje_" + numeroActividad,
    "tiempo_minutos_" + numeroActividad,
    "recursos_didacticos_" + numeroActividad,
    "periodo_tiempo_programado_" + numeroActividad,
    "puntaje_" + numeroActividad,
    "fecha_entrega_" + numeroActividad,
    "tecnica_evaluacion_" + numeroActividad,
    "instrumento_evaluacion_" + numeroActividad,
    "criterios_evaluacion_" + numeroActividad,
    "tipo_evaluacion_" + numeroActividad
  ];
  
  // Verificar si algún campo tiene información
  var algunCampoConInfo = false;
  var todosCamposLlenos = true;
  var camposVacios = [];

  
  $.each(camposActividad, function(index, campoId) {
    var $campo = $("#" + campoId);
    if ($campo.length) {
      var valor = $campo.val();
      var tieneContenido = false;
      
      // Normalizar valor - convertir null, undefined a cadena vacía
      if (valor === null || valor === undefined) {
        valor = "";
      }
      
      // Para campos numéricos (puntaje y tiempo), verificar que no sea 0 o vacío
      if ($campo.is('input[type="number"]')) {
        var valorNumerico = parseFloat(valor);
        tieneContenido = !isNaN(valorNumerico) && valorNumerico > 0;
      } else if ($campo.is('textarea') || $campo.is('input[type="text"]')) {
        // Para campos de texto, verificar que no esté vacío después de trim
        tieneContenido = valor.toString().trim() !== "";
      } else if ($campo.is('input[type="date"]')) {
        // Para campos de fecha, verificar que no esté vacío
        tieneContenido = valor.toString().trim() !== "";
      } else if ($campo.is('select')) {
        // Para selects, verificar que no sea cadena vacía y que no sea la opción por defecto
        tieneContenido = valor !== "" && valor !== null && valor !== undefined;
      } else {
        // Para otros tipos de campos
        tieneContenido = valor !== "" && valor !== null && valor !== undefined;
      }
      
      if (tieneContenido) {
        algunCampoConInfo = true;
      } else {
        todosCamposLlenos = false;
        camposVacios.push(campoId);
      }
    }
  });
  
  // Verificar agentes evaluadores
  var agentesSeleccionados = $('input[name="agente_evaluador_' + numeroActividad + '[]"]:checked').length;
  if (agentesSeleccionados > 0) {
    algunCampoConInfo = true;
  } else {
    todosCamposLlenos = false;
  }
  
  // Si no hay información, está bien - actividad completamente vacía
  if (!algunCampoConInfo) {
    // Limpiar selects - establecer a la opción vacía
    $("#tipo_objetivo_" + numeroActividad + ", #tipo_evaluacion_" + numeroActividad + ", #tecnica_evaluacion_" + numeroActividad + ", #instrumento_evaluacion_" + numeroActividad + ", #periodo_tiempo_programado_" + numeroActividad).val("");
    
    // Desmarcar checkboxes
    $('input[name="agente_evaluador_' + numeroActividad + '[]"]').prop('checked', false);
    
    return true; // Actividad vacía es válida
  }
  
  // Si hay información parcial
  if (algunCampoConInfo && !todosCamposLlenos) {
    // Alertar sobre campos incompletos
    mensajesError.push("La Actividad de Aprendizaje " + numeroActividad + " está incompleta. Complete todos los campos o déjelos todos vacíos.");
    
    // Marcar todos los campos vacíos como inválidos
    $.each(camposVacios, function(index, campoId) {
      $("#" + campoId).addClass("is-invalid");
    });
    
    // Si no hay agentes evaluadores seleccionados, marcar ese campo
    if (agentesSeleccionados === 0) {
      $('input[name="agente_evaluador_' + numeroActividad + '[]"]').first().closest('.form-check').addClass('is-invalid');
    }
    
    return false;
  }
  
  // Si todos los campos están llenos, está completa
  return todosCamposLlenos;
}

/**
 * Recopilación de datos del formulario
 */
function recopilarDatosFormulario() {
  // Crear un objeto con todos los campos del formulario
  var formData = {};

  // Obtener IDs
  formData.silabo_id = typeof SILABO_ID !== "undefined" ? SILABO_ID : null;
  formData.guia_id = $("#guia_id").val() || null;

  // Información general
  formData.numero_encuentro = $("#numero_encuentro").val();
  formData.fecha = $("#fecha").val();
  formData.unidad = $("#unidad").val();
  formData.nombre_de_la_unidad = $("#nombre_de_la_unidad").val();

  // Tarea 1
  formData.tipo_objetivo_1 = $("#tipo_objetivo_1").val();
  formData.objetivo_aprendizaje_1 = $("#objetivo_aprendizaje_1").val();
  formData.contenido_tematico_1 = $("#contenido_tematico_1").val();
  formData.actividad_aprendizaje_1 = $("#actividad_aprendizaje_1").val();
  formData.tecnica_evaluacion_1 = $("#tecnica_evaluacion_1").val();
  formData.tipo_evaluacion_1 = $("#tipo_evaluacion_1").val();
  formData.instrumento_evaluacion_1 = $("#instrumento_evaluacion_1").val();
  formData.criterios_evaluacion_1 = $("#criterios_evaluacion_1").val();
  formData.agente_evaluador_1 = [];
  $('input[name="agente_evaluador_1[]"]:checked').each(function () {
    formData.agente_evaluador_1.push($(this).val());
  });

  formData.tiempo_minutos_1 = $("#tiempo_minutos_1").val();
  formData.recursos_didacticos_1 = $("#recursos_didacticos_1").val();
  formData.periodo_tiempo_programado_1 = $(
    "#periodo_tiempo_programado_1",
  ).val();
  formData.puntaje_1 = $("#puntaje_1").val();
  formData.fecha_entrega_1 = $("#fecha_entrega_1").val();

  // Tarea 2 - Solo incluir si tiene valores válidos
  var tipoObjetivo2 = $("#tipo_objetivo_2").val();
  if (tipoObjetivo2 && tipoObjetivo2 !== "") {
    formData.tipo_objetivo_2 = tipoObjetivo2;
  }
  
  var objetivoAprendizaje2 = $("#objetivo_aprendizaje_2").val();
  if (objetivoAprendizaje2 && objetivoAprendizaje2.trim() !== "") {
    formData.objetivo_aprendizaje_2 = objetivoAprendizaje2;
  }
  
  var contenidoTematico2 = $("#contenido_tematico_2").val();
  if (contenidoTematico2 && contenidoTematico2.trim() !== "") {
    formData.contenido_tematico_2 = contenidoTematico2;
  }
  
  var actividadAprendizaje2 = $("#actividad_aprendizaje_2").val();
  if (actividadAprendizaje2 && actividadAprendizaje2.trim() !== "") {
    formData.actividad_aprendizaje_2 = actividadAprendizaje2;
  }
  
  var tecnicaEvaluacion2 = $("#tecnica_evaluacion_2").val();
  if (tecnicaEvaluacion2 && tecnicaEvaluacion2 !== "") {
    formData.tecnica_evaluacion_2 = tecnicaEvaluacion2;
  }
  
  var tipoEvaluacion2 = $("#tipo_evaluacion_2").val();
  if (tipoEvaluacion2 && tipoEvaluacion2 !== "") {
    formData.tipo_evaluacion_2 = tipoEvaluacion2;
  }
  
  var instrumentoEvaluacion2 = $("#instrumento_evaluacion_2").val();
  if (instrumentoEvaluacion2 && instrumentoEvaluacion2 !== "") {
    formData.instrumento_evaluacion_2 = instrumentoEvaluacion2;
  }
  
  var criteriosEvaluacion2 = $("#criterios_evaluacion_2").val();
  if (criteriosEvaluacion2 && criteriosEvaluacion2.trim() !== "") {
    formData.criterios_evaluacion_2 = criteriosEvaluacion2;
  }
  
  var agentesEvaluador2 = [];
  $('input[name="agente_evaluador_2[]"]:checked').each(function () {
    agentesEvaluador2.push($(this).val());
  });
  if (agentesEvaluador2.length > 0) {
    formData.agente_evaluador_2 = agentesEvaluador2;
  }

  var tiempoMinutos2 = $("#tiempo_minutos_2").val();
  if (tiempoMinutos2 && tiempoMinutos2 !== "") {
    formData.tiempo_minutos_2 = tiempoMinutos2;
  }
  
  var recursosDidacticos2 = $("#recursos_didacticos_2").val();
  if (recursosDidacticos2 && recursosDidacticos2.trim() !== "") {
    formData.recursos_didacticos_2 = recursosDidacticos2;
  }
  
  var periodoTiempo2 = $("#periodo_tiempo_programado_2").val();
  if (periodoTiempo2 && periodoTiempo2 !== "") {
    formData.periodo_tiempo_programado_2 = periodoTiempo2;
  }
  
  var puntaje2 = $("#puntaje_2").val();
  if (puntaje2 && puntaje2 !== "") {
    formData.puntaje_2 = puntaje2;
  }
  
  var fechaEntrega2 = $("#fecha_entrega_2").val();
  if (fechaEntrega2 && fechaEntrega2 !== "") {
    formData.fecha_entrega_2 = fechaEntrega2;
  }

  // Tarea 3 - Solo incluir si tiene valores válidos
  var tipoObjetivo3 = $("#tipo_objetivo_3").val();
  if (tipoObjetivo3 && tipoObjetivo3 !== "") {
    formData.tipo_objetivo_3 = tipoObjetivo3;
  }
  
  var objetivoAprendizaje3 = $("#objetivo_aprendizaje_3").val();
  if (objetivoAprendizaje3 && objetivoAprendizaje3.trim() !== "") {
    formData.objetivo_aprendizaje_3 = objetivoAprendizaje3;
  }
  
  var contenidoTematico3 = $("#contenido_tematico_3").val();
  if (contenidoTematico3 && contenidoTematico3.trim() !== "") {
    formData.contenido_tematico_3 = contenidoTematico3;
  }
  
  var actividadAprendizaje3 = $("#actividad_aprendizaje_3").val();
  if (actividadAprendizaje3 && actividadAprendizaje3.trim() !== "") {
    formData.actividad_aprendizaje_3 = actividadAprendizaje3;
  }
  
  var tecnicaEvaluacion3 = $("#tecnica_evaluacion_3").val();
  if (tecnicaEvaluacion3 && tecnicaEvaluacion3 !== "") {
    formData.tecnica_evaluacion_3 = tecnicaEvaluacion3;
  }
  
  var tipoEvaluacion3 = $("#tipo_evaluacion_3").val();
  if (tipoEvaluacion3 && tipoEvaluacion3 !== "") {
    formData.tipo_evaluacion_3 = tipoEvaluacion3;
  }
  
  var instrumentoEvaluacion3 = $("#instrumento_evaluacion_3").val();
  if (instrumentoEvaluacion3 && instrumentoEvaluacion3 !== "") {
    formData.instrumento_evaluacion_3 = instrumentoEvaluacion3;
  }
  
  var criteriosEvaluacion3 = $("#criterios_evaluacion_3").val();
  if (criteriosEvaluacion3 && criteriosEvaluacion3.trim() !== "") {
    formData.criterios_evaluacion_3 = criteriosEvaluacion3;
  }
  
  var agentesEvaluador3 = [];
  $('input[name="agente_evaluador_3[]"]:checked').each(function () {
    agentesEvaluador3.push($(this).val());
  });
  if (agentesEvaluador3.length > 0) {
    formData.agente_evaluador_3 = agentesEvaluador3;
  }

  var tiempoMinutos3 = $("#tiempo_minutos_3").val();
  if (tiempoMinutos3 && tiempoMinutos3 !== "") {
    formData.tiempo_minutos_3 = tiempoMinutos3;
  }
  
  var recursosDidacticos3 = $("#recursos_didacticos_3").val();
  if (recursosDidacticos3 && recursosDidacticos3.trim() !== "") {
    formData.recursos_didacticos_3 = recursosDidacticos3;
  }
  
  var periodoTiempo3 = $("#periodo_tiempo_programado_3").val();
  if (periodoTiempo3 && periodoTiempo3 !== "") {
    formData.periodo_tiempo_programado_3 = periodoTiempo3;
  }
  
  var puntaje3 = $("#puntaje_3").val();
  if (puntaje3 && puntaje3 !== "") {
    formData.puntaje_3 = puntaje3;
  }
  
  var fechaEntrega3 = $("#fecha_entrega_3").val();
  if (fechaEntrega3 && fechaEntrega3 !== "") {
    formData.fecha_entrega_3 = fechaEntrega3;
  }

  // Tarea 4 - Solo incluir si tiene valores válidos
  var tipoObjetivo4 = $("#tipo_objetivo_4").val();
  if (tipoObjetivo4 && tipoObjetivo4 !== "") {
    formData.tipo_objetivo_4 = tipoObjetivo4;
  }
  
  var objetivoAprendizaje4 = $("#objetivo_aprendizaje_4").val();
  if (objetivoAprendizaje4 && objetivoAprendizaje4.trim() !== "") {
    formData.objetivo_aprendizaje_4 = objetivoAprendizaje4;
  }
  
  var contenidoTematico4 = $("#contenido_tematico_4").val();
  if (contenidoTematico4 && contenidoTematico4.trim() !== "") {
    formData.contenido_tematico_4 = contenidoTematico4;
  }
  
  var actividadAprendizaje4 = $("#actividad_aprendizaje_4").val();
  if (actividadAprendizaje4 && actividadAprendizaje4.trim() !== "") {
    formData.actividad_aprendizaje_4 = actividadAprendizaje4;
  }
  
  var tecnicaEvaluacion4 = $("#tecnica_evaluacion_4").val();
  if (tecnicaEvaluacion4 && tecnicaEvaluacion4 !== "") {
    formData.tecnica_evaluacion_4 = tecnicaEvaluacion4;
  }
  
  var tipoEvaluacion4 = $("#tipo_evaluacion_4").val();
  if (tipoEvaluacion4 && tipoEvaluacion4 !== "") {
    formData.tipo_evaluacion_4 = tipoEvaluacion4;
  }
  
  var instrumentoEvaluacion4 = $("#instrumento_evaluacion_4").val();
  if (instrumentoEvaluacion4 && instrumentoEvaluacion4 !== "") {
    formData.instrumento_evaluacion_4 = instrumentoEvaluacion4;
  }
  
  var criteriosEvaluacion4 = $("#criterios_evaluacion_4").val();
  if (criteriosEvaluacion4 && criteriosEvaluacion4.trim() !== "") {
    formData.criterios_evaluacion_4 = criteriosEvaluacion4;
  }
  
  var agentesEvaluador4 = [];
  $('input[name="agente_evaluador_4[]"]:checked').each(function () {
    agentesEvaluador4.push($(this).val());
  });
  if (agentesEvaluador4.length > 0) {
    formData.agente_evaluador_4 = agentesEvaluador4;
  }

  var tiempoMinutos4 = $("#tiempo_minutos_4").val();
  if (tiempoMinutos4 && tiempoMinutos4 !== "") {
    formData.tiempo_minutos_4 = tiempoMinutos4;
  }
  
  var recursosDidacticos4 = $("#recursos_didacticos_4").val();
  if (recursosDidacticos4 && recursosDidacticos4.trim() !== "") {
    formData.recursos_didacticos_4 = recursosDidacticos4;
  }
  
  var periodoTiempo4 = $("#periodo_tiempo_programado_4").val();
  if (periodoTiempo4 && periodoTiempo4 !== "") {
    formData.periodo_tiempo_programado_4 = periodoTiempo4;
  }
  
  var puntaje4 = $("#puntaje_4").val();
  if (puntaje4 && puntaje4 !== "") {
    formData.puntaje_4 = puntaje4;
  }
  
  var fechaEntrega4 = $("#fecha_entrega_4").val();
  if (fechaEntrega4 && fechaEntrega4 !== "") {
    formData.fecha_entrega_4 = fechaEntrega4;
  }

  return formData;
}

/**
 * Función para guardar el formulario
 */
function guardarFormulario() {
  // Validar el formulario antes de enviar
  if (!validarFormulario()) {
    // Hacer scroll al primer elemento con error
    var primerElementoInvalido = $("#formEstudioIndependiente .is-invalid").first();
    if (primerElementoInvalido.length) {
      $('html, body').animate({
        scrollTop: primerElementoInvalido.offset().top - 100
      }, 500);
    }
    return;
  }

  // Mostrar el spinner de carga
  mostrarSpinnerGuardar();

  // Recopilar datos del formulario
  var formData = recopilarDatosFormulario();

  // Función para obtener el token CSRF de las cookies
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(
            cookie.substring(name.length + 1),
          );
          break;
        }
      }
    }
    return cookieValue;
  }

  // Determinar la URL correcta basada en el ID del sílabo
  var silaboId = typeof SILABO_ID !== "undefined" ? SILABO_ID : null;
  var url = "/guardar-guia/";
  if (silaboId) {
    url = "/guardar-guia/" + silaboId + "/";
  }

  // Realizar la solicitud AJAX para guardar
  $.ajax({
    url: url,
    type: "POST",
    data: JSON.stringify(formData),
    contentType: "application/json",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    success: function (response) {
      ocultarSpinnerGuardar();

      if (response.success) {
        // Actualizar el ID de la guía si se ha creado una nueva
        if (response.guia_id) {
          $("#guia_id").val(response.guia_id);
        }

        // Mostrar mensaje de éxito
        alert("Estudio independiente guardado con éxito");

        // Redirigir a la lista de estudios independientes si es necesario
        if (response.redirect_url) {
          window.location.href = response.redirect_url;
        }
      } else {
        // Mostrar mensaje de error
        alert("Error al guardar el estudio independiente: " + response.error);
      }
    },
    error: function (xhr, status, error) {
      console.error("Error en la solicitud AJAX:", error);
      ocultarSpinnerGuardar();
      alert("Error al comunicarse con el servidor");
    },
  });
}

/**
 * Función para actualizar la suma de puntajes
 */
function actualizarSumaPuntajes() {
  var puntaje1 = parseInt($("#puntaje_1").val()) || 0;
  var puntaje2 = parseInt($("#puntaje_2").val()) || 0;
  var puntaje3 = parseInt($("#puntaje_3").val()) || 0;
  var puntaje4 = parseInt($("#puntaje_4").val()) || 0;

  var sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;

  // Actualizar el contador de suma total
  $("#sumaPuntajes").text(sumaPuntajes);

  // Aplicar estilo según si la suma es correcta o no
  if (sumaPuntajes <= 100 && puntaje1 >= 0 && puntaje2 >= 0 && puntaje3 >= 0 && puntaje4 >= 0) {
    $("#sumaPuntajes").removeClass("text-danger").addClass("text-success");
  } else {
    $("#sumaPuntajes").removeClass("text-success").addClass("text-danger");
  }

  return sumaPuntajes;
}

/**
 * Inicialización cuando el documento está listo
 */
$(document).ready(function () {
  // Ejecutar al cargar la página
  actualizarSumaPuntajes();

  // Validar los puntajes cuando se cambian
  $("#puntaje_1, #puntaje_2, #puntaje_3, #puntaje_4").on(
    "change keyup",
    function () {
      actualizarSumaPuntajes();

      var puntaje1 = parseInt($("#puntaje_1").val()) || 0;
      var puntaje2 = parseInt($("#puntaje_2").val()) || 0;
      var puntaje3 = parseInt($("#puntaje_3").val()) || 0;
      var puntaje4 = parseInt($("#puntaje_4").val()) || 0;

      var sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;

      // Verificar si hay puntajes negativos o si la suma excede 100
      if (sumaPuntajes > 100 || puntaje1 < 0 || puntaje2 < 0 || puntaje3 < 0 || puntaje4 < 0) {
        $(this).addClass("is-invalid");
      } else {
        $(".puntaje").removeClass("is-invalid");
      }
    },
  );

  // Manejar el clic en el botón de guardar
  $("#guardarFormularioBtn").click(function () {
    guardarFormulario();
  });
});
