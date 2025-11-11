# CoreApps/main/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, TemplateView, FormView, ListView
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.edit import FormMixin # <-- Añadir FormMixin
from django.utils.text import slugify
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import datetime, date, timedelta, time
from urllib.parse import urlencode # Para generar el link de Google Calendar
from django.utils.timezone import localtime # Para mostrar la hora local
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum, Count
from django.contrib import messages
# from .forms import RegistrationForm # <-- Descomentaremos esto luego
from django.urls import reverse_lazy # Para la redirección
from .forms import UserProfileForm, BusinessConfigForm, StaffMemberForm, ServiceForm # <-- Importar el nuevo form
import json

# Importaciones de los nuevos modelos y utilidades
from CoreApps.users.models import Business, StaffMember, User, Customer, Plan, Subscription, ServiceZone
from CoreApps.scheduling.models import AvailabilityBlock, TimeOffBlock
from CoreApps.catalog.models import Service
from CoreApps.scheduling.models import Appointment
from .utils import generate_available_slots

from .forms import EmailAuthenticationForm

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
class RegistrationView(TemplateView):
    template_name = "main/registration.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan_id = self.request.GET.get('plan')
        if not plan_id:
            messages.error(self.request, "Por favor, selecciona un plan primero.")
            context['error'] = True
            return context 

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
            context['plan'] = plan
        except Plan.DoesNotExist:
            messages.error(self.request, "El plan seleccionado no es válido.")
            context['error'] = True
        
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
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        business_name = request.POST.get('business_name', '').strip()

        # --- Validaciones básicas (un Form sería mejor) ---
        if not all([email, password, first_name, last_name, business_name]):
            messages.error(request, "Todos los campos son obligatorios.")
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
            counter = 1
            while Business.objects.filter(slug=business_slug).exists():
                business_slug = f"{slugify(business_name)}-{counter}"
                counter += 1

            business = Business.objects.create(
                user=user,
                display_name=business_name,
                slug=business_slug
            )

            # --- INICIO DE LA MODIFICACIÓN (PASO 3) ---
            
            # 3. Crear StaffMember por defecto para el dueño (YA NO LO HACEMOS)
            # Hemos comentado este bloque. Ahora el dueño es solo admin
            # y debe añadirse manualmente si quiere ser staff.
            
            # StaffMember.objects.create(
            #     business=business,
            #     name=f"{first_name} {last_name}", # Usar nombre del dueño
            #     user=user # Asociar al mismo User
            # )
            
            # --- FIN DE LA MODIFICACIÓN ---

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
            return self.get(request, *args, **kwargs)

def login_view(request):
    if request.method == 'POST':
        # --- CAMBIO: Usa EmailAuthenticationForm ---
        form = EmailAuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            # --- CAMBIO: 'username' ahora contiene el email explícitamente ---
            username = form.cleaned_data.get('username') 
            password = form.cleaned_data.get('password')
            
            # Llamamos a authenticate. Nuestro EmailAuthBackend se encargará.
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Tu lógica de redirección (sin cambios, está perfecta)
                if user.is_superuser:
                    return redirect('/admin/')
                elif hasattr(user, 'business_profile'):
                    return redirect('dashboard')
                elif hasattr(user, 'staff_profile'):
                    return redirect('dashboard')
                else:
                    return redirect('/')
            else:
                messages.error(request, "Email o contraseña incorrectos.")
        else:
            messages.error(request, "Email o contraseña incorrectos.")
    
    # --- CAMBIO: Pasa el EmailAuthenticationForm vacío ---
    form = EmailAuthenticationForm()
    return render(request, 'main/login.html', {'form': form})


