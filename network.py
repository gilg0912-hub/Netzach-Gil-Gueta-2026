import socket
import select
import threading
from network_infra import MessageProtocol
import time
import queue

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
    def __init__(self, server_ip, server_udp_port, media_key, udp_token, room_id, frame_queue, my_p_id):
        super().__init__(daemon=True, name="UDP-Media-Thread")

        self.server_address = (server_ip, server_udp_port)
        self.cipher = Fernet(media_key)
        self.room_id = room_id  # שמירת מזהה החדר
        self.udp_token = udp_token  # שמירת הטוקן מה-TCP
        self.my_p_id = my_p_id

        self.is_active = threading.Event()

        self.frame_queue = frame_queue
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.settimeout(1.0)

    def run(self):
        self.is_active.set()

        # 1. שליחת פאקט הצטרפות עם הטוקן כ-Payload
        join_packet = MediaProtocol.pack(
            pkt_type=MediaProtocol.TYPE_JOIN,
            room_id=self.room_id,
            sender_id=self.my_p_id,
            payload=self.udp_token.encode('utf-8')
        )
        self.udp_sock.sendto(join_packet, self.server_address)

        while self.is_active.is_set():
            try:
                data, addr = self.udp_sock.recvfrom(65535)

                # 2. שימוש בפרוטוקול לפריקה בטוחה!
                pkt_type, r_id, sender_id, encrypted_payload = MediaProtocol.unpack(data)

                if pkt_type == MediaProtocol.TYPE_VIDEO:
                    decrypted_frame = self.cipher.decrypt(encrypted_payload)
                    try:
                        # מעבירים ל-GUI גם את מזהה השולח וגם את הפריים
                        self.frame_queue.put((sender_id, decrypted_frame), block=False)
                    except queue.Full:
                        pass

            except socket.timeout:
                continue
            except Exception as e:
                pass

    def send_media(self, raw_bytes):
        if self.is_active.is_set():
            try:
                encrypted_payload = self.cipher.encrypt(raw_bytes)

                video_packet = MediaProtocol.pack(
                    pkt_type=MediaProtocol.TYPE_VIDEO,
                    room_id=self.room_id,
                    sender_id=self.my_p_id,
                    payload=encrypted_payload
                )
                self.udp_sock.sendto(video_packet, self.server_address)
            except Exception:
                pass

    def stop(self):
        self.is_active.clear()
        try:
            leave_packet = MediaProtocol.pack(
                pkt_type=MediaProtocol.TYPE_LEAVE,
                room_id=self.room_id,
                sender_id=self.my_p_id
            )
            self.udp_sock.sendto(leave_packet, self.server_address)
            self.udp_sock.close()
        except Exception:
            pass