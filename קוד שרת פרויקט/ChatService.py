from Protocol import *
import time
import uuid
import random
import string


class ChatManager:
    def __init__(self, db, send_to_client):
        self.db = db
        self.rooms = {
            "educational": {},
            "standard": {}
        }
        self.send_to_client = send_to_client

    def _get_env_by_role(self, role_config):
        if role_config in [UserRole.TEACHER, UserRole.STUDENT]:
            return "educational"
        return "standard"

    def process_new_message(self, client, payload):
        room_id = payload.get(Contract.ROOM_ID)
        content = payload.get(Contract.CONTENT)

        env = self._get_env_by_role(client.role_config)
        target_room = self.rooms[env].get(room_id)

        if not target_room:
            return ResponseFactory.error(msg_type=MsgType.SEND_MSG, code=MsgCodes.NOT_FOUND)

        client_nonce = payload.get(Contract.NONCE)

        msg_id = target_room.handle_new_message(client.db_id, client.p_id, client.sock, content)

        if msg_id:
            return ResponseFactory.create(
                msg_type=MsgType.SEND_MSG,
                code=MsgCodes.SUCCESS,
                raw_data={
                    Contract.MSG_ID: msg_id,
                    Contract.NONCE: client_nonce,
                    Contract.SERVER_TIME: time.time(),
                    Contract.ROOM_ID: target_room.room_id
                }
            )

    def _find_match_room(self, category, invite_code, env, p_id):
        if invite_code:
            room_data = self.db.get_room_by_invite_code(invite_code)
            print('room_data', room_data)
            if room_data:
                r_id = room_data['public_room_id']
                if r_id not in self.rooms[env]:
                    self.rooms[env][r_id] = ChatRoom(self.db, send_func=self.send_to_client, **room_data)
                return self.rooms[env][r_id]

        if category:
            for room in self.rooms[env].values():
                if room.category == category and room.is_open:
                    if not room.is_user_in_room(p_id):
                        return room

            room_data = self.db.find_available_room_for_user(category, p_id)
            if room_data:
                r_id = room_data['public_room_id']  # עודכן לשם העמודה מה-DB
                new_room = ChatRoom(self.db, send_func=self.send_to_client, **room_data)
                self.rooms[env][r_id] = new_room
                return new_room

        return None

    def add_user_to_room(self, client, payload):
        p_id = client.p_id
        db_id = client.db_id
        if client.role_config == UserRole.TEACHER:
            return ResponseFactory.error(msg_type=MsgType.JOIN_ROOM, code=MsgCodes.ACCESS_DENIED)

        category = payload.get(Contract.CATEGORY)
        invite_code = payload.get(Contract.INVITE_CODE)

        env = self._get_env_by_role(client.role_config)

        target_room = self._find_match_room(
            category=category,
            invite_code=invite_code,
            env=env,
            p_id=p_id
        )

        if not target_room:
            return ResponseFactory.create(msg_type=MsgType.JOIN_ROOM, code=MsgCodes.ROOM_NOT_FOUND)

        is_reconnect = target_room.is_user_in_room(p_id)

        if not is_reconnect:
            target_room.participants[p_id] = client.display_name
            self.db.add_user_to_room_db(target_room.room_id, db_id)

            now = time.time()

            join_msg_content = f"{client.display_name} joined the room"
            join_msg_id = str(uuid.uuid4())
            self.db.insert_msg(target_room.internal_id, None, join_msg_content, now, join_msg_id, recipient_db_id=None)

            join_payload = {
                Contract.ROOM_ID: target_room.room_id,
                Contract.CONTENT: join_msg_content,
                Contract.SENDER_PID: None,
                Contract.TIMESTAMP: now,
                Contract.MSG_ID: join_msg_id
            }
            target_room.broadcast(broadcast_payload=join_payload)

            welcome_msg_content = f"Welcome {client.display_name}!"
            welcome_msg_id = str(uuid.uuid4())
            self.db.insert_msg(target_room.internal_id, None, welcome_msg_content, now, welcome_msg_id,
                               recipient_db_id=db_id)

            welcome_payload = {
                Contract.ROOM_ID: target_room.room_id,
                Contract.CONTENT: welcome_msg_content,
                Contract.SENDER_PID: None,
                Contract.TIMESTAMP: now,
                Contract.MSG_ID: welcome_msg_id
            }
            self.send_to_client(client.sock,
                                ResponseFactory.create(MsgType.RECEIVE_MSG, MsgCodes.SUCCESS, welcome_payload))

        room_update = target_room.get_sync_payload()
        print('room_update', room_update)
        room_update[Contract.EVENT] = RoomEvent.USER_RECONNECTED if is_reconnect else RoomEvent.USER_JOINED
        room_update[Contract.USER] = client.display_name

        target_room.broadcast(broadcast_payload=room_update, sender_socket=client.sock)

        return ResponseFactory.create(
            msg_type=MsgType.JOIN_ROOM,
            code=MsgCodes.SUCCESS,
            raw_data=room_update
        )

    def create_new_room(self, creator_client, payload):
        role = creator_client.role_config

        if role == UserRole.TEACHER:
            allowed_role = UserRole.STUDENT
        elif role == UserRole.STANDARD:
            allowed_role = UserRole.STANDARD
        else:
            return ResponseFactory.error(msg_type=MsgType.CREATE_CHAT_ROOM, code=MsgCodes.INVALID_FIELDS)

        category = payload.get(Contract.CATEGORY)
        display_name = payload.get(Contract.DISPLAY_NAME)
        is_open = payload.get(Contract.IS_OPEN)

        room_id = str(uuid.uuid4())
        invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        success = self.db.insert_new_room(
            public_room_id=room_id,  # עודכן לפרמטר המדויק
            category=category,
            display_name=display_name,
            created_by=creator_client.p_id,
            invite_code=invite_code,
            is_open=is_open,
            allowed_role=allowed_role
        )

        if not success:
            return ResponseFactory.error(msg_type=MsgType.CREATE_CHAT_ROOM, code=MsgCodes.SERVER_ERROR)

        room_data = self.db.get_room_by_public_id(room_id)
        if not room_data:
            return ResponseFactory.error(msg_type=MsgType.CREATE_CHAT_ROOM, code=MsgCodes.SERVER_ERROR)

        new_room = ChatRoom(db=self.db, send_func=self.send_to_client, **room_data)
        new_room.participants[creator_client.p_id] = creator_client.display_name

        self.db.add_user_to_room_db(room_id, creator_client.db_id)

        env = self._get_env_by_role(role)
        self.rooms[env][room_id] = new_room

        reply_data = new_room.get_sync_payload()
        reply_data[Contract.ID] = room_id

        return ResponseFactory.create(
            msg_type=MsgType.CREATE_CHAT_ROOM,
            code=MsgCodes.SUCCESS,
            raw_data=reply_data
        )

    def get_initial_rooms_payload(self, client):
        db_id = client.db_id
        p_id = client.p_id
        env = self._get_env_by_role(client.role_config)

        user_rooms_ids = self.db.get_user_room_ids(db_id)
        all_rooms_sync_data = []

        for room_id in user_rooms_ids:
            if room_id not in self.rooms[env]:
                room_data = self.db.get_room_by_public_id(room_id)
                if room_data:
                    self.rooms[env][room_id] = ChatRoom(
                        db=self.db,
                        send_func=self.send_to_client,
                        **room_data
                    )
                    print(self.rooms[env][room_id].get_sync_payload())

            target_room = self.rooms[env].get(room_id)
            if target_room:
                if client.sock not in target_room.clients_sockets:
                    target_room.clients_sockets.append(client.sock)
                target_room.participants[p_id] = client.display_name

                all_rooms_sync_data.append(target_room.get_sync_payload())

        return all_rooms_sync_data

    def handle_older_topics(self, client, payload):
        last_id = payload.get(Contract.TOPIC_ID)
        user_role = client.role

        older_topics = self.db.get_topics_paged(
            role_name=user_role,
            before_id=last_id,
            limit=5
        )

        return ResponseFactory.create(
            msg_type=MsgType.GET_OLDER_TOPICS,
            code=MsgCodes.SUCCESS,
            raw_data={'items': older_topics, 'end_of_data': len(older_topics) == 0}
        )

    def handle_older_messages(self, client, payload):
        room_id = payload.get(Contract.ROOM_ID)
        anchor_id = payload.get(Contract.ANCHOR_ID)

        env = self._get_env_by_role(client.role_config)
        target_room = self.rooms[env].get(room_id)

        if not target_room or not target_room.is_user_in_room(client.p_id):
            return ResponseFactory.error(msg_type=MsgType.GET_OLDER_MESSAGES, code=MsgCodes.ACCESS_DENIED)

        db_response = self.db.get_older_messages(internal_room_id=target_room.internal_id, user_db_id=client.db_id, anchor_id=anchor_id,
                                                 limit=25)

        return ResponseFactory.create(
            msg_type=MsgType.GET_OLDER_MESSAGES,
            code=MsgCodes.SUCCESS,
            raw_data={
                Contract.ROOM_ID: room_id,
                **db_response
            }
        )


