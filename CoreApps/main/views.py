# CoreApps/main/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, TemplateView
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime, date, timedelta
from urllib.parse import urlencode # Para generar el link de Google Calendar
from django.utils.timezone import localtime # Para mostrar la hora local
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden

# Importaciones de los nuevos modelos y utilidades
from CoreApps.users.models import Business, StaffMember, User, Customer
from CoreApps.catalog.models import Service
from CoreApps.scheduling.models import Appointment
from .utils import generate_available_slots

class HomePageView(TemplateView):
    template_name = "main/home.html" # Nombre de nuestra nueva plantilla

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Lógica de Redirección con los nuevos modelos
                if user.is_superuser:
                    return redirect('/admin/')
                elif hasattr(user, 'business_profile'):
                    # Si tiene perfil de Business, es un dueño de negocio
                    return redirect('dashboard')
                elif hasattr(user, 'staff_profile'):
                    # Si tiene perfil de Staff, es un empleado (futuro panel de empleado)
                    return redirect('dashboard')
                else:
                    # Si no, es un Customer, lo mandamos a la página de inicio
                    return redirect('/')
            else:
                messages.error(request, "Email o contraseña incorrectos.")
        else:
            messages.error(request, "Email o contraseña incorrectos.")
    
    form = AuthenticationForm()
    return render(request, 'main/login.html', {'form': form})


@login_required
def dashboard_view(request):
    # Este será el panel para el dueño del negocio o el personal
    return render(request, 'dashboard/professional_dashboard.html')

#Primera pantalla donde se muestran los servicios y logo de la empresa.
class BusinessPublicProfileView(DetailView):
    model = Business
    template_name = 'main/public_profile.html'
    context_object_name = 'business'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        context['services'] = business.services.filter(is_active=True)
        # Ya no necesitamos pasar staff_members aquí, se hará en el siguiente paso
        # context['staff_members'] = business.staff_members.filter(is_active=True) 
        return context

    def post(self, request, *args, **kwargs):
        service_id = request.POST.get('service_id')
        
        if service_id:
            # Guardamos SOLO el ID del servicio en la sesión
            request.session['selected_service_id'] = service_id
            
            # Redirigimos al NUEVO paso para seleccionar al personal
            return redirect(reverse('select_staff_and_time', kwargs={'slug': self.get_object().slug}))
            #return redirect(reverse('select_staff', kwargs={'slug': self.get_object().slug}))
        
        messages.error(request, "Por favor, selecciona un servicio.")
        return redirect(request.path_info)

#Segunda Pantalla donde permite elegir el profesional staff de la empresa y el horario de la cita o servicio
class SelectStaffAndTimeView(TemplateView):
    template_name = 'main/select_staff_and_time.html' # Cambiamos el nombre de la plantilla

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        service_id = self.request.session.get('selected_service_id')

        if not service_id:
            messages.warning(self.request, "Por favor, selecciona un servicio para continuar.")
            context['staff_with_slots'] = [] # Evita error en plantilla si no hay servicio
            return context

        # Determinar la fecha objetivo
        date_str = self.request.GET.get('date')
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

        service = get_object_or_404(Service, id=service_id)
        
        # Encontrar staff members que pueden hacer este servicio
        eligible_staff = StaffMember.objects.filter(
            business=business, 
            services_offered=service, # Filtra por el servicio
            is_active=True
        )

        # Calcular horarios para CADA staff member elegible
        staff_with_slots = []
        for staff in eligible_staff:
            slots = generate_available_slots(staff, service, target_date)
            if slots: # Solo incluir staff si tiene horarios disponibles ese día
                staff_with_slots.append({
                    'staff': staff,
                    'slots': slots
                })

        context['business'] = business
        context['service'] = service
        context['staff_with_slots'] = staff_with_slots # Lista de staff con sus horarios
        
        # Datos para el selector de fecha
        days = []
        for i in range(7):
            current_day = date.today() + timedelta(days=i)
            day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"] # Nombres cortos
            days.append({
                'date': current_day,
                'name': "Hoy" if i == 0 else "Mañana" if i == 1 else day_names[current_day.weekday()],
                'date_str': current_day.strftime('%Y-%m-%d')
            })

        context['available_days'] = days
        context['target_date_str'] = target_date.strftime('%Y-%m-%d')
        context['target_date_display'] = target_date.strftime('%d de %B de %Y')
        
        return context

    def post(self, request, *args, **kwargs):
        # El POST ahora recibe staff_id Y selected_time desde el botón presionado
        staff_id = request.POST.get('staff_member_id')
        selected_time = request.POST.get('selected_time')
        selected_date = request.POST.get('selected_date')
        
        if staff_id and selected_time and selected_date:
            # Guardamos todo en la sesión
            request.session['selected_staff_id'] = staff_id
            request.session['selected_time'] = selected_time
            request.session['selected_date'] = selected_date
            return redirect(reverse('confirm_booking', kwargs={'slug': self.kwargs.get('slug')}))
        
        messages.error(request, "Ocurrió un error. Por favor, selecciona un profesional y un horario.")
        # Reconstruir la URL actual con la fecha para recargar correctamente
        current_date = request.POST.get('selected_date', date.today().strftime('%Y-%m-%d'))
        redirect_url = reverse('select_staff_and_time', kwargs={'slug': self.kwargs.get('slug')}) + f'?date={current_date}'
        return redirect(redirect_url)

    def get_object(self):
        return get_object_or_404(Business, slug=self.kwargs.get('slug'))

