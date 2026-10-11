"""
Extractor de conversaciones y transcripciones desde el almacenamiento nativo de Antigravity.
"""

import os
import re
import json
import sqlite3
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from src.core.paths import (
    get_antigravity_dirs,
    normalize_workspace_uri,
    extract_project_name_from_uri
)
from src.backup.db import save_conversation

def extract_title_from_text(text: str, default: str = "Nueva Conversación") -> str:
    """Extrae un título legible a partir del primer mensaje del usuario."""
    if not text:
        return default
    clean = re.sub(r'<USER_REQUEST>|</USER_REQUEST>|<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>', '', text).strip()
    clean = re.sub(r'^[#/ \t\r\n*]+', '', clean).strip()
    lines = [line.strip() for line in clean.splitlines() if line.strip() and not line.strip().startswith("```")]
    if lines:
        first_line = lines[0]
        if len(first_line) > 70:
            return first_line[:67] + "..."
        return first_line
    return default

def parse_transcript_jsonl(transcript_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Parsea el archivo transcript_full.jsonl de Antigravity brain."""
    messages = []
    metadata = {
        "step_count": 0,
        "user_message_count": 0,
        "created_at": "",
        "updated_at": "",
        "title": ""
    }
    
    if not os.path.exists(transcript_path):
        return messages, metadata
        
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                
                step_idx = entry.get("step_index", len(messages))
                msg_type = entry.get("type", "message")
                source = entry.get("source", "")
                created_at = entry.get("created_at", "")
                content = entry.get("content", "")
                tool_calls = entry.get("tool_calls", [])
                
                if not metadata["created_at"] and created_at:
                    metadata["created_at"] = created_at
                if created_at:
                    metadata["updated_at"] = created_at
                
                sender = "system"
                if msg_type == "USER_INPUT" or "USER" in source:
                    sender = "user"
                    metadata["user_message_count"] += 1
                    if not metadata["title"]:
                        metadata["title"] = extract_title_from_text(content)
                elif msg_type == "PLANNER_RESPONSE" or "MODEL" in source or "AGENT" in source:
                    sender = "agent"
                elif "TOOL" in msg_type or "TOOL" in source:
                    sender = "tool"
                
                text_content = ""
                if isinstance(content, str):
                    text_content = content
                elif isinstance(content, dict):
                    text_content = content.get("text", json.dumps(content, ensure_ascii=False))
                elif isinstance(content, list):
                    text_content = "\n".join([str(item) for item in content])
                    
                messages.append({
                    "step_index": step_idx,
                    "sender": sender,
                    "msg_type": msg_type,
                    "timestamp": created_at,
                    "content": text_content,
                    "tool_calls_json": json.dumps(tool_calls, ensure_ascii=False) if tool_calls else ""
                })
                
        metadata["step_count"] = len(messages)
    except Exception as e:
        print(f"Error procesando transcripción {transcript_path}: {e}")
        
    return messages, metadata

def extract_workspace_from_db(db_path: str) -> Tuple[str, str]:
    """Extrae el URI del workspace y título desde el SQLite de la conversación."""
    uri = ""
    title = ""
    if not os.path.exists(db_path):
        return uri, title
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        c = conn.cursor()
        
        try:
            c.execute("SELECT data FROM trajectory_metadata_blob LIMIT 1")
            row = c.fetchone()
            if row and row[0]:
                blob = row[0]
                matches = re.findall(rb'file:///[a-zA-Z0-9%_\-\.\/\:]+', blob)
                for m in matches:
                    u = m.decode('utf-8', errors='ignore').rstrip('z').rstrip(':')
                    if len(u) > len("file:///d:"):
                        uri = u
                        break
                if not uri and matches:
                    uri = matches[0].decode('utf-8', errors='ignore')
        except Exception:
            pass
            
        conn.close()
    except Exception:
        pass
        
    return uri, title

def sync_single_conversation(conv_id: str, paths: Optional[Dict[str, str]] = None) -> bool:
    """Extrae y respalda una única conversación por UUID."""
    if not paths:
        paths = get_antigravity_dirs()
        
    conv_dir = paths["conversations"]
    brain_dir = paths["brain"]
    
    db_file = os.path.join(conv_dir, f"{conv_id}.db")
    pb_file = os.path.join(conv_dir, f"{conv_id}.pb")
    
    file_type = "sqlite_db" if os.path.exists(db_file) else ("protobuf_pb" if os.path.exists(pb_file) else "unknown")
    source_path = db_file if file_type == "sqlite_db" else pb_file
    
    if not os.path.exists(source_path):
        return False
        
    transcript_full = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript_full.jsonl")
    transcript_short = os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")
    transcript_file = transcript_full if os.path.exists(transcript_full) else (transcript_short if os.path.exists(transcript_short) else "")
    
    messages = []
    metadata = {}
    if transcript_file:
        messages, metadata = parse_transcript_jsonl(transcript_file)
        
    db_uri, db_title = extract_workspace_from_db(db_file) if file_type == "sqlite_db" else ("", "")
    
    workspace_uri = normalize_workspace_uri(db_uri)
    project_name = extract_project_name_from_uri(workspace_uri)
    
    title = metadata.get("title") or db_title
    if not title:
        mtime = os.path.getmtime(source_path)
        date_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
        title = f"Conversación ({date_str}) {conv_id[:8]}"
        
    conv_data = {
        "conversation_id": conv_id,
        "title": title,
        "created_at": metadata.get("created_at") or datetime.fromtimestamp(os.path.getctime(source_path)).isoformat(),
        "updated_at": metadata.get("updated_at") or datetime.fromtimestamp(os.path.getmtime(source_path)).isoformat(),
        "workspace_uri": workspace_uri,
        "project_name": project_name,
        "step_count": metadata.get("step_count", 0),
        "user_message_count": metadata.get("user_message_count", 0),
        "file_type": file_type,
        "source_file_path": source_path,
        "transcript_path": transcript_file,
        "status": "active"
    }
    
    save_conversation(conv_data, messages)
    return True

def sync_all_conversations() -> int:
    """Escanea y sincroniza todas las conversaciones disponibles en Antigravity."""
    paths = get_antigravity_dirs()
    conv_dir = paths["conversations"]
    if not os.path.exists(conv_dir):
        return 0
        
    count = 0
    conv_files = os.listdir(conv_dir)
    uuids = set()
    for f in conv_files:
        if f.endswith(".db") or f.endswith(".pb"):
            base = f[:-3]
            if len(base) == 36 and base.count("-") == 4:
                uuids.add(base)
                
    for cid in uuids:
        try:
            if sync_single_conversation(cid, paths):
                count += 1
        except Exception as e:
            pass
            
    return count
