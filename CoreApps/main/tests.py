# CoreApps/main/tests.py

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime
from unittest.mock import patch

# --- IMPORTS CORREGIDOS ---
# 1. Modelos de Usuarios y Negocio
from CoreApps.users.models import User, Business, StaffMember, Customer, Plan, Subscription
# 2. Modelos de Catálogo (AQUÍ ESTABA EL ERROR)
from CoreApps.catalog.models import Service
# 3. Modelos de Agendamiento
from CoreApps.scheduling.models import Appointment

class AppointmentViewTests(TestCase):
    def setUp(self):
        """
        CONFIGURACIÓN INICIAL (LABORATORIO)
        """
        # 1. Creamos un Usuario Dueño
        self.owner_user = User.objects.create_user(
            username='dueno@tivy.app', email='dueno@tivy.app', password='password123',
            first_name='Juan', last_name='Dueño'
        )
        
        # 2. Creamos el Negocio y Plan
        self.plan = Plan.objects.create(name="Pro", price_monthly=10.00)
        self.business = Business.objects.create(
            user=self.owner_user,
            display_name="Barbería Test",
            slug="barberia-test"
        )
        Subscription.objects.create(business=self.business, plan=self.plan, status='ACTIVE')

        # 3. Creamos Servicio y Staff
        self.staff = StaffMember.objects.create(
            business=self.business, name="Barbero 1"
        )
        
        self.service = Service.objects.create(
            business=self.business, 
            name="Corte Clásico", 
            duration=timedelta(minutes=30), 
            price=15.00
        )
        # Asignamos el servicio al staff (Relación ManyToMany)
        self.service.assignees.add(self.staff)

        # 4. Creamos un Usuario Cliente
        self.client_user = User.objects.create_user(
            username='cliente@gmail.com', email='cliente@gmail.com', password='password123',
            first_name='Pedro', last_name='Cliente', phone_number='0999999999'
        )
        self.customer = Customer.objects.create(
            user=self.client_user,
            business=self.business
        )

        # 5. Creamos una Cita
        start_time = timezone.now() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            business=self.business,
            staff_member=self.staff,
            customer=self.customer,
            service=self.service,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=30),
            status='SCHEDULED'
        )

        self.client = Client()

    def test_api_get_appointments_loads_correctly(self):
        """
        TEST CRÍTICO: Verifica que la API del calendario devuelve los datos 
        correctamente sin romper por referencias a Customer.
        """
        # 1. Iniciamos sesión como el dueño
        self.client.login(email='dueno@tivy.app', password='password123')

        # 2. Definimos rango
        start_str = timezone.now().date().isoformat()
        end_str = (timezone.now() + timedelta(days=2)).date().isoformat()
        
        # URL de tu vista (asegúrate que en urls.py se llame 'api_get_appointments')
        url = reverse('api_get_appointments') 
        
        # 3. Petición GET
        response = self.client.get(url, {'start': start_str, 'end': end_str})

        # 4. Verificaciones
        self.assertEqual(response.status_code, 200, "La API debería responder 200 OK")
        
        events = response.json()
        self.assertTrue(len(events) > 0, "Debería haber citas")
        
        first_event = events[0]
        
        # Verificamos que lea el nombre desde User correctamente
        expected_name_part = "Pedro Cliente"
        self.assertIn(expected_name_part, first_event['title'])
        
        # Verificamos teléfono
        self.assertEqual(first_event['extendedProps']['client_phone'], '0999999999')
        
        print("\n✅ Test A de API Calendario PASÓ correctamente.")
    
    def test_cannot_book_overlapping_appointment(self):
        """
        TEST B (ESCENARIO DE CONFLICTO):
        Verifica que NO se pueda agendar una cita si el horario ya está ocupado.
        """
        # 1. Preparación: Creamos una cita que ocupe el horario de 10:00 a 10:30
        # Usamos una fecha fija para el test (mañana a las 10am)
        target_date = timezone.now().date() + timedelta(days=1)
        start_time_occupied = timezone.make_aware(datetime.combine(target_date, datetime.strptime("10:00", "%H:%M").time()))
        end_time_occupied = start_time_occupied + self.service.duration # 30 min
        
        Appointment.objects.create(
            business=self.business,
            staff_member=self.staff,
            customer=self.customer, # Usamos el cliente existente
            service=self.service,
            start_time=start_time_occupied,
            end_time=end_time_occupied,
            status='SCHEDULED'
        )

        # 2. Configuración de la Sesión (Simulamos que el usuario eligió ESE MISMO horario)
        session = self.client.session
        session['booking_data'] = {
            'service_id': self.service.id,
            'staff_id': self.staff.id,
            'date_str': target_date.strftime('%Y-%m-%d'),
            'time_str': "10:00" # ¡Misma hora!
        }
        session.save()

        # 3. Ejecución: Intentamos confirmar la reserva
        url = reverse('confirm_booking', kwargs={'slug': self.business.slug})
        
        # Datos del formulario (el usuario llena sus datos)
        form_data = {
            'email': 'nuevo_cliente@test.com',
            'first_name': 'Intruso',
            'last_name': 'Test',
            'phone_number': '0991112222',
            'location_type': 'LOCAL'
        }
        
        response = self.client.post(url, form_data)

        # 4. Verificación (Asserts)
        
        # a) No debe haber redirección de éxito (usualmente código 302 a 'booking_confirmed')
        # Si falla, debería mostrar un mensaje de error en la misma página (código 200) o redirigir al perfil.
        # Aquí asumiremos que tu lógica redirige al perfil del negocio con un error si falla.
        
        # Verificamos que NO se creó una segunda cita
        count = Appointment.objects.filter(
            staff_member=self.staff,
            start_time=start_time_occupied
        ).count()
        
        self.assertEqual(count, 1, "¡ERROR CRÍTICO! Se permitió una doble reserva (Overbooking).")
        
        print("\n✅ Test de Conflicto B (Overbooking) PASÓ correctamente.")

    @patch('CoreApps.main.views.send_whatsapp_message')
    def test_booking_succeeds_even_if_whatsapp_crashes(self, mock_send_whatsapp):
        """
        TEST C: Tolerancia a Fallos.
        Si la función de enviar WhatsApp lanza una excepción CRÍTICA,
        la cita debe guardarse igual y NO debe salir Error 500.
        """
        # 1. Saboteamos la función de WhatsApp (Simulamos caída del servidor)
        mock_send_whatsapp.side_effect = Exception("¡CRASH! El servidor de API murió 🔥")

        # 2. Preparamos una reserva válida (Horario libre)
        target_date = timezone.now().date() + timedelta(days=3)
        session = self.client.session
        session['booking_data'] = {
            'service_id': self.service.id,
            'staff_id': self.staff.id,
            'date_str': target_date.strftime('%Y-%m-%d'),
            'time_str': "09:00" # 9 AM libre
        }
        session.save()

        url = reverse('confirm_booking', kwargs={'slug': self.business.slug})
        form_data = {
            'email': 'usuario_suerte@test.com',
            'first_name': 'Usuario',
            'last_name': 'Con Suerte',
            'phone_number': '0999888777',
            'location_type': 'LOCAL'
        }

        # 3. Ejecutamos el POST
        # Si tu vista no tuviera try/except, esto lanzaría el Exception aquí y fallaría el test.
        response = self.client.post(url, form_data)

        # 4. Verificaciones
        
        # a) NO debe ser 500. Debe ser 302 (Redirección exitosa)
        self.assertNotEqual(response.status_code, 500, "El sitio explotó (Error 500) por culpa de WhatsApp.")
        self.assertEqual(response.status_code, 302, "Debería redirigir a confirmación aunque falle el mensaje.")
        
        # b) La cita DEBE existir en la base de datos
        exists = Appointment.objects.filter(customer__user__email='usuario_suerte@test.com').exists()
        self.assertTrue(exists, "La cita no se guardó porque falló la notificación.")

        print("\n✅ Test C (Tolerancia a Fallos WA) PASÓ.")

