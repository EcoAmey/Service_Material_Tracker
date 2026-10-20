document.addEventListener('DOMContentLoaded', function () {
  const searchInput = document.getElementById('material-search');
  const partTypeFilter = document.getElementById('part-type-filter');
  const engineerFilter = document.getElementById('engineer-filter');
  const dateFromInput = document.getElementById('date-from');
  const dateToInput = document.getElementById('date-to');
  const sortSelect = document.getElementById('sort-order');
  const tabButtons = Array.from(document.querySelectorAll('.tab-btn'));
  const rows = Array.from(document.querySelectorAll('.table-row'));
  const tableBody = document.querySelector('.material-table');
  const noItemsMessage = document.getElementById('no-items-message');

  const initialTab = tabButtons.find((b) => b.classList.contains('active')) || tabButtons[0];
  let activeTab = initialTab ? initialTab.dataset.tab : null;

  rows.forEach((row) => {
    const toggleBtn = row.querySelector('.expand-toggle');
    const details = row.querySelector('.row-details');
    if (!toggleBtn || !details) return;
    toggleBtn.addEventListener('click', function () {
      const isHidden = details.hasAttribute('hidden');
      if (isHidden) {
        details.removeAttribute('hidden');
      } else {
        details.setAttribute('hidden', '');
      }
      toggleBtn.classList.toggle('expanded', isHidden);
    });
  });

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
    const engineer = engineerFilter ? engineerFilter.value : '';
    let visibleCount = 0;
    rows.forEach((row) => {
      // A search term looks across every tab, so a match is never hidden
      // just because it lives in a different one.
      const matchesTab = term !== '' || activeTab === 'all' || row.dataset.status === activeTab;
      const matchesSearch = (row.dataset.search || '').includes(term);
      const matchesPartType = !partType || row.dataset.partType === partType;
      // 'user:<id>' = a warehouse / service desk / electronics login (matched
      // against the logins that acted on the row); anything else is the
      // engineer's name as written on the ticket.
      const matchesEngineer = !engineer || (engineer.startsWith('user:')
        ? (' ' + (row.dataset.actors || '') + ' ').includes(' u' + engineer.slice(5) + ' ')
        : row.dataset.engineer === engineer);
      const matchesDate = passesDateRange(row);
      const visible = matchesTab && matchesSearch && matchesPartType && matchesEngineer && matchesDate;
      row.style.display = visible ? '' : 'none';
      if (visible) visibleCount += 1;
    });
    if (noItemsMessage) {
      noItemsMessage.hidden = rows.length === 0 || visibleCount > 0;
    }
    // Only rows in the current tab/filter stay selected, so a hidden row
    // can never be archived by accident.
    checks.forEach((c) => { if (c.closest('.table-row').style.display === 'none') c.checked = false; });
    if (selectAll) selectAll.checked = false;
    updateBulkBar();
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

  const bulkForm = document.getElementById('bulk-archive-form');
  const bulkCount = document.getElementById('bulk-count');
  const bulkSubmit = document.getElementById('bulk-submit');
  const bulkAction = document.getElementById('bulk-action');
  const selectAll = document.getElementById('select-all');
  const checks = Array.from(document.querySelectorAll('.row-check'));

  // Checkbox clicks must not also toggle the row's expand/collapse.
  checks.forEach((c) => c.addEventListener('click', (e) => e.stopPropagation()));

  function updateBulkBar() {
    const n = checks.filter((c) => c.checked).length;
    const ticked = checks.filter((c) => c.checked);
    const restoring = n > 0 && ticked.every((c) => c.closest('.table-row').dataset.status === 'archived');
    bulkForm.hidden = n === 0;
    bulkCount.textContent = n + ' selected';
    bulkAction.value = restoring ? 'restore' : 'archive';
    bulkSubmit.textContent = restoring ? 'Restore selected' : 'Archive selected';
  }

  checks.forEach((c) => c.addEventListener('change', updateBulkBar));
  if (selectAll) {
    selectAll.addEventListener('change', () => {
      checks
        .filter((c) => c.closest('.table-row').style.display !== 'none')
        .forEach((c) => { c.checked = selectAll.checked; });
      updateBulkBar();
    });
  }
  // Ticks every row currently shown (tab + filters) dated before the picked
  // day, so the admin can review the selection before archiving.
  const beforeDate = document.getElementById('select-before-date');
  const beforeBtn = document.getElementById('select-before-btn');
  if (beforeBtn) {
    beforeBtn.addEventListener('click', () => {
      if (!beforeDate.value) return;
      const cutoff = new Date(beforeDate.value).getTime();
      checks.forEach((c) => {
        const row = c.closest('.table-row');
        if (row.style.display !== 'none' && parseInt(row.dataset.date, 10) * 1000 < cutoff) c.checked = true;
      });
      updateBulkBar();
    });
  }

  bulkForm.addEventListener('submit', (e) => {
    if (bulkAction.value !== 'restore' && !confirm('Archive the selected items? They will be hidden from all pages and reports.')) {
      e.preventDefault();
    }
  });

  if (searchInput) searchInput.addEventListener('input', applyFilters);
  if (partTypeFilter) partTypeFilter.addEventListener('change', applyFilters);
  if (engineerFilter) engineerFilter.addEventListener('change', applyFilters);
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
