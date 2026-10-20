// "Download Excel": sends the keys of every row currently visible (current
// tab + search + filters) to the server, which builds the .xlsx.
document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('export-excel-form');
  const btn = document.getElementById('export-excel-btn');
  if (!form || !btn) return;
  btn.addEventListener('click', function () {
    form.querySelectorAll('input[name="keys"]').forEach((el) => el.remove());
    document.querySelectorAll('.table-row[data-export-key]').forEach((row) => {
      if (row.style.display === 'none') return;
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'keys';
      input.value = row.dataset.exportKey;
      form.appendChild(input);
    });
    form.submit();
  });
});
