import json, queue, threading
from cryptography.fernet import Fernet

class Message_Manager:
    def __init__(self):
        # במקום הודעת עדיפות בודדת, יש לנו תור עדיפויות שלם
        self.priority_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()  # תור ההודעות הרגיל
        self.incoming_queue = queue.Queue()

        self.connection_active = threading.Event()

        self.is_authorized = threading.Event()
        self.is_banned = threading.Event()

        self.is_authorized.clear()
        self.is_banned.clear()


    def set_priority_msg(self, msg=None):
        if msg:
            self.priority_queue.put(msg)

    def send_msg(self, formatted_msg):
        self.outgoing_queue.put(formatted_msg)

    def clear_outgoing_queue(self):
        try:
            while True:
                self.outgoing_queue.get_nowait()
        except queue.Empty:
            pass


    def get_next_outbound(self):
        try:
            return self.priority_queue.get_nowait()
        except queue.Empty:
            pass

        if self.is_banned.is_set():
            return None

        if not self.is_authorized.is_set():
            return None

        try:
            return self.outgoing_queue.get_nowait()
        except queue.Empty:
            return None


class MessageProtocol:
    def __init__(self):
        self.cipher = None

    def set_session_key(self, key: bytes):
        self.cipher = Fernet(key)

    def pack(self, data_dict):
        json_data = json.dumps(data_dict).encode('utf-8')
        if self.cipher:
            json_data = self.cipher.encrypt(json_data)
        print('a', json_data)

        header = len(json_data).to_bytes(4, 'big')
        return header + json_data

    def unpack(self, raw_data):
        try:
            if self.cipher:
                raw_data = self.cipher.decrypt(raw_data)

            return json.loads(raw_data.decode('utf-8'))

        except Exception as e:
            print(f"[Protocol Error] Failed to unpack message: {e}")
            raise e