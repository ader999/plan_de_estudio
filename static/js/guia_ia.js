/**
 * guia_ia.js
 * Script para consultar e insertar información generada por IA en el formulario de estudio independiente,
 * sincronizado con GuiaWizard y borrador local.
 */

var guiasEstudio = [];

function mostrarSpinnerEstudio() {
  $("#boton-generar-estudio .spinner").removeClass("d-none");
  $("#boton-generar-estudio").prop("disabled", true);
}

function ocultarSpinnerEstudio() {
  $("#boton-generar-estudio .spinner").addClass("d-none");
  $("#boton-generar-estudio").prop("disabled", false);
}

function notificarIA(tipo, titulo, mensaje) {
  if (typeof mostrarAlertaGuia === "function") {
    mostrarAlertaGuia(tipo, titulo, mensaje, "#guia-ia-alert-container");
    return;
  }
  var $container = $("#guia-ia-alert-container");
  if ($container.length) {
    $container.empty();
    var $alert = $(
      '<div class="alert alert-' + tipo + ' alert-dismissible fade show mt-2 guia-dynamic-alert" role="alert">' +
        '<strong></strong> <span class="guia-ia-msg"></span>' +
        '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
      '</div>'
    );
    $alert.find("strong").text(titulo);
    $alert.find(".guia-ia-msg").text(mensaje);
    $container.append($alert);
    return;
  }
  alert(titulo + " " + mensaje);
}

