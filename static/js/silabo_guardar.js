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

  // Log FormData para depuración (opcional)
  // console.log("FormData a enviar para guardar:");
  // for (var pair of formData.entries()) {
  //     console.log(pair[0]+ ': '+ pair[1]);
  // }

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
        mostrarMensajeExito("Sílabo guardado con éxito. Redirigiendo...");
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
  // Se agrupan por 'name'
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
    // Asumiendo que los checkboxes están dentro de un contenedor que se puede marcar
    const $container = $checkboxes.closest(".form-check-group-container"); // Necesitarás añadir esta clase a los divs que envuelven grupos de checkboxes

    if (group.checked) {
      if (!$container.hasClass("border-danger")) {
        // Usa el contenedor para el borde
        $container.addClass("border-success-group"); // Clase CSS personalizada para borde de grupo
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
      // No añadir borde rojo aquí, eso lo hace la validación al intentar guardar
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
      field.type === "checkbox" || // Aunque manejamos grupo arriba, esto no hace daño
      field.type === "radio"
        ? "change"
        : "input";
    field.addEventListener(eventType, handleInputChange);

    // Estado inicial (excepto checkboxes que se manejan al cargar con highlightFilledFields)
    if (field.type !== "checkbox") {
      const initialValue = $(field).val();
      if (hasContent(initialValue)) {
        if (!field.classList.contains("border-danger")) {
          field.classList.add("border-success");
        }
      }
    }
  });

  // Llama a highlight para el estado inicial de los checkboxes también
  highlightFilledFields();
}

/**
 * Función para validar campos obligatorios antes de enviar el formulario de GUARDAR
 * @returns {boolean} true si todos los campos obligatorios están completados, false en caso contrario
 */
function validarCamposObligatorios() {
  const camposObligatorios = [
    "id_encuentros",
    "id_fecha",
    "id_unidad",
    "id_nombre_de_la_unidad",
    "id_contenido_tematico",
    "id_objetivo_conceptual",
    "id_objetivo_procedimental",
    "id_objetivo_actitudinal",
    "id_tipo_primer_momento",
    "id_detalle_primer_momento",
    "id_tiempo_primer_momento",
    "id_recursos_primer_momento",
    "id_tipo_segundo_momento_claseteoria",
    "id_clase_teorica",
    "id_tipo_segundo_momento_practica",
    "id_clase_practica",
    "id_tiempo_segundo_momento_teorica",
    "id_tiempo_segundo_momento_practica",
    "id_recursos_segundo_momento",
    // "id_tipo_tercer_momento", // Checkbox multiple, validación diferente
    "id_detalle_tercer_momento",
    "id_tiempo_tercer_momento",
    "id_recursos_tercer_momento",
    // "id_eje_transversal", // Checkbox multiple, validación diferente
    "id_detalle_eje_transversal",
    "id_actividad_aprendizaje",
    // "id_tecnica_evaluacion", // Checkbox multiple, validación diferente
    // "id_tipo_evaluacion", // Checkbox multiple, validación diferente
    "id_periodo_tiempo_programado",
    "id_tiempo_minutos",
    // "id_agente_evaluador", // Checkbox multiple, validación diferente
    "id_instrumento_evaluacion",
    "id_criterios_evaluacion",
    "id_puntaje",
  ];
  // IDs de grupos de Checkboxes obligatorios (usar el 'name' del input)
  const checkboxGroupsObligatorios = [
    "tipo_tercer_momento",
    "eje_transversal",
    "tecnica_evaluacion",
    "tipo_evaluacion",
    "agente_evaluador",
  ];

  let formValido = true;
  let primerElementoConError = null;

  // Resetear errores visuales
  $("#form-guardar-silabo .error-message").remove();
  $("#form-guardar-silabo .border-danger").removeClass("border-danger");
  $("#form-guardar-silabo .border-success").removeClass("border-success");
  $("#form-guardar-silabo .border-danger-group").removeClass(
    "border-danger-group",
  );
  $("#form-guardar-silabo .border-success-group").removeClass(
    "border-success-group",
  );
  // Añadir area general de errores si no existe
  if (
    $("#general-error-area").length === 0 &&
    $("#form-guardar-silabo .card-footer").length > 0
  ) {
    $("#form-guardar-silabo .card-footer").prepend(
      '<div id="general-error-area"></div>',
    );
  } else if ($("#general-error-area").length === 0) {
    // Fallback si no hay card-footer
    $("#form-guardar-silabo").prepend('<div id="general-error-area"></div>');
  }
  $("#general-error-area").empty(); // Limpiar errores generales previos

  // Validar campos input/select/textarea
  camposObligatorios.forEach(function (campoId) {
    const campo = $("#" + campoId);
    if (campo.length === 0) {
      console.warn("Campo obligatorio no encontrado:", campoId);
      return;
    }
    const valor = campo.val();
    const estaVacio = Array.isArray(valor)
      ? valor.length === 0
      : !valor || String(valor).trim() === "";

    if (estaVacio) {
      formValido = false;
      campo.addClass("border-danger").removeClass("border-success");
      const errorMsg = $(
        '<div class="error-message text-danger small mt-1">Este campo es obligatorio</div>',
      );
      if (campo.next(".error-message").length === 0) campo.after(errorMsg);
      if (!primerElementoConError) primerElementoConError = campo;
    } else {
      campo.addClass("border-success").removeClass("border-danger");
    }
  });

  // Validar grupos de checkboxes obligatorios
  checkboxGroupsObligatorios.forEach(function (groupName) {
    const $checkboxes = $(`input[name="${groupName}"]`);
    if ($checkboxes.length === 0) {
      console.warn("Grupo de checkboxes obligatorio no encontrado:", groupName);
      return; // Saltar si no se encuentran checkboxes con ese nombre
    }
    const $container = $checkboxes.closest(".form-check-group-container"); // Necesitas este contenedor
    const isAnyChecked = $checkboxes.is(":checked");

    if (!isAnyChecked) {
      formValido = false;
      $container
        .addClass("border-danger-group")
        .removeClass("border-success-group");
      // Añadir mensaje de error después del contenedor o dentro de él
      const errorMsg = $(
        '<div class="error-message text-danger small mt-1">Debe seleccionar al menos una opción.</div>',
      );
      // Poner el mensaje después del contenedor para no interferir con el layout interno
      if ($container.next(".error-message").length === 0)
        $container.after(errorMsg);

      if (!primerElementoConError) primerElementoConError = $container; // Apuntar al contenedor para scroll
    } else {
      $container
        .addClass("border-success-group")
        .removeClass("border-danger-group");
    }
  });

  // Scroll y mensaje general si hay errores
  if (!formValido) {
    if (primerElementoConError && primerElementoConError.length > 0 && typeof primerElementoConError.offset === 'function') {
      $("html, body").animate(
        {
          scrollTop: primerElementoConError.offset().top - 100,
        },
        500,
      );
    }
    mostrarMensajeError(
      "Por favor, complete todos los campos obligatorios marcados en rojo.",
    );
  }

  return formValido;
}

