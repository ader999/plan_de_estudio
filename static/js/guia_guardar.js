/**
 * guia_guardar.js
 * Script para validar, recopilar y guardar el formulario de Guía de Estudio Independiente,
 * integrado con GuiaWizard para navegación paso a paso y borrador local.
 */

var currentSection = "estudioIndependiente";

var GUIA_CAMPOS_GENERALES = ["fecha", "unidad", "nombre_de_la_unidad"];
var GUIA_PREFIJOS_ACTIVIDAD = [
  "tipo_objetivo",
  "objetivo_aprendizaje",
  "contenido_tematico",
  "actividad_aprendizaje",
  "tiempo_minutos",
  "recursos_didacticos",
  "periodo_tiempo_programado",
  "puntaje",
  "fecha_entrega",
  "tecnica_evaluacion",
  "instrumento_evaluacion",
  "criterios_evaluacion",
  "tipo_evaluacion",
];

function mostrarSpinnerGuardar() {
  $("#spinnerGuardar").removeClass("d-none");
  $("#guardarFormularioBtn").prop("disabled", true);
}

function ocultarSpinnerGuardar() {
  $("#spinnerGuardar").addClass("d-none");
  $("#guardarFormularioBtn").prop("disabled", false);
}

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

function obtenerContenedorAlertaGuia(targetSelector) {
  var candidatos = targetSelector
    ? [targetSelector, "#wizard-step-alert-container", "#guardar-alert-container", "#formEstudioIndependiente"]
    : ["#wizard-step-alert-container", "#guardar-alert-container", "#formEstudioIndependiente"];

  for (var i = 0; i < candidatos.length; i++) {
    var $el = $(candidatos[i]);
    if ($el.length > 0) return $el.first();
  }
  return $("body");
}

function limpiarAlertasGuia() {
  $(".guia-dynamic-alert").remove();
}

function mostrarAlertaGuia(tipo, titulo, mensajes, targetSelector) {
  limpiarAlertasGuia();
  var $container = obtenerContenedorAlertaGuia(targetSelector);
  var lista = Array.isArray(mensajes) ? mensajes : [mensajes];

  var $alert = $(
    '<div class="alert alert-' + tipo + ' alert-dismissible fade show mt-3 guia-dynamic-alert text-start" role="alert">' +
      '<div class="fw-bold mb-1 guia-alert-title"></div>' +
      '<div class="guia-alert-body"></div>' +
      '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
    '</div>'
  );
  $alert.find(".guia-alert-title").text(titulo);

  var $body = $alert.find(".guia-alert-body");
  if (lista.length === 1) {
    $body.text(String(lista[0]));
  } else {
    var $ul = $('<ul class="mb-0 ps-3"></ul>');
    lista.forEach(function (msg) {
      $ul.append($("<li></li>").text(String(msg)));
    });
    $body.append($ul);
  }

  $container.prepend($alert);
}

function desplazarHaciaCampo($elemento) {
  if (!$elemento || !$elemento.length) return;
  if (window.GuiaWizard && typeof window.GuiaWizard.goToStepForElement === "function") {
    window.GuiaWizard.goToStepForElement($elemento);
  }

  var navbarHeight = $("#main-navbar").outerHeight() || 72;
  var topOffset = Math.max(0, $elemento.offset().top - navbarHeight - 20);
  $("html, body").animate({ scrollTop: topOffset }, 300);

  if ($elemento.is("input, select, textarea")) {
    $elemento.trigger("focus");
  }
}

function validarPuntajes(mensajesError) {
  var valido = true;
  var puntajes = [];
  var hayNegativo = false;

  for (var i = 1; i <= 4; i++) {
    var raw = $("#puntaje_" + i).val();
    var p = raw === "" || raw === null || raw === undefined ? 0 : parseInt(raw, 10) || 0;
    puntajes.push(p);
    if (p < 0) {
      $("#puntaje_" + i).addClass("is-invalid");
      hayNegativo = true;
      valido = false;
    }
  }

  if (hayNegativo) {
    mensajesError.push(
      "Los puntajes no pueden ser negativos. Por favor, ingrese valores mayores o iguales a 0."
    );
  }

  var sumaPuntajes = puntajes[0] + puntajes[1] + puntajes[2] + puntajes[3];
  if (sumaPuntajes > 100) {
    mensajesError.push(
      "La suma de los puntajes no puede exceder 100 puntos. Actualmente suma: " + sumaPuntajes
    );
    $("#puntaje_1, #puntaje_2, #puntaje_3, #puntaje_4").addClass("is-invalid");
    valido = false;
  }

  return valido;
}

