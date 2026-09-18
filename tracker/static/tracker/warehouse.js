document.addEventListener('DOMContentLoaded', function () {
  const checkboxes = Array.from(document.querySelectorAll('.material-select'));
  const countLabel = document.getElementById('selected-count');
  const forwardBtn = document.getElementById('forward-btn');
  const testedOkBtn = document.getElementById('tested-ok-btn');
  const repairBtn = document.getElementById('repair-btn');
  const oemBtn = document.getElementById('oem-btn');
  const scrapBtn = document.getElementById('scrap-btn');
  const receiveBtn = document.getElementById('receive-btn');
  const receiveMotorBtn = document.getElementById('receive-motor-btn');
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
  const receiveMotorDialog = document.getElementById('receive-motor-dialog');
  const receiveMotorCancel = document.getElementById('receive-motor-cancel');
  const receiveDialog = document.getElementById('receive-dialog');
  const receiveCancel = document.getElementById('receive-cancel');
  const receivedSerialNoField = document.getElementById('received-serial-no-field');
  const receivedSerialNoInput = document.getElementById('id_received_serial_no');
  const serialMatchesYes = document.getElementById('id_serial_matches_yes');
  const serialMatchesNo = document.getElementById('id_serial_matches_no');
  const receiveRemarksInput = document.getElementById('id_receive_remarks');
  const motorOemSelect = document.getElementById('id_motor_oem_name');
  const motorHeadSizeField = document.getElementById('motor-head-size-field');
  const motorHeadSizeSelect = document.getElementById('id_motor_head_size');
  const motorInchSizeField = document.getElementById('motor-inch-size-field');
  const motorInchSizeSelect = document.getElementById('id_motor_inch_size');

  // OEM name list depends on the selected item's pump type -- see
  // DispatchItem.motor_pump_type and the two json_script blocks at the
  // bottom of the page.
  function readJsonScript(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : [];
  }
  const motorSurfaceOemChoices = readJsonScript('motor-surface-oem-choices');
  const submersibleOemChoices = readJsonScript('submersible-oem-choices');

  const fwdPartnerSelect = document.getElementById('id_fwd_delivery_partner');
  const fwdCustomPartnerField = document.getElementById('fwd-custom-partner-field');

  // Every dialog's fields are attached to the same <form> via form="action-form",
  // so a required field in a closed dialog would silently block submission
  // of the one actually open. Toggle `required` based on which is open.
  // Pickup/LR/challan aren't in this list -- like the engineer's own
  // dispatch form, they're only required unless By Hand is picked, which
  // WarehouseActionView checks server-side (see fwdCourierOnlyFields below).
  const forwardRequiredFields = [
    document.getElementById('id_fwd_destination'),
  ];
  // Head/Inch size are required separately in openReceiveMotorDialog --
  // only for Surface/Submersible Pump, not for a bare Motor.
  const receiveMotorRequiredFields = [
    document.getElementById('id_motor_received_date'),
    document.getElementById('id_motor_capacity'),
    document.getElementById('id_motor_oem_name'),
  ];
  const receiveRequiredFields = [
    document.getElementById('id_received_date'),
    document.getElementById('id_reservation_no'),
    document.getElementById('id_serial_matches_yes'),
    document.getElementById('id_serial_matches_no'),
  ];

  function setForwardFieldsRequired(isRequired) {
    forwardRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  function setReceiveMotorFieldsRequired(isRequired) {
    receiveMotorRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
    // Head/Inch size only apply to Surface/Submersible Pump, not a bare
    // Motor -- always reset here; openReceiveMotorDialog sets them true
    // afterward when the selected item's type needs them.
    if (motorHeadSizeSelect) motorHeadSizeSelect.required = false;
    if (motorInchSizeSelect) motorInchSizeSelect.required = false;
  }

  function setReceiveFieldsRequired(isRequired) {
    receiveRequiredFields.forEach((field) => {
      if (field) field.required = isRequired;
    });
  }

  // Mirrors main_warehouse.js's identical receive dialog behavior.
  function updateSerialNoVisibility() {
    const mismatched = !!(serialMatchesNo && serialMatchesNo.checked);
    if (receivedSerialNoField) receivedSerialNoField.hidden = !mismatched;
    if (receivedSerialNoInput) receivedSerialNoInput.required = mismatched;
    if (receiveRemarksInput) receiveRemarksInput.required = mismatched;
  }

  if (serialMatchesYes) serialMatchesYes.addEventListener('change', updateSerialNoVisibility);
  if (serialMatchesNo) serialMatchesNo.addEventListener('change', updateSerialNoVisibility);

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

    [forwardBtn, testedOkBtn, repairBtn, oemBtn, scrapBtn, receiveBtn, receiveMotorBtn].forEach((btn) => {
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
    if (category === 'motor_pump_pending_receive') {
      // Motor / Surface Pump / Submersible Pump each need a different OEM
      // list, and only Surface/Submersible ask for Head/Inch size -- mixing
      // types in one receive would apply one item's answers to all of them.
      const motorTypes = new Set(selected.map((cb) => cb.dataset.motorType));
      if (motorTypes.size > 1) {
        mismatchWarning.hidden = false;
        return;
      }
      receiveMotorBtn.hidden = false;
      receiveMotorBtn.disabled = false;
      return;
    }
    if (category === 'card_pending_receive') {
      receiveBtn.hidden = false;
      receiveBtn.disabled = false;
      return;
    }

    forwardBtn.hidden = false;
    forwardBtn.disabled = false;
    if (category === 'card') {
      forwardBtn.textContent = 'Dispatch';
      testedOkBtn.hidden = false;
      testedOkBtn.disabled = false;
    } else {
      forwardBtn.textContent = 'Service Center';
      repairBtn.hidden = false;
      repairBtn.disabled = false;
      oemBtn.hidden = false;
      oemBtn.disabled = false;
      scrapBtn.hidden = false;
      scrapBtn.disabled = false;
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
    setReceiveMotorFieldsRequired(false);
    setReceiveFieldsRequired(false);
    actionField.value = action;
    remarksDialogTitle.textContent = title;
    document.getElementById('id_simple_remarks').value = '';
    populateSelectedFields();
    remarksDialog.showModal();
  }

  function populateOemOptions(choices) {
    motorOemSelect.innerHTML = '<option value="">— Select —</option>';
    choices.forEach(([value, label]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      motorOemSelect.appendChild(option);
    });
  }

  function openReceiveMotorDialog() {
    setForwardFieldsRequired(false);
    setReceiveFieldsRequired(false);
    setReceiveMotorFieldsRequired(true);
    const selected = getSelected();
    const type = selected.length ? selected[0].dataset.motorType : '';
    const isMotor = type === 'motor';
    populateOemOptions(type === 'submersible_pump' ? submersibleOemChoices : motorSurfaceOemChoices);
    // Head/Inch size don't apply to a bare Motor -- only Surface/Submersible Pump.
    motorHeadSizeField.hidden = isMotor;
    motorInchSizeField.hidden = isMotor;
    motorHeadSizeSelect.required = !isMotor;
    motorInchSizeSelect.required = !isMotor;
    actionField.value = 'receive_motor';
    document.getElementById('id_motor_received_date').value = '';
    document.getElementById('id_motor_capacity').value = '';
    motorOemSelect.value = '';
    motorHeadSizeSelect.value = '';
    motorInchSizeSelect.value = '';
    document.getElementById('id_motor_receive_remarks').value = '';
    populateSelectedFields();
    receiveMotorDialog.showModal();
  }

  function openReceiveDialog() {
    setForwardFieldsRequired(false);
    setReceiveMotorFieldsRequired(false);
    setReceiveFieldsRequired(true);
    actionField.value = 'receive';
    document.getElementById('id_received_date').value = '';
    serialMatchesYes.checked = false;
    serialMatchesNo.checked = false;
    document.getElementById('id_received_serial_no').value = '';
    document.getElementById('id_reservation_no').value = '';
    document.getElementById('id_receive_remarks').value = '';
    updateSerialNoVisibility();
    populateSelectedFields();
    receiveDialog.showModal();
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
  if (scrapBtn) {
    scrapBtn.addEventListener('click', function () {
      openRemarksDialog('scrapped', 'Scrap');
    });
  }
  if (receiveMotorBtn) {
    receiveMotorBtn.addEventListener('click', openReceiveMotorDialog);
  }
  if (receiveBtn) {
    receiveBtn.addEventListener('click', openReceiveDialog);
  }
  if (forwardBtn) {
    forwardBtn.addEventListener('click', function () {
      setForwardFieldsRequired(true);
      setReceiveMotorFieldsRequired(false);
      setReceiveFieldsRequired(false);
      actionField.value = 'dispatch_forward';
      populateSelectedFields();
      forwardDialog.showModal();
    });
  }

  if (receiveMotorCancel) {
    receiveMotorCancel.addEventListener('click', function () {
      setReceiveMotorFieldsRequired(false);
      receiveMotorDialog.close();
    });
  }
  if (receiveCancel) {
    receiveCancel.addEventListener('click', function () {
      setReceiveFieldsRequired(false);
      receiveDialog.close();
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

  // Mirrors dispatch.js's identical By Hand behavior on the engineer's own
  // dispatch form -- hides (and clears) the courier-only fields, since a
  // By Hand dispatch has no pickup/LR/challan number.
  const fwdCourierOnlyFields = [
    document.getElementById('fwd-field-pickup-number'),
    document.getElementById('fwd-field-lr-number'),
    document.getElementById('fwd-field-delivery-challan-number'),
  ];

  if (fwdPartnerSelect && fwdCustomPartnerField) {
    fwdPartnerSelect.addEventListener('change', function () {
      const isOther = fwdPartnerSelect.value === 'other';
      fwdCustomPartnerField.hidden = !isOther;
      if (!isOther) {
        document.getElementById('id_fwd_custom_delivery_partner').value = '';
      }

      const isByHand = fwdPartnerSelect.value === 'by_hand';
      fwdCourierOnlyFields.forEach((field) => {
        if (!field) return;
        field.hidden = isByHand;
        if (isByHand) field.querySelector('input').value = '';
      });
    });
  }
});