#Tercera pantalla donde se confirma los datos del customer y todo organizado
class ConfirmBookingView(TemplateView):
    template_name = 'main/confirm_booking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        service_id = self.request.session.get('selected_service_id')
        staff_id = self.request.session.get('selected_staff_id')
        selected_time_str = self.request.session.get('selected_time')
        selected_date_str = self.request.session.get('selected_date')
        
        # Validamos que todos los datos de sesión existan
        if not all([service_id, staff_id, selected_time_str, selected_date_str]):
            messages.error(self.request, "Faltan datos de la cita. Por favor, empieza de nuevo.")
            context['error'] = True # Indicador para la plantilla
            return context

        service = get_object_or_404(Service, id=service_id)
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_datetime = datetime.combine(selected_date, selected_time)
            selected_datetime = timezone.make_aware(naive_datetime)
        except ValueError:
            messages.error(self.request, "Formato de fecha u hora inválido.")
            context['error'] = True
            return context

        context['business'] = business
        context['service'] = service
        context['staff_member'] = staff_member
        context['selected_datetime'] = selected_datetime
        return context
    
    def post(self, request, *args, **kwargs):
        business = self.get_object()
        service_id = request.session.get('selected_service_id')
        staff_id = request.session.get('selected_staff_id')
        selected_time_str = request.session.get('selected_time')
        selected_date_str = request.session.get('selected_date')
        
        if not all([service_id, staff_id, selected_time_str, selected_date_str]):
            messages.error(request, "Tu sesión ha expirado o faltan datos. Por favor, intenta de nuevo.")
            return redirect(reverse('business_profile', kwargs={'slug': business.slug}))

        service = get_object_or_404(Service, id=service_id)
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address = request.POST.get('address', '').strip()
        location_choice = request.POST.get('location_choice', 'local') # 'local' o 'domicilio'

        if not email:
            messages.error(request, "El correo electrónico es obligatorio.")
            # Volver a cargar la página con los datos de sesión intactos
            return redirect(request.path_info)

        # --- Lógica de Usuario Existente ---
        user = User.objects.filter(email=email).first()
        is_new_user = user is None

        if is_new_user:
            # Crear nuevo usuario (solo si los campos obligatorios están presentes)
            if not first_name or not last_name:
                messages.error(request, "Nombre y Apellido son obligatorios para nuevos usuarios.")
                return redirect(request.path_info)
            user = User.objects.create_user(
                username=email, # Usamos email como username
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=None # Contraseña no usable hasta que la establezca
            )
        # else: Si el usuario existe, NO tocamos sus datos (nombre, apellido, contraseña)

        # --- Lógica de Customer (Relación Usuario-Negocio) ---
        customer, customer_created = Customer.objects.get_or_create(
            user=user, 
            business=business,
            defaults={ # Solo se usan si se crea el Customer por primera vez
                'email': email, 
                'first_name': first_name if first_name else user.first_name, 
                'last_name': last_name if last_name else user.last_name,
                'phone_number': phone_number,
                'address_line': address if (service.location_type == 'DOMICILIO' or (service.location_type == 'AMBOS' and location_choice == 'domicilio')) else None
            }
        )

        # --- Actualizar datos del Customer si ya existía ---
        if not customer_created:
            # Actualizar teléfono SIEMPRE si se proporciona uno nuevo
            if phone_number:
                customer.phone_number = phone_number
            
            # Actualizar dirección si el servicio lo requiere y se proporciona
            is_domicilio_request = (service.location_type == 'DOMICILIO' or (service.location_type == 'AMBOS' and location_choice == 'domicilio'))
            if is_domicilio_request and address:
                customer.address_line = address
                # TODO: Guardar lat/lon si se capturan en el frontend
            
            # Actualizar nombre/apellido del perfil Customer si cambiaron (opcional, pero buena UX)
            if first_name and customer.first_name != first_name:
                customer.first_name = first_name
            if last_name and customer.last_name != last_name:
                 customer.last_name = last_name

            customer.save()

        # --- Crear la Cita ---
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_start_time = datetime.combine(selected_date, selected_time)
            start_time = timezone.make_aware(naive_start_time)
            end_time = start_time + service.duration
        except ValueError:
            messages.error(request, "Error en el formato de fecha u hora guardado.")
            return redirect(request.path_info)

        # Guardamos la cita creada para obtener su ID (pk)
        appointment = Appointment.objects.create(
            business=business,
            staff_member=staff_member,
            customer=customer,
            service=service,
            start_time=start_time,
            end_time=end_time
        )
        
        # Limpiar sesión
        request.session.pop('selected_service_id', None)
        request.session.pop('selected_staff_id', None)
        request.session.pop('selected_time', None)
        request.session.pop('selected_date', None)
        
        messages.success(request, f"¡Tu cita para {service.name} con {staff_member.name} ha sido agendada con éxito!")
        
        # --- LÍNEA MODIFICADA ---
        # Redirigimos a la nueva página de confirmación, pasando el ID de la cita creada
        return redirect(reverse('booking_confirmed', kwargs={'pk': appointment.pk}))
        
    def get_object(self):
        return get_object_or_404(Business, slug=self.kwargs.get('slug'))

