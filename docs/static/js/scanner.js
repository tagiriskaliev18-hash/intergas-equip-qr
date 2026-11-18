/**
 * Mind Equip — Scanner & SPA Entry Controller
 * Strict Instrument Architecture (Teenage Engineering / Anduril / Apple)
 * 100% Offline, Zero CDN, Vanilla ES6
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- DOM Elements ---
  const tabButtons = document.querySelectorAll('.segmented-item');
  const tabViews = document.querySelectorAll('.tab-view');

  const topAlertBadge = document.getElementById('top-alert-badge');
  const topAlertCount = document.getElementById('top-alert-count');
  const tabBadgeBudget = document.getElementById('tab-badge-budget');

  const networkPanel = document.getElementById('network-info-panel');
  const networkHostUrl = document.getElementById('network-host-url');

  const overviewAlertBanner = document.getElementById('overview-alert-banner');
  const overviewAlertHeadline = document.getElementById('overview-alert-headline');
  const overviewAlertDetails = document.getElementById('overview-alert-details');
  const overviewAlertSum = document.getElementById('overview-alert-sum');
  const btnGotoBudget = document.getElementById('btn-goto-budget');

  // Scanner Elements
  const videoElem = document.getElementById('qr-video');
  const canvasElem = document.getElementById('qr-canvas');
  const canvasCtx = canvasElem ? canvasElem.getContext('2d', { willReadFrequently: true }) : null;
  const standbyOverlay = document.getElementById('viewfinder-standby');
  const laserElem = document.getElementById('scanner-laser');
  const errorBox = document.getElementById('scanner-error-box');

  const btnStartScan = document.getElementById('btn-start-scan');
  const btnStopScan = document.getElementById('btn-stop-scan');
  const btnUploadQr = document.getElementById('btn-upload-qr');
  const fileInput = document.getElementById('qr-file-input');

  const qrResultBox = document.getElementById('qr-result-box');
  const qrResultText = document.getElementById('qr-result-text');
  const qrTimestamp = document.getElementById('qr-timestamp');
  const qrGoLink = document.getElementById('qr-go-link');
  const btnRescan = document.getElementById('btn-rescan');
  const qrVerifiedCard = document.getElementById('qr-verified-card');
  const qrVerifiedStatus = document.getElementById('qr-verified-status');
  const qrVerifiedName = document.getElementById('qr-verified-name');
  const qrVerifiedInv = document.getElementById('qr-verified-inv');

  // Registry Elements
  const equipmentTotalCount = document.getElementById('equipment-total-count');
  const equipmentSearchInput = document.getElementById('equipment-search');
  const equipmentRegistryList = document.getElementById('equipment-registry-list');
  const btnOpenAddEquip = document.getElementById('btn-open-add-equip');

  // Budget Elements
  const metricDueCount = document.getElementById('metric-due-count');
  const metricMaterialsSum = document.getElementById('metric-materials-sum');
  const metricServicesSum = document.getElementById('metric-services-sum');
  const metricTotalSum = document.getElementById('metric-total-sum');
  const budgetAlertsContainer = document.getElementById('budget-alerts-container');

  // Modal Elements
  const modalAddEquip = document.getElementById('modal-add-equip');
  const btnCloseModalEquip = document.getElementById('btn-close-modal-equip');
  const btnCancelModalEquip = document.getElementById('btn-cancel-modal-equip');
  const formAddEquipment = document.getElementById('form-add-equipment');

  // --- State Variables ---
  let mediaStream = null;
  let isScanning = false;
  let scanRafId = null;
  let nativeBarcodeDetector = null;
  let cachedOverviewData = null;

  // Initialize BarcodeDetector if natively supported in modern Chromium/Safari
  if ('BarcodeDetector' in window) {
    try {
      nativeBarcodeDetector = new BarcodeDetector({ formats: ['qr_code'] });
    } catch (e) {
      nativeBarcodeDetector = null;
    }
  }

  // --- Number & Currency Formatters ---
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

  // --- Segmented Control Tabs ---
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

    // If leaving scanner view, stop camera stream to conserve power
    if (targetViewId !== 'view-scanner' && isScanning) {
      stopCameraScanning();
    }
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.getAttribute('data-target');
      if (target) switchTab(target);
    });
  });

  if (btnGotoBudget) {
    btnGotoBudget.addEventListener('click', () => {
      switchTab('view-budget');
    });
  }

  if (topAlertBadge) {
    topAlertBadge.addEventListener('click', (e) => {
      e.preventDefault();
      switchTab('view-budget');
    });
  }

  // --- Network Info Fetching ---
  async function loadNetworkInfo() {
    try {
      const res = await fetch('/api/network-info');
      if (res.ok) {
        const data = await res.json();
        const hostUrl = data.primary_url || (window.location.protocol + '//' + window.location.host);
        if (networkHostUrl) {
          networkHostUrl.textContent = hostUrl;
        }
        if (networkPanel) {
          networkPanel.style.display = 'block';
        }
      }
    } catch (_) {
      // Fallback to window.location
      if (networkHostUrl) {
        networkHostUrl.textContent = window.location.origin;
      }
      if (networkPanel) {
        networkPanel.style.display = 'block';
      }
    }
  }

  // --- Camera QR Scanner Engine ---
  function showScannerError(msg) {
    if (errorBox) {
      errorBox.textContent = msg;
      errorBox.classList.add('visible');
    }
  }

  function hideScannerError() {
    if (errorBox) {
      errorBox.textContent = '';
      errorBox.classList.remove('visible');
    }
  }

  async function startCameraScanning() {
    hideScannerError();
    if (qrResultBox) qrResultBox.classList.remove('visible');
    const controlsBox = document.querySelector('.scanner-controls');
    if (controlsBox) controlsBox.style.display = 'flex';

    if (!window.isSecureContext) {
      showScannerError('Требуется защищённое HTTPS-соединение для доступа к видеокамере смартфона (порт 5810).');
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showScannerError('Интерфейс видеокамеры MediaDevices не поддерживается в данном браузере.');
      return;
    }

    try {
      const constraints = {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      };

      try {
        mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (envErr) {
        // Fallback for laptops or devices without environment camera
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      }

      videoElem.srcObject = mediaStream;
      await videoElem.play();

      isScanning = true;
      videoElem.classList.add('active');
      if (standbyOverlay) standbyOverlay.style.display = 'none';
      if (laserElem) laserElem.classList.add('active');

      if (btnStartScan) btnStartScan.style.display = 'none';
      if (btnStopScan) btnStopScan.style.display = 'inline-flex';

      scanRafId = requestAnimationFrame(scanVideoFrame);
    } catch (err) {
      console.error('Camera access error:', err);
      let errMsg = 'Не удалось запустить видеокамеру.';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errMsg = 'Доступ к камере заблокирован в браузере. Разрешите использование камеры в настройках сайта.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errMsg = 'Видеокамера не найдена на данном устройстве. Воспользуйтесь кнопкой «Загрузить фото с QR-кодом».';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errMsg = 'Камера уже используется другим приложением.';
      }
      showScannerError(errMsg);
      stopCameraScanning();
    }
  }

  function stopCameraScanning() {
    isScanning = false;
    if (scanRafId) {
      cancelAnimationFrame(scanRafId);
      scanRafId = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => {
        try { track.stop(); } catch (_) {}
      });
      mediaStream = null;
    }

    if (videoElem) {
      videoElem.srcObject = null;
      videoElem.classList.remove('active');
    }

    if (standbyOverlay && !qrResultBox?.classList.contains('visible')) {
      standbyOverlay.style.display = 'flex';
    }
    if (laserElem) laserElem.classList.remove('active');

    if (btnStartScan) btnStartScan.style.display = 'inline-flex';
    if (btnStopScan) btnStopScan.style.display = 'none';
  }

  async function scanVideoFrame() {
    if (!isScanning || !videoElem || videoElem.readyState < 2) {
      if (isScanning) scanRafId = requestAnimationFrame(scanVideoFrame);
      return;
    }

    const vw = videoElem.videoWidth;
    const vh = videoElem.videoHeight;

    if (vw === 0 || vh === 0) {
      scanRafId = requestAnimationFrame(scanVideoFrame);
      return;
    }

    // 1. Try native BarcodeDetector API if available
    if (nativeBarcodeDetector) {
      try {
        const barcodes = await nativeBarcodeDetector.detect(videoElem);
        if (barcodes && barcodes.length > 0) {
          const rawValue = barcodes[0].rawValue;
          if (rawValue) {
            handleDecodedQr(rawValue);
            return;
          }
        }
      } catch (detErr) {
        // Fallback to jsQR
      }
    }

    // 2. Local jsQR Fallback
    if (window.jsQR && canvasElem && canvasCtx) {
      if (canvasElem.width !== vw || canvasElem.height !== vh) {
        canvasElem.width = vw;
        canvasElem.height = vh;
      }

      canvasCtx.drawImage(videoElem, 0, 0, vw, vh);
      const imageData = canvasCtx.getImageData(0, 0, vw, vh);

      if (imageData && imageData.data) {
        const code = window.jsQR(imageData.data, vw, vh, {
          inversionAttempts: 'dontInvert'
        });

        if (code && code.data) {
          handleDecodedQr(code.data);
          return;
        }
      }
    }

    if (isScanning) {
      scanRafId = requestAnimationFrame(scanVideoFrame);
    }
  }

  // Handle Photo File Upload for QR decoding
  if (btnUploadQr && fileInput) {
    btnUploadQr.addEventListener('click', () => {
      fileInput.click();
    });

    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      hideScannerError();
      const reader = new FileReader();

      reader.onload = (loadEvent) => {
        const img = new Image();
        img.onload = async () => {
          try {
            // Check native BarcodeDetector
            if (nativeBarcodeDetector) {
              const barcodes = await nativeBarcodeDetector.detect(img);
              if (barcodes && barcodes.length > 0 && barcodes[0].rawValue) {
                handleDecodedQr(barcodes[0].rawValue);
                return;
              }
            }

            // Fallback jsQR
            if (window.jsQR) {
              const tempCanvas = document.createElement('canvas');
              tempCanvas.width = img.naturalWidth || img.width;
              tempCanvas.height = img.naturalHeight || img.height;
              const ctx = tempCanvas.getContext('2d', { willReadFrequently: true });
              ctx.drawImage(img, 0, 0);
              const imgData = ctx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
              const code = window.jsQR(imgData.data, tempCanvas.width, tempCanvas.height, {
                inversionAttempts: 'attemptBoth'
              });

              if (code && code.data) {
                handleDecodedQr(code.data);
                return;
              }
            }

            showScannerError('QR-код на выбранной фотографии не обнаружен. Попробуйте сделать более чёткий снимок.');
          } catch (procErr) {
            console.error('Image decode error:', procErr);
            showScannerError('Ошибка при обработке изображения.');
          }
        };
        img.src = loadEvent.target.result;
      };

      reader.readAsDataURL(file);
      fileInput.value = ''; // Reset input
    });
  }

  // --- QR Result Processing (Security & XSS Prevention) ---
  async function handleDecodedQr(rawContent) {
    stopCameraScanning();

    // Haptic pulse on mobile if supported
    if (navigator.vibrate) {
      try { navigator.vibrate([40, 30, 40]); } catch (_) {}
    }

    if (standbyOverlay) standbyOverlay.style.display = 'none';

    const trimmed = String(rawContent).trim();

    // Display RAW content strictly via textContent (Zero XSS)
    if (qrResultText) {
      qrResultText.textContent = trimmed;
    }
    if (qrTimestamp) {
      qrTimestamp.textContent = new Date().toLocaleTimeString('ru-RU');
    }

    if (qrResultBox) {
      qrResultBox.classList.add('visible');
    }
    const controlsBox = document.querySelector('.scanner-controls');
    if (controlsBox) {
      controlsBox.style.display = 'none';
    }

    // Pending verification state
    if (qrVerifiedCard) {
      qrVerifiedCard.style.display = 'block';
      if (qrVerifiedStatus) {
        qrVerifiedStatus.className = 'qr-verified-status standard';
        qrVerifiedStatus.innerHTML = '<span class="cyan-dot"></span> Проверка токена QR...';
      }
      if (qrVerifiedName) qrVerifiedName.textContent = 'Обращение к криптографическому реестру...';
      if (qrVerifiedInv) qrVerifiedInv.textContent = '';
    }

    if (qrGoLink) {
      qrGoLink.style.display = 'none';
    }

    try {
      const res = await fetch('/api/verify-qr-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: trimmed })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.valid) {
          if (qrVerifiedStatus) {
            if (data.is_secure_qr) {
              qrVerifiedStatus.className = 'qr-verified-status secure';
              qrVerifiedStatus.innerHTML = '🔒 Защищённый QR (Закрытый контур Mind Equip)';
            } else {
              qrVerifiedStatus.className = 'qr-verified-status standard';
              qrVerifiedStatus.innerHTML = 'ℹ Стандартный QR-код агрегата';
            }
          }
          if (qrVerifiedName) {
            qrVerifiedName.textContent = data.equipment_name || data.equipment_id;
          }
          if (qrVerifiedInv) {
            qrVerifiedInv.textContent = `Инв. №: ${data.inventory_number || data.equipment_id}`;
          }

          if (qrGoLink) {
            qrGoLink.setAttribute('href', data.card_url || `equipment.html?id=${encodeURIComponent(data.equipment_id)}`);
            qrGoLink.textContent = 'Открыть карточку агрегата';
            qrGoLink.style.display = 'inline-flex';
          }
          return;
        } else {
          // Token invalid or revoked
          if (qrVerifiedStatus) {
            qrVerifiedStatus.className = 'qr-verified-status invalid';
            qrVerifiedStatus.innerHTML = '⚠ ' + (data.error || 'Недействительный токен QR');
          }
          if (qrVerifiedName) {
            qrVerifiedName.textContent = data.equipment_id ? `Агрегат: ${data.equipment_id}` : 'Доступ отклонён';
          }
          if (qrVerifiedInv) {
            qrVerifiedInv.textContent = 'Этот QR-код устарел, был перевыпущен или не принадлежит доверенному контуру.';
          }
          return;
        }
      }
    } catch (netErr) {
      console.warn('Verify QR error, using fallback resolver:', netErr);
    }

    // Fallback if network verification is unreachable
    const targetUrl = resolveQrDestination(trimmed);
    if (qrVerifiedCard) {
      qrVerifiedCard.style.display = 'block';
      if (qrVerifiedStatus) {
        qrVerifiedStatus.className = 'qr-verified-status standard';
        qrVerifiedStatus.textContent = 'Распознано содержимое';
      }
      if (qrVerifiedName) qrVerifiedName.textContent = trimmed;
      if (qrVerifiedInv) qrVerifiedInv.textContent = '';
    }

    if (qrGoLink) {
      qrGoLink.setAttribute('href', targetUrl);
      qrGoLink.textContent = 'Перейти по ссылке';
      qrGoLink.style.display = 'inline-flex';
    }
  }

  function resolveQrDestination(text) {
    if (!text) return '#';

    // Block dangerous URI schemes
    const lower = text.toLowerCase().trim();
    if (lower.startsWith('javascript:') || lower.startsWith('data:') || lower.startsWith('vbscript:')) {
      return '#';
    }

    // Case 1: Full URL (http:// or https://)
    if (lower.startsWith('http://') || lower.startsWith('https://')) {
      try {
        const parsed = new URL(text);
        // If it points to an equipment doc path /doc/<id> on another IP in LAN, map it to current host
        const matchDoc = parsed.pathname.match(/^\/doc\/([^/]+)/);
        if (matchDoc) {
          return `equipment.html?id=${encodeURIComponent(matchDoc[1])}`;
        }
        return parsed.href;
      } catch (_) {
        return '#';
      }
    }

    // Case 2: Relative path starting with /doc/
    if (text.startsWith('/doc/')) {
      return text;
    }

    // Case 3: Plain ID (e.g. "nasos-ch-1" or "1")
    return `equipment.html?id=${encodeURIComponent(text)}`;
  }

  if (btnStartScan) {
    btnStartScan.addEventListener('click', startCameraScanning);
  }

  if (btnStopScan) {
    btnStopScan.addEventListener('click', stopCameraScanning);
  }

  if (btnRescan) {
    btnRescan.addEventListener('click', () => {
      if (qrResultBox) qrResultBox.classList.remove('visible');
      if (qrVerifiedCard) qrVerifiedCard.style.display = 'none';
      startCameraScanning();
    });
  }

  // --- Equipment & Overview Data Loader ---
  async function loadOverview() {
    try {
      const res = await fetch('/api/overview');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      cachedOverviewData = data;

      renderOverviewAlerts(data);
      renderEquipmentRegistry(data.equipment || []);
      renderBudgetPlan(data);
    } catch (err) {
      console.error('Error loading overview data:', err);
      if (equipmentRegistryList) {
        equipmentRegistryList.innerHTML = `
          <div class="empty-state-notice" style="color: var(--state-crit); text-align: center; padding: 20px;">
            Не удалось загрузить данные из локальной базы (${err.message})
          </div>
        `;
      }
    }
  }

  // 1. Render Operational Alert Banner
  function renderOverviewAlerts(data) {
    const alerts = data.alerts || [];
    const dueCount = alerts.length;

    if (dueCount > 0) {
      const isCritical = alerts.some(a => a.is_overdue || a.days_left <= 7);

      if (overviewAlertBanner) {
        overviewAlertBanner.style.display = 'flex';
        overviewAlertBanner.classList.toggle('critical-mode', isCritical);
      }

      if (overviewAlertHeadline) {
        overviewAlertHeadline.textContent = `Требуется внимание по ТО: ${dueCount} ед. оборудования`;
      }

      if (overviewAlertDetails) {
        overviewAlertDetails.textContent = isCritical
          ? 'Зафиксированы просроченные и срочные регламентные работы. Проверьте график и наличие ЗИП.'
          : 'Приближаются плановые регламентные работы. Проверьте готовность персонала и наличие ЗИП.';
      }

      // Update Header Badges
      if (topAlertBadge && topAlertCount) {
        topAlertCount.textContent = dueCount;
        topAlertBadge.classList.remove('empty');
      }

      if (tabBadgeBudget) {
        tabBadgeBudget.textContent = dueCount;
        tabBadgeBudget.style.display = 'inline-block';
      }
    } else {
      if (overviewAlertBanner) {
        overviewAlertBanner.style.display = 'none';
      }
      if (topAlertBadge) {
        topAlertBadge.classList.add('empty');
      }
      if (tabBadgeBudget) {
        tabBadgeBudget.style.display = 'none';
      }
    }
  }

  // 2. Render Equipment Registry List
  function renderEquipmentRegistry(equipmentList) {
    if (!equipmentRegistryList) return;

    if (equipmentTotalCount) {
      equipmentTotalCount.textContent = `(${equipmentList.length})`;
    }

    if (equipmentList.length === 0) {
      equipmentRegistryList.innerHTML = `
        <div class="empty-state-notice" style="text-align: center; padding: 30px;">
          В реестре пока нет оборудования. Нажмите «+ Добавить оборудование», чтобы создать первую запись.
        </div>
      `;
      return;
    }

    const searchTerm = (equipmentSearchInput ? equipmentSearchInput.value : '').toLowerCase().trim();

    const filtered = equipmentList.filter(item => {
      if (!searchTerm) return true;
      const name = (item.name || '').toLowerCase();
      const inv = (item.inventory_number || '').toLowerCase();
      const loc = (item.location || '').toLowerCase();
      const model = (item.model || '').toLowerCase();
      return name.includes(searchTerm) || inv.includes(searchTerm) || loc.includes(searchTerm) || model.includes(searchTerm);
    });

    if (filtered.length === 0) {
      equipmentRegistryList.innerHTML = `
        <div class="empty-state-notice" style="text-align: center; padding: 24px;">
          Ничего не найдено по запросу «${escapeHtml(searchTerm)}».
        </div>
      `;
      return;
    }

    equipmentRegistryList.innerHTML = filtered.map(item => {
      const statusClass = item.status === 'good' ? 'good' : (item.status === 'critical' ? 'critical' : 'attention');
      const statusText = item.status === 'good' ? 'Исправно' : (item.status === 'critical' ? 'Дефект' : 'Внимание');

      let maintenanceBadge = '';
      if (item.next_maintenance_date) {
        const isUrgent = item.maintenance_status === 'urgent' || item.maintenance_status === 'overdue';
        const colorStyle = isUrgent ? 'color: var(--state-crit);' : 'color: var(--text-secondary);';
        const daysText = item.days_until_maintenance !== null ? (item.days_until_maintenance < 0 ? `(просрочено на ${Math.abs(item.days_until_maintenance)} дн.)` : `(через ${item.days_until_maintenance} дн.)`) : '';
        maintenanceBadge = `
          <div class="meta-pill" style="${colorStyle}">
            <span>ТО: ${escapeHtml(item.next_maintenance_code || 'ТО')} — ${formatDate(item.next_maintenance_date)} ${daysText}</span>
          </div>
        `;
      }

      return `
        <article class="equipment-row-card">
          <div class="equip-card-top">
            <div>
              <a href="equipment.html?id=${encodeURIComponent(item.id)}" class="equip-name">
                ${escapeHtml(item.name)}
              </a>
              <div class="equip-inv mono">${escapeHtml(item.inventory_number)}</div>
            </div>
            <span class="status-chip ${statusClass}">
              <span class="mono">●</span>
              ${statusText}
            </span>
          </div>

          <div class="equip-card-meta">
            <div class="meta-pill">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
              </svg>
              <span>${escapeHtml(item.location || 'Цех не указан')}</span>
            </div>
            ${item.model ? `<div class="meta-pill"><span>Модель: ${escapeHtml(item.model)}</span></div>` : ''}
            ${item.has_passport ? '<div class="meta-pill" style="color: var(--state-good);"><span>Паспорт PDF</span></div>' : '<div class="meta-pill" style="color: var(--text-muted);"><span>Без паспорта</span></div>'}
            ${maintenanceBadge}
          </div>

          <div class="equip-card-bottom">
            <a href="qr/${encodeURIComponent(item.id)}.png" target="_blank" class="btn btn-ghost btn-sm" title="Открыть QR-этикетку">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
              QR-стикер
            </a>
            <a href="equipment.html?id=${encodeURIComponent(item.id)}" class="btn btn-secondary btn-sm">
              Открыть карточку
            </a>
          </div>
        </article>
      `;
    }).join('');
  }

  if (equipmentSearchInput) {
    equipmentSearchInput.addEventListener('input', () => {
      if (cachedOverviewData && cachedOverviewData.equipment) {
        renderEquipmentRegistry(cachedOverviewData.equipment);
      }
    });
  }

  // 3. Render Maintenance & Spare Parts (ZIP) Plan & Alerts List
  function renderBudgetPlan(data) {
    const summary = data.summary || {};
    const alerts = data.alerts || [];

    const elDueCount = document.getElementById('metric-due-count');
    const elOverdueCount = document.getElementById('metric-overdue-count');
    const elMaterialsDeficit = document.getElementById('metric-materials-deficit');
    const elDefectsCount = document.getElementById('metric-defects-count');

    if (elDueCount) elDueCount.textContent = summary.due_count || alerts.length || '0';
    if (elOverdueCount) elOverdueCount.textContent = summary.overdue_count || '0';
    if (elMaterialsDeficit) elMaterialsDeficit.textContent = summary.materials_deficit_items_count || '0';
    if (elDefectsCount) elDefectsCount.textContent = summary.open_defects_count || '0';

    if (!budgetAlertsContainer) return;

    if (alerts.length === 0) {
      budgetAlertsContainer.innerHTML = `
        <div class="empty-state-notice" style="text-align: center; padding: 24px;">
          Все единицы оборудования находятся в регламентном графике. Срочных работ на ближайшие 30 дней не запланировано.
        </div>
      `;
      return;
    }

    budgetAlertsContainer.innerHTML = alerts.map(alert => {
      const isOverdue = alert.is_overdue || (alert.days_left < 0);
      const daysText = isOverdue ? `Просрочено на ${Math.abs(alert.days_left)} дн.` : `Осталось ${alert.days_left} дн.`;
      const itemClass = isOverdue ? 'alert-row-item overdue' : 'alert-row-item';

      return `
        <div class="${itemClass}">
          <div class="alert-row-header">
            <div>
              <div style="font-size: 15px; font-weight: 600; color: var(--text-primary);">
                ${escapeHtml(alert.equipment_name)}
                <span class="mono" style="font-size: 12.5px; color: var(--text-secondary); font-weight: normal; margin-left: 4px;">
                  (${escapeHtml(alert.inventory_number)})
                </span>
              </div>
              <div style="font-size: 13.5px; color: var(--text-secondary); margin-top: 2px;">
                Вид ТО: <strong style="color: var(--text-primary);">${escapeHtml(alert.task_code)}</strong> — ${escapeHtml(alert.task_title)}
              </div>
              <div style="font-size: 12.5px; color: var(--text-muted); margin-top: 2px;">
                Локация: ${escapeHtml(alert.location || '—')} · Плановая дата: <span class="mono">${formatDate(alert.next_due_date)}</span>
              </div>
            </div>
            <span class="mono" style="font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: var(--radius-xs); ${isOverdue ? 'background: var(--state-crit-bg); color: var(--state-crit);' : 'background: var(--state-warn-bg); color: var(--state-warn);'}">
              ${daysText}
            </span>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 13px; padding-top: 6px; border-top: 1px solid var(--hairline);">
            <div>
              ${alert.deficit_items_count > 0 ? `<span style="color: var(--state-warn); font-weight: 600;">▲ Дефицит ЗИП: ${alert.deficit_items_count} поз. к поставке</span>` : '<span style="color: var(--state-good); font-weight: 500;">✓ ЗИП в наличии на складе (100%)</span>'}
            </div>
            <a href="equipment.html?id=${encodeURIComponent(alert.equipment_id)}" class="btn btn-secondary btn-sm">
              В карточку агрегата
            </a>
          </div>
        </div>
      `;
    }).join('');
  }

  // --- Modal: Add Equipment ---
  function openModalAddEquip() {
    if (modalAddEquip) {
      modalAddEquip.classList.add('open');
      const firstInput = document.getElementById('inp-equip-name');
      if (firstInput) setTimeout(() => firstInput.focus(), 100);
    }
  }

  function closeModalAddEquip() {
    if (modalAddEquip) {
      modalAddEquip.classList.remove('open');
      if (formAddEquipment) formAddEquipment.reset();
    }
  }

  if (btnOpenAddEquip) btnOpenAddEquip.addEventListener('click', openModalAddEquip);
  if (btnCloseModalEquip) btnCloseModalEquip.addEventListener('click', closeModalAddEquip);
  if (btnCancelModalEquip) btnCancelModalEquip.addEventListener('click', closeModalAddEquip);

  // Close modal on Escape or clicking backdrop
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalAddEquip?.classList.contains('open')) {
      closeModalAddEquip();
    }
  });

  if (modalAddEquip) {
    modalAddEquip.addEventListener('click', (e) => {
      if (e.target === modalAddEquip) closeModalAddEquip();
    });
  }

  if (formAddEquipment) {
    formAddEquipment.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('btn-submit-equip');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Создание...';
      }

      const payload = {
        name: document.getElementById('inp-equip-name').value.trim(),
        inventory_number: document.getElementById('inp-equip-inv').value.trim(),
        model: document.getElementById('inp-equip-model').value.trim(),
        location: document.getElementById('inp-equip-location').value.trim(),
        manufacturer: document.getElementById('inp-equip-manufacturer').value.trim(),
        commission_year: document.getElementById('inp-equip-year').value ? parseInt(document.getElementById('inp-equip-year').value, 10) : null,
        status: document.getElementById('inp-equip-status').value
      };

      try {
        const res = await fetch('/api/equipment', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Ошибка создания оборудования');
        }

        const result = await res.json();
        closeModalAddEquip();
        // Reload overview and navigate to newly created equipment
        if (result.equipment && result.equipment.id) {
          window.location.href = `equipment.html?id=${encodeURIComponent(result.equipment.id)}`;
        } else if (result.id) {
          window.location.href = `equipment.html?id=${encodeURIComponent(result.id)}`;
        } else {
          loadOverview();
        }
      } catch (err) {
        console.error('Add equipment error:', err);
        alert('Не удалось создать оборудование: ' + err.message);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Создать и сформировать QR';
        }
      }
    });
  }

  // --- Helper: HTML Escaping ---
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Initial Bootstrap ---
  loadNetworkInfo();
  loadOverview();
});
