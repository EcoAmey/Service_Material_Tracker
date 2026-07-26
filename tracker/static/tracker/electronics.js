document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = Array.from(document.querySelectorAll('.material-select'));
  const countLabel = document.getElementById('selected-count');
  const proceedBtn = document.getElementById('proceed-btn');
  const sendToWarehouseBtn = document.getElementById('send-to-warehouse-btn');
  const scrapBtn = document.getElementById('scrap-btn');
  const mismatchWarning = document.getElementById('mismatch-warning');
  const hiddenFieldsContainer = document.getElementById('selected-items-fields');
  const actionField = document.getElementById('action-field');
  const searchInput = document.getElementById('material-search');
  const partTypeFilter = document.getElementById('part-type-filter');
  const dateFromInput = document.getElementById('date-from');
  const dateToInput = document.getElementById('date-to');
  const sortSelect = document.getElementById('sort-order');
  const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
  const rows = Array.from(document.querySelectorAll('.table-row'));
  const tableBody = document.querySelector('.material-table');
  const noItemsMessage = document.getElementById('no-items-message');

  const remarksDialog = document.getElementById('remarks-dialog');
  const remarksCancel = document.getElementById('remarks-cancel');
  const reservationDialog = document.getElementById('reservation-dialog');
  const reservationDialogTitle = document.getElementById('reservation-dialog-title');
  const reservationCancel = document.getElementById('reservation-cancel');
  const reservationInput = document.getElementById('id_outward_reservation_no');

  // The two dialogs' fields all share the same <form id="action-form">, so
  // a required field in whichever dialog is currently closed would silently
  // block submission of the other one. Toggle `required` based on which
  // dialog is actually open (same pattern as main_warehouse.js).
  const remarksRequiredFields = Array.from(remarksDialog.querySelectorAll('[name]'));
  const reservationRequiredFields = [reservationInput];

  function setRequired(fields, isRequired) {
    fields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  setRequired(remarksRequiredFields, false);
  setRequired(reservationRequiredFields, false);

  // A small reusable searchable combobox: wraps a native <select> (single or
  // multiple) with a text trigger + filterable panel, while the native
  // select stays in the DOM (visually hidden) as the actual submitted
  // value/source of truth -- Django's form parsing needs no changes.
  function initSearchableSelect(selectEl) {
    const multi = selectEl.multiple;
    const options = Array.from(selectEl.options);

    selectEl.classList.add('sr-only');
    const wrapper = document.createElement('div');
    wrapper.className = 'combo';
    selectEl.parentNode.insertBefore(wrapper, selectEl);
    wrapper.appendChild(selectEl);

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'combo-trigger';
    wrapper.appendChild(trigger);

    const panel = document.createElement('div');
    panel.className = 'combo-panel';
    panel.hidden = true;
    const search = document.createElement('input');
    search.type = 'text';
    search.className = 'combo-search';
    search.placeholder = 'Search...';
    panel.appendChild(search);
    const list = document.createElement('ul');
    list.className = 'combo-options';
    panel.appendChild(list);
    wrapper.appendChild(panel);

    function renderOptions(term) {
      const needle = term.trim().toLowerCase();
      list.innerHTML = '';
      options.forEach((opt) => {
        if (needle && !opt.text.toLowerCase().includes(needle)) return;
        const li = document.createElement('li');
        li.className = 'combo-option' + (opt.selected ? ' selected' : '');
        if (multi) {
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.checked = opt.selected;
          cb.tabIndex = -1;
          li.appendChild(cb);
        }
        const span = document.createElement('span');
        span.textContent = opt.text;
        li.appendChild(span);
        li.addEventListener('click', function (e) {
          // Selecting an option re-renders the list (removing this li from
          // the DOM), so this same click must not keep bubbling to the
          // document-level "click outside closes the panel" listener below
          // -- by the time it runs, e.target would be a detached node,
          // which reads as "outside" and would close the panel immediately.
          e.stopPropagation();
          if (multi) {
            opt.selected = !opt.selected;
          } else {
            options.forEach((o) => { o.selected = false; });
            opt.selected = true;
          }
          selectEl.dispatchEvent(new Event('change'));
          if (multi) {
            renderOptions(search.value);
          } else {
            closePanel();
          }
        });
        list.appendChild(li);
      });
    }

    function updateTriggerLabel() {
      const selected = options.filter((o) => o.selected);
      if (selected.length === 0) {
        trigger.textContent = '— Select —';
      } else if (multi && selected.length > 1) {
        trigger.textContent = selected.length + ' selected';
      } else {
        trigger.textContent = selected.map((o) => o.text).join(', ');
      }
    }

    function openPanel() {
      panel.hidden = false;
      search.value = '';
      renderOptions('');
      search.focus();
    }

    function closePanel() {
      panel.hidden = true;
    }

    trigger.addEventListener('click', function () {
      if (panel.hidden) openPanel(); else closePanel();
    });
    search.addEventListener('input', function () {
      renderOptions(search.value);
    });
    document.addEventListener('click', function (e) {
      if (!wrapper.contains(e.target)) closePanel();
    });
    selectEl.addEventListener('change', updateTriggerLabel);

    updateTriggerLabel();
  }

  // Only Sub Category needs the searchable combobox (it's a long
  // multi-select list) -- the other dropdowns stay plain native <select>s.
  ['sub_category'].forEach(function (name) {
    const el = document.getElementById('id_' + name);
    if (el) initSearchableSelect(el);
  });

  // Dropdowns to clear back to their unselected state whenever the Proceed
  // dialog is opened fresh for a new item -- no forced defaults, just blank.
  const SELECT_FIELD_NAMES = [
    'initial_observation',
    'pcb_type',
    'pcb_issue',
    'failure_category',
    'sub_category',
    'igbt_pin_status',
    'final_remark',
  ];

  function clearSelect(name) {
    const el = document.getElementById('id_' + name);
    if (!el) return;
    Array.from(el.options).forEach((opt, index) => {
      opt.selected = el.multiple ? false : index === 0;
    });
    el.dispatchEvent(new Event('change'));
  }

  let activeTab = 'with_electronics';

  function getSelected() {
    return checkboxes.filter((cb) => cb.checked);
  }

  function updateSelection() {
    const selected = getSelected();
    countLabel.textContent = selected.length + ' selected';

    [proceedBtn, sendToWarehouseBtn, scrapBtn].forEach((btn) => {
      if (!btn) return;
      btn.hidden = true;
      btn.disabled = true;
    });
    if (mismatchWarning) mismatchWarning.hidden = true;

    rows.forEach((row) => {
      const cb = row.querySelector('.material-select');
      row.classList.toggle('selected', !!(cb && cb.checked));
    });

    if (selected.length === 0) {
      return;
    }

    const groups = new Set(selected.map((cb) => cb.dataset.actionGroup));
    if (groups.size > 1) {
      if (mismatchWarning) mismatchWarning.hidden = false;
      return;
    }

    const group = selected[0].dataset.actionGroup;
    const btn = { proceed: proceedBtn, send_to_warehouse: sendToWarehouseBtn, scrap: scrapBtn }[group];
    if (btn) {
      btn.hidden = false;
      btn.disabled = false;
    }
  }

  checkboxes.forEach((cb) => cb.addEventListener('change', updateSelection));
  updateSelection();

  // Clicking anywhere on a row toggles its checkbox when it has one;
  // otherwise it toggles the details panel. The expand chevron always
  // toggles details only, and never affects selection.
  rows.forEach((row) => {
    const rowMain = row.querySelector('.row-main');
    const checkbox = row.querySelector('.material-select');
    const toggleBtn = row.querySelector('.expand-toggle');
    const details = row.querySelector('.row-details');

    function toggleDetails() {
      const isHidden = details.hasAttribute('hidden');
      if (isHidden) {
        details.removeAttribute('hidden');
      } else {
        details.setAttribute('hidden', '');
      }
      toggleBtn.classList.toggle('expanded', isHidden);
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleDetails();
      });
    }

    if (rowMain) {
      rowMain.addEventListener('click', function (e) {
        if (e.target === checkbox) return;
        if (checkbox) {
          checkbox.checked = !checkbox.checked;
          checkbox.dispatchEvent(new Event('change'));
        } else {
          toggleDetails();
        }
      });
    }
  });

  function populateSelectedFields() {
    hiddenFieldsContainer.innerHTML = '';
    getSelected().forEach((cb) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'selected_items';
      input.value = cb.value;
      hiddenFieldsContainer.appendChild(input);
    });
  }

  if (proceedBtn) {
    proceedBtn.addEventListener('click', function () {
      setRequired(remarksRequiredFields, true);
      setRequired(reservationRequiredFields, false);
      actionField.value = 'proceed';
      remarksDialog.querySelectorAll('input[type="text"], textarea').forEach((el) => (el.value = ''));
      remarksDialog.querySelectorAll('input[type="date"]').forEach((el) => (el.value = ''));
      SELECT_FIELD_NAMES.forEach(clearSelect);
      populateSelectedFields();
      remarksDialog.showModal();
    });
  }

  if (remarksCancel) {
    remarksCancel.addEventListener('click', function () {
      setRequired(remarksRequiredFields, false);
      remarksDialog.close();
    });
  }

  function openReservationDialog(action, title) {
    setRequired(reservationRequiredFields, true);
    setRequired(remarksRequiredFields, false);
    actionField.value = action;
    reservationDialogTitle.textContent = title;
    reservationInput.value = '';
    populateSelectedFields();
    reservationDialog.showModal();
  }

  if (sendToWarehouseBtn) {
    sendToWarehouseBtn.addEventListener('click', function () {
      openReservationDialog('send_to_warehouse', 'Send Back to Warehouse');
    });
  }
  if (scrapBtn) {
    scrapBtn.addEventListener('click', function () {
      openReservationDialog('scrap', 'Scrap');
    });
  }
  if (reservationCancel) {
    reservationCancel.addEventListener('click', function () {
      setRequired(reservationRequiredFields, false);
      reservationDialog.close();
    });
  }

  function passesDateRange(row) {
    const ts = parseInt(row.dataset.date, 10) * 1000;
    if (dateFromInput && dateFromInput.value) {
      if (ts < new Date(dateFromInput.value).getTime()) return false;
    }
    if (dateToInput && dateToInput.value) {
      const to = new Date(dateToInput.value).getTime() + 24 * 60 * 60 * 1000 - 1;
      if (ts > to) return false;
    }
    return true;
  }

  function applyFilters() {
    const term = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const partType = partTypeFilter ? partTypeFilter.value : '';
    let visibleCount = 0;
    rows.forEach((row) => {
      const matchesTab = row.dataset.status === activeTab;
      const matchesSearch = (row.dataset.search || '').includes(term);
      const matchesPartType = !partType || row.dataset.partType === partType;
      const matchesDate = passesDateRange(row);
      const visible = matchesTab && matchesSearch && matchesPartType && matchesDate;
      row.style.display = visible ? '' : 'none';
      if (visible) visibleCount += 1;
    });
    if (noItemsMessage) {
      noItemsMessage.hidden = rows.length === 0 || visibleCount > 0;
    }
  }

  function applySort() {
    const direction = sortSelect ? sortSelect.value : 'desc';
    const sorted = rows.slice().sort((a, b) => {
      const da = parseInt(a.dataset.date, 10);
      const db = parseInt(b.dataset.date, 10);
      return direction === 'asc' ? da - db : db - da;
    });
    sorted.forEach((row) => tableBody.appendChild(row));
  }

  if (searchInput) searchInput.addEventListener('input', applyFilters);
  if (partTypeFilter) partTypeFilter.addEventListener('change', applyFilters);
  if (dateFromInput) dateFromInput.addEventListener('change', applyFilters);
  if (dateToInput) dateToInput.addEventListener('change', applyFilters);
  if (sortSelect) sortSelect.addEventListener('change', applySort);

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', function () {
      activeTab = btn.dataset.tab;
      tabButtons.forEach((b) => b.classList.toggle('active', b === btn));
      applyFilters();
    });
  });

  applyFilters();
  applySort();
});
