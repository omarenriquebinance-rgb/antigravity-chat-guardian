"""
Servidor HTTP local ultraligero y API REST para el Centro de Control y Visor de Chats.
Basado 100% en bibliotecas estándar de Python (http.server, json, sqlite3).
"""

import os
import sys
import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

from src.core.paths import get_antigravity_dirs, normalize_workspace_uri, extract_project_name_from_uri
from src.backup.db import get_connection, DB_PATH
from src.backup.extractor import sync_all_conversations, sync_single_conversation

PORT = 7890
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

class AntigravityHubHandler(BaseHTTPRequestHandler):
    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, file_path: str, content_type: str):
        if not os.path.exists(file_path):
            self.send_error(404, "File not found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Rutas estáticas Web
        if path == "/" or path == "/index.html":
            self.send_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path == "/styles.css":
            self.send_file(os.path.join(WEB_DIR, "styles.css"), "text/css; charset=utf-8")
            return
        elif path == "/app.js":
            self.send_file(os.path.join(WEB_DIR, "app.js"), "application/javascript; charset=utf-8")
            return

        # API: Lista de conversaciones
        if path == "/api/conversations":
            project = query.get("project", [""])[0]
            search = query.get("q", [""])[0]
            
            conn = get_connection(readonly=True)
            try:
                cursor = conn.cursor()
                sql = """
                SELECT conversation_id, title, created_at, updated_at,
                       workspace_uri, project_name, step_count, user_message_count, file_type
                FROM conversations
                WHERE 1=1
                """
                params = []
                if project:
                    sql += " AND project_name = ?"
                    params.append(project)
                if search:
                    sql += " AND (title LIKE ? OR conversation_id LIKE ?)"
                    params.extend([f"%{search}%", f"%{search}%"])

                sql += " ORDER BY updated_at DESC LIMIT 100"
                cursor.execute(sql, params)
                
                rows = cursor.fetchall()
                convs = [
                    {
                        "conversation_id": r[0],
                        "title": r[1],
                        "created_at": r[2],
                        "updated_at": r[3],
                        "workspace_uri": r[4],
                        "project_name": r[5],
                        "step_count": r[6],
                        "user_message_count": r[7],
                        "file_type": r[8]
                    }
                    for r in rows
                ]
                self.send_json(convs)
            finally:
                conn.close()
            return

        # API: Conversación individual con mensajes
        if path.startswith("/api/conversations/"):
            conv_id = path[len("/api/conversations/"):].strip()
            conn = get_connection(readonly=True)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT conversation_id, title, created_at, updated_at,
                       workspace_uri, project_name, step_count, user_message_count
                FROM conversations WHERE conversation_id = ?
                """, (conv_id,))
                conv_row = cursor.fetchone()
                if not conv_row:
                    self.send_json({"error": "Conversación no encontrada"}, status=404)
                    return

                cursor.execute("""
                SELECT step_index, sender, msg_type, timestamp, content, tool_calls_json
                FROM messages WHERE conversation_id = ?
                ORDER BY step_index ASC
                """, (conv_id,))
                msg_rows = cursor.fetchall()
                
                messages = [
                    {
                        "step_index": m[0],
                        "sender": m[1],
                        "msg_type": m[2],
                        "timestamp": m[3],
                        "content": m[4],
                        "tool_calls": json.loads(m[5]) if m[5] else []
                    }
                    for m in msg_rows
                ]

                data = {
                    "conversation_id": conv_row[0],
                    "title": conv_row[1],
                    "created_at": conv_row[2],
                    "updated_at": conv_row[3],
                    "workspace_uri": conv_row[4],
                    "project_name": conv_row[5],
                    "step_count": conv_row[6],
                    "user_message_count": conv_row[7],
                    "messages": messages
                }
                self.send_json(data)
            finally:
                conn.close()
            return

        # API: Proyectos
        if path == "/api/projects":
            conn = get_connection(readonly=True)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT project_name, count(*) as count
                FROM conversations
                GROUP BY project_name
                ORDER BY count DESC
                """)
                projects = [{"name": r[0], "count": r[1]} for r in cursor.fetchall()]
                self.send_json(projects)
            finally:
                conn.close()
            return

        # API: Exportar en Markdown
        if path.startswith("/api/export/"):
            conv_id = path[len("/api/export/"):].strip()
            conn = get_connection(readonly=True)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT title, project_name, created_at FROM conversations WHERE conversation_id = ?", (conv_id,))
                c_row = cursor.fetchone()
                if not c_row:
                    self.send_json({"error": "No encontrada"}, status=404)
                    return

                cursor.execute("SELECT sender, timestamp, content FROM messages WHERE conversation_id = ? ORDER BY step_index ASC", (conv_id,))
                messages = cursor.fetchall()
                
                md = f"# {c_row[0]}\n"
                md += f"**Proyecto:** {c_row[1]} | **Fecha:** {c_row[2]} | **ID:** `{conv_id}`\n\n---\n\n"
                for sender, ts, content in messages:
                    role_title = "👤 **Usuario**" if sender == "user" else ("🤖 **Agente Antigravity**" if sender == "agent" else f"⚙️ *{sender}*")
                    md += f"### {role_title} ({ts})\n\n{content}\n\n---\n\n"

                body = md.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="chat_{conv_id[:8]}.md"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            finally:
                conn.close()

        # API: Status
        if path == "/api/status":
            conn = get_connection(readonly=True)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM conversations")
                total_c = cursor.fetchone()[0]
                cursor.execute("SELECT count(*) FROM messages")
                total_m = cursor.fetchone()[0]
                paths = get_antigravity_dirs()
                self.send_json({
                    "status": "online",
                    "total_conversations": total_c,
                    "total_messages": total_m,
                    "backup_db_path": DB_PATH,
                    "active_gemini_dir": paths["active_gemini"]
                })
            finally:
                conn.close()
            return

        self.send_error(404, "Endpoint no encontrado")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/sync":
            count = sync_all_conversations()
            self.send_json({"success": True, "synced": count})
            return

        if path == "/api/restore":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body) if body else {}
            conv_id = data.get("conversation_id")
            target_uri = data.get("target_workspace_uri")

            if not conv_id:
                self.send_json({"success": False, "error": "ID de conversación requerido"}, status=400)
                return

            from src.recovery.restorer import rebind_conversation_to_workspace
            success, msg = rebind_conversation_to_workspace(conv_id, target_uri)
            self.send_json({"success": success, "message": msg})
            return

        self.send_error(404, "Endpoint POST no encontrado")

def run_server(port: int = PORT):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, AntigravityHubHandler)
    print(f"\n========================================================")
    print(f"  ANTIGRAVITY CHAT PERSISTENCE & RECOVERY HUB ACTIVO")
    print(f"  URL: http://127.0.0.1:{port}")
    print(f"========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Servidor apagado.")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
