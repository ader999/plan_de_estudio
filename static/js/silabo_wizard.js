// plan_de_estudio/static/js/silabo_wizard.js
/**
 * silabo_wizard.js
 * Flujo paso a paso (6 pasos) Mobile-First para el formulario de sílabo
 * con persistencia local en el navegador (localStorage) hasta su envío final.
 */

(function (window, $) {
  "use strict";

  const TOTAL_STEPS = 6;
  const DRAFT_VERSION = 1;
  const SAVE_DEBOUNCE_MS = 300;
  const CHECKBOX_LIMITS = {
    tipo_tercer_momento: 2,
    eje_transversal: 2,
    tecnica_evaluacion: 2,
    tipo_evaluacion: 2,
    agente_evaluador: 2,
  };

  // Campos que NO deben sobreescribirse desde un borrador (provienen del servidor)
  const IGNORED_DRAFT_NAMES = new Set([
    "csrfmiddlewaretoken",
    "codigo",
    "encuentros",
  ]);

  const STEP_META = {
    1: {
      title: "Base, IA y Objetivos",
      shortTitle: "Base",
      fields: [
        "id_fecha",
        "id_unidad",
        "id_nombre_de_la_unidad",
        "id_contenido_tematico",
        "id_objetivo_conceptual",
        "id_objetivo_procedimental",
        "id_objetivo_actitudinal",
      ],
      checkboxGroups: [],
    },
    2: {
      title: "1er Momento (Entrada)",
      shortTitle: "Entrada",
      fields: [
        "id_tipo_primer_momento",
        "id_detalle_primer_momento",
        "id_tiempo_primer_momento",
        "id_recursos_primer_momento",
      ],
      checkboxGroups: [],
    },
    3: {
      title: "2do Momento (Desarrollo)",
      shortTitle: "Desarrollo",
      fields: [
        "id_tipo_segundo_momento_claseteoria",
        "id_clase_teorica",
        "id_tipo_segundo_momento_practica",
        "id_clase_practica",
        "id_tiempo_segundo_momento_teorica",
        "id_tiempo_segundo_momento_practica",
        "id_recursos_segundo_momento",
      ],
      checkboxGroups: [],
    },
    4: {
      title: "3er Momento y Ejes",
      shortTitle: "Cierre",
      fields: [
        "id_detalle_tercer_momento",
        "id_tiempo_tercer_momento",
        "id_recursos_tercer_momento",
        "id_detalle_eje_transversal",
      ],
      checkboxGroups: ["tipo_tercer_momento", "eje_transversal"],
    },
    5: {
      title: "Evaluación Dinámica",
      shortTitle: "Evaluación",
      fields: [
        "id_actividad_aprendizaje",
        "id_periodo_tiempo_programado",
        "id_tiempo_minutos",
        "id_instrumento_evaluacion",
        "id_criterios_evaluacion",
        "id_puntaje",
      ],
      checkboxGroups: [
        "tecnica_evaluacion",
        "tipo_evaluacion",
        "agente_evaluador",
      ],
    },
    6: {
      title: "Revisión y Guardado",
      shortTitle: "Guardar",
      fields: [],
      checkboxGroups: [],
    },
  };

  let currentStep = 1;
  let saveTimer = null;
  let isRestoring = false;
  let draftKey = null;

  function buildDraftKey() {
    const $root = $("#silabo-wizard-root");
    const usuario = ($root.data("usuario") || "anon").toString().trim();
    const asignacionId = ($root.data("asignacion-id") || "0").toString().trim();
    const encuentro = ($root.data("encuentro") || "0").toString().trim();
    return `planeauml_silabo_draft_v${DRAFT_VERSION}_${usuario}_${asignacionId}_${encuentro}`;
  }

  function hasNonEmptyValue(val) {
    if (Array.isArray(val)) return val.length > 0;
    return val !== null && val !== undefined && String(val).trim() !== "";
  }

  function getStepRequirements(step) {
    const meta = STEP_META[step];
    if (!meta) return { fields: [], checkboxGroups: [] };
    if (step === 5 && $("#sin_evaluacion_dinamica").is(":checked")) {
      return { fields: [], checkboxGroups: [] };
    }
    return {
      fields: meta.fields.slice(),
      checkboxGroups: meta.checkboxGroups.slice(),
    };
  }

  function evaluateStepStatus(step) {
    if (step === 6) return { status: "review", completed: 0, total: 0 };

    if (step === 5 && $("#sin_evaluacion_dinamica").is(":checked")) {
      return { status: "complete", completed: 1, total: 1, skippedEval: true };
    }

    const req = getStepRequirements(step);
    const total = req.fields.length + req.checkboxGroups.length;
    let completed = 0;

    req.fields.forEach((id) => {
      const $el = $("#" + id);
      if ($el.length && hasNonEmptyValue($el.val())) {
        completed++;
      }
    });

    req.checkboxGroups.forEach((name) => {
      if ($(`input[name="${name}"]:checked`).length > 0) {
        completed++;
      }
    });

    let status = "empty";
    if (completed === total && total > 0) {
      status = "complete";
    } else if (completed > 0) {
      status = "partial";
    }

    return { status, completed, total, skippedEval: false };
  }

  function updateStepBadges() {
    for (let step = 1; step <= 5; step++) {
      const info = evaluateStepStatus(step);
      const $tab = $(`.wizard-step-tab[data-step="${step}"]`);
      $tab.removeClass("is-complete is-partial is-empty");
      $tab.addClass(`is-${info.status}`);

      const $dot = $tab.find(".wizard-tab-status");
      if (info.status === "complete") {
        $dot.html('<i class="fas fa-check"></i>');
      } else if (info.status === "partial") {
        $dot.text(`${info.completed}/${info.total}`);
      } else {
        $dot.text(String(step));
      }
    }

    renderReviewChecklist();
  }

  function renderReviewChecklist() {
    const $list = $("#wizard-review-list");
    if ($list.length === 0) return;

    const itemsHtml = [];
    let allComplete = true;

    for (let step = 1; step <= 5; step++) {
      const meta = STEP_META[step];
      const info = evaluateStepStatus(step);
      let badgeClass = "bg-secondary";
      let badgeText = "Pendiente";
      let iconClass = "fa-circle text-muted";

      if (info.status === "complete") {
        badgeClass = "bg-success";
        badgeText = info.skippedEval ? "Omitida (sin evaluación)" : "Completo";
        iconClass = "fa-check-circle text-success";
      } else if (info.status === "partial") {
        allComplete = false;
        badgeClass = "bg-warning text-dark";
        badgeText = `${info.completed} de ${info.total} campos`;
        iconClass = "fa-exclamation-circle text-warning";
      } else {
        allComplete = false;
        badgeClass = "bg-danger";
        badgeText = `0 de ${info.total} campos`;
        iconClass = "fa-times-circle text-danger";
      }

      itemsHtml.push(`
        <button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center wizard-review-item" data-go-step="${step}">
          <div class="d-flex align-items-center gap-2 text-start">
            <i class="fas ${iconClass} fa-lg"></i>
            <div>
              <div class="fw-semibold">${step}. ${meta.title}</div>
              <small class="text-muted">Toca para revisar o editar</small>
            </div>
          </div>
          <span class="badge rounded-pill ${badgeClass}">${badgeText}</span>
        </button>
      `);
    }

    $list.html(itemsHtml.join(""));

    const $summaryAlert = $("#wizard-review-status-alert");
    if ($summaryAlert.length) {
      if (allComplete) {
        $summaryAlert
          .removeClass("alert-warning")
          .addClass("alert-success")
          .html(
            '<i class="fas fa-check-circle me-2"></i><strong>¡Todo listo!</strong> Completaste todos los pasos requeridos. Puedes guardar tu sílabo.',
          );
      } else {
        $summaryAlert
          .removeClass("alert-success")
          .addClass("alert-warning")
          .html(
            '<i class="fas fa-info-circle me-2"></i>Aún hay pasos con campos pendientes. Toca cualquiera abajo para ir directo a completarlo.',
          );
      }
    }
  }

  function syncReviewMetrics() {
    const tiempoTotal = $("#tiempo_total").val() || "0";
    $("#wizard-header-total-time").text(`${tiempoTotal} min`);
    $("#wizard-review-total-time").text(`${tiempoTotal} min`);

    $("#wizard-review-corte-1").text($("#acumulado_corte_1").text() || "0");
    $("#wizard-review-corte-2").text($("#acumulado_corte_2").text() || "0");
    $("#wizard-review-corte-3").text($("#acumulado_corte_3").text() || "0");
    $("#wizard-review-corte-total").text($("#acumulado_total").text() || "0");
  }

  function goToStep(step, options) {
    const opts = Object.assign({ scroll: true, save: true }, options);
    const targetStep = Math.max(1, Math.min(TOTAL_STEPS, Number(step) || 1));
    currentStep = targetStep;

    // Mostrar solo el panel del paso activo
    $(".wizard-step").addClass("d-none").removeClass("is-active");
    $(`.wizard-step[data-step="${targetStep}"]`)
      .removeClass("d-none")
      .addClass("is-active");

    // El generador de IA vive solo en el Paso 1
    if (targetStep === 1) {
      $("#wizard-ai-panel").removeClass("d-none");
    } else {
      $("#wizard-ai-panel").addClass("d-none");
    }

    // Actualizar pestañas superiores
    $(".wizard-step-tab").removeClass("active");
    const $activeTab = $(`.wizard-step-tab[data-step="${targetStep}"]`).addClass(
      "active",
    );
    const $tabsContainer = $activeTab.closest(".wizard-tabs-scroll");
    if ($activeTab.length && $tabsContainer.length) {
      const container = $tabsContainer[0];
      const tab = $activeTab[0];
      const targetLeft = Math.max(
        0,
        tab.offsetLeft - container.clientWidth / 2 + tab.offsetWidth / 2,
      );
      try {
        if (typeof container.scrollTo === "function") {
          container.scrollTo({ left: targetLeft, behavior: "smooth" });
        } else {
          container.scrollLeft = targetLeft;
        }
      } catch (_) {
        container.scrollLeft = targetLeft;
      }
    }

    // Actualizar barra de progreso y textos de cabecera
    const percent = Math.round((targetStep / TOTAL_STEPS) * 100);
    $("#wizard-progress-bar")
      .css("width", `${percent}%`)
      .attr("aria-valuenow", percent);
    $("#wizard-step-counter").text(`Paso ${targetStep} de ${TOTAL_STEPS}`);
    $("#wizard-step-title").text(STEP_META[targetStep].title);

    // Botones de navegación inferior
    $("#wizardPrevBtn").prop("disabled", targetStep === 1);
    if (targetStep === TOTAL_STEPS) {
      $("#wizardNextBtn").addClass("d-none");
      $("#guardarFormularioBtn").removeClass("d-none");
    } else {
      $("#wizardNextBtn").removeClass("d-none");
      $("#guardarFormularioBtn").addClass("d-none");
    }

    updateStepBadges();
    syncReviewMetrics();
    autoResizeVisibleTextareas();

    if (opts.save && !isRestoring) {
      scheduleSaveDraft();
    }

    if (opts.scroll) {
      $("#silabo-wizard-root .card.shadow-lg").scrollTop(0);
      const $header = $("#wizard-sticky-header");
      const navbarHeight = $("#main-navbar").outerHeight() || 72;
      const targetTop = $header.length
        ? Math.max(0, $header.offset().top - navbarHeight - 12)
        : 0;
      $("html, body").animate({ scrollTop: targetTop }, 220);
    }
  }

  function findStepForElement($element) {
    if (!$element || $element.length === 0) return null;
    const $stepEl = $element.closest(".wizard-step");
    if ($stepEl.length) {
      return Number($stepEl.data("step")) || null;
    }
    return null;
  }

  function goToStepForElement($element) {
    const step = findStepForElement($element);
    if (step) {
      goToStep(step, { scroll: false, save: false });
    }
    return step;
  }

  function setAutosaveStatus(text, stateClass) {
    const $badge = $("#wizard-autosave-status");
    if ($badge.length === 0) return;
    $badge
      .removeClass("text-muted text-success text-warning")
      .addClass(stateClass || "text-muted")
      .html(text);
  }

  function collectDraftData() {
    const fields = {};
    const formEl = document.getElementById("form-guardar-silabo");
    if (!formEl) return null;

    $(formEl)
      .find("input, select, textarea")
      .each(function () {
        const name = $(this).attr("name");
        if (!name || IGNORED_DRAFT_NAMES.has(name)) return;

        if (this.type === "checkbox") {
          if (this.id === "sin_evaluacion_dinamica") return;
          if (!Array.isArray(fields[name])) {
            fields[name] = [];
          }
          if (this.checked) {
            fields[name].push($(this).val());
          }
        } else if (this.type === "radio") {
          if (this.checked) {
            fields[name] = $(this).val();
          }
        } else {
          fields[name] = $(this).val();
        }
      });

    return {
      version: DRAFT_VERSION,
      currentStep: currentStep,
      updatedAt: new Date().toISOString(),
      sinEvaluacionDinamica: $("#sin_evaluacion_dinamica").is(":checked"),
      fields: fields,
    };
  }

  function saveDraftNow() {
    if (isRestoring || !draftKey) return;
    try {
      const payload = collectDraftData();
      if (!payload) return;
      window.localStorage.setItem(draftKey, JSON.stringify(payload));
      setAutosaveStatus(
        '<i class="fas fa-check-circle me-1"></i>Guardado en este dispositivo',
        "text-success",
      );
    } catch (err) {
      console.warn("No se pudo guardar el borrador local:", err);
      setAutosaveStatus(
        '<i class="fas fa-exclamation-circle me-1"></i>Sin almacenamiento local',
        "text-warning",
      );
    }
  }

  function scheduleSaveDraft() {
    if (isRestoring) return;
    setAutosaveStatus(
      '<i class="fas fa-sync fa-spin me-1"></i>Guardando avance...',
      "text-muted",
    );
    if (saveTimer) {
      clearTimeout(saveTimer);
    }
    saveTimer = setTimeout(saveDraftNow, SAVE_DEBOUNCE_MS);
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return "hace unos instantes";
    const diffMs = Date.now() - new Date(isoString).getTime();
    if (isNaN(diffMs) || diffMs < 60000) return "hace menos de 1 min";
    const mins = Math.floor(diffMs / 60000);
    if (mins < 60) return `hace ${mins} min`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `hace ${hrs} h`;
    const days = Math.floor(hrs / 24);
    return `hace ${days} día${days > 1 ? "s" : ""}`;
  }

  function restoreDraftIfAvailable() {
    if (!draftKey) return false;
    let raw = null;
    try {
      raw = window.localStorage.getItem(draftKey);
    } catch (_) {
      return false;
    }
    if (!raw) return false;

    let draft = null;
    try {
      draft = JSON.parse(raw);
    } catch (_) {
      return false;
    }

    if (!draft || typeof draft !== "object" || !draft.fields) return false;

    isRestoring = true;
    try {
      // Restaurar switch de evaluación dinámica primero
      $("#sin_evaluacion_dinamica").prop(
        "checked",
        Boolean(draft.sinEvaluacionDinamica),
      );
      if (typeof window.toggleEvaluacionDinamica === "function") {
        window.toggleEvaluacionDinamica();
      }

      // Restaurar valores de campos
      Object.entries(draft.fields).forEach(([name, value]) => {
        if (IGNORED_DRAFT_NAMES.has(name)) return;
        const $targets = $(`#form-guardar-silabo [name="${name}"]`);
        if ($targets.length === 0) return;

        const firstType = $targets.first().attr("type");
        if (firstType === "checkbox") {
          const arr = Array.isArray(value) ? value : [value];
          $targets.prop("checked", false);
          arr.forEach((v) => {
            $targets.filter(`[value="${CSS.escape(String(v))}"]`).prop("checked", true);
          });
        } else if (firstType === "radio") {
          $targets.prop("checked", false);
          if (value !== undefined && value !== null) {
            $targets.filter(`[value="${CSS.escape(String(value))}"]`).prop("checked", true);
          }
        } else {
          $targets.val(value || "");
        }
      });

      // Actualizar controles dependientes
      syncAllChipGroups();
      syncAllTimePresetButtons();

      if (typeof window.calcularTiempoTotal === "function") {
        window.calcularTiempoTotal();
      }
      $("#id_puntaje, #id_periodo_tiempo_programado").trigger("change");

      if (typeof window.highlightFilledFields === "function") {
        window.highlightFilledFields();
      }

      const restoredStep = Math.max(
        1,
        Math.min(TOTAL_STEPS, Number(draft.currentStep) || 1),
      );
      goToStep(restoredStep, { scroll: false, save: false });

      // Mostrar banner de borrador restaurado
      $("#draft-restored-time").text(formatRelativeTime(draft.updatedAt));
      $("#draft-restored-banner").removeClass("d-none");
      setAutosaveStatus(
        '<i class="fas fa-check-circle me-1"></i>Borrador restaurado',
        "text-success",
      );
    } finally {
      isRestoring = false;
    }

    return true;
  }

  function clearDraft() {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    if (!draftKey) return;
    try {
      window.localStorage.removeItem(draftKey);
    } catch (_) {
      // Ignorar si almacenamiento bloqueado
    }
  }

  function resetDraftAndForm() {
    clearDraft();
    isRestoring = true;
    try {
      const formEl = document.getElementById("form-guardar-silabo");
      if (formEl) {
        $(formEl)
          .find("input, select, textarea")
          .each(function () {
            const name = $(this).attr("name");
            if (!name || IGNORED_DRAFT_NAMES.has(name)) return;
            if (this.type === "checkbox" || this.type === "radio") {
              $(this).prop("checked", false);
            } else {
              $(this).val("");
            }
          });
      }
      $("#sin_evaluacion_dinamica").prop("checked", false);
      if (typeof window.toggleEvaluacionDinamica === "function") {
        window.toggleEvaluacionDinamica();
      }
      $("#form-guardar-silabo .error-message").remove();
      $(
        "#form-guardar-silabo .border-danger, #form-guardar-silabo .border-success",
      ).removeClass("border-danger border-success");
      $(
        "#form-guardar-silabo .border-danger-group, #form-guardar-silabo .border-success-group",
      ).removeClass("border-danger-group border-success-group");

      syncAllChipGroups();
      syncAllTimePresetButtons();
      if (typeof window.calcularTiempoTotal === "function") {
        window.calcularTiempoTotal();
      }
      $("#id_puntaje, #id_periodo_tiempo_programado").trigger("change");
      $("#draft-restored-banner").addClass("d-none");
      goToStep(1, { scroll: true, save: false });
      setAutosaveStatus(
        '<i class="fas fa-eraser me-1"></i>Borrador reiniciado',
        "text-muted",
      );
    } finally {
      isRestoring = false;
    }
  }

  // --- Chips táctiles y límite de selección ---

  function syncChipGroupState(groupName) {
    const limit = CHECKBOX_LIMITS[groupName] || 2;
    const $all = $(`input[name="${groupName}"]`);
    const checkedCount = $all.filter(":checked").length;

    if (checkedCount >= limit) {
      $all.not(":checked").prop("disabled", true);
    } else {
      $all.prop("disabled", false);
    }

    $all.each(function () {
      const $label = $(this).closest("label");
      $label.toggleClass("is-checked", this.checked);
      $label.toggleClass("is-disabled", this.disabled && !this.checked);
    });

    const $counter = $(`.chip-counter[data-group="${groupName}"]`);
    if ($counter.length) {
      $counter.text(`${checkedCount} / ${limit}`);
      $counter
        .toggleClass("bg-success", checkedCount > 0)
        .toggleClass("bg-secondary", checkedCount === 0);
    }
  }

  function syncAllChipGroups() {
    Object.keys(CHECKBOX_LIMITS).forEach(syncChipGroupState);
  }

  // --- Presets de tiempo ---

  function syncTimePresetButtonsForInput($input) {
    const id = $input.attr("id");
    if (!id) return;
    const val = String($input.val() || "").trim();
    $(`.time-preset-row[data-target="#${id}"] .time-preset-btn`).each(
      function () {
        const presetVal = String($(this).data("minutes"));
        $(this).toggleClass("active btn-primary", val === presetVal);
        $(this).toggleClass("btn-outline-secondary", val !== presetVal);
      },
    );
  }

  function syncAllTimePresetButtons() {
    $(".time-preset-row").each(function () {
      const targetSel = $(this).data("target");
      const $input = $(targetSel);
      if ($input.length) {
        syncTimePresetButtonsForInput($input);
      }
    });
  }

  // --- Textareas auto-ajustables ---

  function autoResizeTextarea(el) {
    if (!el || el.tagName !== "TEXTAREA") return;
    el.style.height = "auto";
    const minH = 76;
    const maxH = 260;
    const nextH = Math.min(maxH, Math.max(minH, el.scrollHeight + 2));
    el.style.height = `${nextH}px`;
  }

  function autoResizeVisibleTextareas() {
    $(".wizard-step.is-active textarea").each(function () {
      autoResizeTextarea(this);
    });
  }

  function autoResizeAllTextareas() {
    $("#form-guardar-silabo textarea").each(function () {
      autoResizeTextarea(this);
    });
  }

  function initNumericInputsAndTextareas() {
    $("#form-guardar-silabo .tiempo_minutos, #id_puntaje").attr({
      inputmode: "numeric",
      pattern: "[0-9]*",
    });
    $("#form-guardar-silabo textarea").attr("rows", "2");
  }

  function bindEvents() {
    // Tabs superiores del wizard (navegación libre)
    $(document).on("click", ".wizard-step-tab", function () {
      const target = Number($(this).data("step"));
      goToStep(target);
    });

    // Clic desde la lista de revisión en el Paso 6
    $(document).on("click", ".wizard-review-item", function () {
      const target = Number($(this).data("go-step"));
      goToStep(target);
    });

    // Botón Anterior
    $("#wizardPrevBtn").on("click", function () {
      if (currentStep > 1) {
        goToStep(currentStep - 1);
      }
    });

    // Botón Siguiente (valida únicamente el paso actual)
    $("#wizardNextBtn").on("click", function () {
      if (typeof window.validarCamposObligatorios === "function") {
        const ok = window.validarCamposObligatorios(currentStep);
        if (!ok) {
          return;
        }
      }
      if (currentStep < TOTAL_STEPS) {
        goToStep(currentStep + 1);
      }
    });

    // Presets de tiempo
    $(document).on("click", ".time-preset-btn", function () {
      const $row = $(this).closest(".time-preset-row");
      const targetSel = $row.data("target");
      const minutes = $(this).data("minutes");
      const $input = $(targetSel);
      if ($input.length) {
        $input.val(minutes).trigger("input").trigger("change");
        syncTimePresetButtonsForInput($input);
      }
    });

    // Sincronizar chips al cambiar checkboxes
    Object.keys(CHECKBOX_LIMITS).forEach((groupName) => {
      $(document).on("change", `input[name="${groupName}"]`, function () {
        syncChipGroupState(groupName);
      });
    });

    // Auto-guardado local + métricas en vivo + auto-resize
    $(document).on(
      "input change",
      "#form-guardar-silabo input, #form-guardar-silabo select, #form-guardar-silabo textarea",
      function () {
        if (this.tagName === "TEXTAREA") {
          autoResizeTextarea(this);
        }
        if ($(this).hasClass("tiempo_minutos")) {
          syncTimePresetButtonsForInput($(this));
        }
        updateStepBadges();
        syncReviewMetrics();
        scheduleSaveDraft();
      },
    );

    $(document).on("change", "#sin_evaluacion_dinamica", function () {
      updateStepBadges();
      syncReviewMetrics();
      scheduleSaveDraft();
    });

    // Botón para descartar borrador local
    $("#btn-descartar-borrador").on("click", function () {
      if (
        window.confirm(
          "¿Deseas borrar el avance guardado en este dispositivo y empezar desde cero?",
        )
      ) {
        resetDraftAndForm();
      }
    });
  }

  function onAfterAiAutofill() {
    syncAllChipGroups();
    syncAllTimePresetButtons();
    autoResizeAllTextareas();
    updateStepBadges();
    syncReviewMetrics();
    saveDraftNow();
  }

  $(document).ready(function () {
    if ($("#silabo-wizard-root").length === 0) return;

    draftKey = buildDraftKey();
    initNumericInputsAndTextareas();
    bindEvents();
    syncAllChipGroups();
    syncAllTimePresetButtons();

    const restored = restoreDraftIfAvailable();
    if (!restored) {
      goToStep(1, { scroll: false, save: false });
    }
  });

  // API pública para silabo_validar.js, silabo_guardar.js y silabo_ia.js
  window.SilaboWizard = {
    getCurrentStep: () => currentStep,
    getStepRequirements: getStepRequirements,
    goToStep: goToStep,
    goToStepForElement: goToStepForElement,
    clearDraft: clearDraft,
    saveDraftNow: saveDraftNow,
    updateStepBadges: updateStepBadges,
    syncReviewMetrics: syncReviewMetrics,
    onAfterAiAutofill: onAfterAiAutofill,
  };
})(window, jQuery);