function normalizarTextoOpcionGuia(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function marcarAgentesEvaluadores(num, valorAgente) {
  var selector = 'input[name="agente_evaluador_' + num + '[]"]';
  var $checks = $(selector);
  $checks.prop("checked", false);

  var lista = [];
  if (Array.isArray(valorAgente)) {
    lista = valorAgente;
  } else if (valorAgente) {
    lista = String(valorAgente).split(/\s*[,;/\n]\s*|\s+y\s+/i);
  }

  var checkedCount = 0;
  lista.forEach(function (agente) {
    if (checkedCount >= 2) return;
    var norm = normalizarTextoOpcionGuia(agente);
    if (!norm) return;
    $checks.each(function () {
      if (normalizarTextoOpcionGuia($(this).val()) === norm) {
        if (!$(this).prop("checked")) {
          $(this).prop("checked", true);
          checkedCount++;
        }
        return false;
      }
    });
  });
}

function limpiarCamposActividad(num) {
  var ids = [
    "#tipo_objetivo_" + num,
    "#objetivo_aprendizaje_" + num,
    "#contenido_tematico_" + num,
    "#actividad_aprendizaje_" + num,
    "#tecnica_evaluacion_" + num,
    "#tipo_evaluacion_" + num,
    "#instrumento_evaluacion_" + num,
    "#criterios_evaluacion_" + num,
    "#tiempo_minutos_" + num,
    "#recursos_didacticos_" + num,
    "#periodo_tiempo_programado_" + num,
    "#puntaje_" + num,
    "#fecha_entrega_" + num,
  ];
  $(ids.join(", ")).val("");
  $('input[name="agente_evaluador_' + num + '[]"]').prop("checked", false);
}

function valorCampoNumericoGuia(val) {
  return val !== undefined && val !== null && val !== "" ? val : "";
}

function aplicarDatosActividad(num, datos, numActividades) {
  if (num > numActividades) {
    limpiarCamposActividad(num);
    return;
  }

  var criterios = datos["criterios_evaluacion_" + num];
  if (Array.isArray(criterios)) {
    criterios = criterios.join("\n");
  }
  var recursos = datos["recursos_didacticos_" + num];
  if (Array.isArray(recursos)) {
    recursos = recursos.join(", ");
  }

  $("#tipo_objetivo_" + num).val(datos["tipo_objetivo_" + num] || "");
  $("#objetivo_aprendizaje_" + num).val(datos["objetivo_aprendizaje_" + num] || "");
  $("#contenido_tematico_" + num).val(datos["contenido_tematico_" + num] || "");
  $("#actividad_aprendizaje_" + num).val(datos["actividad_aprendizaje_" + num] || "");
  $("#tecnica_evaluacion_" + num).val(datos["tecnica_evaluacion_" + num] || "");
  $("#tipo_evaluacion_" + num).val(datos["tipo_evaluacion_" + num] || "");
  $("#instrumento_evaluacion_" + num).val(datos["instrumento_evaluacion_" + num] || "");
  $("#criterios_evaluacion_" + num).val(criterios || "");
  marcarAgentesEvaluadores(num, datos["agente_evaluador_" + num]);
  $("#tiempo_minutos_" + num).val(valorCampoNumericoGuia(datos["tiempo_minutos_" + num]));
  $("#recursos_didacticos_" + num).val(recursos || "");
  $("#periodo_tiempo_programado_" + num).val(datos["periodo_tiempo_programado_" + num] || "");
  $("#puntaje_" + num).val(valorCampoNumericoGuia(datos["puntaje_" + num]));
  $("#fecha_entrega_" + num).val(datos["fecha_entrega_" + num] || "");
}

function generarEstudioIndependiente(asignacionId, silaboId) {
  var modeloSeleccionado = $("#modelo_select_estudio").val();
  var numActividades = $("#numero_actividades").val();
  var encuentro = $("#numero_encuentro").val() || 1;

  mostrarSpinnerEstudio();
  $(".guia-dynamic-alert").remove();

  var formSilaboId = $("#silabo_id").val();
  if (formSilaboId && formSilaboId.trim() !== "") {
    silaboId = formSilaboId.trim();
  }

  var csrfToken = typeof getCookie === "function" ? getCookie("csrftoken") : "";
  var formData = new FormData();
  formData.append("modelo", modeloSeleccionado);
  formData.append("csrfmiddlewaretoken", csrfToken);
  formData.append("encuentro", encuentro);
  formData.append("numero_actividades", numActividades);

  if (silaboId && silaboId !== "null" && silaboId.trim() !== "") {
    formData.append("silabo_id", silaboId);
  } else if (asignacionId && asignacionId !== "null" && asignacionId.trim() !== "") {
    formData.append("asignacion_id", asignacionId);
  } else {
    ocultarSpinnerEstudio();
    notificarIA(
      "danger",
      "¡Error!",
      "No se pudo identificar el sílabo o asignación para generar el estudio independiente."
    );
    return;
  }

  $.ajax({
    url: "/generar-estudio-independiente/",
    type: "POST",
    data: formData,
    processData: false,
    contentType: false,
    timeout: 120000,
    beforeSend: function (xhr) {
      xhr.setRequestHeader("X-CSRFToken", csrfToken);
    },
    success: function (response) {
      ocultarSpinnerEstudio();

      if (response && response.success && response.datos) {
        guiasEstudio = response.estudios || [];
        var cantidad = parseInt($("#numero_actividades").val(), 10) || 4;
        var datos = response.datos;

        if (datos.guia_id) {
          $("#guia_id").val(datos.guia_id);
        }

        if (datos.unidad) $("#unidad").val(datos.unidad);
        if (datos.nombre_de_la_unidad) $("#nombre_de_la_unidad").val(datos.nombre_de_la_unidad);
        if (datos.fecha) $("#fecha").val(datos.fecha);

        for (var n = 1; n <= 4; n++) {
          aplicarDatosActividad(n, datos, cantidad);
        }

        $("#formEstudioIndependiente .is-invalid").removeClass("is-invalid");

        if (typeof actualizarSumaPuntajes === "function") {
          actualizarSumaPuntajes();
        }
        $("#puntaje_1").trigger("change");

        if (window.GuiaWizard && typeof window.GuiaWizard.onAfterAiAutofill === "function") {
          window.GuiaWizard.onAfterAiAutofill();
        }

        notificarIA(
          "success",
          "¡Contenido generado!",
          "Se completaron " + cantidad + " actividades. Revisa cada paso antes de guardar."
        );
      } else {
        notificarIA(
          "danger",
          "Error al generar:",
          (response && response.error) || "Respuesta inesperada del servidor."
        );
      }
    },
    error: function (xhr, status) {
      console.error("Error en la solicitud AJAX:", xhr.status, status);
      ocultarSpinnerEstudio();
      var errorMsg = "Error al comunicarse con el servidor.";
      if (status === "timeout") {
        errorMsg = "La solicitud tomó demasiado tiempo. Por favor, intenta nuevamente.";
      } else if (xhr && xhr.responseText) {
        try {
          var parsed = JSON.parse(xhr.responseText);
          if (parsed && parsed.error) errorMsg = parsed.error;
        } catch (_) {
          // Mantener mensaje por defecto
        }
      }
      notificarIA("danger", "Error al generar:", errorMsg);
    },
  });
}

$(document).ready(function () {
  var asignacionId = typeof ASIGNACION_ID !== "undefined" ? ASIGNACION_ID : null;
  var silaboId = typeof SILABO_ID !== "undefined" ? SILABO_ID : null;

  $("#seccionEstudioIndependiente").show();

  $("#boton-generar-estudio").on("click", function () {
    generarEstudioIndependiente(asignacionId, silaboId);
  });
});
