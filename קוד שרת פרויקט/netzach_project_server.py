import socket
import queue
import json
import select

import os
from AIHandler import AIHandler
import hashlib
import DATABASE
from EmailService import EmailService
from ChatService import *
from Protocol import *
import time
import threading
import traceback


class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST= '0.0.0.0'
        self.PORT= 8820

        self.server.bind((self.HOST, self.PORT))
        self.server.listen()
        self.server.setblocking(False)

        self.db= DATABASE.Database()
        self.email_service = EmailService("Netzach.GUETA@gmail.com", "euhizienenibsako")

        self.ai_handler = AIHandler(api_key="AIzaSyBjGP_jGnfQu7AUvkGWavGtS6xCNg0fsMw", db= self.db)
        self.chat_manager = ChatManager(self.db, self.ai_handler, self.send_to_client)



        self.clients={}
        self.online_users= {}

        self.traffic_monitor = TrafficMonitor()
        self.msg_dispatcher = MsgDispatcher(self.send_to_client,  self.traffic_monitor)

        self.auth_handler= AuthHandler(self.db, self.email_service, self.send_to_client, self.on_user_authenticated, self.traffic_monitor)

        self._handlers={
            MsgType.LOGIN: self.auth_handler.process_login,
            MsgType.FORGOT_PASSWORD: self.auth_handler.process_forgot_password,
            MsgType.SIGNUP: self.auth_handler.process_sign_up,
            MsgType.VERIFY_OTP: self.auth_handler.verify_email,
            MsgType.RESEND_OTP: self.auth_handler.process_resend_otp,
            MsgType.RECONNECT: self.auth_handler.reconnect,
            MsgType.SEND_MSG: self.chat_manager.process_new_message,
            MsgType.JOIN_ROOM: self.chat_manager.add_user_to_room,
            MsgType.CREATE_CHAT_ROOM: self.chat_manager.create_new_room,

        }
        self.setup_handlers()



    def setup_handlers(self):
        for k, v in self._handlers.items():
            self.msg_dispatcher.register(k, v)

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
                client = self.clients[sock]
                self.write_to_client(sock, client)

    def new_connection(self):
        try:
            client_socket, addr = self.server.accept()
            ip = addr[0]
            client_socket.setblocking(False)
            client = Client(client_socket, addr)
            self.clients[client_socket] = client

            error_code, freeze_time = self.traffic_monitor.process_new_connection(ip)

            if error_code:
                is_silent = (error_code=='SILENT_DROP')
                if is_silent:
                    self.handle_disconnect(client_socket)
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
            chunk= sock.recv(1024)

            if not chunk:
                self.handle_disconnect(sock)

            else:
                client.incoming_buffer += chunk
                available_data= True

                while available_data:
                    if client.expected_len==0:

                        if len(client.incoming_buffer)>= 4:
                            client.expected_len= int.from_bytes(client.incoming_buffer[:4], 'big')
                            client.incoming_buffer= client.incoming_buffer[4:]

                            if client.expected_len > MAX_MSG_SIZE:
                                print(f"[!] Warning: Client {client.addr} sent huge length: {client.expected_len}")
                                self.handle_disconnect(sock, "Message too large")
                                return


                        else:
                            available_data=False
                            continue

                    if len(client.incoming_buffer)>= client.expected_len:
                        ip = client.addr[0]
                        action, freeze = self.traffic_monitor.process_new_message(ip)

                        if action:
                            client.incoming_buffer = client.incoming_buffer[client.expected_len:]
                            client.expected_len = 0
                            self.handle_penalty(client, action, freeze)
                            return

                        data_bytes= client.incoming_buffer[:client.expected_len]
                        client.incoming_buffer = client.incoming_buffer[client.expected_len:]
                        client.expected_len = 0


                        try:
                            self.handle_client(sock, data_bytes)

                        except Exception as e:
                            print('Invalid data from:', client.addr, e)

        except Exception as e:
            self.handle_disconnect(sock,e)

    def handle_penalty(self, client, action, freeze):

        error_res = ResponseFactory.error(MsgType.GENERAL, action, {Contract.EXPIRY: freeze})
        self.send_to_client(client.sock, error_res)

        if action == MsgCodes.ACCESS_DENIED:
            client.pending_disconnect = True

        return True



    def handle_client(self, sock, data_bytes):
        client = self.clients.get(sock)
        if client:
            self.msg_dispatcher.handle(client, data_bytes)

    def write_to_client(self, sock,client):

        try:
            if client.outgoing_buffer:
                sent = sock.send(client.outgoing_buffer)
                client.outgoing_buffer = client.outgoing_buffer[sent:]

            elif not client.send_queue.empty():
                    data = client.send_queue.get()
                    bytes_data = json.dumps(data).encode('utf-8')
                    full_msg= len(bytes_data).to_bytes(4, 'big') +  bytes_data

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

    def handle_disconnect(self, sock, error=None):
        client = self.clients.pop(sock, None)

        if not client:
            return

        addr = client.addr

        p_id = client.p_id
        if p_id and p_id in self.online_users:
            print(f"[Routing] Removing {p_id} from online_users")
            del self.online_users[p_id]

        print(f"Client {addr} disconnected. Reason: {error if error else 'Cleanly'}")


        try:
            sock.close()
        except Exception:
            pass

    def on_user_authenticated(self, p_id, sock):
        self.online_users[p_id] = sock
        print(f"[Routing] User {p_id} registered.")
        client = self.clients.get(sock)
        if client:
            self.chat_manager.sync_user_rooms(client)

    def sync_user_rooms(self, client):
        rooms_data = self.db.get_user_rooms(client.p_id)

        sync_msg = ResponseFactory.create(
            msg_type=MsgType.SYNC_DATA,
            code=MsgCodes.SUCCESS,
            raw_data={"rooms": rooms_data}
        )

        self.send_to_client(client.sock, sync_msg)

    def close(self):
        self.db.cursor.close()
        self.db.conn.commit()
        self.db.conn.close()

