# CoreApps/users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta
from django.utils.text import slugify
from django.templatetags.static import static

# -----------------------------------------------------------------------------
# Modelo #1: El Usuario Base para Autenticación (SIN CAMBIOS)
# -----------------------------------------------------------------------------
class User(AbstractUser):
    email = models.EmailField(unique=True, help_text="El email será el nombre de usuario único.")
    profile_image = models.ImageField(
        upload_to='users/profile_pics/', 
        null=True, 
        blank=True, 
        help_text="Foto de perfil del usuario."
    )
    phone_number = models.CharField(max_length=20, blank=True, help_text="Número de teléfono del usuario.")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

# planes y suscripciones
class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Nombre del plan (Ej: Básico, Profesional)")
    price_monthly = models.DecimalField(max_digits=6, decimal_places=2, help_text="Precio mensual")
    max_staff = models.IntegerField(default=1, help_text="Número máximo de miembros de personal permitidos (-1 para ilimitado)")
    # --- Añade aquí más campos booleanos para características ---
    allow_payments = models.BooleanField(default=False, help_text="Permite aceptar pagos online")
    allow_whatsapp_reminders = models.BooleanField(default=False)
    allow_custom_branding = models.BooleanField(default=False)
    # ... etc ...
    is_active = models.BooleanField(default=True, help_text="Indica si este plan se puede asignar a nuevos clientes")

    def __str__(self):
        return self.name

#Zonas de servicios para los negocios que son a domicilio
class ServiceZone(models.Model):
    """
    Representa una zona geográfica (barrio, código postal, ciudad)
    donde un negocio puede ofrecer servicios a domicilio.
    """
    name = models.CharField(max_length=150, unique=True, help_text="Nombre único de la zona (Ej: Guayaquil Centro, 090101, Samborondón)")

    def __str__(self):
        return self.name

# -----------------------------------------------------------------------------
# --- NUEVO MODELO: El Negocio ---
# Este modelo reemplaza al antiguo 'Client' y representa la cuenta principal.
# -----------------------------------------------------------------------------
class Business(models.Model):
    class ServiceDeliveryType(models.TextChoices):
        LOCAL_ONLY = 'LOCAL', 'Solo atiende en su local'
        DELIVERY_ONLY = 'DOMICILIO', 'Solo atiende a domicilio'
        BOTH = 'AMBOS', 'Ofrece ambos servicios'

    class BusinessType(models.TextChoices):
        APPOINTMENTS = 'CITAS', 'Basado en Citas'
        RETAIL = 'TIENDA', 'Tienda Minorista'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_profile', help_text="El dueño o administrador del negocio.")
    display_name = models.CharField(max_length=150, help_text="Nombre del negocio (Ej: Peluquería Glamour).")
    slug = models.SlugField(unique=True, max_length=100, help_text="Identificador único para la URL (generado automáticamente).", blank=True)
    photo = models.ImageField(upload_to='business/photos/', null=True, blank=True)
    bio = models.TextField(blank=True, help_text="Una breve descripción del negocio.")
    location_name = models.CharField(max_length=200, blank=True, help_text="Nombre del lugar físico (Ej: Centro Comercial El Sol).")
    address = models.CharField(max_length=255, blank=True, help_text="Dirección detallada (Calle, número, etc.).")
    # --- NUEVOS CAMPOS DE UBICACIÓN ---
    city = models.CharField(max_length=100, blank=True, help_text="Ciudad donde opera el negocio.")
    country = models.CharField(max_length=100, blank=True, default='Ecuador', help_text="País donde opera el negocio.") # Default a Ecuador
    # --- FIN NUEVOS CAMPOS ---
    business_type = models.CharField(max_length=10, choices=BusinessType.choices, default=BusinessType.APPOINTMENTS)
    service_delivery_type = models.CharField(
        max_length=10,
        choices=ServiceDeliveryType.choices,
        default=ServiceDeliveryType.LOCAL_ONLY,
        help_text="Define el modelo de atención general del negocio."
    )
    travel_buffer = models.DurationField(
        default=timedelta(minutes=30),
        help_text="Tiempo extra que se bloqueará para traslados en servicios a domicilio."
    )
    primary_color = models.CharField(max_length=7, default='#3498DB', help_text="Color principal del tema (formato hex, ej: #FF0000)")
    secondary_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Color secundario del tema (formato hex, ej: #00FF00)")
    service_zones = models.ManyToManyField(
        ServiceZone,
        blank=True,
        related_name='businesses',
        help_text="Zonas geográficas cubiertas para servicios a domicilio (basado en nombres/códigos)."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.display_name) if self.display_name else 'negocio'
            slug = base_slug
            counter = 1
            while Business.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

# -----------------------------------------------------------------------------
# --- NUEVO MODELO: El Personal o Recurso Reservable ---
# Representa a cada persona (o silla, o cabina) que puede ser agendada.
# -----------------------------------------------------------------------------
class StaffMember(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='staff_members')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_profile', help_text="Cuenta de usuario para que el personal inicie sesión (opcional).")
    name = models.CharField(max_length=150, help_text="Nombre del miembro del personal (Ej: Ana Pérez).")
    photo = models.ImageField(upload_to='staff/photos/', null=True, blank=True)
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.business.display_name})"
    
    @property
    def get_photo_url(self):
        """
        Esta propiedad inteligente devuelve la URL de la foto correcta.
        - Si el staff es un Usuario, devuelve la foto de perfil del Usuario.
        - Si el staff es un Recurso (sin usuario), devuelve su propia foto.
        """
        default_avatar = static('images/default-profile.png') # Ruta de tu 'profile_form.html'

        # 1. Si el staff es un Usuario (está vinculado a un User)
        if self.user:
            # Si el usuario tiene una foto de perfil, úsala
            if self.user.profile_image:
                return self.user.profile_image.url
            # Si es usuario pero no tiene foto, usa el avatar por defecto
            else:
                return default_avatar

        # 2. Si es un Recurso (no-usuario) Y SÍ tiene foto
        elif not self.user and self.photo:
            return self.photo.url

        # 3. Si es un Recurso (no-usuario) y NO tiene foto
        else:
            # Opcionalmente, podrías cambiar esto a un ícono de "silla" o "recurso"
            # Por ahora, el avatar por defecto funciona bien.
            return default_avatar

# -----------------------------------------------------------------------------
# Modelo #3: El Consumidor Final (Cliente del Negocio)
# CAMBIO: Ahora se relaciona con 'Business' en lugar de 'Client'.
# -----------------------------------------------------------------------------
class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_profiles')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='customers')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    # --- NUEVOS CAMPOS DE DIRECCIÓN ---
    address_line = models.CharField(max_length=255, blank=True, null=True, help_text="Dirección del cliente para servicios a domicilio.")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True, help_text="Coordenada GPS (Latitud) para domicilio.")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True, help_text="Coordenada GPS (Longitud) para domicilio.")
    # --- FIN NUEVOS CAMPOS ---
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'business'), ('business', 'email')]

    def __str__(self):
        return f"{self.first_name} {self.last_name} (Cliente de: {self.business.display_name})"

# --- Subscription ---
class Subscription(models.Model):
    class SubscriptionStatus(models.TextChoices):
        TRIAL = 'TRIAL', 'En Prueba'
        ACTIVE = 'ACTIVE', 'Activo'
        PAST_DUE = 'PAST_DUE', 'Pago Vencido'
        INACTIVE = 'INACTIVE', 'Inactivo'
        CANCELED = 'CANCELED', 'Cancelado'
        DEMO = 'DEMO', 'Demostración'

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions') # PROTECT evita borrar un plan si hay suscripciones activas
    status = models.CharField(max_length=10, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIAL)
    trial_end_date = models.DateField(null=True, blank=True, help_text="Fecha en que termina el periodo de prueba")
    current_period_end = models.DateField(null=True, blank=True, help_text="Fecha en que termina el periodo pagado actual")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Suscripción de {self.business.display_name} ({self.plan.name}) - {self.get_status_display()}"


