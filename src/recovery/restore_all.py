"""
Restaurador Maestro de Historial en la Interfaz de Antigravity IDE.
Reconstruye y re-asocia todas las conversaciones (100+) a sus proyectos correspondientes
en state.vscdb para que aparezcan en la barra lateral de Antigravity.
100% Autónomo, sin dependencias externas.
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import base64
import urllib.parse
from datetime import datetime
from typing import Dict, List, Tuple, Any

# Raíz del proyecto
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from src.core.paths import get_antigravity_dirs, normalize_workspace_uri, extract_project_name_from_uri
from src.backup.db import get_connection
from src.core.protobuf import ProtobufEncoder
from src.core.db_scanner import extract_existing_metadata

PB_KEY = "antigravityUnifiedStateSync.trajectorySummaries"
JSON_KEY = "chat.ChatSessionStore.index"

def build_workspace_dict(path: str) -> Dict[str, str]:
    path_normalized = path.replace("\\", "/").rstrip("/")
    if sys.platform.startswith("win") and len(path_normalized) >= 2 and path_normalized[1] == ":":
        path_normalized = path_normalized[0].lower() + path_normalized[1:]
    
    folder_name = os.path.basename(path_normalized) or "RecoveredProject"

    uri_path_encoded = urllib.parse.quote(path_normalized, safe="/")
    uri_encoded = f"file:///{uri_path_encoded}"
    uri_plain = f"file:///{path_normalized}"

    return {
        "uri_encoded": uri_encoded,
        "uri_plain": uri_plain,
        "corpus": f"local/{folder_name}",
        "git_remote": f"https://github.com/local/{folder_name}.git",
        "branch": "main",
    }

def create_backup(db_path: str, reason: str = "manual") -> str:
    backup_dir = os.path.join(ROOT_DIR, "backups", "vscdb_backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"state_{ts}_{reason}.vscdb")
    shutil.copy2(db_path, backup_path)
    return backup_path

def is_antigravity_running() -> bool:
    import subprocess
    try:
        res = subprocess.run(["tasklist.exe"], capture_output=True, text=True, errors="ignore")
        out = res.stdout.lower()
        return "antigravity ide.exe" in out or "antigravity.exe" in out
    except Exception:
        return False

def build_workspace_map_from_backup_db() -> Dict[str, Dict[str, str]]:
    ws_assignments = {}
    conn = get_connection(readonly=True)
    try:
        c = conn.cursor()
        c.execute("SELECT conversation_id, workspace_uri, project_name FROM conversations")
        fallback_path = ROOT_DIR.replace("\\", "/")
        parent_dir = os.path.dirname(ROOT_DIR).replace("\\", "/")
        for cid, uri, proj in c.fetchall():
            if uri and uri.startswith("file:///"):
                clean_path = urllib.parse.unquote(uri[len("file:///"):])
                if len(clean_path) >= 2 and clean_path[1] == ":":
                    clean_path = clean_path[0].lower() + clean_path[1:]
                ws_assignments[cid] = build_workspace_dict(clean_path)
            elif proj and proj != "General":
                ws_assignments[cid] = build_workspace_dict(f"{parent_dir}/{proj}")
            else:
                ws_assignments[cid] = build_workspace_dict(fallback_path)
    finally:
        conn.close()
    return ws_assignments

def restore_all_to_antigravity(force: bool = False) -> Tuple[bool, str]:
    paths = get_antigravity_dirs()
    state_vscdb = paths["state_vscdb"]
    convs_dir = paths["conversations"]

    if not os.path.exists(state_vscdb):
        return False, f"Base de datos state.vscdb no encontrada en: {state_vscdb}"

    if is_antigravity_running() and not force:
        return False, "Antigravity IDE está abierto. Debes cerrarlo temporalmente antes de restaurar para que no sobrescriba la base de datos."

    # 1. Crear respaldo preventivo
    backup_path = create_backup(state_vscdb, reason="before_full_restore")
    print(f"[*] Respaldo de seguridad creado en: {os.path.basename(backup_path)}")

    # 2. Obtener asignaciones de workspace
    ws_assignments = build_workspace_map_from_backup_db()
    print(f"[*] Mapeados {len(ws_assignments)} proyectos/workspaces para inyección.")

    # 3. Leer metadata existente para conservar títulos
    conn = sqlite3.connect(state_vscdb)
    cur = conn.cursor()

    existing_titles = {}
    existing_inner_blobs = {}
    try:
        cur.execute("SELECT value FROM ItemTable WHERE key=?", (PB_KEY,))
        row = cur.fetchone()
        if row and row[0]:
            decoded = base64.b64decode(row[0])
            existing_titles, existing_inner_blobs = extract_existing_metadata(decoded)
    except Exception:
        pass

    conn_bk = get_connection(readonly=True)
    c_bk = conn_bk.cursor()
    c_bk.execute("SELECT conversation_id, title FROM conversations")
    for cid, t in c_bk.fetchall():
        if t and cid not in existing_titles:
            existing_titles[cid] = t
    conn_bk.close()

    # 4. Listar todas las conversaciones físicas
    raw_files = os.listdir(convs_dir)
    cid_set = {f[:-3] for f in raw_files if f.endswith(".pb") or f.endswith(".db")}
    all_cids = sorted(list(cid_set))

    print(f"[*] Procesando {len(all_cids)} conversaciones físicas...")

    result_bytes = b""
    chat_idx = {"version": 1, "entries": {}}

    for cid in all_cids:
        title = existing_titles.get(cid)
        if not title:
            title = f"Conversación {cid[:8]}"

        ws_dict = ws_assignments.get(cid, build_workspace_dict(ROOT_DIR))

        src_path = os.path.join(convs_dir, f"{cid}.db")
        if not os.path.exists(src_path):
            src_path = os.path.join(convs_dir, f"{cid}.pb")

        ctime = int(os.path.getctime(src_path)) if os.path.exists(src_path) else int(time.time())
        mtime = int(os.path.getmtime(src_path)) if os.path.exists(src_path) else int(time.time())

        inner_data = existing_inner_blobs.get(cid)

        entry = ProtobufEncoder.build_trajectory_entry(
            cid, title, ws_dict, ctime, mtime, existing_inner_data=inner_data
        )
        result_bytes += entry

        mtime_ms = mtime * 1000
        chat_idx["entries"][cid] = {
            "sessionId": cid,
            "title": title,
            "lastModified": mtime_ms,
            "isStale": False
        }

    # 5. Inyección atómica en ItemTable
    encoded_pb = base64.b64encode(result_bytes).decode("utf-8")
    json_str = json.dumps(chat_idx, ensure_ascii=False)

    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (PB_KEY, encoded_pb))
            conn.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (JSON_KEY, json_str))
        conn.close()
        
        return True, f"Éxito total: {len(all_cids)} conversaciones inyectadas en Antigravity IDE con sus respectivos proyectos."
    except Exception as e:
        return False, f"Error escribiendo en state.vscdb: {e}"

if __name__ == "__main__":
    force_run = "--force" in sys.argv
    success, msg = restore_all_to_antigravity(force=force_run)
    print(f"\nResultado: {'[OK]' if success else '[ERROR]'} {msg}")