class TrafficMonitor:
    def __init__(self, penalty_threshold=5):
        self._states = {}
        self._email_states = {}
        self.PENALTY_THRESHOLD = penalty_threshold

    def _get_or_create_state(self, ip):
        if ip not in self._states:
            self._states[ip] = SecurityState()
        return self._states[ip]

    def process_new_connection(self, ip):
        state = self._get_or_create_state(ip)
        now = time.time()


        if now < state.cooldown_until:
            state.violation_count += 1

            if state.violation_count > 10:
                return 'SILENT_DROP', 0

            remaining = int(state.cooldown_until - now)
            return state.last_error_code, max(0, remaining)

        return None, 0


    def process_new_message(self, ip):
        state = self._get_or_create_state(ip)
        now = time.time()

        if now < state.cooldown_until:
            return MsgCodes.ACCESS_DENIED, 600

        time_passed = now - max(state.last_msg_sent_at, state.cooldown_until)
        state.last_msg_sent_at = now

        if time_passed > 30:
            state.violation_count = 0
            state.last_error_code = None
            return None, 0

        if time_passed < 0.02:
            penalty = 6
        elif time_passed < 0.5:
            penalty = 1
        else:
            state.violation_count = max(0, state.violation_count - 2)
            penalty = 0

        state.violation_count += penalty

        if state.violation_count >= 6:
            state.last_error_code = MsgCodes.ACCESS_DENIED
            state.cooldown_until = now + 600
            return MsgCodes.ACCESS_DENIED, 600

        elif state.violation_count >= 1:
            state.last_error_code = MsgCodes.FLOOD_WARNING
            freeze_duration = int(state.violation_count * 5)
            state.cooldown_until = now + freeze_duration
            return MsgCodes.FLOOD_WARNING, freeze_duration

        return None, 0

    def check_flood_and_spam(self, ip, current_hash):
        state = self._get_or_create_state(ip)
        now = time.time()

        if current_hash == state.last_msg_hash:
            state.dupe_count += 1
            if state.dupe_count >= 10:
                state.cooldown_until = now + 60
                state.last_error_code= MsgCodes.FLOOD_WARNING
                return MsgCodes.FLOOD_WARNING, 60
        else:
            state.last_msg_hash = current_hash
            state.dupe_count = 1

        if now > state.window_end:
            state.msg_count = 0
            state.window_end = now + 60

        state.msg_count += 1
        if state.msg_count > 20:
            state.cooldown_until = now + 10
            state.last_error_code= MsgCodes.FLOOD_WARNING
            return MsgCodes.FLOOD_WARNING, 10

        return None, 0

    def report_email_request(self, email):
        now = time.time()
        if email not in self._email_states:
            self._email_states[email] = {'attempts': 0, 'cooldown': 0}
            return None
        status = self._email_states[email]

        # 3. כאן ה-Remaining Lock יעבוד, כי הערך באמת קיים ב-email_states
        if now < status['cooldown']:
            return int(status['cooldown'] - now)

        status['attempts'] += 1

        if status['attempts'] > 3:
            status['cooldown'] = now + 300
            status['attempts'] = 0
            self._email_states[email] = status
            return 300
        self._email_states[email] = status
        return None

class SecurityState:
    def __init__(self):
        self.cooldown_until = 0    # Timestamp של מתי החסימה נגמרת
        self.violation_count = 0   # מונה: כמה הודעות הוא שלח בזמן שהיה חסום
        self.last_error_code = None
        self.msg_count = 0
        self.dupe_count = 0
        self.window_end = 0
        self.last_msg_hash = None
        self.last_msg_sent_at = 0

class MsgDispatcher:
    def __init__(self, send_func, traffic_monitor):
        self.send_func = send_func
        self.traffic_monitor = traffic_monitor
        self._handlers={}

    def handle(self, client, data_bytes):
        data_str = data_bytes.decode('utf-8')
        data_json = json.loads(data_str)
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
            self.send_func(client.sock, ResponseFactory.error(msg_type, MsgCodes.SERVER_ERROR))

    def _check_policy(self, client, msg_type, payload):
        ip = client.addr[0]

        if payload is None:
            payload= {}
        payload_str = json.dumps(payload, sort_keys=True)
        combined_content = f"{msg_type}:{payload_str}"
        current_hash = hashlib.md5(combined_content.encode()).hexdigest()

        error_code, freeze_time=  self.traffic_monitor.check_flood_and_spam(ip, current_hash)
        if error_code:
            return PolicyAction(
            response=ResponseFactory.error(msg_type, error_code, {Contract.EXPIRY: freeze_time}),
            stop_processing=True,
            wait_time=freeze_time)

        return PolicyAction()


    def register(self, msg_type , handler):
        self._handlers[msg_type]=handler


class Client:
    __slots__ = ['sock', 'addr', 'authenticated', 'expected_len',
                 'incoming_buffer', 'outgoing_buffer', 'send_queue',
                 'role', 'user_info', 'display_name', 'p_id', 'auth_bundle', 'background_tasks', 'pending_disconnect']

    def __init__(self, sock, addr):
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

        self.user_info = {}
        self.display_name=None
        self.background_tasks=[]
        self.auth_bundle = None

    def authorized(self, user_record):
        self.auth_bundle = None
        self.user_info = user_record
        self.authenticated = True

        self.role = user_record.get(Contract.ROLE)
        self.p_id = user_record.get(Contract.PUBLIC_ID)
        self.display_name = user_record.get(Contract.DISPLAY_NAME)

    def __repr__(self):
        return f"<Client {self.addr} | Authenticated: {self.authenticated}>"

