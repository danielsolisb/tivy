from django.db import models
from CoreApps.users.models import Client, Customer
from CoreApps.catalog.models import Service

# -----------------------------------------------------------------------------
# Modelo para definir el horario laboral del profesional
# -----------------------------------------------------------------------------
class AvailabilityBlock(models.Model):
    """
    Define un bloque de tiempo específico en el que un profesional está disponible.
    Un profesional puede tener múltiples bloques en un mismo día.
    """
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='availability_blocks')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        # Muestra la fecha y el rango de horas para fácil lectura en el admin
        return f"{self.client.display_name} | {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"


#class AvailabilityRule(models.Model):
#    DAYS_OF_WEEK = [
#        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
#        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
#    ]
#    
#    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='availability_rules')
#    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
#    start_time = models.TimeField()
#    end_time = models.TimeField()
#
#    class Meta:
#        unique_together = ('client', 'day_of_week') # Solo una regla por día para cada profesional.
#
#    def __str__(self):
#        return f"Horario de {self.client.display_name} para {self.get_day_of_week_display()}"

# -----------------------------------------------------------------------------
# Modelo para la cita en sí
# -----------------------------------------------------------------------------
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', 'Agendada'),
        ('COMPLETED', 'Completada'),
        ('CANCELED', 'Cancelada'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='appointments')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='appointments')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SCHEDULED')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cita de {self.customer} con {self.client} a las {self.start_time}"