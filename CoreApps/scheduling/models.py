# CoreApps/scheduling/models.py

from django.db import models
from CoreApps.users.models import StaffMember, Customer, Business
from CoreApps.catalog.models import Service

# -----------------------------------------------------------------------------
# Modelo de Disponibilidad
# CAMBIO: Ahora se relaciona con 'StaffMember' en lugar de 'Client'.
# -----------------------------------------------------------------------------
class AvailabilityBlock(models.Model):
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='availability_blocks')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"{self.staff_member.name} | {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"

# -----------------------------------------------------------------------------
# Modelo para la Cita
# CAMBIO: Ahora se relaciona con 'StaffMember' y 'Business'.
# -----------------------------------------------------------------------------
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Agendada'),
        ('COMPLETED', 'Completada'),
        ('CANCELED', 'Cancelada'),
    ]
    # Guardamos tanto el negocio como el miembro del personal para facilitar las consultas.
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='appointments')
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='appointments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='appointments')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SCHEDULED')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cita de {self.customer} con {self.staff_member.name} a las {self.start_time}"