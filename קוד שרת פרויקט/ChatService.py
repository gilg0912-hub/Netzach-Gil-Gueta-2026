from Protocol import *
import time
import random
from typing import Optional


class ChatManager:
    def __init__(self, db, ai_handler, send_to_client):
        self.db = db
        self.ai_handler = ai_handler
        self.rooms = {
            UserRole.STUDENT: {},
            UserRole.STANDARD: {}
        }
        self.send_to_client = send_to_client

    def process_new_message(self, client, payload):
        room_id = payload.get(Contract.ROOM_ID)
        content = payload.get(Contract.CONTENT)
        role = client.role

        # מציאת החדר בזיכרון
        target_room = self.rooms[role].get(room_id)

        if not target_room:
            return ResponseFactory.error(msg_type=MsgType.SEND_MSG, code=MsgCodes.NOT_FOUND)

        client_nonce = payload.get(Contract.NONCE)
        msg_id = target_room.handle_new_message(client.p_id, client.sock, content)

        if msg_id:

            return ResponseFactory.create(
                msg_type=MsgType.SEND_MSG,
                code=MsgCodes.SUCCESS,
                raw_data={
                    Contract.MSG_ID: msg_id,
                    Contract.NONCE: client_nonce,
                    Contract.SERVER_TIME: time.time()
                }
            )

    def _find_match_room(self, topic, room_id, role, p_id):
        if room_id:
            room = self.rooms[role].get(room_id)
            if not room:
                room_data = self.db.get_room_by_id(room_id)
                if room_data:
                    room = ChatRoom(self.db, send_func= self.send_to_client, **room_data)
                    self.rooms[role][room_id] = room
            return room

        if topic:
            for room in self.rooms[role].values():
                if room.topic == topic and room.is_open:
                    if not room.is_user_in_room(p_id):
                        return room

            room_data = self.db.find_available_room_for_user(topic, role, p_id)

            if room_data:
                r_id = room_data[Contract.ROOM_ID]
                new_room = ChatRoom(self.db, send_func= self.send_to_client, **room_data)
                self.rooms[role][r_id] = new_room
                return new_room

        return None

    def sync_user_rooms(self, client):
        p_id = client.p_id
        role = client.role

        # 1. שליפת רשימת מזהי החדרים מה-DB
        user_rooms_ids = self.db.get_user_room_ids(p_id)
        all_rooms_sync_data = []

        for room_id in user_rooms_ids:
            # טעינת החדר לזיכרון השרת אם אינו קיים (כפי שכתבת)
            if room_id not in self.rooms[role]:
                room_data = self.db.get_room_by_id(room_id)
                if room_data:
                    self.rooms[role][room_id] = ChatRoom(self.db, send_func=self.send_to_client, **room_data)

            target_room = self.rooms[role][room_id]
            if target_room:
                if client.sock not in target_room.clients_sockets:
                    target_room.clients_sockets.append(client.sock)
                target_room.participants[p_id] = client.display_name

                room_info = target_room.get_sync_payload()
                all_rooms_sync_data.append(room_info)

        sync_payload = {
            "rooms": all_rooms_sync_data,
            "server_topics": self.ai_handler.get_topics_for_role(role)
        }
        print(sync_payload)

        sync_msg = ResponseFactory.create(
            msg_type=MsgType.SYNC_DATA,
            code=MsgCodes.SUCCESS,
            raw_data=sync_payload
        )

        self.send_to_client(client.sock, sync_msg)

    def add_user_to_room(self, client, payload):
        p_id = client.p_id
        role = client.role
        topic = payload.get(Contract.TOPIC)
        room_id = payload.get(Contract.ROOM_ID)

        target_room = self._find_match_room(topic, room_id, role, p_id)

        if not target_room:
            return ResponseFactory.create(msg_type=MsgType.JOIN_ROOM, code=MsgCodes.NOT_FOUND)

        is_reconnect = target_room.is_user_in_room(p_id)

        if not is_reconnect:
            target_room.participants[p_id] = client.display_name


        room_update = {
            Contract.ROOM_ID: target_room.room_id,
            Contract.CREATED_AT: target_room.created_at,
            Contract.TOPIC: target_room.topic,
            Contract.TOTAL_PARTICIPANTS: len(target_room.participants),
            Contract.PARTICIPANTS: target_room.participants,
            'is_open': target_room.is_open,
            'is_reconnect': is_reconnect,
            Contract.EVENT: RoomEvent.USER_RECONNECTED if is_reconnect else RoomEvent.USER_JOINED,
            Contract.USER: client.display_name,
        }

        target_room.broadcast(raw_content=room_update, sender_p_id=p_id, sender_socket=client.sock)


        return ResponseFactory.create(
            msg_type=MsgType.JOIN_ROOM,
            code=MsgCodes.SUCCESS,
            raw_data= room_update
        )


    def create_new_room(self, creator_client, payload):
        topic = payload.get(Contract.TOPIC)
        if not topic:
            return None

        if self.db.is_topic_exist(topic):

            role = creator_client.role
            room_id = self._generate_unique_code(role)


            self.db.execute_query(
                "INSERT INTO ChatRooms (Room_ID, Name, Created_By) VALUES (?, ?, ?)",
                (room_id, topic, creator_client.p_id)
            )
            room_data = self.db.get_room_by_id(room_id)

            new_room = ChatRoom(db= self.db, send_func= self.send_to_client, **room_data)

            self.rooms[role][room_id] = new_room
            return ResponseFactory.create(
            msg_type=MsgType.CREATE_CHAT_ROOM,
            code=MsgCodes.SUCCESS,
            raw_data={
                Contract.ROOM_ID: room_id,
                Contract.TOPIC: topic,
                Contract.CREATED_AT: new_room.created_at,
            })

    def _generate_unique_code(self, role):
        while True:
            code = str(random.randint(10000000, 99999999))
            if code not in self.rooms[role] and not self.db.room_exists(code):
                return code


class ChatRoom:
    def __init__(self, db, room_id, created_by, created_at, topic, allowed_type, is_locked, send_func, **kwargs):
        self.db = db
        self.room_id = room_id
        self.topic = topic
        self.creator_p_id = created_by
        self.allowed_type = allowed_type
        self.is_open = (is_locked == 0)
        self.participants = {}
        self.clients_sockets = []
        self.created_at = created_at
        self.send_func = send_func

    def is_user_in_room(self, p_id):
        return p_id in self.participants

    def broadcast(self, broadcast_payload, sender_p_id, sender_socket=None):

        message = ResponseFactory.create(
            msg_type=MsgType.RECEIVE_MSG,
            code=MsgCodes.SUCCESS,
            raw_data=broadcast_payload
        )
        disconnected = []
        for sock in self.clients_sockets:
            if sock != sender_socket:
                try:
                    self.send_func(sock, message)
                except:
                    disconnected.append(sock)
        for sock in disconnected:
            if sock in self.clients_sockets:
                self.clients_sockets.remove(sock)

    def handle_new_message(self, sender_p_id, sender_sock, content):
        now = time.time()
        msg_id = self.db.insert_msg(self.room_id, sender_p_id, content, now)

        if msg_id:
            broadcast_data = {
                Contract.ROOM_ID: self.room_id,
                Contract.CONTENT: content,
                Contract.SENDER_PID: sender_p_id,
                Contract.MSG_ID: msg_id,
                Contract.TIMESTAMP: now
            }

            self.broadcast(broadcast_data, sender_p_id, sender_sock)
            return msg_id
        return None