#@login_required
class DashboardView(LoginRequiredMixin, TemplateView):
    # Apuntamos al mismo template, pero lo vamos a rediseñar
    template_name = "dashboard/dashboard_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        business = None
        subscription = None
        plan = None

        # --- Lógica de Negocio y Suscripción (EXISTENTE Y SIN CAMBIOS) ---
        try:
            business = Business.objects.get(user=user)
            subscription = Subscription.objects.select_related('plan').get(business=business)
            plan = subscription.plan
        except Business.DoesNotExist:
            raise Http404("Perfil de negocio no encontrado para este usuario.")
        except Subscription.DoesNotExist:
            messages.error(self.request, "Error: No se encontró una suscripción para tu negocio.")
            pass 

        allowed_statuses = ['ACTIVE', 'TRIAL', 'DEMO']
        is_subscription_valid = subscription and subscription.status in allowed_statuses

        if not is_subscription_valid:
            self.template_name = "dashboard/dashboard_restricted.html" # Plantilla restringida
            messages.warning(self.request, "Tu suscripción no está activa. Acceso limitado.")

        context['business'] = business
        context['subscription'] = subscription
        context['plan'] = plan
        context['is_subscription_valid'] = is_subscription_valid
        
        # --- INICIO DE NUEVA LÓGICA: DATOS DEL DASHBOARD ---
        # Solo calculamos esto si la suscripción es válida
        if is_subscription_valid and business:
            
            # --- Definir Fechas ---
            today = timezone.localdate()
            now = timezone.now()
            seven_days_ago = today - timedelta(days=6)
            thirty_days_ago = today - timedelta(days=29)

            # --- 1. KPIs (Tarjetas Superiores) ---
            
            # Citas e Ingresos de HOY
            today_appointments = Appointment.objects.filter(
                business=business, 
                start_time__date=today
            )
            context['kpi_total_appointments_today'] = today_appointments.exclude(status='CANCELED').count()
            
            context['kpi_revenue_today'] = today_appointments.exclude(status='CANCELED').aggregate(
                total=Sum('service__price')
            )['total'] or 0
            
            # Nuevos Clientes (Últimos 7 días)
            context['kpi_new_clients_week'] = Customer.objects.filter(
                business=business, 
                created_at__date__gte=seven_days_ago
            ).count()

            # --- 2. Lista de Próximas Citas ---
            context['upcoming_appointments'] = Appointment.objects.filter(
                business=business, 
                start_time__gte=now, 
                status='SCHEDULED'
            ).select_related('service', 'customer', 'staff_member').order_by('start_time')[:3] # Próximas 3

            # --- 3. Datos para Gráficos ---

            # Gráfico de Barras: Rendimiento Semanal (Citas completadas)
            daily_counts_qs = Appointment.objects.filter(
                business=business, 
                start_time__date__gte=seven_days_ago, 
                status='COMPLETED'
            ).values('start_time__date').annotate(count=Count('id')).order_by('start_time__date')
            
            # Formatear para Chart.js
            date_map = {item['start_time__date']: item['count'] for item in daily_counts_qs}
            chart_labels_weekly = []
            chart_data_weekly = []
            for i in range(7):
                date = seven_days_ago + timedelta(days=i)
                chart_labels_weekly.append(date.strftime('%a %d')) # Ej: "Lun 27"
                chart_data_weekly.append(date_map.get(date, 0))

            context['chart_weekly_labels'] = json.dumps(chart_labels_weekly)
            context['chart_weekly_data'] = json.dumps(chart_data_weekly)

            # Gráfico de Pastel: Top 5 Servicios (Últimos 30 días)
            top_services_qs = Appointment.objects.filter(
                business=business, 
                start_time__date__gte=thirty_days_ago
            ).values('service__name').annotate(count=Count('id')).order_by('-count')[:5]

            context['chart_top_services_labels'] = json.dumps([item['service__name'] for item in top_services_qs])
            context['chart_top_services_data'] = json.dumps([item['count'] for item in top_services_qs])

            # Gráfico de Pastel: Top 5 Staff (Últimos 30 días)
            top_staff_qs = Appointment.objects.filter(
                business=business, 
                start_time__date__gte=thirty_days_ago
            ).values('staff_member__name').annotate(count=Count('id')).order_by('-count')[:5]

            context['chart_top_staff_labels'] = json.dumps([item['staff_member__name'] for item in top_staff_qs])
            context['chart_top_staff_data'] = json.dumps([item['count'] for item in top_staff_qs])

        # --- FIN DE NUEVA LÓGICA ---

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
        
class ManageStaffView(LoginRequiredMixin, FormMixin, ListView):
    model = StaffMember
    template_name = 'dashboard/manage_staff.html'
    context_object_name = 'staff_list'
    form_class = StaffMemberForm

    def get_queryset(self):
        try:
            business = self.request.user.business_profile
            return StaffMember.objects.filter(business=business).order_by('name')
        except Business.DoesNotExist:
            return StaffMember.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            business = self.request.user.business_profile
            subscription = Subscription.objects.select_related('plan').get(business=business)
            plan = subscription.plan
        except (Business.DoesNotExist, Subscription.DoesNotExist):
             messages.error(self.request, "No se pudo cargar la información de tu negocio o suscripción.")
             context['can_add_staff'] = False
             context['limit_message'] = "Error al cargar datos."
             
             # --- INICIO DE NUEVA LÓGICA ---
             # Asegurarnos de que estas variables existan incluso si hay un error
             context['is_owner_staff'] = False 
             context['form'] = self.get_form()
             # --- FIN DE NUEVA LÓGICA ---
             
             return context

        context['business'] = business
        context['subscription'] = subscription
        context['plan'] = plan

        # --- INICIO DE NUEVA LÓGICA ---
        # Comprobar si el dueño ya es un miembro del staff
        try:
            StaffMember.objects.get(business=business, user=self.request.user)
            context['is_owner_staff'] = True
        except StaffMember.DoesNotExist:
            context['is_owner_staff'] = False
        # --- FIN DE NUEVA LÓGICA ---

        current_staff_count = self.get_queryset().count()
        max_staff = plan.max_staff
        can_add = (max_staff == -1) or (current_staff_count < max_staff)

        context['current_staff_count'] = current_staff_count
        context['max_staff'] = "Ilimitado" if max_staff == -1 else max_staff
        context['can_add_staff'] = can_add
        if not can_add:
            context['limit_message'] = f"Has alcanzado el límite de {context['max_staff']} miembros de personal para tu plan {plan.name}."

        context['form'] = self.get_form()
        return context

    def post(self, request, *args, **kwargs):
        try:
            business = request.user.business_profile
            subscription = Subscription.objects.select_related('plan').get(business=business)
            plan = subscription.plan
        except (Business.DoesNotExist, Subscription.DoesNotExist):
            messages.error(request, "Error al procesar la solicitud.")
            return redirect('manage_staff')

        current_staff_count = StaffMember.objects.filter(business=business).count()
        max_staff = plan.max_staff
        if max_staff != -1 and current_staff_count >= max_staff:
             messages.error(request, f"No puedes añadir más personal. Has alcanzado el límite de {max_staff} para tu plan.")
             return redirect('manage_staff')

        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        business = self.request.user.business_profile
        
        name = form.cleaned_data['name']
        give_access = form.cleaned_data['give_access']
        email = form.cleaned_data.get('email', '').strip()
        first_name = form.cleaned_data.get('first_name', '').strip()
        last_name = form.cleaned_data.get('last_name', '').strip()
        phone_number = form.cleaned_data.get('phone_number', '').strip()
        
        # --- INICIO DE NUEVA LÓGICA ---
        photo = form.cleaned_data.get('photo', None) # Obtenemos la foto
        staff_photo = None
        # --- FIN DE NUEVA LÓGICA ---


        if give_access and not all([email, first_name, last_name]):
            messages.error(self.request, "Si das acceso al dashboard, el Correo, Nombre y Apellido son obligatorios.")
            return self.render_to_response(self.get_context_data(form=form))

        staff_user = None
        user_created = False
        if give_access:
            # (Tu lógica existente para crear/buscar usuario... sin cambios)
            user = User.objects.filter(email=email).first()
            if user is None:
                temp_password = User.objects.make_random_password()
                print(f"DEBUG: Contraseña temporal para {email}: {temp_password}") 
                user = User.objects.create_user(
                    username=email, email=email,
                    first_name=first_name,
                    last_name=last_name,
                    phone_number=phone_number,
                    password=temp_password
                )
                user_created = True
                messages.info(self.request, f"Se creó una cuenta para {email}.")
            else:
                messages.info(self.request, f"El usuario {email} ya existe. Se vinculará al nuevo perfil de personal.")
                if phone_number and user.phone_number != phone_number:
                    user.phone_number = phone_number
                    user.save(update_fields=['phone_number'])
            
            if StaffMember.objects.filter(business=business, user=user).exists():
                messages.error(self.request, f"El usuario {email} ya está asignado a otro perfil de personal en este negocio.")
                if user_created:
                    user.delete()
                return self.render_to_response(self.get_context_data(form=form))
            
            staff_user = user
            
        # --- INICIO DE NUEVA LÓGICA ---
        # Si NO se dio acceso (es un recurso), asignamos la foto
        else:
            staff_photo = photo
        # --- FIN DE NUEVA LÓGICA ---

        # Crear el StaffMember
        StaffMember.objects.create(
            business=business,
            name=name,
            user=staff_user, # Será None si give_access es False
            photo=staff_photo # --- CAMBIO AQUÍ --- (Será None si give_access es True)
        )

        messages.success(self.request, f"Se ha añadido '{name}' al personal.")
        return redirect('manage_staff')

    def form_invalid(self, form):
         messages.error(self.request, "Por favor, corrige los errores en el formulario.")
         return self.render_to_response(self.get_context_data(form=form))

