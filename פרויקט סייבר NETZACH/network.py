import socket
import select
import threading
from network_infra import MessageProtocol

from app_constants import MsgType, MsgCodes, Contract, StateKey

class Server_Communicator(threading.Thread):
    def __init__(self, server_ip, server_port, user_state, msg_manager):
        super().__init__()

        self.sock_manager=SocketManager(server_ip, server_port)
        self.protocol = MessageProtocol()
        self.user_state = user_state
        self.msg_manager = msg_manager
        self.max_to_read= 1024
        self.expected_length=0
        self.outgoing_buffer =b''
        self.incoming_buffer =b''

    def run(self):
        while self.user_state.get_state(StateKey.IS_ACTIVE):
            sock = self.sock_manager.try_connect()

            if sock:
                self._handle_connect_success(sock)
                try:
                    self.maintain_connection(sock)
                except Exception as e:
                    print(f"Connection error: {e}")
                finally:
                    self._handle_disconnect()


    def _handle_connect_success(self, sock):
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
                            self.msg_manager.incoming_queue.put(raw_data)
                            self.incoming_buffer = self.incoming_buffer[self.expected_length:]
                            self.expected_length = 0
                        except Exception as e:
                            print(f"Protocol Error (JSON): {e}")
                    else:
                        available_data = False
        except Exception as e:
            raise e

    def write_to_server(self, sock):
        try:
            if not self.outgoing_buffer:
                msg_dict = self.msg_manager.get_next_outbound()
                if msg_dict:
                    self.outgoing_buffer = self.protocol.pack(msg_dict)

            if self.outgoing_buffer:
                sent = sock.send(self.outgoing_buffer)
                self.outgoing_buffer = self.outgoing_buffer[sent:]
        except Exception as e:
            self.user_state.set_state(StateKey.CONNECTED, False)
            raise e

    def _handle_disconnect(self):
        self.sock_manager.close()

        self.incoming_buffer=b''
        self.outgoing_buffer=b''
        self.expected_length = 0

        self.msg_manager.incoming_queue.put({
            Contract.TYPE: MsgType.SYSTEM,
            Contract.CODE: MsgCodes.CONNECTION_LOST,
            "update_state": {
                StateKey.CONNECTED: False,
            }
        })
        print('server disconnected')
        self.msg_manager.connection_active.clear()

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
        self.sock.close()
        self.sock = None