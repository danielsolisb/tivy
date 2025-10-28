# CoreApps/main/forms.py

from django import forms
from CoreApps.users.models import User, Business, ServiceZone # Importamos Business y ServiceZone
from tagify import fields # Necesitarás instalar pip install django-tagify

class UserProfileForm(forms.ModelForm):
    """
    Formulario para editar los datos básicos del perfil de usuario.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile_image'] 
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            # Opcional: Estilo para el input de archivo
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-control'}), 
        }

class BusinessConfigForm(forms.ModelForm):
    """
    Formulario para editar la configuración del negocio.
    """
    # Usamos TagifyField para gestionar las zonas como etiquetas
    service_zones_tags = fields.TagField(
        label="Zonas de Servicio (Códigos Postales o Barrios)",
        required=False, # No obligatorio
        help_text="Escribe una zona y presiona Enter o coma para añadirla.",
        widget=forms.TextInput(attrs={'class': 'form-control tagify-input'}) # Clase para JS
    )

    class Meta:
        model = Business
        # Lista de campos editables
        fields = [
            'display_name', 'photo', 'bio', 'location_name', 'address',
            'service_delivery_type', 'travel_buffer',
            'primary_color', 'secondary_color',
            # 'service_zones' # El campo M2M se manejará con el campo Tagify
        ]
        widgets = {
            # Aplicamos clases de Bootstrap
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'service_delivery_type': forms.Select(attrs={'class': 'form-control'}),
            'travel_buffer': forms.TimeInput(attrs={'class': 'form-control', 'type':'text', 'placeholder':'HH:MM:SS'}), # Puede necesitar JS para formato Duration
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}), # Input de color HTML5
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }