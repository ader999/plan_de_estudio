// plan_de_estudio/static/js/silabo_ia.js
/**
 * silabo_ia.js
 * Script para manejar la generación de sílabo mediante IA
 * y el autocompletado del formulario de guardado.
 */




$(document).ready(function () {
  // --- Manejador de eventos para el formulario de GENERACIÓN ---

  $("#silabo-form").on("submit", function (e) {
    e.preventDefault();

    mostrarSpinner(); // Mostrar spinner y ocultar texto/icono del botón generar
    $("#boton-generar").prop("disabled", true);

    const formData = new FormData(this);

    $.ajax({
      url: $(this).attr("action"),
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      success: function (response) {
        console.log("Respuesta de generación recibida:", response);

        if (response.silabo_data) {
          const silaboData = response.silabo_data;
          console.log("--- Iniciando Autocompletado ---");
          // console.log("Datos Completos (silaboData):", JSON.stringify(silaboData, null, 2));

          // Rellenar los campos del formulario de GUARDAR (#form-guardar-silabo)
          autocompletarFormularioGuardar(silaboData);

          // Disparar evento change para que los estilos de validación se apliquen
          $(
            "#form-guardar-silabo input, #form-guardar-silabo select, #form-guardar-silabo textarea",
          ).trigger("change");

          // Resaltar campos llenados (función definida en silabo_guardar.js)
          // Asegúrate que silabo_guardar.js se carga ANTES que silabo_ia.js
          if (typeof highlightFilledFields === "function") {
            highlightFilledFields();
          } else {
            console.warn(
              "La función highlightFilledFields no está definida. Asegúrate de cargar silabo_guardar.js primero.",
            );
          }

          console.log("--- Autocompletado Finalizado ---");
        } else {
          console.error("No se encontró silabo_data en la respuesta");
          // Usar la función de mensaje de error si está disponible
          if (typeof mostrarMensajeError === "function") {
            mostrarMensajeError(
              "La respuesta del servidor no contiene los datos esperados para el sílabo.",
            );
          } else {
            alert(
              "La respuesta del servidor no contiene los datos esperados para el sílabo.",
            );
          }
        }
      },
      error: function (xhr) {
        console.error("Error en la solicitud de generación:", xhr.responseText);
        // Usar la función de mensaje de error si está disponible
        if (typeof mostrarMensajeError === "function") {
          mostrarMensajeError(
            "Hubo un error al generar el sílabo. Por favor, revise la consola e intente nuevamente.",
          );
        } else {
          alert(
            "Hubo un error al generar el sílabo. Por favor, revise la consola e intente nuevamente.",
          );
        }
      },
      complete: function () {
        // Restaurar el botón de generar y ocultar spinners
        $("#boton-generar").prop("disabled", false);
        $(".spinner").addClass("d-none"); // Ocultar todos los spinners asociados
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

/**
 * Función auxiliar para marcar/desmarcar checkboxes de un grupo
 * @param {string} fieldName - El atributo 'name' de los checkboxes
 * @param {string|string[]} values - El valor o array de valores a seleccionar
 */
function setCheckboxMultiple(fieldName, values) {
  // 1. Desmarcar todos los checkboxes de este grupo primero
  $(`input[name="${fieldName}"]`).prop("checked", false);

  // 2. Asegurarse de que 'values' sea un array
  let valuesArray = [];
  if (values) {
    if (Array.isArray(values)) {
      valuesArray = values;
    } else if (typeof values === "string") {
      // Intentar dividir si es un string separado por comas (o manejar como valor único)
      // Normalizar: quitar espacios extra y convertir a string por si acaso
      const normalizedValue = String(values).trim();
      if (normalizedValue) {
        // Solo si no es vacío
        // Considerar si un string puede representar múltiples valores (e.g., "op1, op2")
        // Esto depende de cómo la IA devuelva los datos. Asumamos que devuelve un array
        // o un string que representa UN SOLO valor de checkbox.
        // Si puede devolver "op1, op2", necesitarías .split(',') aquí.
        // Por ahora, tratamos el string como un valor único.
        valuesArray = [normalizedValue];
      }
    } else {
      // Si es otro tipo (ej. número), convertirlo a string
      valuesArray = [String(values)];
    }
  }

  // 3. Marcar los checkboxes correspondientes si hay valores
  if (valuesArray.length > 0) {
    console.log(
      `Intentando marcar checkboxes para ${fieldName} con valores:`,
      valuesArray,
    );
    valuesArray.forEach(function (valueToSelect) {
      // Normalizar el valor a buscar (quitar espacios extra)
      const normalizedValueToSelect = String(valueToSelect).trim();
      if (!normalizedValueToSelect) return; // Saltar si el valor está vacío

      // Encontrar el checkbox por nombre y valor exacto (después de normalizar)
      const checkbox = $(
        `input[name="${fieldName}"][value="${normalizedValueToSelect}"]`,
      );

      if (checkbox.length > 0) {
        checkbox.prop("checked", true);
        console.log(
          `Checkbox encontrado y marcado: name=${fieldName}, value=${normalizedValueToSelect}`,
        );
      } else {
        // Intentar búsqueda insensible a mayúsculas/minúsculas como fallback? (Opcional)
        let foundCaseInsensitive = false;
        $(`input[name="${fieldName}"]`).each(function () {
          if (
            $(this).val().toLowerCase() ===
            normalizedValueToSelect.toLowerCase()
          ) {
            $(this).prop("checked", true);
            console.log(
              `Checkbox encontrado (case-insensitive) y marcado: name=${fieldName}, value=${$(this).val()} (buscado: ${normalizedValueToSelect})`,
            );
            foundCaseInsensitive = true;
            return false; // salir del each
          }
        });

        if (!foundCaseInsensitive) {
          console.warn(
            `No se encontró checkbox para: name=${fieldName}, value=${normalizedValueToSelect}`,
          );
        }
      }
    });
  } else {
    console.log(
      `No hay valores válidos para marcar o el array está vacío para ${fieldName}`,
    );
  }

  // Disparar 'change' en el primer checkbox del grupo para que los listeners reaccionen
  $(`input[name="${fieldName}"]`).first().trigger("change");
}

/**
 * Rellena los campos del formulario #form-guardar-silabo con los datos de la IA
 * @param {object} silaboData - Objeto con los datos generados por la IA
 */
function autocompletarFormularioGuardar(silaboData) {
  // Sección 1: Información general
  $("#id_codigo").val(silaboData.codigo || ""); // El código usualmente no lo genera la IA, pero por si acaso
  $("#id_encuentros").val(silaboData.encuentros || "");
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
  $("#id_tiempo_segundo_momento_teorica").val(
    silaboData.tiempo_segundo_momento_teorica || "",
  );
  $("#id_tiempo_segundo_momento_practica").val(
    silaboData.tiempo_segundo_momento_practica || "",
  );
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
  $("#id_actividad_aprendizaje").val(silaboData.actividad_aprendizaje || "");
  setCheckboxMultiple("tecnica_evaluacion", silaboData.tecnica_evaluacion);
  setCheckboxMultiple("tipo_evaluacion", silaboData.tipo_evaluacion);
  $("#id_periodo_tiempo_programado").val(
    silaboData.periodo_tiempo_programado || "",
  );
  $("#id_tiempo_minutos").val(silaboData.tiempo_minutos || "");
  setCheckboxMultiple("agente_evaluador", silaboData.agente_evaluador);
  $("#id_instrumento_evaluacion").val(silaboData.instrumento_evaluacion || ""); // Asume select normal
  // Criterios: si viene como array, unirlo; si no, usarlo tal cual
  let criterios = silaboData.criterios_evaluacion || "";
  if (Array.isArray(criterios)) {
    // Unir con salto de línea o coma y espacio, según prefieras
    criterios = criterios.join("\n"); // O ", "
  }
  $("#id_criterios_evaluacion").val(criterios);
  $("#id_puntaje").val(silaboData.puntaje || "");

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
