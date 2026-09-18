document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = Array.from(document.querySelectorAll('.material-select'));
  const dispatchBtn = document.getElementById('open-dispatch-btn');
  const countLabel = document.getElementById('selected-count');
  const dialog = document.getElementById('dispatch-dialog');
  const cancelBtn = document.getElementById('dispatch-cancel');
  const hiddenFieldsContainer = document.getElementById('selected-items-fields');
  const searchInput = document.getElementById('material-search');
  const partTypeFilter = document.getElementById('part-type-filter');
  const dateFromInput = document.getElementById('date-from');
  const dateToInput = document.getElementById('date-to');
  const sortSelect = document.getElementById('sort-order');
  const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
  const rows = Array.from(document.querySelectorAll('.table-row'));
  const tableBody = document.querySelector('.material-table');
  const noItemsMessage = document.getElementById('no-items-message');
  const partnerSelect = document.getElementById('id_delivery_partner');
  const customPartnerField = document.getElementById('custom-delivery-partner-field');

  let activeTab = 'pending';

  function updateSelection() {
    const selected = checkboxes.filter((cb) => cb.checked);
    countLabel.textContent = selected.length + ' selected';
    if (dispatchBtn) dispatchBtn.disabled = selected.length === 0;
    rows.forEach((row) => {
      const cb = row.querySelector('.material-select');
      row.classList.toggle('selected', !!(cb && cb.checked));
    });
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

  if (dispatchBtn) {
    dispatchBtn.addEventListener('click', function () {
      const selected = checkboxes.filter((cb) => cb.checked);
      hiddenFieldsContainer.innerHTML = '';
      selected.forEach((cb) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'selected_items';
        input.value = cb.value;
        hiddenFieldsContainer.appendChild(input);
      });
      dialog.showModal();
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', function () {
      dialog.close();
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

  const courierOnlyFields = [
    document.getElementById('field-pickup-number'),
    document.getElementById('field-lr-number'),
    document.getElementById('field-delivery-challan-number'),
  ];

  if (partnerSelect) {
    partnerSelect.addEventListener('change', function () {
      const isOther = partnerSelect.value === 'other';
      if (customPartnerField) {
        customPartnerField.hidden = !isOther;
        if (!isOther) document.getElementById('id_custom_delivery_partner').value = '';
      }

      const isByHand = partnerSelect.value === 'by_hand';
      courierOnlyFields.forEach((field) => {
        if (!field) return;
        field.hidden = isByHand;
        if (isByHand) field.querySelector('input').value = '';
      });
    });
  }
});