function verificarListaCamposRequeridos(fieldIds, camposFaltantes) {
  var valido = true;
  $.each(fieldIds, function (_, campoId) {
    var $campo = $("#" + campoId);
    if ($campo.length && String($campo.val() || "").trim() === "") {
      $campo.addClass("is-invalid");
      var labelText = $("label[for='" + campoId + "']").first().text().replace(/\*/g, "").trim();
      if (labelText) {
        camposFaltantes.push(labelText);
      }
      valido = false;
    }
  });
  return valido;
}

function validarActividad1(camposFaltantes) {
  var ids = GUIA_PREFIJOS_ACTIVIDAD.map(function (prefijo) {
    return prefijo + "_1";
  });
  var okCampos = verificarListaCamposRequeridos(ids, camposFaltantes);

  var agentes1 = $('input[name="agente_evaluador_1[]"]:checked').length;
  if (agentes1 === 0) {
    $('input[name="agente_evaluador_1[]"]')
      .first()
      .closest(".agent-chip-list, .form-check")
      .addClass("is-invalid");
    camposFaltantes.push("Agente Evaluador 1");
    return false;
  }
  return okCampos;
}

/**
 * Valida una actividad opcional (2, 3 o 4): debe estar totalmente vacía o totalmente llena.
 */
function validarActividadOpcional(numeroActividad, mensajesError) {
  var camposActividad = GUIA_PREFIJOS_ACTIVIDAD.map(function (prefijo) {
    return prefijo + "_" + numeroActividad;
  });

  var algunCampoConInfo = false;
  var todosCamposLlenos = true;
  var camposVacios = [];

  $.each(camposActividad, function (_, campoId) {
    var $campo = $("#" + campoId);
    if (!$campo.length) return;

    var valor = $campo.val();
    if (valor === null || valor === undefined) valor = "";
    var tieneContenido = false;

    if ($campo.is('input[type="number"]')) {
      var valorNumerico = parseFloat(valor);
      var esPuntaje = ($campo.attr("id") || "").indexOf("puntaje_") === 0;
      tieneContenido = !isNaN(valorNumerico) && (esPuntaje ? valorNumerico >= 0 : valorNumerico > 0);
    } else {
      tieneContenido = String(valor).trim() !== "";
    }

    if (tieneContenido) {
      algunCampoConInfo = true;
    } else {
      todosCamposLlenos = false;
      camposVacios.push(campoId);
    }
  });

  var agentesSeleccionados = $(
    'input[name="agente_evaluador_' + numeroActividad + '[]"]:checked'
  ).length;
  if (agentesSeleccionados > 0) {
    algunCampoConInfo = true;
  } else {
    todosCamposLlenos = false;
  }

  if (!algunCampoConInfo) {
    $(
      "#tipo_objetivo_" + numeroActividad +
      ", #tipo_evaluacion_" + numeroActividad +
      ", #tecnica_evaluacion_" + numeroActividad +
      ", #instrumento_evaluacion_" + numeroActividad +
      ", #periodo_tiempo_programado_" + numeroActividad
    ).val("");
    $('input[name="agente_evaluador_' + numeroActividad + '[]"]').prop("checked", false);
    return true;
  }

  if (algunCampoConInfo && !todosCamposLlenos) {
    mensajesError.push(
      "La Actividad de Aprendizaje " +
        numeroActividad +
        " está incompleta. Complete todos los campos o use 'Limpiar' para omitirla."
    );
    $.each(camposVacios, function (_, campoId) {
      $("#" + campoId).addClass("is-invalid");
    });
    if (agentesSeleccionados === 0) {
      $('input[name="agente_evaluador_' + numeroActividad + '[]"]')
        .first()
        .closest(".agent-chip-list, .form-check")
        .addClass("is-invalid");
    }
    return false;
  }

  return todosCamposLlenos;
}

function construirMensajeFaltantes(camposFaltantes, mensajesError) {
  if (camposFaltantes.length === 0) return;
  if (camposFaltantes.length <= 4) {
    mensajesError.push(
      "Complete los siguientes campos obligatorios: " + camposFaltantes.join(", ") + "."
    );
  } else {
    mensajesError.push(
      "Faltan " +
        camposFaltantes.length +
        " campos obligatorios (marcados en color). Complétalos para continuar."
    );
  }
}

/**
 * Validación por paso (usada por el botón "Siguiente" del wizard)
 */
