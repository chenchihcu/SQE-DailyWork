## 2026-06-07T05:12:08Z
You are the Worker agent for the SQE DailyWork database warning resolution task.
Your working directory is: c:\Users\user\Documents\SQE DailyWork\.agents\worker_implementation

Your task is to implement the approved changes in `implementation_plan.md` to resolve 'ResourceWarning: unclosed database' warnings:

1. In `src/database/connection.py`, declare:
```python
class ClosingConnection(sqlite3.Connection):
    """A sqlite3.Connection subclass that guarantees close() is called upon exiting context."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()
```
And use it inside `get_connection` via the `factory` parameter:
```python
def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create SQLite connection with row mapping and foreign key support."""
    target = db_path or DB_PATH
    conn = sqlite3.connect(target, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

2. In `src/database/migration.py`, refactor `migrate_legacy_data_if_needed` to use explicit `try...finally` blocks instead of `with sqlite3.connect(v2_path)` and `with sqlite3.connect(legacy_path)`, ensuring `.close()` is called on both connections in their respective `finally` blocks.

3. In `src/database/ncr_migration.py`, refactor `migrate_ncr_data_once` to initialize `src_conn = None`, wrap the connection and migration processes in a `try...finally` block, and call `src_conn.close()` inside the `finally` block if it is not None.

4. Run `python -Wd -m pytest` or `.\scripts\verify.ps1` to verify all 278 unit tests pass without any `ResourceWarning: unclosed database connection`. Capture the verification output.

5. Update the task list in `C:\Users\user\.gemini\antigravity\brain\c57a1efd-75c3-4082-b51b-c17c248050ae\task.md` to mark completed tasks.

6. Write a detailed handoff report to `c:\Users\user\Documents\SQE DailyWork\.agents\worker_implementation\handoff.md` and send a completion message to the orchestrator (ID: c57a1efd-75c3-4082-b51b-c17c248050ae).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
