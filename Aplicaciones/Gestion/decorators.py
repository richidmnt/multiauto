# decorators.py
from django.shortcuts import redirect, render
from .models import Usuario

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
        else:
            try:
                request.user = Usuario.objects.get(id_usr=request.session['id_usr'])
                if request.user.rol != Usuario.ADMINISTRADOR:
                    return render(request, 'permission_denied.html')  #
            except Usuario.DoesNotExist:
                return redirect('login')
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
        return view_func(request, *args, **kwargs)
    return wrapper

