/**
 * Archivo: silabo_actualizar_validar.js
 * Descripción: Validaciones del lado del cliente para el formulario de actualización de sílabo.
 */

$(document).ready(function() {
    // Interceptar el envío del formulario
    $('form').on('submit', function(e) {
        if (!validarCamposObligatorios()) {
            e.preventDefault(); // Detener el envío si la validación falla
            // El scroll y mensaje ya se manejan dentro de validarCamposObligatorios
        } else {
            // Si la validación pasa, mostrar estado de carga
            var $btn = $('#btn-actualizar');
            $btn.prop('disabled', true);
            $btn.html('<i class="fas fa-spinner fa-spin me-2"></i> Actualizando...');
        }
    });

    /**
     * Función para limitar el número de checkboxes que se pueden seleccionar en un grupo.
     * @param {string} checkboxName - El atributo 'name' del grupo de checkboxes.
     * @param {number} limit - El número máximo de selecciones permitidas.
     */
    function limitCheckboxSelection(checkboxName, limit) {
        // Adjuntar un evento 'change' a todos los checkboxes con el nombre especificado.
        $('input[name="' + checkboxName + '"]').on('change', function () {
            // Contar cuántos checkboxes de este grupo están actualmente seleccionados.
            const checkedCount = $('input[name="' + checkboxName + '"]:checked').length;

            // Obtener todos los checkboxes del grupo.
            const allCheckboxes = $('input[name="' + checkboxName + '"]');

            if (checkedCount >= limit) {
                // Si el número de seleccionados alcanza o supera el límite,
                // deshabilitar todos los que NO están seleccionados.
                allCheckboxes.not(':checked').prop('disabled', true);
            } else {
                // Si se deselecciona uno y el conteo es menor que el límite,
                // habilitar todos los checkboxes del grupo nuevamente.
                allCheckboxes.prop('disabled', false);
            }
        });

        // Ejecutar la lógica al cargar la página por si el formulario
        // viene con valores pre-seleccionados desde el servidor.
        $('input[name="' + checkboxName + '"]').first().trigger('change');
    }

    // Aplicar la función a los grupos de checkboxes deseados con un límite de 2.
    limitCheckboxSelection('tipo_tercer_momento', 2);
    limitCheckboxSelection('eje_transversal', 2);
    limitCheckboxSelection('tecnica_evaluacion', 2);
    limitCheckboxSelection('tipo_evaluacion', 2);
    limitCheckboxSelection('agente_evaluador', 2);
});

/**
 * Función para validar campos obligatorios antes de enviar el formulario
 * @returns {boolean} true si todos los campos obligatorios están completados, false en caso contrario
 */
function validarCamposObligatorios() {
  const camposObligatorios = [
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
  $(".error-message").remove();
  $(".border-danger").removeClass("border-danger");
  $(".border-success").removeClass("border-success");
  $(".border-danger-group").removeClass("border-danger-group");
  $(".border-success-group").removeClass("border-success-group");

  // Validar campos input/select/textarea
  camposObligatorios.forEach(function (campoId) {
    const campo = $("#" + campoId);
    if (campo.length === 0) {
      // Algunos campos pueden no existir o ser opcionales dependiendo de la lógica, 
      // pero si están en la lista se asume que deben estar.
      // Si es aceptable que falten, se puede ignorar.
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
      return; 
    }
    const $container = $checkboxes.closest(".form-check-group-container"); 
    // Si no encuentra el contenedor específico, intentamos con el padre directo o un card-body
    const $targetContainer = $container.length > 0 ? $container : $checkboxes.first().parent().parent();

    const isAnyChecked = $checkboxes.is(":checked");

    if (!isAnyChecked) {
      formValido = false;
      $targetContainer
        .addClass("border-danger-group")
        .removeClass("border-success-group");
      
      const errorMsg = $(
        '<div class="error-message text-danger small mt-1">Debe seleccionar al menos una opción.</div>',
      );
      
      if ($targetContainer.next(".error-message").length === 0)
        $targetContainer.after(errorMsg);

      if (!primerElementoConError) primerElementoConError = $targetContainer;
    } else {
      $targetContainer
        .addClass("border-success-group")
        .removeClass("border-danger-group");
    }
  });

  // Scroll y mensaje general si hay errores
  if (!formValido) {
    if (primerElementoConError && primerElementoConError.length > 0) {
      $("html, body").animate(
        {
          scrollTop: primerElementoConError.offset().top - 100,
        },
        500,
      );
    }
    // Puedes usar una alerta estándar o un modal si prefieres
    alert("Por favor, complete todos los campos obligatorios marcados en rojo.");
  }

  return formValido;
}
