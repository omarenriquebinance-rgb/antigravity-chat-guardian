"""
Módulo de resolución de rutas y utilidades del entorno de Google Antigravity IDE en Windows.
"""

import os
import sys
import urllib.parse
from typing import Dict, List, Optional

def get_home_dir() -> str:
    return os.path.expanduser("~")

def get_appdata_dir() -> str:
    if sys.platform == "darwin":
        # macOS: ~/Library/Application Support
        return os.path.join(get_home_dir(), "Library", "Application Support")
    elif sys.platform.startswith("linux"):
        # Linux: ~/.config
        return os.environ.get("XDG_CONFIG_HOME", os.path.join(get_home_dir(), ".config"))
    # Windows
    return os.environ.get("APPDATA", os.path.join(get_home_dir(), "AppData", "Roaming"))

def get_antigravity_dirs() -> Dict[str, str]:
    home = get_home_dir()
    appdata = get_appdata_dir()
    
    # Directorio moderno (v2.x)
    ide_dir = os.path.join(home, ".gemini", "antigravity-ide")
    # Directorio heredado (v1.x)
    legacy_dir = os.path.join(home, ".gemini", "antigravity")
    
    active_gemini_dir = ide_dir if os.path.exists(ide_dir) else legacy_dir
    
    return {
        "gemini_ide": ide_dir,
        "gemini_legacy": legacy_dir,
        "active_gemini": active_gemini_dir,
        "conversations": os.path.join(active_gemini_dir, "conversations"),
        "brain": os.path.join(active_gemini_dir, "brain"),
        "global_storage_dir": os.path.join(appdata, "Antigravity IDE", "User", "globalStorage"),
        "state_vscdb": os.path.join(appdata, "Antigravity IDE", "User", "globalStorage", "state.vscdb"),
        "workspace_storage": os.path.join(appdata, "Antigravity IDE", "User", "workspaceStorage"),
        "legacy_state_vscdb": os.path.join(appdata, "Antigravity", "User", "globalStorage", "state.vscdb")
    }

def normalize_workspace_uri(path_or_uri: str) -> str:
    """
    Normaliza rutas locales y URIs al formato canónico de Antigravity IDE.
    Ej: 'd:\\ARREGLO-ANTIGAVITY' -> 'file:///d:/ARREGLO-ANTIGAVITY'
    Ej macOS/Linux: '/Users/username/my-project' -> 'file:///Users/username/my-project'
    """
    if not path_or_uri:
        return ""
    
    p = path_or_uri.strip()
    if p.startswith("file:///"):
        # Decodificar %3A si existe para estandarizar
        p = urllib.parse.unquote(p)
        p = p.replace("\\", "/")
        return p
    
    # Si es ruta Windows estándar tipo D:\carpeta
    p = p.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = f"file:///{p[0].lower()}:{p[2:]}"
    elif p.startswith("/"):
        p = f"file://{p}"
    elif not p.startswith("file://"):
        p = f"file:///{p.lstrip('/')}"
        
    return p

def extract_project_name_from_uri(uri: str) -> str:
    """Extrae el nombre limpio de la carpeta del proyecto a partir de un URI."""
    if not uri:
        return "General"
    clean = urllib.parse.unquote(uri).rstrip("/\\")
    parts = [p for p in clean.replace("\\", "/").split("/") if p and not p.endswith(":") and p != "file:"]
    if parts:
        return parts[-1]
    return "General"
