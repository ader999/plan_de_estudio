/**
 * estudio_independiente.js
 * Script para manejar la funcionalidad del formulario de estudio independiente
 */

// Variables globales
var currentSection = "estudioIndependiente";

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
  // Validar que los puntajes sumen 100
  var puntaje1 = parseInt($("#puntaje_1").val()) || 0;
  var puntaje2 = parseInt($("#puntaje_2").val()) || 0;
  var puntaje3 = parseInt($("#puntaje_3").val()) || 0;
  var puntaje4 = parseInt($("#puntaje_4").val()) || 0;

  var sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;

  if (sumaPuntajes !== 100) {
    alert(
      "La suma de los puntajes debe ser exactamente 100 puntos. Actualmente suma: " +
        sumaPuntajes,
    );
    return false;
  }

  // Validar campos requeridos
  var formularioValido = true;
  $("#formEstudioIndependiente [required]").each(function () {
    if ($(this).val() === "") {
      alert("Por favor complete todos los campos requeridos");
      $(this).focus();
      formularioValido = false;
      return false;
    }
  });

  return formularioValido;
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

  // Tarea 2
  formData.tipo_objetivo_2 = $("#tipo_objetivo_2").val();
  formData.objetivo_aprendizaje_2 = $("#objetivo_aprendizaje_2").val();
  formData.contenido_tematico_2 = $("#contenido_tematico_2").val();
  formData.actividad_aprendizaje_2 = $("#actividad_aprendizaje_2").val();
  formData.tecnica_evaluacion_2 = $("#tecnica_evaluacion_2").val();
  formData.tipo_evaluacion_2 = $("#tipo_evaluacion_2").val();
  formData.instrumento_evaluacion_2 = $("#instrumento_evaluacion_2").val();
  formData.criterios_evaluacion_2 = $("#criterios_evaluacion_2").val();
  formData.agente_evaluador_2 = [];
  $('input[name="agente_evaluador_2[]"]:checked').each(function () {
    formData.agente_evaluador_2.push($(this).val());
  });

  formData.tiempo_minutos_2 = $("#tiempo_minutos_2").val();
  formData.recursos_didacticos_2 = $("#recursos_didacticos_2").val();
  formData.periodo_tiempo_programado_2 = $(
    "#periodo_tiempo_programado_2",
  ).val();
  formData.puntaje_2 = $("#puntaje_2").val();
  formData.fecha_entrega_2 = $("#fecha_entrega_2").val();

  // Tarea 3
  formData.tipo_objetivo_3 = $("#tipo_objetivo_3").val();
  formData.objetivo_aprendizaje_3 = $("#objetivo_aprendizaje_3").val();
  formData.contenido_tematico_3 = $("#contenido_tematico_3").val();
  formData.actividad_aprendizaje_3 = $("#actividad_aprendizaje_3").val();
  formData.tecnica_evaluacion_3 = $("#tecnica_evaluacion_3").val();
  formData.tipo_evaluacion_3 = $("#tipo_evaluacion_3").val();
  formData.instrumento_evaluacion_3 = $("#instrumento_evaluacion_3").val();
  formData.criterios_evaluacion_3 = $("#criterios_evaluacion_3").val();
  formData.agente_evaluador_3 = [];
  $('input[name="agente_evaluador_3[]"]:checked').each(function () {
    formData.agente_evaluador_3.push($(this).val());
  });

  formData.tiempo_minutos_3 = $("#tiempo_minutos_3").val();
  formData.recursos_didacticos_3 = $("#recursos_didacticos_3").val();
  formData.periodo_tiempo_programado_3 = $(
    "#periodo_tiempo_programado_3",
  ).val();
  formData.puntaje_3 = $("#puntaje_3").val();
  formData.fecha_entrega_3 = $("#fecha_entrega_3").val();

  // Tarea 4
  formData.tipo_objetivo_4 = $("#tipo_objetivo_4").val();
  formData.objetivo_aprendizaje_4 = $("#objetivo_aprendizaje_4").val();
  formData.contenido_tematico_4 = $("#contenido_tematico_4").val();
  formData.actividad_aprendizaje_4 = $("#actividad_aprendizaje_4").val();
  formData.tecnica_evaluacion_4 = $("#tecnica_evaluacion_4").val();
  formData.tipo_evaluacion_4 = $("#tipo_evaluacion_4").val();
  formData.instrumento_evaluacion_4 = $("#instrumento_evaluacion_4").val();
  formData.criterios_evaluacion_4 = $("#criterios_evaluacion_4").val();
  formData.agente_evaluador_4 = [];
  $('input[name="agente_evaluador_4[]"]:checked').each(function () {
    formData.agente_evaluador_4.push($(this).val());
  });

  formData.tiempo_minutos_4 = $("#tiempo_minutos_4").val();
  formData.recursos_didacticos_4 = $("#recursos_didacticos_4").val();
  formData.periodo_tiempo_programado_4 = $(
    "#periodo_tiempo_programado_4",
  ).val();
  formData.puntaje_4 = $("#puntaje_4").val();
  formData.fecha_entrega_4 = $("#fecha_entrega_4").val();

  return formData;
}

