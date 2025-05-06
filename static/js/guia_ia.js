/**
 * guia_ia.js
 * Script para manejar la funcionalidad de consultar e insertar información de IA en el formulario de estudio independiente
 */

// Variables globales
let guiasEstudio = [];

/**
 * Funciones para controlar los spinners
 */
function mostrarSpinnerEstudio() {
  $("#boton-generar-estudio .spinner").removeClass("d-none");
  $("#boton-generar-estudio").prop("disabled", true);
}

function ocultarSpinnerEstudio() {
  $("#boton-generar-estudio .spinner").addClass("d-none");
  $("#boton-generar-estudio").prop("disabled", false);
}

/**
 * Función auxiliar para obtener el token CSRF
 */
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

/**
 * Función para generar el estudio independiente
 */
function generarEstudioIndependiente(asignacionId, silaboId) {
  console.log("Botón generar estudio clickeado");

  // Obtener el modelo seleccionado
  var modeloSeleccionado = $("#modelo_select_estudio").val();
  console.log("Modelo seleccionado:", modeloSeleccionado);

  // Mostrar spinner
  mostrarSpinnerEstudio();

  // Intentar obtener el silabo_id del campo oculto en el formulario
  var formSilaboId = $("#silabo_id").val();
  if (formSilaboId && formSilaboId.trim() !== "") {
    silaboId = formSilaboId;
    console.log("Usando silabo_id del formulario:", silaboId);
  }

  // Preparar los datos para la solicitud
  var requestData = {
    modelo: modeloSeleccionado,
    csrfmiddlewaretoken: getCookie('csrftoken'),
    encuentro: $("#numero_encuentro").val() || 1, // Usar el nombre correcto del campo
  };

  // Priorizar silabo_id sobre asignacion_id según la nueva estructura del backend
  if (silaboId && silaboId !== "null" && silaboId.trim() !== "") {
    requestData.silabo_id = silaboId;
    console.log("Usando silabo_id:", silaboId);
  } else if (
    asignacionId &&
    asignacionId !== "null" &&
    asignacionId.trim() !== ""
  ) {
    requestData.asignacion_id = asignacionId;
    console.log("Usando asignacion_id:", asignacionId);
  } else {
    console.error("No se proporcionó ni silabo_id ni asignacion_id");
    ocultarSpinnerEstudio();
    alert(
      "Error: No se pudo identificar el sílabo para generar el estudio independiente",
    );
    return;
  }

  // Realizar la solicitud AJAX
  $.ajax({
    url: "/generar-estudio-independiente/",
    type: "POST",
    data: requestData,
    timeout: 120000, // 2 minutos
    beforeSend: function(xhr) {
      xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
    },
    success: function (response) {
      ocultarSpinnerEstudio();

      if (response.success) {
        // Guardar los datos generados
        guiasEstudio = response.estudios || [];

        // Actualizar el formulario con los datos generados
        // Completar ID de la guía si existe
        if (response.datos.guia_id) {
          $("#guia_id").val(response.datos.guia_id);
        }

        // Tarea 1
        $("#tipo_objetivo_1").val(response.datos.tipo_objetivo_1);
        $("#objetivo_aprendizaje_1").val(response.datos.objetivo_aprendizaje_1);
        $("#contenido_tematico_1").val(response.datos.contenido_tematico_1);
        $("#actividad_aprendizaje_1").val(
          response.datos.actividad_aprendizaje_1,
        );
        $("#tecnica_evaluacion_1").val(response.datos.tecnica_evaluacion_1);
        $("#tipo_evaluacion_1").val(response.datos.tipo_evaluacion_1);
        $("#instrumento_evaluacion_1").val(
          response.datos.instrumento_evaluacion_1,
        );
        $("#criterios_evaluacion_1").val(response.datos.criterios_evaluacion_1);
        
        // Limpiar checkboxes existentes
        $('input[name="agente_evaluador_1[]"]').prop('checked', false);
        
        // Marcar los checkboxes correspondientes
        if (Array.isArray(response.datos.agente_evaluador_1)) {
          response.datos.agente_evaluador_1.forEach(function(agente) {
            $('input[name="agente_evaluador_1[]"][value="' + agente + '"]').prop('checked', true);
          });
        } else if (response.datos.agente_evaluador_1) {
          // Si no es un array, convertir a string y dividir por comas
          var agentes = String(response.datos.agente_evaluador_1).split(',');
          agentes.forEach(function(agente) {
            $('input[name="agente_evaluador_1[]"][value="' + agente.trim() + '"]').prop('checked', true);
          });
        }
        
        $("#tiempo_minutos_1").val(response.datos.tiempo_minutos_1);
        $("#recursos_didacticos_1").val(response.datos.recursos_didacticos_1);
        $("#periodo_tiempo_programado_1").val(
          response.datos.periodo_tiempo_programado_1,
        );
        $("#puntaje_1").val(response.datos.puntaje_1);
        $("#fecha_entrega_1").val(response.datos.fecha_entrega_1);

        // Tarea 2
        $("#tipo_objetivo_2").val(response.datos.tipo_objetivo_2);
        $("#objetivo_aprendizaje_2").val(response.datos.objetivo_aprendizaje_2);
        $("#contenido_tematico_2").val(response.datos.contenido_tematico_2);
        $("#actividad_aprendizaje_2").val(
          response.datos.actividad_aprendizaje_2,
        );
        $("#tecnica_evaluacion_2").val(response.datos.tecnica_evaluacion_2);
        $("#tipo_evaluacion_2").val(response.datos.tipo_evaluacion_2);
        $("#instrumento_evaluacion_2").val(
          response.datos.instrumento_evaluacion_2,
        );
        $("#criterios_evaluacion_2").val(response.datos.criterios_evaluacion_2);
        
        // Limpiar checkboxes existentes
        $('input[name="agente_evaluador_2[]"]').prop('checked', false);
        
        // Marcar los checkboxes correspondientes
        if (Array.isArray(response.datos.agente_evaluador_2)) {
          response.datos.agente_evaluador_2.forEach(function(agente) {
            $('input[name="agente_evaluador_2[]"][value="' + agente + '"]').prop('checked', true);
          });
        } else if (response.datos.agente_evaluador_2) {
          // Si no es un array, convertir a string y dividir por comas
          var agentes = String(response.datos.agente_evaluador_2).split(',');
          agentes.forEach(function(agente) {
            $('input[name="agente_evaluador_2[]"][value="' + agente.trim() + '"]').prop('checked', true);
          });
        }
        
        $("#tiempo_minutos_2").val(response.datos.tiempo_minutos_2);
        $("#recursos_didacticos_2").val(response.datos.recursos_didacticos_2);
        $("#periodo_tiempo_programado_2").val(
          response.datos.periodo_tiempo_programado_2,
        );
        $("#puntaje_2").val(response.datos.puntaje_2);
        $("#fecha_entrega_2").val(response.datos.fecha_entrega_2);

        // Tarea 3
        $("#tipo_objetivo_3").val(response.datos.tipo_objetivo_3);
        $("#objetivo_aprendizaje_3").val(response.datos.objetivo_aprendizaje_3);
        $("#contenido_tematico_3").val(response.datos.contenido_tematico_3);
        $("#actividad_aprendizaje_3").val(
          response.datos.actividad_aprendizaje_3,
        );
        $("#tecnica_evaluacion_3").val(response.datos.tecnica_evaluacion_3);
        $("#tipo_evaluacion_3").val(response.datos.tipo_evaluacion_3);
        $("#instrumento_evaluacion_3").val(
          response.datos.instrumento_evaluacion_3,
        );
        $("#criterios_evaluacion_3").val(response.datos.criterios_evaluacion_3);
        
        // Limpiar checkboxes existentes
        $('input[name="agente_evaluador_3[]"]').prop('checked', false);
        
        // Marcar los checkboxes correspondientes
        if (Array.isArray(response.datos.agente_evaluador_3)) {
          response.datos.agente_evaluador_3.forEach(function(agente) {
            $('input[name="agente_evaluador_3[]"][value="' + agente + '"]').prop('checked', true);
          });
        } else if (response.datos.agente_evaluador_3) {
          // Si no es un array, convertir a string y dividir por comas
          var agentes = String(response.datos.agente_evaluador_3).split(',');
          agentes.forEach(function(agente) {
            $('input[name="agente_evaluador_3[]"][value="' + agente.trim() + '"]').prop('checked', true);
          });
        }
        
        $("#tiempo_minutos_3").val(response.datos.tiempo_minutos_3);
        $("#recursos_didacticos_3").val(response.datos.recursos_didacticos_3);
        $("#periodo_tiempo_programado_3").val(
          response.datos.periodo_tiempo_programado_3,
        );
        $("#puntaje_3").val(response.datos.puntaje_3);
        $("#fecha_entrega_3").val(response.datos.fecha_entrega_3);

        // Tarea 4
        $("#tipo_objetivo_4").val(response.datos.tipo_objetivo_4);
        $("#objetivo_aprendizaje_4").val(response.datos.objetivo_aprendizaje_4);
        $("#contenido_tematico_4").val(response.datos.contenido_tematico_4);
        $("#actividad_aprendizaje_4").val(
          response.datos.actividad_aprendizaje_4,
        );
        $("#tecnica_evaluacion_4").val(response.datos.tecnica_evaluacion_4);
        $("#tipo_evaluacion_4").val(response.datos.tipo_evaluacion_4);
        $("#instrumento_evaluacion_4").val(
          response.datos.instrumento_evaluacion_4,
        );
        $("#criterios_evaluacion_4").val(response.datos.criterios_evaluacion_4);
        
        // Limpiar checkboxes existentes
        $('input[name="agente_evaluador_4[]"]').prop('checked', false);
        
        // Marcar los checkboxes correspondientes
        if (Array.isArray(response.datos.agente_evaluador_4)) {
          response.datos.agente_evaluador_4.forEach(function(agente) {
            $('input[name="agente_evaluador_4[]"][value="' + agente + '"]').prop('checked', true);
          });
        } else if (response.datos.agente_evaluador_4) {
          // Si no es un array, convertir a string y dividir por comas
          var agentes = String(response.datos.agente_evaluador_4).split(',');
          agentes.forEach(function(agente) {
            $('input[name="agente_evaluador_4[]"][value="' + agente.trim() + '"]').prop('checked', true);
          });
        }
        
        $("#tiempo_minutos_4").val(response.datos.tiempo_minutos_4);
        $("#recursos_didacticos_4").val(response.datos.recursos_didacticos_4);
        $("#periodo_tiempo_programado_4").val(
          response.datos.periodo_tiempo_programado_4,
        );
        $("#puntaje_4").val(response.datos.puntaje_4);
        $("#fecha_entrega_4").val(response.datos.fecha_entrega_4);

        // Información general
        if (response.datos.unidad) {
          $("#unidad").val(response.datos.unidad);
        }
        if (response.datos.nombre_de_la_unidad) {
          $("#nombre_de_la_unidad").val(response.datos.nombre_de_la_unidad);
        }
        if (response.datos.fecha) {
          $("#fecha").val(response.datos.fecha);
        }

        // Actualizar la suma de puntajes
        if (typeof actualizarSumaPuntajes === 'function') {
          actualizarSumaPuntajes();
        }

        // Mostrar mensaje de éxito
        alert("Estudio independiente generado con éxito");
      } else {
        // Mostrar mensaje de error
        alert("Error al generar el estudio independiente: " + response.error);
      }
    },
    error: function (xhr, status, error) {
      console.error("Error en la solicitud AJAX:", error);
      ocultarSpinnerEstudio();
      
      if (status === "timeout") {
        alert("La solicitud tomó demasiado tiempo. Por favor, intenta nuevamente.");
      } else {
        alert("Error al comunicarse con el servidor");
      }
    }
  });
}

/**
 * Inicialización cuando el documento está listo
 */
$(document).ready(function () {
  console.log("Documento listo - guia_ia.js");

  // ID de asignación desde Django
  var asignacionId =
    typeof ASIGNACION_ID !== "undefined" ? ASIGNACION_ID : null;
  console.log("ID de asignación:", asignacionId);

  // ID de sílabo desde Django (si existe)
  var silaboId = typeof SILABO_ID !== "undefined" ? SILABO_ID : null;
  console.log("ID de sílabo:", silaboId);

  // ID de guía desde Django (si existe)
  var guiaId = typeof GUIA_ID !== "undefined" ? GUIA_ID : null;
  console.log("ID de guía:", guiaId);

  // Mostrar la sección de estudio independiente por defecto
  $("#seccionEstudioIndependiente").show();

  // Manejar el clic en el botón de generar estudio
  $("#boton-generar-estudio").click(function () {
    generarEstudioIndependiente(asignacionId, silaboId);
  });
});
