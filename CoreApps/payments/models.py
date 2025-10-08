from django.db import models
from CoreApps.users.models import Customer, Client
from CoreApps.scheduling.models import Appointment

class Transaction(models.Model):
    """
    Registra una transacción financiera en el sistema.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDIENTE', 'Pendiente'
        SUCCESSFUL = 'EXITOSO', 'Exitoso'
        FAILED = 'FALLIDO', 'Fallido'

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True)
    # Esta cita es el "motivo" del pago. Podría expandirse para productos.
    appointment = models.ForeignKey(Appointment, on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=50, default='payphone') # Proveedor de pago
    provider_tx_id = models.CharField(max_length=255, blank=True, null=True) # ID de la transacción externa
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transacción {self.id} - {self.amount} - {self.status}"