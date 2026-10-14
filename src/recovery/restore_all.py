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
from typing import Dict, List, Tuple, Any, Optional

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

def get_all_workspace_storage_mappings() -> Dict[str, Tuple[str, str]]:
    """
    Escanea la carpeta User/workspaceStorage y mapea cada hash a su URI y nombre de proyecto.
    Retorna: { hash: (normalized_uri, project_name) }
    """
    paths = get_antigravity_dirs()
    ws_dir = paths.get("workspace_storage")
    mappings = {}
    if not ws_dir or not os.path.exists(ws_dir):
        return mappings

    for item in os.listdir(ws_dir):
        item_path = os.path.join(ws_dir, item)
        if os.path.isdir(item_path):
            ws_json = os.path.join(item_path, "workspace.json")
            if os.path.exists(ws_json):
                try:
                    with open(ws_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        raw_folder = data.get("folder", "")
                        if raw_folder:
                            norm = urllib.parse.unquote(raw_folder).replace("\\", "/").rstrip("/")
                            pname = norm.split("/")[-1] if "/" in norm else norm
                            mappings[item] = (norm, pname)
                except Exception:
                    pass
    return mappings

def update_workspace_storages(chat_idx: Dict[str, Any], target_workspace_uri: Optional[str] = None) -> int:
    """
    Propaga el índice de sesiones a las bases de datos locales de workspaceStorage.
    Inyecta todas las conversaciones en el workspace activo (target),
    y en los demás proyectos inyecta sus conversaciones correspondientes.
    """
    paths = get_antigravity_dirs()
    ws_dir = paths.get("workspace_storage")
    if not ws_dir or not os.path.exists(ws_dir):
        return 0

    mappings = get_all_workspace_storage_mappings()
    updated_count = 0

    # Normalizar URI objetivo
    norm_target = normalize_workspace_uri(target_workspace_uri or ROOT_DIR).lower() if target_workspace_uri else None

    # Mapeo de conversaciones a proyectos desde la DB de respaldo
    conn_bk = get_connection(readonly=True)
    c_bk = conn_bk.cursor()
    c_bk.execute("SELECT conversation_id, project_name, workspace_uri FROM conversations")
    conv_to_proj = {}
    for cid, proj, uri in c_bk.fetchall():
        conv_to_proj[cid] = (proj or "").lower(), (uri or "").lower()
    conn_bk.close()

    for ws_hash, (ws_uri, ws_pname) in mappings.items():
        ws_vscdb = os.path.join(ws_dir, ws_hash, "state.vscdb")
        if not os.path.exists(ws_vscdb):
            continue

        is_target_ws = norm_target and (norm_target in ws_uri.lower() or ws_uri.lower() in norm_target)

        # Construir entries para este workspace específico
        ws_entries = {}
        for cid, entry_data in chat_idx.get("entries", {}).items():
            if is_target_ws:
                # El workspace activo recibe todas las conversaciones
                ws_entries[cid] = entry_data
            else:
                # Comprobar si pertenece a este proyecto
                proj_info = conv_to_proj.get(cid)
                if proj_info:
                    p_name, p_uri = proj_info
                    if (ws_pname and ws_pname.lower() in p_name) or (ws_uri and ws_uri.lower() in p_uri):
                        ws_entries[cid] = entry_data

        if ws_entries:
            try:
                conn_local = sqlite3.connect(ws_vscdb)
                with conn_local:
                    c_loc = conn_local.cursor()
                    c_loc.execute("SELECT value FROM ItemTable WHERE key = ?", (JSON_KEY,))
                    row = c_loc.fetchone()
                    local_idx = {"version": 1, "entries": {}}
                    if row and row[0]:
                        try:
                            local_idx = json.loads(row[0])
                            if "entries" not in local_idx or not isinstance(local_idx["entries"], dict):
                                local_idx["entries"] = {}
                        except Exception:
                            local_idx = {"version": 1, "entries": {}}
                    
                    # Unir preservando
                    for cid, edata in ws_entries.items():
                        local_idx["entries"][cid] = edata

                    c_loc.execute(
                        "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
                        (JSON_KEY, json.dumps(local_idx, ensure_ascii=False))
                    )
                    c_loc.execute("PRAGMA wal_checkpoint(FULL)")
                conn_local.close()
                updated_count += 1
            except Exception as e:
                print(f"[-] Advertencia al actualizar workspaceStorage {ws_hash} ({ws_pname}): {e}")

    return updated_count

def restore_all_to_antigravity(
    force: bool = False,
    target_workspace: Optional[str] = None,
    bind_all_to_target: bool = True
) -> Tuple[bool, str]:
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
    
    # Si se pide vincular todo al workspace destino (por defecto la carpeta activa de Antigravity)
    target_ws_dict = None
    if bind_all_to_target:
        effective_target = target_workspace or ROOT_DIR
        target_ws_dict = build_workspace_dict(effective_target)
        print(f"[*] Modo Unificado: Todas las conversaciones serán visibles en: {effective_target}")
    else:
        print(f"[*] Mapeados {len(ws_assignments)} proyectos/workspaces para inyección individual.")

    # 3. Leer metadata existente para conservar títulos limpios
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
        if t:
            # Limpiar posibles caracteres mal decodificados
            clean_t = t.replace("\ufffd", "").strip()
            existing_titles[cid] = clean_t
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

        # Si bind_all_to_target está activo, usar target_ws_dict para que aparezca en la ventana actual
        if bind_all_to_target and target_ws_dict:
            ws_dict = target_ws_dict
        else:
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
            "customTitle": title,
            "lastModified": mtime_ms,
            "isStale": False
        }

    # 5. Inyección atómica en ItemTable global
    encoded_pb = base64.b64encode(result_bytes).decode("utf-8")
    json_str = json.dumps(chat_idx, ensure_ascii=False)

    try:
        with conn:
            conn.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (PB_KEY, encoded_pb))
            conn.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)", (JSON_KEY, json_str))
            conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.close()

        # 6. Actualizar workspaceStorage locales
        ws_updated = update_workspace_storages(chat_idx, target_workspace_uri=target_workspace or ROOT_DIR)
        print(f"[+] Actualizadas {ws_updated} bases de datos locales en workspaceStorage.")

        return True, (
            f"Éxito total: {len(all_cids)} conversaciones inyectadas en Antigravity IDE "
            f"(Global + {ws_updated} workspaces locales actualizados)."
        )
    except Exception as e:
        return False, f"Error escribiendo en state.vscdb: {e}"

if __name__ == "__main__":
    force_run = "--force" in sys.argv
    target_arg = None
    for arg in sys.argv:
        if arg.startswith("--target="):
            target_arg = arg.split("=", 1)[1]
    success, msg = restore_all_to_antigravity(force=force_run, target_workspace=target_arg)
    print(f"\nResultado: {'[OK]' if success else '[ERROR]'} {msg}")
