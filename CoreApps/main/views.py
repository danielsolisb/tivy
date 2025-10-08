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
from CoreApps.scheduling.models import AvailabilityRule, Appointment
from datetime import datetime, date, timedelta



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

    # --- AÑADE ESTE MÉTODO ---
    def post(self, request, *args, **kwargs):
        # Cuando el usuario envía el formulario (elige un servicio)...
        service_id = request.POST.get('service_id')
        if service_id:
            # Guardamos el ID del servicio en la sesión (el "carrito")
            request.session['selected_service_id'] = service_id
            # Redirigimos al usuario al siguiente paso (selección de horario)
            return redirect(reverse('select_schedule', kwargs={'slug': self.kwargs.get('slug')}))
        
        # Si algo sale mal, simplemente volvemos a cargar la página
        return redirect(self.request.path_info)
    """
    Muestra la página pública de un profesional usando una Vista Basada en Clases.
    """
    model = Client  # 1. Le decimos qué modelo debe buscar.
    template_name = 'main/public_profile.html'  # 2. Le decimos qué plantilla debe renderizar.
    context_object_name = 'client'  # 3. Le decimos cómo llamar al objeto en la plantilla.
    slug_field = 'slug'  # 4. Le decimos qué campo del modelo coincide con el 'slug' de la URL.

    def get_context_data(self, **kwargs):
        # Este método nos permite añadir más información (contexto) a la plantilla.
        
        # Primero, obtenemos el contexto base que DetailView ya preparó (que incluye el objeto 'client')
        context = super().get_context_data(**kwargs)
        
        # Ahora, añadimos nuestra información extra: la lista de servicios.
        # 'self.object' es el objeto 'Client' que DetailView ya encontró por nosotros.
        context['services'] = self.object.services.filter(is_active=True)
        
        return context

class SelectScheduleView(TemplateView):
    template_name = 'main/select_schedule.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service_id = self.request.session.get('selected_service_id')
        client = self.get_object()

        if not service_id:
            return context

        service = get_object_or_404(Service, id=service_id)
        context['service'] = service
        context['client'] = client

        # --- LÓGICA DE LA "FÁBRICA DE SLOTS" ---
        # TODO: Por ahora, calculamos para el día de hoy. Más adelante añadiremos un calendario.
        target_date = date.today() 
        
        # ¡Llamamos a nuestra nueva función para obtener los horarios reales!
        context['available_slots'] = generate_available_slots(client, service, target_date)
        context['target_date_display'] = target_date.strftime('%d de %B de %Y')

        return context

    def get_object(self):
        return get_object_or_404(Client, slug=self.kwargs.get('slug'))


def generate_available_slots(client, service, target_date):
    """
    Calcula los slots de tiempo disponibles para un cliente, un servicio y una fecha específicos.
    """
    available_slots = []
    
    # 1. Encontrar la regla de disponibilidad para ese día de la semana
    day_of_week = target_date.weekday() # Lunes=0, Domingo=6
    try:
        rule = AvailabilityRule.objects.get(client=client, day_of_week=day_of_week)
    except AvailabilityRule.DoesNotExist:
        return [] # Si no hay regla para ese día, no hay horarios.

    # 2. Obtener todas las citas ya agendadas para ese día
    existing_appointments = Appointment.objects.filter(client=client, start_time__date=target_date)

    # 3. Calcular la duración total del bloqueo (lógica de búfer)
    block_duration = service.duration
    # TODO: Aquí irá la lógica para añadir el travel_buffer si el servicio es a domicilio

    # 4. Iterar y encontrar los espacios libres
    step = timedelta(minutes=15) # Podemos buscar horarios cada 15 minutos
    current_time = datetime.combine(target_date, rule.start_time)
    end_time = datetime.combine(target_date, rule.end_time)

    while (current_time + block_duration) <= end_time:
        is_available = True
        # Comprobar si el slot se solapa con una cita existente
        for app in existing_appointments:
            # Un slot no está disponible si su inicio o fin cae dentro de una cita existente
            if (app.start_time <= current_time < app.end_time) or \
               (app.start_time < (current_time + block_duration) <= app.end_time):
                is_available = False
                break # No hace falta seguir comprobando, este slot está ocupado
        
        if is_available:
            available_slots.append(current_time.strftime('%H:%M'))

        current_time += step
        
    return available_slots