function validarPasoFormulario(stepNumber) {
  if (stepNumber === 5) {
    return validarFormulario();
  }

  var $stepScope = $('.wizard-step[data-step="' + stepNumber + '"]');
  $stepScope.find(".is-invalid").removeClass("is-invalid");
  limpiarAlertasGuia();

  var valido = true;
  var mensajesError = [];
  var camposFaltantes = [];

  if (stepNumber === 1) {
    valido = verificarListaCamposRequeridos(GUIA_CAMPOS_GENERALES, camposFaltantes);
  } else if (stepNumber === 2) {
    var okAct1 = validarActividad1(camposFaltantes);
    var okPts1 = validarPuntajes(mensajesError);
    valido = okAct1 && okPts1;
  } else if (stepNumber === 3) {
    var okAct2 = validarActividadOpcional(2, mensajesError);
    var okPts2 = validarPuntajes(mensajesError);
    valido = okAct2 && okPts2;
  } else if (stepNumber === 4) {
    var okAct3 = validarActividadOpcional(3, mensajesError);
    var okAct4 = validarActividadOpcional(4, mensajesError);
    var okPts34 = validarPuntajes(mensajesError);
    valido = okAct3 && okAct4 && okPts34;
    if (!okAct3 && window.GuiaWizard) window.GuiaWizard.setActivityCollapsed(3, false);
    if (!okAct4 && window.GuiaWizard) window.GuiaWizard.setActivityCollapsed(4, false);
  }

  construirMensajeFaltantes(camposFaltantes, mensajesError);

  if (!valido || mensajesError.length > 0) {
    mostrarAlertaGuia("warning", "Revisa este paso antes de continuar:", mensajesError, "#wizard-step-alert-container");
    var $primer = $stepScope.find(".is-invalid").first();
    if ($primer.length) {
      desplazarHaciaCampo($primer);
    }
    return false;
  }

  return true;
}

/**
 * Validación completa del formulario antes de guardar en servidor
 */
function validarFormulario() {
  var formularioValido = true;
  var mensajesError = [];
  var camposFaltantes = [];

  $("#formEstudioIndependiente .is-invalid").removeClass("is-invalid");
  limpiarAlertasGuia();

  if (!validarPuntajes(mensajesError)) {
    formularioValido = false;
  }
  if (!verificarListaCamposRequeridos(GUIA_CAMPOS_GENERALES, camposFaltantes)) {
    formularioValido = false;
  }
  if (!validarActividad1(camposFaltantes)) {
    formularioValido = false;
  }

  for (var n = 2; n <= 4; n++) {
    if (!validarActividadOpcional(n, mensajesError)) {
      formularioValido = false;
    }
  }

  construirMensajeFaltantes(camposFaltantes, mensajesError);

  if (!formularioValido || mensajesError.length > 0) {
    mostrarAlertaGuia("danger", "Corrige lo siguiente para guardar la guía:", mensajesError, "#wizard-step-alert-container");
    var $primerInvalido = $("#formEstudioIndependiente .is-invalid").first();
    if ($primerInvalido.length) {
      desplazarHaciaCampo($primerInvalido);
    }
    return false;
  }

  return true;
}

function resolverSilaboId() {
  var formSilaboId = $("#silabo_id").val();
  if (formSilaboId && formSilaboId.trim() !== "") {
    return formSilaboId.trim();
  }
  if (typeof SILABO_ID !== "undefined" && SILABO_ID && SILABO_ID !== "null") {
    return String(SILABO_ID).trim();
  }
  return null;
}

/**
 * Recopilación de datos del formulario (Actividades 1 a 4)
 */
function recopilarDatosFormulario() {
  var formData = {};
  formData.silabo_id = resolverSilaboId();
  formData.guia_id = $("#guia_id").val() || null;
  formData.numero_encuentro = $("#numero_encuentro").val();
  formData.fecha = $("#fecha").val();
  formData.unidad = $("#unidad").val();
  formData.nombre_de_la_unidad = $("#nombre_de_la_unidad").val();

  // Tarea 1 (siempre incluida)
  GUIA_PREFIJOS_ACTIVIDAD.forEach(function (prefijo) {
    formData[prefijo + "_1"] = $("#" + prefijo + "_1").val();
  });
  formData.agente_evaluador_1 = [];
  $('input[name="agente_evaluador_1[]"]:checked').each(function () {
    formData.agente_evaluador_1.push($(this).val());
  });

  // Tareas opcionales 2, 3 y 4 (solo incluir campos con valor)
  for (var n = 2; n <= 4; n++) {
    GUIA_PREFIJOS_ACTIVIDAD.forEach(function (prefijo) {
      var val = $("#" + prefijo + "_" + n).val();
      if (val !== null && val !== undefined && String(val).trim() !== "") {
        formData[prefijo + "_" + n] = val;
      }
    });

    var agentesN = [];
    $('input[name="agente_evaluador_' + n + '[]"]:checked').each(function () {
      agentesN.push($(this).val());
    });
    if (agentesN.length > 0) {
      formData["agente_evaluador_" + n] = agentesN;
    }
  }

  return formData;
}

