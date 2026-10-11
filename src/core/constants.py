"""
Constants shared across all recovery modules.
"""

from __future__ import annotations

# ==============================================================================
# VERSION & IDENTITY
# ==============================================================================
VERSION = "1.0.0"
APP_NAME = "Antigravity Chat Guardian"
APP_URL = "https://github.com/omarenriquebinance-rgb/antigravity-chat-guardian"

# ==============================================================================
# DATABASE SETTINGS
# ==============================================================================
DB_FILENAME = "state.vscdb"
STORAGE_FILENAME = "storage.json"
MIN_PYTHON_VERSION = (3, 10)

# ==============================================================================
# TUNING PARAMETERS
# ==============================================================================
BACKUP_PREFIX = "guardian_recovery"

# Prefix of auto-generated fallback titles; db_scanner treats titles starting
# with this as placeholders (they round-trip instead of masking real titles).
PLACEHOLDER_TITLE_PREFIX = "Conversation"

# ==============================================================================
# DATABASE KEYS
# ==============================================================================
PB_KEY = "antigravityUnifiedStateSync.trajectorySummaries"
JSON_KEY = "chat.ChatSessionStore.index"
