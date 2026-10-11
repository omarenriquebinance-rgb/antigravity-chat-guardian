"""
Servicio Inteligente en Segundo Plano (Smart Antigravity Live Daemon).
Detecta automáticamente la apertura y cierre de Antigravity IDE mediante llamadas nativas
a la API de Windows (ctypes, <3ms de tiempo de verificación).

Comportamiento:
- Cuando Antigravity está ABIERTO: Activa monitoreo de alta frecuencia (cada 2s),
  capturando en tiempo real cada mensaje, respuesta y tool call.
- Cuando Antigravity se CIERRA: Ejecuta un volcado final atómico y re-inmuniza
  el índice state.vscdb para evitar que los chats desaparezcan de la barra lateral.
- Cuando Antigravity está CERRADO: Modo de bajo consumo (reposo inteligente).
"""

import os
import sys
import time
import json
import sqlite3
import ctypes
import ctypes.wintypes
from datetime import datetime
from typing import Dict, Optional

# Añadir raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.paths import get_antigravity_dirs
from src.backup.extractor import sync_single_conversation, sync_all_conversations
from src.recovery.restorer import backup_state_vscdb
from src.backup.db import get_connection

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backups", "watcher.log")

def log_event(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass

def is_antigravity_running_fast() -> bool:
    """Verificación ultrarrápida nativa de Windows con EnumProcesses (<3ms, 0% CPU)."""
    try:
        EnumProcesses = ctypes.windll.psapi.EnumProcesses
        OpenProcess = ctypes.windll.kernel32.OpenProcess
        GetModuleBaseNameW = ctypes.windll.psapi.GetModuleBaseNameW
        CloseHandle = ctypes.windll.kernel32.CloseHandle

        pids = (ctypes.wintypes.DWORD * 1024)()
        cb = ctypes.wintypes.DWORD()
        EnumProcesses(ctypes.byref(pids), ctypes.sizeof(pids), ctypes.byref(cb))
        count = cb.value // ctypes.sizeof(ctypes.wintypes.DWORD)

        for i in range(count):
            pid = pids[i]
            h = OpenProcess(0x0410, False, pid)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
            if h:
                buf = ctypes.create_unicode_buffer(260)
                GetModuleBaseNameW(h, 0, buf, ctypes.sizeof(buf) // 2)
                CloseHandle(h)
                name = buf.value.lower()
                if "antigravity" in name and name.endswith(".exe"):
                    return True
        return False
    except Exception:
        # Fallback multiplataforma si ctypes falla (macOS, Linux y Windows)
        import subprocess
        try:
            if sys.platform in ("darwin", "linux"):
                res = subprocess.run(["pgrep", "-f", "Antigravity"], capture_output=True, text=True)
                return res.returncode == 0
            else:
                res = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq Antigravity IDE.exe"], capture_output=True, text=True)
                return "antigravity" in res.stdout.lower()
        except Exception:
            return False

def auto_repair_state_indices():
    """
    Auto-inmunización: Si Antigravity al cerrarse vació chat.ChatSessionStore.index,
    re-inyecta las conversaciones del respaldo en state.vscdb para que al reabrir el IDE
    sigan visibles en la barra lateral.
    """
    paths = get_antigravity_dirs()
    state_vscdb = paths["state_vscdb"]
    if not os.path.exists(state_vscdb):
        return

    try:
        conn = sqlite3.connect(state_vscdb)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM ItemTable WHERE key = 'chat.ChatSessionStore.index'")
        row = cursor.fetchone()
        
        index_data = {}
        if row and row[0]:
            try:
                index_data = json.loads(row[0])
            except Exception:
                index_data = {}
                
        entries = index_data.get("entries", {})
        
        # Si el índice quedó vacío o con muy pocos chats frente al respaldo:
        conn_bk = get_connection(readonly=True)
        c_bk = conn_bk.cursor()
        c_bk.execute("SELECT conversation_id, title, updated_at FROM conversations ORDER BY updated_at DESC LIMIT 30")
        recent_chats = c_bk.fetchall()
        conn_bk.close()

        if len(entries) < len(recent_chats):
            log_event(f"[*] Reparando índice state.vscdb (tenía {len(entries)} sesiones, inyectando recientes)...")
            backup_state_vscdb(state_vscdb)
            
            if "entries" not in index_data:
                index_data = {"version": 1, "entries": {}}

            ms_now = int(time.time() * 1000)
            for cid, title, up_time in recent_chats:
                if cid not in index_data["entries"]:
                    index_data["entries"][cid] = {
                        "sessionId": cid,
                        "creationDate": ms_now,
                        "customTitle": title or "Chat Recuperado",
                        "isImported": False
                    }

            with conn:
                conn.execute("""
                INSERT INTO ItemTable (key, value) VALUES ('chat.ChatSessionStore.index', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (json.dumps(index_data, ensure_ascii=False),))
                
            log_event(f"[✓] Índice auto-reparado con éxito. {len(index_data['entries'])} conversaciones preservadas.")
        conn.close()
    except Exception as e:
        log_event(f"[!] Error durante auto-reparación de índices: {e}")

class SmartAntigravityWatcher:
    def __init__(self, active_interval: float = 2.0, idle_interval: float = 5.0):
        self.active_interval = active_interval
        self.idle_interval = idle_interval
        self.paths = get_antigravity_dirs()
        self.conv_dir = self.paths["conversations"]
        self.brain_dir = self.paths["brain"]
        self.known_mtimes: Dict[str, float] = {}
        self.was_running = False
        self.running = True
        self._init_baseline_mtimes()

    def _init_baseline_mtimes(self):
        """Carga inicial instantánea (<10ms) de las marcas de tiempo para evitar demoras."""
        if not os.path.exists(self.conv_dir):
            return
        try:
            # Obtener IDs ya registrados en base de datos local
            conn = get_connection(readonly=True)
            c = conn.cursor()
            c.execute("SELECT conversation_id FROM conversations")
            existing_db_ids = set(r[0] for r in c.fetchall())
            conn.close()

            files = os.listdir(self.conv_dir)
            for f in files:
                if f.endswith(".db") or f.endswith(".pb"):
                    base_id = f[:-3]
                    if len(base_id) == 36 and base_id.count("-") == 4:
                        if base_id in existing_db_ids:
                            fp = os.path.join(self.conv_dir, f)
                            t_path = os.path.join(self.brain_dir, base_id, ".system_generated", "logs", "transcript_full.jsonl")
                            mtime = os.path.getmtime(fp) if os.path.exists(fp) else 0.0
                            t_mtime = os.path.getmtime(t_path) if os.path.exists(t_path) else 0.0
                            self.known_mtimes[base_id] = max(mtime, t_mtime)
        except Exception:
            pass

    def scan_active_conversations(self) -> int:
        """Escanea cambios en las conversaciones activas."""
        if not os.path.exists(self.conv_dir):
            return 0

        synced = 0
        try:
            files = os.listdir(self.conv_dir)
        except Exception:
            return 0

        for f in files:
            if f.endswith(".db") or f.endswith(".pb"):
                base_id = f[:-3]
                if len(base_id) == 36 and base_id.count("-") == 4:
                    fp = os.path.join(self.conv_dir, f)
                    try:
                        mtime = os.path.getmtime(fp)
                        t_path = os.path.join(self.brain_dir, base_id, ".system_generated", "logs", "transcript_full.jsonl")
                        t_mtime = os.path.getmtime(t_path) if os.path.exists(t_path) else 0.0
                        comp_mtime = max(mtime, t_mtime)

                        if self.known_mtimes.get(base_id) != comp_mtime:
                            if sync_single_conversation(base_id, self.paths):
                                synced += 1
                            self.known_mtimes[base_id] = comp_mtime
                    except Exception:
                        pass
        return synced

    def run(self):
        log_event("=" * 60)
        log_event("INICIANDO SERVICIO INTELIGENTE DE RESPALDO CONTINUO ANTIGRAVITY")
        log_event("=" * 60)

        # Sincronización inicial rápida
        init_synced = self.scan_active_conversations()
        if init_synced > 0:
            log_event(f"[+] Sincronización inicial: {init_synced} conversaciones verificadas.")

        while self.running:
            try:
                is_open = is_antigravity_running_fast()

                if is_open:
                    if not self.was_running:
                        log_event("[🟢] ANTIGRAVITY IDE DETECTADO ABIERTO. Activando modo de captura continua en tiempo real.")
                        self.was_running = True

                    # Monitoreo activo
                    changes = self.scan_active_conversations()
                    if changes > 0:
                        log_event(f"[💾] Respaldo en vivo: {changes} conversación(es) actualizada(s) en tiempo real.")

                    time.sleep(self.active_interval)
                else:
                    if self.was_running:
                        log_event("[🔴] ANTIGRAVITY IDE SE HA CERRADO.")
                        log_event("[*] Ejecutando sincronización atómica final de cierre...")
                        time.sleep(1.5)  # Esperar liberación de bloqueos de archivo
                        self.scan_active_conversations()
                        # Auto-inmunizar índice de la base de datos
                        auto_repair_state_indices()
                        self.was_running = False
                        log_event("[💤] Entrando en modo de reposo inteligente (esperando próxima apertura)...")

                    time.sleep(self.idle_interval)

            except KeyboardInterrupt:
                log_event("[*] Deteniendo servicio por solicitud del usuario.")
                self.running = False
                break
            except Exception as e:
                log_event(f"[!] Excepción en ciclo del servicio: {e}")
                time.sleep(self.idle_interval)

    def start(self):
        self.run()

AntigravityLiveWatcher = SmartAntigravityWatcher

if __name__ == "__main__":
    watcher = SmartAntigravityWatcher()
    watcher.run()
