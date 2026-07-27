document.addEventListener('DOMContentLoaded', function () {
  const addUserBtn = document.getElementById('add-user-btn');
  const createUserDialog = document.getElementById('create-user-dialog');
  const changePasswordDialog = document.getElementById('change-password-dialog');
  const changeRoleDialog = document.getElementById('change-role-dialog');

  if (addUserBtn && createUserDialog) {
    addUserBtn.addEventListener('click', function () {
      createUserDialog.querySelectorAll('input[type="text"], input[type="email"]').forEach((el) => (el.value = ''));
      createUserDialog.showModal();
    });
  }

  document.querySelectorAll('[data-open="change-password-dialog"]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById('id_password_target_user_id').value = btn.dataset.userId;
      document.getElementById('change-password-target').textContent = '- ' + btn.dataset.userEmail;
      document.getElementById('id_new_password_value').value = '';
      changePasswordDialog.showModal();
    });
  });

  document.querySelectorAll('[data-open="change-role-dialog"]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById('id_role_target_user_id').value = btn.dataset.userId;
      document.getElementById('change-role-target').textContent = '- ' + btn.dataset.userEmail;
      document.getElementById('id_new_role_value').value = btn.dataset.userRole;
      changeRoleDialog.showModal();
    });
  });

  document.querySelectorAll('[data-close]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.getElementById(btn.dataset.close).close();
    });
  });
});
