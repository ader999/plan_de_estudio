// --- START OF FILE silabo_guardar.js ---

$(document).ready(function () {
  // --- Manejadores de eventos para el formulario de GUARDAR ---

  // Manejar el botón de guardar formularios
  $("#guardarFormularioBtn").on("click", function () {
    // Mostrar spinner de guardado
    $("#spinnerGuardar").removeClass("d-none");
    $(this).prop("disabled", true);

    // Guardar el formulario de sílabo (#form-guardar-silabo)
    guardarSilabo();
  });

  // Inicializar manejo de cambios en los campos del formulario de GUARDAR
  initializeFieldChangeHandling();
});

/**
 * Función para guardar el sílabo (usa #form-guardar-silabo)
 */
function guardarSilabo() {
  // Validar campos obligatorios del formulario de GUARDAR
  if (!validarCamposObligatorios()) {
    resetearEstadoBotonGuardar();
    return false; // Detener si la validación falla
  }

  // Obtener el ID de asignación de la URL actual
  const currentUrl = window.location.pathname;
  console.log("URL actual:", currentUrl); // Depuración de la URL

  // Intentar varios patrones posibles
  let asignacionIdMatch = currentUrl.match(/\/formulario_silabo\/(\d+)\/?/);
  if (!asignacionIdMatch || !asignacionIdMatch[1]) {
    // Intentar patrón alternativo
    asignacionIdMatch = currentUrl.match(/\/(\d+)\/?$/);
  }

  if (!asignacionIdMatch || !asignacionIdMatch[1]) {
    console.error(
      "No se pudo extraer el ID de asignación de la URL:",
      currentUrl,
    );
    alert("Error: No se pudo determinar la asignación para guardar el sílabo.");
    resetearEstadoBotonGuardar();
    return false;
  }
  const asignacionId = asignacionIdMatch[1];
  console.log("ID de asignación extraído:", asignacionId); // Depuración del ID extraído

  // Usar el formulario correcto para obtener los datos a guardar
  const formData = new FormData(document.getElementById("form-guardar-silabo"));

  $.ajax({
    url: `/guardar_silabo/${asignacionId}/`, // URL para guardar
    type: "POST",
    data: formData,
    processData: false,
    contentType: false,
    headers: {
      "X-CSRFToken": getCookie("csrftoken"), // Necesaria función getCookie
    },
    success: function (response) {
      console.log("Sílabo guardado:", response);

      if (response.silabo_id) {
        $("#form-guardar-silabo").data("silabo_id", response.silabo_id); // Opcional
      }

      if (response.redirect_url) {
        setTimeout(function () {
          window.location.href = response.redirect_url;
        }, 1500);
        return; // No resetear botón si redirige
      }

      mostrarMensajeExito("Sílabo guardado con éxito");
      resetearEstadoBotonGuardar();
    },
    error: function (xhr) {
      console.error("Error al guardar sílabo:", xhr.responseText);
      resetearEstadoBotonGuardar(); // Resetear botón en caso de error

      try {
        const errorResponse = JSON.parse(xhr.responseText);
        let errorMessage = "Error al guardar el sílabo."; // Mensaje por defecto

        if (errorResponse.message) {
          errorMessage = errorResponse.message;
        }

        if (errorResponse.errors) {
          resaltarCamposConError(errorResponse.errors);
          // Si hay errores específicos, añadir un mensaje general si no existe ya uno
          if (!errorResponse.message) {
            errorMessage = "Por favor, corrija los errores marcados en rojo.";
          }
        }
        mostrarMensajeError(errorMessage); // Mostrar el mensaje de error consolidado
      } catch (e) {
        alert(
          "Error al procesar la respuesta del servidor al guardar. Por favor, intente nuevamente.",
        );
        console.error("Error al parsear JSON de error o error inesperado:", e);
      }
    },
  });
}

/**
 * Función para mostrar mensaje de éxito
 * @param {string} mensaje - Mensaje a mostrar en la alerta
 */
