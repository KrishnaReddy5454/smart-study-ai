import hashlib
import hmac
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = "study_app.db"


def _hash_password(password: str) -> str:
    """Hashes a password with a randomly generated 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        100000,
    ).hex()
    return f"{salt}:{key}"


def _verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """Verifies a provided password against the stored salt:key hash string."""
    try:
        salt, expected_key = stored_password_hash.split(":")
        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            provided_password.encode("utf-8"),
            bytes.fromhex(salt),
            100000,
        ).hex()
        return hmac.compare_digest(expected_key, computed_key)
    except Exception:
        return False


def init_db(db_path: str = DB_PATH) -> None:
    """Initializes the SQLite database tables for users and study sessions."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                document_text TEXT NOT NULL,
                study_kit_json TEXT NOT NULL,
                chat_history_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        conn.commit()


def register_user(
    full_name: str,
    username: str,
    password: str,
    db_path: str = DB_PATH,
) -> Tuple[bool, str]:
    """Registers a new user with salted password hashing.

    Returns:
        (True, "Success message") or (False, "Error message")
    """
    full_name = (full_name or "").strip()
    username = (username or "").strip().lower()
    password = password or ""

    if not full_name:
        return False, "Full name cannot be empty."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 4:
        return False, "Password must be at least 4 characters."

    pw_hash = _hash_password(password)

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, full_name, password_hash) VALUES (?, ?, ?)",
                (username, full_name, pw_hash),
            )
            conn.commit()
            return True, "Account registered successfully."
    except sqlite3.IntegrityError:
        return False, f"Username '{username}' is already taken. Please choose another."
    except Exception as e:
        return False, f"Registration failed: {e}"


def authenticate_user(
    username: str,
    password: str,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    """Authenticates a user by username and password.

    Returns:
        User dict (id, username, full_name, created_at) if valid, None otherwise.
    """
    username = (username or "").strip().lower()
    if not username or not password:
        return None

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, full_name, password_hash, created_at FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            if row and _verify_password(row["password_hash"], password):
                return {
                    "id": row["id"],
                    "username": row["username"],
                    "full_name": row["full_name"],
                    "created_at": row["created_at"],
                }
    except Exception:
        pass
    return None


def save_study_session(
    user_id: int,
    title: str,
    document_text: str,
    study_kit_data: Any,
    db_path: str = DB_PATH,
) -> int:
    """Saves a newly generated study session to the database.

    Args:
        user_id: ID of the authenticated user.
        title: Title of the study session (e.g. filenames + timestamp).
        document_text: The extracted multi-document text.
        study_kit_data: StudyKit Pydantic instance, dict, or JSON string.

    Returns:
        int: The session ID of the newly created session.
    """
    if hasattr(study_kit_data, "model_dump_json"):
        kit_json = study_kit_data.model_dump_json()
    elif isinstance(study_kit_data, dict):
        kit_json = json.dumps(study_kit_data)
    elif isinstance(study_kit_data, str):
        kit_json = study_kit_data
    else:
        kit_json = json.dumps(str(study_kit_data))

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO study_sessions (user_id, title, document_text, study_kit_json, chat_history_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, title, document_text, kit_json, "[]"),
        )
        conn.commit()
        return cursor.lastrowid


def update_session_chat(
    session_id: int,
    chat_messages: List[Dict[str, Any]],
    db_path: str = DB_PATH,
) -> bool:
    """Updates the chat_history_json of an existing study session."""
    chat_json = json.dumps(chat_messages)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE study_sessions SET chat_history_json = ? WHERE id = ?",
            (chat_json, session_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_user_sessions(
    user_id: int,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """Retrieves all past study sessions for a given user, sorted newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, title, created_at, length(document_text) as char_count
            FROM study_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def load_session_by_id(
    session_id: int,
    db_path: str = DB_PATH,
) -> Optional[Dict[str, Any]]:
    """Loads a full study session by ID, parsing stored JSON fields.

    Returns:
        dict with keys: id, user_id, title, document_text, study_kit (parsed dict),
        chat_history (parsed list), created_at.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM study_sessions WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        data = dict(row)
        try:
            data["study_kit"] = json.loads(data["study_kit_json"])
        except Exception:
            data["study_kit"] = None

        try:
            data["chat_history"] = json.loads(data["chat_history_json"])
        except Exception:
            data["chat_history"] = []

        return data
