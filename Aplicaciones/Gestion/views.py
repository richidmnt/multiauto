from gettext import translation
import json
from django.db.models.functions import Concat
from django.db import transaction, IntegrityError
from django.forms import ValidationError
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count,Value
from django.db.models.functions import ExtractMonth
from django.core.mail import send_mail,BadHeaderError
from django.urls import reverse
from django.http import JsonResponse
from django.conf import settings
from django.http import HttpResponseServerError

from .decorators import login_required,admin_required,mecanico_required
from .models import *
import logging

logger = logging.getLogger(__name__)

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        try:
            user = Usuario.objects.get(username=username)
            if user.check_password(password):
                if user.is_active:
                    request.session['id_usr'] = user.id_usr
                    messages.success(request, 'Inicio de sesión exitoso')
                    if user.rol == Usuario.ADMINISTRADOR:
                        return redirect('home')
                    elif user.rol == Usuario.MECANICO:
                        return redirect('home2')
                else:
                    messages.error(request, 'Cuenta inactiva. Contacta al administrador.')
            else:
                messages.error(request, 'Contraseña incorrecta')
        except Usuario.DoesNotExist:
            messages.error(request, 'Usuario no encontrado')
    return render(request, 'login.html')

def logout(request):
    if 'id_usr' in request.session:
        del request.session['id_usr']
    return redirect('login')

@admin_required
def home(request):
  
    total_clientes = Cliente.objects.filter(is_deleted=False).count()

   
    ordenes_por_estado = Orden.objects.filter(is_deleted=False).values('estado_ord').annotate(total=Count('estado_ord'))

   
    ordenes_por_mes = Orden.objects.filter(is_deleted=False).annotate(month=ExtractMonth('fecha_ord')).values('month').annotate(total=Count('id_ord')).order_by('month')

    
    ordenes_pendientes_count = Orden.objects.filter(estado_ord='PENDIENTE', ).count()
    ordenes_completadas_count = Orden.objects.filter(estado_ord='COMPLETADA', ).count()
    ordenes_finalizadas_count = Orden.objects.filter(estado_ord='FINALIZADA',).count()
    top_servicios_usados = OrdenServicio.objects.filter(
        servicio_id__is_deleted=False
    ).values('servicio_id__nombre_ser').annotate(total=Count('servicio_id')).order_by('-total')[:5]

    
    bottom_servicios_usados = OrdenServicio.objects.filter(
        servicio_id__is_deleted=False
    ).values('servicio_id__nombre_ser').annotate(total=Count('servicio_id')).order_by('total')[:5]
    ordenes_por_mecanico = Orden.objects.filter(is_deleted=False,usuario_id__is_active=True).exclude(estado_ord__in=['COMPLETADA', 'FINALIZADA']).annotate(
        mecanico=Concat('usuario_id__nombre', Value(' '), 'usuario_id__apellido')
    ).values('mecanico').annotate(total=Count('id_ord'))

    context = {
        'total_clientes': total_clientes,
        'ordenes_por_estado': ordenes_por_estado,
        'ordenes_por_mes': list(ordenes_por_mes),
        'ordenes_pendientes_count': ordenes_pendientes_count,
        'ordenes_completadas_count': ordenes_completadas_count,
        'ordenes_finalizadas_count': ordenes_finalizadas_count,
        'top_servicios_usados': list(top_servicios_usados),
        'bottom_servicios_usados': list(bottom_servicios_usados),
        'ordenes_por_mecanico': list(ordenes_por_mecanico),

    }

    return render(request, 'index.html', context)


@mecanico_required
def home2(request):
    try:
        usuario_actual = request.user

        ordenes_pendientes_count = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='PENDIENTE').count()
        ordenes_progreso_count = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='EN_PROGRESO').count()
        ordenes_buscando_repuestos_count = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='ESPERANDO_REPUESTOS').count()
        ordenes_completadas_count = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='COMPLETADA').count()
        ordenes_finalizadas_count = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='FINALIZADA').count()
        ordenes_por_estado = Orden.objects.filter(usuario_id=usuario_actual).values('estado_ord').annotate(total=Count('estado_ord'))
        ordenes_por_mes = Orden.objects.filter(usuario_id=usuario_actual, estado_ord='FINALIZADA', fecha_fin_ord__isnull=False).annotate(
            month=ExtractMonth('fecha_fin_ord')
        ).values('month').annotate(total=Count('id_ord')).order_by('month')

        context = {
            'ordenes_pendientes_count': ordenes_pendientes_count,
            'ordenes_progreso_count': ordenes_progreso_count,
            'ordenes_buscando_repuestos_count': ordenes_buscando_repuestos_count,
            'ordenes_completadas_count': ordenes_completadas_count,
            'ordenes_finalizadas_count': ordenes_finalizadas_count,
            'ordenes_por_estado': list(ordenes_por_estado),
            'ordenes_completadas_por_mes': list(ordenes_por_mes),
        }
        return render(request, 'prueba.html', context)
    except Exception as e:
        logger.error(f"Error en home2: {e}")
        return HttpResponseServerError("Se ha producido un error en el servidor.")

@admin_required
def index1(request):
    usuarios = Usuario.objects.filter(is_deleted=False)
    return render(request, 'listaUsuarios.html', {'usuarios': usuarios})

@admin_required
def listaUsuariosEliminados(request):
    usuarios = Usuario.objects.filter(is_deleted=True)
    return render(request, 'lista_usuarios_eliminados.html', {'usuarios': usuarios})

@admin_required
def restaurarUsuario(request,id):
    usuario = get_object_or_404(Usuario, id_usr=id)
    usuario.is_active=True
    usuario.is_deleted=False
    usuario.deleted_at=None
    usuario.save()
    messages.success(request,f'Usuario {usuario.username} restaurado correctamente.')
    return redirect('usuariosEliminados')

@admin_required
def guardarUsuario(request):
    return render(request, 'guardarUsuario.html')

@admin_required
def registrarUsuario(request):
    if request.method == 'POST':
        username = request.POST.get('username').strip()
        nombre = request.POST.get('nombre').upper()
        apellido = request.POST.get('apellido').upper()
        telefono = request.POST.get('telefono')
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()
        rol = request.POST.get('rol')
        is_active = 'is_active' in request.POST

        try:
            
            if Usuario.objects.filter(username=username).exists():
                messages.error(request, 'El nombre de usuario ya existe. Por favor, elige otro.')
                return redirect('guardarUsuario')

            if Usuario.objects.filter(email=email).exists():
                messages.error(request, 'El email ya existe. Por favor, ingresa otro.')
                return redirect('guardarUsuario')

            usuario = Usuario.objects.create(
                username=username,
                nombre=nombre,
                apellido=apellido,
                telefono=telefono,
                email=email,
                rol=rol,
                is_active=is_active
            )
            usuario.set_password(password)
            usuario.save()
            
            messages.success(request, 'Usuario guardado correctamente')
            return redirect('index1')

        except IntegrityError as e:
            if 'username' in str(e):
                messages.error(request, 'El nombre de usuario ya existe. Por favor, elige otro.')
            elif 'email' in str(e):
                messages.error(request, 'El email ya existe. Por favor, ingresa otro.')
            else:
                messages.error(request, 'Ocurrió un error al guardar el usuario. Por favor, inténtalo de nuevo.')
            return redirect('guardarUsuario')
    else:
        return render(request, 'guardarUsuario.html')

