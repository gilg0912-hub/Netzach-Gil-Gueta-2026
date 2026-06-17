import socket
import queue
import json
import select
import bcrypt

import os

from Crypto.PublicKey import RSA

from AIHandler import AIHandler
from UDPMediaServer import UDPMediaServer
import hashlib
import DATABASE

from EmailService import EmailService
from ChatService import *

from Protocol import *
import time
import threading
import traceback

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST= '0.0.0.0'
        self.PORT= 8820

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key_pem = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        self.server.bind((self.HOST, self.PORT))
        self.server.listen()
        self.server.setblocking(False)

        self.db= DATABASE.Database()
        self.email_service = EmailService("Netzach.GUETA@gmail.com", "euhizienenibsako")

        self.ai_handler = AIHandler(api_key="AIzaSyBUTtCftupCqtOV_WAnTvkY-iRWj8pDfSw", db= self.db)
        self.stop_ai_thread = threading.Event()

        #self.start_ai_service()

        self.chat_manager = ChatManager(self.db, self.send_to_client, self.send_to_user)

        self.clients={}
        self.online_users= {}
        self.routing_lock = threading.Lock()

        self.traffic_monitor = TrafficMonitor()
        self.msg_dispatcher = MsgDispatcher(self.send_to_client,  self.traffic_monitor)

        self.auth_handler= AuthHandler(self.db, self.email_service, self.send_to_client, self.on_user_authenticated, self.traffic_monitor, self.on_user_logout)

        self._handlers={
            MsgType.LOGIN: self.auth_handler.process_login,
            MsgType.FORGOT_PASSWORD: self.auth_handler.process_forgot_password,
            MsgType.SIGNUP: self.auth_handler.process_sign_up,
            MsgType.VERIFY_OTP: self.auth_handler.verify_email,
            MsgType.RESEND_OTP: self.auth_handler.process_resend_otp,
            MsgType.RECONNECT: self.auth_handler.reconnect,
            MsgType.AUTH_UPLOAD: self.auth_handler.process_bulk_upload,
            MsgType.SEND_MSG: self.chat_manager.process_new_message,
            MsgType.JOIN_ROOM: self.chat_manager.add_user_to_room,
            MsgType.CREATE_CHAT_ROOM: self.chat_manager.create_new_room,
            MsgType.GET_OLDER_TOPICS: self.chat_manager.handle_older_topics,
            MsgType.GET_OLDER_MESSAGES: self.chat_manager.handle_older_messages,
            MsgType.GET_OLDER_GROUPS: self.chat_manager.handle_older_groups,
            MsgType.LOGOUT: self.auth_handler.process_logout,
            MsgType.START_CALL: self.chat_manager.handle_start_call,
            MsgType.JOIN_CALL: self.chat_manager.handle_join_call,
            MsgType.LEAVE_CALL: self.chat_manager.handle_leave_call,
            MsgType.UPDATE_ROOM_MEDIA_KEY: self.chat_manager.handle_update_room_media_keys,
        }

        self.setup_handlers()

        self.logic_queue = queue.Queue()
        self.num_workers = 4
        self.workers = []

        for i in range(self.num_workers):
            t = threading.Thread(target=self._logic_worker_loop, daemon=True, name=f"Worker-{i + 1}")
            t.start()
            self.workers.append(t)

        self.udp_server = UDPMediaServer(host= self.HOST, port=8821)
        self.udp_server.set_auth_validator(self.chat_manager.validate_udp_join)
        self.udp_server.start()

    def _logic_worker_loop(self):
        while True:
            try:
                client, data_bytes = self.logic_queue.get()

                if client.pending_disconnect:
                    self.logic_queue.task_done()
                    continue

                self.msg_dispatcher.handle(client, data_bytes)

                self.logic_queue.task_done()

            except Exception as e:
                print(f"[{threading.current_thread().name}] Critical error in logic loop: {e}")

    def setup_handlers(self):
        for k, v in self._handlers.items():
            self.msg_dispatcher.register(k, v)

    def start_ai_service(self):
        t = threading.Thread(target=self._background_update_loop, daemon=True, name="AI-Update-Thread")
        t.start()

    def _background_update_loop(self):
        print("[Server] AI Update Thread is now running.")

        while not self.stop_ai_thread.is_set():
            try:
                success = self.ai_handler.update_all_topics()
                if success:
                    print("[Server] Global update successful.")
                else:
                    print("[Server] Global update failed, will retry.")
            except Exception as e:
                print(f"[Server] Critical error in AI Thread: {e}")

            stopped = self.stop_ai_thread.wait(timeout=60 * 60 * 5)
            if stopped:
                print("[Server] AI Thread received stop signal, shutting down.")
                return

    def run(self):

        while True:

            potential_readers= [self.server]+ [sock for sock, client in self.clients.items() if not client.pending_disconnect]
            potential_writers= [sock for sock, client in self.clients.items() if not client.send_queue.empty() or client.outgoing_buffer]

            r_list, w_list, x_list = select.select(potential_readers, potential_writers, [], 0.1)

            for sock in r_list:
                if sock == self.server:
                    self.new_connection()
                else:
                    self.read_from_client(sock)

            for sock in w_list:
                client = self.clients.get(sock)
                if client:
                    self.write_to_client(sock, client)

    def new_connection(self):
        try:
            client_socket, addr = self.server.accept()
            ip = addr[0]
            client_socket.setblocking(False)

            # יצירת אובייקט הלקוח - הקונסטרקטור שלו מאתחל אוטומטית מופע פרטי של MessageProtocol
            client = Client(client_socket, addr)
            self.clients[client_socket] = client

            # 1. בניית הודעת ה-RSA הראשונית (שליחת המפתח הציבורי של השרת ללקוח)
            rsa_msg = ResponseFactory.create(
                msg_type=MsgType.KEY_EXCHANGE,
                code=MsgCodes.RSA_KEY,
                raw_data={Contract.PUBLIC_KEY: self.public_key_pem}
            )

            # 2. דחיפת המילון ישירות לתור השליחה.
            # write_to_client ימשוך אותו ויפעיל אוטומטית את client.protocol.pack() שיטפל ב-JSON וב-Header
            self.send_to_client(client_socket, rsa_msg)

            # 3. בדיקות והגנות אבטחה של שכבת התעבורה מול ה-TrafficMonitor
            error_code, freeze_time = self.traffic_monitor.process_new_connection(ip)
            if error_code:
                is_silent = (error_code == 'SILENT_DROP')
                if is_silent:
                    self.handle_disconnect(client_socket)
                    return
                self.handle_penalty(client, error_code, freeze_time)
                print(f"[Security] Notified and banning {ip} for {freeze_time}s")
                return

        except Exception as e:
            print(f"Error in new connection: {e}")

    def read_from_client(self, sock):
        MAX_MSG_SIZE = 4096
        client = self.clients[sock]

        if client.pending_disconnect:
            return

        try:
            chunk = sock.recv(1024)
            if not chunk:
                self.handle_disconnect(sock)
                return

            client.incoming_buffer += chunk

            while True:
                if client.expected_len == 0:
                    if len(client.incoming_buffer) < 4:
                        return
                    client.expected_len = int.from_bytes(client.incoming_buffer[:4], 'big')
                    client.incoming_buffer = client.incoming_buffer[4:]

                    if client.expected_len > MAX_MSG_SIZE:
                        self.handle_disconnect(sock, "Message too large")
                        return

                if len(client.incoming_buffer) < client.expected_len:
                    return

                raw_bytes = client.incoming_buffer[:client.expected_len]
                client.incoming_buffer = client.incoming_buffer[client.expected_len:]
                client.expected_len = 0

                try:
                    data_json = client.protocol.unpack(raw_bytes)

                    # 1. בודקים גם את הסוג (KEY_EXCHANGE) וגם את הקוד (SESSION_KEY)
                    if data_json.get(Contract.TYPE) == MsgType.KEY_EXCHANGE and data_json.get(
                            Contract.CODE) == MsgCodes.SESSION_KEY:

                        # 2. הנתונים נמצאים כעת בתוך מפתח DATA
                        payload = data_json.get(Contract.DATA, {})
                        encrypted_key = bytes.fromhex(payload.get("encrypted_key"))

                        session_key = self.private_key.decrypt(
                            encrypted_key,
                            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                         algorithm=hashes.SHA256(), label=None)
                        )

                        client.protocol.set_session_key(session_key)
                        print(f"[Security] Secure session established for {client.addr}")

                        # 3. בניית הודעת האישור עם סוג הודעה מפורש של KEY_EXCHANGE והקוד המתאים
                        handshake_ok = ResponseFactory.create(
                            msg_type=MsgType.KEY_EXCHANGE,
                            code=MsgCodes.SUCCESS
                        )
                        self.send_to_client(sock, handshake_ok)

                    else:
                        # אם זה לא ה-Handshake, חייבים לוודא שהערוץ כבר מוצפן!
                        if not client.protocol.cipher:
                            self.handle_disconnect(sock, "Unauthorized: Handshake required")
                            return

                        # העברה ל-Dispatcher (כמילון פייתון נקי לחלוטין)
                        self.handle_client(sock, data_json)

                except Exception as e:
                    print(f"[Security] Processing error from {client.addr}: {e}")
                    self.handle_disconnect(sock, "Decryption/Protocol error")
                    return

        except Exception as e:
            self.handle_disconnect(sock, e)

    def handle_penalty(self, client, action, freeze):

        error_res = ResponseFactory.error(MsgType.GENERAL, action, {Contract.EXPIRY: freeze})
        self.send_to_client(client.sock, error_res)

        if action == MsgCodes.ACCESS_DENIED:
            client.pending_disconnect = True

        return True

    def handle_client(self, sock, data_json):
        client = self.clients.get(sock)
        if client:
            self.logic_queue.put((client, data_json))

    def write_to_client(self, sock,client):

        try:
            if client.outgoing_buffer:
                sent = sock.send(client.outgoing_buffer)
                client.outgoing_buffer = client.outgoing_buffer[sent:]

            elif not client.send_queue.empty():
                    data = client.send_queue.get()

                    full_msg = client.protocol.pack(data)

                    sent= sock.send(full_msg)
                    client.outgoing_buffer = full_msg[sent:]

            if client.pending_disconnect and not client.outgoing_buffer and client.send_queue.empty():
                self.handle_disconnect(sock, "Banned: Final message delivered")

        except (OSError, BlockingIOError):
            pass
        except Exception as e:
            self.handle_disconnect(sock, e)

    def send_to_client(self, sock, data):
        if sock in self.clients:
            self.clients[sock].send_queue.put(data)

    def send_to_user(self, p_id, data):
        with self.routing_lock:
            active_sockets = list(self.online_users.get(p_id, []))

        for sock in active_sockets:
            self.send_to_client(sock, data)

    def get_online_sockets(self, p_id):
        with self.routing_lock:
            return list(self.online_users.get(p_id, []))

    def handle_disconnect(self, sock, error=None):
        client = self.clients.pop(sock, None)

        if not client:
            return

        addr = client.addr
        p_id = client.p_id

        if p_id:
            with self.routing_lock:
                if sock in self.online_users[p_id]:
                    self.online_users[p_id].remove(sock)
                    print(f"[Routing] Removed socket for {p_id}. Remaining active sessions: {len(self.online_users[p_id])}")
                if not self.online_users[p_id]:
                    del self.online_users[p_id]

        print(f"Client {addr} disconnected. Reason: {error if error else 'Cleanly'}")


        try:
            sock.close()
        except Exception:
            pass

    def on_user_logout(self, p_id):
        with self.routing_lock:
            if p_id in self.online_users:
                print(f"[Routing] Removing {p_id} from online_users due to explicit logout.")

                for sock in self.online_users[p_id]:
                    client = self.clients.get(sock)
                    if client:
                        client.pending_disconnect = True

                del self.online_users[p_id]

    def on_user_authenticated(self, p_id, sock):
        with self.routing_lock:
            if p_id not in self.online_users:
                self.online_users[p_id] = []

            if sock not in self.online_users[p_id]:
                self.online_users[p_id].append(sock)

        client = self.clients.get(sock)

        if client:
            rooms_payload = self.chat_manager.get_initial_rooms_payload(client)

            sync_payload = {
                Contract.ROOMS: rooms_payload
            }

            sync_msg = ResponseFactory.create(
                msg_type=MsgType.SYNC_DATA,
                code=MsgCodes.SUCCESS,
                raw_data=sync_payload
            )

            # 4. שליחה סופית של המידע המינימלי והנחוץ ללקוח לצורך רינדור מסך הבית/קבוצות
            self.send_to_client(client.sock, sync_msg)


    def close(self):
        print("\n[Server] Initiating graceful shutdown...")

        self.stop_ai_thread.set()
        print("[Server] Signaled AI thread to stop.")

        pending_tasks = self.logic_queue.qsize()
        if pending_tasks > 0:
            print(f"[Server] Waiting for {pending_tasks} pending tasks to complete...")

        self.logic_queue.join()
        print("[Server] All logic tasks completed successfully.")

        try:
            self.db.cursor.close()
            self.db.conn.commit()
            self.db.conn.close()
            print("[Server] Database connection closed safely.")
        except Exception as e:
            print(f"[Server] Error closing database: {e}")

        try:
            self.server.close()
            print("[Server] Main socket closed.")
        except:
            pass


