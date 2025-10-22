# CoreApps/main/utils.py

from datetime import datetime, timedelta
from django.utils import timezone
from CoreApps.scheduling.models import AvailabilityBlock, Appointment

def generate_available_slots(staff_member, service, target_date):
    """
    Calcula los slots de tiempo disponibles para un MIEMBRO DEL PERSONAL,
    un servicio y una fecha específicos.
    """
    available_slots = []
    
    # 1. Buscar los bloques de disponibilidad para el MIEMBRO DEL PERSONAL seleccionado
    availability_blocks = AvailabilityBlock.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date
    ).order_by('start_time')

    if not availability_blocks:
        return []

    # 2. Obtener las citas ya agendadas para ESE MIEMBRO DEL PERSONAL
    existing_appointments = Appointment.objects.filter(
        staff_member=staff_member, 
        start_time__date=target_date
    )

    block_duration = service.duration
    # TODO: La lógica del travel_buffer ahora se obtendrá del 'business' al que pertenece el staff_member.

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
                available_slots.append(current_time.strftime('%H:%M'))
                current_time += block_duration
            else:
                current_time += probe_step
            
    return available_slots