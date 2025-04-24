from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Homepage and signup
    path('', views.home, name='home'),
    path('signup/', views.signup_view, name='signup'),

    # Login and logout
    path('login/', auth_views.LoginView.as_view(template_name='main/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),

    # Password reset flow
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='main/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='main/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='main/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='main/password_reset_complete.html'), name='password_reset_complete'),

    # Dashboards
    path('account/', views.account_info, name='account_info'),
    path('dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('owner-dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('concierge-dashboard/', views.concierge_dashboard, name='concierge_dashboard'),
    path('dealer-dashboard/', views.dealer_dashboard, name='dealer_dashboard'),
    path('redirect-after-login/', views.redirect_after_login, name='redirect_after_login'),

    # Cars
    path('my-cars/', views.my_cars, name='my_cars'),
    path('cars/add/', views.add_car, name='add_car'),
    path('delete-car/<int:car_id>/', views.delete_car, name='delete_car'),
    path('edit-car/<int:car_id>/', views.edit_car, name='edit_car'),

    # Service Requests
    path('request-service/', views.create_service_request, name='create_service_request'),
    path('service-request/<int:request_id>/delete/', views.delete_service_request, name='delete_service_request'),
    path('request/<int:request_id>/view/', views.view_service_request, name='view_service_request'),
    path('concierge/service/<int:request_id>/view/', views.view_service_request, name='concierge_view_service_request'),
    path('concierge/service/<int:request_id>/edit/', views.edit_service_request, name='edit_service_request'),
    path('requests/<int:pk>/set_delivery/', views.set_request_pending, name='set_request_delivery'),


    # Invoices
    path('invoice/<int:invoice_type>/<int:invoice_id>/', views.view_invoice, name='view_invoice'),
    path('owner-dashboard/edit-invoice/<int:invoice_id>/', views.edit_invoice, name='edit_invoice'),

    # Static Pages
    path('about/', TemplateView.as_view(template_name='main/about.html'), name='about'),
    path('contact/', TemplateView.as_view(template_name='main/contact.html'), name='contact'),

    # Concierge management
    path('concierge/add/', views.add_concierge, name='add_concierge'),
    path('concierges/', views.view_concierges, name='view_concierges'),
    path('concierges/edit/<int:concierge_id>/', views.edit_concierge, name='edit_concierge'),
    path('concierges/delete/<int:concierge_id>/', views.delete_concierge, name='delete_concierge'),

    # Owners
    path('add-owner/', views.add_owner, name='add_owner'),
    path('owners/', views.view_owners, name='view_owners'),
    path('owners/delete/<int:owner_id>/', views.delete_owner, name='delete_owner'),

    # Dealers
    path('add-dealer/', views.add_dealer, name='add_dealer'),
    path('dealers/', views.view_dealers, name='view_dealers'),
    path('dealers/edit/<int:dealer_id>/', views.edit_dealer, name='edit_dealer'),
    path('dealers/delete/<int:dealer_id>/', views.delete_dealer, name='delete_dealer'),

    # Inventory
    path('inventory/', views.view_inventory, name='view_inventory'),
    path('inventory/add/', views.add_inventory, name='add_inventory'),
    path('inventory/<int:inventory_id>/edit/', views.edit_inventory, name='edit_inventory'),
    path('inventory/delete/<int:item_id>/', views.delete_inventory, name='delete_inventory'),

    # Map live location
    path(
        'service-request/<int:request_id>/location/',
        views.service_request_location,
        name='service_request_location'
    ),
    path(
        'service-request/<int:request_id>/location/update/',
        views.update_concierge_location,
        name='update_concierge_location'
    ),

    # Health check endpoint (for Render)
    path('health/', views.health, name='health'),
]