class ChatRoom:
    def __init__(self, db, id, public_room_id, created_by, display_name, created_at, category, allowed_role, is_open, invite_code, send_func,
                 **kwargs):
        self.db = db
        self.internal_id = id
        self.room_id = public_room_id
        self.invite_code = invite_code
        self.category = category
        self.creator_p_id = created_by
        self.display_name = display_name
        self.allowed_role = allowed_role
        self.is_open = (is_open == 0)
        self.participants = {}
        self.clients_sockets = []
        self.created_at = created_at
        self.send_func = send_func

    def get_sync_payload(self):
        return {
            Contract.ROOM_ID: self.room_id,
            Contract.INVITE_CODE: self.invite_code,
            Contract.CREATED_AT: self.created_at,
            Contract.CATEGORY: self.category,
            Contract.TOTAL_PARTICIPANTS: len(self.participants),
            Contract.PARTICIPANTS: self.participants,
            Contract.DISPLAY_NAME: self.display_name,
            Contract.IS_OPEN: self.is_open
        }

    def is_user_in_room(self, p_id):
        return p_id in self.participants

    def broadcast(self, broadcast_payload, sender_socket=None):
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
                except Exception as e:
                    disconnected.append(sock)

        for sock in disconnected:
            if sock in self.clients_sockets:
                self.clients_sockets.remove(sock)

    def handle_new_message(self, sender_db_id, sender_p_id, sender_sock, content):
        now = time.time()
        public_msg_id = str(uuid.uuid4())

        success = self.db.insert_msg(self.internal_id, sender_db_id, content, now, public_msg_id)

        if success:
            broadcast_data = {
                Contract.ROOM_ID: self.room_id,
                Contract.CONTENT: content,
                Contract.SENDER_PID: sender_p_id,
                Contract.MSG_ID: public_msg_id,
                Contract.TIMESTAMP: now
            }

            self.broadcast(broadcast_payload=broadcast_data, sender_socket=sender_sock)
            return public_msg_id
        return None
