#!/bin/bash
# Limpia procesos duplicados de agendamiento y reinicia correctamente
# Uso: bash reiniciar_agendamiento.sh

PROYECTO="$HOME/proyectos/agendamiento"
PUERTO=8003

echo "=== Procesos actuales de agendamiento ==="
ps aux | grep "agendamiento.*runserver" | grep -v grep

echo ""
echo "=== Matando todos los procesos del agendamiento en puerto $PUERTO ==="
pkill -f "agendamiento.*runserver" && echo "✅ Procesos terminados." || echo "⚠️  No había procesos corriendo."

sleep 2

echo ""
echo "=== Verificando que no queden procesos ==="
RESTANTES=$(ps aux | grep "agendamiento.*runserver" | grep -v grep | wc -l)
if [ "$RESTANTES" -gt 0 ]; then
    echo "⚠️  Aún quedan procesos, forzando..."
    pkill -9 -f "agendamiento.*runserver"
    sleep 1
fi

echo ""
echo "=== Reparando JSON corrupto (si aplica) ==="
cd "$PROYECTO"
python3 reparar_json.py

echo ""
echo "=== Iniciando servidor en background ==="
cd "$PROYECTO"
source venv/bin/activate
nohup python manage.py runserver 0.0.0.0:$PUERTO > /tmp/agendamiento.log 2>&1 &
NUEVO_PID=$!
sleep 2

if ps -p $NUEVO_PID > /dev/null; then
    echo "✅ Servidor iniciado con PID $NUEVO_PID en puerto $PUERTO"
    echo "   Logs en: /tmp/agendamiento.log"
else
    echo "❌ El servidor no pudo iniciar. Revisa los logs:"
    cat /tmp/agendamiento.log
fi