@admin_required
def actualizarUsuario(request, id_usr):
    usuario = get_object_or_404(Usuario, id_usr=id_usr)

    if request.method == 'POST':
        username = request.POST.get('username').strip()
        nombre = request.POST.get('nombre').upper()
        apellido = request.POST.get('apellido').upper()
        telefono = request.POST.get('telefono')
        email = request.POST.get('email').strip()
        password = request.POST.get('password').strip()
        rol = request.POST.get('rol')
        is_active = 'is_active' in request.POST

        try:
            # Verificar si el nombre de usuario ya existe y no es el del usuario actual
            if Usuario.objects.filter(username=username).exclude(id_usr=id_usr).exists():
                messages.error(request, 'El nombre de usuario ya existe. Por favor, elige otro.')
                return redirect('actualizarUsuario', id_usr=id_usr)

            # Verificar si el email ya existe y no es el del usuario actual
            if Usuario.objects.filter(email=email).exclude(id_usr=id_usr).exists():
                messages.error(request, 'El email ya existe. Por favor, ingresa otro.')
                return redirect('actualizarUsuario', id_usr=id_usr)

            # Actualizar los campos del usuario
            usuario.username = username
            usuario.nombre = nombre
            usuario.apellido = apellido
            usuario.telefono = telefono
            usuario.email = email
            usuario.rol = rol
            usuario.is_active = is_active

            if password:
                usuario.set_password(password)

            usuario.save()

            messages.success(request, 'Usuario actualizado correctamente')
            return redirect('index1')

        except IntegrityError as e:
            if 'username' in str(e):
                messages.error(request, 'El nombre de usuario ya existe. Por favor, elige otro.')
            elif 'email' in str(e):
                messages.error(request, 'El email ya existe. Por favor, ingresa otro.')
            else:
                messages.error(request, 'Ocurrió un error al actualizar el usuario. Por favor, inténtalo de nuevo.')
            return redirect('actualizarUsuario', id_usr=id_usr)
    else:
        return render(request, 'obtener_usuario.html', {'usuario': usuario})



@admin_required
def eliminarUsuario(request, id,permanent= False):
    try:
        
        usuario = Usuario.objects.get(id_usr=id)
        if permanent:
            messages.success(request, 'Usuario eliminado permanentemente.')
        else:
            usuario.is_deleted = True
            usuario.is_active = False 
            usuario.deleted_at = timezone.now()
            usuario.save()
            messages.success(request, 'Usuario eliminado correctamente.')
    except Usuario.DoesNotExist:
        messages.error(request, 'El usuario no existe')
    except ProtectedError as e:
        messages.error(request, 'No se puede eliminar el usuario porque está asociado con una o más órdenes.')
    except IntegrityError as e:
        messages.error(request, 'No se puede eliminar el usuario debido a una restricción de integridad.')
    except Exception as e:
        messages.error(request, f'Ocurrió un error al eliminar el usuario: {str(e)}')
    
    return redirect('index1')


# Gestion de Clientes
@admin_required
def listaClientes(request):
    clientes = Cliente.objects.filter(is_deleted =False)
    return render(request,'listaClientes.html',{'clientes':clientes})
@admin_required
def clientesEliminados(request):
    clientes = Cliente.objects.filter(is_deleted=True)
    return render(request,'lista_clientes_eliminados.html',{'clientes':clientes})

@admin_required
def guardarCliente(request):
    return render(request,'guardarCliente.html')

