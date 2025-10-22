#CoreApps/users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta

# -----------------------------------------------------------------------------
# Modelo #1: El Usuario Base para Autenticación
# -----------------------------------------------------------------------------
class User(AbstractUser):
    """
    Modelo de usuario personalizado que maneja la autenticación.
    Cualquier persona que se loguea en el sistema es un 'User'.
    """
    email = models.EmailField(unique=True, help_text="El email será el nombre de usuario único.")
    
    # Usamos el email como el campo principal para el login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    def __str__(self):
        return self.email

# -----------------------------------------------------------------------------
# Modelo #2: El Cliente Principal de Tivy (El Profesional Independiente)
# -----------------------------------------------------------------------------
class Client(models.Model):
    """
    Representa al profesional independiente que contrata el servicio de Tivy.
    Este es el modelo central del sistema.
    """
    class ServiceDeliveryType(models.TextChoices):
        LOCAL_ONLY = 'LOCAL', 'Solo atiende en su local'
        DELIVERY_ONLY = 'DOMICILIO', 'Solo atiende a domicilio'
        BOTH = 'AMBOS', 'Ofrece ambos servicios'

    class BusinessType(models.TextChoices):
        APPOINTMENTS = 'CITAS', 'Basado en Citas'
        RETAIL = 'TIENDA', 'Tienda Minorista'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client_profile')
    display_name = models.CharField(max_length=150, help_text="Nombre a mostrar públicamente (Ej: Dr. Juan Pérez).")
    slug = models.SlugField(unique=True, max_length=100, help_text="Identificador único para la URL personal.")
    photo = models.ImageField(upload_to='clients/photos/', null=True, blank=True)
    bio = models.TextField(blank=True, help_text="Una breve descripción del profesional y sus servicios.")
    location_name = models.CharField(max_length=200, blank=True, help_text="Nombre del lugar físico (Ej: Clínica Dental Sonrisas).")
    address = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=10, choices=BusinessType.choices, default=BusinessType.APPOINTMENTS)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    service_delivery_type = models.CharField(
        max_length=10,
        choices=ServiceDeliveryType.choices,
        default=ServiceDeliveryType.LOCAL_ONLY,
        help_text="Define el modelo de atención general del profesional."
    )
    travel_buffer = models.DurationField(
        default=timedelta(minutes=30),
        help_text="Tiempo extra que se bloqueará ANTES y DESPUÉS de cada servicio a domicilio para traslados."
    )

    def __str__(self):
        return self.display_name

# -----------------------------------------------------------------------------
# Modelo #3: El Consumidor Final (Cliente del Profesional)
# -----------------------------------------------------------------------------
class Customer(models.Model):
    """
    Representa el vínculo entre un 'User' (consumidor) y un 'Client' (profesional).
    Un User puede ser Customer de múltiples Clients.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_profiles')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='customers')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'client') # Un usuario solo puede ser cliente de un profesional una vez.
        unique_together = ('client', 'email') # Un email solo puede registrarse una vez por profesional.

    def __str__(self):
        return f"{self.first_name} {self.last_name} (Cliente de: {self.client.display_name})"