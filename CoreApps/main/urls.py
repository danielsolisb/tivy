# CoreApps/main/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

# --- ESTA ES LA PARTE CLAVE QUE FALTABA O ESTABA INCOMPLETA ---
# Importamos todas las vistas que vamos a usar desde el archivo views.py de esta misma app.
from .views import login_view, dashboard_view, ClientPublicProfileView, SelectScheduleView

urlpatterns = [
    # URL para la vista de login (basada en función)
    path('login/', login_view, name='login'),

    # URL para la vista de logout (usando la vista de Django)
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # URL para el panel del profesional (basada en función)
    path('dashboard/', dashboard_view, name='dashboard'),

    # URL para el perfil público del profesional (usando la Vista Basada en Clases)
    path('p/<slug:slug>/', ClientPublicProfileView.as_view(), name='client_profile'),
    path('p/<slug:slug>/schedule/', SelectScheduleView.as_view(), name='select_schedule'),
]