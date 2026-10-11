# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-11

### Added
- **Core Recovery Engine:** Protobuf Wire Format parser & writer for `antigravityUnifiedStateSync.trajectorySummaries` and JSON encoder for `chat.ChatSessionStore.index`.
- **Bulk Restorer (`cli.py restore-all`):** Automated recovery and project mapping for 100+ conversations into Antigravity IDE sidebar.
- **Smart Conditional Watcher (`src/backup/watcher.py`):** Ctypes-based Windows process monitor with 0% CPU idle consumption and real-time capture when Antigravity IDE is open.
- **Auto-Immunization:** Automatic repair of `state.vscdb` on IDE termination to prevent session wipes.
- **System Doctor (`cli.py doctor`):** Interactive health check of physical storage, brain logs, and IDE state.
- **Multi-format Exporter (`cli.py export`):** Export full conversation transcripts to Markdown and JSON.
- **Local Web Viewer & Control Hub:** Modern dark-mode SPA at `http://127.0.0.1:7890`.
- **1-Click Windows Launchers:** `setup.bat`, `restaurar_historial_antigravity.bat`, `iniciar_vigilante_silencioso.vbs`, `run_hub.bat`.
