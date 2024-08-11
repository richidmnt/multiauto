import logging
from django.http import HttpResponseForbidden
from .models import Usuario

logger = logging.getLogger(__name__)

class CustomUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Omitir el middleware si la ruta es para el admin de Django
        if request.path.startswith('/admin/'):
            return self.get_response(request)

        if 'id_usr' in request.session:
            try:
                user = Usuario.objects.get(id_usr=request.session['id_usr'])
                if user.is_active:
                    request.user = user
                else:
                    logger.warning(f"Usuario inactivo intentó acceder: {user.username}")
                    return HttpResponseForbidden("Tu cuenta está inactiva.")
            except Usuario.DoesNotExist:
                logger.error(f"Usuario con id_usr={request.session['id_usr']} no encontrado.")
                request.user = None
            except Exception as e:
                logger.error(f"Error inesperado: {e}")
                request.user = None
        else:
            request.user = None

        response = self.get_response(request)
        return response

    


