from django.urls import path
from django.contrib.auth import views as auth_views

# Importamos TODAS las vistas que vamos a usar
from .views import (
    login_view, 
    dashboard_view, 
    ClientPublicProfileView, 
    SelectScheduleView, 
    ConfirmBookingView,
    check_customer_view # <-- La vista de API
)

urlpatterns = [
    # URLs de autenticación y panel
    path('login/', login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),

    # URLs del flujo de agendamiento
    path('p/<slug:slug>/', ClientPublicProfileView.as_view(), name='client_profile'),
    path('p/<slug:slug>/schedule/', SelectScheduleView.as_view(), name='select_schedule'),
    path('p/<slug:slug>/confirm/', ConfirmBookingView.as_view(), name='confirm_booking'),

    # --- RUTA DE LA API (ASEGÚRATE DE QUE ESTÉ PRESENTE) ---
    path('api/check-customer/', check_customer_view, name='check_customer'),
]