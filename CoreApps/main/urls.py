# CoreApps/main/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from django.shortcuts import render
# Necesitás esta importación para success_url en PasswordChangeView
from django.urls import reverse_lazy
# Ahora importamos la vista del Paso 3 también
from .views import (
    login_view, 
    DashboardView,
    BusinessPublicProfileView,
    SelectStaffAndTimeView,
    ConfirmBookingView,    # <-- Descomentamos esta importación
    BookingConfirmedView,
    RescheduleAppointmentView,
    HomePageView,
    SelectPlanView,
    RegistrationView,
    UserProfileView,
    check_customer_view,
    BusinessConfigView,
    ManageStaffView,
    StaffMemberUpdateView,
    ServiceListView,    # <-- Nueva
    ServiceCreateView,  # <-- Nueva
    ServiceUpdateView,   # <-- Nueva
    ManageAvailabilityView,
    AppointmentCalendarView,
    #API
    api_create_availability,
    api_create_time_off,
    api_get_availability_events,
    api_update_event,
    api_delete_event,
    api_get_appointments,
    api_update_appointment_status,
    add_owner_as_staff_view
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    #path('dashboard/', dashboard_view, name='dashboard'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/profile/', UserProfileView.as_view(), name='user_profile'),
    
    path('', HomePageView.as_view(), name='home'),
    path('seleccionar-plan/', SelectPlanView.as_view(), name='select_plan'),
    path('registro/', RegistrationView.as_view(), name='register'), # La activaremos después
    #path('registro/', lambda request: render(request, 'main/registration_placeholder.html'), name='register'),
    path('dashboard/password_change/',
         auth_views.PasswordChangeView.as_view(
             template_name='dashboard/password_change_form.html', # Nuestra plantilla personalizada
             success_url = reverse_lazy('password_change_done') # A dónde ir tras éxito
         ),
         name='password_change'),

    path('dashboard/password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='dashboard/password_change_done.html' # Nuestra plantilla personalizada
         ),
         name='password_change_done'),
    path('dashboard/configuracion/', BusinessConfigView.as_view(), name='business_config'),
    path('dashboard/personal/', ManageStaffView.as_view(), name='manage_staff'),
    path('personal/editar/<int:pk>/', StaffMemberUpdateView.as_view(), name='edit_staff'),
    path('dashboard/servicios/', ServiceListView.as_view(), name='service_list'),
    path('dashboard/servicios/nuevo/', ServiceCreateView.as_view(), name='service_create'),
    path('dashboard/servicios/<int:pk>/editar/', ServiceUpdateView.as_view(), name='service_update'),
    path('dashboard/disponibilidad/', ManageAvailabilityView.as_view(), name='manage_availability'),
    path('dashboard/appointments/', AppointmentCalendarView.as_view(), name='appointment_calendar'),

    path('dashboard/personal/add-owner/', add_owner_as_staff_view, name='add_owner_as_staff'),    

    #--------------Flujo de reserva------------------------------------------------------------------------#
    path('p/<slug:slug>/', BusinessPublicProfileView.as_view(), name='business_profile'),
    path('p/<slug:slug>/select-time/', SelectStaffAndTimeView.as_view(), name='select_staff_and_time'),
    path('p/<slug:slug>/confirm/', ConfirmBookingView.as_view(), name='confirm_booking'),
    path('booking-confirmed/<int:pk>/', BookingConfirmedView.as_view(), name='booking_confirmed'),
    path('appointment/<int:pk>/reschedule/', RescheduleAppointmentView.as_view(), name='reschedule_appointment'),
    
    #Api Endpoints
    path('api/check-customer/', check_customer_view, name='check_customer'),
    #Api para el calendario y disponibilidad
    path('api/availability/create/', api_create_availability, name='api_create_availability'),
    path('api/timeoff/create/', api_create_time_off, name='api_create_time_off'),
    path('api/availability/events/', api_get_availability_events, name='api_get_availability_events'),
    path('api/events/update/', api_update_event, name='api_update_event'),
    path('api/events/delete/', api_delete_event, name='api_delete_event'),
    #api para obtener las citas filtradas por rol
    path('api/appointments/get/', api_get_appointments, name='api_get_appointments'),
    #actualizacion de estado de citas
    path('api/appointment/status/update/', api_update_appointment_status, name='api_update_appointment_status'),
]