class StaffMemberUpdateView(LoginRequiredMixin, UpdateView):
    model = StaffMember
    form_class = StaffMemberForm
    template_name = 'dashboard/edit_staff.html'  # Crearemos este template
    success_url = reverse_lazy('manage_staff')   # A dónde ir después de guardar
    context_object_name = 'staff'              # Nombre del objeto en el template
    
    def get_object(self, queryset=None):
        """
        Asegura que el staff a editar pertenezca
        al negocio del usuario logueado.
        """
        obj = super().get_object(queryset)
        try:
            business = self.request.user.business_profile
            if obj.business != business:
                raise Http404("No tienes permiso para editar este personal.")
        except Business.DoesNotExist:
            raise Http404("Perfil de negocio no encontrado.")
        return obj

    def get_initial(self):
        """
        Pre-rellena el formulario con los datos actuales
        del StaffMember y del User (si existe).
        """
        initial = super().get_initial()
        staff = self.get_object()
        
        # Datos del StaffMember
        initial['name'] = staff.name
        
        # Datos del User (si está vinculado)
        if staff.user:
            initial['give_access'] = True
            initial['email'] = staff.user.email
            initial['first_name'] = staff.user.first_name
            initial['last_name'] = staff.user.last_name
            initial['phone_number'] = staff.user.phone_number
        else:
            initial['give_access'] = False
            
        return initial

    def form_valid(self, form):
        staff = self.get_object() 
        business = self.request.user.business_profile
        
        name = form.cleaned_data['name']
        give_access = form.cleaned_data['give_access']
        email = form.cleaned_data.get('email', '').strip()
        first_name = form.cleaned_data.get('first_name', '').strip()
        last_name = form.cleaned_data.get('last_name', '').strip()
        phone_number = form.cleaned_data.get('phone_number', '').strip()
        
        # --- INICIO DE NUEVA LÓGICA ---
        photo = form.cleaned_data.get('photo', None) # Obtenemos la foto
        # --- FIN DE NUEVA LÓGICA ---

        staff.name = name

        if give_access:
            # (Tu lógica existente de 'if give_access' ... sin cambios)
            if not all([email, first_name, last_name]):
                messages.error(self.request, "Si das acceso, el Correo, Nombre y Apellido son obligatorios.")
                return self.form_invalid(form)

            target_user = User.objects.filter(email=email).first()
            
            if staff.user:
                if staff.user.email != email and target_user:
                     messages.error(self.request, f"El email {email} ya pertenece a otro usuario.")
                     return self.form_invalid(form)
                staff.user.email = email
                staff.user.username = email
                staff.user.first_name = first_name
                staff.user.last_name = last_name
                staff.user.phone_number = phone_number
                staff.user.save()
                messages.success(self.request, f"Se actualizaron los datos de usuario para {staff.name}.")
            
            else:
                if target_user:
                    if StaffMember.objects.filter(business=business, user=target_user).exists():
                        messages.error(self.request, f"El usuario {email} ya está asignado a otro perfil de personal.")
                        return self.form_invalid(form)
                    staff.user = target_user
                    messages.info(self.request, f"Se vinculó al usuario existente {email} a {staff.name}.")
                else:
                    temp_password = User.objects.make_random_password()
                    print(f"DEBUG: Contraseña temporal para {email}: {temp_password}")
                    user = User.objects.create_user(
                        username=email, email=email,
                        first_name=first_name, last_name=last_name,
                        phone_number=phone_number, password=temp_password
                    )
                    staff.user = user
                    messages.info(self.request, f"Se creó y vinculó una nueva cuenta para {email}.")
            
            # --- INICIO DE NUEVA LÓGICA ---
            # Si damos acceso, borramos la foto de recurso (si existía)
            if staff.photo:
                staff.photo = None
            # --- FIN DE NUEVA LÓGICA ---
        
        else:
            # --- INICIO DE NUEVA LÓGICA ---
            # NO se da acceso (es un Recurso)
            if staff.user:
                messages.warning(self.request, f"Se ha desvinculado la cuenta de usuario de {staff.name}. El usuario no ha sido borrado.")
                staff.user = None # Desvinculamos el usuario
            
            # Si se subió una nueva foto, la guardamos
            if photo:
                staff.photo = photo
            # Si no se subió una nueva, simplemente dejamos la que ya tenía (o no)
            # --- FIN DE NUEVA LÓGICA ---

        staff.save()
        messages.success(self.request, f"Se ha actualizado el perfil de '{staff.name}'.")
        return redirect(self.success_url)
    
    def form_invalid(self, form):
        messages.error(self.request, "Por favor, corrige los errores en el formulario.")
        return super().form_invalid(form)