#confirmación de la cita con sus datos, pantalla final.
class BookingConfirmedView(DetailView):
    """
    Muestra la página de confirmación después de agendar una cita.
    Usa DetailView para buscar la cita por su ID (pk).
    """
    model = Appointment
    template_name = 'main/booking_confirmed.html'
    context_object_name = 'appointment' # Cómo llamaremos a la cita en la plantilla

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.get_object()

        # --- Generar Enlace de Google Calendar ---
        start_time_utc = appointment.start_time.astimezone(timezone.utc)
        end_time_utc = appointment.end_time.astimezone(timezone.utc)

        params = {
            'action': 'TEMPLATE',
            'text': f'Cita: {appointment.service.name} con {appointment.staff_member.name}',
            'dates': f'{start_time_utc.strftime("%Y%m%dT%H%M%SZ")}/{end_time_utc.strftime("%Y%m%dT%H%M%SZ")}',
            'details': f'Cita para {appointment.service.name} reservada a través de Tivy.\nProfesional: {appointment.staff_member.name}\nNegocio: {appointment.business.display_name}',
            'location': appointment.business.address, # O la dirección del cliente si es a domicilio
        }
        google_calendar_url = f'https://www.google.com/calendar/render?{urlencode(params)}'
        context['google_calendar_url'] = google_calendar_url

        # Pasamos también la hora local para mostrarla
        context['local_start_time'] = localtime(appointment.start_time)

        return context

