// plan_de_estudio/static/js/silabo_ia.js
/**
 * silabo_ia.js
 * Script para manejar la generación de sílabo mediante IA
 * y el autocompletado del formulario de guardado.
 */




function notificarErrorGeneracion(mensaje) {
  if (typeof mostrarMensajeError === "function") {
    mostrarMensajeError(mensaje, "#silabo-alert-container");
    return;
  }
  const $container = $("#silabo-alert-container");
  if ($container.length > 0) {
    $container.empty();
    const $alert = $(
      '<div class="alert alert-danger alert-dismissible fade show mt-3 silabo-dynamic-alert" role="alert"><strong>¡Error!</strong> <span class="silabo-alert-body"></span><button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>',
    );
    $alert.find(".silabo-alert-body").text(mensaje);
    $container.append($alert);
  } else {
    alert(mensaje);
  }
}

function extraerMensajeErrorAjax(xhr, status) {
  const defaultMsg =
    "Hubo un error al generar el sílabo. Por favor, revise la consola e intente nuevamente.";
  if (status === "timeout") {
    return "La solicitud tomó demasiado tiempo. Por favor, intente nuevamente.";
  }
  if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
    return xhr.responseJSON.error;
  }
  if (xhr && xhr.responseText) {
    try {
      const parsed = JSON.parse(xhr.responseText);
      if (parsed && parsed.error) {
        return parsed.error;
      }
    } catch (_) {
      // No es JSON válido
    }
  }
  if (xhr && xhr.status === 403) {
    return "Error de permisos o sesión (CSRF). Recargue la página e intente nuevamente.";
  }
  if (xhr && xhr.status === 0) {
    return "No se pudo conectar con el servidor. Verifique su conexión e intente nuevamente.";
  }
  return defaultMsg;
}

$(document).ready(function () {
  // --- Manejador de eventos para el formulario de GENERACIÓN ---

  $("#silabo-form").on("submit", function (e) {
    e.preventDefault();

    $(".silabo-dynamic-alert").remove();
    mostrarSpinner(); // Mostrar spinner y ocultar texto/icono del botón generar
    $("#boton-generar").prop("disabled", true);

    const formData = new FormData(this);

    $.ajax({
      url: $(this).attr("action"),
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      timeout: 120000,
      success: function (response) {
        console.log("Respuesta de generación recibida:", response);

        if (response && typeof response === "object" && response.silabo_data) {
          const silaboData = response.silabo_data;
          console.log("--- Iniciando Autocompletado ---");

          // Rellenar los campos del formulario de GUARDAR (#form-guardar-silabo)
          autocompletarFormularioGuardar(silaboData);

          // Disparar evento change para que los estilos de validación se apliquen
          $(
            "#form-guardar-silabo input, #form-guardar-silabo select, #form-guardar-silabo textarea",
          ).trigger("change");

          // Resaltar campos llenados (función definida en silabo_guardar.js)
          if (typeof highlightFilledFields === "function") {
            highlightFilledFields();
          } else {
            console.warn(
              "La función highlightFilledFields no está definida. Asegúrate de cargar silabo_guardar.js primero.",
            );
          }

          if (
            window.SilaboWizard &&
            typeof window.SilaboWizard.onAfterAiAutofill === "function"
          ) {
            window.SilaboWizard.onAfterAiAutofill();
          }

          if (typeof mostrarMensajeExito === "function") {
            mostrarMensajeExito(
              "Contenido generado con éxito. Revisa cada paso antes de guardar.",
              "#silabo-alert-container",
            );
          }

          console.log("--- Autocompletado Finalizado ---");
        } else {
          console.error("No se encontró silabo_data en la respuesta:", response);
          const errorMsg =
            response && typeof response === "object" && response.error
              ? response.error
              : "La respuesta del servidor no contiene los datos esperados para el sílabo. Si su sesión expiró, recargue la página.";
          notificarErrorGeneracion(errorMsg);
        }
      },
      error: function (xhr, status) {
        console.error("Error en la solicitud de generación:", xhr.status, xhr.responseText);
        const errorMsg = extraerMensajeErrorAjax(xhr, status);
        notificarErrorGeneracion(errorMsg);
      },
      complete: function () {
        // Restaurar el botón de generar y ocultar spinners
        $("#boton-generar").prop("disabled", false);
        $("#boton-generar .spinner").addClass("d-none"); // Ocultar todos los spinners asociados
        $("#boton-generar .text, #boton-generar .sparkle").removeClass(
          "d-none",
        ); // Mostrar texto/icono
      },
    });
  });
});

