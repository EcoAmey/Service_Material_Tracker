document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = Array.from(document.querySelectorAll('.material-select'));
  const countLabel = document.getElementById('selected-count');
  const receiveBtn = document.getElementById('receive-btn');
  const receiveMotorBtn = document.getElementById('receive-motor-btn');
  const oemBtn = document.getElementById('oem-btn');
  const scrapBtn = document.getElementById('scrap-btn');
  const repairedBtn = document.getElementById('repaired-btn');
  const stockBtn = document.getElementById('stock-btn');
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
  const receiveDialog = document.getElementById('receive-dialog');
  const receiveCancel = document.getElementById('receive-cancel');
  const motorDialog = document.getElementById('motor-dialog');
  const motorDialogTitle = document.getElementById('motor-dialog-title');
  const motorCancel = document.getElementById('motor-cancel');
  const cardOemDialog = document.getElementById('card-oem-dialog');
  const cardOemCancel = document.getElementById('card-oem-cancel');
  const cardScrapDialog = document.getElementById('card-scrap-dialog');
  const cardScrapCancel = document.getElementById('card-scrap-cancel');
  const receivedSerialNoField = document.getElementById('received-serial-no-field');
  const receivedSerialNoInput = document.getElementById('id_received_serial_no');
  const serialMatchesYes = document.getElementById('id_serial_matches_yes');
  const serialMatchesNo = document.getElementById('id_serial_matches_no');
  const receiveRemarksInput = document.getElementById('id_receive_remarks');
  const receiveMotorDialog = document.getElementById('receive-motor-dialog');
  const receiveMotorCancel = document.getElementById('receive-motor-cancel');
  const stockReservationField = document.getElementById('stock-reservation-field');

  // The receive dialog's fields share the same <form> as the simple remarks
  // dialog, so a required field in the closed dialog would silently block
  // submission of the other one. Toggle `required` based on which dialog
  // is actually open.
  const receiveRequiredFields = [
    document.getElementById('id_received_date'),
    document.getElementById('id_reservation_no'),
    document.getElementById('id_serial_matches_yes'),
    document.getElementById('id_serial_matches_no'),
  ];
  const motorRequiredFields = [document.getElementById('id_inward_reservation_no'), document.getElementById('id_outward_reservation_no')];
  const stockRequiredFields = [document.getElementById('id_stock_outward_reservation_no')];
  // Capacity/OEM/Head/Inch are per item and built (with their own
  // `required`) by motor_receive.js when the dialog opens.
  const receiveMotorRequiredFields = [document.getElementById('id_motor_received_date')];
  const cardOemRequiredFields = [
    document.getElementById('id_card_oem_lr_no'),
    document.getElementById('id_card_oem_challan_no'),
    document.getElementById('id_card_oem_outward_reservation_no'),
  ];
  const cardScrapRequiredFields = [
    document.getElementById('id_card_scrap_condition'),
    document.getElementById('id_card_scrap_outward_reservation_no'),
  ];

  function setReceiveFieldsRequired(isRequired) {
    receiveRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setMotorFieldsRequired(isRequired) {
    motorRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setStockFieldsRequired(isRequired) {
    stockRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setCardOemFieldsRequired(isRequired) {
    cardOemRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setCardScrapFieldsRequired(isRequired) {
    cardScrapRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setReceiveMotorFieldsRequired(isRequired) {
    receiveMotorRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  // Turns off every dialog's required fields except the one named -- called
  // whenever a dialog opens, so a stray required field left over from a
  // previously-opened (now closed) dialog can never block this submission.
  function setOnlyRequired(name) {
    setReceiveFieldsRequired(name === 'receive');
    setMotorFieldsRequired(name === 'motor');
    setStockFieldsRequired(name === 'stock');
    setCardOemFieldsRequired(name === 'cardOem');
    setCardScrapFieldsRequired(name === 'cardScrap');
    setReceiveMotorFieldsRequired(name === 'receiveMotor');
    if (stockReservationField) stockReservationField.hidden = name !== 'stock';
  }

  function updateSerialNoVisibility() {
    const mismatched = !!(serialMatchesNo && serialMatchesNo.checked);
    if (receivedSerialNoField) receivedSerialNoField.hidden = !mismatched;
    if (receivedSerialNoInput) receivedSerialNoInput.required = mismatched;
    if (receiveRemarksInput) receiveRemarksInput.required = mismatched;
  }

  if (serialMatchesYes) serialMatchesYes.addEventListener('change', updateSerialNoVisibility);
  if (serialMatchesNo) serialMatchesNo.addEventListener('change', updateSerialNoVisibility);

  setOnlyRequired(null);

  let activeTab = 'incoming';
  // Which action-group is currently selected -- 'dispatch_to_oem' (motor/
  // pump) and 'card_disposal' (P-serial cards) both show the same OEM/Scrap
  // buttons, so their click handlers read this to decide which dialog
  // (motor vs card) to open.
  let currentGroup = null;

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

    [receiveBtn, receiveMotorBtn, oemBtn, scrapBtn, repairedBtn, stockBtn].forEach((btn) => {
      btn.hidden = true;
      btn.disabled = true;
    });
    mismatchWarning.hidden = true;
    currentGroup = null;

    if (selected.length === 0) {
      return;
    }

    const groups = new Set(selected.map((cb) => cb.dataset.actionGroup));
    if (groups.size > 1) {
      mismatchWarning.hidden = false;
      return;
    }

    const group = selected[0].dataset.actionGroup;

    // Motors/pumps of different types can be received together: the dialog
    // asks for each item's own specs.
    currentGroup = group;
    const btns = {
      receive: [receiveBtn],
      receive_motor: [receiveMotorBtn],
      motor_disposal: [oemBtn, scrapBtn, repairedBtn],
      card_disposal: [oemBtn, scrapBtn],
      add_to_stock: [stockBtn],
    }[group] || [];
    btns.forEach((btn) => {
      btn.hidden = false;
      btn.disabled = false;
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
    // Only 'add_to_stock' needs the reservation number -- this dialog is
    // reused as a plain remarks-only prompt for 'repaired' too.
    setOnlyRequired(action === 'add_to_stock' ? 'stock' : null);
    actionField.value = action;
    remarksDialogTitle.textContent = title;
    document.getElementById('id_stock_outward_reservation_no').value = '';
    document.getElementById('id_simple_remarks').value = '';
    populateSelectedFields();
    remarksDialog.showModal();
  }

  function openReceiveMotorDialog() {
    setOnlyRequired('receiveMotor');
    actionField.value = 'receive_motor';
    window.MotorReceive.fill(getSelected());
    populateSelectedFields();
    receiveMotorDialog.showModal();
  }

  function openMotorDialog(action, title) {
    setOnlyRequired('motor');
    actionField.value = action;
    motorDialogTitle.textContent = title;
    document.getElementById('id_inward_reservation_no').value = '';
    document.getElementById('id_outward_reservation_no').value = '';
    document.getElementById('id_motor_remarks').value = '';
    populateSelectedFields();
    motorDialog.showModal();
  }

  function openCardOemDialog() {
    setOnlyRequired('cardOem');
    actionField.value = 'card_dispatch_to_oem';
    document.getElementById('id_card_oem_lr_no').value = '';
    document.getElementById('id_card_oem_challan_no').value = '';
    document.getElementById('id_card_oem_outward_reservation_no').value = '';
    populateSelectedFields();
    cardOemDialog.showModal();
  }

  function openCardScrapDialog() {
    setOnlyRequired('cardScrap');
    actionField.value = 'card_scrap';
    document.getElementById('id_card_scrap_condition').value = '';
    document.getElementById('id_card_scrap_remarks').value = '';
    document.getElementById('id_card_scrap_outward_reservation_no').value = '';
    populateSelectedFields();
    cardScrapDialog.showModal();
  }

  if (oemBtn) {
    oemBtn.addEventListener('click', function () {
      if (currentGroup === 'card_disposal') {
        openCardOemDialog();
      } else {
        openMotorDialog('dispatch_to_oem', 'Dispatch to OEM');
      }
    });
  }
  if (scrapBtn) {
    scrapBtn.addEventListener('click', function () {
      if (currentGroup === 'card_disposal') {
        openCardScrapDialog();
      } else {
        openMotorDialog('scrap', 'Scrap');
      }
    });
  }
  if (stockBtn) {
    stockBtn.addEventListener('click', function () {
      openRemarksDialog('add_to_stock', 'Add to Stock');
    });
  }
  if (repairedBtn) {
    repairedBtn.addEventListener('click', function () {
      openRemarksDialog('repaired', 'Repaired');
    });
  }
  if (receiveMotorBtn) {
    receiveMotorBtn.addEventListener('click', openReceiveMotorDialog);
  }
  if (receiveBtn) {
    receiveBtn.addEventListener('click', function () {
      setOnlyRequired('receive');
      actionField.value = 'receive';
      document.getElementById('id_received_date').value = '';
      document.getElementById('id_serial_matches_yes').checked = false;
      document.getElementById('id_serial_matches_no').checked = false;
      document.getElementById('id_received_serial_no').value = '';
      document.getElementById('id_reservation_no').value = '';
      document.getElementById('id_receive_remarks').value = '';
      updateSerialNoVisibility();
      populateSelectedFields();
      receiveDialog.showModal();
    });
  }

  if (remarksCancel) {
    remarksCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      remarksDialog.close();
    });
  }
  if (receiveCancel) {
    receiveCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      receiveDialog.close();
    });
  }
  if (receiveMotorCancel) {
    receiveMotorCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      receiveMotorDialog.close();
    });
  }
  if (motorCancel) {
    motorCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      motorDialog.close();
    });
  }
  if (cardOemCancel) {
    cardOemCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      cardOemDialog.close();
    });
  }
  if (cardScrapCancel) {
    cardScrapCancel.addEventListener('click', function () {
      setOnlyRequired(null);
      cardScrapDialog.close();
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
      // A search term looks across every tab, so a match is never hidden
      // just because it lives in a different one.
      const matchesTab = term !== '' || activeTab === 'all' || row.dataset.status === activeTab;
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
