#!/usr/bin/env bash
# ========================================================
#   ANTIGRAVITY CHAT GUARDIAN - SETUP (macOS & Linux)
# ========================================================

echo "========================================================"
echo "      ANTIGRAVITY CHAT GUARDIAN - SETUP (macOS & Linux) "
echo "========================================================"
echo ""

# Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "[X] Python 3 no fue encontrado."
    echo "    Por favor instala Python 3.10 o superior (ej: brew install python en macOS)."
    exit 1
fi

python3 --version
echo "[V] Python 3 detectado correctamente."
echo ""

# Ejecutar Diagnóstico
echo "[*] Ejecutando diagnostico del sistema..."
python3 cli.py doctor

echo ""
echo "========================================================"
echo "  Instalacion completada con exito."
echo "========================================================"
echo ""
echo "Comandos rapidos disponibles:"
echo "  - Restaurar historial:  python3 cli.py restore-all --force"
echo "  - Activar vigilancia:   nohup python3 cli.py watch > /dev/null 2>&1 &"
echo "  - Abrir visor web:      python3 cli.py serve"
echo ""
