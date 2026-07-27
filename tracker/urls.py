from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'tracker'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='tracker/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='tracker:login'), name='logout'),
    path('dispatch/', views.DispatchSubmitView.as_view(), name='dispatch_submit'),
    path('engineer/', views.EngineerHomeView.as_view(), name='engineer_home'),
    path('warehouse/', views.RegionalWarehouseHomeView.as_view(), name='warehouse_home'),
    path('warehouse/action/', views.WarehouseActionView.as_view(), name='warehouse_action'),
    path('main-warehouse/', views.MainWarehouseHomeView.as_view(), name='main_warehouse_home'),
    path('main-warehouse/action/', views.MainWarehouseActionView.as_view(), name='main_warehouse_action'),
    path('service-desk/', views.ServiceDeskHomeView.as_view(), name='service_desk_home'),
    path('service-desk/action/', views.ServiceDeskActionView.as_view(), name='service_desk_action'),
    path('electronics/', views.ElectronicsHomeView.as_view(), name='electronics_home'),
    path('electronics/action/', views.ElectronicsActionView.as_view(), name='electronics_action'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin-dashboard/users/', views.AdminUserManagementView.as_view(), name='admin_users'),
    path('admin-dashboard/users/action/', views.AdminUserActionView.as_view(), name='admin_users_action'),
    path('admin-dashboard/reports/', views.AdminReportsView.as_view(), name='admin_reports'),
    path('admin-dashboard/lookup/', views.AdminMaterialLookupView.as_view(), name='admin_lookup'),
    path('', views.HomeDispatchView.as_view(), name='home'),
]
