#!/usr/bin/env bash
# Exit on error
set -o errexit

# Modify this line as needed for your package manager (pip, poetry, etc.)
pip install -r requirements.txt

# Convert static asset files
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
python manage.py migrate

# Crear un usuario de ejemplo con una contraseña de prueba
python manage.py shell <<EOF
from Aplicaciones.Gestion.models import Usuario  

# Verificar si el usuario ya existe
if not Usuario.objects.filter(username='admin2').exists():
    usuario = Usuario(
        username='admin2',
        nombre='Jorge',
        apellido='Muela',
        telefono='123456789',
        email='admin@example.com',
        rol=Usuario.ADMINISTRADOR,
        is_active=True,
        is_deleted=False
    )
    # Establecer la contraseña utilizando el método set_password
    usuario.set_password('12345678')
    # Guardar el usuario en la base de datos
    usuario.save()

EOF
