# CoreApps/users/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta

# -----------------------------------------------------------------------------
# Modelo #1: El Usuario Base para Autenticación (SIN CAMBIOS)
# -----------------------------------------------------------------------------
class User(AbstractUser):
    email = models.EmailField(unique=True, help_text="El email será el nombre de usuario único.")
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

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
    slug = models.SlugField(unique=True, max_length=100, help_text="Identificador único para la URL del negocio.")
    photo = models.ImageField(upload_to='business/photos/', null=True, blank=True)
    bio = models.TextField(blank=True, help_text="Una breve descripción del negocio.")
    location_name = models.CharField(max_length=200, blank=True, help_text="Nombre del lugar físico (Ej: Centro Comercial El Sol).")
    address = models.CharField(max_length=255, blank=True)
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
    # --- NUEVOS CAMPOS DE COLOR ---
    primary_color = models.CharField(max_length=7, default='#3498DB', help_text="Color principal del tema (formato hex, ej: #FF0000)")
    secondary_color = models.CharField(max_length=7, default='#FFFFFF', help_text="Color secundario del tema (formato hex, ej: #00FF00)")
    # --- FIN NUEVOS CAMPOS ---
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name
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