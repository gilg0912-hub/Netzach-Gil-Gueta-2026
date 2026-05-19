import sqlite3
from Protocol import *
import threading
import uuid


class Database:
    def __init__(self, db_name=r"C:\Users\User\Documents\לימודים\database_of_the_project.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.db_lock = threading.RLock()
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def _clean_user_row(self, row):
        if not row:
            return None

        user_data = dict(row)
        user_data.pop(Contract.PASSWORD, None)

        return user_data

    # ==========================================
    # פונקציה חדשה: אימות Mock (משרד החינוך)
    # ==========================================
    def is_authorized_identity(self, identifier, role):
        with self.db_lock:
            try:
                query = "SELECT 1 FROM Authorized_Identities WHERE identity = ? AND role = ?"
                self.cursor.execute(query, (identifier, role))
                return self.cursor.fetchone() is not None
            except sqlite3.Error as e:
                print(f"Mock validation error: {e}")
                return False

    def get_user_by_email(self, email):
        with self.db_lock:
            query = "SELECT * FROM Users WHERE email = ?"
            self.cursor.execute(query, (email,))
            return self._clean_user_row(self.cursor.fetchone())

    def get_user_by_public_id(self, p_id):
        with self.db_lock:
            try:
                query = "SELECT * FROM Users WHERE public_id = ?"
                self.cursor.execute(query, (p_id,))
                return self._clean_user_row(self.cursor.fetchone())
            except sqlite3.Error as e:
                print(f"Database error in get_user_by_public_id: {e}")
                return None

    def get_user_by_token(self, token):
        with self.db_lock:
            try:
                query = "SELECT * FROM Users WHERE session_token = ?"
                self.cursor.execute(query, (token,))
                return self._clean_user_row(self.cursor.fetchone())
            except sqlite3.Error as e:
                print(f"Database error in get_user_by_token: {e}")
                return None

    def authenticate_user(self, identity, password):
        with self.db_lock:
            query = "SELECT * FROM Users WHERE identity = ? AND password = ?"
            self.cursor.execute(query, (identity, password))
            return self._clean_user_row(self.cursor.fetchone())

    def user_exists(self, identity):
        with self.db_lock:
            query = "SELECT 1 FROM Users WHERE identity = ?"
            self.cursor.execute(query, (identity,))
            return self.cursor.fetchone() is not None

    def email_exists(self, email):
        with self.db_lock:
            query = "SELECT 1 FROM Users WHERE email = ?"
            self.cursor.execute(query, (email,))
            return self.cursor.fetchone() is not None

    def register_user(self, role, identifier, hashed_password, email, p_id, session_token, display_name):
        with self.db_lock:
            try:
                query_user = """
                    INSERT INTO Users (identity, display_name, email, password, public_id, session_token, role) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                self.cursor.execute(query_user,
                                    (identifier, display_name, email, hashed_password, p_id, session_token, role))
                self.conn.commit()
                return self.get_user_by_public_id(p_id)

            except sqlite3.Error as e:
                print(f"Registration database error: {e}")
                self.conn.rollback()
                return None

    def get_verified_educational_name(self, identifier, role):
        with self.db_lock:  # שמירה על בטיחות בריצה מקבילית (Thread-Safe)
            try:
                query = "SELECT pre_approved_name FROM Authorized_Identities WHERE identity = ? AND role = ?"
                self.cursor.execute(query, (identifier, role))
                row = self.cursor.fetchone()

                # אם נמצאה רשומה, נשלוף את השם הרשמי. אחרת, נחזיר None.
                return row['pre_approved_name'] if row else None

            except sqlite3.Error as e:
                print(f"Mock validation database error: {e}")
                return None

    def update_user_token(self, p_id, session_token):
        with self.db_lock:
            query = "UPDATE Users SET session_token = ? WHERE public_id = ?"
            self.cursor.execute(query, (session_token, p_id))
            self.conn.commit()
            return self.get_user_by_public_id(p_id)

    def get_user_room_ids(self, db_id):
        with self.db_lock:
            query = """
                SELECT room_id 
                FROM RoomParticipants 
                WHERE user_id = ?
            """
            try:
                self.cursor.execute(query, (db_id,))
                rows = self.cursor.fetchall()
                return [row['room_id'] for row in rows]
            except Exception as e:
                print(f"Error fetching rooms: {e}")
                return []

    def get_room_by_id(self, room_id):
        with self.db_lock:
            query = "SELECT * FROM ChatRooms WHERE id = ?"
            try:
                self.cursor.execute(query, (room_id,))
                row = self.cursor.fetchone()
                return dict(row) if row else None
            except Exception as e:
                print(f"Error fetching room by ID: {e}")
                return None

    def find_available_room_for_user(self, allowed_role, db_id):
        with self.db_lock:
            query = """
                    SELECT * FROM ChatRooms 
                    WHERE allowed_role = ?
                    AND is_locked = 0
                    AND id NOT IN (
                        SELECT room_id 
                        FROM RoomParticipants 
                        WHERE user_id = ?
                    )
                    LIMIT 1
                """
            try:
                self.cursor.execute(query, (allowed_role, db_id))
                row = self.cursor.fetchone()
                return dict(row) if row else None
            except Exception as e:
                print(f"Find room error: {e}")
                return None

    def insert_msg(self, room_id, sender_id, content, now, public_msg_id):
        with self.db_lock:
            # 🟢 תוקן מ-id ל-room_id בשם העמודה
            query = "INSERT INTO Messages (room_id, sender_id, content, timestamp, public_id) VALUES (?, ?, ?, ?, ?)"
            try:
                self.cursor.execute(query, (room_id, sender_id, content, now, public_msg_id))
                self.conn.commit()
                return self.cursor.lastrowid
            except Exception as e:
                print(f"Insert message error: {e}")
                return None

    def get_topics_paged(self, role_name, before_id=None, limit=5):
        with self.db_lock:
            try:
                if before_id:
                    query = "SELECT * FROM HotTopics WHERE role = ? AND id < ? ORDER BY id DESC LIMIT ?"
                    params = (role_name, before_id, limit)
                else:
                    query = "SELECT * FROM HotTopics WHERE role = ? ORDER BY id DESC LIMIT ?"
                    params = (role_name, limit)
                self.cursor.execute(query, params)
                rows = self.cursor.fetchall()
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                print(f"Paged fetch error: {e}")
                return []

    def save_hot_topics(self, topics, role_name):
        with self.db_lock:
            try:
                query = "INSERT INTO HotTopics (ai_topic_id, category, title, role, url, summary) VALUES (?, ?, ?, ?, ?, ?)"
                for item in topics:
                    values = (
                        item.get("topic_id", "N/A"),
                        item.get("category", "כללי"),
                        item.get("title", "אין כותרת"),
                        role_name,
                        item.get("url", ""),
                        item.get("summary", "")
                    )
                    self.cursor.execute(query, values)
                    item['id'] = self.cursor.lastrowid
                self.conn.commit()
                return True
            except Exception as e:
                print(f"Save topics error: {e}")
                return False

    def add_user_to_room_db(self, room_id, db_id):
        with self.db_lock:
            query = "INSERT OR IGNORE INTO RoomParticipants (room_id, user_id) VALUES (?, ?)"
            try:
                self.cursor.execute(query, (room_id, db_id))
                self.conn.commit()
            except sqlite3.Error as e:
                print(f"[DB Error] Failed to add user {db_id} to room {room_id}: {e}")

    def room_exists(self, room_id):
        with self.db_lock:
            query = "SELECT 1 FROM ChatRooms WHERE id = ?"
            self.cursor.execute(query, (room_id,))
            return self.cursor.fetchone() is not None

    def insert_new_room(self, room_id, category, display_name, created_by, allowed_role, invite_code, is_open=0):
        with self.db_lock:
            try:
                room_query = """
                    INSERT INTO ChatRooms (id, category, is_open, display_name, created_by, invite_code, allowed_role) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                self.cursor.execute(room_query,
                                    (room_id, category, is_open, display_name, created_by, invite_code, allowed_role))

                system_content = f"החדר '{display_name}' נוצר בהצלחה! ברוכים הבאים לצ'אט NETZACH."
                now_timestamp = time.time()

                system_msg_public_id = str(uuid.uuid4())

                msg_query = """
                    INSERT INTO Messages (room_id, sender_id, content, timestamp, public_id)
                    VALUES (?, ?, ?, ?, ?)
                """
                self.cursor.execute(msg_query, (room_id, None, system_content, now_timestamp, system_msg_public_id))

                self.conn.commit()
                print(f"[DB Success] Atomic transaction completed for room {room_id} with system message.")
                return True

            except sqlite3.Error as e:
                print(f"[DB Error] Critical failure, rolling back room creation for {room_id}: {e}")
                self.conn.rollback()
                return False

    def get_older_messages(self, room_id: str, anchor_id: str = None, limit: int = 25) -> dict:
        fetch_limit = limit + 1

        with self.db_lock:
            try:
                if anchor_id is None:
                    query = """
                        SELECT m.*, u.public_id AS sender_p_id 
                        FROM Messages m
                        LEFT JOIN Users u ON m.sender_id = u.id
                        WHERE m.room_id = ? 
                        ORDER BY m.timestamp DESC 
                        LIMIT ?
                    """
                    self.cursor.execute(query, (room_id, fetch_limit))
                    raw_messages = self.cursor.fetchall()

                else:
                    anchor_query = "SELECT timestamp FROM Messages WHERE public_id = ?"
                    self.cursor.execute(anchor_query, (anchor_id,))
                    anchor_row = self.cursor.fetchone()

                    if not anchor_row:
                        return {"items": [], "end_of_data": True}

                    anchor_time = anchor_row['timestamp']

                    query = """
                        SELECT m.*, u.public_id AS sender_p_id 
                        FROM Messages m
                        LEFT JOIN Users u ON m.sender_id = u.id
                        WHERE m.room_id = ? AND m.timestamp < ? 
                        ORDER BY m.timestamp DESC 
                        LIMIT ?
                    """
                    self.cursor.execute(query, (room_id, anchor_time, fetch_limit))
                    raw_messages = self.cursor.fetchall()

                end_of_data = len(raw_messages) <= limit
                if not end_of_data:
                    raw_messages = raw_messages[:limit]

                raw_messages.reverse()

                formatted_messages = []
                for row in raw_messages:
                    sender_pid = row['sender_p_id'] if row['sender_p_id'] else "System"

                    formatted_messages.append({
                        Contract.MSG_ID: str(row['public_id']),
                        Contract.ROOM_ID: str(row['room_id']),
                        Contract.SENDER_PID: sender_pid,
                        Contract.CONTENT: row['content'],
                        Contract.TIMESTAMP: row['timestamp'],
                    })

                return {
                    "items": formatted_messages,
                    "end_of_data": end_of_data
                }

            except sqlite3.Error as e:
                print(f"[DB Error] Failed to fetch older messages for room {room_id}: {e}")
                return {"items": [], "end_of_data": True}