/**
 * Función para resaltar campos con errores reportados por el backend en el formulario de GUARDAR
 * @param {Object} errores - Objeto con los errores del backend {nombre_campo: ["mensaje", ...], ...}
 */
function resaltarCamposConError(errores) {
  const mapeoNombreAId = {
    codigo: "id_codigo",
    encuentros: "id_encuentros",
    fecha: "id_fecha",
    unidad: "id_unidad",
    nombre_de_la_unidad: "id_nombre_de_la_unidad",
    contenido_tematico: "id_contenido_tematico",
    objetivo_conceptual: "id_objetivo_conceptual",
    objetivo_procedimental: "id_objetivo_procedimental",
    objetivo_actitudinal: "id_objetivo_actitudinal",
    tipo_primer_momento: "id_tipo_primer_momento",
    detalle_primer_momento: "id_detalle_primer_momento",
    tiempo_primer_momento: "id_tiempo_primer_momento",
    recursos_primer_momento: "id_recursos_primer_momento",
    tipo_segundo_momento_claseteoria: "id_tipo_segundo_momento_claseteoria",
    clase_teorica: "id_clase_teorica",
    tipo_segundo_momento_practica: "id_tipo_segundo_momento_practica",
    clase_practica: "id_clase_practica",
    tiempo_segundo_momento_teorica: "id_tiempo_segundo_momento_teorica",
    tiempo_segundo_momento_practica: "id_tiempo_segundo_momento_practica",
    recursos_segundo_momento: "id_recursos_segundo_momento",
    tipo_tercer_momento: "id_tipo_tercer_momento", // Apunta al *grupo* de checkboxes
    detalle_tercer_momento: "id_detalle_tercer_momento",
    tiempo_tercer_momento: "id_tiempo_tercer_momento",
    recursos_tercer_momento: "id_recursos_tercer_momento",
    eje_transversal: "id_eje_transversal", // Apunta al *grupo* de checkboxes
    detalle_eje_transversal: "id_detalle_eje_transversal",
    actividad_aprendizaje: "id_actividad_aprendizaje",
    tecnica_evaluacion: "id_tecnica_evaluacion", // Apunta al *grupo* de checkboxes
    tipo_evaluacion: "id_tipo_evaluacion", // Apunta al *grupo* de checkboxes
    periodo_tiempo_programado: "id_periodo_tiempo_programado",
    tiempo_minutos: "id_tiempo_minutos",
    agente_evaluador: "id_agente_evaluador", // Apunta al *grupo* de checkboxes
    instrumento_evaluacion: "id_instrumento_evaluacion",
    criterios_evaluacion: "id_criterios_evaluacion",
    puntaje: "id_puntaje",
    __all__: "general-error-area", // Para errores generales del formulario
  };
  // Nombres de campo que corresponden a grupos de checkboxes
  const checkboxGroupFields = [
    "tipo_tercer_momento",
    "eje_transversal",
    "tecnica_evaluacion",
    "tipo_evaluacion",
    "agente_evaluador",
  ];

  // Resetear errores visuales previos del backend
  $("#form-guardar-silabo .error-message").remove();
  $("#form-guardar-silabo .border-danger").removeClass("border-danger");
  $("#form-guardar-silabo .border-danger-group").removeClass(
    "border-danger-group",
  );
  $("#general-error-area").empty(); // Limpiar errores generales previos

  let primerElementoConError = null;

  for (const [nombreCampo, mensajeErrorArray] of Object.entries(errores)) {
    const mensajeError = Array.isArray(mensajeErrorArray)
      ? mensajeErrorArray.join(" ")
      : mensajeErrorArray;
    const campoIdOrName = mapeoNombreAId[nombreCampo]; // Puede ser ID o nombre de grupo

    if (!campoIdOrName) {
      console.warn(
        "No se encontró mapeo para el campo con error:",
        nombreCampo,
      );
      // Mostrar en área general si no es '__all__' (que ya se maneja)
      if (nombreCampo !== "__all__") {
        $("#general-error-area").append(
          `<div class="text-danger small mt-1">${nombreCampo}: ${mensajeError}</div>`,
        );
        if (!primerElementoConError)
          primerElementoConError = $("#general-error-area");
      }
      continue;
    }

    // Manejar error general __all__
    if (campoIdOrName === "general-error-area") {
      // Usar mostrarMensajeError para consistencia
      mostrarMensajeError(mensajeError);
      if (!primerElementoConError)
        primerElementoConError = $("#" + campoIdOrName);
      continue; // Pasar al siguiente error
    }

    // Determinar si es un grupo de checkboxes o un campo normal
    const isCheckboxGroup = checkboxGroupFields.includes(nombreCampo);

    if (isCheckboxGroup) {
      // Usamos el *nombre* del campo para encontrar los checkboxes
      const groupName = nombreCampo; // El nombre del campo es el 'name' de los checkboxes
      const $checkboxes = $(`input[name="${groupName}"]`);
      if ($checkboxes.length > 0) {
        const $container = $checkboxes.closest(".form-check-group-container");
        $container
          .addClass("border-danger-group")
          .removeClass("border-success-group");
        // Añadir mensaje de error después del contenedor
        const errorMsg = $(
          '<div class="error-message text-danger small mt-1">' +
            mensajeError +
            "</div>",
        );
        if ($container.next(".error-message").length === 0)
          $container.after(errorMsg);

        if (!primerElementoConError) primerElementoConError = $container;
      } else {
        console.warn(
          "Grupo de checkboxes mapeado no encontrado en el DOM:",
          groupName,
        );
      }
    } else {
      // Es un campo normal (input, select, textarea)
      const campo = $("#" + campoIdOrName); // Usamos el ID
      if (campo.length === 0) {
        console.warn(
          "Campo mapeado no encontrado en el DOM:",
          campoIdOrName,
          "para error en",
          nombreCampo,
        );
        continue;
      }

      campo.addClass("border-danger").removeClass("border-success");
      const errorMsg = $(
        '<div class="error-message text-danger small mt-1">' +
          mensajeError +
          "</div>",
      );
      if (campo.next(".error-message").length === 0) campo.after(errorMsg);

      if (!primerElementoConError) primerElementoConError = campo;
    }
  }

  // Scroll al primer error detectado
  if (primerElementoConError) {
    $("html, body").animate(
      {
        scrollTop: primerElementoConError.offset().top - 100,
      },
      500,
    );
  }
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

// ----- CSS Sugerido para los bordes de grupo -----
/*
En tu archivo CSS, añade algo como:

.form-check-group-container {
    padding: 10px;
    border: 1px solid #dee2e6; // Borde por defecto similar a los inputs
    border-radius: 0.25rem; // Opcional: redondear esquinas
    margin-bottom: 1rem; // Espacio debajo del grupo
    transition: border-color 0.15s ease-in-out;
}

.form-check-group-container.border-success-group {
    border-color: #198754 !important; // Verde éxito
}

.form-check-group-container.border-danger-group {
    border-color: #dc3545 !important; // Rojo peligro
}

.form-check-group-container + .error-message {
    // Asegura que el mensaje de error para el grupo aparezca debajo del contenedor
    display: block;
}

*/
