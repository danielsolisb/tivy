# CoreApps/scheduling/models.py

from django.db import models
from CoreApps.users.models import StaffMember, Customer, Business
from CoreApps.catalog.models import Service

# -----------------------------------------------------------------------------
# Modelo de Disponibilidad
# CAMBIO: Ahora se relaciona con 'StaffMember' en lugar de 'Client'.
# -----------------------------------------------------------------------------
class AvailabilityBlock(models.Model):
    """
    Define un bloque de tiempo específico en el que un profesional ESTÁ disponible
    (su horario laboral base para ese día/periodo).
    """
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='availability_blocks')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    # --- NUEVO CAMPO DE PERMISO ---
    staff_can_edit = models.BooleanField(
        default=True,
        help_text="Permite que el miembro del staff (si tiene login) modifique o elimine este bloque."
    )
    # --- FIN NUEVO CAMPO ---

    def __str__(self):
        # Muestra la fecha y el rango de horas para fácil lectura en el admin
        return f"{self.staff_member.name} | {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"

    class Meta:
        # Evitar solapamientos accidentales de horarios para el mismo staff
        constraints = [
            models.CheckConstraint(check=models.Q(start_time__lt=models.F('end_time')), name='availability_start_before_end')
        ]
        ordering = ['start_time']
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


class TimeOffBlock(models.Model):
    """
    Define un bloque de tiempo específico en el que un StaffMember NO está disponible,
    incluso si cae dentro de su AvailabilityBlock (horario laboral).
    Ej: Almuerzo, Cita Médica, Emergencia.
    """
    staff_member = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name='time_off_blocks')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.CharField(max_length=150, blank=True, null=True, help_text="Motivo del bloqueo (opcional)")

    def __str__(self):
        return f"Bloqueo para {self.staff_member.name} | {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"

    class Meta:
        # Evitar solapamientos accidentales de bloqueos para el mismo staff
        constraints = [
            models.CheckConstraint(check=models.Q(start_time__lt=models.F('end_time')), name='timeoff_start_before_end')
        ]
        ordering = ['start_time']