/**
 * Función para mostrar spinner durante la generación
 */
function mostrarSpinner() {
  // Mostrar los spinners asociados al botón de generar (puedes ajustar el selector si es necesario)
  $("#boton-generar .spinner-border, #boton-generar .spinner-grow").removeClass(
    "d-none",
  );
  // Ocultar el texto y el icono del botón de generar
  $("#boton-generar .text, #boton-generar .sparkle").addClass("d-none");
}

function normalizarTextoOpcion(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/**
 * Función auxiliar para marcar/desmarcar checkboxes de un grupo
 * @param {string} fieldName - El atributo 'name' de los checkboxes
 * @param {string|string[]} values - El valor o array de valores a seleccionar
 */
function setCheckboxMultiple(fieldName, values) {
  // 1. Desmarcar todos los checkboxes de este grupo primero
  const $allCheckboxes = $(`input[name="${fieldName}"]`);
  $allCheckboxes.prop("checked", false);

  // 2. Asegurarse de que 'values' sea un array, verificando primero coincidencia exacta antes de dividir
  let valuesArray = [];
  if (values) {
    if (Array.isArray(values)) {
      valuesArray = values;
    } else if (typeof values === "string") {
      const normalizedValue = String(values).trim();
      if (normalizedValue) {
        const targetNorm = normalizarTextoOpcion(normalizedValue);
        let matchesSingleOption = false;
        $allCheckboxes.each(function () {
          if (normalizarTextoOpcion($(this).val()) === targetNorm) {
            matchesSingleOption = true;
            return false;
          }
        });
        valuesArray = matchesSingleOption
          ? [normalizedValue]
          : normalizedValue
              .split(/\s*[,;/\n]\s*|\s+y\s+/i)
              .map((v) => v.trim())
              .filter(Boolean);
      }
    } else {
      valuesArray = [String(values)];
    }
  }

  // 3. Marcar hasta 2 checkboxes correspondientes si hay valores
  if (valuesArray.length > 0) {
    let checkedCount = 0;
    valuesArray.forEach(function (valueToSelect) {
      if (checkedCount >= 2) return;
      const normalizedValueToSelect = String(valueToSelect).trim();
      if (!normalizedValueToSelect) return;

      const targetNorm = normalizarTextoOpcion(normalizedValueToSelect);
      $allCheckboxes.each(function () {
        if (normalizarTextoOpcion($(this).val()) === targetNorm) {
          if (!$(this).prop("checked")) {
            $(this).prop("checked", true);
            checkedCount++;
          }
          return false;
        }
      });
    });
  }

  // Disparar 'change' en el primer checkbox del grupo para que los listeners reaccionen
  $allCheckboxes.first().trigger("change");
}

/**
 * Rellena los campos del formulario #form-guardar-silabo con los datos de la IA
 * @param {object} silaboData - Objeto con los datos generados por la IA
 */
function autocompletarFormularioGuardar(silaboData) {
  // Sección 1: Información general (proteger codigo y encuentros asignados por el servidor)
  if (!$("#id_codigo").val() && silaboData.codigo) {
    $("#id_codigo").val(silaboData.codigo);
  }
  if (!$("#id_encuentros").val() && silaboData.encuentros) {
    $("#id_encuentros").val(silaboData.encuentros);
  }
  $("#id_fecha").val(silaboData.fecha || "");
  $("#id_unidad").val(silaboData.unidad || "");
  $("#id_nombre_de_la_unidad").val(silaboData.nombre_de_la_unidad || "");
  $("#id_contenido_tematico").val(silaboData.contenido_tematico || "");

  // Sección 2: Objetivos de la unidad
  $("#id_objetivo_conceptual").val(silaboData.objetivo_conceptual || "");
  $("#id_objetivo_procedimental").val(silaboData.objetivo_procedimental || "");
  $("#id_objetivo_actitudinal").val(silaboData.objetivo_actitudinal || "");

  // Sección 3: Descripción de las fases del acto mental
  // Primer momento
  $("#id_tipo_primer_momento").val(silaboData.tipo_primer_momento || "");
  $("#id_detalle_primer_momento").val(silaboData.detalle_primer_momento || "");
  $("#id_tiempo_primer_momento").val(silaboData.tiempo_primer_momento || "");
  $("#id_recursos_primer_momento").val(
    silaboData.recursos_primer_momento || "",
  );

  // Segundo momento
  $("#id_tipo_segundo_momento_claseteoria").val(
    silaboData.tipo_segundo_momento_claseteoria || "",
  );
  $("#id_clase_teorica").val(silaboData.clase_teorica || "");
  $("#id_tipo_segundo_momento_practica").val(
    silaboData.tipo_segundo_momento_practica || "",
  );
  $("#id_clase_practica").val(silaboData.clase_practica || "");
  let tiempoTeo = silaboData.tiempo_segundo_momento_teorica;
  let tiempoPra = silaboData.tiempo_segundo_momento_practica;
  if (!tiempoTeo && !tiempoPra && silaboData.tiempo_segundo_momento) {
    const totalSeg = parseInt(silaboData.tiempo_segundo_momento, 10) || 60;
    tiempoTeo = Math.max(1, Math.floor(totalSeg / 2));
    tiempoPra = Math.max(1, totalSeg - tiempoTeo);
  }
  $("#id_tiempo_segundo_momento_teorica").val(tiempoTeo || "");
  $("#id_tiempo_segundo_momento_practica").val(tiempoPra || "");
  $("#id_recursos_segundo_momento").val(
    silaboData.recursos_segundo_momento || "",
  );

  // Tercer momento
  setCheckboxMultiple("tipo_tercer_momento", silaboData.tipo_tercer_momento);
  $("#id_detalle_tercer_momento").val(silaboData.detalle_tercer_momento || "");
  $("#id_tiempo_tercer_momento").val(silaboData.tiempo_tercer_momento || "");
  $("#id_recursos_tercer_momento").val(
    silaboData.recursos_tercer_momento || "",
  );

  // Ejes transversales
  setCheckboxMultiple("eje_transversal", silaboData.eje_transversal);
  $("#id_detalle_eje_transversal").val(
    silaboData.detalle_eje_transversal || "",
  );

  // Sección 4: Evaluación dinámica
  if (
    typeof silaboData.actividad_aprendizaje === "string" &&
    silaboData.actividad_aprendizaje &&
    !silaboData.actividad_aprendizaje.toLowerCase().includes("no se realizará")
  ) {
    $("#sin_evaluacion_dinamica").prop("checked", false);
    if (typeof toggleEvaluacionDinamica === "function") {
      toggleEvaluacionDinamica();
    } else {
      $("#container_evaluacion_dinamica").show();
    }
  }
  $("#id_actividad_aprendizaje").val(silaboData.actividad_aprendizaje || "");
  setCheckboxMultiple("tecnica_evaluacion", silaboData.tecnica_evaluacion);
  setCheckboxMultiple("tipo_evaluacion", silaboData.tipo_evaluacion);
  $("#id_periodo_tiempo_programado").val(
    silaboData.periodo_tiempo_programado || "",
  );
  const tiempoMinutosVal =
    silaboData.tiempo_minutos !== undefined &&
    silaboData.tiempo_minutos !== null &&
    silaboData.tiempo_minutos !== ""
      ? silaboData.tiempo_minutos
      : "";
  $("#id_tiempo_minutos").val(tiempoMinutosVal);
  setCheckboxMultiple("agente_evaluador", silaboData.agente_evaluador);
  $("#id_instrumento_evaluacion").val(silaboData.instrumento_evaluacion || ""); // Asume select normal
  // Criterios: si viene como array, unirlo; si no, usarlo tal cual
  let criterios = silaboData.criterios_evaluacion || "";
  if (Array.isArray(criterios)) {
    // Unir con salto de línea o coma y espacio, según prefieras
    criterios = criterios.join("\n"); // O ", "
  }
  $("#id_criterios_evaluacion").val(criterios);
  const puntajeVal =
    silaboData.puntaje !== undefined &&
    silaboData.puntaje !== null &&
    silaboData.puntaje !== ""
      ? silaboData.puntaje
      : "";
  $("#id_puntaje").val(puntajeVal);

  // =======================================================
  // === ¡AQUÍ ESTÁ LA LÍNEA AÑADIDA! ===
  // Llamar a la función para recalcular el tiempo total después de rellenar los campos.
  // =======================================================
  if (typeof calcularTiempoTotal === "function") {
    calcularTiempoTotal();
    console.log("calcularTiempoTotal ejecutada después del autocompletado de la IA.");
  } else {
    console.warn("La función calcularTiempoTotal no fue encontrada.");
  }
}
