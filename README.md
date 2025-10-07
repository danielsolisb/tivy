_____________________________________________________
Tivy
_____________________________________________________
Sistema de agendamiento de citas para toda industria, 
peluqueria, spa, hoteles, etc.
El sistema permite agendar citas, verificar disponibilidad, 
y generar reportes de citas.
_____________________________________________________
Sistema basado en Django, con una interfaz de usuario intuitiva, 
y una base de datos relacional para almacenar la información.
_____________________________________________________
"""e.register(Cita)
admin.site.register(Cliente)
admin.site.register(Servicio)
admin.site.register(Empleado)
admin.site.register(Horario)
admin.site.register(Estado)
admin.site.register(Tipo)
admin.site.register(Tipo_Cita)
admin.site.register(Tipo_Servicio)
admin.site.register(Tipo_Empleado)
admin.site.register(Tipo_Horario)
admin.site.register(Tipo_Estado)
admin.site.register(Tipo_Tipo)
admin.site.register(Tipo_Tipo_Cita)
admin.site.register(Tipo_Tipo_Servicio)
admin.site.register(Tipo_Tipo_Empleado)
admin.site.register(Tipo_Tipo_Horario)
admin.site.register(Tipo_Tipo_Estado)
admin.site.register(Tipo_Tipo_Tipo)
from django.contrib import admin
from.models import *
_____________________________________________________
