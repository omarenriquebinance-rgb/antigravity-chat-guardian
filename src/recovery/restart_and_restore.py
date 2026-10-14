"""
Antigravity Chat Guardian - Módulo de Reinicio y Restauración Automática (1-Click).
Cierra Antigravity IDE de forma ordenada, inyecta todas las conversaciones en la base de datos
(tanto en globalStorage como en cada workspaceStorage correspondiente), y reabre Antigravity IDE
para que todos los chats aparezcan de inmediato en la barra lateral.
"""

import os
import sys
import time
import subprocess
from typing import Optional

# Raíz del proyecto
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from src.backup.extractor import sync_all_conversations
from src.recovery.restore_all import restore_all_to_antigravity
from src.core.paths import get_antigravity_dirs

def get_antigravity_exe() -> Optional[str]:
    """Busca la ruta del ejecutable de Antigravity IDE."""
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE\Antigravity IDE.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Antigravity IDE\Antigravity IDE.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Antigravity IDE\Antigravity IDE.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def kill_antigravity_safe():
    """Cierra todos los procesos de Antigravity IDE asegurando que se liberen los archivos."""
    print("[*] Cerrando instancias activas de Antigravity IDE...")
    proc_names = ["Antigravity IDE.exe", "antigravity ide.exe", "Antigravity.exe", "antigravity.exe"]
    for name in proc_names:
        subprocess.run(["taskkill.exe", "/IM", name, "/F"], capture_output=True, text=True)
    
    # Esperar hasta 5 segundos a que todos los procesos hayan terminado
    for _ in range(10):
        try:
            res = subprocess.run(["tasklist.exe"], capture_output=True, text=True, errors="ignore")
            out = res.stdout.lower()
            if not any(n.lower() in out for n in proc_names):
                break
        except Exception:
            pass
        time.sleep(0.5)
    time.sleep(1.0)
    print("[+] Procesos de Antigravity detenidos y archivos liberados.")

def reopen_antigravity(target_dir: str):
    """Reabre Antigravity IDE de forma desacoplada abriendo el directorio indicado."""
    exe_path = get_antigravity_exe()
    if not exe_path:
        print("[-] Advertencia: No se encontró la ruta del ejecutable de Antigravity IDE.")
        return False

    print(f"[*] Reabriendo Antigravity IDE en: {target_dir}...")
    try:
        # Usar PowerShell Start-Process para desacoplamiento total en Windows
        ps_cmd = f'Start-Process -FilePath "{exe_path}" -ArgumentList \'"{target_dir}"\''
        subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", ps_cmd], close_fds=True)
        print("[+] Antigravity IDE iniciado exitosamente.")
        return True
    except Exception as e:
        print(f"[-] Error al reabrir Antigravity IDE: {e}")
        return False

def restart_and_restore(target_workspace: Optional[str] = None, bind_all_to_target: bool = True) -> bool:
    target_dir = target_workspace or ROOT_DIR
    print("=" * 65)
    print("   ANTIGRAVITY CHAT GUARDIAN - REINICIAR Y RESTAURAR CHATS")
    print("=" * 65)
    print(f"[*] Espacio de trabajo activo objetivo: {target_dir}")

    # 1. Cerrar Antigravity IDE
    kill_antigravity_safe()

    # 2. Sincronizar conversaciones
    print("[*] Sincronizando historial desde disco...")
    try:
        synced = sync_all_conversations()
        print(f"[+] Sincronizadas {synced} conversaciones.")
    except Exception as e:
        print(f"[-] Advertencia durante sincronización: {e}")

    # 3. Inyectar en bases de datos (globalStorage + workspaceStorage)
    print("[*] Inyectando conversaciones en state.vscdb y workspaceStorage...")
    success, msg = restore_all_to_antigravity(
        force=True,
        target_workspace=target_dir,
        bind_all_to_target=bind_all_to_target
    )

    if success:
        print(f"[+] {msg}")
    else:
        print(f"[-] {msg}")
        return False

    # 4. Reabrir Antigravity IDE
    reopen_antigravity(target_dir)

    print("\n" + "=" * 65)
    print("   ¡OPERACIÓN COMPLETADA EXITOSAMENTE!")
    print("   Tus chats ahora están cargados y visibles en la barra lateral.")
    print("=" * 65 + "\n")
    return True

if __name__ == "__main__":
    target = None
    by_proj = False
    for arg in sys.argv[1:]:
        if arg.startswith("--target="):
            target = arg.split("=", 1)[1]
        elif arg == "--by-project":
            by_proj = True

    restart_and_restore(target_workspace=target, bind_all_to_target=not by_proj)
