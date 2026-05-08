import json, queue, threading

class Message_Manager:
    def __init__(self):
        self.outgoing_queue = queue.Queue()
        self.incoming_queue = queue.Queue()
        self.connection_active = threading.Event()  # ה"סכר" שלנו
        self.priority_lock = threading.Lock()
        self.priority_msg = None

    def set_priority_msg(self, msg=None):
        with self.priority_lock:
            self.priority_msg = msg

    def send_msg(self, formatted_msg):
        self.outgoing_queue.put(formatted_msg)
    def clear_outgoing_queue(self):
        try:
            while True:
                self.outgoing_queue.get_nowait()
        except queue.Empty:
            pass

    def get_next_outbound(self):
        with self.priority_lock:
            if self.priority_msg:
                msg = self.priority_msg
                self.priority_msg = None
                return msg

        try:
            return self.outgoing_queue.get_nowait()
        except queue.Empty:
            return None

class MessageProtocol:
    """אחראית על אריזה ופריקה של מידע"""
    @staticmethod
    def pack(data_dict):
        # המרה ל-JSON עם ה-Encoder המקצועי שבנינו
        json_data = json.dumps(data_dict).encode('utf-8')
        header = len(json_data).to_bytes(4, 'big')
        return header + json_data

    @staticmethod
    def unpack(raw_data):
        # פיענוח מהיר של JSON
        return json.loads(raw_data.decode('utf-8'))