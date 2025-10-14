# CoreApps/main/utils.py

from datetime import datetime, timedelta
from django.utils import timezone
from CoreApps.scheduling.models import AvailabilityBlock, Appointment

def generate_available_slots(client, service, target_date):
    """
    Calcula los slots de tiempo disponibles con una lógica de avance híbrida.
    """
    available_slots = []
    
    availability_blocks = AvailabilityBlock.objects.filter(
        client=client,
        start_time__date=target_date
    ).order_by('start_time')

    if not availability_blocks:
        return []

    existing_appointments = Appointment.objects.filter(client=client, start_time__date=target_date)

    block_duration = service.duration
    # TODO: Añadir la lógica del travel_buffer aquí si el servicio es a domicilio

    # El "paso" para sondear cuando hay conflictos.
    probe_step = timedelta(minutes=15)

    for block in availability_blocks:
        current_time = timezone.make_aware(datetime.combine(target_date, block.start_time.time()))
        end_time = timezone.make_aware(datetime.combine(target_date, block.end_time.time()))
        
        while (current_time + block_duration) <= end_time:
            is_available = True
            for app in existing_appointments:
                if (app.start_time <= current_time < app.end_time) or \
                   (app.start_time < (current_time + block_duration) <= app.end_time):
                    is_available = False
                    break
            
            if is_available:
                # Si encontramos un slot, lo añadimos y saltamos por la duración del servicio.
                available_slots.append(current_time.strftime('%H:%M'))
                current_time += block_duration
            else:
                # Si hay conflicto, solo avanzamos un pequeño paso para seguir buscando.
                current_time += probe_step
            
    return available_slots