/**
 * Función para guardar el formulario
 */
function guardarFormulario() {
  if (!validarFormulario()) {
    return;
  }

  mostrarSpinnerGuardar();

  var formData = recopilarDatosFormulario();
  var silaboId = typeof SILABO_ID !== "undefined" ? SILABO_ID : null;

  // Determinar la URL correcta basada en el ID del sílabo
  var url = "/guardar-guia/";
  if (silaboId) {
    url = "/guardar-guia/" + silaboId + "/";
  }

  // Obtener el token CSRF de la cookie
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      var cookies = document.cookie.split(";");
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Incluir el token CSRF en la solicitud AJAX
  var csrftoken = getCookie("csrftoken");

  $.ajax({
    url: url,
    type: "POST",
    contentType: "application/json",
    data: JSON.stringify(formData),
    headers: {
      "X-CSRFToken": csrftoken,
    },
    success: function (response) {
      ocultarSpinnerGuardar();

      if (response.success) {
        // Si se proporciona un ID de guía en la respuesta, actualizamos el campo oculto
        if (response.guia_id) {
          if ($("#guia_id").length) {
            $("#guia_id").val(response.guia_id);
          } else {
            $("#formEstudioIndependiente").append(
              '<input type="hidden" id="guia_id" name="guia_id" value="' +
                response.guia_id +
                '">',
            );
          }
        }

        alert("Guía guardada con éxito");

        // Redirigir si es necesario
        if (response.redirect_url) {
          window.location.href = response.redirect_url;
        }
      } else {
        alert("Error al guardar la guía: " + response.error);
      }
    },
    error: function (xhr, status, error) {
      ocultarSpinnerGuardar();
      console.error("Error en la solicitud AJAX:", error);
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

  if (sumaPuntajes !== 100) {
    $("#sumaPuntajes")
      .text("Suma actual: " + sumaPuntajes + " puntos (debe ser 100)")
      .removeClass("text-success")
      .addClass("text-danger");
  } else {
    $("#sumaPuntajes")
      .text("Suma correcta: 100 puntos")
      .removeClass("text-danger")
      .addClass("text-success");
  }
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
    csrfmiddlewaretoken: $("input[name=csrfmiddlewaretoken]").val(),
    encuentro: $("#numero_encuentro").val() || 1, // Usar el nombre correcto del campo
  };

  // Intentar obtener el silabo_id del campo oculto en el formulario
  var formSilaboId = $("#silabo_id").val();
  if (formSilaboId && formSilaboId.trim() !== "") {
    silaboId = formSilaboId;
    console.log("Usando silabo_id del formulario:", silaboId);
  }

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
      xhr.setRequestHeader('X-CSRFToken', $('input[name=csrfmiddlewaretoken]').val());
    },
    success: function (response) {
      console.log("Respuesta recibida:", response);

      // Ocultar spinner
      ocultarSpinnerEstudio();

      if (response.success) {
        // Rellenar los campos del formulario con los datos generados
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
        $("#agente_evaluador_1").val(response.datos.agente_evaluador_1);
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
        $("#agente_evaluador_2").val(response.datos.agente_evaluador_2);
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
        $("#agente_evaluador_3").val(response.datos.agente_evaluador_3);
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
        $("#agente_evaluador_4").val(response.datos.agente_evaluador_4);
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
        actualizarSumaPuntajes();

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
  console.log("Documento listo");

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

  // Ejecutar al cargar la página
  actualizarSumaPuntajes();

  // Validar que los puntajes sumen 100 cuando se cambian
  $("#puntaje_1, #puntaje_2, #puntaje_3, #puntaje_4").on(
    "change keyup",
    function () {
      actualizarSumaPuntajes();

      var puntaje1 = parseInt($("#puntaje_1").val()) || 0;
      var puntaje2 = parseInt($("#puntaje_2").val()) || 0;
      var puntaje3 = parseInt($("#puntaje_3").val()) || 0;
      var puntaje4 = parseInt($("#puntaje_4").val()) || 0;

      var sumaPuntajes = puntaje1 + puntaje2 + puntaje3 + puntaje4;

      if (sumaPuntajes !== 100) {
        $(this).addClass("is-invalid");
      } else {
        $(".puntaje").removeClass("is-invalid");
      }
    },
  );

  // Manejar el clic en el botón de generar estudio
  $("#boton-generar-estudio").click(function () {
    generarEstudioIndependiente(asignacionId, silaboId);
  });

  // Manejar el clic en el botón de guardar
  $("#guardarFormularioBtn").click(function () {
    guardarFormulario();
  });
});
