"""
Módulo de Diagnóstico del Sistema (Health & Integrity Doctor) para Antigravity IDE.
Evalúa el estado físico del almacenamiento, índices SQLite y coherencia de sesiones.
"""

import os
import sys
import json
import sqlite3
from typing import Dict, Any

from src.core.paths import get_antigravity_dirs
from src.recovery.restorer import is_antigravity_running
from src.backup.db import get_connection

def run_doctor_diagnostics() -> Dict[str, Any]:
    paths = get_antigravity_dirs()
    report = {
        "python_version": sys.version.split()[0],
        "ide_running": is_antigravity_running(),
        "paths": {},
        "physical_conversations": 0,
        "brain_conversations": 0,
        "vscdb_exists": False,
        "vscdb_index_count": 0,
        "vscdb_trajectory_count": 0,
        "backup_db_exists": False,
        "backup_conversations": 0,
        "backup_messages": 0,
        "issues": [],
        "recommendations": []
    }

    # 1. Verificar carpetas físicas
    for name, p in paths.items():
        exists = os.path.exists(p)
        report["paths"][name] = {"path": p, "exists": exists}

    conv_dir = paths.get("conversations", "")
    if os.path.exists(conv_dir):
        files = os.listdir(conv_dir)
        c_files = [f for f in files if (f.endswith(".db") or f.endswith(".pb")) and len(f) > 30]
        report["physical_conversations"] = len(c_files)
    else:
        report["issues"].append("No se encontró el directorio de conversaciones de Antigravity.")

    brain_dir = paths.get("brain", "")
    if os.path.exists(brain_dir):
        report["brain_conversations"] = len(os.listdir(brain_dir))

    # 2. Verificar state.vscdb
    state_vscdb = paths.get("state_vscdb", "")
    if os.path.exists(state_vscdb):
        report["vscdb_exists"] = True
        try:
            conn = sqlite3.connect(f"file:{state_vscdb}?mode=ro", uri=True)
            cur = conn.cursor()
            
            # Chequear chat.ChatSessionStore.index
            cur.execute("SELECT value FROM ItemTable WHERE key = 'chat.ChatSessionStore.index'")
            row = cur.fetchone()
            if row and row[0]:
                try:
                    data = json.loads(row[0])
                    report["vscdb_index_count"] = len(data.get("entries", {}))
                except Exception:
                    pass
            
            # Chequear trajectorySummaries
            cur.execute("SELECT value FROM ItemTable WHERE key = 'antigravityUnifiedStateSync.trajectorySummaries'")
            row_traj = cur.fetchone()
            if row_traj and row_traj[0]:
                from src.core.db_scanner import extract_existing_metadata
                try:
                    meta = extract_existing_metadata(row_traj[0])
                    report["vscdb_trajectory_count"] = len(meta)
                except Exception:
                    pass

            conn.close()
        except Exception as e:
            report["issues"].append(f"No se pudo leer state.vscdb: {e}")
    else:
        report["issues"].append("state.vscdb no encontrado.")

    # 3. Verificar base de respaldo local
    from src.backup.db import DB_PATH as bk_path
    if os.path.exists(bk_path):
        report["backup_db_exists"] = True
        try:
            conn_bk = get_connection(readonly=True)
            c = conn_bk.cursor()
            c.execute("SELECT count(*) FROM conversations")
            report["backup_conversations"] = c.fetchone()[0]
            c.execute("SELECT count(*) FROM messages")
            report["backup_messages"] = c.fetchone()[0]
            conn_bk.close()
        except Exception:
            pass

    # 4. Diagnosticar anomalías
    if report["physical_conversations"] > 0 and report["vscdb_index_count"] < report["physical_conversations"]:
        diff = report["physical_conversations"] - report["vscdb_index_count"]
        report["issues"].append(f"Desfase detectado: Hay {report['physical_conversations']} conversaciones físicas pero solo {report['vscdb_index_count']} visibles en Antigravity IDE (faltan {diff}).")
        report["recommendations"].append("Ejecuta 'python cli.py restore-all' para reinyectar todas las conversaciones en la barra lateral.")

    if not report["backup_db_exists"] or report["backup_conversations"] == 0:
        report["recommendations"].append("Ejecuta 'python cli.py sync' para crear tu primer respaldo local inmutable.")

    return report

def print_doctor_report():
    print("\n============================================================")
    print("   ANTIGRAVITY CHAT GUARDIAN - DIAGNOSTICO DE SALUD")
    print("============================================================")
    r = run_doctor_diagnostics()

    print(f"[*] Version de Python:             {r['python_version']}")
    print(f"[*] Antigravity IDE activo:         {'SI' if r['ide_running'] else 'NO'}")
    print(f"[*] Conversaciones en disco:       {r['physical_conversations']} archivos")
    print(f"[*] Transcripciones en Brain:       {r['brain_conversations']} carpetas")
    print(f"[*] Sesiones en state.vscdb:       {r['vscdb_index_count']} visibles")
    print(f"[*] Trayectorias mapeadas:         {r['vscdb_trajectory_count']} proyectos")
    print(f"[*] Respaldo local seguro:          {r['backup_conversations']} chats ({r['backup_messages']:,} mensajes)")
    print("------------------------------------------------------------")

    if r["issues"]:
        print("\n[!] ADVERTENCIAS DETECTADAS:")
        for iss in r["issues"]:
            print(f"    - {iss}")

    if r["recommendations"]:
        print("\n[V] RECOMENDACIONES:")
        for rec in r["recommendations"]:
            print(f"    - {rec}")
    else:
        print("\n[OK] El sistema esta en perfecto estado de integridad y sincronizacion.")

    print("============================================================\n")
