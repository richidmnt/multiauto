# decorators.py
from django.shortcuts import redirect, render
from .models import Usuario
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)

def login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'id_usr' not in request.session:
            return redirect('login')
        else:
            try:
                request.user = Usuario.objects.get(id_usr=request.session['id_usr'])
            except Usuario.DoesNotExist:
                return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'id_usr' not in request.session:
            return redirect('login')
        
        try:
            usuario = Usuario.objects.get(id_usr=request.session['id_usr'])
            
            if usuario.rol != Usuario.ADMINISTRADOR:
                logger.warning(f"Acceso denegado para el usuario {usuario.username} con rol {usuario.rol}")
                return render(request, 'permission_denied.html')
            
            request.user = usuario
        
        except ObjectDoesNotExist:
            logger.error("Usuario no encontrado en la base de datos")
            return redirect('login')
        
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return render(request, 'error.html')  # Renderiza una página de error genérica.
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def mecanico_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'id_usr' not in request.session:
            return redirect('login')
        else:
            try:
                request.user = Usuario.objects.get(id_usr=request.session['id_usr'])
                if request.user.rol != Usuario.MECANICO:
                    return render(request, 'permission_denied.html') 
            except Usuario.DoesNotExist:
                return redirect('login')
            except Exception as e:
                
                logger.error(f"Error en mecanico_required: {e}")
                return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper
