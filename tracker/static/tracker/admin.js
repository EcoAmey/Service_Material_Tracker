document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('admin-sidebar');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const isMobile = () => window.matchMedia('(max-width: 899px)').matches;

  // Every admin page is a full reload (plain links, no SPA routing), so the
  // collapsed state has to be persisted -- otherwise it silently resets to
  // expanded on every navigation, which reads as "the sidebar re-expands
  // when I click another section."
  const SIDEBAR_COLLAPSED_KEY = 'admin-sidebar-collapsed';
  if (sidebar && !isMobile() && localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1') {
    sidebar.classList.add('collapsed');
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      if (isMobile()) {
        sidebar.classList.toggle('mobile-open');
        sidebarBackdrop.classList.toggle('visible', sidebar.classList.contains('mobile-open'));
      } else {
        sidebar.classList.toggle('collapsed');
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebar.classList.contains('collapsed') ? '1' : '0');
      }
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', function () {
      sidebar.classList.remove('mobile-open');
      sidebarBackdrop.classList.remove('visible');
    });
  }

  // Placeholder nav items (sections not built yet) shouldn't navigate.
  document.querySelectorAll('.admin-nav-soon').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
    });
  });
});
