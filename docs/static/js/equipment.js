/**
 * Mind Equip — Equipment Detail & Document Controller
 * Strict Instrument Architecture (Teenage Engineering / Anduril / Apple)
 * 100% Offline, Zero CDN, Vanilla ES6
 */

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('equipment-container');
  if (!container) return;

  const equipmentId = container.getAttribute('data-equipment-id');
  if (!equipmentId) {
    console.error('Equipment ID is missing in data-equipment-id');
    return;
  }

  // --- DOM Elements ---
  const tabButtons = document.querySelectorAll('.segmented-item');
  const tabViews = document.querySelectorAll('.tab-view');

  // Header Elements
  const equipTitle = document.getElementById('equip-title');
  const equipInvNum = document.getElementById('equip-inv-num');
  const equipStatusChip = document.getElementById('equip-status-chip');
  const equipStatusText = document.getElementById('equip-status-text');
  const equipLocation = document.getElementById('equip-location');
  const equipModel = document.getElementById('equip-model');
  const equipSerial = document.getElementById('equip-serial');
  const equipMfr = document.getElementById('equip-mfr');
  const equipYear = document.getElementById('equip-year');
  const btnShowQrSticker = document.getElementById('btn-show-qr-sticker');
  const btnEquipBudgetPdf = document.getElementById('btn-equip-budget-pdf');

  // Alert Banner
  const equipAlertBanner = document.getElementById('equip-alert-banner');
  const equipAlertHeadline = document.getElementById('equip-alert-headline');
  const equipAlertDetails = document.getElementById('equip-alert-details');
  const equipAlertSum = document.getElementById('equip-alert-sum');
  const btnEquipTabBudget = document.getElementById('btn-equip-tab-budget');
  const btnEquipAlertPdf = document.getElementById('btn-equip-alert-pdf');

  // Documents Elements
  const docsPassportList = document.getElementById('docs-passport-list');
  const docsDiagnosticsList = document.getElementById('docs-diagnostics-list');
  const docsScheduleList = document.getElementById('docs-schedule-list');
  const docsDefectsList = document.getElementById('docs-defects-list');
  const docFileUploadInput = document.getElementById('doc-file-upload-input');
  const btnGenerateSchedulePdf = document.getElementById('btn-generate-schedule-pdf');
  const btnGenerateDefectPdfFromDocs = document.getElementById('btn-generate-defect-pdf-from-docs');

  // Maintenance Elements
  const equipMetricMaterials = document.getElementById('equip-metric-materials');
  const equipMetricServices = document.getElementById('equip-metric-services');
  const equipMetricTotal = document.getElementById('equip-metric-total');
  const btnDownloadMaintBudgetPdf = document.getElementById('btn-download-maint-budget-pdf');
  const btnToggleAddMaint = document.getElementById('btn-toggle-add-maint');
  const panelAddMaint = document.getElementById('panel-add-maint');
  const btnCancelAddMaint = document.getElementById('btn-cancel-add-maint');
  const formAddMaintenance = document.getElementById('form-add-maintenance');
  const maintMaterialsRows = document.getElementById('maint-materials-rows');
  const btnAddMaterialRow = document.getElementById('btn-add-material-row');
  const maintTasksContainer = document.getElementById('maint-tasks-container');
  const maintHistoryContainer = document.getElementById('maint-history-container');

  // Photos Elements
  const formUploadPhoto = document.getElementById('form-upload-photo');
  const btnSelectPhoto = document.getElementById('btn-select-photo');
  const inpPhotoFile = document.getElementById('inp-photo-file');
  const photoFilenameLabel = document.getElementById('photo-filename-label');
  const photoPreviewImg = document.getElementById('photo-preview-img');
  const btnSubmitPhoto = document.getElementById('btn-submit-photo');
  const conditionChips = document.querySelectorAll('.condition-chip');
  const inpPhotoCondition = document.getElementById('inp-photo-condition');
  const photosTotalCount = document.getElementById('photos-total-count');
  const photosGalleryContainer = document.getElementById('photos-gallery-container');

  // Defects Elements
  const defectsBadge = document.getElementById('defects-badge');
  const btnGenerateDefectPdf = document.getElementById('btn-generate-defect-pdf');
  const btnToggleAddDefect = document.getElementById('btn-toggle-add-defect');
  const panelAddDefect = document.getElementById('panel-add-defect');
  const btnCancelAddDefect = document.getElementById('btn-cancel-add-defect');
  const formAddDefect = document.getElementById('form-add-defect');
  const defectsListContainer = document.getElementById('defects-list-container');

  // Modals
  const modalCompleteMaint = document.getElementById('modal-complete-maint');
  const btnCloseCompleteModal = document.getElementById('btn-close-complete-modal');
  const btnCancelCompleteModal = document.getElementById('btn-cancel-complete-modal');
  const formCompleteMaint = document.getElementById('form-complete-maint');
  const inpCompleteTaskId = document.getElementById('inp-complete-task-id');
  const completeTaskDisplayName = document.getElementById('complete-task-display-name');
  const inpCompleteDate = document.getElementById('inp-complete-date');

  const modalQrSticker = document.getElementById('modal-qr-sticker');
  const btnCloseQrModal = document.getElementById('btn-close-qr-modal');
  const qrModalImage = document.getElementById('qr-modal-image');
  const qrModalInv = document.getElementById('qr-modal-inv');
  const qrModalDownloadLink = document.getElementById('qr-modal-download-link');
  const btnRotateQrToken = document.getElementById('btn-rotate-qr-token');

  const lightboxModal = document.getElementById('lightbox-modal');
  const btnCloseLightbox = document.getElementById('btn-close-lightbox');
  const lightboxImage = document.getElementById('lightbox-image');
  const lightboxCaption = document.getElementById('lightbox-caption');

  // State
  let activeUploadCategory = 'passport';
  let cachedData = null;

  // --- Helpers ---
  function formatTenge(amount) {
    const num = Math.round(Number(amount) || 0);
    return num.toLocaleString('ru-RU') + ' ₸';
  }
  const formatRubles = formatTenge;

  function formatDate(isoStr) {
    if (!isoStr) return '—';
    try {
      const parts = isoStr.split('-');
      if (parts.length === 3) {
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
      }
    } catch (_) {}
    return isoStr;
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      if (!isNaN(d.getTime())) {
        return d.toLocaleDateString('ru-RU') + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
      }
    } catch (_) {}
    return isoStr;
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Tab Navigation ---
  function switchTab(targetViewId) {
    tabButtons.forEach(btn => {
      const isTarget = btn.getAttribute('data-target') === targetViewId;
      btn.classList.toggle('active', isTarget);
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });

    tabViews.forEach(view => {
      if (view.id === targetViewId) {
        view.style.display = 'block';
        view.classList.add('active');
      } else {
        view.style.display = 'none';
        view.classList.remove('active');
      }
    });
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-target');
      if (target) switchTab(target);
    });
  });

  if (btnEquipTabBudget) {
    btnEquipTabBudget.addEventListener('click', () => {
      switchTab('section-maint');
    });
  }

  // --- Fetch & Render Equipment Data ---
  async function loadEquipmentData() {
    try {
      const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}`);
      if (!res.ok) {
        if (res.status === 404) {
          window.location.href = '404.html';
          return;
        }
        throw new Error('HTTP ' + res.status);
      }

      const data = await res.json();
      cachedData = data;

      renderHeader(data);
      renderDocuments(data.documents || {});
      renderMaintenance(data);
      renderPhotos(data.equipment.photos || []);
      renderDefects(data.equipment.defects || []);
    } catch (err) {
      console.error('Error loading equipment:', err);
      if (equipTitle) {
        equipTitle.textContent = 'Ошибка загрузки данных оборудования';
      }
    }
  }

  // --- 1. Render Header & Alerts ---
  function renderHeader(data) {
    const eq = data.equipment;
    const ev = data.evaluation || {};

    if (equipTitle) equipTitle.textContent = eq.name;
    if (equipInvNum) equipInvNum.textContent = `ИНВ: ${eq.inventory_number}`;
    if (equipLocation) equipLocation.textContent = eq.location || '—';
    if (equipModel) equipModel.textContent = eq.model || '—';
    if (equipSerial) equipSerial.textContent = eq.serial_number || '—';
    if (equipMfr) equipMfr.textContent = eq.manufacturer || '—';
    if (equipYear) equipYear.textContent = eq.commission_year ? String(eq.commission_year) : '—';

    // Status Chip
    const status = eq.status || 'good';
    if (equipStatusChip && equipStatusText) {
      equipStatusChip.className = `status-chip ${status === 'good' ? 'good' : (status === 'critical' ? 'critical' : 'attention')}`;
      equipStatusText.textContent = status === 'good' ? 'Исправно' : (status === 'critical' ? 'Критический дефект' : 'Требует внимания');
    }

    // Budget PDF Links
    const budgetPdfUrl = `reports/plan_${encodeURIComponent(equipmentId)}.pdf`;
    if (btnEquipBudgetPdf) btnEquipBudgetPdf.href = budgetPdfUrl;
    if (btnEquipAlertPdf) btnEquipAlertPdf.href = budgetPdfUrl;
    if (btnDownloadMaintBudgetPdf) btnDownloadMaintBudgetPdf.href = budgetPdfUrl;

    // Check Upcoming / Overdue Maintenance Alert
    const urgentAlerts = ev.urgent_alerts || [];
    const budgetAlerts = ev.budget_alerts || [];
    const hasAlert = urgentAlerts.length > 0 || budgetAlerts.length > 0;

    if (hasAlert && equipAlertBanner) {
      equipAlertBanner.style.display = 'flex';

      if (urgentAlerts.length > 0) {
        equipAlertBanner.classList.add('critical-mode');
        if (equipAlertHeadline) equipAlertHeadline.textContent = 'Внимание: Срочное или просроченное ТО!';
      } else {
        equipAlertBanner.classList.remove('critical-mode');
        if (equipAlertHeadline) equipAlertHeadline.textContent = 'Скоро плановое ТО';
      }
    } else if (equipAlertBanner) {
      equipAlertBanner.style.display = 'none';
    }

    // Configure Secure QR Sticker Modal
    const secureQrUrl = `qr/${encodeURIComponent(equipmentId)}.png`;

    if (btnShowQrSticker) {
      btnShowQrSticker.onclick = () => {
        if (qrModalImage) qrModalImage.src = `${secureQrUrl}?t=${Date.now()}`;
        if (qrModalInv) qrModalInv.textContent = `${eq.name} (${eq.inventory_number})`;
        if (qrModalDownloadLink) qrModalDownloadLink.href = secureQrUrl;
        if (modalQrSticker) modalQrSticker.classList.add('open');
      };
    }

    if (btnRotateQrToken) {
      btnRotateQrToken.onclick = async () => {
        const confirmed = confirm(
          'ВНИМАНИЕ: Вы действительно хотите перевыпустить защищённый токен QR?\n\n' +
          'Старый распечатанный QR-код агрегата немедленно перестанет распознаваться приложением. ' +
          'Вам потребуется распечатать и наклеить новую этикетку.'
        );
        if (!confirmed) return;

        btnRotateQrToken.disabled = true;
        btnRotateQrToken.textContent = 'Генерация...';

        try {
          const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/rotate-qr`, {
            method: 'POST'
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Ошибка перевыпуска токена');
          }

          const data = await res.json();
          const freshUrl = `${secureQrUrl}?t=${Date.now()}`;
          if (qrModalImage) qrModalImage.src = freshUrl;
          if (qrModalDownloadLink) qrModalDownloadLink.href = freshUrl;
          alert(`Новый защищённый токен QR успешно сгенерирован!\nКлюч: ${data.token}`);
        } catch (err) {
          console.error('Rotate QR error:', err);
          alert('Не удалось перевыпустить токен: ' + err.message);
        } finally {
          btnRotateQrToken.disabled = false;
          btnRotateQrToken.textContent = '🔄 Перевыпустить токен';
        }
      };
    }
  }

  // --- 2. Render Documents Section ---
  function renderDocuments(docs) {
    renderDocCategory('passport', docs.passport || [], docsPassportList, 'Паспорт оборудования не загружен. Прикрепите заводской или эксплуатационный PDF-паспорт.');
    renderDocCategory('diagnostics', docs.diagnostics || [], docsDiagnosticsList, 'Документы диагностики отсутствуют (протоколы вибродиагностики, тепловизионного или неразрушающего контроля загружаются по мере проведения).');
    renderDocCategory('schedule', docs.schedule || [], docsScheduleList, 'Графики ТО в формате PDF отсутствуют. Вы можете сформировать график кнопкой выше или загрузить файл.');
    renderDocCategory('defects', docs.defects || [], docsDefectsList, 'Дефектные ведомости в формате PDF отсутствуют. Вы можете сформировать ведомость кнопкой выше.');
  }

  function renderDocCategory(categoryKey, files, containerElem, emptyNoticeText) {
    if (!containerElem) return;

    if (files.length === 0) {
      containerElem.innerHTML = `<div class="empty-state-notice">${escapeHtml(emptyNoticeText)}</div>`;
      return;
    }

    containerElem.innerHTML = files.map(f => `
      <div class="file-item-card">
        <div class="file-info">
          <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <div class="file-meta-col">
            <div class="file-name" title="${escapeHtml(f.filename)}">${escapeHtml(f.filename)}</div>
            <div class="file-subtext">${escapeHtml(f.size_human || '')} · ${formatDateTime(f.modified_at)}</div>
          </div>
        </div>
        <div class="file-actions">
          <a href="${escapeHtml(f.view_url || f.download_url)}" target="_blank" class="btn btn-ghost btn-sm" title="Открыть в браузере">
            Открыть
          </a>
          <a href="${escapeHtml(f.download_url)}" download class="btn btn-primary btn-sm" title="Скачать PDF">
            Скачать PDF
          </a>
        </div>
      </div>
    `).join('');
  }

  // Document Upload Trigger
  window.triggerDocUpload = function(category) {
    activeUploadCategory = category;
    if (docFileUploadInput) {
      docFileUploadInput.value = '';
      docFileUploadInput.click();
    }
  };

  if (docFileUploadInput) {
    docFileUploadInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/documents/${encodeURIComponent(activeUploadCategory)}`, {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка загрузки документа');
        }

        await loadEquipmentData();
      } catch (err) {
        console.error('Doc upload error:', err);
        alert('Не удалось загрузить PDF: ' + err.message);
      }
    });
  }

  // Generate Schedule PDF Action
  if (btnGenerateSchedulePdf) {
    btnGenerateSchedulePdf.addEventListener('click', async () => {
      btnGenerateSchedulePdf.disabled = true;
      btnGenerateSchedulePdf.textContent = 'Формирование...';
      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/schedule/generate-pdf`, {
          method: 'POST'
        });
        if (!res.ok) throw new Error('Ошибка генерации графика');
        await loadEquipmentData();
        alert('График ТО успешно сформирован и сохранён в формате PDF!');
      } catch (err) {
        console.error('Schedule PDF error:', err);
        alert('Не удалось сформировать график ТО: ' + err.message);
      } finally {
        btnGenerateSchedulePdf.disabled = false;
        btnGenerateSchedulePdf.textContent = 'Сформировать график ТО в PDF';
      }
    });
  }

  // Generate Defect PDF Action
  const generateDefectPdfHandler = async (btnElem) => {
    btnElem.disabled = true;
    const oldText = btnElem.textContent;
    btnElem.textContent = 'Формирование...';
    try {
      const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/defects/generate-pdf`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Ошибка генерации ведомости');
      }
      await loadEquipmentData();
      alert('Дефектная ведомость успешно сформирована и добавлена в архив PDF!');
    } catch (err) {
      console.error('Defect PDF error:', err);
      alert('Не удалось сформировать дефектную ведомость: ' + err.message);
    } finally {
      btnElem.disabled = false;
      btnElem.textContent = oldText;
    }
  };

  if (btnGenerateDefectPdf) {
    btnGenerateDefectPdf.addEventListener('click', () => generateDefectPdfHandler(btnGenerateDefectPdf));
  }
  if (btnGenerateDefectPdfFromDocs) {
    btnGenerateDefectPdfFromDocs.addEventListener('click', () => generateDefectPdfHandler(btnGenerateDefectPdfFromDocs));
  }

  // --- 3. Render Maintenance Section ---
  function renderMaintenance(data) {
    const ev = data.evaluation || {};
    const tasks = data.equipment.maintenance_tasks || [];
    const history = data.equipment.maintenance_history || [];

    // Update Metric Cards
    const elTasksCount = document.getElementById('equip-metric-tasks-count');
    const elDeficitCount = document.getElementById('equip-metric-deficit-count');
    const elDefectsCount = document.getElementById('equip-metric-defects-count');

    let totalDeficitPositions = 0;
    tasks.forEach(t => {
      (t.materials || []).forEach(m => {
        if ((Number(m.qty_required) || 0) > (Number(m.qty_in_stock) || 0)) {
          totalDeficitPositions++;
        }
      });
    });

    const openDefects = (data.equipment.defects || []).filter(d => d.status === 'open');

    if (elTasksCount) elTasksCount.textContent = tasks.length;
    if (elDeficitCount) {
      elDeficitCount.textContent = totalDeficitPositions;
      elDeficitCount.className = 'metric-value mono' + (totalDeficitPositions > 0 ? ' qty-deficit-warn' : '');
    }
    if (elDefectsCount) {
      elDefectsCount.textContent = openDefects.length;
      elDefectsCount.className = 'metric-value mono' + (openDefects.length > 0 ? ' alert-urgent' : '');
    }

    // Render Tasks
    if (maintTasksContainer) {
      if (tasks.length === 0) {
        maintTasksContainer.innerHTML = `
          <div class="empty-state-notice">
            Виды технического обслуживания пока не заведены. Нажмите «+ Добавить вид ТО и материалы».
          </div>
        `;
      } else {
        const today = new Date().toISOString().slice(0, 10);

        maintTasksContainer.innerHTML = tasks.map(task => {
          // Calculate days until next due
          let daysLeft = null;
          let isOverdue = false;
          let isUrgent = false;

          if (task.next_due_date) {
            const dueMs = new Date(task.next_due_date).getTime();
            const nowMs = new Date(today).getTime();
            daysLeft = Math.round((dueMs - nowMs) / (1000 * 60 * 60 * 24));
            if (daysLeft < 0) isOverdue = true;
            else if (daysLeft <= 7) isUrgent = true;
          }

          let statusBadgeText = 'В графике';
          let statusBadgeStyle = 'background: var(--state-good-bg); color: var(--state-good); border: 1px solid var(--state-good-border);';

          if (isOverdue) {
            statusBadgeText = `Просрочено на ${Math.abs(daysLeft)} дн.`;
            statusBadgeStyle = 'background: var(--state-crit-bg); color: var(--state-crit); border: 1px solid var(--state-crit-border);';
          } else if (isUrgent) {
            statusBadgeText = `Срочно ТО (${daysLeft} дн.)`;
            statusBadgeStyle = 'background: var(--state-crit-bg); color: var(--state-crit); border: 1px solid var(--state-crit-border);';
          } else if (daysLeft !== null && daysLeft <= 30) {
            statusBadgeText = `Скоро ТО (${daysLeft} дн.)`;
            statusBadgeStyle = 'background: var(--state-warn-bg); color: var(--state-warn); border: 1px solid var(--state-warn-border);';
          }

          // Materials Table Calculation
          const materials = task.materials || [];
          let taskDeficitCount = 0;

          const materialsHtml = materials.length > 0 ? `
            <div class="table-responsive-container">
              <table class="instrument-table">
                <thead>
                  <tr>
                    <th>Наименование ТМЦ</th>
                    <th>Артикул / ГОСТ</th>
                    <th>Норма</th>
                    <th>На складе</th>
                    <th>Дефицит к поставке</th>
                  </tr>
                </thead>
                <tbody>
                  ${materials.map(m => {
                    const req = Number(m.qty_required) || 0;
                    const stock = Number(m.qty_in_stock) || 0;
                    const deficit = Math.max(0, req - stock);
                    if (deficit > 0) taskDeficitCount++;

                    return `
                      <tr>
                        <td style="font-weight: 500;">${escapeHtml(m.name)}</td>
                        <td class="mono" style="color: var(--text-muted);">${escapeHtml(m.sku || '—')}</td>
                        <td class="mono">${req} ${escapeHtml(m.unit || 'шт.')}</td>
                        <td class="mono">${stock} ${escapeHtml(m.unit || 'шт.')}</td>
                        <td class="mono ${deficit > 0 ? 'qty-deficit-warn' : ''}">
                          ${deficit > 0 ? `▲ ${deficit} ${escapeHtml(m.unit || 'шт.')}` : '<span style="color: var(--state-good);">0 (норма)</span>'}
                        </td>
                      </tr>
                    `;
                  }).join('')}
                </tbody>
              </table>
            </div>
          ` : '<div class="empty-state-notice" style="padding: 6px 0;">Нормы расхода материалов не заданы.</div>';

          return `
            <div class="task-card">
              <div class="task-card-header">
                <div>
                  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                    <span class="task-code-badge">${escapeHtml(task.code)}</span>
                    <span class="task-title">${escapeHtml(task.title)}</span>
                  </div>
                  <div style="font-size: 13px; color: var(--text-secondary);">
                    Периодичность: <strong>${task.interval_days} дн.</strong> · Ответственный: ${escapeHtml(task.responsible || '—')}
                  </div>
                </div>
                <span class="mono" style="font-size: 12px; font-weight: 600; padding: 4px 8px; border-radius: var(--radius-xs); ${statusBadgeStyle}">
                  ${statusBadgeText}
                </span>
              </div>

              <div class="task-meta-grid">
                <div>
                  <span style="color: var(--text-muted);">Последнее ТО:</span>
                  <span class="mono" style="color: var(--text-primary); margin-left: 4px;">${formatDate(task.last_completed_date)}</span>
                </div>
                <div>
                  <span style="color: var(--text-muted);">Следующее ТО:</span>
                  <span class="mono" style="color: var(--text-primary); margin-left: 4px;">${formatDate(task.next_due_date)}</span>
                </div>
              </div>

              <div style="font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-top: 8px;">
                Материалы и ЗИП для проведения ТО:
              </div>
              ${materialsHtml}

              <div class="task-footer-cost">
                <div style="font-size: 13.5px;">
                  ${taskDeficitCount > 0 ? `<span style="color: var(--state-warn); font-weight: 600;">▲ Дефицит ЗИП: ${taskDeficitCount} поз. к поставке</span>` : '<span style="color: var(--state-good); font-weight: 500;">✓ ЗИП укомплектован на 100%</span>'}
                </div>
                <button type="button" class="btn btn-primary btn-sm" onclick="openCompleteMaintModal('${escapeHtml(task.id)}', '${escapeHtml(task.code)} — ${escapeHtml(task.title)}')">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  Отметить ТО выполненным
                </button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Render History
    if (maintHistoryContainer) {
      if (history.length === 0) {
        maintHistoryContainer.innerHTML = '<div class="empty-state-notice">Записей об истории выполнения ТО пока нет.</div>';
      } else {
        maintHistoryContainer.innerHTML = history.slice().reverse().map(h => `
          <div style="padding: 10px 0; border-bottom: 1px solid var(--hairline); font-size: 13.5px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="color: var(--text-primary);">${escapeHtml(h.task_code)}</strong> — ${escapeHtml(h.task_title)}
              </div>
              <span class="mono" style="color: var(--text-muted); font-size: 12.5px;">${formatDate(h.completed_at)}</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 13px; margin-top: 2px;">
              Исполнитель: ${escapeHtml(h.performer || 'Дежурный инженер')}
              ${h.comment ? `· <span style="font-style: italic;">«${escapeHtml(h.comment)}»</span>` : ''}
            </div>
          </div>
        `).join('');
      }
    }
  }

  // Complete Maintenance Modal
  window.openCompleteMaintModal = function(taskId, taskLabel) {
    if (inpCompleteTaskId) inpCompleteTaskId.value = taskId;
    if (completeTaskDisplayName) completeTaskDisplayName.textContent = taskLabel;
    if (inpCompleteDate) inpCompleteDate.value = new Date().toISOString().slice(0, 10);
    if (modalCompleteMaint) modalCompleteMaint.classList.add('open');
  };

  function closeCompleteMaintModal() {
    if (modalCompleteMaint) modalCompleteMaint.classList.remove('open');
    if (formCompleteMaint) formCompleteMaint.reset();
  }

  if (btnCloseCompleteModal) btnCloseCompleteModal.addEventListener('click', closeCompleteMaintModal);
  if (btnCancelCompleteModal) btnCancelCompleteModal.addEventListener('click', closeCompleteMaintModal);

  if (formCompleteMaint) {
    formCompleteMaint.addEventListener('submit', async (e) => {
      e.preventDefault();
      const taskId = inpCompleteTaskId.value;
      if (!taskId) return;

      const payload = {
        performer: document.getElementById('inp-complete-performer').value.trim(),
        completed_date: inpCompleteDate.value || null,
        comment: document.getElementById('inp-complete-comment').value.trim(),
        restock_used_materials: document.getElementById('inp-complete-restock').checked
      };

      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/maintenance/${encodeURIComponent(taskId)}/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка сохранения отметки');
        }

        closeCompleteMaintModal();
        await loadEquipmentData();
        alert('Выполнение ТО успешно зафиксировано! Следующая плановая дата пересчитана.');
      } catch (err) {
        console.error('Complete maint error:', err);
        alert('Не удалось отметить ТО: ' + err.message);
      }
    });
  }

  // Toggle & Dynamic Materials for Add Maintenance Form
  if (btnToggleAddMaint && panelAddMaint) {
    btnToggleAddMaint.addEventListener('click', () => {
      panelAddMaint.style.display = panelAddMaint.style.display === 'none' ? 'block' : 'none';
      if (panelAddMaint.style.display === 'block') {
        const nextDate = new Date();
        nextDate.setDate(nextDate.getDate() + 30);
        const inpNext = document.getElementById('inp-maint-next-date');
        if (inpNext && !inpNext.value) {
          inpNext.value = nextDate.toISOString().slice(0, 10);
        }
      }
    });
  }

  if (btnCancelAddMaint && panelAddMaint) {
    btnCancelAddMaint.addEventListener('click', () => {
      panelAddMaint.style.display = 'none';
      if (formAddMaintenance) formAddMaintenance.reset();
      if (maintMaterialsRows) maintMaterialsRows.innerHTML = '';
    });
  }

  function addMaterialRow() {
    if (!maintMaterialsRows) return;
    const rowId = 'mat-row-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);
    const rowDiv = document.createElement('div');
    rowDiv.className = 'mat-row';
    rowDiv.id = rowId;
    rowDiv.style.display = 'grid';
    rowDiv.style.gridTemplateColumns = '2fr 1.2fr 0.8fr 1fr 1fr 36px';
    rowDiv.style.gap = '6px';
    rowDiv.style.alignItems = 'center';

    rowDiv.innerHTML = `
      <input type="text" class="form-input row-mat-name" placeholder="Наименование (напр. Масло турбинное)" required style="padding: 6px 8px; font-size: 14px;">
      <input type="text" class="form-input row-mat-sku" placeholder="Артикул / ГОСТ" style="padding: 6px 8px; font-size: 14px;">
      <input type="text" class="form-input row-mat-unit" value="л" placeholder="Ед." style="padding: 6px 8px; font-size: 14px;">
      <input type="number" step="any" min="0.01" class="form-input mono row-mat-qty" placeholder="Норма" required style="padding: 6px 8px; font-size: 14px;">
      <input type="number" step="any" min="0" class="form-input mono row-mat-stock" placeholder="Склад" value="0" style="padding: 6px 8px; font-size: 14px;">
      <button type="button" class="btn btn-ghost btn-sm" onclick="document.getElementById('${rowId}').remove()" style="padding: 0; color: var(--state-crit);" title="Удалить строку">✕</button>
    `;
    maintMaterialsRows.appendChild(rowDiv);
  }

  if (btnAddMaterialRow) {
    btnAddMaterialRow.addEventListener('click', addMaterialRow);
  }

  if (formAddMaintenance) {
    formAddMaintenance.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Collect materials
      const materialRows = maintMaterialsRows ? maintMaterialsRows.querySelectorAll('.mat-row') : [];
      const materials = [];
      materialRows.forEach(row => {
        const name = row.querySelector('.row-mat-name').value.trim();
        const sku = row.querySelector('.row-mat-sku').value.trim();
        const unit = row.querySelector('.row-mat-unit').value.trim() || 'шт.';
        const qty_required = parseFloat(row.querySelector('.row-mat-qty').value) || 1;
        const qty_in_stock = parseFloat(row.querySelector('.row-mat-stock')?.value) || 0;
        if (name) {
          materials.push({ name, sku, unit, qty_required, qty_in_stock, unit_price_rub: 0 });
        }
      });

      const payload = {
        code: document.getElementById('inp-maint-code').value.trim(),
        title: document.getElementById('inp-maint-title').value.trim(),
        interval_days: parseInt(document.getElementById('inp-maint-interval').value, 10) || 30,
        next_due_date: document.getElementById('inp-maint-next-date').value,
        service_cost_rub: 0,
        materials,
        notes: ''
      };

      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/maintenance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка добавления ТО');
        }

        if (panelAddMaint) panelAddMaint.style.display = 'none';
        formAddMaintenance.reset();
        if (maintMaterialsRows) maintMaterialsRows.innerHTML = '';
        await loadEquipmentData();
      } catch (err) {
        console.error('Add maint error:', err);
        alert('Не удалось добавить регламент ТО: ' + err.message);
      }
    });
  }

  // --- 4. Render Photo Inspection Section ---
  function renderPhotos(photos) {
    if (photosTotalCount) photosTotalCount.textContent = `(${photos.length})`;

    if (!photosGalleryContainer) return;

    if (photos.length === 0) {
      photosGalleryContainer.innerHTML = `
        <div class="empty-state-notice" style="grid-column: 1 / -1; text-align: center; padding: 24px;">
          Фотографий технического состояния пока нет. Вы можете сделать снимок на камеру смартфона прямо сейчас.
        </div>
      `;
      return;
    }

    photosGalleryContainer.innerHTML = photos.slice().reverse().map(p => {
      const conditionClass = p.condition === 'good' ? 'good' : (p.condition === 'critical' ? 'critical' : 'attention');
      const conditionText = p.condition === 'good' ? 'Исправно' : (p.condition === 'critical' ? 'Критический дефект' : 'Внимание');

      return `
        <div class="photo-card">
          <div class="photo-thumb-wrap" onclick="openLightbox('${escapeHtml(p.url)}', '${escapeHtml(p.node || 'Осмотр')}: ${escapeHtml(p.comment || '')} (${formatDateTime(p.created_at)})')">
            <img src="${escapeHtml(p.url)}" alt="${escapeHtml(p.node || 'Фото осмотра')}" class="photo-thumb-img" loading="lazy">
          </div>
          <div class="photo-card-info">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span class="status-chip ${conditionClass}" style="font-size: 11px; padding: 2px 6px;">
                ${conditionText}
              </span>
              <span class="mono" style="font-size: 11px; color: var(--text-muted);">${formatDateTime(p.created_at)}</span>
            </div>
            ${p.node ? `<div style="font-size: 13px; font-weight: 600; color: var(--text-primary); margin-top: 2px;">${escapeHtml(p.node)}</div>` : ''}
            ${p.comment ? `<div style="font-size: 12px; color: var(--text-secondary); line-height: 1.35;">${escapeHtml(p.comment)}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  // Condition selector chips in photo form
  conditionChips.forEach(chip => {
    chip.addEventListener('click', () => {
      conditionChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (inpPhotoCondition) {
        inpPhotoCondition.value = chip.getAttribute('data-val');
      }
    });
  });

  // Photo file picker and preview
  if (btnSelectPhoto && inpPhotoFile) {
    btnSelectPhoto.addEventListener('click', () => inpPhotoFile.click());

    inpPhotoFile.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      if (photoFilenameLabel) photoFilenameLabel.textContent = file.name;

      const reader = new FileReader();
      reader.onload = (loadEvent) => {
        if (photoPreviewImg) {
          photoPreviewImg.src = loadEvent.target.result;
          photoPreviewImg.classList.add('visible');
        }
        if (btnSubmitPhoto) btnSubmitPhoto.style.display = 'block';
      };
      reader.readAsDataURL(file);
    });
  }

  if (formUploadPhoto) {
    formUploadPhoto.addEventListener('submit', async (e) => {
      e.preventDefault();
      const file = inpPhotoFile.files && inpPhotoFile.files[0];
      if (!file) {
        alert('Пожалуйста, выберите снимок или сделайте фото.');
        return;
      }

      if (btnSubmitPhoto) {
        btnSubmitPhoto.disabled = true;
        btnSubmitPhoto.textContent = 'Сохранение снимка...';
      }

      const formData = new FormData();
      formData.append('file', file);
      formData.append('condition', inpPhotoCondition ? inpPhotoCondition.value : 'good');
      formData.append('node', document.getElementById('inp-photo-node').value.trim());
      formData.append('comment', document.getElementById('inp-photo-comment').value.trim());

      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/photos`, {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка сохранения снимка');
        }

        formUploadPhoto.reset();
        if (photoPreviewImg) photoPreviewImg.classList.remove('visible');
        if (photoFilenameLabel) photoFilenameLabel.textContent = 'Файл не выбран';
        if (btnSubmitPhoto) btnSubmitPhoto.style.display = 'none';

        await loadEquipmentData();
        alert('Фотоосмотр успешно сохранён в локальную базу!');
      } catch (err) {
        console.error('Photo save error:', err);
        alert('Не удалось сохранить фото: ' + err.message);
      } finally {
        if (btnSubmitPhoto) {
          btnSubmitPhoto.disabled = false;
          btnSubmitPhoto.textContent = 'Зафиксировать осмотр в базе';
        }
      }
    });
  }

  // --- 5. Render Defects Section ---
  function renderDefects(defects) {
    const openCount = defects.filter(d => d.status === 'open').length;

    if (defectsBadge) {
      defectsBadge.textContent = openCount;
      defectsBadge.style.display = openCount > 0 ? 'inline-block' : 'none';
    }

    if (!defectsListContainer) return;

    if (defects.length === 0) {
      defectsListContainer.innerHTML = `
        <div class="empty-state-notice">
          Дефектов и замечаний не зафиксировано. Оборудование находится в нормативном техническом состоянии.
        </div>
      `;
      return;
    }

    defectsListContainer.innerHTML = defects.slice().reverse().map(d => {
      const isResolved = d.status === 'resolved';

      let severityLabel = 'Средняя';
      let severityClass = 'warn';
      if (d.severity === 'critical') {
        severityLabel = 'Критическая / Аварийная';
        severityClass = 'danger';
      } else if (d.severity === 'high') {
        severityLabel = 'Высокая';
        severityClass = 'danger';
      } else if (d.severity === 'low') {
        severityLabel = 'Низкая';
        severityClass = 'good';
      }

      return `
        <div class="defect-card ${isResolved ? 'resolved' : ''}">
          <div class="defect-top">
            <div>
              <div class="defect-node-title">${escapeHtml(d.node)}</div>
              <div class="mono" style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
                Дата фиксации: ${formatDate(d.created_at)}
              </div>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <span class="status-chip ${severityClass}" style="font-size: 11px;">
                ${severityLabel}
              </span>
              <span class="status-chip ${isResolved ? 'good' : 'attention'}" style="font-size: 11px;">
                ${isResolved ? 'Устранён' : 'Открыт'}
              </span>
            </div>
          </div>

          <div class="defect-desc">${escapeHtml(d.description)}</div>

          ${d.recommended_action ? `
            <div class="defect-action-rec">
              Мероприятие: <strong>${escapeHtml(d.recommended_action)}</strong>
            </div>
          ` : ''}

          <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--hairline); flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 13px; color: var(--text-secondary);">
              Журнал дефектов технологического оборудования
            </div>
            ${!isResolved ? `
              <button type="button" class="btn btn-secondary btn-sm" onclick="resolveDefect('${escapeHtml(d.id)}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Отметить устранённым
              </button>
            ` : '<span style="font-size: 12px; color: var(--state-good); font-weight: 500;">✓ Замечание закрыто</span>'}
          </div>
        </div>
      `;
    }).join('');
  }

  // Toggle & Submit Add Defect Form
  if (btnToggleAddDefect && panelAddDefect) {
    btnToggleAddDefect.addEventListener('click', () => {
      panelAddDefect.style.display = panelAddDefect.style.display === 'none' ? 'block' : 'none';
    });
  }

  if (btnCancelAddDefect && panelAddDefect) {
    btnCancelAddDefect.addEventListener('click', () => {
      panelAddDefect.style.display = 'none';
      if (formAddDefect) formAddDefect.reset();
    });
  }

  if (formAddDefect) {
    formAddDefect.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        node: document.getElementById('inp-defect-node').value.trim(),
        severity: document.getElementById('inp-defect-severity').value,
        description: document.getElementById('inp-defect-desc').value.trim(),
        recommended_action: document.getElementById('inp-defect-action').value.trim(),
        estimated_cost_rub: parseFloat(document.getElementById('inp-defect-cost').value) || 0
      };

      try {
        const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/defects`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка фиксации дефекта');
        }

        if (panelAddDefect) panelAddDefect.style.display = 'none';
        formAddDefect.reset();
        await loadEquipmentData();
      } catch (err) {
        console.error('Defect add error:', err);
        alert('Не удалось зафиксировать дефект: ' + err.message);
      }
    });
  }

  // Resolve Defect Action
  window.resolveDefect = async function(defectId) {
    if (!confirm('Отметить данный дефект как устранённый?')) return;
    try {
      const res = await fetch(`/api/equipment/${encodeURIComponent(equipmentId)}/defects/${encodeURIComponent(defectId)}/resolve`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Ошибка обновления дефекта');
      await loadEquipmentData();
    } catch (err) {
      console.error('Defect resolve error:', err);
      alert('Не удалось обновить статус дефекта: ' + err.message);
    }
  };

  // --- Lightbox Functions ---
  window.openLightbox = function(imgSrc, captionText) {
    if (!lightboxModal) return;
    if (lightboxImage) lightboxImage.src = imgSrc;
    if (lightboxCaption) lightboxCaption.textContent = captionText;
    lightboxModal.classList.add('open');
  };

  function closeLightbox() {
    if (lightboxModal) {
      lightboxModal.classList.remove('open');
      if (lightboxImage) lightboxImage.src = '';
    }
  }

  if (btnCloseLightbox) btnCloseLightbox.addEventListener('click', closeLightbox);
  if (lightboxModal) {
    lightboxModal.addEventListener('click', (e) => {
      if (e.target === lightboxModal) closeLightbox();
    });
  }

  // Close QR Sticker Modal
  function closeQrModal() {
    if (modalQrSticker) modalQrSticker.classList.remove('open');
  }

  if (btnCloseQrModal) btnCloseQrModal.addEventListener('click', closeQrModal);
  if (modalQrSticker) {
    modalQrSticker.addEventListener('click', (e) => {
      if (e.target === modalQrSticker) closeQrModal();
    });
  }

  // Keyboard Escape listener for modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeLightbox();
      closeQrModal();
      closeCompleteMaintModal();
    }
  });

  // --- Bootstrap ---
  loadEquipmentData();
});
