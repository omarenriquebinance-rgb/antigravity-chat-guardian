"""
Interfaz de Línea de Comandos (CLI) para Antigravity Chat Persistence & Recovery Suite.
"""

import sys
import os
import argparse

# Asegurar que el directorio raíz del proyecto esté en el sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backup.extractor import sync_all_conversations, sync_single_conversation
from src.backup.watcher import AntigravityLiveWatcher
from src.recovery.restorer import rebind_conversation_to_workspace, is_antigravity_running
from src.viewer.server import run_server
from src.backup.db import get_connection

def cmd_status():
    print("\n--- ESTADO DE LA SUITE DE PERSISTENCIA ---")
    conn = get_connection(readonly=True)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM conversations")
    total_c = c.fetchone()[0]
    c.execute("SELECT count(*) FROM messages")
    total_m = c.fetchone()[0]
    c.execute("SELECT project_name, count(*) FROM conversations GROUP BY project_name ORDER BY count(*) DESC")
    projs = c.fetchall()
    conn.close()

    print(f"Conversaciones Respaldadas: {total_c}")
    print(f"Total Mensajes y Pasos:     {total_m:,}")
    print(f"Antigravity IDE en ejecucin: {'S' if is_antigravity_running() else 'No'}")
    print("\nProyectos mapeados:")
    for name, cnt in projs:
        print(f"  - {name:<28} ({cnt} chats)")
    print("------------------------------------------\n")

def cmd_sync():
    print("[*] Iniciando sincronizacin completa de conversaciones...")
    count = sync_all_conversations()
    print(f"[+] Sincronizacin completada: {count} conversaciones procesadas.")

def cmd_watch():
    watcher = AntigravityLiveWatcher()
    watcher.start()

def cmd_serve(port: int):
    run_server(port)

def cmd_restore(conv_id: str, workspace_uri: str = None):
    from src.core.paths import normalize_workspace_uri
    if not workspace_uri:
        workspace_uri = normalize_workspace_uri(os.getcwd())
    print(f"[*] Intentando restaurar conversacion {conv_id}...")
    success, msg = rebind_conversation_to_workspace(conv_id, workspace_uri)
    if success:
        print(f"[+] {msg}")
    else:
        print(f"[-] {msg}")

def cmd_restore_all(force: bool = False, target: str = None, by_project: bool = False):
    from src.recovery.restore_all import restore_all_to_antigravity
    print("[*] Iniciando restauracion completa de todas las conversaciones...")
    success, msg = restore_all_to_antigravity(
        force=force,
        target_workspace=target or os.getcwd(),
        bind_all_to_target=not by_project
    )
    if success:
        print(f"[+] {msg}")
    else:
        print(f"[-] {msg}")

def cmd_doctor():
    from src.core.doctor import print_doctor_report
    print_doctor_report()

def cmd_export(conv_id: str, fmt: str, out_path: str = None):
    from src.core.exporter import export_conversation_to_markdown, export_conversation_to_json
    if not out_path:
        ext = "md" if fmt == "md" else "json"
        out_path = f"export_{conv_id[:8]}.{ext}"
    
    if fmt == "md":
        export_conversation_to_markdown(conv_id, out_path)
    else:
        export_conversation_to_json(conv_id, out_path)
    print(f"[+] Conversacion exportada exitosamente a: {out_path}")

def main():
    parser = argparse.ArgumentParser(description="Antigravity Chat Guardian CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Muestra el estado de la base de datos y procesos")
    subparsers.add_parser("doctor", help="Diagnostico completo de salud y analisis de integridad")
    subparsers.add_parser("sync", help="Sincroniza todas las conversaciones supervivientes")
    subparsers.add_parser("watch", help="Inicia el servicio de respaldo continuo en segundo plano")

    serve_p = subparsers.add_parser("serve", help="Inicia el servidor Web y visor de conversaciones")
    serve_p.add_argument("--port", type=int, default=7890, help="Puerto HTTP (defecto 7890)")

    restore_p = subparsers.add_parser("restore", help="Restaura una conversacion en Antigravity")
    restore_p.add_argument("conv_id", help="UUID de la conversacion a restaurar")
    restore_p.add_argument("--workspace", default=None, help="URI del workspace de destino (por defecto carpeta actual)")

    restore_all_p = subparsers.add_parser("restore-all", help="Restaura todas las conversaciones (100+) a sus proyectos correspondientes")
    restore_all_p.add_argument("--force", action="store_true", help="Forzar escritura incluso si Antigravity esta abierto")
    restore_all_p.add_argument("--target", default=None, help="Carpeta o workspace destino (por defecto carpeta actual)")
    restore_all_p.add_argument("--by-project", action="store_true", help="Vincular cada conversacion exclusivamente a su carpeta de proyecto original")

    export_p = subparsers.add_parser("export", help="Exporta una conversacion a Markdown o JSON")
    export_p.add_argument("conv_id", help="UUID de la conversacion a exportar")
    export_p.add_argument("--format", choices=["md", "json"], default="md", help="Formato de exportacion")
    export_p.add_argument("--out", default=None, help="Ruta del archivo de salida")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command == "sync":
        cmd_sync()
    elif args.command == "watch":
        cmd_watch()
    elif args.command == "serve":
        cmd_serve(args.port)
    elif args.command == "restore":
        cmd_restore(args.conv_id, args.workspace)
    elif args.command == "restore-all":
        cmd_restore_all(args.force, args.target, args.by_project)
    elif args.command == "export":
        cmd_export(args.conv_id, args.format, args.out)
    else:
        cmd_status()

if __name__ == "__main__":
    main()

