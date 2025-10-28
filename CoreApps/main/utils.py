# CoreApps/main/utils.py

from datetime import datetime, timedelta
from django.utils import timezone
from CoreApps.scheduling.models import AvailabilityBlock, Appointment
# Ya no necesitamos importar Service aquí directamente si lo pasamos como argumento

def generate_available_slots(staff_member, service, target_date, is_domicilio=False):
    """
    Calcula los slots de tiempo disponibles para un MIEMBRO DEL PERSONAL,
    un servicio, una fecha específica y si es a domicilio.
    """
    available_slots = []
    business = staff_member.business # Obtenemos el negocio al que pertenece el staff

    # 1. Buscar TODOS los bloques de disponibilidad para el staff member en el día seleccionado
    availability_blocks = AvailabilityBlock.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date
    ).order_by('start_time')

    if not availability_blocks:
        return [] # Si no hay bloques definidos para ese día, no hay horarios.

    # 2. Obtener todas las citas ya agendadas para ESE MIEMBRO DEL PERSONAL en ese día
    existing_appointments = Appointment.objects.filter(
        staff_member=staff_member,
        start_time__date=target_date
    )

    # 3. Calcular la duración TOTAL del bloqueo, aplicando el buffer si es a domicilio
    block_duration = service.duration
    if is_domicilio:
        # Sumamos el buffer configurado en el negocio
        # Asumiendo que renombraste el campo a domicilio_buffer_total o similar
        # Si sigue siendo travel_buffer, usá business.travel_buffer
        # ¡Importante! Asegurate que service.duration y business.travel_buffer sean timedelta
        try:
             # Usaremos el nombre 'travel_buffer' como estaba en los modelos que me pasaste
             block_duration = service.duration + business.travel_buffer
        except TypeError:
             # Manejo de error por si alguno no es timedelta (poco probable con DurationField)
             print(f"Error: No se pudo sumar duration ({type(service.duration)}) y travel_buffer ({type(business.travel_buffer)})")
             # Podrías decidir devolver [], o continuar sin el buffer
             pass


    # El "paso" pequeño para sondear cuando hay conflictos.
    probe_step = timedelta(minutes=15)

    # 4. Iterar sobre CADA bloque de disponibilidad del día
    for block in availability_blocks:
        # Aseguramos que las horas de inicio y fin sean "conscientes"
        # Usamos .time() para evitar problemas si el block tiene fecha diferente a target_date (aunque no debería)
        current_time = timezone.make_aware(datetime.combine(target_date, block.start_time.time()))
        end_time = timezone.make_aware(datetime.combine(target_date, block.end_time.time()))

        # Generar slots dentro de ESTE bloque de disponibilidad
        while (current_time + block_duration) <= end_time:
            is_available = True
            # Comprobar si el slot se solapa con una cita ya existente
            for app in existing_appointments:
                # Comparamos [slot_start, slot_end) con [app_start, app_end)
                slot_end_time = current_time + block_duration
                app_start_time = app.start_time
                app_end_time = app.end_time

                # Hay solapamiento si:
                # 1. El slot empieza durante la cita existente O
                # 2. La cita existente empieza durante el slot
                if (app_start_time <= current_time < app_end_time) or \
                   (current_time <= app_start_time < slot_end_time):
                    is_available = False
                    break # Hay colisión, no necesitamos seguir revisando

            if is_available:
                # Si encontramos un slot, lo añadimos y saltamos por la duración del servicio ORIGINAL
                # (El salto siempre es por la duración REAL del servicio, no por el bloqueo total)
                available_slots.append(current_time.strftime('%H:%M'))
                current_time += service.duration # Saltamos por la duración del servicio
                # Aseguramos un avance mínimo si la duración es 0 o muy pequeña
                if service.duration.total_seconds() < probe_step.total_seconds():
                     current_time += probe_step

            else:
                # Si hay conflicto, solo avanzamos un pequeño paso para seguir buscando.
                current_time += probe_step

    return available_slots