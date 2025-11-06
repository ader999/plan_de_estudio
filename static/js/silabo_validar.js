// --- START OF FILE silabo_validar.js ---

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
    "id_detalle_tercer_momento",
    "id_tiempo_tercer_momento",
    "id_recursos_tercer_momento",
    "id_detalle_eje_transversal",
    "id_actividad_aprendizaje",
    "id_periodo_tiempo_programado",
    "id_tiempo_minutos",
    "id_instrumento_evaluacion",
    "id_criterios_evaluacion",
    "id_puntaje",
  ];
  // IDs de grupos de Checkboxes obligatorios (usar el 'name' del input)
  const checkboxGroupsObligatorios = [
    "tipo_tercer_momento",
    "eje_transversal",
    "tipo_evaluacion",
    "tecnica_evaluacion",
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
// --- END OF FILE silabo_validar.js ---