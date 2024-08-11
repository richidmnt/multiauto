# middlewares.py
from .models import Usuario
from django.utils import timezone
from django.http import HttpResponseForbidden
from datetime import time

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
                    request.user = None
            except Usuario.DoesNotExist:
                request.user = None
        else:
            request.user = None

        response = self.get_response(request)
        return response
    


