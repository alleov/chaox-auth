#!/bin/bash

PYTHON_VENV="./venv/bin/python3"

if [ ! -f "$PYTHON_VENV" ]; then
    echo "[ERROR] No se encontró el entorno virtual en $PYTHON_VENV"
    echo "Asegúrate de que el venv esté en la carpeta raíz del proyecto."
    exit 1
fi

echo "------------------------------------------------"
echo "         ASIGNADOR DE ADMINISTRADORES            "
echo "------------------------------------------------"

read -p "Ingresa la matrícula (username) para ser Admin: " USER_ID

$PYTHON_VENV << END
try:
    from app import db, Usuario, app
    with app.app_context():
        user = Usuario.query.filter_by(username="$USER_ID").first()
        if user:
            user.is_admin = True
            user.bloqueado = False
            user.intentos_fallidos = 0
            db.session.commit()
            print(f"\n[OK] El usuario '{user.nombre}' ($USER_ID) ahora es ADMINISTRADOR.")
        else:
            print(f"\n[ERROR] No se encontró al usuario: $USER_ID")
except Exception as e:
    print(f"\n[FATAL] Error al conectar con la base de datos: {e}")
END

echo "------------------------------------------------"