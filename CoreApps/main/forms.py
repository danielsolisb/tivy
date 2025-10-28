# CoreApps/main/forms.py

from django import forms
from CoreApps.users.models import User, Business, ServiceZone

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile_image']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class BusinessConfigForm(forms.ModelForm):
    """
    Formulario para editar la configuración del negocio.
    """
    service_zones_text = forms.CharField(
        label="Zonas de Servicio (Códigos Postales o Barrios)",
        required=False,
        help_text="Escribe una zona y presiona Enter o coma para añadirla.",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'id': 'id_service_zones_tags'})
    )

    class Meta:
        model = Business
        fields = [
            'display_name', 'photo', 'bio',
            'location_name', 'address', 'city', 'country', # <-- Añadidos city y country
            'service_delivery_type', 'travel_buffer',
            'primary_color', 'secondary_color',
        ]
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}), # <-- Nuevo widget
            'country': forms.TextInput(attrs={'class': 'form-control'}), # <-- Nuevo widget
            'service_delivery_type': forms.Select(attrs={'class': 'form-control'}),
            'travel_buffer': forms.TimeInput(attrs={'class': 'form-control', 'type':'text', 'placeholder':'HH:MM:SS'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }