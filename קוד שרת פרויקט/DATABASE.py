import  sqlite3
from Protocol import *

class Database:
    def __init__(self, db_name=r"C:\Users\User\Documents\netzach_project\db.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_user_by_email(self, role_config, email):
        query = f"""
            SELECT * FROM {role_config.table} 
            WHERE {Contract.EMAIL} = ?
        """

        self.cursor.execute(query, (email,))
        row = self.cursor.fetchone()

        if row:
            user_data = dict(row)
            user_data.pop(Contract.PASSWORD, None)
            return user_data

    def get_user_by_public_id(self, role_config, p_id):
        try:
            query = f"""
                SELECT * FROM {role_config.table} 
                WHERE public_id = ?
            """

            self.cursor.execute(query, (p_id,))
            row = self.cursor.fetchone()

            if row:
                user_data = dict(row)
                user_data.pop(Contract.PASSWORD, None)
                return user_data

            return

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_user_by_token(self, role_config, token):
        try:
            query = f"""
                SELECT * FROM {role_config.table} 
                WHERE session_token = ?
            """

            self.cursor.execute(query, (token,))
            row = self.cursor.fetchone()

            if row:
                user_data = dict(row)
                user_data.pop(Contract.PASSWORD, None)
                return user_data

            return

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def authenticate_user(self, role_config, search_value, password):

        query = f"SELECT * FROM {role_config.table} WHERE {role_config.id_field} = ? and password = ?"
        self.cursor.execute(query, (search_value, password))

        row= self.cursor.fetchone()

        if row:
            user_data = dict(row)
            user_data.pop(Contract.PASSWORD, None)
            return user_data
        return None

    def user_exists(self, role_config, search_value):

        query = f"SELECT 1 FROM {role_config.table} WHERE {role_config.id_field} = ?"
        self.cursor.execute(query, (search_value,))
        return self.cursor.fetchone() is not None


    def register_user(self, role_config, identifier, hashed_password, email, p_id, session_token):

        query = f"INSERT INTO {role_config.table} ({role_config.id_field}, password, email, public_id, session_token) VALUES (?, ?, ?, ?, ?)"
        try:
            self.cursor.execute(query, (identifier, hashed_password, email, p_id, session_token))
            self.conn.commit()

            return {
                role_config.id_field: identifier,
                Contract.EMAIL: email,
                Contract.PUBLIC_ID: p_id,
                Contract.TOKEN: session_token
            }
        except sqlite3.Error as e:
            print(f"[Database] שגיאה ברישום משתמש: {e}")
            return None


    def update_user_token(self, role_config, p_id, session_token):
        query = f"UPDATE {role_config.table} SET session_token = ? WHERE public_id = ?"
        self.cursor.execute(query, (session_token, p_id))
        self.conn.commit()
        return self.get_user_by_public_id(role_config, p_id)

    #________________________________________________________________#


    def get_user_room_ids(self, p_id):
        query = f"SELECT {Contract.ROOM_ID} FROM PARTICIPANTS WHERE public_id = ?"
        try:
            self.cursor.execute(query, (p_id,))
            rows = self.cursor.fetchall()

            return [row[Contract.ROOM_ID] for row in rows]

        except Exception as e:
            print(f"Error fetching user rooms for {p_id}: {e}")
            return []

    def get_room_by_id(self, room_id):
        query = f"SELECT * FROM ChatRooms WHERE {Contract.ROOM_ID} = ?"
        try:
            self.cursor.execute(query, (room_id,))
            row = self.cursor.fetchone()

            return dict(row) if row else None

        except Exception as e:
            return None

    def find_available_room_for_user(self, topic, role, p_id):
        query = f"""
                SELECT * FROM ChatRooms 
                WHERE topic = ? 
                AND role = ? 
                AND is_locked = 0
                AND {Contract.ROOM_ID} NOT IN (
                    SELECT {Contract.ROOM_ID} 
                    FROM participants 
                    WHERE public_id = ?
                )
                LIMIT 1
            """
        try:
            self.cursor.execute(query, (topic, role, p_id))
            row = self.cursor.fetchone()

            return dict(row) if row else None

        except Exception as e:
            return None

    def insert_msg(self, room_id, sender_id, content, now):
        query = "INSERT INTO Messages (room_id, sender_id, content) VALUES (?, ?, ?, ?)"

        try:
            self.cursor.execute(query, (room_id, sender_id, content, now))
            self.conn.commit()

            return self.cursor.lastrowid
        except Exception as e:
            print(f"Error inserting message: {e}")
            return None

    def is_topic_exists(self, topic_name):
        try:
            check_query = "SELECT 1 FROM HotTopics WHERE topic_name = ?"
            self.cursor.execute(check_query, (topic_name,))

            return self.cursor.fetchone() is not None
        except Exception as e:
            return False

    def update_topic_list(self, topic_name):
        try:
            update_query = "UPDATE HotTopics SET usage_count = usage_count + 1 WHERE topic_name = ?"
            self.cursor.execute(update_query, (topic_name,))
            self.conn.commit()
            return True
        except Exception as e:
            return False