function mostrarMensajeExito(mensaje) {
  $(".alert-success, .alert-danger").remove();
  const alertHTML = `
        <div class="alert alert-success alert-dismissible fade show mt-3" role="alert">
            <strong>¡Éxito!</strong> ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
  $("#form-guardar-silabo .card-footer").prepend(alertHTML);
  setTimeout(() => $(".alert-success").alert("close"), 5000);
}

/**
 * Función para mostrar mensaje de error general
 * @param {string} mensaje - Mensaje a mostrar en la alerta
 */
function mostrarMensajeError(mensaje) {
  $(".alert-success, .alert-danger").remove();
  const alertHTML = `
        <div class="alert alert-danger alert-dismissible fade show mt-3" role="alert">
            <strong>¡Error!</strong> ${mensaje}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
  $("#form-guardar-silabo .card-footer").prepend(alertHTML);
  // No se cierra automáticamente
}

/**
 * Función para resetear el estado del botón de guardar
 */
function resetearEstadoBotonGuardar() {
  $("#spinnerGuardar").addClass("d-none");
  $("#guardarFormularioBtn").prop("disabled", false);
}

/**
 * Función para resaltar campos rellenados en el formulario de guardar
 * (Llamada desde silabo_ia.js después de autocompletar)
 */
function highlightFilledFields() {
  $(
    "#form-guardar-silabo .form-control, #form-guardar-silabo .form-select",
  ).each(function () {
    const value = $(this).val();
    const hasValue = Array.isArray(value)
      ? value.length > 0
      : value && String(value).trim() !== "";

    if (hasValue) {
      if (!$(this).hasClass("border-danger")) {
        $(this).addClass("border-success");
      }
    } else {
      $(this).removeClass("border-success");
    }
  });

  // Manejo especial para checkboxes (considerarlos 'rellenos' si al menos uno está marcado)
  const checkboxGroups = {};
  $('#form-guardar-silabo input[type="checkbox"]').each(function () {
    const name = $(this).attr("name");
    if (!checkboxGroups[name]) {
      checkboxGroups[name] = {
        selector: `input[name="${name}"]`,
        checked: false,
      };
    }
    if ($(this).is(":checked")) {
      checkboxGroups[name].checked = true;
    }
  });

  for (const name in checkboxGroups) {
    const group = checkboxGroups[name];
    const $checkboxes = $(group.selector);
    const $container = $checkboxes.closest(".form-check-group-container");

    if (group.checked) {
      if (!$container.hasClass("border-danger")) {
        $container.addClass("border-success-group");
        $container.removeClass("border-danger-group");
      }
    } else {
      $container.removeClass("border-success-group");
    }
  }
}

/**
 * Función para inicializar el manejo de cambios en los campos del formulario de GUARDAR
 */
function initializeFieldChangeHandling() {
  const fields = document.querySelectorAll(
    "#form-guardar-silabo .form-control, #form-guardar-silabo .form-select",
  );

  function hasContent(value) {
    if (Array.isArray(value)) return value.length > 0;
    return value && String(value).trim() !== "";
  }

  function handleInputChange(event) {
    const field = event.target;
    const value = $(field).val();

    $(field).next(".error-message").remove(); // Eliminar mensaje de error específico

    if (hasContent(value)) {
      field.classList.add("border-success");
      field.classList.remove("border-danger");
    } else {
      field.classList.remove("border-success");
    }
  }

  // Event listener para checkboxes (maneja el grupo)
  $('#form-guardar-silabo input[type="checkbox"]').on("change", function () {
    const name = $(this).attr("name");
    const $checkboxes = $(`input[name="${name}"]`);
    const $container = $checkboxes.closest(".form-check-group-container");
    const isAnyChecked = $checkboxes.is(":checked");

    $container.find(".error-message").remove(); // Remover error del grupo

    if (isAnyChecked) {
      $container.addClass("border-success-group");
      $container.removeClass("border-danger-group");
    } else {
      $container.removeClass("border-success-group");
    }
  });

  fields.forEach((field) => {
    const eventType =
      field.tagName === "SELECT" ||
      field.type === "date" ||
      field.type === "checkbox" ||
      field.type === "radio"
        ? "change"
        : "input";
    field.addEventListener(eventType, handleInputChange);

    if (field.type !== "checkbox") {
      const initialValue = $(field).val();
      if (hasContent(initialValue)) {
        if (!field.classList.contains("border-danger")) {
          field.classList.add("border-success");
        }
      }
    }
  });

  highlightFilledFields();
}

/**
 * Función auxiliar para obtener el valor de una cookie (necesaria para CSRF)
 * @param {string} name - Nombre de la cookie
 * @returns {string|null} Valor de la cookie o null si no se encuentra
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
