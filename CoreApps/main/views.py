# CoreApps/main/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, Http404
from django.views.generic import DetailView, TemplateView, FormView, UpdateView
from django.utils.text import slugify
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
# from .forms import RegistrationForm # <-- Descomentaremos esto luego
from django.urls import reverse_lazy # Para la redirección
from .forms import UserProfileForm, BusinessConfigForm # <-- Importar el nuevo form

# Importaciones de los nuevos modelos y utilidades
from CoreApps.users.models import Business, StaffMember, User, Customer, Plan, Subscription, ServiceZone
from CoreApps.catalog.models import Service
from CoreApps.scheduling.models import Appointment
from .utils import generate_available_slots

#pagina principal
class HomePageView(TemplateView):
    template_name = "main/home.html" # Nombre de nuestra nueva plantilla

#primera pantalla para suscripcion
class SelectPlanView(TemplateView):
    """
    Muestra los planes disponibles para que el usuario elija uno
    antes de registrarse.
    """
    template_name = "main/select_plan.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtenemos solo los planes marcados como activos
        context['plans'] = Plan.objects.filter(is_active=True).order_by('price_monthly')
        return context
#segunda pantalla para suscripcion
class RegistrationView(TemplateView): # Cambiaremos a FormView después
    template_name = "main/registration.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_id = self.request.GET.get('plan')
        if not plan_id:
            messages.error(self.request, "Por favor, selecciona un plan primero.")
            # Si no hay plan, redirigir a la selección de plan
            context['error'] = True # Indicador para la plantilla
            return context # O redirigir: redirect('select_plan')

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
            context['plan'] = plan
        except Plan.DoesNotExist:
            messages.error(self.request, "El plan seleccionado no es válido.")
            context['error'] = True
            # Redirigir si el plan no existe
            # return redirect('select_plan')

        # context['form'] = RegistrationForm() # Añadiremos el formulario después
        return context

    def post(self, request, *args, **kwargs):
        plan_id = request.GET.get('plan')
        if not plan_id:
             messages.error(request, "No se especificó un plan.")
             return redirect('select_plan')
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
             messages.error(request, "El plan seleccionado no es válido.")
             return redirect('select_plan')

        # --- Recoger datos del formulario ---
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password') # TODO: Añadir confirmación de contraseña
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        business_name = request.POST.get('business_name', '').strip()

        # --- Validaciones básicas (un Form sería mejor) ---
        if not all([email, password, first_name, last_name, business_name]):
            messages.error(request, "Todos los campos son obligatorios.")
            # Volver a mostrar el formulario con los datos
            # TODO: Repopular el formulario
            return self.get(request, *args, **kwargs)

        if User.objects.filter(email=email).exists():
             messages.error(request, "Ya existe un usuario con este correo electrónico.")
             return self.get(request, *args, **kwargs)

        # --- Creación de Objetos ---
        try:
            # 1. Crear User
            user = User.objects.create_user(
                username=email, # Usar email como username
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # 2. Crear Business
            business_slug = slugify(business_name)
            # Asegurar slug único (simple, se puede mejorar)
            counter = 1
            while Business.objects.filter(slug=business_slug).exists():
                business_slug = f"{slugify(business_name)}-{counter}"
                counter += 1

            business = Business.objects.create(
                user=user,
                display_name=business_name,
                slug=business_slug
                # Otros campos tomarán valores por defecto
            )

            # 3. Crear StaffMember por defecto para el dueño
            StaffMember.objects.create(
                business=business,
                name=f"{first_name} {last_name}", # Usar nombre del dueño
                user=user # Asociar al mismo User (opcional)
            )

            # 4. Crear Subscription en modo TRIAL
            trial_days = 30
            trial_end = date.today() + timedelta(days=trial_days)
            Subscription.objects.create(
                business=business,
                plan=plan,
                status=Subscription.SubscriptionStatus.TRIAL,
                trial_end_date=trial_end
            )

            # 5. Iniciar Sesión
            login(request, user)

            # 6. Redirigir al Dashboard
            messages.success(request, f"¡Bienvenido a Tivy! Tu prueba gratuita del plan {plan.name} ha comenzado.")
            return redirect('dashboard')

        except Exception as e:
            # Captura de error genérica (mejorar con logging)
            print(f"Error durante el registro: {e}")
            messages.error(request, "Ocurrió un error inesperado durante el registro. Por favor, intenta de nuevo.")
            # Podríamos borrar el usuario si se creó a medias, o manejarlo mejor
            return self.get(request, *args, **kwargs)

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


#@login_required
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/dashboard_home.html" # New template name for the main dashboard page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        business = None
        subscription = None
        plan = None

        # Try to find the Business profile associated with the logged-in user
        try:
            # Check if the user is the owner of a business
            business = Business.objects.get(user=user)
            # Find the subscription for this business
            subscription = Subscription.objects.select_related('plan').get(business=business)
            plan = subscription.plan
        except Business.DoesNotExist:
            # Handle case where user might be StaffMember or has no business yet
            # For now, we raise 404 if no business owner profile found
            # A better approach later might be to check StaffMember profile
            raise Http404("Perfil de negocio no encontrado para este usuario.")
        except Subscription.DoesNotExist:
            # Handle case where business exists but has no subscription (shouldn't happen with current registration logic)
            messages.error(self.request, "Error: No se encontró una suscripción para tu negocio.")
            # We can let it render the dashboard but show an error, or raise 404
            pass # Let it continue, but 'subscription' and 'plan' will be None

        # --- Subscription Status Check ---
        allowed_statuses = ['ACTIVE', 'TRIAL', 'DEMO']
        is_subscription_valid = subscription and subscription.status in allowed_statuses

        if not is_subscription_valid:
            # If subscription is not valid, maybe render a different template or add a flag
            self.template_name = "dashboard/dashboard_restricted.html" # Use a restricted template
            messages.warning(self.request, "Tu suscripción no está activa. Acceso limitado.")

        context['business'] = business
        context['subscription'] = subscription
        context['plan'] = plan
        context['is_subscription_valid'] = is_subscription_valid # Pass validity flag to template

        return context

class UserProfileView(LoginRequiredMixin, UpdateView):
    """
    Permite al usuario logueado editar su propio perfil (nombre, apellido).
    """
    model = User # El modelo que vamos a editar
    form_class = UserProfileForm # El formulario que usaremos
    template_name = 'dashboard/profile_form.html' # La plantilla para mostrar el form
    success_url = reverse_lazy('user_profile') # A dónde redirigir tras guardar con éxito

    def get_object(self, queryset=None):
        # Asegura que el usuario solo pueda editar su PROPIO perfil
        return self.request.user

    def form_valid(self, form):
        # Añadir un mensaje de éxito antes de guardar y redirigir
        messages.success(self.request, "Tu perfil ha sido actualizado con éxito.")
        return super().form_valid(form)
        
class BusinessConfigView(LoginRequiredMixin, UpdateView):
    model = Business
    form_class = BusinessConfigForm
    template_name = 'dashboard/business_config_form.html'
    success_url = reverse_lazy('business_config')

    def get_object(self, queryset=None):
        try:
            return self.request.user.business_profile
        except Business.DoesNotExist:
            raise Http404("No se encontró un negocio asociado a tu cuenta.")

    def get_initial(self):
        """ Carga las zonas actuales en el campo de texto, separadas por comas. """
        initial = super().get_initial()
        business = self.get_object()
        # Convertimos las zonas M2M a una cadena separada por comas para el input
        initial['service_zones_text'] = ", ".join([zone.name for zone in business.service_zones.all()])
        return initial

    def form_valid(self, form):
        business = form.instance # El objeto Business antes de guardar

        # --- Lógica modificada para procesar el CharField ---
        zones_text = form.cleaned_data.get('service_zones_text', '')
        # Dividimos por comas y limpiamos espacios
        tag_names = [name.strip() for name in zones_text.split(',') if name.strip()] 

        current_zones = []
        for name in tag_names:
            zone, created = ServiceZone.objects.get_or_create(name=name)
            current_zones.append(zone)
        
        # Guardamos el formulario principal SIN el M2M todavía
        # El campo 'service_zones_text' no es parte del modelo, así que no interfiere
        response = super().form_valid(form) 

        # AHORA asignamos las zonas al M2M después de que el Business se haya guardado
        business.service_zones.set(current_zones) 

        messages.success(self.request, "La configuración de tu negocio ha sido actualizada.")
        return response
        
#Primera pantalla donde se muestran los servicios y logo de la empresa.
class BusinessPublicProfileView(DetailView):
    model = Business
    template_name = 'main/public_profile.html'
    context_object_name = 'business'
    slug_field = 'slug'

    def get(self, request, *args, **kwargs):
        """
        Sobrescribimos el método GET para añadir la verificación de suscripción.
        """
        try:
            # Intentamos obtener el objeto Business usando la lógica de DetailView
            self.object = self.get_object()
        except Http404:
            # Si el negocio no existe por el slug, devolvemos 404
            raise Http404("Negocio no encontrado.")

        # --- Verificación del Estado de la Suscripción ---
        # Verificamos si tiene suscripción y si el estado es permitido
        allowed_statuses = ['ACTIVE', 'TRIAL', 'DEMO']
        has_valid_subscription = (
            hasattr(self.object, 'subscription') and
            self.object.subscription is not None and
            self.object.subscription.status in allowed_statuses
        )

        if not has_valid_subscription:
            # Si no tiene suscripción válida, devolvemos 404
            # (Podrías renderizar una plantilla específica si lo prefieres)
            raise Http404("Este negocio no está aceptando reservas en este momento.")

        # Si la suscripción es válida, procedemos con la lógica normal de DetailView
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.get_object() # get_object ya fue llamado en get()
        context['services'] = business.services.filter(is_active=True)
        # La obtención de staff_members se hará en el siguiente paso (SelectStaffAndTimeView)
        return context

    def post(self, request, *args, **kwargs):
        # La lógica POST no necesita la verificación de suscripción aquí,
        # ya que si llegó a esta página, la verificación GET ya pasó.
        # Solo verificamos que el objeto exista (lo cual get_object hace).
        self.object = self.get_object()

        service_id = request.POST.get('service_id')
        if service_id:
            request.session['selected_service_id'] = service_id
            return redirect(reverse('select_staff_and_time', kwargs={'slug': self.object.slug}))

        messages.error(request, "Por favor, selecciona un servicio.")
        return redirect(request.path_info)

#Segunda Pantalla donde permite elegir el profesional staff de la empresa y el horario de la cita o servicio
#tomar en cuenta que esta actualizado con los mnuevos modelos de plan y suscripcion.
class SelectStaffAndTimeView(TemplateView):
    template_name = 'main/select_staff_and_time.html'

    def get_context_data(self, **kwargs):
        print("\n--- Iniciando get_context_data ---") # DEBUG
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        service_id = self.request.session.get('selected_service_id')
        print(f"DEBUG: service_id de sesión: {service_id}") # DEBUG

        if not service_id:
            messages.warning(self.request, "Por favor, selecciona un servicio para continuar.")
            context['business'] = business
            context['staff_with_slots'] = []
            print("DEBUG: No se encontró service_id en sesión.") # DEBUG
            return context

        date_str = self.request.GET.get('date')
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        print(f"DEBUG: Fecha objetivo (target_date): {target_date}") # DEBUG

        service = get_object_or_404(Service, id=service_id)
        print(f"DEBUG: Servicio encontrado: {service.name} (ID: {service.id})") # DEBUG
        
        # --- Punto crítico 1: Encontrar staff elegible ---
        eligible_staff = StaffMember.objects.filter(
            business=business, 
            services_offered=service, # Filtra por el servicio asignado
            is_active=True
        )
        print(f"DEBUG: Staff elegible encontrado (QuerySet): {eligible_staff}") # DEBUG
        print(f"DEBUG: Número de staff elegible: {eligible_staff.count()}") # DEBUG

        staff_with_slots = []
        print("DEBUG: Calculando horarios para cada staff...") # DEBUG
        # --- Punto crítico 2: Calcular horarios para cada uno ---
        for staff in eligible_staff:
            print(f"DEBUG: Procesando staff: {staff.name} (ID: {staff.id})") # DEBUG
            # TODO: Determinar si es_domicilio y pasarlo
            is_domicilio_request = False 
            slots = generate_available_slots(staff, service, target_date, is_domicilio=is_domicilio_request)
            print(f"DEBUG: Slots encontrados para {staff.name} en {target_date}: {slots}") # DEBUG
            
            # Solo añadimos si tiene slots disponibles
            if slots: 
                staff_with_slots.append({
                    'staff': staff,
                    'slots': slots
                })
            else:
                 print(f"DEBUG: {staff.name} NO tiene slots para {target_date}, no se añade a la lista final.") # DEBUG

        # --- Punto crítico 3: Resultado final ---
        print(f"DEBUG: Lista final staff_with_slots: {staff_with_slots}") # DEBUG

        context['business'] = business
        context['service'] = service
        # context['staff_member'] = staff_member # Ya no pasamos un solo staff, sino la lista
        context['staff_with_slots'] = staff_with_slots 
        
        # Datos para el selector de fecha (sin cambios)
        days = []
        for i in range(7):
            current_day = date.today() + timedelta(days=i)
            day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            days.append({
                'date': current_day,
                'name': "Hoy" if i == 0 else "Mañana" if i == 1 else day_names[current_day.weekday()],
                'date_str': current_day.strftime('%Y-%m-%d')
            })

        context['available_days'] = days
        context['target_date_str'] = target_date.strftime('%Y-%m-%d')
        context['target_date_display'] = target_date.strftime('%d de %B de %Y')
        
        print("--- Finalizando get_context_data ---") # DEBUG
        return context

    def post(self, request, *args, **kwargs):
        # El post no debería ser el problema ahora, lo dejamos como está
        selected_time = request.POST.get('selected_time')
        selected_date = request.POST.get('selected_date')
        staff_id = request.session.get('selected_staff_id') # Recuperamos staff_id de la sesión si es necesario
        
        # Corrección: El staff_id viene del botón presionado, no de la sesión aquí
        staff_id_from_post = request.POST.get('staff_member_id')

        if selected_time and selected_date and staff_id_from_post:
            request.session['selected_time'] = selected_time
            request.session['selected_date'] = selected_date
            request.session['selected_staff_id'] = staff_id_from_post # Guardamos el staff elegido
            return redirect(reverse('confirm_booking', kwargs={'slug': self.kwargs.get('slug')}))
        
        messages.error(request, "Ocurrió un error. Por favor, selecciona un profesional y un horario.")
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
        # Obtenemos el Business de la URL
        business = self.get_object()
        # Obtenemos los IDs de la sesión
        service_id = self.request.session.get('selected_service_id')
        staff_id = self.request.session.get('selected_staff_id')
        selected_time_str = self.request.session.get('selected_time')
        selected_date_str = self.request.session.get('selected_date')
        
        # Validamos que todos los datos de sesión necesarios existan
        if not all([service_id, staff_id, selected_time_str, selected_date_str]):
            messages.error(self.request, "Faltan datos de la cita. Por favor, empieza de nuevo.")
            context['error'] = True # Indicador para la plantilla de que algo falló
            context['business'] = business # Pasamos business para que la plantilla base funcione
            return context

        # Obtenemos los objetos Service y StaffMember
        service = get_object_or_404(Service, id=service_id)
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        
        # Calculamos el datetime completo para mostrar en el resumen
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_datetime = datetime.combine(selected_date, selected_time)
            selected_datetime = timezone.make_aware(naive_datetime)
        except ValueError:
            messages.error(self.request, "Formato de fecha u hora inválido guardado en la sesión.")
            context['error'] = True
            context['business'] = business
            return context

        # Pasamos todos los datos necesarios al contexto de la plantilla
        context['business'] = business
        context['service'] = service
        context['staff_member'] = staff_member
        context['selected_datetime'] = selected_datetime
        return context
    
    def post(self, request, *args, **kwargs):
        # Obtenemos el Business de la URL
        business = self.get_object()
        # Obtenemos los IDs y datos de la sesión
        service_id = request.session.get('selected_service_id')
        staff_id = request.session.get('selected_staff_id')
        selected_time_str = request.session.get('selected_time')
        selected_date_str = request.session.get('selected_date')
        
        # Re-validamos que todos los datos de sesión existan antes de procesar
        if not all([service_id, staff_id, selected_time_str, selected_date_str]):
            messages.error(request, "Tu sesión ha expirado o faltan datos. Por favor, intenta de nuevo.")
            return redirect(reverse('business_profile', kwargs={'slug': business.slug}))

        # Obtenemos los objetos Service y StaffMember
        service = get_object_or_404(Service, id=service_id)
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        
        # Obtenemos los datos enviados por el formulario
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        address = request.POST.get('address', '').strip()
        location_choice = request.POST.get('location_choice', 'local') # 'local' o 'domicilio'

        # Validación básica del email
        if not email:
             messages.error(request, "El correo electrónico es obligatorio.")
             # Volvemos a renderizar el GET de esta misma vista
             return self.get(request, *args, **kwargs)

        # --- Lógica de Usuario Existente / Nuevo ---
        user = User.objects.filter(email=email).first()
        is_new_user = user is None

        if is_new_user:
            # Si es nuevo, necesita nombre y apellido
            if not first_name or not last_name:
                 messages.error(request, "Nombre y Apellido son obligatorios para nuevos usuarios.")
                 return self.get(request, *args, **kwargs)
            # Creamos el usuario sin contraseña usable
            user = User.objects.create_user(
                username=email, email=email, first_name=first_name,
                last_name=last_name, password=None
            )
        # Si el usuario ya existe, no modificamos sus datos centrales (User)

        # --- Lógica de Customer (Relación Usuario-Negocio) ---
        customer, customer_created = Customer.objects.get_or_create(
            user=user, 
            business=business,
            defaults={ # Valores por defecto SOLO si se crea el Customer
                'email': email, 
                'first_name': first_name if first_name else user.first_name, 
                'last_name': last_name if last_name else user.last_name,
                'phone_number': phone_number,
                # Guardamos la dirección solo si aplica al servicio/elección
                'address_line': address if (service.location_type == 'DOMICILIO' or (service.location_type == 'AMBOS' and location_choice == 'domicilio')) else None
            }
        )

        # --- Actualizamos datos del Customer si ya existía ---
        if not customer_created:
            update_fields = [] # Lista para actualizar solo campos modificados
            # Actualizar teléfono si se proporcionó uno nuevo
            if phone_number and customer.phone_number != phone_number:
                customer.phone_number = phone_number
                update_fields.append('phone_number')
            
            # Actualizar dirección si el servicio lo requiere y se proporcionó una
            is_domicilio_request = (service.location_type == 'DOMICILIO' or (service.location_type == 'AMBOS' and location_choice == 'domicilio'))
            if is_domicilio_request and address and customer.address_line != address:
                customer.address_line = address
                update_fields.append('address_line')
                # TODO: Guardar lat/lon si se capturan en el frontend y cambiaron
            
            # Actualizar nombre/apellido del perfil Customer si se proporcionaron y son diferentes
            if first_name and customer.first_name != first_name:
                customer.first_name = first_name
                update_fields.append('first_name')
            if last_name and customer.last_name != last_name:
                 customer.last_name = last_name
                 update_fields.append('last_name')

            # Guardamos solo si hubo cambios
            if update_fields:
                customer.save(update_fields=update_fields)

        # --- Crear la Cita ---
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_start_time = datetime.combine(selected_date, selected_time)
            start_time = timezone.make_aware(naive_start_time)
            end_time = start_time + service.duration
        except ValueError:
            messages.error(request, "Error en el formato de fecha u hora guardado en la sesión.")
            return self.get(request, *args, **kwargs)

        # Creamos la cita con las nuevas relaciones
        appointment = Appointment.objects.create(
            business=business,
            staff_member=staff_member,
            customer=customer,
            service=service,
            start_time=start_time,
            end_time=end_time
        )
        
        # Limpiamos los datos de la sesión relacionados con esta reserva
        request.session.pop('selected_service_id', None)
        request.session.pop('selected_staff_id', None)
        request.session.pop('selected_time', None)
        request.session.pop('selected_date', None)
        
        messages.success(request, f"¡Tu cita para {service.name} con {staff_member.name} ha sido agendada con éxito!")
        
        # Redirigimos a la página de confirmación de la cita recién creada
        return redirect(reverse('booking_confirmed', kwargs={'pk': appointment.pk}))
        
    def get_object(self):
        # El objeto principal sigue siendo el Business de la URL
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