class AuthHandler:

    def __init__(self, db, email_service, send_func, auth_func, traffic_monitor):
        self.db = db
        self.email_service = email_service
        self.send= send_func
        self.on_auth_success_callback = auth_func
        self.traffic_monitor = traffic_monitor

        # הגדרת המיפוי פעם אחת ב-Constructor
        self._auth_finalize_actions = {
            MsgType.SIGNUP: self._finalize_signup,
            MsgType.LOGIN: self._finalize_login  # <--- הנתיב החדש
        }


    def process_sign_up(self, client, payload):
        role_label = payload.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)

        if role_config != UserRole.STANDARD:
            return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.INVALID_FIELDS)

        identifier = payload.get(Contract.IDENTITY)
        password = payload.get(Contract.PASSWORD)
        email = payload.get(Contract.EMAIL)
        is_valid = (
                Validator.is_valid_field(role_config.id_field, identifier) and
                Validator.is_valid_field(Contract.PASSWORD, password) and
                Validator.is_valid_field(Contract.EMAIL, email)  # תוקן מ-identifier ל-email
        )

        if not is_valid:
            return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.INVALID_FIELDS)

        if self.db.user_exists(role_config, identifier):
            return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.USER_ALREADY_EXISTS)

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
        return ResponseFactory.error(purpose, MsgCodes.SERVER_ERROR)

    def _finalize_signup(self, client):
        user_data = client.auth_bundle.get(Contract.DATA)
        role_label = user_data.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)

        identifier = user_data.get(Contract.IDENTITY)
        password = user_data.get(Contract.PASSWORD)
        email = user_data.get(Contract.EMAIL)

        session_token = os.urandom(16).hex()
        p_id = os.urandom(24).hex()

        final_user_record =  self.db.register_user(role_config, identifier, password, email, p_id, session_token)
        print('wow', final_user_record)
        if final_user_record:
            final_user_record[Contract.ROLE] = role_label
            if final_user_record:
                final_user_record[Contract.ROLE] = role_label
                return self._complete_auth_flow(client, final_user_record, MsgType.SIGNUP, MsgCodes.SIGNUP_SUCCESS)

        return ResponseFactory.error(MsgType.SIGNUP, MsgCodes.USER_ALREADY_EXISTS)

    def process_login(self, client, payload):
        identifier = payload.get(Contract.IDENTITY)
        password = payload.get(Contract.PASSWORD)
        role_label = payload.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)
        print(payload)
        if not role_config:
            return ResponseFactory.error(MsgType.LOGIN, MsgCodes.INVALID_FIELDS)


        user_record = self.db.authenticate_user(role_config, identifier, password)
        if user_record:

            user_record[Contract.ROLE] = role_label
            client.auth_bundle = {Contract.DATA: user_record}
            return self._finalize_login(client)

        return ResponseFactory.error(MsgType.LOGIN, MsgCodes.INVALID_FIELDS)


    def process_forgot_password(self, client, data):
        payload = data.get(Contract.DATA, {})
        email = payload.get(Contract.EMAIL)
        role_label = payload.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)

        if role_config!= UserRole.STANDARD:
            return ResponseFactory.error(MsgType.FORGOT_PASSWORD, MsgCodes.INVALID_FIELDS)

        if email:
            user_record = self.db.get_user_by_email(role_config, email)

            if user_record:

                user_record[Contract.ROLE] = role_label
                return self.generate_otp_session(
                    client,
                    user_record,
                    MsgType.FORGOT_PASSWORD,
                    email
                )


            return ResponseFactory.error(MsgType.FORGOT_PASSWORD, MsgCodes.INVALID_FIELDS)


        return ResponseFactory.error(MsgType.FORGOT_PASSWORD, MsgCodes.INVALID_FIELDS)

    def _finalize_login(self, client):
        user_record = client.auth_bundle.get(Contract.DATA)
        role_label = user_record.get(Contract.ROLE)

        user_record[Contract.ROLE] = role_label
        if user_record:
            user_record[Contract.ROLE] = role_label
            return self._complete_auth_flow(client, user_record, MsgType.LOGIN, MsgCodes.LOGIN_SUCCESS)


        return ResponseFactory.error(MsgType.LOGIN, MsgCodes.DATABASE_ERROR)

    def reconnect(self, client, payload):
        token= payload.get(Contract.TOKEN)
        role_label = payload.get(Contract.ROLE)
        if role_label and token:
            role_config = UserRole.get_role_config(role_label)
            user_info = self.db.get_user_by_token(role_config, token)

            if user_info:
                user_info[Contract.ROLE] = role_label
                return self._complete_auth_flow(client, user_info, MsgType.RECONNECT, MsgCodes.LOGIN_SUCCESS)

        return ResponseFactory.error(MsgType.RECONNECT, MsgCodes.SESSION_EXPIRED)

    def _complete_auth_flow(self, client, user_record, msg_type, msg_code):
        role_label = user_record.get(Contract.ROLE)
        role_config = UserRole.get_role_config(role_label)
        p_id = user_record[Contract.PUBLIC_ID]

        if msg_type in [MsgType.LOGIN, MsgType.RECONNECT]:
            new_session_token = os.urandom(16).hex()
            updated_record = self.db.update_user_token(role_config, p_id, new_session_token)
            if updated_record:
                user_record.update(updated_record)

        user_record[Contract.ROLE] = role_label

        if Contract.DISPLAY_NAME not in user_record:
            display_val = user_record.get(role_config.display_name, 'Guest')
            user_record[Contract.DISPLAY_NAME] = display_val

        client.authorized(user_record)

        self.on_auth_success_callback(p_id, client.sock)


        # שליחת התשובה הסופית
        return ResponseFactory.create(msg_type=msg_type, raw_data=user_record, code=msg_code)


server = Server()
try:
    server.run()
except KeyboardInterrupt:
    print('server stopped')
finally:
    server.close()