@admin_required
def registrarCliente(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                ciudad = request.POST['ciudad_dir'].strip().upper()
                barrio = request.POST['barrio_dir'].strip().upper()
                calle = request.POST['calle_dir'].strip().upper()
               

                # Crear la instancia de la dirección pero no guardarla aún
                direccion = Direccion(ciudad_dir=ciudad, barrio_dir=barrio, calle_dir=calle)

                nombre = request.POST['nombre_cli'].strip().upper()
                apellido = request.POST['apellido_cli'].strip().upper()
                ci = request.POST['ci_cli'].strip()
                telefono = request.POST['telefono_cli'].strip()
                email = request.POST['email_cli'].strip()

                # Verificar si el CI del cliente ya existe
                if Cliente.objects.filter(ci_cli=ci).exists():
                    messages.error(request, 'El cliente con este CI ya existe.')
                    raise IntegrityError('CI del cliente duplicado')

                # Verificar si el email del cliente ya existe
                if Cliente.objects.filter(email_cli=email).exists():
                    messages.error(request, 'El cliente con este email ya existe.')
                    raise IntegrityError('Email del cliente duplicado')

                # Guardar la dirección y luego el cliente
                direccion.save()
                cliente = Cliente(nombre_cli=nombre, apellido_cli=apellido, ci_cli=ci, telefono_cli=telefono, email_cli=email, dir_id=direccion)
                cliente.save()

            messages.success(request, 'Cliente registrado correctamente.')
            return redirect('listaClientes') 

        except IntegrityError as e:
            error_message = str(e)
            if 'ci_cli' in error_message:
                messages.error(request, 'El CI del cliente ya existe. Por favor, ingresa otro.')
            elif 'email_cli' in error_message:
                messages.error(request, 'El email del cliente ya existe. Por favor, ingresa otro.')
            else:
                messages.error(request, f'Error de integridad: {error_message}')
        except Exception as e:
            messages.error(request, f'Error al registrar el cliente: {e}')

        return redirect('guardarCliente')


@admin_required
def eliminarCliente(request, id):
    try:
        cliente = get_object_or_404(Cliente, id_cli=id)
        cliente.delete()
        messages.success(request, 'El cliente ha sido eliminado correctamente')
    
    except Cliente.DoesNotExist:
        messages.error(request, 'El cliente no existe')
    except ProtectedError as e:
        messages.error(request, f'No se puede eliminar el cliente porque está relacionado con uno  más vehiculos')
    except Exception as e:
        messages.error(request, f'Ocurrió un error al intentar eliminar el cliente: {e}')
    
    return redirect('listaClientes')

@admin_required
def restaurarCliente(request,id):
    cliente = get_object_or_404(Cliente, id_cli=id)
    cliente.is_deleted = False
    cliente.deleted_at = None
    cliente.save()
    messages.success(request, f'Cliente {cliente.nombre_cli} {cliente.apellido_cli} restaurado correctamente.')
    return redirect("clientesEliminados")

@admin_required
def actualizarCliente(request,id_cli):
    cliente = get_object_or_404(Cliente,id_cli=id_cli)
    if request.method == 'POST':
        id_cli = request.POST["id_cli"]
        cliente = Cliente.objects.get(id_cli=id_cli)

        
        nuevo_ci = request.POST['ci_cli'].strip()
        nuevo_email = request.POST['email_cli'].strip()
        
       
        if Cliente.objects.filter(ci_cli=nuevo_ci).exclude(id_cli=id_cli).exists():
            messages.error(request, 'La cédula ya existe. Por favor, ingrese otra.')
            return redirect('editarCliente', id_cli=id_cli)

        if Cliente.objects.filter(email_cli=nuevo_email).exclude(id_cli=id_cli).exists():
            messages.error(request, 'El correo electrónico ya existe. Por favor, ingrese otro.')
            return redirect('editarCliente', id_cli=id_cli)

       
        cliente.dir_id.ciudad_dir = request.POST['ciudad_dir'].strip().upper()
        cliente.dir_id.barrio_dir = request.POST['barrio_dir'].strip().upper()
        cliente.dir_id.calle_dir = request.POST['calle_dir'].strip().upper()
        cliente.dir_id.save()

       
        cliente.nombre_cli = request.POST['nombre_cli'].strip().upper()
        cliente.apellido_cli = request.POST['apellido_cli'].strip().upper()
        cliente.ci_cli = nuevo_ci
        cliente.telefono_cli = request.POST['telefono_cli'].strip()
        cliente.email_cli = nuevo_email
        cliente.save()
        
        messages.success(request, 'Cliente actualizado correctamente')
        return redirect('listaClientes')
    else:
        return render(request,'obtenerCliente.html',{'cliente':cliente})

    
# Gestion de servicios
@admin_required
def listaServicios(request):
    servicios = Servicio.objects.filter(is_deleted=False)
    return render(request,'listaServicios.html',{'servicios':servicios})

@admin_required
def serviciosEliminados(request):
    servicios = Servicio.objects.filter(is_deleted=True)
    return render(request,'lista_servicios_eliminados.html',{'servicios':servicios})


@admin_required
def guardarServicio(request):
    return render(request,'guardarServicio.html')

@admin_required
def registrarServicio(request):
    if request.method == 'POST':
        nombre = request.POST['nombre_ser'].strip().upper()
        descripcion = request.POST['descripcion_ser'].upper()
        precio = request.POST.get('precio_ser').replace(',', '.')

        try:
            if Servicio.objects.filter(nombre_ser=nombre).exists():
                messages.error(request, 'El nombre del servicio ya existe. Por favor, elige otro nombre.')
                return redirect('guardarServicio')

            servicio = Servicio(
                nombre_ser=nombre,
                descripcion_ser=descripcion,
                precio_ser=precio
            )
            servicio.save()
            messages.success(request, 'Servicio creado correctamente')
            return redirect('listaServicios')
        except IntegrityError:
            messages.error(request, 'El nombre del servicio ya existe. Por favor, elige otro nombre.')
            return redirect('guardarServicio')
    else:
        return render(request, 'guardarServicio.html')
@admin_required
def eliminarServicio(request, id):
    servicio = get_object_or_404(Servicio, id_ser=id)
    try:
        servicio.is_deleted=True
        servicio.deleted_at= timezone.now()
        servicio.save()
        messages.success(request, f'Servicio  {servicio.nombre_ser}  eliminado correctamente')
    except ProtectedError:
        messages.error(request, 'No se puede eliminar el servicio porque está referenciado en órdenes existentes.')
    return redirect('listaServicios')

@admin_required
def restaurarServicio(request,id):
    servicio = get_object_or_404(Servicio,id_ser=id)
    servicio.is_deleted = False
    servicio.deleted_at = None
    servicio.save()
    messages.success(request, f'Servicio  {servicio.nombre_ser}  restaurado correctamente')
    return redirect('serviciosEliminados')



@admin_required
def obtenerServicio(request,id):
    servicio = Servicio.objects.get(id_ser = id)
    return render(request,'obtenerServicio.html',{'servicio':servicio})
@admin_required
def actualizarServicio(request):
    if request.method == 'POST':
        try:
            servicio_id = request.POST['id_ser']
            servicio = Servicio.objects.get(id_ser=servicio_id)
            servicio.nombre_ser = request.POST['nombre_ser'].strip().upper()
            servicio.descripcion_ser = request.POST['descripcion_ser'].upper()
            servicio.precio_ser = request.POST['precio_ser'].replace(',','.')
            servicio.save()
            messages.success(request, 'Servicio actualizado correctamente')
        except IntegrityError:
            messages.error(request, 'El nombre del servicio ya existe. Por favor, elige otro nombre.')
        except Servicio.DoesNotExist:
            messages.error(request, 'El servicio no existe.')
        except ValueError:
            messages.error(request, 'El precio debe ser un número decimal válido.')
        except Exception as e:
            messages.error(request, f'Error inesperado: {str(e)}')
        
        return redirect('listaServicios')
    else:
        return render(request, 'obtenerServicio') 

@admin_required
def listaVehiculos(request):
    vehiculos =Vehiculo.objects.all()
    
    return render(request,'listaVehiculos.html',{'vehiculos':vehiculos})
@admin_required
def guardarVehiculo(request):
    clientes = Cliente.objects.all()
    return render(request,'guardarVehiculo.html',{'clientes':clientes})
@admin_required
def registrarVehiculo(request):
    if request.method == 'POST':
        try:
            marca = request.POST['marca_veh'].strip().upper()
            modelo = request.POST['modelo_veh'].strip().upper()
            placa = request.POST['placa_veh'].strip().upper()
            anio = request.POST['anio_veh']
            color = request.POST['color_veh'].strip().upper()
            cliente_id = request.POST['id_cli']
            cliente = Cliente.objects.get(id_cli=cliente_id)

            vehiculo = Vehiculo(
                marca_veh=marca,
                modelo_veh=modelo,
                placa_veh=placa,
                anio_veh=anio,
                color_veh=color,
                cli_id=cliente
            )

            vehiculo.save()
            messages.success(request, 'Vehículo creado correctamente')
            return redirect('listaVehiculos')  
        except Cliente.DoesNotExist:
            messages.error(request, 'El cliente no existe. Por favor, seleccione un cliente válido.')
        except IntegrityError:
            messages.error(request, 'La placa  ya están registrados. Por favor, ingrese datos únicos.')
        except Exception as e:
            messages.error(request, f'Error inesperado: {e}')
        return redirect('guardarVehiculo')

        
@admin_required
def eliminarVehiculo(request, id):
    vehiculo = get_object_or_404(Vehiculo, id_veh=id)
    try:
        vehiculo.delete()
        messages.success(request, 'Vehículo eliminado correctamente')
    except ProtectedError as e:
        messages.error(request, f'No se puede eliminar el vehículo porque está asociado a una o más órdenes')
    return redirect('listaVehiculos')
@admin_required
def obtenerVehiculo(request,id):
    vehiculo = Vehiculo.objects.get(id_veh=id)
    clientes = Cliente.objects.all()
    return render(request,'obtenerVehiculo.html',{'vehiculo':vehiculo,'clientes':clientes})
@admin_required
def actualizarVehiculo(request,id_veh):
    vehiculo = get_object_or_404(Vehiculo,id_veh=id_veh)
    clientes = Cliente.objects.all()
    if request.method == 'POST':
        id_veh = request.POST['id_veh']
        vehiculo = Vehiculo.objects.get(id_veh=id_veh)
        nueva_placa = request.POST['placa_veh'].strip().upper()
        

        
        if Vehiculo.objects.filter(placa_veh=nueva_placa).exclude(id_veh=id_veh).exists():
            messages.error(request, 'La placa ya existe. Por favor, ingrese otra.')
            return redirect('editarVehiculo', id_veh=id_veh)

        

        vehiculo.marca_veh = request.POST['marca_veh'].strip().upper()
        vehiculo.modelo_veh = request.POST['modelo_veh'].strip().upper()
        vehiculo.placa_veh = nueva_placa
        vehiculo.anio_veh = request.POST['anio_veh'].strip()
        
        vehiculo.color_veh = request.POST['color_veh'].strip().upper()
        cliente_id = request.POST['cli_id'].strip()
        vehiculo.cli_id = Cliente.objects.get(id_cli=cliente_id)
        vehiculo.save()

        messages.success(request, 'Vehículo actualizado correctamente')
        return redirect('listaVehiculos')
    else:
        return render(request,'obtenerVehiculo.html',{'vehiculo':vehiculo,'clientes':clientes})

    
#Registrar Orden Cliente
@admin_required
def guardarOrden(request):
    max_numero_ord = Orden.objects.aggregate(models.Max('numero_ord'))['numero_ord__max']
    next_numero_ord = 1 if max_numero_ord is None else max_numero_ord + 1
    context = {
            'next_numero_ord': next_numero_ord,
            'usuarios': Usuario.objects.filter(is_active = True, rol = "MECANICO"),
            'servicios': Servicio.objects.filter(is_deleted = False),
            'ESTADOS': Orden.ESTADOS,
        }
    return render(request,'generarorden.html',context)

@admin_required
def registrarOrden(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                
                direccion = Direccion.objects.create(
                    ciudad_dir=request.POST['ciudad_dir'].strip().upper(),
                    barrio_dir=request.POST['barrio_dir'].strip().upper(),
                    calle_dir=request.POST['calle_dir'].strip().upper(),
                    
                )

                
                if Cliente.objects.filter(ci_cli=request.POST['ci_cli']).exists():
                    raise IntegrityError('ci_cli')

                
                if Cliente.objects.filter(email_cli=request.POST['email_cli']).exists():
                    raise IntegrityError('email_cli')

        
                cliente = Cliente.objects.create(
                    nombre_cli=request.POST['nombre_cli'].strip().upper(),
                    apellido_cli=request.POST['apellido_cli'].strip().upper(),
                    ci_cli=request.POST['ci_cli'].strip(),
                    telefono_cli=request.POST['telefono_cli'].strip(),
                    email_cli=request.POST['email_cli'],
                    dir_id=direccion
                )

                
                if Vehiculo.objects.filter(placa_veh=request.POST['placa_veh']).exists():
                    raise IntegrityError('placa_veh')

                
                vehiculo = Vehiculo.objects.create(
                    marca_veh=request.POST['marca_veh'].strip().upper(),
                    modelo_veh=request.POST['modelo_veh'].strip().upper(),
                    placa_veh=request.POST['placa_veh'].strip().upper(),
                    anio_veh=request.POST['anio_veh'],
                    color_veh=request.POST['color_veh'].strip().upper(),
                    cli_id=cliente
                )

                # Generar el próximo número de orden
                ultimo_numero_ord = Orden.objects.all().order_by('numero_ord').last()
                next_numero_ord = ultimo_numero_ord.numero_ord + 1 if ultimo_numero_ord else 1

                # Crear la orden
                orden = Orden.objects.create(
                    fecha_ord=timezone.now(),
                    numero_ord=next_numero_ord,
                    observaciones_ord=request.POST['observaciones_ord'],
                    estado_ord=request.POST['estado_ord'],
                    usuario_id=Usuario.objects.get(id_usr=request.POST['usuario_id']),
                    vehiculo_id=vehiculo,
                )

                # Crear servicios de la orden
                servicios_ids = request.POST.getlist('servicio_id[]')
                subtotales = request.POST.getlist('subtotal[]')

                for servicio_id, subtotal in zip(servicios_ids, subtotales):
                    if servicio_id and subtotal:
                        subtotal = subtotal.replace(',', '.')
                        OrdenServicio.objects.create(
                            orden_id=orden,
                            servicio_id=Servicio.objects.get(id_ser=servicio_id),
                            subtotal=subtotal
                        )

            messages.success(request, 'Orden creada correctamente')
            return redirect('listarOrdenes')

        except IntegrityError as e:
            if str(e) == 'ci_cli':
                messages.error(request, 'El CI del cliente ya existe. Por favor, ingresa otro.')
            elif str(e) == 'email_cli':
                messages.error(request, 'El email del cliente ya existe. Por favor, ingresa otro.')
            elif str(e) == 'placa_veh':
                messages.error(request, 'La placa del vehículo ya existe. Por favor, ingresa otra.')
            elif str(e) == 'chasis_veh':
                messages.error(request, 'El chasis del vehículo ya existe. Por favor, ingresa otro.')
            else:
                messages.error(request, f'Error de integridad: {e}')
        except ValidationError as e:
            messages.error(request, f'Error de validación: {e}')
        except ObjectDoesNotExist as e:
            messages.error(request, f'Error de objeto no encontrado: {e}')
        except Exception as e:
            messages.error(request, f'Error inesperado: {e}')
        
      
        return redirect('ordenCliente')
    
@admin_required
def finalizarOrden(request,id):
    orden = get_object_or_404(Orden,id_ord=id)
    orden.estado_ord='FINALIZADA'
    orden.fecha_fin_ord=timezone.now()
    
        
    orden.save()
   
    messages.success(request,'Orden finalizada correctamente')
    return  redirect('listarOrdenes') 

    

   
@admin_required
def guardarOrden2(request):
    max_numero_ord = Orden.objects.aggregate(models.Max('numero_ord'))['numero_ord__max']
    next_numero_ord = 1 if max_numero_ord is None else max_numero_ord + 1
    context = {
            'next_numero_ord': next_numero_ord,
            'usuarios': Usuario.objects.filter(rol = "MECANICO" , is_active = True),
            'servicios': Servicio.objects.filter(is_deleted =False),
            'ESTADOS': Orden.ESTADOS,
            'vehiculos': Vehiculo.objects.all()
        }
    return render(request,'guardarOrden2.html',context)

@admin_required
def registrarOrden2(request):
    if request.method == 'POST':
        print("Datos POST recibidos:", request.POST)  # Añadir esta línea
        try:
            vehiculo_id = request.POST['vehiculo_id']
            vehiculo = Vehiculo.objects.get(id_veh = vehiculo_id)
            # Generar el próximo número de orden
            ultimo_numero_ord = Orden.objects.all().order_by('numero_ord').last()
            next_numero_ord = ultimo_numero_ord.numero_ord + 1 if ultimo_numero_ord else 1
            # Crear la orden
            orden = Orden.objects.create(
                fecha_ord=timezone.now(),
                numero_ord=next_numero_ord,
                observaciones_ord=request.POST['observaciones_ord'],
                estado_ord=request.POST['estado_ord'],
                usuario_id=Usuario.objects.get(id_usr=request.POST['usuario_id']),
                vehiculo_id=vehiculo,
            )
          
            servicios_ids = request.POST.getlist('servicio_id[]')
            subtotales = request.POST.getlist('subtotal[]')

            for servicio_id, subtotal in zip(servicios_ids, subtotales):
                if servicio_id and subtotal:
                    subtotal = subtotal.replace(',', '.')
                    OrdenServicio.objects.create(
                        orden_id=orden,
                        servicio_id=Servicio.objects.get(id_ser=servicio_id),
                        subtotal=subtotal
                    )

            messages.success(request, 'Orden creada correctamente')
            return redirect('listarOrdenes')

        except Exception as e:
            messages.error(request, f'Error al crear la orden: {e}')
            return redirect('listarOrdenes')



@admin_required
def listarOrdenesNoFinalizadas(request):
    ordenes_no_finalizadas = Orden.objects.exclude(estado_ord='FINALIZADA')
    
    context = {
        'ordenes': ordenes_no_finalizadas
    }
    return render(request, 'listarOrdenesF.html', context)

@admin_required
def listarOrdenesFinalizadas(request):
    ordenes = Orden.objects.filter(estado_ord = 'FINALIZADA')
    return render(request,'ordenes_finalizadas.html',{'ordenes':ordenes})


@admin_required
def obtenerOrden(request,id):
    orden = get_object_or_404(Orden, id_ord=id)
    servicios = Servicio.objects.all()
    usuarios = Usuario.objects.filter(rol = "MECANICO")
    orden_servicios = OrdenServicio.objects.filter(orden_id=orden)
    vehiculos=Vehiculo.objects.all()
    ESTADOS = Orden.ESTADOS
    context = {
        'orden': orden,
        'servicios': servicios,
        'usuarios': usuarios,
        'ESTADOS': ESTADOS,
        'orden_servicios': orden_servicios,
        'vehiculos':vehiculos
    }
    return render(request, 'obtenerOrden.html', context)
@admin_required
def editarOrden(request):
    if request.method == 'POST':
        vehiculo_id = request.POST['vehiculo_id']
        vehiculo = Vehiculo.objects.get(id_veh=vehiculo_id)
        id_ord =request.POST['id_ord']
        orden = Orden.objects.get(id_ord=id_ord)
        orden.vehiculo_id_id = vehiculo
        orden.fecha_ord = request.POST['fecha_ord']
        orden.numero_ord = request.POST['numero_ord']
        orden.observaciones_ord = request.POST['observaciones_ord']
        estado_ord = request.POST['estado_ord']
        if estado_ord == 'FINALIZADA':
            orden.fecha_fin_ord=timezone.now()
        orden.estado_ord=estado_ord
        orden.usuario_id_id = request.POST['usuario_id']
        
        orden.save()

        # Eliminar los servicios antiguos y agregar los nuevos
        OrdenServicio.objects.filter(orden_id=orden).delete()
        servicio_ids = request.POST.getlist('servicio_id[]')
        subtotales = request.POST.getlist('subtotal[]')
        
        for servicio_id, subtotal in zip(servicio_ids, subtotales):
            subtotal = subtotal.replace(',', '.')
            OrdenServicio.objects.create(
                orden_id=orden,
                servicio_id_id=servicio_id,
                subtotal=subtotal
            )

        messages.success(request, 'Orden actualizada correctamente.')
        return redirect('listarOrdenes')
@admin_required
def eliminarOrden(request, id):
    orden = get_object_or_404(Orden, id_ord=id)
    try:
        with transaction.atomic():
            OrdenServicio.objects.filter(orden_id=orden).delete()
            orden.delete()
            messages.success(request, 'Orden eliminada correctamente.')
        return redirect('listarOrdenes')   
    except ProtectedError as e:
        messages.error(request, f'No se puede eliminar la orden porque está referenciada por: {e.protected_objects}')
        return redirect('listarOrdenes')  
    except Orden.DoesNotExist:
        messages.error(request, 'La orden no existe.')
        return redirect('listarOrdenes')  
    except IntegrityError:
        messages.error(request, 'Ha ocurrido un error durante la eliminación de la orden.')
        return redirect('listarOrdenes')
   
    


#Registrar Danios
@admin_required
def registrarDanios(request):
    ordenes = Orden.objects.all()
    return render(request,'registrarDanios2.html',{'ordenes':ordenes})
@admin_required
def guardarDanios(request):
    if request.method == 'POST':
        orden_id = request.POST['orden']
        orden = Orden.objects.get(id_ord=orden_id)
        if Inspeccion.objects.filter(orden_id=orden).exists():
            messages.error(request, 'Ya existe una inspección para esta orden.')
            return redirect('registrarDanios')
        # Crear inspección
        inspeccion = Inspeccion.objects.create(
                km=request.POST['km'],
                orden_id =orden,
                nivel_gasolina=request.POST['nivel_gasolina'],
                plumas='plumas' in request.POST,
                antena='antena' in request.POST,
                radio='radio' in request.POST,
                encendedor='encendedor' in request.POST,
                espejos='espejos' in request.POST,
                gata='gata' in request.POST,
                llave_de_ruedas='llave_de_ruedas' in request.POST,
                llanta_emergencia='llanta_emergencia' in request.POST,
                parlantes='parlantes' in request.POST,
                direccionales='direccionales' in request.POST,
                manubrios='manubrios' in request.POST,
                parabrisas='parabrisas' in request.POST,
                t_seguridad='t_seguridad' in request.POST,
                tapa_radiador='tapa_radiador' in request.POST,
                mandos_funcionales='mandos_funcionales' in request.POST,
                cenicero='cenicero' in request.POST,
                palanca='palanca' in request.POST,
                herramientas='herramientas' in request.POST,
                botiquin='botiquin' in request.POST,
                tapa_gasolina='tapa_gasolina' in request.POST,
                lunas='lunas' in request.POST,
                faros='faros' in request.POST,
                extintor='extintor' in request.POST,
                tapa_cubas='tapa_cubas' in request.POST,
                triangulos='triangulos' in request.POST,
                emblemas='emblemas' in request.POST,
                placas='placas' in request.POST,
                moquetas='moquetas' in request.POST
            )

        x_positions = request.POST.getlist('x_pos[]')
        y_positions = request.POST.getlist('y_pos[]')
        descriptions = request.POST.getlist('descripcion_dan[]')

        for x, y, desc in zip(x_positions, y_positions, descriptions):
            Danio.objects.create(
                x_pos=float(x),
                y_pos=float(y),
                descripcion_dan=desc,
                inspeccion_id=inspeccion
            )

        messages.success(request, 'Inspección registrados correctamente')
        return redirect('listarDanios')
@admin_required
def listarDanios(request):
    
    inspecciones = Inspeccion.objects.all()
    return render(request, 'listar_danios.html', {'danios': inspecciones})

@admin_required
def obtenerDanios(request, id_ord):
    inspeccion = get_object_or_404(Inspeccion, id_ins=id_ord)
    danios = Danio.objects.filter(inspeccion_id=inspeccion).values('id_dan', 'x_pos', 'y_pos', 'descripcion_dan')
    ordenes = Orden.objects.all()
    context = {
        'ordenes':ordenes,
        'inspeccion': inspeccion,
        'danios': json.dumps(list(danios)),
    }
    return render(request, 'obtenerDanio.html', context)

@admin_required
def actualizarDanios(request):
    if request.method == 'POST':
        orden_id = request.POST['orden_id']
        orden = get_object_or_404(Orden, id_ord=orden_id)
        id_ins = request.POST['id_ins']

        inspeccion, created = Inspeccion.objects.get_or_create(id_ins=id_ins)
        inspeccion.orden_id = orden
        inspeccion.km = request.POST.get('km')
        inspeccion.nivel_gasolina = request.POST.get('nivel_gasolina')

        checkboxes = [
            'plumas', 'antena', 'radio', 'encendedor', 'espejos',
            'gata', 'llave_de_ruedas', 'llanta_emergencia', 'parlantes',
            'direccionales', 'manubrios', 'parabrisas', 't_seguridad',
            'tapa_radiador', 'mandos_funcionales', 'cenicero', 'palanca',
            'herramientas', 'botiquin', 'tapa_gasolina', 'lunas', 'faros',
            'extintor', 'tapa_cubas', 'triangulos', 'emblemas', 'placas', 'moquetas'
        ]

        for checkbox in checkboxes:
            setattr(inspeccion, checkbox, checkbox in request.POST)

        inspeccion.save()

        id_dan_list = request.POST.getlist('id_dan[]')
        x_pos_list = request.POST.getlist('x_pos[]')
        y_pos_list = request.POST.getlist('y_pos[]')
        descripcion_dan_list = request.POST.getlist('descripcion_dan[]')
        delete_id_dan_list = request.POST.getlist('deleted_marker_ids[]')

        # Eliminar marcadores
        if delete_id_dan_list:
            Danio.objects.filter(id_dan__in=delete_id_dan_list).delete()

        # Actualizar o crear nuevos marcadores
        for id_dan, x_pos, y_pos, descripcion_dan in zip(id_dan_list, x_pos_list, y_pos_list, descripcion_dan_list):
            if id_dan.startswith('marker-'):  # Nuevo marcador
                Danio.objects.create(
                    x_pos=float(x_pos),
                    y_pos=float(y_pos),
                    descripcion_dan=descripcion_dan,
                    inspeccion_id=inspeccion,
                )
            else:
                danio = Danio.objects.get(id_dan=id_dan)
                danio.x_pos = float(x_pos)
                danio.y_pos = float(y_pos)
                danio.descripcion_dan = descripcion_dan
                danio.save()

        messages.success(request, 'Daños actualizados correctamente')
        return redirect('listarDanios')

    return redirect('listarDanios')
    
def custom_404_view(request, exception):
    return render(request, '404.html')

@admin_required
def eliminarDanios(request,id_ins):
    inspeccion = get_object_or_404(Inspeccion, id_ins=id_ins)
    Danio.objects.filter(inspeccion_id=inspeccion).delete()
    inspeccion.delete()
    messages.success(request, 'Todos los daños asociados a la orden han sido eliminados correctamente')
    return redirect('listarDanios')
    
@admin_required
def listarDetalleOrden(request):
    ordenes_con_repuestos = Orden.objects.filter(ordenrepuesto__isnull=False).distinct()
    return render(request, 'listaDetalle.html', {'ordenes': ordenes_con_repuestos})

@admin_required
def guardarDetalle(request):
    ordenes = Orden.objects.filter(estado_ord ="COMPLETADA")
    return render(request,'detallesOrden.html',{'ordenes':ordenes})

@admin_required
def guardarRepuestos(request):
    if request.method == 'POST':
        orden_id = request.POST.get('orden_id')
        orden = Orden.objects.get(id_ord=orden_id)

        if OrdenRepuesto.objects.filter(orden_id=orden).exists():
            messages.error(request, 'Ya existen repuestos registrados para esta orden.')
            return redirect('registrarDetalle')

        nombres_rep = [nombre.upper() for nombre in request.POST.getlist('nombre_rep[]')]
        descripciones_rep = [descripcion.upper() for descripcion in request.POST.getlist('descripcion_rep[]')]
        precios_rep = request.POST.getlist('precio_rep[]')
        cantidades_rep = request.POST.getlist('cantidad_rep[]')
        subtotales_rep = request.POST.getlist('subtotal_rep[]')

        try:
            with transaction.atomic():
                for nombre, descripcion, precio, cantidad, subtotal in zip(nombres_rep, descripciones_rep, precios_rep, cantidades_rep, subtotales_rep):
                    OrdenRepuesto.objects.create(
                        orden_id=orden,
                        nombre_rep=nombre,
                        descripcion_rep=descripcion,
                        precio_rep=precio,
                        cantidad_rep=cantidad,
                        subtotal_rep=subtotal
                    )
            
            messages.success(request, 'Repuesto(s) guardado(s) correctamente')
            return redirect('listaDetalle')

        except Exception as e:
            messages.error(request, f'Error al guardar repuestos: {e}')
            return redirect('registrarDetalle')
    
    
@admin_required  
def obtenerRepuestos(request, id):
    orden = get_object_or_404(Orden, id_ord=id)
    try:
        repuestos = OrdenRepuesto.objects.filter(orden_id=orden)
    except ObjectDoesNotExist:
        repuestos = []
    
    context = {
        'orden': orden,
        'repuestos': repuestos,
    }
    return render(request, 'obtenerRepuestos.html', context)
@admin_required
def editarRepuestos(request):
    if request.method == 'POST':
        
        orden_id = request.POST['orden_id']
        orden = Orden.objects.get(id_ord=orden_id)
        OrdenRepuesto.objects.filter(orden_id=orden).delete()
        nombre_rep_list = [nombre.upper() for nombre in request.POST.getlist('nombre_rep[]')]
        descripcion_rep_list= [descripcion.upper() for descripcion in request.POST.getlist('descripcion_rep[]')]
        precio_rep_list = request.POST.getlist('precio_rep[]')
        cantidad_rep_list = request.POST.getlist('cantidad_rep[]')
        subtotal_rep_list = request.POST.getlist('subtotal_rep[]')
        
        for nombre_rep, descripcion_rep, precio_rep, cantidad_rep, subtotal_rep in zip(nombre_rep_list, descripcion_rep_list, precio_rep_list, cantidad_rep_list, subtotal_rep_list):
            subtotal_rep = subtotal_rep.replace(',', '.')
            OrdenRepuesto.objects.create(
                orden_id=orden,
                nombre_rep=nombre_rep,
                descripcion_rep=descripcion_rep,
                precio_rep=precio_rep,
                cantidad_rep=cantidad_rep,
                subtotal_rep=subtotal_rep
            )

        messages.success(request, 'Detalle actualizado correctamente.')
        return redirect('listaDetalle')
@admin_required  
def eliminarRepuestos(request,id):
    orden = get_object_or_404(Orden, id_ord=id)
    try:
        OrdenRepuesto.objects.filter(orden_id=orden).delete()
        messages.success(request, 'Todos los repuestos asociados a la orden han sido eliminados correctamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar repuestos: {str(e)}')
    return redirect('listaDetalle')

@admin_required
def detalleOrden(request, id):
    configuracion = Configuracion.objects.get(id=1)
    orden = get_object_or_404(Orden, id_ord=id)
    cliente = orden.vehiculo_id.cli_id
    vehiculo = orden.vehiculo_id
    servicios = OrdenServicio.objects.filter(orden_id=orden)
    repuestos = OrdenRepuesto.objects.filter(orden_id=orden)
    total_servicios = sum(servicio.subtotal for servicio in servicios)
    total_repuestos = sum(repuesto.subtotal_rep for repuesto in repuestos)
    total = total_servicios + total_repuestos
    
    context = {
        'orden': orden,
        'cliente': cliente,
        'vehiculo': vehiculo,
        'servicios': servicios,
        'repuestos': repuestos,
        'configuracion':configuracion,
        'total': total,
    }
    
    return render(request, 'detalle_orden.html', context)
@admin_required
def reporte_inspeccion(request, id):
    inspeccion = get_object_or_404(Inspeccion, id_ins=id)
    danios = Danio.objects.filter(inspeccion_id=inspeccion).values('id_dan', 'x_pos', 'y_pos', 'descripcion_dan')
    ordenes = Orden.objects.all()
    context = {
        'ordenes':ordenes,
        'inspeccion': inspeccion,
        'danios': json.dumps(list(danios)),
    }
   
    return render(request, 'reporte_danios.html', context)


@mecanico_required
def ordenes_mecanico(request):
    user = request.user
    if user.rol == Usuario.MECANICO:
        ordenes = Orden.objects.filter(usuario_id=user, estado_ord='PENDIENTE')
        ordenes_con_servicios = []
        for orden in ordenes:
            servicios = OrdenServicio.objects.filter(orden_id=orden)
            ordenes_con_servicios.append((orden, servicios))
        return render(request, 'lista_orden_m.html', {'ordenes_con_servicios': ordenes_con_servicios})
    else:
        return redirect('home2')
    
@mecanico_required 
def aceptar_orden(request, id_ord):
    orden = get_object_or_404(Orden, id_ord=id_ord)
    vehiculo = orden.vehiculo_id
    
    # Obtener la inspección más reciente asociada a este vehículo
    ultima_inspeccion = Inspeccion.objects.filter(orden_id__vehiculo_id=vehiculo).order_by('-id_ins').first()
    ultimo_kilometraje = ultima_inspeccion.km if ultima_inspeccion else None
    

    if request.user.rol == Usuario.MECANICO and orden.usuario_id == request.user:
        orden.estado_ord = 'EN_PROGRESO'
        orden.save()
        messages.success(request,'Orden acepta correctamente')
        return render(request,'inspeccion_m.html',{'orden':orden,'ultimo_kilometraje':ultimo_kilometraje})
    
@mecanico_required    
def lista_progreso(request):
    user = request.user
    if user.rol == Usuario.MECANICO:
        ordenes = Orden.objects.filter(usuario_id=user, estado_ord__in=['EN_PROGRESO', 'ESPERANDO_REPUESTOS'])
        ordenes_con_servicios = []
        for orden in ordenes:
            servicios = OrdenServicio.objects.filter(orden_id=orden)
            ordenes_con_servicios.append((orden, servicios))
        return render(request, 'lista_orden_progreso.html', {'ordenes_con_servicios': ordenes_con_servicios})
    else:
        return redirect('home2')

@mecanico_required
def cambiar_estado_orden(request, id_ord, nuevo_estado):
    orden = get_object_or_404(Orden, id_ord=id_ord)
    if request.user.rol == Usuario.MECANICO and orden.usuario_id == request.user:
        orden.estado_ord = nuevo_estado
        orden.save()
        messages.success(request, f'Orden cambiada a estado {nuevo_estado} exitosamente.')

        if nuevo_estado == 'COMPLETADA':
            cliente_email = orden.vehiculo_id.cli_id.email_cli
            try:
                send_mail(
                    'Orden Completada',
                    f'Estimado/a {orden.vehiculo_id.cli_id.nombre_cli} {orden.vehiculo_id.cli_id.apellido_cli},\n\nSu orden #{orden.numero_ord} ha sido completada.\n\nGracias por confiar en nosotros.\n\nSaludos,\nMultiAuto',
                    'tu_correo@example.com',  # Cambia esto por el correo electrónico del remitente
                    [cliente_email],
                    fail_silently=False,
                )
                messages.success(request, 'Correo electrónico enviado al cliente exitosamente.')
            except BadHeaderError:
                messages.error(request, 'Error al enviar el correo electrónico.')
            except Exception as e:
                messages.error(request, f'Error al enviar el correo electrónico: {str(e)}')
    else:
        messages.error(request, 'No tienes permiso para cambiar el estado de esta orden.')
    return redirect('listaProgreso')

@mecanico_required
def listar_inspecciones(request):
    usuario_actual = request.user
    inspecciones = Inspeccion.objects.filter(orden_id__usuario_id=usuario_actual)
    return render(request, 'listar_inspecciones_m.html', {'danios': inspecciones})

@mecanico_required
def guardarDaniosM(request):
    if request.method == 'POST':
        orden_id = request.POST['orden']
        orden = Orden.objects.get(id_ord=orden_id)
        if Inspeccion.objects.filter(orden_id=orden).exists():
            messages.error(request, 'Ya existe una inspección para esta orden.')
            return redirect(reverse('aceptar_orden', args=[orden_id]))
        
        inspeccion = Inspeccion.objects.create(
                km=request.POST['km'],
                orden_id =orden,
                nivel_gasolina=request.POST['nivel_gasolina'],
                plumas='plumas' in request.POST,
                antena='antena' in request.POST,
                radio='radio' in request.POST,
                encendedor='encendedor' in request.POST,
                espejos='espejos' in request.POST,
                gata='gata' in request.POST,
                llave_de_ruedas='llave_de_ruedas' in request.POST,
                llanta_emergencia='llanta_emergencia' in request.POST,
                parlantes='parlantes' in request.POST,
                direccionales='direccionales' in request.POST,
                manubrios='manubrios' in request.POST,
                parabrisas='parabrisas' in request.POST,
                t_seguridad='t_seguridad' in request.POST,
                tapa_radiador='tapa_radiador' in request.POST,
                mandos_funcionales='mandos_funcionales' in request.POST,
                cenicero='cenicero' in request.POST,
                palanca='palanca' in request.POST,
                herramientas='herramientas' in request.POST,
                botiquin='botiquin' in request.POST,
                tapa_gasolina='tapa_gasolina' in request.POST,
                lunas='lunas' in request.POST,
                faros='faros' in request.POST,
                extintor='extintor' in request.POST,
                tapa_cubas='tapa_cubas' in request.POST,
                triangulos='triangulos' in request.POST,
                emblemas='emblemas' in request.POST,
                placas='placas' in request.POST,
                moquetas='moquetas' in request.POST
            )

        x_positions = request.POST.getlist('x_pos[]')
        y_positions = request.POST.getlist('y_pos[]')
        descriptions = request.POST.getlist('descripcion_dan[]')

        for x, y, desc in zip(x_positions, y_positions, descriptions):
            Danio.objects.create(
                x_pos=float(x),
                y_pos=float(y),
                descripcion_dan=desc,
                inspeccion_id=inspeccion
            )

        messages.success(request, 'Inspección registrados correctamente')
        return redirect('listaProgreso')

@mecanico_required   
def obtenerDaniosM(request, id_ord):
    inspeccion = get_object_or_404(Inspeccion, id_ins=id_ord)
    danios = Danio.objects.filter(inspeccion_id=inspeccion).values('id_dan', 'x_pos', 'y_pos', 'descripcion_dan')
    ordenes = Orden.objects.all()
    context = {
        'ordenes':ordenes,
        'inspeccion': inspeccion,
        'danios': json.dumps(list(danios)),
    }
    return render(request, 'obtener_danio_m.html', context)

@mecanico_required   
def actualizarDaniosM(request):
    if request.method == 'POST':
        orden_id = request.POST['orden_id']
        orden = get_object_or_404(Orden, id_ord=orden_id)
        id_ins = request.POST['id_ins']

        inspeccion, created = Inspeccion.objects.get_or_create(id_ins=id_ins)
        inspeccion.orden_id = orden
        inspeccion.km = request.POST.get('km')
        inspeccion.nivel_gasolina = request.POST.get('nivel_gasolina')

        checkboxes = [
            'plumas', 'antena', 'radio', 'encendedor', 'espejos',
            'gata', 'llave_de_ruedas', 'llanta_emergencia', 'parlantes',
            'direccionales', 'manubrios', 'parabrisas', 't_seguridad',
            'tapa_radiador', 'mandos_funcionales', 'cenicero', 'palanca',
            'herramientas', 'botiquin', 'tapa_gasolina', 'lunas', 'faros',
            'extintor', 'tapa_cubas', 'triangulos', 'emblemas', 'placas', 'moquetas'
        ]

        for checkbox in checkboxes:
            setattr(inspeccion, checkbox, checkbox in request.POST)

        inspeccion.save()

        id_dan_list = request.POST.getlist('id_dan[]')
        x_pos_list = request.POST.getlist('x_pos[]')
        y_pos_list = request.POST.getlist('y_pos[]')
        descripcion_dan_list = request.POST.getlist('descripcion_dan[]')
        delete_id_dan_list = request.POST.getlist('deleted_marker_ids[]')

        # Eliminar marcadores
        if delete_id_dan_list:
            Danio.objects.filter(id_dan__in=delete_id_dan_list).delete()

      
        for id_dan, x_pos, y_pos, descripcion_dan in zip(id_dan_list, x_pos_list, y_pos_list, descripcion_dan_list):
            if id_dan.startswith('marker-'):  
                Danio.objects.create(
                    x_pos=float(x_pos),
                    y_pos=float(y_pos),
                    descripcion_dan=descripcion_dan,
                    inspeccion_id=inspeccion,
                )
            else:
                danio = Danio.objects.get(id_dan=id_dan)
                danio.x_pos = float(x_pos)
                danio.y_pos = float(y_pos)
                danio.descripcion_dan = descripcion_dan
                danio.save()

        messages.success(request, 'Daños actualizados correctamente')
        return redirect('listarInspeccionM')

    return redirect('listarInspeccionM')

@mecanico_required   
def eliminarDaniosM(request,id_ins):
    inspeccion = get_object_or_404(Inspeccion, id_ins=id_ins)
    Danio.objects.filter(inspeccion_id=inspeccion).delete()
    inspeccion.delete()
    messages.success(request, 'Todos los daños asociados a la orden han sido eliminados correctamente')
    return redirect('listarInspeccionM')

@mecanico_required
def listar_ordenes_completadas(request):
    usuario_actual = request.user
    ordenes_completadas = Orden.objects.filter(estado_ord__in=['COMPLETADA', 'FINALIZADA'], usuario_id=usuario_actual)
    orden_repuestos_ids = OrdenRepuesto.objects.values_list('orden_id', flat=True)
    return render(request, 'lista_ordenes_f.html', {'ordenes': ordenes_completadas,'orden_repuestos_ids':orden_repuestos_ids})



def buscar_vehiculo(request):
    query = request.GET.get('q', '')
    vehiculos = []
    ordenes = []

    if query:
        vehiculos = Vehiculo.objects.filter(cli_id__ci_cli__exact=query)
        ordenes = Orden.objects.filter(vehiculo_id__in=vehiculos).exclude(estado_ord='FINALIZADA')

    context = {
        'query': query,
        'vehiculos': vehiculos,
        'ordenes': ordenes
    }

   
    if not query:
        context['query'] = ''

    return render(request, 'principal.html', context)


def obtener_nombres_repuestos(request):
    term = request.GET.get('term', '')
    repuestos = OrdenRepuesto.objects.filter(nombre_rep__icontains=term).values('nombre_rep', 'precio_rep').distinct()[:10]
    results = []
    for repuesto in repuestos:
        results.append({
            'label': repuesto['nombre_rep'],
            'value': repuesto['nombre_rep'],
            'precio': repuesto['precio_rep'],
        })
    return JsonResponse(results, safe=False)

def obtener_marcas(request):
    term = request.GET.get('term', '')
    marcas = Vehiculo.objects.filter(marca_veh__icontains=term).values('marca_veh').distinct()[:10]
    results = [marca['marca_veh'] for marca in marcas]
    return JsonResponse(results, safe=False)

def obtener_modelos(request):
    term = request.GET.get('term', '')
    modelos = Vehiculo.objects.filter(modelo_veh__icontains=term).values('modelo_veh').distinct()[:10]
    results = [modelo['modelo_veh'] for modelo in modelos]
    return JsonResponse(results, safe=False)

def obtener_colores(request):
    term = request.GET.get('term', '')
    colores = Vehiculo.objects.filter(color_veh__icontains=term).values('color_veh').distinct()[:10]
    results = [color['color_veh'] for color in colores]
    return JsonResponse(results, safe=False)


def index(request):
    configuracion = Configuracion.objects.get(id=1)
    return render(request,'principal.html',{'configuracion':configuracion})

@mecanico_required
def agregarDetalleM(request,id):
    orden = get_object_or_404(Orden,id_ord=id)
    return render(request,'agregar_detalle_m.html',{'orden':orden})



@mecanico_required
def guardarRepuestosM(request):
    try:
       if request.method == 'POST':
        orden_id = request.POST.get('orden')
        orden = Orden.objects.get(id_ord=orden_id)

        if OrdenRepuesto.objects.filter(orden_id=orden).exists():
            messages.error(request, 'Ya existen repuestos registrados para esta orden.')
            return redirect('registrarDetalle')

        nombres_rep = [nombre.upper() for nombre in request.POST.getlist('nombre_rep[]')]
        descripciones_rep = [descripcion.upper() for descripcion in request.POST.getlist('descripcion_rep[]')]
        precios_rep = request.POST.getlist('precio_rep[]')
        cantidades_rep = request.POST.getlist('cantidad_rep[]')
        subtotales_rep = request.POST.getlist('subtotal_rep[]')

        try:
            with transaction.atomic():
                for nombre, descripcion, precio, cantidad, subtotal in zip(nombres_rep, descripciones_rep, precios_rep, cantidades_rep, subtotales_rep):
                    OrdenRepuesto.objects.create(
                        orden_id=orden,
                        nombre_rep=nombre,
                        descripcion_rep=descripcion,
                        precio_rep=precio,
                        cantidad_rep=cantidad,
                        subtotal_rep=subtotal
                    )
            
            messages.success(request, 'Repuesto(s) guardado(s) correctamente')
            return redirect('ordenesCompletas')

        except Exception as e:
            messages.error(request, f'Error al guardar repuestos: {e}')
            return redirect('agregar_detalle_m')
    except Exception as e:
        logger.error(f"Error en agregardetalle: {e}")
        return HttpResponseServerError("Se ha producido un error en el servidor.")

@mecanico_required  
def obtenerRepuestosM(request, id):
    orden = get_object_or_404(Orden, id_ord=id)
    try:
        repuestos = OrdenRepuesto.objects.filter(orden_id=orden)
    except ObjectDoesNotExist:
        repuestos = []
    
    context = {
        'orden': orden,
        'repuestos': repuestos,
    }
    return render(request, 'obtener_detalle_m.html', context)


@mecanico_required
def editarRepuestosM(request):
    if request.method == 'POST':
        
        orden_id = request.POST['orden']
        orden = Orden.objects.get(id_ord=orden_id)
        OrdenRepuesto.objects.filter(orden_id=orden).delete()
        nombre_rep_list = [nombre.upper() for nombre in request.POST.getlist('nombre_rep[]')]
        descripcion_rep_list= [descripcion.upper() for descripcion in request.POST.getlist('descripcion_rep[]')]
        precio_rep_list = request.POST.getlist('precio_rep[]')
        cantidad_rep_list = request.POST.getlist('cantidad_rep[]')
        subtotal_rep_list = request.POST.getlist('subtotal_rep[]')
        
        for nombre_rep, descripcion_rep, precio_rep, cantidad_rep, subtotal_rep in zip(nombre_rep_list, descripcion_rep_list, precio_rep_list, cantidad_rep_list, subtotal_rep_list):
            subtotal_rep = subtotal_rep.replace(',', '.')
            OrdenRepuesto.objects.create(
                orden_id=orden,
                nombre_rep=nombre_rep,
                descripcion_rep=descripcion_rep,
                precio_rep=precio_rep,
                cantidad_rep=cantidad_rep,
                subtotal_rep=subtotal_rep
            )

        messages.success(request, 'Detalle actualizado correctamente.')
        return redirect('ordenesCompletas')

@mecanico_required  
def eliminarRepuestosM(request,id):
    orden = get_object_or_404(Orden, id_ord=id)
    try:
        OrdenRepuesto.objects.filter(orden_id=orden).delete()
        messages.success(request, 'Todos los repuestos asociados a la orden han sido eliminados correctamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar repuestos: {str(e)}')
    return redirect('ordenesCompletas')

def password_reset_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = Usuario.objects.get(email=email)
            token = PasswordResetToken.objects.create(user=user)
            
            reset_link = request.build_absolute_uri(f'/reset-password/{token.token}/')
            send_mail(
                'Recuperar Contraseña',
                f'Haz clic en el siguiente enlace para restablecer tu contraseña: {reset_link}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            messages.success(request, 'Te hemos enviado un enlace para restablecer tu contraseña.')
        except Usuario.DoesNotExist:
            messages.error(request, 'No encontramos ningún usuario con ese correo electrónico.')

    return render(request, 'password_reset_request.html')

def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        if reset_token.is_expired():
            messages.error(request, 'El token ha expirado.')
            return redirect('password_reset_request')
        if reset_token.is_used:
            messages.error(request, 'El token ya ha sido utilizado.')
            return redirect('password_reset_request')

        if request.method == 'POST':
            new_password = request.POST.get('password')
            user = reset_token.user
            user.set_password(new_password)
            user.save()
            reset_token.is_used = True
            reset_token.save()
            messages.success(request, 'Tu contraseña ha sido actualizada.')
            return redirect('login')

    except PasswordResetToken.DoesNotExist:
        messages.error(request, 'Token inválido.')
        return redirect('password_reset_request')

    return render(request, 'reset_password.html', {'token': token})


def custom_404_view(request, exception):
    return render(request, '404.html', status=404)

def custom_500_view(request):
    return render(request, '500.html', status=500)

@admin_required
def configurar_sitio(request):
    # Si ya existe una configuración, la recupera; si no, crea una nueva.
    configuracion, created = Configuracion.objects.get_or_create(id=1)

    if request.method == 'POST':
        telefono = request.POST.get('telefono')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')
        mision = request.POST.get('mision')
        vision = request.POST.get('vision')

        # Validar datos
        if not telefono or not email or not direccion or not mision or not vision:
            messages.error(request, 'Todos los campos son obligatorios.')
        elif len(telefono) != 10 or not telefono.isdigit():
            messages.error(request, 'El teléfono debe tener 10 dígitos numéricos.')
        elif '@' not in email:
            messages.error(request, 'El correo electrónico no es válido.')
        else:
            configuracion.telefono = telefono
            configuracion.correo = email
            configuracion.direccion = direccion
            configuracion.mision = mision
            configuracion.vision = vision
            configuracion.save()

            messages.success(request, 'Configuración guardada exitosamente.')
            return redirect('home')

    context = {'configuracion': configuracion}
    return render(request, 'configuracion.html', context)