from django.db import models
from CoreApps.users.models import Customer

class LoyaltyCard(models.Model):
    """
    Tarjeta de lealtad virtual para un Customer de un Client específico.
    """
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='loyalty_card')
    points = models.PositiveIntegerField(default=0)
    tier_level = models.CharField(max_length=50, default='Bronce')
    # Campo para el identificador de la API de Google Wallet u otra
    external_pass_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tarjeta de {self.customer} - {self.points} puntos"

class LoyaltyLog(models.Model):
    """
    Un registro de cada vez que se añaden o restan puntos, para auditoría.
    """
    card = models.ForeignKey(LoyaltyCard, on_delete=models.CASCADE, related_name='logs')
    points_change = models.IntegerField()
    reason = models.CharField(max_length=255, help_text="Ej: 'Cita completada', 'Bono de bienvenida'")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.points_change} puntos para {self.card.customer} por {self.reason}"