class ServiceListView(LoginRequiredMixin, ListView):
    """ Muestra la lista de servicios del negocio logueado. """
    model = Service
    template_name = 'dashboard/service_list.html'
    context_object_name = 'services'

    def get_queryset(self):
        # Filtrar servicios por el negocio del usuario logueado
        try:
            business = self.request.user.business_profile
            return Service.objects.filter(business=business).order_by('name')
        except Business.DoesNotExist:
            return Service.objects.none()

    def get_context_data(self, **kwargs):
        # Opcional: Pasar el business al contexto si la plantilla lo necesita
        context = super().get_context_data(**kwargs)
        try:
             context['business'] = self.request.user.business_profile
        except Business.DoesNotExist:
             context['business'] = None
        return context

class ServiceCreateView(LoginRequiredMixin, CreateView):
    """ Permite crear un nuevo servicio. """
    model = Service
    form_class = ServiceForm
    template_name = 'dashboard/service_form.html'
    success_url = reverse_lazy('service_list') # Redirigir a la lista tras crear

    def get_form_kwargs(self):
        # Pasamos el 'business' actual al __init__ del formulario
        kwargs = super().get_form_kwargs()
        kwargs['business'] = self.request.user.business_profile
        return kwargs

    def form_valid(self, form):
        # Asignamos el negocio al servicio antes de guardarlo
        form.instance.business = self.request.user.business_profile
        messages.success(self.request, f"Servicio '{form.instance.name}' creado con éxito.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        # Añadir título para la plantilla
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Añadir Nuevo Servicio"
        return context

class ServiceUpdateView(LoginRequiredMixin, UpdateView):
    """ Permite editar un servicio existente. """
    model = Service
    form_class = ServiceForm
    template_name = 'dashboard/service_form.html'
    success_url = reverse_lazy('service_list') # Redirigir a la lista tras editar

    def get_queryset(self):
        # Asegurarnos que solo se puedan editar servicios del negocio propio
        business = self.request.user.business_profile
        return Service.objects.filter(business=business)

    def get_form_kwargs(self):
        # Pasamos el 'business' actual al __init__ del formulario
        kwargs = super().get_form_kwargs()
        kwargs['business'] = self.request.user.business_profile
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Servicio '{form.instance.name}' actualizado con éxito.")
        return super().form_valid(form)
        
    def get_context_data(self, **kwargs):
        # Añadir título para la plantilla
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Servicio: {self.object.name}"
        return context

# En CoreApps/main/views.py

class ManageAvailabilityView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/manage_availability.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        business = None
        selected_staff = None
        staff_list = []

        try:
            business = user.business_profile
            staff_list = StaffMember.objects.filter(business=business, is_active=True).order_by('name')

            staff_id_param = self.request.GET.get('staff_id')
            if staff_id_param:
                try:
                    selected_staff = staff_list.get(id=staff_id_param)
                except StaffMember.DoesNotExist:
                    messages.warning(self.request, "El miembro del personal seleccionado no es válido.")
                    selected_staff = staff_list.filter(user=user).first() or staff_list.first()
            else:
                 selected_staff = staff_list.filter(user=user).first() or staff_list.first()

            context['business'] = business
            context['staff_list'] = staff_list
            context['selected_staff'] = selected_staff
            
            # --- La lógica de 'calendar_events_json' se ha ELIMINADO de aquí ---

        except Business.DoesNotExist:
             messages.error(self.request, "No se encontró un negocio asociado a tu cuenta.")
        except Exception as e:
            messages.error(self.request, f"Ocurrió un error inesperado al cargar datos: {e}")

        # Ya no pasamos 'calendar_events_json'
        return context

class AppointmentCalendarView(LoginRequiredMixin, TemplateView):
    """
    Muestra la página principal del calendario que contendrá las citas.
    """
    template_name = 'dashboard/appointment_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Determinar el contexto del negocio, ya sea como dueño o como staff
        try:
            # Opción 1: El usuario es el dueño del negocio
            context['business'] = user.business_profile
        except Business.DoesNotExist:
            try:
                # Opción 2: El usuario es un miembro del staff
                staff_member = user.staff_profiles.first()
                if staff_member:
                    context['business'] = staff_member.business
                else:
                    messages.error(self.request, "No estás asociado a ningún negocio.")
                    context['business'] = None
            except Exception as e:
                messages.error(self.request, f"Error al cargar tu perfil: {e}")
                context['business'] = None
        
        context['page_title'] = "Calendario de Citas"
        return context


@login_required
@require_POST  # Esta vista solo acepta peticiones POST
def add_owner_as_staff_view(request):
    try:
        business = request.user.business_profile
    except Business.DoesNotExist:
        messages.error(request, "No se encontró tu perfil de negocio.")
        return redirect('dashboard')
    
    # 1. Comprobar si ya existe (seguridad)
    if StaffMember.objects.filter(business=business, user=request.user).exists():
        messages.warning(request, "Ya eres parte del personal.")
        return redirect('manage_staff')

    # 2. Comprobar el límite de personal (lógica copiada de tu ManageStaffView.post)
    try:
        subscription = Subscription.objects.select_related('plan').get(business=business)
        plan = subscription.plan
        current_staff_count = StaffMember.objects.filter(business=business).count()
        max_staff = plan.max_staff
        
        if max_staff != -1 and current_staff_count >= max_staff:
            messages.error(request, f"No puedes añadirte. Has alcanzado el límite de {max_staff} para tu plan.")
            return redirect('manage_staff')
            
    except Subscription.DoesNotExist:
        messages.error(request, "Error al verificar la suscripción.")
        return redirect('manage_staff')

    # 3. Todo en orden. Crear el StaffMember para el dueño.
    owner_name = request.user.get_full_name() or request.user.email
    StaffMember.objects.create(
        business=business,
        user=request.user,
        name=owner_name
        # 'photo' es None, así que la propiedad 'get_photo_url' usará la foto del User.
    )
    
    messages.success(request, f"¡Listo! Te has añadido al personal como '{owner_name}'.")
    return redirect('manage_staff')


#API para calendarios y disponibilidad
@login_required
@require_POST # Solo permitir peticiones POST
def api_create_availability(request):
    """
    Endpoint de API para crear bloques de disponibilidad (Horario Laboral),
    incluyendo lógica de recurrencia.
    """
    try:
        staff_id = request.POST.get('staff_id')
        start_dt_str = request.POST.get('start_time')
        end_dt_str = request.POST.get('end_time')
        staff_can_edit = request.POST.get('staff_can_edit') == 'on' # Checkbox
        is_repeating = request.POST.get('repeat') == 'on' # Checkbox
        repeat_days = request.POST.getlist('repeat_on') # Lista de días (ej: ['0', '2', '4'])
        repeat_until_str = request.POST.get('repeat_until')

        # --- Validación de Permisos ---
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        # El usuario logueado debe ser el dueño del negocio de este staff
        if staff_member.business.user != request.user:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para modificar este calendario.'}, status=403)

        # --- Parseo de Fechas/Horas ---
        start_datetime = datetime.fromisoformat(start_dt_str)
        end_datetime = datetime.fromisoformat(end_dt_str)
        start_time_obj = start_datetime.time()
        end_time_obj = end_datetime.time()

        if end_datetime <= start_datetime:
            return JsonResponse({'success': False, 'error': 'La hora de fin debe ser posterior a la hora de inicio.'}, status=400)

        blocks_to_create = []

        if is_repeating and repeat_days and repeat_until_str:
            # --- Lógica de Recurrencia ---
            repeat_until_date = datetime.strptime(repeat_until_str, '%Y-%m-%d').date()
            current_date = start_datetime.date()
            end_repeat_date = min(repeat_until_date, current_date + timedelta(days=365)) # Límite de 1 año

            repeat_days_int = [int(day) for day in repeat_days] # Convertir a enteros (0=Lunes, 6=Domingo)

            while current_date <= end_repeat_date:
                # Si el día de la semana está en los días seleccionados
                if current_date.weekday() in repeat_days_int:
                    # Crear el datetime de inicio y fin para ESE día
                    new_start_dt = timezone.make_aware(datetime.combine(current_date, start_time_obj))
                    new_end_dt = timezone.make_aware(datetime.combine(current_date, end_time_obj))
                    
                    blocks_to_create.append(
                        AvailabilityBlock(
                            staff_member=staff_member,
                            start_time=new_start_dt,
                            end_time=new_end_dt,
                            staff_can_edit=staff_can_edit
                        )
                    )
                current_date += timedelta(days=1)
        else:
            # --- Creación Única ---
            blocks_to_create.append(
                AvailabilityBlock(
                    staff_member=staff_member,
                    start_time=timezone.make_aware(start_datetime),
                    end_time=timezone.make_aware(end_datetime),
                    staff_can_edit=staff_can_edit
                )
            )

        # TODO: Añadir validación de solapamiento (overlap) aquí antes de crear

        # Crear todos los bloques en la base de datos
        AvailabilityBlock.objects.bulk_create(blocks_to_create)
        
        return JsonResponse({'success': True, 'message': f'Se crearon {len(blocks_to_create)} bloques.'})

    except Exception as e:
        print(f"Error en api_create_availability: {e}") # Para depuración en servidor
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def api_create_time_off(request):
    """
    Endpoint de API para crear un bloqueo de tiempo libre (TimeOffBlock).
    """
    try:
        staff_id = request.POST.get('staff_id')
        start_dt_str = request.POST.get('start_time')
        end_dt_str = request.POST.get('end_time')
        reason = request.POST.get('reason', '')

        # --- Validación de Permisos ---
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        # El dueño O el propio staff (si tiene login) pueden crear un bloqueo
        is_owner = staff_member.business.user == request.user
        is_self = staff_member.user == request.user
        
        if not is_owner and not is_self:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para crear este bloqueo.'}, status=403)

        start_datetime = timezone.make_aware(datetime.fromisoformat(start_dt_str))
        end_datetime = timezone.make_aware(datetime.fromisoformat(end_dt_str))

        if end_datetime <= start_datetime:
            return JsonResponse({'success': False, 'error': 'La hora de fin debe ser posterior a la hora de inicio.'}, status=400)
        
        # TODO: Validación de solapamiento

        TimeOffBlock.objects.create(
            staff_member=staff_member,
            start_time=start_datetime,
            end_time=end_datetime,
            reason=reason
        )

        return JsonResponse({'success': True, 'message': 'Bloqueo creado.'})

    except Exception as e:
        print(f"Error en api_create_time_off: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def api_get_availability_events(request):
    """
    Endpoint de API para que FullCalendar obtenga los eventos (horarios y bloqueos)
    de un miembro del personal.
    """
    # Obtenemos el staff_id de los parámetros GET (ej: ?staff_id=8)
    staff_id = request.GET.get('staff_id')
    
    # Parámetros opcionales que FullCalendar envía automáticamente
    # start_str = request.GET.get('start')
    # end_str = request.GET.get('end')

    if not staff_id:
        return JsonResponse([], safe=False) # Devolver lista vacía si no hay staff

    try:
        staff_member = StaffMember.objects.get(id=staff_id)
        
        # --- Validación de Permisos ---
        # El usuario logueado debe ser el dueño del negocio O el propio staff
        is_owner = staff_member.business.user == request.user
        is_self = staff_member.user == request.user
        
        if not is_owner and not is_self:
            return JsonResponse({'error': 'No tienes permiso'}, status=403)
        
        # --- Obtener y Formatear Eventos ---
        # Filtramos por staff. FullCalendar manejará el filtrado por rango de fechas
        # si le pasamos todos los eventos.
        availability_blocks = AvailabilityBlock.objects.filter(staff_member=staff_member)
        time_off_blocks = TimeOffBlock.objects.filter(staff_member=staff_member)
        
        events = []
        # Formatear Horarios Laborales
        for block in availability_blocks:
            events.append({
                'id': f'avail_{block.pk}',
                'title': 'Disponible',
                'start': block.start_time.isoformat(),
                'end': block.end_time.isoformat(),
                
                # --- INICIO DE LA CORRECCIÓN ---
                # 'display': 'background',  <-- ELIMINADO O COMENTADO
                'color': '#198754',         # <-- AÑADIR (Verde sólido de Bootstrap)
                'borderColor': '#146c43',  # <-- AÑADIR (Borde más oscuro)
                'textColor': '#ffffff',     # <-- AÑADIR (Texto blanco)
                # --- FIN DE LA CORRECCIÓN ---

                'extendedProps': {
                    'type': 'availability',
                    'editable_by_staff': block.staff_can_edit
                }
            })
        # Formatear Bloqueos de Tiempo Libre
        for block in time_off_blocks:
             events.append({
                'id': f'off_{block.pk}',
                'title': block.reason or 'Tiempo Bloqueado',
                'start': block.start_time.isoformat(),
                'end': block.end_time.isoformat(),
                'color': '#f8d7da',
                'borderColor': '#dc3545',
                'textColor': '#58151c',
                 'extendedProps': {
                    'type': 'time_off'
                }
            })
            
        # Devolvemos la lista de eventos como JSON
        return JsonResponse(events, safe=False)

    except StaffMember.DoesNotExist:
        return JsonResponse([], safe=False)
    except Exception as e:
        print(f"Error en api_get_availability_events: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
def api_update_event(request):
    """
    Endpoint de API para ACTUALIZAR un bloque existente (ya sea Horario o Tiempo Libre).
    """
    try:
        event_id_str = request.POST.get('event_id')
        start_dt_str = request.POST.get('start_time')
        end_dt_str = request.POST.get('end_time')

        if not all([event_id_str, start_dt_str, end_dt_str]):
            return JsonResponse({'success': False, 'error': 'Faltan datos requeridos.'}, status=400)

        # 1. Parsear el ID del evento para saber el tipo y el PK
        try:
            event_type, pk = event_id_str.split('_')
            pk = int(pk)
        except (ValueError, IndexError):
            return JsonResponse({'success': False, 'error': 'ID de evento no válido.'}, status=400)

        # 2. Obtener el objeto correcto y validar permisos
        model = None
        if event_type == 'avail':
            model = AvailabilityBlock
        elif event_type == 'off':
            model = TimeOffBlock
        else:
            return JsonResponse({'success': False, 'error': 'Tipo de evento desconocido.'}, status=400)

        try:
            event_obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
             return JsonResponse({'success': False, 'error': 'El bloque no fue encontrado.'}, status=404)


        # Permiso: Solo el dueño del negocio puede editar
        if event_obj.staff_member.business.user != request.user:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para editar este bloque.'}, status=403)

        # 3. Actualizar el objeto
        event_obj.start_time = timezone.make_aware(datetime.fromisoformat(start_dt_str))
        event_obj.end_time = timezone.make_aware(datetime.fromisoformat(end_dt_str))

        if event_type == 'avail':
            # Actualiza campos específicos de AvailabilityBlock
            event_obj.staff_can_edit = request.POST.get('staff_can_edit') == 'on'
        elif event_type == 'off':
            # Actualiza campos específicos de TimeOffBlock
            event_obj.reason = request.POST.get('reason', '')

        event_obj.save()

        return JsonResponse({'success': True, 'message': 'Bloque actualizado correctamente.'})

    except Exception as e:
        # Log del error en el servidor para depuración
        print(f"Error en api_update_event: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_POST
def api_delete_event(request):
    """
    Endpoint de API para ELIMINAR un bloque existente.
    """
    try:
        event_id_str = request.POST.get('event_id')
        if not event_id_str:
            return JsonResponse({'success': False, 'error': 'ID de evento no proporcionado.'}, status=400)

        # Parsear ID y obtener el objeto (lógica similar a la de actualización)
        try:
            event_type, pk = event_id_str.split('_')
            pk = int(pk)
        except (ValueError, IndexError):
            return JsonResponse({'success': False, 'error': 'ID de evento no válido.'}, status=400)

        model = AvailabilityBlock if event_type == 'avail' else TimeOffBlock if event_type == 'off' else None
        if not model:
            return JsonResponse({'success': False, 'error': 'Tipo de evento desconocido.'}, status=400)

        try:
            event_obj = model.objects.get(pk=pk)
        except ObjectDoesNotExist:
             return JsonResponse({'success': False, 'error': 'El bloque no fue encontrado.'}, status=404)

        # Permiso: Solo el dueño del negocio puede eliminar
        if event_obj.staff_member.business.user != request.user:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para eliminar este bloque.'}, status=403)

        # Eliminar el objeto
        event_obj.delete()

        return JsonResponse({'success': True, 'message': 'Bloque eliminado correctamente.'})

    except Exception as e:
        print(f"Error en api_delete_event: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- API PARA OBTENER LAS CITAS FILTRADAS POR ROL ---
@login_required
def api_get_appointments(request):
    """
    Endpoint de API para que FullCalendar obtenga las CITAS (Appointments)
    filtradas por el rol del usuario (Dueño vs Staff).
    
    CORREGIDO:
    - Compara los estados con 'COMPLETED' y 'CANCELED' (del modelo)
      en lugar de 'COMPLETADA' y 'CANCELADA'.
    """
    user = request.user
    
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    if not start_str or not end_str:
        return JsonResponse({'error': 'Faltan parámetros de fecha.'}, status=400)

    try:
        naive_start_date = datetime.fromisoformat(start_str)
        naive_end_date = datetime.fromisoformat(end_str)
        
        start_date = timezone.make_aware(naive_start_date)
        end_date = timezone.make_aware(naive_end_date)
        
    except ValueError:
        return JsonResponse({'error': 'Formato de fecha inválido.'}, status=400)

    base_queryset = Appointment.objects.none()

    if hasattr(user, 'business_profile'):
        business = user.business_profile
        base_queryset = Appointment.objects.filter(
            business=business,
            start_time__range=[start_date, end_date]
        )
    elif hasattr(user, 'staff_profiles') and user.staff_profiles.exists():
        staff_member = user.staff_profiles.first()
        base_queryset = Appointment.objects.filter(
            staff_member=staff_member,
            start_time__range=[start_date, end_date]
        )
    
    appointments = base_queryset.select_related(
        'service', 
        'customer',
        'staff_member'
    ).order_by('start_time')

    events = []
    
    for app in appointments:
        title = f"{app.service.name}\n"
        title += f"Cliente: {app.customer.first_name} {app.customer.last_name}\n"
        
        if hasattr(user, 'business_profile'):
             title += f"Staff: {app.staff_member.name}"

        # --- LÓGICA DE COLOR POR ESTADO (CORREGIDA) ---
        color = '#007bff' # Azul (Agendada - SCHEDULED)
        if app.status == 'COMPLETED':   # <-- CORREGIDO
            color = '#198754' # Verde
        elif app.status == 'CANCELED':  # <-- CORREGIDO
            color = '#dc3545' # Rojo

        events.append({
            'id': app.pk,
            'title': title,
            'start': app.start_time.isoformat(),
            'end': app.end_time.isoformat(),
            'color': color, 
            'borderColor': color,
            'extendedProps': {
                'service_name': app.service.name,
                'client_name': f"{app.customer.first_name} {app.customer.last_name}",
                'client_phone': app.customer.phone_number or "N/A",
                'staff_name': app.staff_member.name,
                'price': f"${app.service.price}",
                'status_display': app.get_status_display(),
                'raw_status': app.status 
            }
        })

    return JsonResponse(events, safe=False)


#actualizacion de estado de las citas
@login_required
@require_POST
def api_update_appointment_status(request):
    """
    Endpoint de API para actualizar el estado de una cita.
    """
    try:
        data = json.loads(request.body)
        appointment_id = data.get('appointment_id')
        new_status = data.get('status')

        if not appointment_id or not new_status:
            return JsonResponse({'success': False, 'error': 'Faltan datos.'}, status=400)

        # Validar que el estado sea uno de los permitidos
        valid_statuses = [status[0] for status in Appointment.STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Estado no válido.'}, status=400)

        # Obtener la cita
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        
        # --- Validación de Permisos ---
        user = request.user
        is_owner = hasattr(user, 'business_profile') and appointment.business == user.business_profile
        
        # --- CORRECCIÓN APLICADA AQUÍ ---
        # 1. Comprobar si el usuario logueado TIENE un perfil de staff
        is_staff = hasattr(user, 'staff_profile')
        # 2. Si es staff, comprobar si SU perfil de staff es IGUAL al staff de la cita
        is_assigned_staff = is_staff and (user.staff_profile == appointment.staff_member)
        # --- FIN DE LA CORRECCIÓN ---

        if not is_owner and not is_assigned_staff:
            return JsonResponse({'success': False, 'error': 'No tienes permiso para modificar esta cita.'}, status=403)
        
        # Actualizar el estado y guardar
        appointment.status = new_status
        appointment.save()

        return JsonResponse({'success': True, 'message': 'Estado de la cita actualizado.'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Datos JSON mal formados.'}, status=400)
    except Exception as e:
        print(f"Error en api_update_appointment_status: {e}")
        # Devuelve el error real que estabas viendo
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

#------------------------------------------------------------------------------#
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
        # ... (Tu método get_context_data está perfecto, no necesita cambios) ...
        # ... (Se mantiene exactamente igual) ...
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        service_id = self.request.session.get('selected_service_id')
        staff_id = self.request.session.get('selected_staff_id')
        selected_time_str = self.request.session.get('selected_time')
        selected_date_str = self.request.session.get('selected_date')
        
        if not all([service_id, staff_id, selected_time_str, selected_date_str]):
            messages.error(self.request, "Faltan datos de la cita. Por favor, empieza de nuevo.")
            context['error'] = True
            context['business'] = business
            return context

        service = get_object_or_404(Service, id=service_id)
        staff_member = get_object_or_404(StaffMember, id=staff_id)
        
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
        location_choice = request.POST.get('location_choice', 'local')

        if not email:
            messages.error(request, "El correo electrónico es obligatorio.")
            return self.get(request, *args, **kwargs)

        # --- INICIO DE LA LÓGICA REFACTORIZADA ---
        user = User.objects.filter(email=email).first()
        is_new_user = user is None

        if is_new_user:
            if not first_name or not last_name:
                messages.error(request, "Nombre y Apellido son obligatorios para nuevos usuarios.")
                return self.get(request, *args, **kwargs)
            
            # --- CAMBIO: Implementamos tu lógica de contraseña aleatoria ---
            # (Por ahora se imprime, en el futuro se enviará por email)
            password = User.objects.make_random_password()
            print(f"DEBUG: Contraseña temporal para {email}: {password}")

            user = User.objects.create_user(
                username=email, 
                email=email, 
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number, # Guardamos el teléfono en el User
                password=password # Usamos la contraseña aleatoria
            )
        else:
            # Si el usuario ya existe, actualizamos su teléfono si es necesario
            if phone_number and user.phone_number != phone_number:
                user.phone_number = phone_number
                user.save(update_fields=['phone_number'])
            # (Ya no actualizamos nombre/apellido, esos son fijos del User)

        # --- Lógica de Customer (Relación Usuario-Negocio) REFACTORIZADA ---
        
        # Determinamos si la dirección es necesaria
        is_domicilio_request = (service.location_type == 'DOMICILIO' or (service.location_type == 'AMBOS' and location_choice == 'domicilio'))
        address_to_save = address if is_domicilio_request else None

        customer, customer_created = Customer.objects.get_or_create(
            user=user, 
            business=business,
            defaults={ # Valores por defecto SOLO si se crea el Customer
                'address_line': address_to_save
                # Ya no pasamos first_name, email, etc.
            }
        )

        # --- Actualizamos datos del Customer si ya existía (SOLO DIRECCIÓN) ---
        if not customer_created:
            update_fields = []
            
            if is_domicilio_request and address and customer.address_line != address:
                customer.address_line = address
                update_fields.append('address_line')
                # TODO: Guardar lat/lon
            
            # (Ya no actualizamos first_name, last_name, phone)

            if update_fields:
                customer.save(update_fields=update_fields)
        # --- FIN DE LA LÓGICA REFACTORIZADA ---

        # --- Crear la Cita (Sin Cambios) ---
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            selected_time = datetime.strptime(selected_time_str, '%H:%M').time()
            naive_start_time = datetime.combine(selected_date, selected_time)
            start_time = timezone.make_aware(naive_start_time)
            end_time = start_time + service.duration
        except ValueError:
            messages.error(request, "Error en el formato de fecha u hora guardado en la sesión.")
            return self.get(request, *args, **kwargs)

        appointment = Appointment.objects.create(
            business=business,
            staff_member=staff_member,
            customer=customer, # Este es el 'conector'
            service=service,
            start_time=start_time,
            end_time=end_time
        )
        
        # Limpiamos la sesión (Sin Cambios)
        request.session.pop('selected_service_id', None)
        request.session.pop('selected_staff_id', None)
        request.session.pop('selected_time', None)
        request.session.pop('selected_date', None)
        
        messages.success(request, f"¡Tu cita para {service.name} con {staff_member.name} ha sido agendada con éxito!")
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
        
        # --- CAMBIO: Ahora devolvemos los datos desde el User (la fuente de verdad) ---
        data = {
            'exists': True, 
            'first_name': user.first_name, 
            'last_name': user.last_name,
            'phone_number': user.phone_number # Devolvemos el teléfono global
        }
        # (Ya no necesitamos consultar el modelo Customer)
        return JsonResponse(data)

    except User.DoesNotExist:
        return JsonResponse({'exists': False})