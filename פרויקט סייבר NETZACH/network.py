import socket
import select
import threading
from network_infra import MessageProtocol
import time
import queue
import pyaudio

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet

from app_constants import MsgType, MsgCodes, Contract, StateKey
from MediaProtocol import *

class Server_Communicator(threading.Thread):
    def __init__(self, server_ip, server_port, user_state, msg_manager):
        super().__init__()

        self.sock_manager = SocketManager(server_ip, server_port)
        self.protocol = MessageProtocol()
        self.user_state = user_state
        self.msg_manager = msg_manager
        self.max_to_read = 1024
        self.expected_length = 0
        self.outgoing_buffer = b''
        self.incoming_buffer = b''

    def run(self):

        while self.user_state.get_state(StateKey.IS_ACTIVE):

            if self.msg_manager.is_banned.is_set():
                time.sleep(1)
                continue

            sock = self.sock_manager.try_connect()

            if sock:
                self._handle_connect_success()
                try:
                    self.maintain_connection(sock)
                except Exception as e:
                    print(f"Connection error: {e}")
                finally:
                    self._handle_disconnect()
            else:
                time.sleep(1)

    def write_to_server(self, sock):
        try:
            if not self.outgoing_buffer:
                msg_dict = self.msg_manager.get_next_outbound()
                if msg_dict:
                    self.outgoing_buffer = self.protocol.pack(msg_dict)
                    print('A')

            if self.outgoing_buffer:
                sent = sock.send(self.outgoing_buffer)
                self.outgoing_buffer = self.outgoing_buffer[sent:]
        except Exception as e:
            self.user_state.set_state(StateKey.CONNECTED, False)
            raise e

    def _handle_connect_success(self):
        self.msg_manager.incoming_queue.put({
            Contract.TYPE: MsgType.SYSTEM,
            Contract.CODE: MsgCodes.CONNECTION_ESTABLISHED,
            "update_state": {
                StateKey.CONNECTED: True,
            }
        })
        print('Connected Successfully')

    def maintain_connection(self, sock):
        while self.user_state.get_state(StateKey.IS_ACTIVE):
            r_list, w_list, _ = select.select([sock], [sock], [], 0.1)

            if sock in r_list:
                self.read_from_server(sock)

            if w_list:
                self.write_to_server(sock)

    def read_from_server(self, sock):
        try:
            chunk = sock.recv(self.max_to_read)
            if not chunk:
                raise ConnectionError

            else:
                self.incoming_buffer += chunk

                available_data = True
                while self.user_state.get_state(StateKey.IS_ACTIVE) and available_data:
                    if self.expected_length == 0:
                        if len(self.incoming_buffer) >= 4:
                            self.expected_length = int.from_bytes(self.incoming_buffer[:4], 'big')
                            self.incoming_buffer = self.incoming_buffer[4:]
                        else:
                            available_data = False
                            continue

                    if len(self.incoming_buffer) >= self.expected_length:
                        try:
                            raw_data = self.protocol.unpack(self.incoming_buffer[:self.expected_length])
                            print(raw_data)
                            print(f"[Network] Received: {raw_data}")

                            # --- התיקון: ניתוב חכם לפי KEY_EXCHANGE ---
                            msg_type = raw_data.get(Contract.TYPE)
                            msg_code = raw_data.get(Contract.CODE)

                            if msg_type == MsgType.KEY_EXCHANGE:
                                if msg_code == MsgCodes.RSA_KEY:
                                    public_key_pem = raw_data.get(Contract.DATA).get("public_key").encode('utf-8')
                                    self._handle_rsa_handshake(sock, public_key_pem)

                                elif msg_code == MsgCodes.SUCCESS:
                                    print("[Security] Handshake confirmed by server. Connection is fully secure.")
                                    self.msg_manager.incoming_queue.put({
                                        Contract.TYPE: MsgType.SYSTEM,
                                        Contract.CODE: MsgCodes.SUCCESS,
                                        Contract.DATA: {
                                            "update_state": {
                                                StateKey.HANDSHAKE_ESTABLISHED: True,
                                            }
                                        }
                                    })
                            else:
                                self.msg_manager.incoming_queue.put(raw_data)

                            self.incoming_buffer = self.incoming_buffer[self.expected_length:]
                            self.expected_length = 0

                        except Exception as e:
                            print(f"Protocol Error (JSON): {e}")

                            # הדפסת דיבאג שתגלה לנו מה השרת שלח שגרם לקריסה!
                            corrupted_data = self.incoming_buffer[:self.expected_length]
                            print(f"[DEBUG] Raw bytes that failed: {corrupted_data}")

                            # התיקון: חובה למחוק את החבילה הפגומה ולאפס את האורך כדי לעצור את הלופ האינסופי
                            self.incoming_buffer = self.incoming_buffer[self.expected_length:]
                            self.expected_length = 0

                            # מאחר שזו שגיאת הצפנה/פרוטוקול, הערוץ יצא מסנכרון. ננתק כדי להתחבר מחדש בצורה נקייה.
                            raise ConnectionError("Stream corrupted or decryption failed.")
                    else:
                        available_data = False
        except Exception as e:
            raise e

    def _handle_disconnect(self):
        self.sock_manager.close()

        self.incoming_buffer = b''
        self.outgoing_buffer = b''
        self.expected_length = 0

        self.msg_manager.is_authorized.clear()

        self.protocol.cipher = None

        self.msg_manager.clear_outgoing_queue()

        self.msg_manager.incoming_queue.put({
            Contract.TYPE: MsgType.SYSTEM,
            Contract.CODE: MsgCodes.CONNECTION_LOST,
            Contract.DATA: {
                "update_state": {
                    StateKey.CONNECTED: False,
                    StateKey.HANDSHAKE_ESTABLISHED: False,
                }
            }
        })
        print('server disconnected')
        self.msg_manager.connection_active.clear()

        time.sleep(1)

    def _handle_rsa_handshake(self, sock, public_key_pem):
        # 1. טעינת המפתח הציבורי של השרת
        public_key = serialization.load_pem_public_key(public_key_pem)

        # 2. יצירת מפתח סשן מהיר (AES) משלנו
        session_key = Fernet.generate_key()

        # 3. הצפנת המפתח שלנו בעזרת ה-RSA של השרת כדי שרק השרת יוכל לקרוא אותו
        encrypted_session_key = public_key.encrypt(
            session_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

        msg_dict = {
            Contract.TYPE: MsgType.KEY_EXCHANGE,
            Contract.CODE: MsgCodes.SESSION_KEY,
            Contract.DATA: {
                "encrypted_key": encrypted_session_key.hex()
            }
        }

        # חובה לשלוח ישירות לסוקט *לפני* שמפעילים את ה-Fernet אצלנו!
        sock.send(self.protocol.pack(msg_dict))

        # 5. הדלקת ההצפנה בצד הלקוח - מכאן הכל מוצפן!
        self.protocol.set_session_key(session_key)
        print("[Security] Fernet key sent. Waiting for server confirmation...")

class SocketManager:
    def __init__(self, ip, port):
        self.address = (ip, port)
        self.sock = None

    def try_connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.address)
            return self.sock
        except Exception as e:
            return

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None