function resaltarErroresBackend(errors) {
  if (!errors || typeof errors !== "object") return;
  Object.keys(errors).forEach(function (field) {
    var $el = $("#" + field);
    if ($el.length) {
      $el.addClass("is-invalid");
    } else {
      var $checks = $('input[name="' + field + '[]"]');
      if ($checks.length) {
        $checks.first().closest(".agent-chip-list, .form-check").addClass("is-invalid");
      }
    }
  });
  var $primer = $("#formEstudioIndependiente .is-invalid").first();
  if ($primer.length) {
    desplazarHaciaCampo($primer);
  }
}

/**
 * Envío final del formulario por AJAX
 */
function guardarFormulario() {
  if (!validarFormulario()) {
    return;
  }

  mostrarSpinnerGuardar();
  var formData = recopilarDatosFormulario();
  var silaboId = resolverSilaboId();
  var url = silaboId ? "/guardar-guia/" + silaboId + "/" : "/guardar-guia/";

  $.ajax({
    url: url,
    type: "POST",
    data: JSON.stringify(formData),
    contentType: "application/json",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    success: function (response) {
      if (response && response.success) {
        if (response.guia_id) {
          $("#guia_id").val(response.guia_id);
        }

        // Eliminar borrador local únicamente cuando el backend confirmó el guardado
        if (window.GuiaWizard && typeof window.GuiaWizard.clearDraft === "function") {
          window.GuiaWizard.clearDraft();
        }

        mostrarAlertaGuia(
          "success",
          "¡Guía guardada!",
          "Estudio independiente guardado con éxito.",
          "#guardar-alert-container"
        );

        if (response.redirect_url) {
          setTimeout(function () {
            window.location.href = response.redirect_url;
          }, 900);
          return;
        }
        ocultarSpinnerGuardar();
      } else {
        ocultarSpinnerGuardar();
        if (response && response.errors) {
          resaltarErroresBackend(response.errors);
        }
        mostrarAlertaGuia(
          "danger",
          "Error al guardar:",
          (response && response.error) || "No se pudo guardar la guía.",
          "#guardar-alert-container"
        );
      }
    },
    error: function (xhr) {
      console.error("Error en la solicitud AJAX:", xhr.status, xhr.responseText);
      ocultarSpinnerGuardar();
      var errorMsg = "Error al comunicarse con el servidor.";
      try {
        var errorResponse = JSON.parse(xhr.responseText);
        if (errorResponse && errorResponse.errors) {
          resaltarErroresBackend(errorResponse.errors);
        }
        if (errorResponse && errorResponse.error) {
          errorMsg = errorResponse.error;
        }
      } catch (e) {
        console.error("No se pudo parsear la respuesta de error:", e);
      }
      mostrarAlertaGuia("danger", "No se pudo guardar:", errorMsg, "#guardar-alert-container");
    },
  });
}

/**
 * Actualiza el texto y estado de la suma total de puntajes de las 4 actividades
 */
function actualizarSumaPuntajes() {
  var p1 = parseInt($("#puntaje_1").val(), 10) || 0;
  var p2 = parseInt($("#puntaje_2").val(), 10) || 0;
  var p3 = parseInt($("#puntaje_3").val(), 10) || 0;
  var p4 = parseInt($("#puntaje_4").val(), 10) || 0;

  var sumaPuntajes = p1 + p2 + p3 + p4;
  var $suma = $("#sumaPuntajes");
  $suma.text(sumaPuntajes);

  if (sumaPuntajes <= 100 && p1 >= 0 && p2 >= 0 && p3 >= 0 && p4 >= 0) {
    $suma.removeClass("text-danger").addClass("text-success");
  } else {
    $suma.removeClass("text-success").addClass("text-danger");
  }

  return sumaPuntajes;
}

$(document).ready(function () {
  actualizarSumaPuntajes();

  $("#puntaje_1, #puntaje_2, #puntaje_3, #puntaje_4").on("input change keyup", function () {
    actualizarSumaPuntajes();

    var p1 = parseInt($("#puntaje_1").val(), 10) || 0;
    var p2 = parseInt($("#puntaje_2").val(), 10) || 0;
    var p3 = parseInt($("#puntaje_3").val(), 10) || 0;
    var p4 = parseInt($("#puntaje_4").val(), 10) || 0;
    var sumaPuntajes = p1 + p2 + p3 + p4;

    if (sumaPuntajes > 100 || p1 < 0 || p2 < 0 || p3 < 0 || p4 < 0) {
      $(this).addClass("is-invalid");
    } else {
      $(".puntaje").removeClass("is-invalid");
    }
  });

  $("#guardarFormularioBtn").on("click", function () {
    guardarFormulario();
  });
});
