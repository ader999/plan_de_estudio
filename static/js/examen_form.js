(function () {
    'use strict';

    const root = document.getElementById('examen-form-root');
    if (!root) return;

    const ROMANOS = [
        'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
        'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'
    ];

    const ASIGNACION_ID = parseInt(root.dataset.asignacionId || '0', 10);
    const NUMERO_EVALUACION = parseInt(root.dataset.numeroEvaluacion || '1', 10);
    const EXAMEN_ID = root.dataset.examenId ? parseInt(root.dataset.examenId, 10) : null;
    const MODO_EDICION = root.dataset.modoEdicion === 'true';
    const PUNTAJE_REQUERIDO = parseInt(root.dataset.puntajeRequerido || '0', 10) || 0;
    const BLOQUEADO_POR_PUNTAJE = root.dataset.bloqueadoPuntaje === 'true';
    const URL_GUARDAR = root.dataset.urlGuardar || '';
    const URL_IA = root.dataset.urlIa || '';

    const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
    const CSRF_TOKEN = csrfEl ? csrfEl.value : '';

    // Constantes sincronizadas exactamente con utils/exam_utils.py
    const CHARS_OBJ = 42;
    const CHARS_EJER = 46;
    const CHARS_RESP = 36;
    const CHARS_PTS = 11;
    const LINEAS_P1 = 25.0;
    const LINEAS_SIG = 38.0;
    const LINEAS_FIRMA = 3.0;
    const LINEAS_PAD = 1.5;
    const MIN_PAGINAS_EXCL = parseFloat(root.dataset.minPaginas || '2.0') || 2.0;
    const MIN_ITEMS = 2;
    const MIN_CHARS_UTILES = 1200;

    const DRAFT_KEY = `planeauml_examen_draft_${ASIGNACION_ID}_${NUMERO_EVALUACION}`;

    const container = document.getElementById('apartados-container');
    const countBadge = document.getElementById('apartados-count-badge');
    const errorAlert = document.getElementById('form-error-alert');
    const btnGuardar = document.getElementById('btn-guardar-examen');
    const metaDetails = document.getElementById('exam-meta-details');
    const metaSummaryText = document.getElementById('exam-meta-summary-text');
    const draftBanner = document.getElementById('draft-restored-banner');
    const draftTimeEl = document.getElementById('draft-restored-time');
    const btnDescartarDraft = document.getElementById('btn-descartar-borrador');

    const saveBtnOriginalHtml = btnGuardar ? btnGuardar.innerHTML : '';

    let hojasObjetivoUsadasIA = null;
    const aiHojasEl = document.getElementById('ai-hojas-select');
    if (MODO_EDICION && aiHojasEl && aiHojasEl.value) {
        const hInit = parseInt(aiHojasEl.value, 10);
        if (!Number.isNaN(hInit)) {
            hojasObjetivoUsadasIA = hInit;
        }
    }

    let apartadoSeq = 0;
    let draftTimer = null;

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function parsePuntaje(raw) {
        if (raw === '' || raw === null || raw === undefined) return 0;
        const val = parseFloat(String(raw).replace(',', '.'));
        if (!Number.isFinite(val)) return 0;
        return Math.max(0, Math.round(val));
    }

    function itemEsVacio(it) {
        return !(it.objetivo || it.ejercicios || it.posibles_respuestas || it.puntaje);
    }

    function contarLineas(texto, charsPorLinea) {
        const limpio = String(texto || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
        if (!limpio) return 1.0;
        const colapsado = limpio.replace(/\n{3,}/g, '\n\n');
        let total = 0;
        for (const linea of colapsado.split('\n')) {
            const t = linea.trim();
            if (!t) {
                total += 0.6;
            } else {
                total += Math.max(1, Math.ceil(t.length / charsPorLinea));
            }
        }
        return Math.max(1.0, total);
    }

    function obtenerItemsDesdeDOM() {
        const cards = container.querySelectorAll('.apartado-card');
        const items = [];
        cards.forEach((card, idx) => {
            const num = ROMANOS[idx] || String(idx + 1);
            const objetivo = card.querySelector('.inp-objetivo').value.trim();
            const ejercicios = card.querySelector('.inp-ejercicios').value.trim();
            const posibles_respuestas = card.querySelector('.inp-respuestas').value.trim();
            const puntaje = parsePuntaje(card.querySelector('.inp-puntaje').value);
            const detalle_puntaje = card.querySelector('.inp-detalle-puntaje').value.trim();
            items.push({
                numero: num,
                objetivo,
                ejercicios,
                posibles_respuestas,
                puntaje,
                detalle_puntaje,
                _card: card
            });
        });
        return items;
    }

    function estimarPaginas(rawItems) {
        // Sincronizado con normalizar_items_examen_entrada: ignora apartados completamente vacíos
        const items = (rawItems || []).filter((it) => !itemEsVacio(it));
        if (items.length === 0) {
            return { paginas: 0.0, hojas: 0, charsUtiles: 0, itemsValidos: 0, cumple: false };
        }

        let totalLineas = 0.0;
        let charsUtiles = 0;
        let itemsValidos = 0;

        for (const it of items) {
            if (it.objetivo && it.ejercicios && it.posibles_respuestas) {
                itemsValidos++;
            }
            for (const c of [it.objetivo, it.ejercicios, it.posibles_respuestas]) {
                charsUtiles += String(c || '').replace(/[\s_.\-]+/g, '').length;
            }
            const lObj = contarLineas(it.objetivo, CHARS_OBJ);
            const lEjer = contarLineas(it.ejercicios, CHARS_EJER);
            const lResp = contarLineas(it.posibles_respuestas, CHARS_RESP);
            const lPts = contarLineas(it.detalle_puntaje || `${it.puntaje} pts`, CHARS_PTS);
            totalLineas += Math.max(lObj, lEjer, lResp, lPts) + LINEAS_PAD;
        }

        const conFirma = totalLineas + LINEAS_FIRMA;
        let paginas = conFirma <= LINEAS_P1
            ? (conFirma / LINEAS_P1)
            : (1.0 + (conFirma - LINEAS_P1) / LINEAS_SIG);
        paginas = Math.round(paginas * 10) / 10;
        const hojas = Math.max(1, Math.ceil(paginas));
        const cumple = itemsValidos >= MIN_ITEMS && paginas > MIN_PAGINAS_EXCL && charsUtiles >= MIN_CHARS_UTILES;
        return { paginas, hojas, charsUtiles, itemsValidos, cumple };
    }

    function actualizarResumenMeta() {
        if (!metaSummaryText) return;
        const anio = document.getElementById('id_anio_lectivo')?.value.trim() || '—';
        const trim = document.getElementById('id_trimestre')?.value.trim() || '—';
        const muni = document.getElementById('id_municipio')?.value.trim() || 'Sede';
        metaSummaryText.textContent = `Datos institucionales prellenados (${anio} · Trim. ${trim} · ${muni})`;
    }

    function actualizarPreviewTarjeta(card) {
        const preview = card.querySelector('.apartado-preview');
        if (!preview) return;
        const pts = parsePuntaje(card.querySelector('.inp-puntaje').value);
        const obj = card.querySelector('.inp-objetivo').value.trim();
        const texto = obj ? obj.slice(0, 48) + (obj.length > 48 ? '…' : '') : 'Sin objetivo aún';
        preview.textContent = card.classList.contains('is-collapsed')
            ? `${pts} pts · ${texto}`
            : '';
    }

    function actualizarMedidores() {
        const items = obtenerItemsDesdeDOM();
        const noVacios = items.filter((it) => !itemEsVacio(it));
        const sumaPts = noVacios.reduce((acc, it) => acc + (it.puntaje || 0), 0);
        const est = estimarPaginas(items);

        // Puntaje
        const badgePts = document.getElementById('meter-puntaje-badge');
        const barPts = document.getElementById('meter-puntaje-bar');
        const hintPts = document.getElementById('meter-puntaje-hint');
        const pctPts = PUNTAJE_REQUERIDO > 0
            ? Math.min(100, Math.round((sumaPts / PUNTAJE_REQUERIDO) * 100))
            : 0;

        badgePts.textContent = `${sumaPts} / ${PUNTAJE_REQUERIDO} pts`;
        barPts.style.width = `${pctPts}%`;
        barPts.setAttribute('aria-valuenow', String(sumaPts));

        if (PUNTAJE_REQUERIDO <= 0) {
            badgePts.className = 'badge bg-danger';
            barPts.className = 'progress-bar bg-danger';
            hintPts.textContent = 'Sin puntaje disponible en el corte. Ajusta tus sílabos o guías primero.';
        } else if (sumaPts === PUNTAJE_REQUERIDO) {
            badgePts.className = 'badge bg-success';
            barPts.className = 'progress-bar bg-success';
            hintPts.textContent = 'Puntaje exacto completado.';
        } else if (sumaPts < PUNTAJE_REQUERIDO) {
            badgePts.className = 'badge bg-warning text-dark';
            barPts.className = 'progress-bar bg-warning';
            hintPts.textContent = `Faltan ${PUNTAJE_REQUERIDO - sumaPts} pts por distribuir entre los apartados.`;
        } else {
            badgePts.className = 'badge bg-danger';
            barPts.className = 'progress-bar bg-danger';
            hintPts.textContent = `Excede por ${sumaPts - PUNTAJE_REQUERIDO} pts el puntaje disponible del corte.`;
        }

        // Páginas
        const badgePag = document.getElementById('meter-paginas-badge');
        const barPag = document.getElementById('meter-paginas-bar');
        const hintPag = document.getElementById('meter-paginas-hint');
        const pctPag = Math.min(100, Math.round((est.paginas / 3.0) * 100));

        badgePag.textContent = `${est.paginas.toFixed(1)} pág.`;
        barPag.style.width = `${pctPag}%`;
        barPag.setAttribute('aria-valuenow', String(pctPag));

        if (est.cumple) {
            badgePag.className = 'badge bg-success';
            barPag.className = 'progress-bar bg-success';
            hintPag.textContent = `Extensión aprobada (${est.itemsValidos} apartados completos, ${est.charsUtiles} caracteres efectivos).`;
        } else {
            badgePag.className = 'badge bg-danger';
            barPag.className = 'progress-bar bg-danger';
            if (est.itemsValidos < MIN_ITEMS) {
                hintPag.textContent = `Mínimo requerido: superar ${MIN_PAGINAS_EXCL.toFixed(1)} páginas con al menos ${MIN_ITEMS} apartados completos.`;
            } else if (est.paginas <= MIN_PAGINAS_EXCL) {
                hintPag.textContent = `Extensión insuficiente (${est.paginas.toFixed(1)} pág.): debe superar ${MIN_PAGINAS_EXCL.toFixed(1)} páginas.`;
            } else {
                hintPag.textContent = `Contenido aún breve (${est.charsUtiles}/${MIN_CHARS_UTILES} caracteres efectivos). Amplía los ejercicios y respuestas.`;
            }
        }
    }

    function renumerarApartados() {
        const cards = container.querySelectorAll('.apartado-card');
        cards.forEach((card, idx) => {
            const num = ROMANOS[idx] || String(idx + 1);
            card.querySelector('.apartado-badge').textContent = `Apartado ${num}`;
            const btnDel = card.querySelector('.btn-del-apartado');
            btnDel.disabled = cards.length <= 1;
            actualizarPreviewTarjeta(card);
        });
        if (countBadge) {
            countBadge.textContent = `${cards.length} apartado${cards.length === 1 ? '' : 's'}`;
        }
        actualizarMedidores();
    }

    function setCardCollapsed(card, collapsed) {
        const btn = card.querySelector('.btn-toggle-apartado');
        card.classList.toggle('is-collapsed', collapsed);
        if (btn) {
            btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            btn.innerHTML = collapsed
                ? '<i class="fas fa-chevron-down"></i>'
                : '<i class="fas fa-chevron-up"></i>';
            btn.title = collapsed ? 'Expandir apartado' : 'Contraer apartado';
        }
        actualizarPreviewTarjeta(card);
    }

    function crearCardApartado(data = {}) {
        apartadoSeq += 1;
        const seq = apartadoSeq;
        const ptsId = `apartado_pts_${seq}`;
        const detId = `apartado_det_${seq}`;
        const objId = `apartado_obj_${seq}`;
        const ejerId = `apartado_ejer_${seq}`;
        const respId = `apartado_resp_${seq}`;

        const card = document.createElement('div');
        card.className = 'apartado-card';
        card.innerHTML = `
            <div class="apartado-header">
                <div class="d-flex align-items-center gap-2 min-w-0">
                    <span class="apartado-badge">Apartado</span>
                    <button type="button" class="btn btn-sm btn-outline-secondary btn-toggle-apartado" aria-expanded="true" title="Contraer apartado" aria-label="Contraer o expandir apartado">
                        <i class="fas fa-chevron-up"></i>
                    </button>
                    <span class="apartado-preview"></span>
                </div>
                <div class="apartado-controls">
                    <div class="apartado-pts-field">
                        <label for="${ptsId}" class="visually-hidden">Puntaje del apartado *</label>
                        <input type="number" id="${ptsId}" min="1" max="100" step="1" class="form-control form-control-sm inp-puntaje" value="${escapeHtml(data.puntaje || '')}" placeholder="Pts *" aria-label="Puntaje del apartado" required>
                    </div>
                    <div class="apartado-detalle-field">
                        <label for="${detId}" class="visually-hidden">Desglose opcional de puntaje</label>
                        <input type="text" id="${detId}" class="form-control form-control-sm inp-detalle-puntaje" value="${escapeHtml(data.detalle_puntaje || '')}" placeholder="Desglose (ej. 5 c/u)" aria-label="Desglose opcional de puntaje">
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger btn-del-apartado" title="Eliminar apartado" aria-label="Eliminar apartado">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </div>
            <div class="apartado-body p-3">
                <div class="mb-3">
                    <label for="${objId}" class="form-label small fw-bold">Objetivos *</label>
                    <textarea id="${objId}" rows="2" class="form-control inp-objetivo" placeholder="Objetivo específico que evalúa este apartado..." required>${escapeHtml(data.objetivo || '')}</textarea>
                </div>
                <div class="row g-3">
                    <div class="col-lg-6">
                        <label for="${ejerId}" class="form-label small fw-bold">Ejercicios propuestos *</label>
                        <textarea id="${ejerId}" rows="7" class="form-control inp-ejercicios" placeholder="Redacte las instrucciones y todos los ejercicios / incisos numerados (1, 2, 3...)..." required>${escapeHtml(data.ejercicios || '')}</textarea>
                    </div>
                    <div class="col-lg-6">
                        <label for="${respId}" class="form-label small fw-bold">Posibles respuestas / Clave de corrección *</label>
                        <textarea id="${respId}" rows="7" class="form-control inp-respuestas" placeholder="Soluciones modelo, respuestas esperadas y criterios claros de evaluación..." required>${escapeHtml(data.posibles_respuestas || '')}</textarea>
                    </div>
                </div>
            </div>
        `;

        card.querySelectorAll('textarea, input').forEach((el) => {
            el.addEventListener('input', () => {
                el.classList.remove('is-invalid');
                actualizarMedidores();
                programarAutoguardado();
            });
        });

        card.querySelector('.btn-toggle-apartado').addEventListener('click', () => {
            setCardCollapsed(card, !card.classList.contains('is-collapsed'));
        });

        card.querySelector('.btn-del-apartado').addEventListener('click', () => {
            card.remove();
            renumerarApartados();
            programarAutoguardado();
        });

        container.appendChild(card);
        renumerarApartados();
    }

    function cargarItems(items) {
        container.innerHTML = '';
        if (Array.isArray(items) && items.length > 0) {
            items.forEach((it) => crearCardApartado(it));
        } else {
            crearCardApartado({});
            crearCardApartado({});
        }
    }

    function guardarBorradorLocal() {
        if (MODO_EDICION) return;
        try {
            const payload = {
                ts: Date.now(),
                fecha: document.getElementById('id_fecha')?.value || '',
                anio_lectivo: document.getElementById('id_anio_lectivo')?.value || '',
                trimestre: document.getElementById('id_trimestre')?.value || '',
                codigo_grupo: document.getElementById('id_codigo_grupo')?.value || '',
                carrera_texto: document.getElementById('id_carrera_texto')?.value || '',
                modalidad: document.getElementById('id_modalidad')?.value || '',
                tipo_examen: document.getElementById('id_tipo_examen')?.value || '',
                municipio: document.getElementById('id_municipio')?.value || '',
                hojas_objetivo_ia: hojasObjetivoUsadasIA,
                items: obtenerItemsDesdeDOM().map(({ numero, objetivo, ejercicios, posibles_respuestas, puntaje, detalle_puntaje }) => ({
                    numero, objetivo, ejercicios, posibles_respuestas, puntaje, detalle_puntaje
                }))
            };
            const hayContenido = payload.items.some((it) => !itemEsVacio(it)) || Boolean(payload.codigo_grupo.trim());
            if (!hayContenido) return;
            localStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
        } catch (_err) {
            // Ignorar errores de almacenamiento privado / cuota llena
        }
    }

    function programarAutoguardado() {
        if (MODO_EDICION) return;
        clearTimeout(draftTimer);
        draftTimer = setTimeout(guardarBorradorLocal, 400);
    }

    function limpiarBorradorLocal() {
        try {
            localStorage.removeItem(DRAFT_KEY);
        } catch (_err) {
            // Ignorar
        }
    }

    function intentarRestaurarBorrador() {
        if (MODO_EDICION || !draftBanner) return false;
        try {
            const raw = localStorage.getItem(DRAFT_KEY);
            if (!raw) return false;
            const draft = JSON.parse(raw);
            if (!draft || !Array.isArray(draft.items) || !draft.items.some((it) => !itemEsVacio(it))) {
                return false;
            }
            if (draft.fecha) document.getElementById('id_fecha').value = draft.fecha;
            if (draft.anio_lectivo) document.getElementById('id_anio_lectivo').value = draft.anio_lectivo;
            if (draft.trimestre) document.getElementById('id_trimestre').value = draft.trimestre;
            if (draft.codigo_grupo !== undefined) document.getElementById('id_codigo_grupo').value = draft.codigo_grupo;
            if (draft.carrera_texto) document.getElementById('id_carrera_texto').value = draft.carrera_texto;
            if (draft.modalidad) document.getElementById('id_modalidad').value = draft.modalidad;
            if (draft.tipo_examen) document.getElementById('id_tipo_examen').value = draft.tipo_examen;
            if (draft.municipio !== undefined) document.getElementById('id_municipio').value = draft.municipio;
            if (draft.hojas_objetivo_ia) hojasObjetivoUsadasIA = draft.hojas_objetivo_ia;

            cargarItems(draft.items);
            actualizarResumenMeta();

            if (draftTimeEl && draft.ts) {
                const fecha = new Date(draft.ts);
                draftTimeEl.textContent = fecha.toLocaleString('es-NI', {
                    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                });
            }
            draftBanner.classList.remove('d-none');
            return true;
        } catch (_err) {
            return false;
        }
    }

    async function parseJsonSafe(resp) {
        const text = await resp.text();
        if (!text) {
            throw new Error(`El servidor respondió sin contenido (HTTP ${resp.status}).`);
        }
        try {
            return JSON.parse(text);
        } catch (_err) {
            if (resp.status === 403) {
                throw new Error('Tu sesión o token de seguridad expiró (HTTP 403). Recarga la página e intenta nuevamente.');
            }
            if (resp.status >= 500) {
                throw new Error(`El servidor tardó demasiado o falló al procesar la solicitud (HTTP ${resp.status}). Intenta nuevamente.`);
            }
            throw new Error(`La respuesta del servidor no es válida (HTTP ${resp.status}). Verifica que tu sesión siga activa.`);
        }
    }

    function mostrarErrores(mensajes) {
        const lista = Array.isArray(mensajes) ? mensajes.filter(Boolean) : [mensajes];
        if (!lista.length) return;

        if (lista.length === 1) {
            errorAlert.textContent = lista[0];
        } else {
            errorAlert.innerHTML = '';
            const title = document.createElement('div');
            title.className = 'fw-bold mb-1';
            title.textContent = 'Revisa los siguientes puntos antes de guardar:';
            const ul = document.createElement('ul');
            ul.className = 'mb-0 ps-3';
            lista.forEach((msg) => {
                const li = document.createElement('li');
                li.textContent = msg;
                ul.appendChild(li);
            });
            errorAlert.appendChild(title);
            errorAlert.appendChild(ul);
        }
        errorAlert.classList.remove('d-none');
        errorAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function limpiarErroresVisuales() {
        errorAlert.classList.add('d-none');
        errorAlert.textContent = '';
        root.querySelectorAll('.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
    }

    // Listeners de encabezado e institucionales
    ['id_fecha', 'id_codigo_grupo', 'id_modalidad', 'id_tipo_examen',
     'id_anio_lectivo', 'id_trimestre', 'id_carrera_texto', 'id_municipio'].forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        const handler = () => {
            el.classList.remove('is-invalid');
            actualizarResumenMeta();
            programarAutoguardado();
        };
        el.addEventListener('input', handler);
        el.addEventListener('change', handler);
    });

    if (btnDescartarDraft) {
        btnDescartarDraft.addEventListener('click', () => {
            if (!window.confirm('¿Descartar el avance guardado localmente y empezar un examen en blanco?')) {
                return;
            }
            limpiarBorradorLocal();
            window.location.reload();
        });
    }

    document.getElementById('btn-agregar-apartado')?.addEventListener('click', () => {
        crearCardApartado({});
        programarAutoguardado();
    });

    // Generación con IA (4 a 8 hojas) con timeout de 120s y confirmación si ya hay texto
    const btnIA = document.getElementById('btn-generar-ia');
    if (btnIA) {
        btnIA.addEventListener('click', async () => {
            const statusEl = document.getElementById('ai-status-msg');
            const modelo = document.getElementById('ai-modelo-select').value;
            const hojas = document.getElementById('ai-hojas-select').value;

            const actuales = obtenerItemsDesdeDOM();
            if (actuales.some((it) => !itemEsVacio(it))) {
                if (!window.confirm('Los apartados actuales serán reemplazados por la propuesta generada con IA. ¿Deseas continuar?')) {
                    return;
                }
            }

            const btnOriginal = btnIA.innerHTML;
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);

            btnIA.disabled = true;
            btnIA.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generando...';
            statusEl.innerHTML = `<span class="text-primary fw-semibold"><i class="fas fa-hourglass-half me-1"></i>Diseñando examen de ${escapeHtml(hojas)} hojas con IA...</span>`;
            limpiarErroresVisuales();

            try {
                const formData = new FormData();
                formData.append('asignacion_id', String(ASIGNACION_ID));
                formData.append('numero_evaluacion', String(NUMERO_EVALUACION));
                formData.append('modelo_select', modelo);
                formData.append('numero_hojas', hojas);

                const resp = await fetch(URL_IA, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': CSRF_TOKEN },
                    body: formData,
                    signal: controller.signal
                });
                const json = await parseJsonSafe(resp);
                if (!resp.ok || !json.success) {
                    throw new Error(json.error || 'No se pudo generar el proyecto de examen con IA.');
                }

                const datos = json.datos || {};
                if (datos.fecha) document.getElementById('id_fecha').value = datos.fecha;
                if (datos.anio_lectivo) document.getElementById('id_anio_lectivo').value = datos.anio_lectivo;
                if (datos.trimestre) document.getElementById('id_trimestre').value = datos.trimestre;
                actualizarResumenMeta();

                hojasObjetivoUsadasIA = parseInt(hojas, 10) || 4;
                const itemsGen = Array.isArray(datos.items) ? datos.items : [];
                cargarItems(itemsGen);
                programarAutoguardado();

                const pagEst = datos.estimacion?.paginas_estimadas;
                const ptsGen = datos.puntaje_total ?? PUNTAJE_REQUERIDO;
                const sufijoPag = typeof pagEst === 'number' ? `, ~${pagEst} pág.` : '';
                statusEl.innerHTML = `<span class="text-success fw-semibold"><i class="fas fa-check-circle me-1"></i>Examen generado (${itemsGen.length} apartados, ${ptsGen} pts${sufijoPag}). Revisa y ajusta si deseas antes de guardar.</span>`;
            } catch (err) {
                const msg = err.name === 'AbortError'
                    ? 'La generación con IA superó el tiempo máximo de espera (120 s). Intenta nuevamente.'
                    : (err.message || 'Error inesperado al generar con IA.');
                statusEl.innerHTML = `<span class="text-danger fw-semibold"><i class="fas fa-exclamation-triangle me-1"></i>${escapeHtml(msg)}</span>`;
            } finally {
                clearTimeout(timeoutId);
                btnIA.disabled = false;
                btnIA.innerHTML = btnOriginal;
            }
        });
    }

    // Validación y envío del formulario
    document.getElementById('examen-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        limpiarErroresVisuales();

        if (BLOQUEADO_POR_PUNTAJE) {
            mostrarErrores(['No quedan puntos disponibles en este corte evaluativo. Ajusta tus sílabos o guías primero.']);
            return;
        }

        const errores = [];
        let primerCampoInvalido = null;

        const camposObligatorios = [
            { id: 'id_fecha', nombre: 'La fecha del examen es obligatoria.', enMeta: false },
            { id: 'id_anio_lectivo', nombre: 'El año lectivo es obligatorio.', enMeta: true },
            { id: 'id_trimestre', nombre: 'El trimestre es obligatorio.', enMeta: true },
            { id: 'id_carrera_texto', nombre: 'El campo Carrera(s) es obligatorio.', enMeta: true }
        ];

        for (const campo of camposObligatorios) {
            const el = document.getElementById(campo.id);
            if (!el || !el.value.trim()) {
                if (el) {
                    el.classList.add('is-invalid');
                    if (!primerCampoInvalido) primerCampoInvalido = el;
                }
                if (campo.enMeta && metaDetails) {
                    metaDetails.open = true;
                }
                errores.push(campo.nombre);
            }
        }

        const todosItems = obtenerItemsDesdeDOM();
        const itemsNoVacios = todosItems.filter((it) => !itemEsVacio(it));

        if (itemsNoVacios.length < MIN_ITEMS) {
            errores.push(`Debes completar al menos ${MIN_ITEMS} apartados en el examen.`);
            let faltanPorMarcar = MIN_ITEMS - itemsNoVacios.length;
            todosItems.forEach((it) => {
                if (faltanPorMarcar <= 0 || !itemEsVacio(it)) return;
                faltanPorMarcar -= 1;
                setCardCollapsed(it._card, false);
                ['.inp-puntaje', '.inp-objetivo', '.inp-ejercicios', '.inp-respuestas'].forEach((selector) => {
                    const el = it._card.querySelector(selector);
                    if (el) {
                        el.classList.add('is-invalid');
                        if (!primerCampoInvalido) primerCampoInvalido = el;
                    }
                });
            });
        }

        itemsNoVacios.forEach((it, idx) => {
            const labelNum = ROMANOS[idx] || String(idx + 1);
            const card = it._card;
            const faltantes = [];

            const checkField = (ok, selector, etiqueta) => {
                if (!ok) {
                    const el = card.querySelector(selector);
                    if (el) {
                        el.classList.add('is-invalid');
                        if (!primerCampoInvalido) primerCampoInvalido = el;
                    }
                    faltantes.push(etiqueta);
                }
            };

            checkField(it.puntaje > 0, '.inp-puntaje', 'Puntaje (> 0)');
            checkField(Boolean(it.objetivo), '.inp-objetivo', 'Objetivo');
            checkField(Boolean(it.ejercicios), '.inp-ejercicios', 'Ejercicios propuestos');
            checkField(Boolean(it.posibles_respuestas), '.inp-respuestas', 'Posibles respuestas');

            if (faltantes.length > 0) {
                setCardCollapsed(card, false);
                errores.push(`Apartado ${labelNum}: completa ${faltantes.join(', ')}.`);
            }
        });

        const sumaPts = itemsNoVacios.reduce((acc, it) => acc + (it.puntaje || 0), 0);
        if (sumaPts !== PUNTAJE_REQUERIDO) {
            errores.push(`La suma de puntajes (${sumaPts} pts) debe ser exactamente ${PUNTAJE_REQUERIDO} pts.`);
        }

        const est = estimarPaginas(itemsNoVacios);
        if (itemsNoVacios.length >= MIN_ITEMS && !est.cumple) {
            errores.push(
                `Extensión insuficiente (${est.paginas.toFixed(1)} páginas, ${est.charsUtiles} caracteres efectivos): ` +
                `debe superar las ${MIN_PAGINAS_EXCL.toFixed(1)} páginas con contenido completo.`
            );
        }

        if (errores.length > 0) {
            mostrarErrores(errores);
            if (primerCampoInvalido) {
                primerCampoInvalido.focus({ preventScroll: true });
            }
            return;
        }

        const itemsPayload = itemsNoVacios.map((it, idx) => ({
            numero: ROMANOS[idx] || String(idx + 1),
            objetivo: it.objetivo,
            ejercicios: it.ejercicios,
            posibles_respuestas: it.posibles_respuestas,
            puntaje: it.puntaje,
            detalle_puntaje: it.detalle_puntaje
        }));

        const payload = {
            examen_id: EXAMEN_ID,
            numero_evaluacion: NUMERO_EVALUACION,
            fecha: document.getElementById('id_fecha').value,
            anio_lectivo: document.getElementById('id_anio_lectivo').value.trim(),
            trimestre: document.getElementById('id_trimestre').value.trim(),
            codigo_grupo: document.getElementById('id_codigo_grupo').value.trim(),
            carrera_texto: document.getElementById('id_carrera_texto').value.trim(),
            modalidad: document.getElementById('id_modalidad').value,
            tipo_examen: document.getElementById('id_tipo_examen').value,
            municipio: document.getElementById('id_municipio').value.trim(),
            hojas_objetivo_ia: hojasObjetivoUsadasIA,
            items: itemsPayload
        };

        btnGuardar.disabled = true;
        btnGuardar.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Guardando...';

        try {
            const resp = await fetch(URL_GUARDAR, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify(payload)
            });
            const json = await parseJsonSafe(resp);
            if (!resp.ok || !json.success) {
                const serverErrors = Array.isArray(json.errors) && json.errors.length
                    ? json.errors
                    : [json.error || 'Error al guardar el proyecto de examen.'];
                mostrarErrores(serverErrors);
                btnGuardar.disabled = false;
                btnGuardar.innerHTML = saveBtnOriginalHtml;
                return;
            }
            limpiarBorradorLocal();
            window.location.href = json.redirect_url;
        } catch (err) {
            mostrarErrores([err.message || 'Error de conexión al guardar el proyecto de examen.']);
            btnGuardar.disabled = false;
            btnGuardar.innerHTML = saveBtnOriginalHtml;
        }
    });

    // Inicialización segura mediante json_script
    let iniciales = [];
    const dataScript = document.getElementById('examen-items-iniciales');
    if (dataScript && dataScript.textContent) {
        try {
            iniciales = JSON.parse(dataScript.textContent);
        } catch (_err) {
            iniciales = [];
        }
    }

    if (!intentarRestaurarBorrador()) {
        cargarItems(iniciales);
        actualizarResumenMeta();
    }
})();