class MediaCommunicator(threading.Thread):
    # 🟢 סנכרון מלא של סדר הפרמטרים מול פאנל ה-GUI
    def __init__(self, server_ip, server_udp_port, room_id, frame_queue, udp_token, my_p_id):
        super().__init__(daemon=True, name="UDP-Media-Thread")

        self.server_address = (server_ip, server_udp_port)
        self.cipher_lock = threading.Lock()
        self.cipher = None
        self.room_id = room_id
        self.udp_token = udp_token
        self.my_p_id = my_p_id

        self.is_active = threading.Event()
        self.frame_queue = frame_queue

        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.settimeout(1.0)

        self.audio_queue = queue.Queue()
        self.pyaudio_instance = pyaudio.PyAudio()

        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000

        # משתנים לשמירת ת'רדי השמע לצורך סגירה בטוחה
        self.record_thread = None
        self.play_thread = None

    def update_media_key(self, new_media_key):
        with self.cipher_lock:
            self.cipher = Fernet(new_media_key)
        print(f"[Media Lock] Media cipher rotated successfully for room {self.room_id}")

    def _get_cipher(self):
        """ שליפה מהירה ואטומית של הציפר הנוכחי ללא חסימת תהליכי הסטרימינג """
        with self.cipher_lock:
            return self.cipher

    def _find_device_by_keyword(self, keywords, want_input):
        """
        מחפש device קלט/פלט שהשם שלו מכיל אחת ממילות המפתח (למשל אוזניות).
        מחזיר את האינדקס שלו, או None אם לא נמצא (ואז PyAudio ייפול לדיפולט).
        """
        try:
            for i in range(self.pyaudio_instance.get_device_count()):
                info = self.pyaudio_instance.get_device_info_by_index(i)
                name = info.get('name', '').lower()
                channels_key = 'maxInputChannels' if want_input else 'maxOutputChannels'

                if info.get(channels_key, 0) <= 0:
                    continue

                if any(kw in name for kw in keywords):
                    print(f"[Audio] Selected {'input' if want_input else 'output'} device: {info.get('name')}")
                    return i
        except Exception as e:
            print(f"[Audio] Device scan failed: {e}")
        return None

    def _get_output_device_index(self):
        # מתעדף אוזניות/headset על פני רמקול ברירת מחדל, כדי למנוע feedback למיקרופון
        return self._find_device_by_keyword(['headset', 'headphone', 'earphone'], want_input=False)

    def _get_input_device_index(self):
        return self._find_device_by_keyword(['headset', 'headphone', 'microphone array', 'mic'], want_input=True)

    def run(self):
        self.is_active.set()
        last_join_time = 0.0

        self.record_thread = threading.Thread(target=self._record_audio_loop, daemon=True, name="UDP-Audio-Record")
        self.play_thread = threading.Thread(target=self._play_audio_loop, daemon=True, name="UDP-Audio-Play")
        self.record_thread.start()
        self.play_thread.start()

        while self.is_active.is_set():
            try:
                current_cipher = self._get_cipher()
                if not current_cipher:
                    time.sleep(0.1)
                    continue

                now = time.time()
                if now - last_join_time > 3.0:
                    join_packet = MediaProtocol.pack(
                        pkt_type=MediaProtocol.TYPE_JOIN,
                        room_id=self.room_id,
                        sender_id=self.my_p_id,
                        payload=self.udp_token.encode('utf-8')
                    )
                    self.udp_sock.sendto(join_packet, self.server_address)
                    last_join_time = now

                data, addr = self.udp_sock.recvfrom(65535)
                pkt_type, r_id, sender_id, encrypted_payload = MediaProtocol.unpack(data)

                if pkt_type == MediaProtocol.TYPE_VIDEO:
                    try:
                        decrypted_frame = current_cipher.decrypt(encrypted_payload)
                        self.frame_queue.put((sender_id, decrypted_frame), block=False)
                    except queue.Full:
                        print('queue is full')
                    except Exception as e:
                        print(f"[CRITICAL Decrypt Error] {e}")

                elif pkt_type == MediaProtocol.TYPE_AUDIO:
                    try:
                        decrypted_audio = current_cipher.decrypt(encrypted_payload)
                        self.audio_queue.put((sender_id, decrypted_audio), block=False)
                    except queue.Full:
                        pass
                    except Exception:
                        pass

            except socket.timeout:
                continue
            except Exception:
                time.sleep(0.01)

    def send_media(self, raw_bytes):
        if self.is_active.is_set():
            try:
                current_cipher = self._get_cipher()
                if not current_cipher:
                    print("Cipher not initialized yet!")
                    return
                encrypted_payload = current_cipher.encrypt(raw_bytes)
                video_packet = MediaProtocol.pack(
                    pkt_type=MediaProtocol.TYPE_VIDEO,
                    room_id=self.room_id,
                    sender_id=self.my_p_id,
                    payload=encrypted_payload
                )

                self.udp_sock.sendto(video_packet, self.server_address)
            except Exception as e:
                print(e, 'AAAAAAAAAAAA')
                pass

    def _record_audio_loop(self):
        try:
            input_stream = self.pyaudio_instance.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=self._get_input_device_index(),
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            print(f"[Audio Error] Microphone failed: {e}")
            return

        while self.is_active.is_set():
            try:
                raw_audio = input_stream.read(self.CHUNK, exception_on_overflow=False)
                current_cipher = self._get_cipher()
                if not raw_audio or not current_cipher:
                    continue
                encrypted_audio = current_cipher.encrypt(raw_audio)
                audio_packet = MediaProtocol.pack(
                    pkt_type=MediaProtocol.TYPE_AUDIO,
                    room_id=self.room_id,
                    sender_id=self.my_p_id,
                    payload=encrypted_audio
                )
                self.udp_sock.sendto(audio_packet, self.server_address)
            except Exception:
                continue

        input_stream.stop_stream()
        input_stream.close()

    def _play_audio_loop(self):
        try:
            output_stream = self.pyaudio_instance.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                output_device_index=self._get_output_device_index(),
                frames_per_buffer=self.CHUNK
            )
        except Exception:
            return

        # גודל בייטים תקין לצ'אנק אחד (paInt16 = 2 בייטים לדגימה, ערוץ אחד)
        expected_chunk_bytes = self.CHUNK * 2

        while self.is_active.is_set():
            try:
                _, decrypted_audio = self.audio_queue.get(timeout=0.2)
                if decrypted_audio and len(decrypted_audio) == expected_chunk_bytes:
                    output_stream.write(decrypted_audio)
                else:
                    print(
                        f"[Audio Warning] Dropped malformed chunk, size={len(decrypted_audio) if decrypted_audio else 0}")
            except queue.Empty:
                continue
            except Exception:
                continue

        output_stream.stop_stream()
        output_stream.close()

    def stop(self):
        # 1. כיבוי ה-Flag הראשי - גורם לכל הת'רדים לדעת שעליהם לצאת מהלולאה
        self.is_active.clear()

        try:
            leave_packet = MediaProtocol.pack(
                pkt_type=MediaProtocol.TYPE_LEAVE,
                room_id=self.room_id,
                sender_id=self.my_p_id
            )
            self.udp_sock.sendto(leave_packet, self.server_address)
        except Exception:
            pass

        # 2. וידוא שה-thread הראשי (run) באמת יצא לפני שסוגרים את הסוקט.
        #    מונע race-condition שבו run() מנסה להשתמש בסוקט אחרי שהוא נסגר,
        #    ומונע מצב שבו שני MediaCommunicator (ישן+חדש) רצים במקביל.
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=1.5)

        try:
            self.udp_sock.close()
        except Exception:
            pass

        # 3. וידוא סגירת סטרימי האודיו - ממתינים שהת'רדים יסיימו בצורה חלקה
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=1.0)
        if self.play_thread and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)

        # 4. רק לאחר שאין אף ת'רד רקע שנוגע ברכיבי השמע, בטוח לסגור את ה-Instance
        try:
            self.pyaudio_instance.terminate()
            print("[Audio System] Closed successfully without leaks.")
        except Exception:
            pass

        # 5. ניקוי תורים - מונע זליגת אודיו/וידאו ישן לשיחה הבאה
        for q in (self.audio_queue, self.frame_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
