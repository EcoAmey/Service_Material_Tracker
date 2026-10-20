// Per-item "Receive Motor/Pump" form shared by the regional and main
// warehouse pages: every selected motor/pump gets its own capacity, OEM,
// head size and inch size (field names suffixed with the item's pk, read by
// views._motor_receive_forms). Only the receive date is common.
window.MotorReceive = (function () {
  function json(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : [];
  }

  function select(name, label, choices, required) {
    const wrap = document.createElement('div');
    wrap.className = 'field';
    const lab = document.createElement('label');
    lab.textContent = label;
    const sel = document.createElement('select');
    sel.name = name;
    sel.setAttribute('form', 'action-form');
    sel.required = required;
    sel.innerHTML = '<option value="">— Select —</option>';
    choices.forEach(([value, text]) => {
      const opt = document.createElement('option');
      opt.value = value;
      opt.textContent = text;
      sel.appendChild(opt);
    });
    wrap.append(lab, sel);
    return wrap;
  }

  function fill(selected) {
    const list = document.getElementById('motor-receive-list');
    const capacity = json('motor-capacity-choices');
    const head = json('motor-head-size-choices');
    const inch = json('motor-inch-size-choices');
    const surfaceOem = json('motor-surface-oem-choices');
    const submersibleOem = json('submersible-oem-choices');
    list.innerHTML = '';

    selected.forEach((cb) => {
      const pk = cb.value;
      const type = cb.dataset.motorType;
      const isMotor = type === 'motor';
      const card = document.createElement('fieldset');
      card.className = 'motor-receive-item';
      card.dataset.type = type;
      const legend = document.createElement('legend');
      legend.textContent = cb.dataset.label || ('Item ' + pk);
      card.appendChild(legend);

      card.appendChild(select('motor_capacity_' + pk, 'Capacity', capacity, true));
      card.appendChild(select('motor_oem_name_' + pk, 'OEM Name', type === 'submersible_pump' ? submersibleOem : surfaceOem, true));
      if (!isMotor) {
        card.appendChild(select('motor_head_size_' + pk, 'Head Size', head, true));
        card.appendChild(select('motor_inch_size_' + pk, 'Inch Size', inch, true));
      }
      const remarks = document.createElement('div');
      remarks.className = 'field';
      remarks.innerHTML = '<label>Remarks (optional)</label>';
      const ta = document.createElement('textarea');
      ta.name = 'motor_receive_remarks_' + pk;
      ta.rows = 2;
      ta.setAttribute('form', 'action-form');
      remarks.appendChild(ta);
      card.appendChild(remarks);
      list.appendChild(card);
    });

    const copyBtn = document.getElementById('motor-copy-first');
    if (copyBtn) copyBtn.hidden = selected.length < 2;
    const date = document.getElementById('id_motor_received_date');
    if (date) { date.value = ''; date.required = true; }
  }

  // Removing the fields when the dialog closes (Cancel, Esc or submit) keeps
  // a stale `required` select from blocking some other dialog's submit.
  function clear() {
    const list = document.getElementById('motor-receive-list');
    if (list) list.innerHTML = '';
    const date = document.getElementById('id_motor_received_date');
    if (date) date.required = false;
  }

  function copyFirst() {
    const cards = Array.from(document.querySelectorAll('.motor-receive-item'));
    if (cards.length < 2) return;
    const first = cards[0];
    cards.slice(1).forEach((card) => {
      if (card.dataset.type !== first.dataset.type) return;
      first.querySelectorAll('select').forEach((src, i) => {
        const dst = card.querySelectorAll('select')[i];
        if (dst) dst.value = src.value;
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const dialog = document.getElementById('receive-motor-dialog');
    if (dialog) dialog.addEventListener('close', clear);
    const copyBtn = document.getElementById('motor-copy-first');
    if (copyBtn) copyBtn.addEventListener('click', copyFirst);
  });

  return { fill, clear };
})();
