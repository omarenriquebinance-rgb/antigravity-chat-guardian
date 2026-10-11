"""
Módulo de recuperación, respaldo de seguridad y re-asociación de conversaciones a Antigravity IDE.
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import subprocess
import urllib.parse
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

from src.core.paths import get_antigravity_dirs, normalize_workspace_uri, extract_project_name_from_uri
from src.backup.db import get_connection

def is_antigravity_running() -> bool:
    """Verifica si Antigravity IDE está actualmente en ejecución."""
    try:
        res = subprocess.run(["tasklist.exe"], capture_output=True, text=True, errors="ignore")
        out = res.stdout.lower()
        return "antigravity ide.exe" in out or "antigravity.exe" in out
    except Exception:
        return False

def close_antigravity_safe():
    """Cierra de forma ordenada los procesos de Antigravity para liberar bloqueos."""
    try:
        for name in ("Antigravity IDE.exe", "antigravity ide.exe", "antigravity.exe", "Antigravity.exe"):
            subprocess.run(["taskkill.exe", "/IM", name], capture_output=True)
        time.sleep(1.5)
    except Exception as e:
        print(f"Error cerrando proceso: {e}")

def backup_state_vscdb(state_db_path: str) -> str:
    """Crea una copia de seguridad timestamped de state.vscdb antes de modificarlo."""
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backups", "vscdb_backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"state_{ts}.vscdb")
    shutil.copy2(state_db_path, dest)
    return dest

def find_workspace_storage_hash(target_workspace_uri: str, workspace_storage_dir: str) -> Optional[str]:
    """Encuentra el hash de workspaceStorage correspondiente al URI del proyecto."""
    if not os.path.exists(workspace_storage_dir):
        return None
        
    norm_target = normalize_workspace_uri(target_workspace_uri).lower()
    for item in os.listdir(workspace_storage_dir):
        item_path = os.path.join(workspace_storage_dir, item)
        if os.path.isdir(item_path):
            ws_json = os.path.join(item_path, "workspace.json")
            if os.path.exists(ws_json):
                try:
                    with open(ws_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        folder = data.get("folder", "")
                        if normalize_workspace_uri(folder).lower() == norm_target:
                            return item
                except Exception:
                    pass
    return None

def rebind_conversation_to_workspace(conv_id: str, target_workspace_uri: Optional[str] = None) -> Tuple[bool, str]:
    """
    Re-asocia e inyecta una conversación en state.vscdb de Antigravity.
    """
    paths = get_antigravity_dirs()
    state_vscdb = paths["state_vscdb"]
    
    if not os.path.exists(state_vscdb):
        return False, f"Base de datos de estado no encontrada: {state_vscdb}"
        
    if is_antigravity_running():
        return False, "Antigravity IDE está abierto. Debe cerrarlo temporalmente antes de restaurar para evitar que sobrescriba los datos."

    # Obtener datos de la conversación desde el respaldo
    conn_backup = get_connection(readonly=True)
    try:
        c = conn_backup.cursor()
        c.execute("SELECT title, created_at, updated_at, workspace_uri, project_name FROM conversations WHERE conversation_id = ?", (conv_id,))
        conv_row = c.fetchone()
        if not conv_row:
            return False, f"Conversación {conv_id} no encontrada en la base de datos de respaldo."
        
        title, created_at, updated_at, orig_uri, project = conv_row
    finally:
        conn_backup.close()

    final_uri = normalize_workspace_uri(target_workspace_uri or orig_uri or normalize_workspace_uri(os.getcwd()))

    # 1. Crear copia de seguridad preventiva
    backup_file = backup_state_vscdb(state_vscdb)

    # 2. Modificar state.vscdb de forma atómica
    try:
        conn = sqlite3.connect(state_vscdb)
        with conn:
            cursor = conn.cursor()
            
            # Actualizar chat.ChatSessionStore.index
            cursor.execute("SELECT value FROM ItemTable WHERE key = 'chat.ChatSessionStore.index'")
            row = cursor.fetchone()
            index_data = {"version": 1, "entries": {}}
            if row and row[0]:
                try:
                    index_data = json.loads(row[0])
                    if "entries" not in index_data:
                        index_data["entries"] = {}
                except Exception:
                    index_data = {"version": 1, "entries": {}}

            # Fecha en milisegundos
            ms_time = int(time.time() * 1000)
            index_data["entries"][conv_id] = {
                "sessionId": conv_id,
                "creationDate": ms_time,
                "customTitle": title,
                "isImported": False
            }

            cursor.execute("""
            INSERT INTO ItemTable (key, value) VALUES ('chat.ChatSessionStore.index', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (json.dumps(index_data, ensure_ascii=False),))

            # Si existe un workspaceStorage específico, también actualizarlo allí
            ws_hash = find_workspace_storage_hash(final_uri, paths["workspace_storage"])
            if ws_hash:
                ws_vscdb = os.path.join(paths["workspace_storage"], ws_hash, "state.vscdb")
                if os.path.exists(ws_vscdb):
                    try:
                        conn_ws = sqlite3.connect(ws_vscdb)
                        with conn_ws:
                            c_ws = conn_ws.cursor()
                            c_ws.execute("SELECT value FROM ItemTable WHERE key = 'chat.ChatSessionStore.index'")
                            ws_row = c_ws.fetchone()
                            ws_index = {"version": 1, "entries": {}}
                            if ws_row and ws_row[0]:
                                try:
                                    ws_index = json.loads(ws_row[0])
                                    if "entries" not in ws_index:
                                        ws_index["entries"] = {}
                                except Exception:
                                    pass
                            ws_index["entries"][conv_id] = {
                                "sessionId": conv_id,
                                "creationDate": ms_time,
                                "customTitle": title,
                                "isImported": False
                            }
                            c_ws.execute("""
                            INSERT INTO ItemTable (key, value) VALUES ('chat.ChatSessionStore.index', ?)
                            ON CONFLICT(key) DO UPDATE SET value = excluded.value
                            """, (json.dumps(ws_index, ensure_ascii=False),))
                        conn_ws.close()
                    except Exception as e:
                        print(f"Nota: No se pudo actualizar workspaceStorage local: {e}")

        conn.close()
        return True, f"Conversación '{title}' restaurada exitosamente para el workspace {final_uri}. Respaldo previo creado en: {os.path.basename(backup_file)}"
    except Exception as e:
        return False, f"Error durante la inyección en state.vscdb: {e}"
