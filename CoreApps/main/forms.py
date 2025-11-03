# CoreApps/main/forms.py

from django import forms
from CoreApps.users.models import User, Business, ServiceZone, StaffMember
from CoreApps.catalog.models import Service

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        
        # --- CAMBIO AQUÍ ---
        # Añade 'phone_number' a la lista
        fields = ['first_name', 'last_name', 'phone_number', 'profile_image']
        
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            
            # --- CAMBIO AQUÍ ---
            # Añade el widget para el nuevo campo
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 0991234567'
            }),
            
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

class StaffMemberForm(forms.Form):
    """
    Formulario para añadir o editar un miembro de personal.
    Modificado para aceptar 'instance' de UpdateView sin ser ModelForm.
    """

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
    
    # --- Campos existentes (sin cambios) ---
    name = forms.CharField(
        label="Nombre del Recurso o Empleado",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Ana Gómez o Silla 1'})
    )
    give_access = forms.BooleanField(
        label="Dar acceso al dashboard a este empleado",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # --- INICIO DEL NUEVO CAMPO ---
    photo = forms.ImageField(
        label="Foto del Recurso (Opcional)",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    # --- FIN DEL NUEVO CAMPO ---
    
    email = forms.EmailField(
        label="Correo Electrónico del Empleado",
        required=False, 
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    first_name = forms.CharField(
        label="Nombre del Empleado",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        label="Apellido del Empleado",
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        label="Teléfono del Empleado",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09xxxxxxxx'})
    )
    
class ServiceForm(forms.ModelForm):
    """
    Formulario para crear y editar Servicios.
    """
    # Sobrescribimos el campo assignees para filtrar por el negocio actual
    assignees = forms.ModelMultipleChoiceField(
        queryset=StaffMember.objects.none(), # Queryset vacío inicialmente
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}), # O forms.CheckboxSelectMultiple
        required=False,
        label="Personal Asignado",
        help_text="Selecciona el personal que puede realizar este servicio."
    )
    
    class Meta:
        model = Service
        # Lista completa de campos a incluir en el formulario
        fields = [
            'name', 'description', 'duration', 'price', 
            'location_type', 'assignees', 'photo', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'duration': forms.TimeInput(attrs={'class': 'form-control', 'type':'text', 'placeholder': 'HH:MM:SS'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'location_type': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'duration': 'Formato HH:MM:SS (Ej: 01:30:00 para 1h 30m).',
        }

    def __init__(self, *args, **kwargs):
        # Obtenemos el 'business' pasado desde la vista
        business = kwargs.pop('business', None) 
        super().__init__(*args, **kwargs)

        if business:
            # 1. Filtrar queryset de 'assignees'
            self.fields['assignees'].queryset = StaffMember.objects.filter(business=business, is_active=True)
            
            # 2. Limitar opciones de 'location_type'
            delivery_type = business.service_delivery_type
            if delivery_type == Business.ServiceDeliveryType.LOCAL_ONLY:
                # Si el negocio solo atiende en local, quitamos las opciones de domicilio
                self.fields['location_type'].choices = [
                    (Service.LocationType.LOCAL_ONLY, Service.LocationType.LOCAL_ONLY.label)
                ]
                # Asegurarnos que el valor por defecto sea LOCAL
                self.fields['location_type'].initial = Service.LocationType.LOCAL_ONLY 
            elif delivery_type == Business.ServiceDeliveryType.DELIVERY_ONLY:
                 # Si el negocio solo atiende a domicilio, quitamos las opciones de local
                 self.fields['location_type'].choices = [
                     (Service.LocationType.DELIVERY_ONLY, Service.LocationType.DELIVERY_ONLY.label),
                     (Service.LocationType.BOTH, Service.LocationType.BOTH.label) # Puede ofrecer AMBOS aunque el negocio sea solo Domicilio? O quitamos BOTH? Mejor quitar BOTH.
                     #(Service.LocationType.BOTH, Service.LocationType.BOTH.label) 
                 ]
                 # Valor por defecto DOMICILIO
                 self.fields['location_type'].initial = Service.LocationType.DELIVERY_ONLY
            # Si es BOTH, dejamos todas las opciones por defecto