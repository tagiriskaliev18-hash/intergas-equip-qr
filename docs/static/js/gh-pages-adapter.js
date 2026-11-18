/**
 * Intergas Central Asia — GitHub Pages Client-Side Runtime Adapter
 * Enables 100% live interactive operation on static GitHub Pages HTTPS hosting:
 * - Real smartphone camera QR scanning (MINDEQUIP:v2:<id>:<token>)
 * - Role-based Keycloak demo auth (admin / engineer / operator) in localStorage
 * - Real PDF downloads (passports, diagnostics, schedules, defect sheets)
 * - Interactive maintenance tasks, ZIP deficit tracking, defects, photo inspections
 * - Zero monetary sums (pure engineering & maintenance mode)
 */
(function () {
  'use strict';

  const STATE_KEY = 'ica_equip_gh_state_v2';
  const USER_KEY = 'ica_equip_gh_user_v2';
  const URGENT_DAYS = 7;
  const HORIZON_DAYS = 30;

  const DEMO_USERS = {
    admin: {
      username: 'admin',
      password: 'admin123',
      name: 'Главный механик (Админ)',
      email: 'admin@intergas.kz',
      roles: ['admin', 'engineer', 'operator'],
      role_label: 'Главный механик',
      is_admin: true,
      is_engineer: true
    },
    engineer: {
      username: 'engineer',
      password: 'engineer123',
      name: 'Инженер ТО и диагностики',
      email: 'engineer@intergas.kz',
      roles: ['engineer', 'operator'],
      role_label: 'Инженер ТО',
      is_admin: false,
      is_engineer: true
    },
    operator: {
      username: 'operator',
      password: 'operator123',
      name: 'Дежурный оператор КС/ГРС',
      email: 'operator@intergas.kz',
      roles: ['operator'],
      role_label: 'Оператор',
      is_admin: false,
      is_engineer: false
    }
  };

  const nativeFetch = window.fetch.bind(window);
  let stateCache = null;

  // --- Auth Helpers ---
  function getCurrentUser() {
    try {
      const raw = localStorage.getItem(USER_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function setCurrentUser(user) {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(USER_KEY);
    }
  }

  function loginUser(username, password) {
    const u = DEMO_USERS[(username || '').trim().toLowerCase()];
    if (!u || (password !== undefined && password !== u.password)) {
      return null;
    }
    const profile = {
      username: u.username,
      name: u.name,
      email: u.email,
      roles: u.roles,
      role_label: u.role_label,
      is_admin: u.is_admin,
      is_engineer: u.is_engineer
    };
    setCurrentUser(profile);
    return profile;
  }

  // Expose auth API for login.html
  window.ICAAuth = {
    getCurrentUser,
    setCurrentUser,
    loginUser,
    logout: function () {
      setCurrentUser(null);
      window.location.href = 'index.html';
    },
    DEMO_USERS
  };

  // --- State Loader ---
  async function loadState() {
    if (stateCache) return stateCache;
    try {
      const saved = localStorage.getItem(STATE_KEY);
      if (saved) {
        stateCache = JSON.parse(saved);
        return stateCache;
      }
    } catch (_) {}

    const res = await nativeFetch('data/initial-state.json');
    if (!res.ok) throw new Error('Failed to load data/initial-state.json');
    stateCache = await res.json();
    saveState();
    return stateCache;
  }

  function saveState() {
    if (!stateCache) return;
    try {
      localStorage.setItem(STATE_KEY, JSON.stringify(stateCache));
    } catch (err) {
      console.warn('localStorage quota warning:', err);
    }
  }

  // Start preloading immediately
  const readyPromise = loadState();

  // --- Date & Evaluation Logic (mirrors app/notifications.py, zero sums) ---
  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  function diffDays(targetIso, fromIso) {
    const d1 = new Date(targetIso + 'T00:00:00Z');
    const d2 = new Date(fromIso + 'T00:00:00Z');
    if (isNaN(d1.getTime()) || isNaN(d2.getTime())) return 0;
    return Math.round((d1.getTime() - d2.getTime()) / (1000 * 60 * 60 * 24));
  }

  function addDaysIso(baseIso, days) {
    const d = new Date(baseIso + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + (parseInt(days, 10) || 30));
    return d.toISOString().slice(0, 10);
  }

  function evaluateEquipment(eq, docsMap) {
    const today = todayIso();
    const docs = docsMap || { passport: [], diagnostics: [], schedule: [], defects: [] };
    const tasks = eq.maintenance_tasks || [];
    let totalDeficitPositions = 0;

    const evaluatedTasks = tasks.map(task => {
      const daysLeft = diffDays(task.next_due_date || today, today);
      const mats = task.materials || [];
      let defCount = 0;
      const materialsDetail = mats.map(m => {
        const req = Number(m.qty_required) || 0;
        const stock = Number(m.qty_in_stock) || 0;
        const toBuy = Math.max(0, Math.round((req - stock) * 1000) / 1000);
        if (toBuy > 0) defCount++;
        return {
          id: m.id,
          name: m.name,
          sku: m.sku || '',
          unit: m.unit || 'шт.',
          qty_required: req,
          qty_in_stock: stock,
          qty_to_buy: toBuy
        };
      });
      totalDeficitPositions += defCount;

      let urgency = 'ok';
      let urgencyLabel = 'В графике';
      let alertMessage = `Плановое ${task.code} запланировано на ${task.next_due_date} (через ${daysLeft} дн.).`;

      if (daysLeft < 0) {
        urgency = 'overdue';
        urgencyLabel = 'Просрочено';
        alertMessage = `Просрочено на ${Math.abs(daysLeft)} дн.! Требуется срочное проведение ${task.code} (${task.title}).`;
      } else if (daysLeft <= URGENT_DAYS) {
        urgency = 'urgent';
        urgencyLabel = 'Срочно ТО';
        alertMessage = defCount > 0
          ? `Через ${daysLeft} дн. плановое ${task.code} (${task.title}). Требуется ревизия узлов и комплектация ЗИП (дефицит: ${defCount} поз.).`
          : `Через ${daysLeft} дн. плановое ${task.code} (${task.title}). Требуется ревизия узлов и подготовка рабочего места (ЗИП укомплектован).`;
      } else if (daysLeft <= HORIZON_DAYS) {
        urgency = 'soon';
        urgencyLabel = 'Скоро регламентное ТО';
        alertMessage = defCount > 0
          ? `Через ${daysLeft} дн. плановое ${task.code} (${task.title}). Запланируйте поставку ЗИП (дефицит: ${defCount} поз.).`
          : `Через ${daysLeft} дн. плановое ${task.code} (${task.title}). Запланируйте проведение регламентных работ (ЗИП в наличии).`;
      }

      return {
        task_id: task.id,
        task_code: task.code,
        task_title: task.title,
        interval_days: task.interval_days,
        last_completed_date: task.last_completed_date,
        next_due_date: task.next_due_date,
        responsible: task.responsible,
        days_left: daysLeft,
        urgency,
        urgency_label: urgencyLabel,
        alert_message: alertMessage,
        deficit_items_count: defCount,
        budget: {
          deficit_items_count: defCount,
          materials_detail: materialsDetail
        },
        notes: task.notes || ''
      };
    });

    evaluatedTasks.sort((a, b) => a.days_left - b.days_left);

    const openDefects = (eq.defects || []).filter(d => d.status === 'open');
    const urgentAlerts = evaluatedTasks.filter(t => t.urgency === 'overdue' || t.urgency === 'urgent');
    const budgetAlerts = evaluatedTasks.filter(t => t.urgency === 'soon');
    const nextTask = evaluatedTasks[0] || null;

    return {
      id: eq.id,
      equipment_id: eq.id,
      name: eq.name,
      inventory_number: eq.inventory_number,
      model: eq.model || '',
      location: eq.location || '',
      status: eq.status || 'good',
      has_passport: (docs.passport || []).length > 0,
      has_diagnostics: (docs.diagnostics || []).length > 0,
      next_maintenance_date: nextTask ? nextTask.next_due_date : null,
      next_maintenance_code: nextTask ? nextTask.task_code : null,
      days_until_maintenance: nextTask ? nextTask.days_left : null,
      maintenance_status: nextTask ? nextTask.urgency : 'ok',
      tasks: evaluatedTasks,
      urgent_alerts: urgentAlerts,
      budget_alerts: budgetAlerts,
      materials_deficit_items_count: totalDeficitPositions,
      open_defects_count: openDefects.length
    };
  }

  function buildOverview(state) {
    const equipmentList = [];
    const alerts = [];

    for (const eq of state.equipment) {
      const docs = state.documents[eq.id] || { passport: [], diagnostics: [], schedule: [], defects: [] };
      const ev = evaluateEquipment(eq, docs);
      equipmentList.push(ev);

      for (const t of ev.tasks) {
        if (t.urgency === 'overdue' || t.urgency === 'urgent' || t.urgency === 'soon') {
          alerts.push({
            equipment_id: eq.id,
            equipment_name: eq.name,
            inventory_number: eq.inventory_number,
            location: eq.location,
            task_id: t.task_id,
            task_code: t.task_code,
            task_title: t.task_title,
            next_due_date: t.next_due_date,
            days_left: t.days_left,
            is_overdue: t.days_left < 0,
            urgency: t.urgency,
            urgency_label: t.urgency_label,
            message: t.alert_message,
            deficit_items_count: t.deficit_items_count
          });
        }
      }
    }

    alerts.sort((a, b) => a.days_left - b.days_left);

    const overdueCount = alerts.filter(a => a.urgency === 'overdue').length;
    const upcoming30dCount = alerts.filter(a => a.urgency === 'urgent' || a.urgency === 'soon').length;
    const openDefectsCount = equipmentList.reduce((acc, e) => acc + e.open_defects_count, 0);
    const materialsDeficitItemsCount = equipmentList.reduce((acc, e) => acc + e.materials_deficit_items_count, 0);

    return {
      equipment: equipmentList,
      alerts,
      summary: {
        total_equipment: state.equipment.length,
        due_count: alerts.length,
        overdue_count: overdueCount,
        upcoming_30d_count: upcoming30dCount,
        open_defects_count: openDefectsCount,
        materials_deficit_items_count: materialsDeficitItemsCount
      }
    };
  }

  function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
      status,
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }

  function randomHex(len) {
    const chars = '0123456789abcdef';
    let out = '';
    for (let i = 0; i < len; i++) {
      out += chars[Math.floor(Math.random() * chars.length)];
    }
    return out;
  }

  function slugify(str) {
    const map = {
      а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'e',ж:'zh',з:'z',и:'i',й:'y',к:'k',л:'l',
      м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'h',ц:'ts',ч:'ch',ш:'sh',
      щ:'sch',ъ:'',ы:'y',ь:'',э:'e',ю:'yu',я:'ya'
    };
    return String(str || '')
      .toLowerCase()
      .split('')
      .map(c => map[c] !== undefined ? map[c] : c)
      .join('')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || ('equip-' + randomHex(6));
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // --- Fetch Interceptor ---
  window.fetch = async function (input, init) {
    const urlStr = typeof input === 'string' ? input : (input && input.url) || '';
    const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();

    // Parse path relative to origin
    let pathname = urlStr;
    try {
      const u = new URL(urlStr, window.location.href);
      pathname = u.pathname;
    } catch (_) {}

    // Only intercept /api/* endpoints
    const apiIdx = pathname.indexOf('/api/');
    if (apiIdx === -1) {
      return nativeFetch(input, init);
    }

    const apiPath = pathname.slice(apiIdx);
    const state = await readyPromise;

    // 1. GET /api/network-info
    if (apiPath === '/api/network-info' && method === 'GET') {
      const baseHref = window.location.href.split('?')[0].replace(/\/[^/]*\.html$/, '/');
      return jsonResponse({
        primary_url: baseHref,
        host_urls: [baseHref],
        port: 443,
        mode: 'github-pages'
      });
    }

    // 2. GET /api/overview
    if (apiPath === '/api/overview' && method === 'GET') {
      return jsonResponse(buildOverview(state));
    }

    // 3. POST /api/verify-qr-token
    if (apiPath === '/api/verify-qr-token' && method === 'POST') {
      const body = JSON.parse(init && init.body ? init.body : '{}');
      const raw = (body.token || body.qr_payload || '').trim();
      const m = /^MINDEQUIP:v2:([a-zA-Z0-9_-]+):([a-fA-F0-9]+)$/.exec(raw);
      if (!m) {
        return jsonResponse({
          is_secure_qr: false,
          valid: false,
          equipment_id: null,
          card_url: null,
          error: 'Отсканированный QR-код не является защищённым кодом системы АО «Интергаз Центральная Азия».'
        }, 200);
      }
      const eqId = m[1];
      const token = m[2].toUpperCase();
      const expected = (state.qr_tokens && state.qr_tokens[eqId] || '').toUpperCase();
      const eq = state.equipment.find(e => e.id === eqId);
      if (!eq || !expected || expected !== token) {
        return jsonResponse({
          is_secure_qr: true,
          valid: false,
          equipment_id: eq ? eq.id : null,
          card_url: null,
          error: 'Токен QR-кода устарел или был перевыпущен'
        }, 200);
      }
      return jsonResponse({
        is_secure_qr: true,
        valid: true,
        equipment_id: eq.id,
        equipment_name: eq.name,
        inventory_number: eq.inventory_number,
        card_url: `equipment.html?id=${encodeURIComponent(eq.id)}`,
        error: null
      }, 200);
    }

    // 4. POST /api/equipment (create new equipment)
    if (apiPath === '/api/equipment' && method === 'POST') {
      const user = getCurrentUser();
      if (user && !user.is_engineer) {
        return jsonResponse({ detail: 'Недостаточно прав. Требуется роль Инженера или Администратора.' }, 403);
      }
      const payload = JSON.parse(init && init.body ? init.body : '{}');
      const id = payload.id || slugify(payload.inventory_number || payload.name);
      if (state.equipment.some(e => e.id === id)) {
        return jsonResponse({ detail: 'Оборудование с таким идентификатором уже существует' }, 409);
      }
      const newEq = {
        id,
        name: payload.name || 'Новое оборудование',
        inventory_number: payload.inventory_number || 'ИНВ-000',
        model: payload.model || '',
        serial_number: payload.serial_number || '',
        manufacturer: payload.manufacturer || '',
        commission_year: payload.commission_year || new Date().getFullYear(),
        location: payload.location || 'Объект ЛПУ / ГРС / КС',
        status: payload.status || 'good',
        maintenance_tasks: [],
        maintenance_history: [],
        photos: [],
        defects: []
      };
      state.equipment.push(newEq);
      state.documents[id] = { passport: [], diagnostics: [], schedule: [], defects: [] };
      state.qr_tokens[id] = randomHex(24);
      saveState();
      return jsonResponse({ equipment: newEq, id }, 201);
    }

    // Match /api/equipment/{id}...
    const eqMatch = /^\/api\/equipment\/([^/]+)(\/.*)?$/.exec(apiPath);
    if (eqMatch) {
      const eqId = decodeURIComponent(eqMatch[1]);
      const subPath = eqMatch[2] || '';
      const eq = state.equipment.find(e => e.id === eqId);

      if (!eq) {
        return jsonResponse({ detail: 'Оборудование не найдено' }, 404);
      }
      if (!state.documents[eqId]) {
        state.documents[eqId] = { passport: [], diagnostics: [], schedule: [], defects: [] };
      }

      // GET /api/equipment/{id}
      if (subPath === '' && method === 'GET') {
        const docs = state.documents[eqId];
        const evaluation = evaluateEquipment(eq, docs);
        return jsonResponse({
          equipment: eq,
          documents: docs,
          evaluation,
          qr_payload: `MINDEQUIP:v2:${eq.id}:${state.qr_tokens[eq.id] || ''}`
        });
      }

      // POST /api/equipment/{id}/rotate-qr
      if (subPath === '/rotate-qr' && method === 'POST') {
        const user = getCurrentUser();
        if (!user || !user.is_engineer) {
          return jsonResponse({ detail: 'Требуется авторизация с ролью Инженер или Администратор.' }, 403);
        }
        const newToken = randomHex(24);
        state.qr_tokens[eqId] = newToken;
        saveState();
        return jsonResponse({
          status: 'rotated',
          equipment_id: eqId,
          qr_payload: `MINDEQUIP:v2:${eqId}:${newToken}`,
          message: 'Токен QR-кода успешно перевыпущен в текущей сессии.'
        });
      }

      // POST /api/equipment/{id}/maintenance
      if (subPath === '/maintenance' && method === 'POST') {
        const payload = JSON.parse(init && init.body ? init.body : '{}');
        const newTask = {
          id: 'task-' + randomHex(6),
          code: payload.code || 'ТО-1',
          title: payload.title || 'Регламентное ТО',
          interval_days: parseInt(payload.interval_days, 10) || 30,
          last_completed_date: payload.last_completed_date || null,
          next_due_date: payload.next_due_date || addDaysIso(todayIso(), 30),
          responsible: payload.responsible || 'Служба эксплуатации',
          service_cost_rub: 0,
          notes: payload.notes || '',
          materials: (payload.materials || []).map(m => ({
            id: 'mat-' + randomHex(5),
            name: m.name,
            sku: m.sku || '',
            unit: m.unit || 'шт.',
            qty_required: Number(m.qty_required) || 1,
            qty_in_stock: Number(m.qty_in_stock) || 0,
            unit_price_rub: 0
          }))
        };
        eq.maintenance_tasks = eq.maintenance_tasks || [];
        eq.maintenance_tasks.push(newTask);
        saveState();
        return jsonResponse(newTask, 201);
      }

      // POST /api/equipment/{id}/maintenance/{taskId}/complete
      const compMatch = /^\/maintenance\/([^/]+)\/complete$/.exec(subPath);
      if (compMatch && method === 'POST') {
        const taskId = decodeURIComponent(compMatch[1]);
        const task = (eq.maintenance_tasks || []).find(t => t.id === taskId);
        if (!task) return jsonResponse({ detail: 'Задача ТО не найдена' }, 404);
        const payload = JSON.parse(init && init.body ? init.body : '{}');
        const completedDate = payload.completed_date || todayIso();
        task.last_completed_date = completedDate;
        task.next_due_date = addDaysIso(completedDate, task.interval_days || 30);

        if (payload.restock_used_materials && Array.isArray(task.materials)) {
          task.materials.forEach(m => {
            m.qty_in_stock = Math.max(0, (Number(m.qty_in_stock) || 0) - (Number(m.qty_required) || 0));
          });
        }

        eq.maintenance_history = eq.maintenance_history || [];
        eq.maintenance_history.push({
          id: 'hist-' + randomHex(6),
          task_id: task.id,
          task_code: task.code,
          task_title: task.title,
          completed_at: completedDate,
          performer: payload.performer || (getCurrentUser() && getCurrentUser().name) || 'Дежурный инженер',
          comment: payload.comment || ''
        });
        saveState();
        return jsonResponse({ status: 'completed', task });
      }

      // POST /api/equipment/{id}/defects
      if (subPath === '/defects' && method === 'POST') {
        const payload = JSON.parse(init && init.body ? init.body : '{}');
        const newDef = {
          id: 'def-' + randomHex(6),
          node: payload.node || 'Технологический узел',
          description: payload.description || '',
          severity: payload.severity || 'medium',
          recommended_action: payload.recommended_action || 'Выполнить ремонт / замену узла',
          estimated_cost_rub: 0,
          status: 'open',
          created_at: new Date().toISOString()
        };
        eq.defects = eq.defects || [];
        eq.defects.push(newDef);
        if (newDef.severity === 'critical') {
          eq.status = 'critical';
        } else if (eq.status === 'good') {
          eq.status = 'attention';
        }
        saveState();
        return jsonResponse(newDef, 201);
      }

      // POST /api/equipment/{id}/defects/{defectId}/resolve
      const resDefMatch = /^\/defects\/([^/]+)\/resolve$/.exec(subPath);
      if (resDefMatch && method === 'POST') {
        const defId = decodeURIComponent(resDefMatch[1]);
        const def = (eq.defects || []).find(d => d.id === defId);
        if (!def) return jsonResponse({ detail: 'Дефект не найден' }, 404);
        def.status = 'resolved';
        const stillOpen = (eq.defects || []).filter(d => d.status === 'open');
        if (stillOpen.length === 0) {
          eq.status = 'good';
        } else if (!stillOpen.some(d => d.severity === 'critical')) {
          eq.status = 'attention';
        }
        saveState();
        return jsonResponse(def);
      }

      // POST /api/equipment/{id}/photos
      if (subPath === '/photos' && method === 'POST') {
        const fd = init && init.body;
        let dataUrl = '';
        let filename = 'photo_' + Date.now() + '.jpg';
        let condition = 'good';
        let node = 'Общий осмотр';
        let comment = '';
        if (fd instanceof FormData) {
          const file = fd.get('file');
          if (file && file instanceof File) {
            filename = file.name || filename;
            dataUrl = await fileToDataUrl(file);
          }
          condition = fd.get('condition') || 'good';
          node = fd.get('node') || 'Общий осмотр';
          comment = fd.get('comment') || '';
        }
        const photoItem = {
          id: 'photo-' + randomHex(6),
          filename,
          url: dataUrl,
          condition,
          node,
          comment,
          captured_at: new Date().toISOString()
        };
        eq.photos = eq.photos || [];
        eq.photos.push(photoItem);
        eq.status = condition;
        saveState();
        return jsonResponse(photoItem, 201);
      }

      // POST /api/equipment/{id}/documents/{category}
      const docUpMatch = /^\/documents\/([^/]+)$/.exec(subPath);
      if (docUpMatch && method === 'POST') {
        const cat = decodeURIComponent(docUpMatch[1]);
        const fd = init && init.body;
        let file = null;
        if (fd instanceof FormData) file = fd.get('file');
        if (!file || !(file instanceof File)) {
          return jsonResponse({ detail: 'Файл не передан' }, 400);
        }
        const blobUrl = URL.createObjectURL(file);
        const docItem = {
          filename: file.name,
          category: cat,
          size_bytes: file.size,
          updated_at: new Date().toISOString(),
          download_url: blobUrl
        };
        state.documents[eqId][cat] = state.documents[eqId][cat] || [];
        state.documents[eqId][cat].push(docItem);
        saveState();
        return jsonResponse(docItem, 201);
      }

      // POST /api/equipment/{id}/schedule/generate-pdf
      if (subPath === '/schedule/generate-pdf' && method === 'POST') {
        const existing = (state.documents[eqId].schedule || [])[0];
        if (existing) return jsonResponse(existing, 201);
        const fallback = {
          filename: `plan_${eqId}.pdf`,
          category: 'schedule',
          size_bytes: 58000,
          updated_at: new Date().toISOString(),
          download_url: `reports/plan_${eqId}.pdf`
        };
        state.documents[eqId].schedule = [fallback];
        saveState();
        return jsonResponse(fallback, 201);
      }

      // POST /api/equipment/{id}/defects/generate-pdf
      if (subPath === '/defects/generate-pdf' && method === 'POST') {
        const existing = (state.documents[eqId].defects || [])[0];
        if (existing) return jsonResponse(existing, 201);
        const fallback = {
          filename: `plan_${eqId}.pdf`,
          category: 'defects',
          size_bytes: 56000,
          updated_at: new Date().toISOString(),
          download_url: `reports/plan_${eqId}.pdf`
        };
        state.documents[eqId].defects = [fallback];
        saveState();
        return jsonResponse(fallback, 201);
      }
    }

    return jsonResponse({ detail: 'Endpoint not available in static preview: ' + apiPath }, 404);
  };

  // --- UI Hydration on DOMContentLoaded ---
  document.addEventListener('DOMContentLoaded', () => {
    // 1. Update Auth Header Pill dynamically based on localStorage user
    const user = getCurrentUser();
    const authHeader = document.getElementById('gh-auth-header');
    if (authHeader) {
      if (user) {
        authHeader.innerHTML = `
          <div class="user-badge" title="${user.name} (${user.role_label})">
            <span class="user-role-dot ${user.is_admin ? 'admin' : (user.is_engineer ? 'engineer' : 'operator')}"></span>
            <span class="user-name-label">${user.username}</span>
            <a href="#" class="btn-logout" id="gh-btn-logout" title="Выйти из системы">Выйти</a>
          </div>
        `;
        const btnLogout = document.getElementById('gh-btn-logout');
        if (btnLogout) {
          btnLogout.addEventListener('click', (e) => {
            e.preventDefault();
            window.ICAAuth.logout();
          });
        }
      } else {
        authHeader.innerHTML = `
          <a href="login.html" class="btn-login" id="btn-top-login" title="Войти в систему через Keycloak">
            <span class="cyan-dot" aria-hidden="true"></span>
            <span>Войти</span>
          </a>
        `;
      }
    }

    // 2. Toggle Rotate QR button based on engineer role
    const btnRotate = document.getElementById('btn-rotate-qr-token');
    if (btnRotate) {
      btnRotate.style.display = (user && user.is_engineer) ? 'inline-flex' : 'none';
    }

    // 3. Update Network Info label for GitHub Pages HTTPS
    const netPanel = document.getElementById('network-info-panel');
    if (netPanel) {
      const lbl = netPanel.querySelector('span');
      if (lbl && lbl.textContent.includes('Wi-Fi')) {
        lbl.textContent = 'Защищённый адрес системы (GitHub Pages HTTPS):';
      }
    }
  });
})();
