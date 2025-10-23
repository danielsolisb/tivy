# CoreApps/main/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

# Ahora importamos la vista del Paso 3 también
from .views import (
    login_view, 
    dashboard_view, 
    BusinessPublicProfileView,
    SelectStaffAndTimeView,
    ConfirmBookingView,    # <-- Descomentamos esta importación
    BookingConfirmedView,
    RescheduleAppointmentView,
    HomePageView,
    check_customer_view
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('', HomePageView.as_view(), name='home'),
    
    path('p/<slug:slug>/', BusinessPublicProfileView.as_view(), name='business_profile'),
    path('p/<slug:slug>/select-time/', SelectStaffAndTimeView.as_view(), name='select_staff_and_time'),
    path('p/<slug:slug>/confirm/', ConfirmBookingView.as_view(), name='confirm_booking'),
    path('booking-confirmed/<int:pk>/', BookingConfirmedView.as_view(), name='booking_confirmed'),
    path('appointment/<int:pk>/reschedule/', RescheduleAppointmentView.as_view(), name='reschedule_appointment'),
    
    path('api/check-customer/', check_customer_view, name='check_customer'),
]