#Reprogramar la cita
class RescheduleAppointmentView(LoginRequiredMixin, TemplateView): # Usamos LoginRequiredMixin para seguridad
    template_name = 'main/reschedule_appointment.html'

    def dispatch(self, request, *args, **kwargs):
        # --- Verificación de Permisos ---
        appointment = self.get_object()
        # Solo el customer asociado a la cita puede reprogramarla (o superuser)
        # Una lógica más avanzada podría permitir al negocio reprogramar
        if appointment.customer.user != request.user and not request.user.is_superuser:
            return HttpResponseForbidden("No tienes permiso para modificar esta cita.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        appointment = self.get_object()
        service = appointment.service
        staff_member = appointment.staff_member
        business = appointment.business

        # Determinar la fecha objetivo (desde URL o hoy)
        date_str = self.request.GET.get('date')
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

        context['appointment'] = appointment
        context['business'] = business
        context['service'] = service
        context['staff_member'] = staff_member
        context['target_date_str'] = target_date.strftime('%Y-%m-%d')
        context['target_date_display'] = target_date.strftime('%d de %B de %Y')

        # --- Calcular Día Anterior/Siguiente ---
        today = date.today()
        prev_date = target_date - timedelta(days=1)
        next_date = target_date + timedelta(days=1)
        
        context['prev_date_str'] = prev_date.strftime('%Y-%m-%d')
        context['next_date_str'] = next_date.strftime('%Y-%m-%d')
        # Deshabilitar "Día Anterior" si ya estamos en hoy
        context['can_go_back'] = target_date > today

        # Generar slots disponibles para la fecha objetivo
        context['available_slots'] = generate_available_slots(staff_member, service, target_date)

        return context

    def post(self, request, *args, **kwargs):
        appointment = self.get_object()
        service = appointment.service
        
        selected_time_str = request.POST.get('selected_time')
        selected_date_str = request.POST.get('selected_date')

        if not selected_time_str or not selected_date_str:
            messages.error(request, "Por favor, selecciona una nueva fecha y hora.")
            return redirect(request.path_info) # Recargar la página de edición

        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_start_time = datetime.combine(selected_date, selected_time)
            new_start_time = timezone.make_aware(naive_start_time)
            new_end_time = new_start_time + service.duration
        except ValueError:
            messages.error(request, "Formato de fecha u hora inválido.")
            return redirect(request.path_info)

        # --- Validación de Disponibilidad (Doble Check) ---
        # Verificamos si el slot elegido SIGUE disponible
        # (Esta es una validación simple, una más robusta comprobaría colisiones)
        is_still_available = new_start_time.strftime('%H:%M') in generate_available_slots(
            appointment.staff_member, service, selected_date
        )
        # TODO: Añadir regla de negocio (ej. no reprogramar con < 24h)
        # time_until_appointment = appointment.start_time - timezone.now()
        # if time_until_appointment < timedelta(hours=24):
        #     messages.error(request, "No puedes reprogramar con menos de 24 horas de antelación.")
        #     return redirect(request.path_info)


        if is_still_available:
            # Actualizar la cita existente
            appointment.start_time = new_start_time
            appointment.end_time = new_end_time
            appointment.save()

            messages.success(request, "¡Tu cita ha sido reprogramada con éxito!")
            # Redirigir a la confirmación de la cita actualizada
            return redirect(reverse('booking_confirmed', kwargs={'pk': appointment.pk}))
        else:
            messages.error(request, "El horario seleccionado ya no está disponible. Por favor, elige otro.")
            return redirect(request.path_info)

    def get_object(self):
        # Obtenemos la cita específica usando el 'pk' de la URL
        return get_object_or_404(Appointment, pk=self.kwargs.get('pk'))

def check_customer_view(request):
    email = request.GET.get('email', None)
    if not email:
        return JsonResponse({'error': 'Email no proporcionado'}, status=400)

    try:
        user = User.objects.get(email=email)
        # La lógica se mantiene simple: devuelve los datos del usuario si existe.
        # Una mejora futura sería buscar si es cliente de este 'business' en particular.
        data = {'exists': True, 'first_name': user.first_name, 'last_name': user.last_name}
        customer_profile = Customer.objects.filter(user=user).last()
        if customer_profile:
             data['phone_number'] = customer_profile.phone_number

        return JsonResponse(data)

    except User.DoesNotExist:
        return JsonResponse({'exists': False})