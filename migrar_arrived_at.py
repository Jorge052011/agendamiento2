#!/usr/bin/env python
"""
Script para migrar la base de datos existente:
- Agrega columna arrived_at si no existe (como TEXT)
- Agrega columna departed_at si no existe (como TEXT)
- Si ya existen como DATETIME, convierte los valores a texto HH:MM

Ejecutar en el servidor:
    python migrar_arrived_at.py
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'repartotrack.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db import connection

def migrar():
    cursor = connection.cursor()

    # Ver columnas actuales
    cols_info = cursor.execute("PRAGMA table_info(deliveries)").fetchall()
    cols = {row[1]: row[2] for row in cols_info}  # nombre -> tipo
    print(f"Columnas actuales en 'deliveries': {list(cols.keys())}")

    for campo in ('arrived_at', 'departed_at'):
        if campo not in cols:
            cursor.execute(f"ALTER TABLE deliveries ADD COLUMN {campo} TEXT")
            print(f"✅ Columna '{campo}' agregada como TEXT")
        elif cols[campo].upper() in ('DATETIME', 'TIMESTAMP'):
            # Existe como DATETIME — convertir valores a texto HH:MM y renombrar
            print(f"⚠️  '{campo}' existe como {cols[campo]}, convirtiendo valores...")
            # SQLite no permite ALTER COLUMN, hay que recrear
            # Guardamos los valores convertidos en una columna temporal
            tmp = f"{campo}_txt"
            cursor.execute(f"ALTER TABLE deliveries ADD COLUMN {tmp} TEXT")
            cursor.execute(f"""
                UPDATE deliveries
                SET {tmp} = CASE
                    WHEN {campo} IS NOT NULL
                    THEN substr({campo}, 12, 5)
                    ELSE NULL
                END
            """)
            # Vaciamos la columna original (no podemos borrarla en SQLite sin recrear tabla)
            cursor.execute(f"UPDATE deliveries SET {campo} = {tmp}")
            cursor.execute(f"UPDATE deliveries SET {tmp} = NULL")
            print(f"✅ Valores de '{campo}' convertidos a formato HH:MM")
        else:
            print(f"✅ '{campo}' ya existe como {cols[campo]}, sin cambios")

    connection.commit()
    print("\n✅ Migración completada. Reinicia el servidor Django.")

if __name__ == '__main__':
    migrar()
