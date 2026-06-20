import threading
import socket
from MediaProtocol import *

class UDPMediaServer:
    def __init__(self, host='0.0.0.0', port=8821):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))

        # מנגנוני סנכרון ומבני נתונים
        self.lock = threading.Lock()
        self.rooms = {}              # מבנה: { room_id: set(client_addresses) }
        self.clients_room_map = {}   # מבנה: { client_address: room_id }
        self.authorized_clients = {}  # { sender_id: room_id }

        self.is_running = False
        self.auth_validator = None

    def set_auth_validator(self, func):
        self.auth_validator = func

    def start(self):
        self.is_running = True
        threading.Thread(target=self._listen, daemon=True, name="UDP-Server-Thread").start()
        print(f"[UDP Server] Listening for encrypted media routing on {self.host}:{self.port}")

    def _listen(self):
        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(65535)
                self._handle_packet(data, addr)
            except socket.error:
                break
            except Exception as e:
                print(f"[UDP Server Error] Exception in listen loop: {e}")

    def _handle_packet(self, data, addr):
        try:
            pkt_type, room_id, sender_id, payload = MediaProtocol.unpack(data)
            if not pkt_type:
                return

            room_id = str(room_id)

            with self.lock:  # הנעילה עוטפת את כל הלוגיקה לשינוי מבני נתונים
                if pkt_type == MediaProtocol.TYPE_LEAVE:
                    self._remove_client_unsafe(addr, room_id)
                    print(f"[UDP Server] Client {sender_id} ({addr}) left room {room_id}")
                    return


                elif pkt_type == MediaProtocol.TYPE_JOIN:

                    # 1. בדיקה אם המשתמש כבר מורשה

                    if sender_id in self.authorized_clients:

                        # התיקון הקריטי: עדכון החדר העדכני במאגר ההרשאות

                        self.authorized_clients[sender_id] = room_id

                        if addr not in self.clients_room_map:
                            self.clients_room_map[addr] = room_id

                            self.rooms.setdefault(room_id, set()).add(addr)

                            print(f"[UDP Server] Auto-joined existing user {sender_id} on port {addr[1]}")

                        return

                    # 2. ניסיון אימות ראשוני ללקוח חדש

                    try:

                        token = payload.decode('utf-8')

                    except UnicodeDecodeError:

                        return

                    if self.auth_validator and self.auth_validator(room_id, token):

                        self.authorized_clients[sender_id] = room_id

                        self.clients_room_map[addr] = room_id

                        self.rooms.setdefault(room_id, set()).add(addr)

                        print(f"[UDP Server] Auth SUCCESS: {sender_id} joined room {room_id}")

                    else:

                        print(f"[UDP Server] Auth FAILED for {sender_id}")

                    return

                elif pkt_type in (MediaProtocol.TYPE_VIDEO, MediaProtocol.TYPE_AUDIO):
                    # 3. מנגנון רישום אוטומטי: אם הכתובת לא מוכרת, נבדוק אם הלקוח אושר בעבר
                    if addr not in self.clients_room_map:
                        print('check')
                        if sender_id in self.authorized_clients and self.authorized_clients[sender_id] == room_id:
                            self.clients_room_map[addr] = room_id
                            self.rooms.setdefault(room_id, set()).add(addr)
                            print(f"[UDP Server] Auto-registered media port for {sender_id} ({addr})")
                        else:
                            # הלקוח לא מוכר ולא אומת מעולם - מתעלמים מהפקטה
                            return

                    # 4. ניתוב המדיה לשאר המשתתפים בחדר
                    if self.clients_room_map.get(addr) == room_id:
                        destinations = self.rooms.get(room_id, set())
                        for client_addr in destinations:
                            if client_addr != addr:
                                try:
                                    self.sock.sendto(data, client_addr)
                                except Exception:
                                    pass
                    return

        except Exception as e:
            print(f"[UDP Server Error] Failed to handle packet from {addr}: {e}")

    def _remove_client_unsafe(self, addr, room_id):
        if addr in self.clients_room_map:
            del self.clients_room_map[addr]
        if room_id in self.rooms and addr in self.rooms[room_id]:
            self.rooms[room_id].remove(addr)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    def stop(self):
        print("[UDP Server] Stopping media server...")
        self.is_running = False
        with self.lock:
            self.rooms.clear()
            self.clients_room_map.clear()
        try:
            self.sock.close()
        except Exception:
            pass