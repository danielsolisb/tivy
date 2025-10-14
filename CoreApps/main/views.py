# CoreApps/main/views.py
from django.shortcuts import render, redirect, get_object_or_404 # Añade get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from CoreApps.users.models import Client # Importa el modelo Client
from django.views.generic import DetailView, TemplateView
from django.urls import reverse
from CoreApps.catalog.models import Service 
from CoreApps.scheduling.models import Appointment
from datetime import datetime, date, timedelta
from .utils import generate_available_slots # Suponiendo que moviste la función a un archivo utils.py o la dejas en views.py
from CoreApps.users.models import User, Customer # Añade User y Customer
from django.contrib.auth.hashers import make_password # Para crear usuarios nuevos
from django.utils import timezone
from django.http import JsonResponse




def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # --- Lógica de Redirección por Rol ---
                if user.is_superuser:
                    # Si es superusuario, va al admin de Django
                    return redirect('/admin/')
                elif hasattr(user, 'client_profile'):
                    # Si tiene perfil de Client, es un profesional
                    return redirect('dashboard')
                else:
                    # Si no, es un Customer u otro tipo, lo mandamos al inicio
                    # (En el futuro, podría ser a 'mis-citas')
                    return redirect('/') # Cambiar a la URL de la página principal
            else:
                messages.error(request, "Email o contraseña incorrectos.")
        else:
            messages.error(request, "Email o contraseña incorrectos.")
    
    form = AuthenticationForm()
    return render(request, 'main/login.html', {'form': form})

@login_required
def dashboard_view(request):
    # Por ahora, es solo un placeholder.
    # Aquí irá la lógica para el panel del profesional.
    return render(request, 'dashboard/professional_dashboard.html')
class ClientPublicProfileView(DetailView):
    model = Client
    template_name = 'main/public_profile.html'
    context_object_name = 'client'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = self.object.services.filter(is_active=True)
        return context

    def post(self, request, *args, **kwargs):
        service_id = request.POST.get('service_id')
        if service_id:
            request.session['selected_service_id'] = service_id
            return redirect(reverse('select_schedule', kwargs={'slug': self.kwargs.get('slug')}))
        return redirect(self.request.path_info)
    
   

class SelectScheduleView(TemplateView):
    template_name = 'main/select_schedule.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_id = self.request.session.get('selected_service_id')
        client = self.get_object()

        if not service_id:
            messages.warning(self.request, "Por favor, selecciona un servicio para continuar.")
            return context

        # Obtener la fecha de la URL (ej: ?date=2025-10-09), si no, usar hoy
        date_str = self.request.GET.get('date')
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today()

        service = get_object_or_404(Service, id=service_id)
        context['service'] = service
        context['client'] = client
        
        # Generar los próximos 7 días para el selector
        days = []
        for i in range(7):
            current_day = date.today() + timedelta(days=i)
            day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            days.append({
                'date': current_day,
                'name': "Hoy" if i == 0 else "Mañana" if i == 1 else day_names[current_day.weekday()],
                'date_str': current_day.strftime('%Y-%m-%d')
            })

        context['available_days'] = days
        context['target_date'] = target_date
        context['target_date_str'] = target_date.strftime('%Y-%m-%d')
        context['target_date_display'] = target_date.strftime('%d de %B de %Y')
        context['available_slots'] = generate_available_slots(client, service, target_date)
        return context

    # El método post ahora debe guardar la fecha también
    def post(self, request, *args, **kwargs):
        selected_time = request.POST.get('selected_time')
        selected_date = request.POST.get('selected_date')
        if selected_time and selected_date:
            request.session['selected_time'] = selected_time
            request.session['selected_date'] = selected_date # Guardamos la fecha
            return redirect(reverse('confirm_booking', kwargs={'slug': self.kwargs.get('slug')}))
        
        messages.error(request, "Ocurrió un error. Por favor, intenta de nuevo.")
        return redirect(request.path_info)

    def get_object(self):
        return get_object_or_404(Client, slug=self.kwargs.get('slug'))

class ConfirmBookingView(TemplateView):
    template_name = 'main/confirm_booking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_id = self.request.session.get('selected_service_id')
        selected_time_str = self.request.session.get('selected_time')
        selected_date_str = self.request.session.get('selected_date')
        
        if not all([service_id, selected_time_str, selected_date_str]):
            messages.error(self.request, "Faltan datos de la cita. Por favor, empieza de nuevo.")
            # En una implementación más robusta, se redirigiría aquí,
            # pero para no romper el flujo de get_context_data, devolvemos un contexto vacío.
            # La redirección se puede manejar en un método dispatch.
            return context

        client = self.get_object()
        service = get_object_or_404(Service, id=service_id)
        
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        naive_datetime = datetime.combine(selected_date, datetime.strptime(selected_time_str, '%H:%M').time())
        selected_datetime = timezone.make_aware(naive_datetime)

        context['client'] = client
        context['service'] = service
        context['selected_datetime'] = selected_datetime
        return context
    
    def post(self, request, *args, **kwargs):
        service_id = request.session.get('selected_service_id')
        selected_time_str = request.session.get('selected_time')
        selected_date_str = request.session.get('selected_date')
        client = self.get_object()
        service = get_object_or_404(Service, id=service_id)
        
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
                'password': make_password(None)
            }
        )
        customer, created = Customer.objects.get_or_create(user=user, client=client, defaults={'email': email, 'first_name': first_name, 'last_name': last_name})
        
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        naive_start_time = datetime.combine(selected_date, datetime.strptime(selected_time_str, '%H:%M').time())
        start_time = timezone.make_aware(naive_start_time)
        end_time = start_time + service.duration
        
        Appointment.objects.create(
            customer=customer,
            client=client,
            service=service,
            start_time=start_time,
            end_time=end_time
        )
        
        # Limpiamos todos los datos de la sesión para la reserva
        del request.session['selected_service_id']
        del request.session['selected_time']
        del request.session['selected_date']
        
        messages.success(request, f"¡Tu cita para {service.name} ha sido agendada con éxito!")
        return redirect(reverse('client_profile', kwargs={'slug': client.slug}))
        
    def get_object(self):
        return get_object_or_404(Client, slug=self.kwargs.get('slug'))

def check_customer_view(request):
    """
    Una vista de API que comprueba si un cliente existe por su email.
    Devuelve datos en formato JSON.
    """
    email = request.GET.get('email', None)
    if not email:
        return JsonResponse({'error': 'Email no proporcionado'}, status=400)

    try:
        user = User.objects.get(email=email)
        # Buscamos el perfil de Customer más reciente para este usuario
        customer_profile = Customer.objects.filter(user=user).last()

        if customer_profile:
            data = {
                'exists': True,
                'first_name': customer_profile.first_name,
                'last_name': customer_profile.last_name,
                'phone_number': customer_profile.phone_number,
            }
        else:
            # El usuario existe en Tivy, pero no como cliente de este profesional aún
            data = {'exists': True, 'first_name': user.first_name, 'last_name': user.last_name, 'phone_number': ''}
        
        return JsonResponse(data)

    except User.DoesNotExist:
        return JsonResponse({'exists': False})
