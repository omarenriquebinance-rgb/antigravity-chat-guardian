# Contributing to Antigravity Chat Guardian

Thank you for your interest in improving Antigravity Chat Guardian!

## Development Guidelines

1. **Zero External Dependencies:**
   - Keep the core engine dependent ONLY on the Python Standard Library (`sqlite3`, `ctypes`, `http.server`, `urllib`, `json`, `datetime`, etc.) to ensure instant execution without virtual environment setup.

2. **Windows Compatibility:**
   - Ensure file paths, process handlers, and PowerShell/Batch scripts support Windows 10 and Windows 11 properly.
   - Use `ctypes` and native Win32 APIs where ultra-fast performance (<5ms) is required.

3. **Non-Destructive Operations:**
   - Always create a backup of `state.vscdb` before writing or updating any keys.

## Submitting Pull Requests

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.