# --- NUEVO TEST ESCENARIO D ---
    def test_anonymous_user_cannot_see_private_appointments(self):
        """
        TEST D (SEGURIDAD):
        Un usuario anónimo (no logueado) NO debe poder ver los datos del calendario.
        Debe ser redirigido al login (Código 302).
        """
        # 1. Aseguramos que no hay nadie logueado (Logout explícito)
        self.client.logout()

        # 2. Intentamos entrar a la API de citas
        url = reverse('api_get_appointments')
        
        # Intentamos obtener datos sin credenciales
        response = self.client.get(url)

        # 3. Verificaciones
        
        # a) NO debe ser 200 OK (Eso sería una brecha de seguridad grave: datos expuestos)
        self.assertNotEqual(response.status_code, 200, "¡PELIGRO! Datos privados visibles sin login.")

        # b) Debe ser 302 (Redirección al login) 
        # Esto confirma que @login_required está funcionando
        self.assertEqual(response.status_code, 302, "El usuario anónimo no fue redirigido al login.")

        print("\n✅ Test D (Seguridad/Acceso Denegado) PASÓ.")
    
    # --- NUEVO TEST ESCENARIO E ---
    @patch('CoreApps.main.views.Appointment.objects.create')
    def test_atomic_rollback_on_db_failure(self, mock_create_appt):
        """
        TEST E (INTEGRIDAD/ROLLBACK):
        Si la base de datos falla al crear la cita (último paso),
        el sistema debe deshacer TODO (el usuario nuevo NO debe existir).
        """
        # 1. Simulamos fallo Fatal de DB al intentar guardar la cita
        mock_create_appt.side_effect = Exception("Error DB Fatal simulado")
        
        # 2. Datos de un usuario TOTALMENTE NUEVO
        new_email = "rollback_user@tivy.app"
        
        # Preparamos la sesión
        session = self.client.session
        session['booking_data'] = {
            'service_id': self.service.id,
            'staff_id': self.staff.id,
            'date_str': timezone.now().date().strftime('%Y-%m-%d'),
            'time_str': "11:00"
        }
        session.save()
        
        url = reverse('confirm_booking', kwargs={'slug': self.business.slug})
        form_data = {
            'email': new_email,
            'first_name': 'Rollback',
            'last_name': 'User',
            'phone_number': '0999111000',
            'location_type': 'LOCAL'
        }
        
        # 3. Ejecutamos el POST (Aquí ocurrirá la explosión controlada)
        response = self.client.post(url, form_data)
        
        # 4. Verificaciones
        
        # a) El sistema no debió explotar (500), debió manejarlo (redirigir)
        self.assertNotEqual(response.status_code, 500, "El servidor explotó en lugar de hacer rollback.")
        
        # b) PRUEBA DE FUEGO: ¿Existe el usuario? 
        # Si el atomic() funcionó, el usuario debió ser borrado automáticamente.
        user_exists = User.objects.filter(email=new_email).exists()
        self.assertFalse(user_exists, "FALLO CRÍTICO: El rollback no funcionó. Se creó un usuario huérfano.")
        
        print("\n✅ Test E (Rollback Atómico) PASÓ.")