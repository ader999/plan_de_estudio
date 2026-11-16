// plan_de_estudio/static/js/guia_wizard.js
/**
 * guia_wizard.js
 * Flujo paso a paso (5 pasos) Mobile-First para el formulario de Guía de Estudio Independiente
 * con persistencia local en el navegador (localStorage) hasta su envío final.
 */

(function (window, $) {
  "use strict";

  const TOTAL_STEPS = 5;
  const DRAFT_VERSION = 1;
  const SAVE_DEBOUNCE_MS = 300;

  const GENERAL_FIELDS = ["fecha", "unidad", "nombre_de_la_unidad"];
  const ACTIVITY_FIELD_PREFIXES = [
    "tipo_objetivo",
    "objetivo_aprendizaje",
    "contenido_tematico",
    "actividad_aprendizaje",
    "tecnica_evaluacion",
    "tipo_evaluacion",
    "instrumento_evaluacion",
    "criterios_evaluacion",
    "tiempo_minutos",
    "recursos_didacticos",
    "periodo_tiempo_programado",
    "puntaje",
    "fecha_entrega",
  ];

  // Campos controlados por servidor que nunca deben sobreescribirse desde borrador local
  const IGNORED_DRAFT_NAMES = new Set([
    "csrfmiddlewaretoken",
    "asignacion_id",
    "silabo_id",
    "guia_id",
    "numero_encuentro",
  ]);

  const STEP_META = {
    1: { title: "Base, IA y Configuración", shortTitle: "Base e IA" },
    2: { title: "Primera Actividad (Obligatoria)", shortTitle: "Act. 1" },
    3: { title: "Segunda Actividad (Opcional)", shortTitle: "Act. 2" },
    4: { title: "Tercera y Cuarta Actividad (Opcionales)", shortTitle: "Act. 3 y 4" },
    5: { title: "Revisión, Puntajes y Guardado", shortTitle: "Guardar" },
  };

  let currentStep = 1;
  let saveTimer = null;
  let isRestoring = false;
  let draftKey = null;
  const accordionCollapsed = { 3: false, 4: true };

  function buildDraftKey() {
    const $root = $("#guia-wizard-root");
    const usuario = ($root.data("usuario") || "anon").toString().trim();
    const asignacionId = ($root.data("asignacion-id") || "0").toString().trim();
    const encuentro = ($root.data("encuentro") || "0").toString().trim();
    return `planeauml_guia_draft_v${DRAFT_VERSION}_${usuario}_${asignacionId}_${encuentro}`;
  }

  function hasTextValue(val) {
    return val !== null && val !== undefined && String(val).trim() !== "";
  }

  function isActivityFieldFilled($field, isRequired) {
    if (!$field || $field.length === 0) return false;
    const raw = $field.val();
    if (raw === null || raw === undefined) return false;
    const strVal = String(raw).trim();
    if ($field.is('input[type="number"]')) {
      const num = parseFloat(strVal);
      if (isNaN(num)) return false;
      return isRequired ? num >= 0 : num > 0;
    }
    return strVal !== "";
  }

  function evaluateBaseStatus() {
    let completed = 0;
    GENERAL_FIELDS.forEach((id) => {
      if (hasTextValue($("#" + id).val())) {
        completed++;
      }
    });
    const total = GENERAL_FIELDS.length;
    let status = "empty";
    if (completed === total) status = "complete";
    else if (completed > 0) status = "partial";
    return { completed, total, status };
  }

  function evaluateActivityStatus(num) {
    const isRequired = num === 1;
    let filled = 0;

    ACTIVITY_FIELD_PREFIXES.forEach((prefix) => {
      if (isActivityFieldFilled($(`#${prefix}_${num}`), isRequired)) {
        filled++;
      }
    });

    if ($(`input[name="agente_evaluador_${num}[]"]:checked`).length > 0) {
      filled++;
    }

    const total = ACTIVITY_FIELD_PREFIXES.length + 1; // 14 campos por actividad
    let status = "empty";
    if (filled === total) {
      status = "complete";
    } else if (filled > 0) {
      status = "partial";
    } else if (!isRequired) {
      status = "optional";
    }

    const puntaje = parseFloat($(`#puntaje_${num}`).val()) || 0;
    const tiempo = parseInt($(`#tiempo_minutos_${num}`).val(), 10) || 0;

    return {
      activity: num,
      required: isRequired,
      filled,
      total,
      status,
      puntaje,
      tiempo,
    };
  }

  function evaluateStepStatus(step) {
    if (step === 1) return evaluateBaseStatus();
    if (step === 2) {
      const act1 = evaluateActivityStatus(1);
      return { status: act1.status, completed: act1.filled, total: act1.total };
    }
    if (step === 3) {
      const act2 = evaluateActivityStatus(2);
      return { status: act2.status, completed: act2.filled, total: act2.total };
    }
    if (step === 4) {
      const act3 = evaluateActivityStatus(3);
      const act4 = evaluateActivityStatus(4);
      if (act3.status === "partial" || act4.status === "partial") {
        const partial = act3.status === "partial" ? act3 : act4;
        return {
          status: "partial",
          completed: partial.filled,
          total: partial.total,
        };
      }
      if (act3.status === "complete" || act4.status === "complete") {
        return { status: "complete", completed: 1, total: 1 };
      }
      return { status: "optional", completed: 0, total: 0 };
    }
    return { status: "review", completed: 0, total: 0 };
  }

  function updateActivityCardBadges() {
    for (let num = 1; num <= 4; num++) {
      const info = evaluateActivityStatus(num);
      const $badge = $(`#activity-badge-${num}`);
      const $clearBtn = $(`#clear-activity-${num}`);

      if ($badge.length) {
        $badge.removeClass("bg-success bg-warning text-dark bg-secondary bg-danger");
        if (info.status === "complete") {
          $badge.addClass("bg-success").text("Completa (14/14)");
        } else if (info.status === "partial") {
          $badge.addClass("bg-warning text-dark").text(`Incompleta (${info.filled}/${info.total})`);
        } else if (info.required) {
          $badge.addClass("bg-danger").text(`Pendiente (0/${info.total})`);
        } else {
          $badge.addClass("bg-secondary").text("Omitida (opcional)");
        }
      }

      if ($clearBtn.length) {
        $clearBtn.toggleClass("d-none", info.filled === 0);
      }
    }
  }

  function updateStepBadges() {
    for (let step = 1; step <= 4; step++) {
      const info = evaluateStepStatus(step);
      const $tab = $(`.wizard-step-tab[data-step="${step}"]`);
      $tab.removeClass("is-complete is-partial is-optional is-empty");
      $tab.addClass(`is-${info.status}`);

      const $dot = $tab.find(".wizard-tab-status");
      if (info.status === "complete") {
        $dot.html('<i class="fas fa-check"></i>');
      } else if (info.status === "partial") {
        $dot.text(`${info.completed}/${info.total}`);
      } else if (info.status === "optional") {
        $dot.text("Opc");
      } else {
        $dot.text(String(step));
      }
    }

    updateActivityCardBadges();
    renderReviewChecklist();
  }

  function buildReviewRowHtml(opts) {
    return `
      <button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center wizard-review-item" data-go-step="${opts.step}" ${opts.expandActivity ? `data-expand-activity="${opts.expandActivity}"` : ""}>
        <div class="d-flex align-items-center gap-2 text-start">
          <i class="fas ${opts.iconClass} fa-lg"></i>
          <div>
            <div class="fw-semibold">${opts.title}</div>
            <small class="text-muted">${opts.subtitle}</small>
          </div>
        </div>
        <span class="badge rounded-pill ${opts.badgeClass}">${opts.badgeText}</span>
      </button>
    `;
  }

  function resolveActivityRowStyle(info) {
    if (info.status === "complete") {
      return {
        badgeClass: "bg-success",
        badgeText: "Completa",
        iconClass: "fa-check-circle text-success",
        subtitle: `${info.puntaje} pts • ${info.tiempo} min — Toca para editar`,
        ok: true,
      };
    }
    if (info.status === "partial") {
      return {
        badgeClass: "bg-warning text-dark",
        badgeText: `${info.filled} de ${info.total} campos`,
        iconClass: "fa-exclamation-circle text-warning",
        subtitle: info.required
          ? "Faltan campos obligatorios — Toca para completar"
          : "Actividad parcial: complétala o límpiala para omitir",
        ok: false,
      };
    }
    if (!info.required) {
      return {
        badgeClass: "bg-secondary",
        badgeText: "Omitida (opcional)",
        iconClass: "fa-minus-circle text-secondary",
        subtitle: "No se incluirá — Toca si deseas agregarla",
        ok: true,
      };
    }
    return {
      badgeClass: "bg-danger",
      badgeText: `0 de ${info.total} campos`,
      iconClass: "fa-times-circle text-danger",
      subtitle: "Obligatoria — Toca para completar",
      ok: false,
    };
  }

  function renderReviewChecklist() {
    const $list = $("#wizard-review-list");
    if ($list.length === 0) return;

    const baseInfo = evaluateBaseStatus();
    const act1 = evaluateActivityStatus(1);
    const act2 = evaluateActivityStatus(2);
    const act3 = evaluateActivityStatus(3);
    const act4 = evaluateActivityStatus(4);

    let allValid = true;
    const rows = [];

    // Fila 1: Base e IA
    let baseBadge = {
      badgeClass: "bg-danger",
      badgeText: `0 de ${baseInfo.total} campos`,
      iconClass: "fa-times-circle text-danger",
      subtitle: "Obligatorio — Toca para completar",
    };
    if (baseInfo.status === "complete") {
      baseBadge = {
        badgeClass: "bg-success",
        badgeText: "Completo",
        iconClass: "fa-check-circle text-success",
        subtitle: "Toca para revisar o editar",
      };
    } else if (baseInfo.status === "partial") {
      allValid = false;
      baseBadge = {
        badgeClass: "bg-warning text-dark",
        badgeText: `${baseInfo.completed} de ${baseInfo.total} campos`,
        iconClass: "fa-exclamation-circle text-warning",
        subtitle: "Faltan datos generales — Toca para completar",
      };
    } else {
      allValid = false;
    }

    rows.push(
      buildReviewRowHtml({
        step: 1,
        title: "1. Base, IA y Configuración",
        subtitle: baseBadge.subtitle,
        badgeClass: baseBadge.badgeClass,
        badgeText: baseBadge.badgeText,
        iconClass: baseBadge.iconClass,
      }),
    );

    const activityDefinitions = [
      { info: act1, step: 2, title: "2. Primera Actividad (Obligatoria)", expandActivity: null },
      { info: act2, step: 3, title: "3. Segunda Actividad (Opcional)", expandActivity: null },
      { info: act3, step: 4, title: "4. Tercera Actividad (Opcional)", expandActivity: 3 },
      { info: act4, step: 4, title: "5. Cuarta Actividad (Opcional)", expandActivity: 4 },
    ];

    activityDefinitions.forEach((def) => {
      const style = resolveActivityRowStyle(def.info);
      if (!style.ok) allValid = false;
      rows.push(
        buildReviewRowHtml({
          step: def.step,
          expandActivity: def.expandActivity,
          title: def.title,
          subtitle: style.subtitle,
          badgeClass: style.badgeClass,
          badgeText: style.badgeText,
          iconClass: style.iconClass,
        }),
      );
    });

    $list.html(rows.join(""));

    const totalPts = act1.puntaje + act2.puntaje + act3.puntaje + act4.puntaje;
    const scoreOverflow = totalPts > 100 || act1.puntaje < 0 || act2.puntaje < 0 || act3.puntaje < 0 || act4.puntaje < 0;

    const $summaryAlert = $("#wizard-review-status-alert");
    if ($summaryAlert.length) {
      if (scoreOverflow) {
        $summaryAlert
          .removeClass("alert-success alert-warning")
          .addClass("alert-danger")
          .html(
            `<i class="fas fa-exclamation-triangle me-2"></i><strong>Revisa los puntajes:</strong> la suma de las actividades (${totalPts} pts) debe ser positiva y no mayor a 100 puntos.`,
          );
      } else if (allValid) {
        $summaryAlert
          .removeClass("alert-warning alert-danger")
          .addClass("alert-success")
          .html(
            '<i class="fas fa-check-circle me-2"></i><strong>¡Todo listo!</strong> Las secciones obligatorias están completas y no hay actividades parciales. Ya puedes guardar la guía.',
          );
      } else {
        $summaryAlert
          .removeClass("alert-success alert-danger")
          .addClass("alert-warning")
          .html(
            '<i class="fas fa-info-circle me-2"></i>Hay campos obligatorios pendientes o una actividad opcional a medias. Toca cualquier fila abajo para completarla o limpiarla.',
          );
      }
    }
  }

  function syncReviewMetrics() {
    let totalPts = 0;
    let totalMinutes = 0;

    for (let num = 1; num <= 4; num++) {
      const info = evaluateActivityStatus(num);
      totalPts += info.puntaje;
      totalMinutes += info.tiempo;

      const $ptsCard = $(`#wizard-review-act-${num}-pts`);
      const $minCard = $(`#wizard-review-act-${num}-min`);
      if ($ptsCard.length) {
        $ptsCard.text(info.status === "optional" ? "Omitida" : `${info.puntaje} pts`);
      }
      if ($minCard.length) {
        $minCard.text(info.status === "optional" ? "0 min" : `${info.tiempo} min`);
      }
    }

    $("#wizard-header-score")
      .html(`<i class="fas fa-star me-1"></i>${totalPts}/100 pts`)
      .toggleClass("is-danger", totalPts > 100);
    $("#wizard-header-total-time").html(`<i class="fas fa-clock me-1"></i>${totalMinutes} min`);
    $("#wizard-review-total-time").text(`${totalMinutes} min`);

    if (typeof window.actualizarSumaPuntajes === "function") {
      window.actualizarSumaPuntajes();
    }
  }

  function setActivityCollapsed(num, collapsed) {
    if (num !== 3 && num !== 4) return;
    accordionCollapsed[num] = Boolean(collapsed);
    const $body = $(`#activity-body-${num}`);
    const $btn = $(`[data-toggle-activity="${num}"]`);
    const $icon = $btn.find("i");
    const $label = $btn.find(".toggle-label");

    if (accordionCollapsed[num]) {
      $body.addClass("d-none");
      $btn.attr("aria-expanded", "false");
      $icon.removeClass("fa-chevron-up").addClass("fa-chevron-down");
      if ($label.length) $label.text("Abrir");
    } else {
      $body.removeClass("d-none");
      $btn.attr("aria-expanded", "true");
      $icon.removeClass("fa-chevron-down").addClass("fa-chevron-up");
      if ($label.length) $label.text("Ocultar");
      autoResizeVisibleTextareas();
    }
  }

  function syncAccordionsFromContentAndPreference(preferCount) {
    const act3 = evaluateActivityStatus(3);
    const act4 = evaluateActivityStatus(4);
    const count = parseInt($("#numero_actividades").val(), 10) || 4;

    if (preferCount) {
      setActivityCollapsed(3, act3.filled === 0 && count < 3);
      setActivityCollapsed(4, act4.filled === 0 && count < 4);
      return;
    }

    // Por defecto al entrar manualmente: Act. 3 abierta si tiene contenido o si Act. 4 está vacía; Act. 4 abierta solo si tiene datos
    setActivityCollapsed(3, false);
    setActivityCollapsed(4, act4.filled === 0);
  }

  function scrollTabsContainerTo($activeTab) {
    const $tabsContainer = $activeTab.closest(".wizard-tabs-scroll");
    if (!$activeTab.length || !$tabsContainer.length) return;
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

  function goToStep(step, options) {
    const opts = Object.assign({ scroll: true, save: true, expandActivity: null }, options);
    const targetStep = Math.max(1, Math.min(TOTAL_STEPS, Number(step) || 1));
    currentStep = targetStep;

    $(".wizard-step").addClass("d-none").removeClass("is-active");
    $(`.wizard-step[data-step="${targetStep}"]`)
      .removeClass("d-none")
      .addClass("is-active");

    if (targetStep === 1) {
      $("#wizard-ai-panel").removeClass("d-none");
    } else {
      $("#wizard-ai-panel").addClass("d-none");
    }

    if (targetStep === 4 && (opts.expandActivity === 3 || opts.expandActivity === 4)) {
      setActivityCollapsed(opts.expandActivity, false);
    }

    $(".wizard-step-tab").removeClass("active");
    const $activeTab = $(`.wizard-step-tab[data-step="${targetStep}"]`).addClass("active");
    scrollTabsContainerTo($activeTab);

    const percent = Math.round((targetStep / TOTAL_STEPS) * 100);
    $("#wizard-progress-bar")
      .css("width", `${percent}%`)
      .attr("aria-valuenow", percent);
    $("#wizard-step-counter").text(`Paso ${targetStep} de ${TOTAL_STEPS}`);
    $("#wizard-step-title").text(STEP_META[targetStep].title);

    $("#wizardPrevBtn").prop("disabled", targetStep === 1);
    if (targetStep === TOTAL_STEPS) {
      $("#wizardNextBtn").addClass("d-none");
      $("#guardarFormularioBtn").removeClass("d-none");
    } else {
      $("#wizardNextBtn").removeClass("d-none");
      $("#guardarFormularioBtn").addClass("d-none");
    }

    // Limpiar alerta de paso al navegar normalmente si no es un salto por error
    if (opts.clearAlerts !== false) {
      $("#wizard-step-alert-container .guia-dynamic-alert").remove();
    }

    updateStepBadges();
    syncReviewMetrics();
    autoResizeVisibleTextareas();

    if (opts.save && !isRestoring) {
      scheduleSaveDraft();
    }

    if (opts.scroll) {
      $("#guia-wizard-root .card.shadow-lg").scrollTop(0);
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
    return $stepEl.length ? Number($stepEl.data("step")) || null : null;
  }

  function goToStepForElement($element) {
    if (!$element || $element.length === 0) return null;
    const step = findStepForElement($element);
    let expandActivity = null;
    if ($element.closest("#activity-body-3").length) expandActivity = 3;
    if ($element.closest("#activity-body-4").length) expandActivity = 4;

    if (step) {
      goToStep(step, {
        scroll: false,
        save: false,
        clearAlerts: false,
        expandActivity,
      });
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
    const formEl = document.getElementById("formEstudioIndependiente");
    if (!formEl) return null;

    $(formEl)
      .find("input, select, textarea")
      .each(function () {
        const name = $(this).attr("name");
        if (!name || IGNORED_DRAFT_NAMES.has(name)) return;

        if (this.type === "checkbox") {
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
      numeroActividades: $("#numero_actividades").val() || "4",
      modeloIA: $("#modelo_select_estudio").val() || "",
      accordionCollapsed: Object.assign({}, accordionCollapsed),
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
      console.warn("No se pudo guardar el borrador local de guía:", err);
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
      if (draft.numeroActividades && $(`#numero_actividades option[value="${draft.numeroActividades}"]`).length) {
        $("#numero_actividades").val(draft.numeroActividades);
      }
      if (draft.modeloIA && $(`#modelo_select_estudio option[value="${draft.modeloIA}"]`).length) {
        $("#modelo_select_estudio").val(draft.modeloIA);
      }

      Object.entries(draft.fields).forEach(([name, value]) => {
        if (IGNORED_DRAFT_NAMES.has(name)) return;
        const $targets = $(`#formEstudioIndependiente [name="${name}"]`);
        if ($targets.length === 0) return;

        const firstType = $targets.first().attr("type");
        if (firstType === "checkbox") {
          const arr = Array.isArray(value) ? value : [value];
          $targets.prop("checked", false);
          arr.forEach((v) => {
            $targets
              .filter(function () {
                return $(this).val() === String(v);
              })
              .prop("checked", true);
          });
        } else if (firstType === "radio") {
          $targets.prop("checked", false);
          if (value !== undefined && value !== null) {
            $targets
              .filter(function () {
                return $(this).val() === String(value);
              })
              .prop("checked", true);
          }
        } else {
          $targets.val(value !== null && value !== undefined ? value : "");
        }
      });

      syncAllAgentChips();
      syncAllTimePresetButtons();

      if (draft.accordionCollapsed && typeof draft.accordionCollapsed === "object") {
        const act3Filled = evaluateActivityStatus(3).filled > 0;
        const act4Filled = evaluateActivityStatus(4).filled > 0;
        setActivityCollapsed(3, !act3Filled && Boolean(draft.accordionCollapsed[3]));
        setActivityCollapsed(4, !act4Filled && Boolean(draft.accordionCollapsed[4]));
      } else {
        syncAccordionsFromContentAndPreference(false);
      }

      syncReviewMetrics();
      if (typeof window.updateAccumulatedScores === "function") {
        window.updateAccumulatedScores();
      } else {
        $("#puntaje_1").trigger("change");
      }

      const restoredStep = Math.max(
        1,
        Math.min(TOTAL_STEPS, Number(draft.currentStep) || 1),
      );
      goToStep(restoredStep, { scroll: false, save: false });

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
      // Ignorar si localStorage no está disponible
    }
  }

  function clearOptionalActivity(num) {
    if (num !== 2 && num !== 3 && num !== 4) return;
    ACTIVITY_FIELD_PREFIXES.forEach((prefix) => {
      $(`#${prefix}_${num}`).val("").removeClass("is-invalid campo-invalido");
    });
    const $checks = $(`input[name="agente_evaluador_${num}[]"]`);
    $checks.prop("checked", false);
    $checks.closest(".agent-chip-list, .form-check").removeClass("is-invalid");

    if (num >= 3) {
      setActivityCollapsed(num, true);
    }

    syncAgentChipsForGroup(`agente_evaluador_${num}[]`);
    syncTimePresetButtonsForInput($(`#tiempo_minutos_${num}`));
    syncReviewMetrics();
    if (typeof window.updateAccumulatedScores === "function") {
      window.updateAccumulatedScores();
    } else {
      $(`#puntaje_${num}`).trigger("change");
    }
    updateStepBadges();
    saveDraftNow();
  }

  function resetDraftAndForm() {
    clearDraft();
    isRestoring = true;
    try {
      const formEl = document.getElementById("formEstudioIndependiente");
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

      if ($('#numero_actividades option[value="4"]').length) {
        $("#numero_actividades").val("4");
      }

      $("#formEstudioIndependiente .is-invalid, #formEstudioIndependiente .campo-invalido")
        .removeClass("is-invalid campo-invalido");
      $(".guia-dynamic-alert").remove();

      syncAllAgentChips();
      syncAllTimePresetButtons();
      syncAccordionsFromContentAndPreference(false);
      syncReviewMetrics();
      if (typeof window.updateAccumulatedScores === "function") {
        window.updateAccumulatedScores();
      }
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

  // --- Chips táctiles para Agente Evaluador ---

  function syncAgentChipsForGroup(groupName) {
    $(`input[name="${groupName}"]`).each(function () {
      const $label = $(this).closest("label");
      $label.toggleClass("is-checked", this.checked);
    });
  }

  function syncAllAgentChips() {
    for (let num = 1; num <= 4; num++) {
      syncAgentChipsForGroup(`agente_evaluador_${num}[]`);
    }
  }

  // --- Presets de tiempo ---

  function syncTimePresetButtonsForInput($input) {
    if (!$input || $input.length === 0) return;
    const id = $input.attr("id");
    if (!id) return;
    const val = String($input.val() || "").trim();
    $(`.time-preset-row[data-target="#${id}"] .time-preset-btn`).each(function () {
      const presetVal = String($(this).data("minutes"));
      $(this).toggleClass("active btn-primary", val === presetVal);
      $(this).toggleClass("btn-outline-secondary", val !== presetVal);
    });
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
    const minH = 74;
    const maxH = 260;
    const nextH = Math.min(maxH, Math.max(minH, el.scrollHeight + 2));
    el.style.height = `${nextH}px`;
  }

  function autoResizeVisibleTextareas() {
    $(".wizard-step.is-active textarea").each(function () {
      if (!$(this).closest(".d-none").length) {
        autoResizeTextarea(this);
      }
    });
  }

  function autoResizeAllTextareas() {
    $("#formEstudioIndependiente textarea").each(function () {
      autoResizeTextarea(this);
    });
  }

  function initNumericInputsAndTextareas() {
    $('#formEstudioIndependiente [id^="tiempo_minutos_"], #formEstudioIndependiente .puntaje').attr({
      inputmode: "numeric",
      pattern: "[0-9]*",
    });
    $("#formEstudioIndependiente textarea").attr("rows", "2");
  }

  function bindEvents() {
    // Pestañas superiores (navegación libre)
    $(document).on("click", ".wizard-step-tab", function () {
      const target = Number($(this).data("step"));
      goToStep(target);
    });

    // Clic desde lista de revisión en Paso 5
    $(document).on("click", ".wizard-review-item", function () {
      const target = Number($(this).data("go-step"));
      const expandActivity = Number($(this).data("expand-activity")) || null;
      goToStep(target, { expandActivity });
    });

    // Acordeón en Paso 4 (Actividades 3 y 4)
    $(document).on("click", "[data-toggle-activity]", function () {
      const num = Number($(this).data("toggle-activity"));
      setActivityCollapsed(num, !accordionCollapsed[num]);
      scheduleSaveDraft();
    });

    // Botón limpiar / omitir actividad opcional (2, 3, 4)
    $(document).on("click", "[data-clear-activity]", function (e) {
      e.stopPropagation();
      const num = Number($(this).data("clear-activity"));
      if (
        evaluateActivityStatus(num).filled > 0 &&
        !window.confirm(`¿Deseas vaciar todos los campos de la Actividad ${num} para omitirla?`)
      ) {
        return;
      }
      clearOptionalActivity(num);
    });

    // Botón Anterior
    $("#wizardPrevBtn").on("click", function () {
      if (currentStep > 1) {
        goToStep(currentStep - 1);
      }
    });

    // Botón Siguiente (valida el paso actual cuando corresponde)
    $("#wizardNextBtn").on("click", function () {
      if (typeof window.validarPasoFormulario === "function") {
        if (!window.validarPasoFormulario(currentStep)) {
          return;
        }
      }
      if (currentStep < TOTAL_STEPS) {
        goToStep(currentStep + 1);
      }
    });

    // Presets de minutos
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

    // Sincronizar chips al marcar checkboxes de Agente Evaluador
    for (let num = 1; num <= 4; num++) {
      const groupName = `agente_evaluador_${num}[]`;
      $(document).on("change", `input[name="${groupName}"]`, function () {
        syncAgentChipsForGroup(groupName);
        $(this).closest(".agent-chip-list, .form-check").removeClass("is-invalid");
      });
    }

    // Cambio en cantidad de actividades (Paso 1) -> ajusta acordeones del Paso 4 y guarda borrador
    $(document).on("change", "#numero_actividades, #modelo_select_estudio", function () {
      if (this.id === "numero_actividades") {
        syncAccordionsFromContentAndPreference(true);
      }
      scheduleSaveDraft();
    });

    // Autoguardado y métricas en vivo al editar cualquier campo del formulario
    $(document).on(
      "input change",
      "#formEstudioIndependiente input, #formEstudioIndependiente select, #formEstudioIndependiente textarea",
      function () {
        if (this.tagName === "TEXTAREA") {
          autoResizeTextarea(this);
        }
        if (this.id && this.id.startsWith("tiempo_minutos_")) {
          syncTimePresetButtonsForInput($(this));
        }
        if (hasTextValue($(this).val())) {
          $(this).removeClass("is-invalid campo-invalido");
        }
        updateStepBadges();
        syncReviewMetrics();
        scheduleSaveDraft();
      },
    );

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
    syncAllAgentChips();
    syncAllTimePresetButtons();
    syncAccordionsFromContentAndPreference(true);
    autoResizeAllTextareas();
    if (typeof window.updateAccumulatedScores === "function") {
      window.updateAccumulatedScores();
    } else {
      $("#puntaje_1").trigger("change");
    }
    syncReviewMetrics();
    updateStepBadges();
    saveDraftNow();
  }

  $(document).ready(function () {
    if ($("#guia-wizard-root").length === 0) return;

    draftKey = buildDraftKey();
    initNumericInputsAndTextareas();
    bindEvents();
    syncAllAgentChips();
    syncAllTimePresetButtons();

    const restored = restoreDraftIfAvailable();
    if (!restored) {
      syncAccordionsFromContentAndPreference(false);
      goToStep(1, { scroll: false, save: false });
    }
  });

  // API pública para guia_guardar.js y guia_ia.js
  window.GuiaWizard = {
    getCurrentStep: () => currentStep,
    goToStep: goToStep,
    goToStepForElement: goToStepForElement,
    clearDraft: clearDraft,
    saveDraftNow: saveDraftNow,
    clearOptionalActivity: clearOptionalActivity,
    setActivityCollapsed: setActivityCollapsed,
    evaluateActivityStatus: evaluateActivityStatus,
    updateStepBadges: updateStepBadges,
    syncReviewMetrics: syncReviewMetrics,
    onAfterAiAutofill: onAfterAiAutofill,
  };
})(window, jQuery);
