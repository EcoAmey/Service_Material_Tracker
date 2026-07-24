document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = Array.from(document.querySelectorAll('.material-select'));
  const countLabel = document.getElementById('selected-count');
  const forwardBtn = document.getElementById('forward-btn');
  const testedOkBtn = document.getElementById('tested-ok-btn');
  const repairBtn = document.getElementById('repair-btn');
  const oemBtn = document.getElementById('oem-btn');
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
  const remarksDialogTitle = document.getElementById('remarks-dialog-title');
  const remarksCancel = document.getElementById('remarks-cancel');
  const forwardDialog = document.getElementById('forward-dialog');
  const forwardCancel = document.getElementById('forward-cancel');

  const fwdPartnerSelect = document.getElementById('id_fwd_delivery_partner');
  const fwdCustomPartnerField = document.getElementById('fwd-custom-partner-field');

  // Both dialogs' fields are attached to the same <form> via form="action-form",
  // so a required field in the closed dialog would silently block submission
  // of the other one. Toggle `required` based on which dialog is actually open.
  const forwardRequiredFields = [
    document.getElementById('id_fwd_pickup_number'),
    document.getElementById('id_fwd_lr_number'),
    document.getElementById('id_fwd_delivery_challan_number'),
    document.getElementById('id_fwd_destination'),
  ];

  function setForwardFieldsRequired(isRequired) {
    forwardRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  setForwardFieldsRequired(false);

  let activeTab = 'dispatched';

  function getSelected() {
    return checkboxes.filter((cb) => cb.checked);
  }

  function updateSelection() {
    const selected = getSelected();
    countLabel.textContent = selected.length + ' selected';

    rows.forEach((row) => {
      const cb = row.querySelector('.material-select');
      row.classList.toggle('selected', !!(cb && cb.checked));
    });

    [forwardBtn, testedOkBtn, repairBtn, oemBtn].forEach((btn) => {
      btn.hidden = true;
      btn.disabled = true;
    });
    mismatchWarning.hidden = true;

    if (selected.length === 0) {
      return;
    }

    const categories = new Set(selected.map((cb) => cb.dataset.category));
    if (categories.size > 1) {
      mismatchWarning.hidden = false;
      return;
    }

    const category = selected[0].dataset.category;
    forwardBtn.hidden = false;
    forwardBtn.disabled = false;
    if (category === 'card') {
      forwardBtn.textContent = 'Dispatch';
      testedOkBtn.hidden = false;
      testedOkBtn.disabled = false;
    } else {
      forwardBtn.textContent = 'Dispatch to Warehouse';
      repairBtn.hidden = false;
      repairBtn.disabled = false;
      oemBtn.hidden = false;
      oemBtn.disabled = false;
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

  function openRemarksDialog(action, title) {
    setForwardFieldsRequired(false);
    actionField.value = action;
    remarksDialogTitle.textContent = title;
    document.getElementById('id_simple_remarks').value = '';
    populateSelectedFields();
    remarksDialog.showModal();
  }

  if (testedOkBtn) {
    testedOkBtn.addEventListener('click', function () {
      openRemarksDialog('tested_ok', 'Tested OK');
    });
  }
  if (repairBtn) {
    repairBtn.addEventListener('click', function () {
      openRemarksDialog('repaired', 'Repair');
    });
  }
  if (oemBtn) {
    oemBtn.addEventListener('click', function () {
      openRemarksDialog('dispatched_to_oem', 'Dispatch to OEM');
    });
  }
  if (forwardBtn) {
    forwardBtn.addEventListener('click', function () {
      setForwardFieldsRequired(true);
      actionField.value = 'dispatch_forward';
      populateSelectedFields();
      forwardDialog.showModal();
    });
  }

  if (remarksCancel) {
    remarksCancel.addEventListener('click', function () {
      remarksDialog.close();
    });
  }
  if (forwardCancel) {
    forwardCancel.addEventListener('click', function () {
      setForwardFieldsRequired(false);
      forwardDialog.close();
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

  if (fwdPartnerSelect && fwdCustomPartnerField) {
    fwdPartnerSelect.addEventListener('change', function () {
      const isOther = fwdPartnerSelect.value === 'other';
      fwdCustomPartnerField.hidden = !isOther;
      if (!isOther) {
        document.getElementById('id_fwd_custom_delivery_partner').value = '';
      }
    });
  }
});
