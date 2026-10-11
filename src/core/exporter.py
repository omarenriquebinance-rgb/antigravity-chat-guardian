"""
Módulo de Exportación Multiformato (Markdown, HTML, JSON) para conversaciones de Antigravity IDE.
Permite respaldar, compartir y documentar interacciones con agentes.
"""

import os
import json
import html
from typing import Dict, Any, Optional
from datetime import datetime

from src.backup.db import get_connection

def export_conversation_to_markdown(conv_id: str, out_file: Optional[str] = None) -> str:
    conn = get_connection(readonly=True)
    c = conn.cursor()
    c.execute("SELECT conversation_id, title, project_name, workspace_uri, created_at, updated_at FROM conversations WHERE conversation_id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise ValueError(f"Conversación {conv_id} no encontrada en la base de datos.")

    c.execute("SELECT step_index, sender, msg_type, timestamp, content, tool_calls_json FROM messages WHERE conversation_id = ? ORDER BY step_index ASC", (conv_id,))
    messages = c.fetchall()
    conn.close()

    cid, title, proj, ws_uri, c_at, u_at = conv

    md_lines = [
        f"# {title or 'Conversación Antigravity'}\n",
        f"- **ID:** `{cid}`",
        f"- **Proyecto:** `{proj}`",
        f"- **Workspace:** `{ws_uri}`",
        f"- **Fecha Creación:** {c_at}",
        f"- **Última Actualización:** {u_at}\n",
        "---\n"
    ]

    for step, sender, msg_type, msg_time, content, tool_calls_json in messages:
        display_role = "👤 Usuario" if sender == "USER" else ("🤖 Agente Antigravity" if sender == "MODEL" else f"⚙️ {sender}")
        md_lines.append(f"### {display_role} (Paso {step})")
        if msg_time:
            md_lines.append(f"*{msg_time}*\n")
        
        if content:
            md_lines.append(content.strip() + "\n")

        if tool_calls_json:
            try:
                tc = json.loads(tool_calls_json)
                if tc:
                    md_lines.append("<details><summary>🛠️ Herramientas ejecutadas</summary>\n")
                    md_lines.append("```json\n" + json.dumps(tc, indent=2, ensure_ascii=False) + "\n```\n</details>\n")
            except Exception:
                pass
        
        md_lines.append("\n---\n")

    result = "\n".join(md_lines)
    if out_file:
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(result)
    return result

def export_conversation_to_json(conv_id: str, out_file: Optional[str] = None) -> str:
    conn = get_connection(readonly=True)
    c = conn.cursor()
    c.execute("SELECT conversation_id, title, project_name, workspace_uri, created_at, updated_at FROM conversations WHERE conversation_id = ?", (conv_id,))
    conv = c.fetchone()
    if not conv:
        conn.close()
        raise ValueError(f"Conversación {conv_id} no encontrada.")

    c.execute("SELECT step_index, sender, msg_type, timestamp, content, tool_calls_json FROM messages WHERE conversation_id = ? ORDER BY step_index ASC", (conv_id,))
    messages = c.fetchall()
    conn.close()

    cid, title, proj, ws_uri, c_at, u_at = conv
    data = {
        "conversation_id": cid,
        "title": title,
        "project_name": proj,
        "workspace_uri": ws_uri,
        "created_at": c_at,
        "updated_at": u_at,
        "messages": []
    }

    for step, sender, msg_type, msg_time, content, tool_calls_json in messages:
        tc = None
        if tool_calls_json:
            try:
                tc = json.loads(tool_calls_json)
            except Exception:
                tc = tool_calls_json
        data["messages"].append({
            "step_index": step,
            "sender": sender,
            "msg_type": msg_type,
            "timestamp": msg_time,
            "content": content,
            "tool_calls": tc
        })

    result = json.dumps(data, indent=2, ensure_ascii=False)
    if out_file:
        os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(result)
    return result
