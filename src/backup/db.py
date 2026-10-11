"""
Gestión de la base de datos SQLite de respaldo centralizado: antigravity_history.db
"""

import os
import sqlite3
from typing import Dict, List, Optional, Any

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backups")
DB_PATH = os.path.join(DB_DIR, "antigravity_history.db")

def init_backup_db() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT,
            updated_at TEXT,
            workspace_uri TEXT,
            project_name TEXT,
            step_count INTEGER DEFAULT 0,
            user_message_count INTEGER DEFAULT 0,
            file_type TEXT,
            source_file_path TEXT,
            transcript_path TEXT,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            step_index INTEGER,
            sender TEXT,
            msg_type TEXT,
            timestamp TEXT,
            content TEXT,
            tool_calls_json TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_conv_project ON conversations(project_name);
        CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at);
        CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender);
        """)
        
    return conn

def get_connection(readonly: bool = False) -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(DB_PATH):
        init_backup_db()
    if readonly:
        return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return sqlite3.connect(DB_PATH)

def save_conversation(conv_data: Dict[str, Any], messages: List[Dict[str, Any]]):
    """Guarda o actualiza una conversación y sus mensajes de manera transaccional."""
    conn = get_connection(readonly=False)
    try:
        with conn:
            conn.execute("""
            INSERT INTO conversations (
                conversation_id, title, created_at, updated_at, workspace_uri,
                project_name, step_count, user_message_count, file_type,
                source_file_path, transcript_path, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                title = excluded.title,
                updated_at = excluded.updated_at,
                workspace_uri = CASE WHEN excluded.workspace_uri != '' THEN excluded.workspace_uri ELSE conversations.workspace_uri END,
                project_name = CASE WHEN excluded.project_name != 'General' THEN excluded.project_name ELSE conversations.project_name END,
                step_count = excluded.step_count,
                user_message_count = excluded.user_message_count,
                transcript_path = excluded.transcript_path;
            """, (
                conv_data["conversation_id"],
                conv_data.get("title", "Conversación sin título"),
                conv_data.get("created_at", ""),
                conv_data.get("updated_at", ""),
                conv_data.get("workspace_uri", ""),
                conv_data.get("project_name", "General"),
                conv_data.get("step_count", 0),
                conv_data.get("user_message_count", 0),
                conv_data.get("file_type", "sqlite_db"),
                conv_data.get("source_file_path", ""),
                conv_data.get("transcript_path", ""),
                conv_data.get("status", "active")
            ))

            if messages:
                # Reemplazar mensajes de forma consistente
                conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_data["conversation_id"],))
                insert_msgs = [
                    (
                        conv_data["conversation_id"],
                        m.get("step_index", 0),
                        m.get("sender", "unknown"),
                        m.get("msg_type", "message"),
                        m.get("timestamp", ""),
                        m.get("content", ""),
                        m.get("tool_calls_json", "")
                    )
                    for m in messages
                ]
                conn.executemany("""
                INSERT INTO messages (
                    conversation_id, step_index, sender, msg_type,
                    timestamp, content, tool_calls_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """, insert_msgs)
    finally:
        conn.close()
