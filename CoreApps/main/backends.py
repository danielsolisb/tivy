from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailAuthBackend(ModelBackend):
    """
    Autentica a un usuario usando el email en lugar del username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 'username' aquí es el email que pasa la vista de login
        UserModel = get_user_model()
        try:
            # Buscamos al usuario por su email
            user = UserModel.objects.get(email=username)
            if user.check_password(password):
                return user
        except UserModel.DoesNotExist:
            # Si no existe, devolvemos None (falla la autenticación)
            return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None