class SecurityState:
    def __init__(self):
        # מנעול ייעודי להגנה על המצב הלוגי של כתובת ה-IP הזו
        self.lock = threading.Lock()

        # ניהול זיכרון ופעילות
        self.last_activity = time.time()

        # חסימות רשת קשיחות (TCP / פרוטוקול)
        self.cooldown_until = 0
        self.violation_count = 0
        self.warnings_ignored = 0
        self.last_error_code = None

        # השתקות ספאם והצפות תוכן (אפליקציה / צ'אט)
        self.spam_cooldown_until = 0
        self.msg_count = 0
        self.dupe_count = 0
        self.window_end = 0
        self.last_msg_hash = None
        self.last_msg_sent_at = 0


class TrafficMonitor:
    def __init__(self, penalty_threshold=5):
        self._states = {}
        self._email_states = {}

        # מנעול גלובלי להגנה על המילונים המשותפים
        self.monitor_lock = threading.Lock()

        self.PENALTY_THRESHOLD = penalty_threshold
        self.MAX_IGNORED_WARNINGS = 3

        # הגדרות ניקוי זיכרון (Garbage Collection)
        self.cleanup_interval = 600  # ריצה כל 10 דקות
        self.state_ttl = 3600  # תפוגה לאחר שעה של חוסר פעילות

        # הפעלת תהליכון רקע שקט לניקוי זיכרון
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="TrafficMonitor-Cleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        """תהליכון רקע המנקה כתובות IP ואימיילים ישנים למניעת זליגת זיכרון"""
        while True:
            time.sleep(self.cleanup_interval)
            now = time.time()

            with self.monitor_lock:
                ips_to_remove = [
                    ip for ip, state in self._states.items()
                    if now - state.last_activity > self.state_ttl
                ]
                for ip in ips_to_remove:
                    del self._states[ip]

                emails_to_remove = [
                    email for email, status in self._email_states.items()
                    if now - status.get('last_activity', 0) > self.state_ttl
                ]
                for email in emails_to_remove:
                    del self._email_states[email]

            if ips_to_remove or emails_to_remove:
                print(f"[Security] Cleanup: Removed {len(ips_to_remove)} IPs and {len(emails_to_remove)} Emails.")

    def _get_or_create_state(self, ip):
        with self.monitor_lock:
            if ip not in self._states:
                self._states[ip] = SecurityState()

            # עדכון חותמת זמן לפעילות אחרונה
            self._states[ip].last_activity = time.time()
            return self._states[ip]

    def process_new_message(self, ip, payload_size):
        """הגנת שכבת הרשת (Socket/TCP) - מניעת הצפת פאקטות ו-DDoS"""
        state = self._get_or_create_state(ip)

        with state.lock:
            now = time.time()

            # בדיקה האם ה-IP נמצא תחת חסימת רשת קשיחה
            if now < state.cooldown_until:
                state.warnings_ignored += 1

                # ניסיון מעקף או התעלמות אגרסיבית מובילים לניתוק מיידי מהסוקט
                if state.warnings_ignored >= self.MAX_IGNORED_WARNINGS:
                    state.last_error_code = MsgCodes.ACCESS_DENIED
                    state.cooldown_until = now + 600  # אכיפת חסימה ל-10 דקות מלאות
                    return MsgCodes.ACCESS_DENIED, 600, True  # True = פקודת ניתוק לשרת

                remaining = int(state.cooldown_until - now)
                return state.last_error_code, remaining, False

            state.warnings_ignored = 0

            # בדיקת חלון זמן לאיפוס מונה ההפרות של הרשת
            time_passed = now - max(state.last_msg_sent_at, state.cooldown_until)
            state.last_msg_sent_at = now

            if time_passed > 30:
                state.violation_count = 0
                state.last_error_code = None
                return None, 0, False

            # קביעת קנסות לפי מהירות הגעת המידע וגודלו
            size_multiplier = 1 + (payload_size // 1024)

            if time_passed < 0.02:
                penalty = 6 * size_multiplier
            elif time_passed < 0.15:
                penalty = 1 * size_multiplier
            else:
                state.violation_count = max(0, state.violation_count - 2)
                penalty = 0

            state.violation_count += penalty

            # הגעה לרף חסימה קשיחה
            if state.violation_count >= 6:
                state.last_error_code = MsgCodes.ACCESS_DENIED
                state.cooldown_until = now + 600
                return MsgCodes.ACCESS_DENIED, 600, False

            # הגעה לרף אזהרת רשת זמנית
            elif state.violation_count >= 1:
                state.last_error_code = MsgCodes.FLOOD_WARNING
                freeze_duration = int(state.violation_count * 5)
                state.cooldown_until = now + freeze_duration
                return MsgCodes.FLOOD_WARNING, freeze_duration, False

            return None, 0, False

    def check_flood_and_spam(self, ip, current_hash):
        """הגנת שכבת האפליקציה (Chat Logic) - מניעת הצפות טקסט, חפירות והודעות כפולות"""
        state = self._get_or_create_state(ip)

        with state.lock:
            now = time.time()

            # בדיקה האם המשתמש מושתק כרגע ברמת האפליקציה
            if now < state.spam_cooldown_until:
                remaining = int(state.spam_cooldown_until - now)
                return MsgCodes.FLOOD_WARNING, remaining

            # 1. מניעת שליחת הודעות זהות ברצף (Spam Bot / כפתור תקוע)
            if current_hash == state.last_msg_hash:
                state.dupe_count += 1
                if state.dupe_count >= 10:
                    state.spam_cooldown_until = now + 60  # השתקה לדקה אחת
                    state.last_error_code = MsgCodes.FLOOD_WARNING
                    return MsgCodes.FLOOD_WARNING, 60
            else:
                state.last_msg_hash = current_hash
                state.dupe_count = 1

            # 2. הגבלת כמות הודעות כללית בדקה (חלון זמן מתגלגל)
            if now > state.window_end:
                state.msg_count = 0
                state.window_end = now + 60

            state.msg_count += 1
            if state.msg_count > 20:
                state.spam_cooldown_until = now + 10  # השתקה זמנית ל-10 שניות
                state.last_error_code = MsgCodes.FLOOD_WARNING
                return MsgCodes.FLOOD_WARNING, 10

            return None, 0

    def report_email_request(self, email):
        """ניהול והגבלת בקשות קוד אימות (OTP) לנמען דואר אלקטרוני"""
        with self.monitor_lock:
            now = time.time()
            if email not in self._email_states:
                self._email_states[email] = {'attempts': 1, 'cooldown': 0, 'last_activity': now}
                return None

            status = self._email_states[email]
            status['last_activity'] = now  # עדכון שהאימייל בשימוש פעיל

            if now < status['cooldown']:
                return int(status['cooldown'] - now)

            status['attempts'] += 1

            # חסימת שליחת מיילים חוזרים לאחר 3 ניסיונות רצופים
            if status['attempts'] > 3:
                status['cooldown'] = now + 300  # חסימה ל-5 דקות
                status['attempts'] = 0
                return 300

            return None

    def process_new_connection(self, ip):
        """ניהול שלבי לחיצת היד (Handshake) הראשוניים בחיבור ה-Socket"""
        state = self._get_or_create_state(ip)

        with state.lock:
            now = time.time()

            if now < state.cooldown_until:
                state.violation_count += 1

                # אם ה-IP מנסה לפתוח סוקטים מרובים בזמן חסימה - התעלמות מוחלטת
                if state.violation_count > 10:
                    return 'SILENT_DROP', 0

                remaining = int(state.cooldown_until - now)
                return state.last_error_code, max(0, remaining)

            return None, 0



class MsgDispatcher:
    def __init__(self, send_func, traffic_monitor):
        self.send_func = send_func
        self.traffic_monitor = traffic_monitor
        self._handlers={}

    def handle(self, client, data_json):
        print(data_json)

        msg_type = data_json.get(Contract.TYPE)
        payload = data_json.get(Contract.DATA)

        policy_action = self._check_policy(client, msg_type, payload)


        if policy_action.response:
            self.send_func(client.sock, policy_action.response)

        if policy_action.should_block:
            client.pending_disconnect=True

        if policy_action.stop_processing:
            return


        handler = self._handlers.get(msg_type)

        if not handler:
            self.send_func(client.sock, ResponseFactory.error(msg_type= msg_type, code= MsgCodes.NOT_FOUND))
            return

        if not Validator.validate_structure(msg_type, payload):
            self.send_func(client.sock, ResponseFactory.error(msg_type=msg_type, code= MsgCodes.INVALID_FIELDS))
            return
        try:
            response = handler(client, payload)
            print(f"DEBUG: result is {response}")
            if response:
                self.send_func(client.sock, response)

            print(client.background_tasks)
            for task_func, task_args in client.background_tasks:
                t = threading.Thread(target=task_func, args=task_args)
                t.daemon = True
                t.start()
            client.background_tasks = []
        except Exception as e:
            print("-" * 30)
            print(f"Logic Error in {msg_type}:")
            traceback.print_exc()
            print("-" * 30)
            print(f"Logic Error: {e}")
            self.send_func(client.sock, ResponseFactory.error(msg_type, MsgCodes.INTERNAL_SERVER_ERROR))

    def _check_policy(self, client, msg_type, payload):
        ip = client.addr[0]

        if payload is None:
            payload = {}

        clean_payload = {
            k: (v.strip() if isinstance(v, str) else v)
            for k, v in payload.items()
            if k not in (Contract.NONCE, Contract.TIMESTAMP)
        }

        payload_str = json.dumps(clean_payload, sort_keys=True)
        combined_content = f"{msg_type}:{payload_str}"
        current_hash = hashlib.md5(combined_content.encode()).hexdigest()

        error_code, freeze_time = self.traffic_monitor.check_flood_and_spam(ip, current_hash)
        if error_code:
            return PolicyAction(
                response=ResponseFactory.error(msg_type, error_code, {Contract.EXPIRY: freeze_time}),
                stop_processing=True,
                wait_time=freeze_time
            )

        return PolicyAction()


    def register(self, msg_type , handler):
        self._handlers[msg_type]=handler


class Client:
    __slots__ = ['sock', 'addr', 'authenticated', 'expected_len',
                 'incoming_buffer', 'outgoing_buffer', 'send_queue',
                 'role', 'is_admin', 'user_info', 'display_name', 'p_id',
                 'auth_bundle', 'db_id', 'background_tasks', 'pending_disconnect',
                 'protocol'] # <-- הוספנו את protocol במקום cipher

    def __init__(self, sock, addr):
        self.protocol = MessageProtocol() # אתחול הפרוטוקול ללקוח הספציפי
        self.sock = sock
        self.addr = addr

        # מצב התקשורת
        self.expected_len = 0
        self.incoming_buffer = b''
        self.outgoing_buffer = b''
        self.send_queue = queue.Queue()

        # מצב לוגי
        self.authenticated = False
        self.pending_disconnect=False
        self.role = None
        self.is_admin = None

        self.user_info = {}
        self.display_name=None
        self.background_tasks=[]
        self.auth_bundle = None
        self.db_id = None
        self.p_id=None

    @property
    def role_config(self):
        if self.role:
            return UserRole.get_role_config(self.role)
        return None

    def authorized(self, user_record):
        self.auth_bundle = None
        self.user_info = user_record
        self.authenticated = True

        self.role = user_record.get(Contract.ROLE)
        self.p_id = user_record.get(Contract.PUBLIC_ID)
        self.display_name = user_record.get(Contract.DISPLAY_NAME)

    def reset_auth(self):
        """מנקה את הזהות הלוגית של המשתמש ומשאירה את ערוץ ההצפנה פתוח"""
        self.authenticated = False
        self.role = None
        self.is_admin = None
        self.user_info = {}
        self.display_name = None
        self.p_id = None
        self.auth_bundle = None
        self.db_id = None

    def __repr__(self):
        return f"<Client {self.addr} | Authenticated: {self.authenticated}>"

class AuthHandler:

    def __init__(self, db, email_service, send_func, auth_func, traffic_monitor, on_logout_callback):
        self.db = db
        self.email_service = email_service
        self.send= send_func
        self.on_auth_success_callback = auth_func
        self.traffic_monitor = traffic_monitor
        self.on_logout_callback = on_logout_callback

        self._auth_finalize_actions = {
            MsgType.SIGNUP: self._finalize_signup,
            MsgType.LOGIN: self._finalize_login,
            MsgType.FORGOT_PASSWORD: self._finalize_login
        }
    
    
    
    def process_sign_up(self, client, payload):
        role_label = payload.get(Contract.ROLE)
        identifier = payload.get(Contract.IDENTITY)
        password = payload.get(Contract.PASSWORD)
        email = payload.get(Contract.EMAIL)

        validation_type = Contract.USERNAME if role_label == UserRole.STANDARD else Contract.ID

        is_valid = (
                Validator.is_valid_field(validation_type, identifier) and
                Validator.is_valid_field(Contract.PASSWORD, password) and
                Validator.is_valid_field(Contract.EMAIL, email)
        )

        if not is_valid:
            return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.INVALID_FIELDS)

        if self.db.user_exists(identifier):
            return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.USER_ALREADY_EXISTS)

        if role_label in [UserRole.STUDENT, UserRole.TEACHER]:
            pre_approved_name = self.db.get_verified_educational_name(identifier, role_label)

            if not pre_approved_name:
                print(
                    f"[Security Alert] Identity {identifier} tried to register as {role_label} but is not pre-approved.")
                return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.ACCESS_DENIED)

            payload[Contract.DISPLAY_NAME] = pre_approved_name
        else:
            payload[Contract.DISPLAY_NAME] = identifier

        return self._handle_otp_flow(client, payload, MsgType.SIGNUP, email)

    def generate_otp_session(self, client, user_data, purpose, email, is_resend=False):
        otp_code = OTPService.generate_code()

        current_attempts = 0
        if is_resend and client.auth_bundle:
            current_attempts = client.auth_bundle.get(Contract.ATTEMPTS, 0)

        client.auth_bundle = {
            Contract.DATA: user_data,
            Contract.EMAIL: email,
            Contract.OTP_CODE: otp_code,
            Contract.EXPIRY: time.time() + 600,
            Contract.PURPOSE: purpose,
            Contract.ATTEMPTS: current_attempts
        }


        client.background_tasks.append((self.email_service.send_otp, (email, otp_code)))
        return ResponseFactory.create(msg_type=MsgType.RESEND_OTP if is_resend else purpose, code=MsgCodes.OTP_RESENT if is_resend else MsgCodes.OTP_SENT, raw_data={Contract.EMAIL: email, Contract.ATTEMPTS: current_attempts})


    def _handle_otp_flow(self, client, user_data, purpose, email, is_resend=False):

        remaining_lock = self.traffic_monitor.report_email_request(email)
        if remaining_lock:
            return ResponseFactory.error(
                MsgType.RESEND_OTP if is_resend else purpose,
                MsgCodes.BLOCKED_EMAIL,
            )

        return self.generate_otp_session(
            client, user_data, purpose, email,
            is_resend=is_resend
        )

    def process_resend_otp(self, client, payload):
        pending_info = client.auth_bundle

        if not pending_info:
            return ResponseFactory.error(code=MsgCodes.SESSION_EXPIRED)


        email = pending_info.get(Contract.EMAIL)
        purpose = pending_info.get(Contract.PURPOSE)
        user_data = pending_info.get(Contract.DATA)
        return self._handle_otp_flow(client, user_data, purpose, email, is_resend=True)

    def verify_email(self, client, data):
        pending_info = client.auth_bundle

        if not pending_info:
            return ResponseFactory.error(code=MsgCodes.SESSION_EXPIRED)

        purpose = pending_info.get(Contract.PURPOSE)

        if time.time() > pending_info[Contract.EXPIRY]:
            client.auth_bundle = None
            return ResponseFactory.error(purpose, MsgCodes.SESSION_EXPIRED)

        user_code = data.get(Contract.OTP_CODE)
        print(f'aaaaa{data}')
        correct_code = pending_info.get(Contract.OTP_CODE)
        print(correct_code, user_code)
        if user_code != correct_code:
            pending_info[Contract.ATTEMPTS] += 1
            if pending_info[Contract.ATTEMPTS] >= 3:
                client.auth_bundle = None
                return ResponseFactory.error(purpose, MsgCodes.SESSION_EXPIRED)

            return ResponseFactory.error(purpose, MsgCodes.INVALID_OTP, raw_data={Contract.EMAIL: client.auth_bundle.get(Contract.EMAIL, ''), Contract.ATTEMPTS: pending_info.get(Contract.ATTEMPTS,0)})

        purpose = pending_info.get(Contract.PURPOSE)
        action_func = self._auth_finalize_actions.get(purpose)

        if action_func:
            return action_func(client)


        client.auth_bundle = None
        return ResponseFactory.error(purpose, MsgCodes.INTERNAL_SERVER_ERROR)

    def _finalize_signup(self, client):
        user_data = client.auth_bundle.get(Contract.DATA)
        role_label = user_data.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)

        identifier = user_data.get(Contract.IDENTITY)
        password = user_data.get(Contract.PASSWORD)
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        email = user_data.get(Contract.EMAIL)

        display_name = user_data.get(Contract.DISPLAY_NAME)

        session_token = os.urandom(16).hex()
        p_id = os.urandom(24).hex()

        final_user_record =  self.db.register_user(role_config, identifier, hashed_password, email, p_id, session_token, display_name)


        if final_user_record:
            final_user_record[Contract.ROLE] = role_label
            return self._complete_auth_flow(client, final_user_record, MsgType.SIGNUP)

        return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.USER_ALREADY_EXISTS)

    def process_login(self, client, payload):
        identifier = payload.get(Contract.IDENTITY)
        password = payload.get(Contract.PASSWORD)

        user_record = self.db.authenticate_user(identifier, password)
        if user_record:
            if user_record[Contract.ROLE] != payload.get(Contract.ROLE):
                return ResponseFactory.error(msg_type=MsgType.LOGIN, code=MsgCodes.INVALID_FIELDS)
            client.auth_bundle = {Contract.DATA: user_record}
            return self._finalize_login(client)

        return ResponseFactory.error(MsgType.LOGIN, MsgCodes.INVALID_FIELDS)

    def process_forgot_password(self, client, payload):
        email = payload.get(Contract.EMAIL)

        if email:

            user_record = self.db.get_user_by_email(email)

            if user_record:
                return self.generate_otp_session(
                    client,
                    user_record,
                    MsgType.FORGOT_PASSWORD,
                    email
                )

        return ResponseFactory.error(MsgType.FORGOT_PASSWORD, MsgCodes.INVALID_FIELDS)

    def _finalize_login(self, client):
        user_record = client.auth_bundle.get(Contract.DATA)

        if user_record:
            return self._complete_auth_flow(client, user_record, MsgType.LOGIN)


        return ResponseFactory.error(MsgType.LOGIN, MsgCodes.DATABASE_ERROR)

    def reconnect(self, client, payload):
        token= payload.get(Contract.TOKEN)
        if token:
            user_info = self.db.get_user_by_token(token)

            if user_info:
                return self._complete_auth_flow(client, user_info, MsgType.RECONNECT)

        return ResponseFactory.error(MsgType.RECONNECT, MsgCodes.SESSION_EXPIRED)

    def _complete_auth_flow(self, client, user_record, msg_type):
        p_id = user_record[Contract.PUBLIC_ID]

        if msg_type in [MsgType.LOGIN, MsgType.RECONNECT]:
            new_session_token = os.urandom(16).hex()
            updated_record = self.db.update_user_token(p_id, new_session_token)
            if updated_record:
                user_record.update(updated_record)

        client.db_id = user_record.pop(Contract.ID)
        client.authorized(user_record)

        self.on_auth_success_callback(p_id, client.sock)

        print(user_record)
        return ResponseFactory.create(msg_type=msg_type, raw_data=user_record, code=MsgCodes.SUCCESS)

    def process_bulk_upload(self, client, payload):
        if client.role_config != UserRole.TEACHER and client.is_admin:
            return ResponseFactory.error(MsgType.AUTH_UPLOAD, MsgCodes.NO_PERMISSION)

        users_list = payload.get(Contract.ITEMS, [])
        if not users_list:
            return ResponseFactory.error(MsgType.AUTH_UPLOAD, MsgCodes.INVALID_FIELDS)

        success = self.db.bulk_add_authorized_users(users_list)

        if success:
            return ResponseFactory.create(MsgType.AUTH_UPLOAD, MsgCodes.SUCCESS)
        else:
            return ResponseFactory.error(MsgType.AUTH_UPLOAD, MsgCodes.DATABASE_ERROR)

    def process_logout(self, client, payload):
        if not client.authenticated:
            return None

        print(f"[AuthHandler] Processing secure logout for {client.display_name} ({client.p_id})")

        # 1. ביטול הטוקן בבסיס הנתונים (מונע שימוש חוזר בטוקן שנגנב)
        if client.p_id:
            self.db.update_user_token(client.p_id, None)

        if self.on_auth_success_callback:
            self.on_logout_callback(client.p_id)

        # 3. איפוס האובייקט בעזרת הפונקציה שיצרנו
        client.reset_auth()

        return None

server = Server()
try:
    server.run()
except KeyboardInterrupt:
    print('server stopped')
finally:
    server.close()