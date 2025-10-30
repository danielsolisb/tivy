# CoreApps/main/utils.py

from datetime import datetime, timedelta
from django.utils import timezone
# Importamos los 3 modelos relevantes de scheduling
from CoreApps.scheduling.models import AvailabilityBlock, Appointment, TimeOffBlock

def generate_available_slots(staff_member, service, target_date, is_domicilio=False):
    """
    Calcula los slots de tiempo disponibles considerando horario laboral (AvailabilityBlock),
    bloqueos (TimeOffBlock) y citas existentes (Appointment).
    """
    available_slots = []
    business = staff_member.business

    # 1. Obtener los bloques de horario laboral para el día
    working_blocks = AvailabilityBlock.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date # Filtra por la fecha exacta de inicio
    ).order_by('start_time')

    # Si no hay horario laboral definido para ese día, no hay slots.
    if not working_blocks:
        return []

    # 2. Obtener TODOS los eventos que bloquean tiempo en ese día
    time_off_blocks = TimeOffBlock.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date # Filtra bloqueos que inician ese día
        # Consideración: Bloqueos que abarcan varios días podrían necesitar un filtro más complejo
        # ej. filter(staff_member=staff_member, start_time__lte=datetime.combine(target_date, time.max), end_time__gte=datetime.combine(target_date, time.min))
    )
    existing_appointments = Appointment.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date # Filtra citas que inician ese día
    )

    # Combinamos todos los bloqueos (citas y tiempo libre) en una lista para facilitar la comprobación
    blockers = []
    for block in time_off_blocks:
        blockers.append((block.start_time, block.end_time))
    for app in existing_appointments:
        blockers.append((app.start_time, app.end_time))
    
    # Ordenamos los bloqueos por hora de inicio
    blockers.sort()

    # 3. Calcular la duración TOTAL del bloqueo necesario para el servicio (incluye buffer si aplica)
    service_actual_duration = service.duration
    block_duration_with_buffer = service_actual_duration # Duración base
    if is_domicilio:
        try:
            # Añadimos el buffer del negocio si es a domicilio
            block_duration_with_buffer += business.travel_buffer
        except TypeError:
             # Manejo básico de error si los tipos no son compatibles (DurationField debería prevenir esto)
             print(f"Advertencia: No se pudo sumar duration ({type(service_actual_duration)}) y travel_buffer ({type(business.travel_buffer)}) para {business}. Usando duración base.")
             pass # Continuar sin el buffer en caso de error

    # 4. Definir el paso mínimo para buscar (granularidad)
    probe_step = timedelta(minutes=15)
    # El avance después de encontrar un slot debe ser al menos el probe_step
    advance_step_after_found = max(service_actual_duration, probe_step)


    # 5. Iterar sobre cada bloque de horario laboral del día
    for work_block in working_blocks:
        # Asegurar que las horas sean "aware" y usen la fecha correcta
        # Usamos .time() por si el DateTimeField tuviera fecha incorrecta (aunque no debería si se filtra por __date)
        current_time = timezone.make_aware(datetime.combine(target_date, work_block.start_time.time()))
        work_end_time = timezone.make_aware(datetime.combine(target_date, work_block.end_time.time()))

        # Iterar dentro del bloque laboral buscando huecos
        while (current_time + block_duration_with_buffer) <= work_end_time:
            slot_start_time = current_time
            slot_end_time = current_time + block_duration_with_buffer
            
            # --- Comprobar colisión con CUALQUIER bloqueo (TimeOff o Appointment) ---
            has_conflict = False
            for block_start, block_end in blockers:
                # Hay solapamiento si el inicio del slot es antes que el fin del bloqueo Y
                # el fin del slot es después que el inicio del bloqueo.
                if slot_start_time < block_end and slot_end_time > block_start:
                    has_conflict = True
                    break # Conflicto encontrado, no seguir revisando bloqueos para este slot

            # --- Decisión: Añadir slot o seguir buscando ---
            if not has_conflict:
                # ¡Hueco encontrado! Añadir y avanzar por la duración del servicio (o el probe_step)
                available_slots.append(slot_start_time.strftime('%H:%M'))
                current_time += advance_step_after_found
            else:
                # Conflicto: Avanzar solo el pequeño paso para probar el siguiente posible inicio
                current_time += probe_step

    return available_slots