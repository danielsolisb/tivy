#CoreApps/catalog/models.py
from django.db import models
from CoreApps.users.models import Client # Importamos el modelo Client

# -----------------------------------------------------------------------------
# Modelo para negocios basados en citas
# -----------------------------------------------------------------------------
class Service(models.Model):
    class LocationType(models.TextChoices):
        LOCAL_ONLY = 'LOCAL', 'En el local'
        DELIVERY_ONLY = 'DOMICILIO', 'A domicilio'
        BOTH = 'AMBOS', 'Ambos (a elegir por el cliente)'
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    duration = models.DurationField(help_text="Duración del servicio. Formato: HH:MM:SS.")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    location_type = models.CharField(
        max_length=10,
        choices=LocationType.choices,
        default=LocationType.LOCAL_ONLY,
        help_text="Define dónde se puede realizar este servicio específico."
    )

    def __str__(self):
        return f"{self.name} - {self.client.display_name}"

# -----------------------------------------------------------------------------
# Modelo para negocios tipo tienda
# -----------------------------------------------------------------------------
class Product(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.client.display_name}"