from gui_state_mgmt import *
from abc import abstractmethod
from chat_widgets import ChatRoom
from app_constants import Contract
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization, hashes
import random
import time


class BaseService:
    def __init__(self, dispatcher, gui_state):
        self.dispatcher = dispatcher
        self.gui_state = gui_state
        self._register_handlers()

    @abstractmethod
    def _register_handlers(self):
        pass

class ChatService(BaseService):
    def __init__(self, dispatcher, gui_state):
        super().__init__(dispatcher, gui_state)
        self.rooms = {}

    def _register_handlers(self):
        # --- צ'אט וסנכרון בסיסי ---
        self.dispatcher.register(MsgType.SYNC_DATA, self.handle_sync_data)
        self.dispatcher.register(MsgType.JOIN_ROOM, self.handle_join_room_response)
        self.dispatcher.register(MsgType.GET_OLDER_MESSAGES, self.handle_older_messages_response)
        self.dispatcher.register(MsgType.GET_OLDER_TOPICS, self.handle_older_topics)
        self.dispatcher.register(MsgType.GET_OLDER_GROUPS, self.handle_older_groups)
        self.dispatcher.register(MsgType.CREATE_CHAT_ROOM, self.handle_new_room)
        self.dispatcher.register(MsgType.SEND_MSG, self.handle_send_msg_response)
        self.dispatcher.register(MsgType.RECEIVE_MSG, self.handle_receive_msg)
        self.gui_state.register(StateKey.CONNECTED, self._on_connection_changed)
        self.dispatcher.register(MsgType.CALL_STATE, self.room_video_call_update)
        self.dispatcher.register(MsgType.LEAVE_CALL, self._handle_leave_call)

        # --- ניהול שיחות וידאו ---
        self.dispatcher.register(MsgType.START_CALL, self.handle_start_call_response)
        self.dispatcher.register(MsgType.JOIN_CALL, self.handle_join_call_response)

        # --- אבטחה וניהול מפתחות ---

        # --- עדכוני משתתפים בזמן אמת (חדש) ---
        self.dispatcher.register(MsgType.USER_JOINED_CALL, self.handle_user_joined_call)
        self.dispatcher.register(MsgType.USER_LEFT_CALL, self.handle_user_left_call)
        self.dispatcher.register(MsgType.DELIVER_CALL_MEDIA_KEY, self.handle_deliver_media_key)

    def handle_sync_data(self, data, code):
        if code == MsgCodes.SUCCESS:

            if Contract.ROOMS in data:
                self._update_rooms_list(data[Contract.ROOMS])

        else:
            print(f"[ChatService] Sync Data failed with code: {code}")

    def join_room_by_category(self, category):
        if not category:
            return
        payload = {Contract.CATEGORY: category}
        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def handle_receive_msg(self, data, code):
        if code == MsgCodes.SUCCESS:
            room_id = data.get(Contract.ROOM_ID)
            self._update_messages_list(
                room_id=room_id,
                messages_to_add=[data],
                is_older=False
            )
            self._update_rooms_list([{Contract.ROOM_ID: room_id}], at_top=True)

    def handle_older_messages_response(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        messages = data.get(Contract.ITEMS, [])
        is_end = data.get('end_of_data', False)

        if code == MsgCodes.SUCCESS:
            self._update_messages_list(
                room_id=room_id,
                messages_to_add=messages,
                is_older=True,
                end_of_data=is_end
            )
        else:
            self.gui_state.set_state(StateKey.MESSAGES_UI_SIGNAL, {
                "room_id": room_id,
                Contract.ITEMS: [],
                "is_older": True,
                "end_of_data": True
            })

    def _update_messages_list(self, room_id, messages_to_add, is_older=False, end_of_data=False):
        if not room_id:
            return

        room_id_str = str(room_id)

        all_rooms_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}
        current_room_messages = list(all_rooms_messages.get(room_id_str, []))

        existing_ids = {str(m.get(Contract.MSG_ID)) for m in current_room_messages if
                        m.get(Contract.MSG_ID) is not None}
        new_items = []

        for msg in messages_to_add:
            prepared = {
                Contract.MSG_ID: msg.get(Contract.MSG_ID),
                Contract.ROOM_ID: room_id_str,
                Contract.CONTENT: msg.get(Contract.CONTENT),
                Contract.SENDER_PID: msg.get(Contract.SENDER_PID),
                Contract.TIMESTAMP: msg.get(Contract.TIMESTAMP, time.time())
            }
            if str(prepared[Contract.MSG_ID]) not in existing_ids:
                new_items.append(prepared)

        if not new_items and not end_of_data:
            return

        new_items.sort(key=lambda x: x[Contract.TIMESTAMP])

        if is_older:
            updated_room_messages = new_items + current_room_messages
        else:
            updated_room_messages = current_room_messages + new_items

        all_rooms_messages[room_id_str] = updated_room_messages
        self.gui_state.set_state(StateKey.SYNC_MESSAGES, all_rooms_messages)

        self.gui_state.set_state(StateKey.MESSAGES_UI_SIGNAL, {
            "room_id": room_id_str,
            Contract.ITEMS: new_items,
            "is_older": is_older,
            "end_of_data": end_of_data
        })

    def _update_rooms_list(self, rooms_to_update, at_top=False):
        if len(rooms_to_update) == 0 or not rooms_to_update[0]:
            return

        processed_items = []
        updated_room_ids = set()

        for room_dict in rooms_to_update:
            raw_id = room_dict.get(Contract.ID) or room_dict.get(Contract.ROOM_ID)

            if not raw_id:
                continue

            r_id = str(raw_id)
            updated_room_ids.add(r_id)

            if r_id not in self.rooms:
                self.rooms[r_id] = ChatRoom.from_dict(room_dict)
            else:
                self.rooms[r_id].is_open = room_dict.get(Contract.IS_OPEN, self.rooms[r_id].is_open)

            processed_items.append(self.rooms[r_id])

        remaining_rooms = [
            room_obj
            for room_id, room_obj in self.rooms.items()
            if room_id not in updated_room_ids
        ]

        if at_top:
            updated_full_list = processed_items + remaining_rooms
        else:
            updated_full_list = remaining_rooms + processed_items

        self.gui_state.set_state(StateKey.SYNC_ROOMS, updated_full_list)

        self.gui_state.set_state(StateKey.ROOMS_UI_SIGNAL, {
            "rooms": processed_items,
            "on_top": at_top
        })

    def handle_join_room_response(self, data, code):
        if code == MsgCodes.SUCCESS:
            self._update_rooms_list([data])
            room_id = str(data.get(Contract.ROOM_ID))

            self._update_messages_list(
                room_id=room_id,
                messages_to_add=data.get(Contract.ITEMS, []),
                is_older=True
            )

            self.switch_to_room(self.rooms.get(room_id))

    def _update_generic_list(self, items_to_add, sync_key, signal_key, at_top=False, end_of_data=False):
        current_list = self.gui_state.get_state(sync_key)
        if not isinstance(current_list, list):
            current_list = []

        existing_ids = {str(d.get(Contract.ID)) for d in current_list if d.get(Contract.ID) is not None}
        new_items = [t for t in items_to_add if str(t.get(Contract.ID)) not in existing_ids] if items_to_add else []

        if new_items:
            updated_list = new_items + current_list if at_top else current_list + new_items
            self.gui_state.set_state(sync_key, updated_list)


        self.gui_state.set_state(signal_key, {Contract.ITEMS: new_items, "on_top": at_top, "end_of_data": end_of_data})

    def handle_older_topics(self, data, code):
        topics = data.get(Contract.ITEMS, [])
        is_end = data.get('end_of_data', False)

        if code == MsgCodes.SUCCESS:
            # 🟢 שימוש בפונקציה הגנרית עם המפתחות הייעודיים של Topics
            self._update_generic_list(topics, StateKey.SYNC_TOPICS, StateKey.TOPICS_UI_SIGNAL, at_top=False,
                                      end_of_data=is_end)
        else:
            self.gui_state.set_state(StateKey.TOPICS_UI_SIGNAL, {
                Contract.ITEMS: [],
                "on_top": False,
                "end_of_data": True
            })

    def handle_older_groups(self, data, code):
        groups = data.get(Contract.ITEMS, [])
        is_end = data.get('end_of_data', False)

        if code == MsgCodes.SUCCESS:
            self._update_generic_list(groups, StateKey.SYNC_GROUPS, StateKey.GROUPS_UI_SIGNAL, at_top=False, end_of_data=is_end)
        else:
            self.gui_state.set_state(StateKey.GROUPS_UI_SIGNAL, {
                Contract.ITEMS: [],
                "on_top": False,
                "end_of_data": True
            })

    def handle_new_room(self, data, code):
        if code == MsgCodes.SUCCESS:
            self._update_rooms_list([data], at_top=True)

    def room_video_call_update(self, data, code):
        if code != MsgCodes.SUCCESS:
            return

        room_id = str(data.get(Contract.ROOM_ID))
        is_call_active = data.get(Contract.CALL_STATE, False)

        all_rooms = self.gui_state.get_state(StateKey.SYNC_ROOMS) or []
        target_room = next((r for r in all_rooms if str(r.room_id) == room_id), None)

        if target_room:
            target_room.is_call_active = is_call_active
            self.gui_state.set_state(StateKey.ROOM_VIDEO_STATUS, room_id)

    def fetch_older_messages(self, room_id, oldest_msg_id=None):
        payload = {
            Contract.ROOM_ID: room_id,
            Contract.ANCHOR_ID: oldest_msg_id,
        }
        self.dispatcher.send_msg(MsgType.GET_OLDER_MESSAGES, payload)

    def send_message(self, room_id, content):

        client_nonce = str(random.randint(1000, 9999))

        payload = {
            Contract.ROOM_ID: room_id,
            Contract.CONTENT: content,
            Contract.NONCE: client_nonce
        }

        my_p_id = self.gui_state.get_state(StateKey.PUBLIC_ID)
        local_msg = {
            Contract.MSG_ID: f"tmp_{client_nonce}",
            Contract.CONTENT: content,
            Contract.SENDER_PID: my_p_id ,
            Contract.TIMESTAMP: time.time()
        }

        self._update_messages_list(room_id, [local_msg])

        self._update_rooms_list([{Contract.ROOM_ID: room_id}], at_top=True)

        self.dispatcher.send_msg(MsgType.SEND_MSG, payload)
        return client_nonce

    def join_room(self, category=None, invite_code=None):
        payload = {}
        if invite_code:
            payload[Contract.INVITE_CODE] = invite_code
        if category:
            payload[Contract.CATEGORY] = category

        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def create_room(self, payload):
        self.dispatcher.send_msg(MsgType.CREATE_CHAT_ROOM, payload)

    def fetch_older_groups(self, oldest_id=None, category=None):
        payload = {
            Contract.ANCHOR_ID: oldest_id,
        }
        if category:
            payload[Contract.CATEGORY] = category

        self.dispatcher.send_msg(MsgType.GET_OLDER_GROUPS, payload)

    def fetch_older_topics(self, last_topic_id=None, category=None):
        payload = {
            Contract.ANCHOR_ID: last_topic_id,
        }
        if category:
            payload[Contract.CATEGORY] = category

        self.dispatcher.send_msg(MsgType.GET_OLDER_TOPICS, payload)

    def handle_send_msg_response(self, data, code):
        if code == MsgCodes.SUCCESS:
            room_id = str(data.get(Contract.ROOM_ID))
            nonce = data.get(Contract.NONCE)
            real_id = data.get(Contract.MSG_ID)
            server_time = data.get(Contract.SERVER_TIME, time.time())
            tmp_id = f"tmp_{nonce}"

            self._confirm_local_message(room_id, tmp_id, real_id, server_time)

            self.gui_state.set_state(StateKey.MESSAGES_UI_SIGNAL, {
                Contract.ROOM_ID: room_id,
                "is_confirmation": True,
                "tmp_id": tmp_id,
                "real_id": real_id,
                "server_time": server_time
            })

    def _confirm_local_message(self, room_id, tmp_id, real_id, server_time):
        all_rooms_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}

        if room_id in all_rooms_messages:
            updated = False

            for msg in all_rooms_messages[room_id]:
                if str(msg.get(Contract.MSG_ID)) == tmp_id and not updated:
                    msg[Contract.MSG_ID] = real_id
                    msg[Contract.TIMESTAMP] = server_time
                    updated = True

            self.gui_state.set_state(StateKey.SYNC_MESSAGES, all_rooms_messages)

    def switch_to_room(self, room_obj):
        if not room_obj:
            return

        room_id_str = str(room_obj.room_id)

        self.gui_state.set_state(StateKey.CURRENT_ROOM_ID, room_id_str)

        all_rooms_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}

        if room_id_str not in all_rooms_messages:
            print(f"[Cache Miss] First time entering room {room_id_str}. Locking cache immediately...")

            all_rooms_messages[room_id_str] = []
            self.gui_state.set_state(StateKey.SYNC_MESSAGES, all_rooms_messages)

            self.fetch_older_messages(room_id = room_id_str, oldest_msg_id=None)

        else:
            print(f"[Cache Hit] Room {room_id_str} is already tracked. Handled locally by UI.")

    def _on_connection_changed(self, is_connected):
        if not is_connected:
            self.mark_pending_as_failed()

    def mark_pending_as_failed(self):
        """סורק את כל ההודעות ומסמן הודעות ממתינות (tmp_) כנכשלו."""
        all_rooms_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}
        updated = False

        for room_id, messages in all_rooms_messages.items():
            for msg in messages:
                if str(msg.get(Contract.MSG_ID)).startswith("tmp_") and msg.get("status") != "failed":
                    msg["status"] = "failed"
                    updated = True

        if updated:
            self.gui_state.set_state(StateKey.SYNC_MESSAGES, all_rooms_messages)

            current_room = self.gui_state.get_state(StateKey.CURRENT_ROOM_ID)
            self.gui_state.set_state(StateKey.MESSAGES_UI_SIGNAL, {
                "is_refresh": True
            })

    # --- 1. ניהול מפתחות הצפנה (RSA) ---
    def _get_or_create_call_keys(self):
        private_key_pem = self.gui_state.get_state(StateKey.PRIVATE_CALL_KEY)
        public_key_pem = self.gui_state.get_state(StateKey.PUBLIC_CALL_KEY)

        if private_key_pem and public_key_pem:
            return public_key_pem

        print("[Security] Generating new RSA call keys...")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        self.gui_state.set_state(StateKey.PRIVATE_CALL_KEY, private_pem)
        self.gui_state.set_state(StateKey.PUBLIC_CALL_KEY, public_pem)
        return public_pem

    # --- 2. יצירה והצטרפות לשיחה ---
    def start_video_call(self, room_id):
        if self.gui_state.get_state(StateKey.ACTIVE_CALL_ROOM_ID): return
        self.gui_state.set_state(StateKey.ACTIVE_CALL_ROOM_ID, room_id)
        self.gui_state.set_state(StateKey.OPEN_CAMERA, True)

        public_key_pem = self._get_or_create_call_keys()

        room = self.rooms.get(str(room_id))
        if room:
            my_p_id = str(self.gui_state.get_state(StateKey.PUBLIC_ID))
            room.call_participants[my_p_id] = public_key_pem.hex()

        self.dispatcher.send_msg(MsgType.START_CALL, {
            Contract.ROOM_ID: room_id,
            Contract.PUBLIC_CALL_KEY: public_key_pem.hex()
        })

    def join_video_call(self, room_id):
        if self.gui_state.get_state(StateKey.ACTIVE_CALL_ROOM_ID): return
        self.gui_state.set_state(StateKey.ACTIVE_CALL_ROOM_ID, room_id)
        self.gui_state.set_state(StateKey.OPEN_CAMERA, True)


        public_key_pem = self._get_or_create_call_keys()

        room = self.rooms.get(str(room_id))
        if room:
            my_p_id = str(self.gui_state.get_state(StateKey.PUBLIC_ID))
            room.call_participants[my_p_id] = public_key_pem.hex()

        self.dispatcher.send_msg(MsgType.JOIN_CALL, {
            Contract.ROOM_ID: room_id,
            Contract.PUBLIC_CALL_KEY: public_key_pem.hex()
        })

    def leave_video_call(self, room_id):
        self.dispatcher.send_msg(MsgType.LEAVE_CALL, {Contract.ROOM_ID: room_id})

    # --- 3. Handlers לאירועי שיחה ---
    def handle_start_call_response(self, data, code):
        if code == MsgCodes.SUCCESS:
            self.gui_state.set_state(StateKey.PENDING_UDP_TOKEN, data.get(Contract.UDP_TOKEN))
            self.gui_state.set_state(StateKey.CALL_ESTABLISHED, True)
        else:
            self.clear_call_state()

    def handle_join_call_response(self, data, code):
        if code == MsgCodes.SUCCESS:
            self.gui_state.set_state(StateKey.PENDING_UDP_TOKEN, data.get(Contract.UDP_TOKEN))
            self.gui_state.set_state(StateKey.CALL_ESTABLISHED, True)

            room_id = str(data.get(Contract.ROOM_ID))
            room = self.rooms.get(room_id)
            if room:
                for p in data.get(Contract.PARTICIPANTS, []):
                    p_id = str(p.get(Contract.PUBLIC_ID))
                    room.call_participants[p_id] = p.get(Contract.PUBLIC_CALL_KEY)

        else:
            self.clear_call_state()

    def _handle_leave_call(self, data, code):
        if code == MsgCodes.SUCCESS:
            self.gui_state.set_state(StateKey.ROOM_VIDEO_STATUS, data.get(Contract.CALL_STATE))
            self.clear_call_state()
    def handle_user_joined_call(self, data, code):
        room_id = str(data.get(Contract.ROOM_ID))

        room = self.rooms.get(room_id)
        if not room:
            print(f"[Warning] Received join event for unknown room {room_id}. Ignoring.")
            return

        if data:
            p_id = str(data.get(Contract.PUBLIC_ID))
            room.call_participants[p_id] = data.get(Contract.PUBLIC_CALL_KEY)

            if self.gui_state.get_state(StateKey.PUBLIC_ID) == data.get(Contract.DISTRIBUTOR_ID):
                self._attempt_key_rotation(room)

    def handle_user_left_call(self, data, code):
        room = self.rooms.get(str(data.get(Contract.ROOM_ID)))
        p_id = str(data.get(Contract.PUBLIC_ID))
        if room and p_id in room.call_participants:
            del room.call_participants[p_id]
            self._attempt_key_rotation(room)

    # --- 4. מנוע אבטחה ורוטציית מפתחות ---
    def _attempt_key_rotation(self, room):
        if not room.call_participants or len(room.call_participants) <= 1:
            return

        self._perform_key_rotation(room.room_id)

    def _perform_key_rotation(self, room_id):
        room = self.rooms.get(room_id)
        if not room or not room.call_participants: return

        new_media_key = Fernet.generate_key()
        self.gui_state.set_state(StateKey.ACTIVE_MEDIA_KEY, new_media_key)
        keys_map = {}

        # ניקוי משתתפים עם מפתח חסר כדי למנוע קריסה
        valid_participants = {pid: key for pid, key in room.call_participants.items() if key is not None}

        for p_id, participant_pub_key in valid_participants.items():
            try:
                pub_key_obj = self._prepare_public_key(participant_pub_key)
                if not pub_key_obj:
                    print(f"[Security Error] Could not parse key for {p_id}")
                    continue

                encrypted_key = pub_key_obj.encrypt(new_media_key, padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                ))
                keys_map[p_id] = encrypted_key.hex()
            except Exception as e:
                print(f"[Security Error] Encryption failed for {p_id}: {e}")
                continue

        # שליחה רק אם הצלחנו ליצור מפתחות עבור כולם
        if len(keys_map) == len(valid_participants):
            self.dispatcher.send_msg(MsgType.UPDATE_ROOM_MEDIA_KEY, {
                Contract.ROOM_ID: room_id,
                "encrypted_keys_map": keys_map
            })
        else:
            print(
                f"[Security Error] Key rotation aborted: only {len(keys_map)}/{len(valid_participants)} keys generated.")

    def handle_deliver_media_key(self, data, code):
        encrypted_key_hex = data.get("encrypted_media_key")
        if not encrypted_key_hex: return

        private_key = serialization.load_pem_private_key(
            self.gui_state.get_state(StateKey.PRIVATE_CALL_KEY),
            password=None
        )

        try:
            decrypted_key = private_key.decrypt(bytes.fromhex(encrypted_key_hex), padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            ))
            self.gui_state.set_state(StateKey.ACTIVE_MEDIA_KEY, decrypted_key)

            udp_token = self.gui_state.get_state(StateKey.PENDING_UDP_TOKEN)
            if udp_token:
                self.gui_state.set_state(StateKey.CALL_ESTABLISHED, True)
                self.gui_state.set_state(StateKey.PENDING_UDP_TOKEN, udp_token)
                self.gui_state.set_state(StateKey.ACTIVE_MEDIA_KEY, decrypted_key)

        except Exception as e:
            print(f"[Security] Decryption failed: {e}")

    # --- 5. עזרים ---
    def _prepare_public_key(self, pub_key):
        if isinstance(pub_key, str):
            try:
                pub_key = bytes.fromhex(pub_key)  # אם זה hex
            except ValueError:
                pub_key = pub_key.encode('utf-8')  # אם זה PEM רגיל
        return serialization.load_pem_public_key(pub_key)

    def clear_call_state(self):
        self.gui_state.set_state(StateKey.ACTIVE_CALL_ROOM_ID, None)
        self.gui_state.set_state(StateKey.ACTIVE_MEDIA_KEY, None)
        self.gui_state.set_state(StateKey.PENDING_UDP_TOKEN, None)
        self.gui_state.set_state(StateKey.OPEN_CAMERA, False)
        self.gui_state.set_state(StateKey.CALL_ESTABLISHED, False)

class AuthService(BaseService):
    def __init__(self, dispatcher, gui_state, user_state):
        super().__init__(dispatcher, gui_state)
        self.user_state = user_state
        self._on_success_callback = None

        self.gui_state.register(StateKey.HANDSHAKE_ESTABLISHED, self.reconnect)

        handlers = [
            MsgType.LOGIN, MsgType.SIGNUP, MsgType.FORGOT_PASSWORD,
            MsgType.VERIFY_OTP, MsgType.RESEND_OTP, MsgType.RECONNECT,
        ]
        for msg_type in handlers:
            self.dispatcher.register(msg_type, self.handle_auth_response)

        self.update_map = {
            Contract.DISPLAY_NAME: (self.gui_state, StateKey.DISPLAY_NAME),
            Contract.IDENTITY: (self.gui_state, StateKey.IDENTITY),
            Contract.ROLE: (self.gui_state, StateKey.ROLE),
            Contract.PUBLIC_ID: (self.gui_state, StateKey.PUBLIC_ID),
            Contract.EMAIL: (self.gui_state, StateKey.EMAIL),
            Contract.TOKEN: (self.user_state, StateKey.TOKEN),
        }


    def handle_auth_response(self, data, code):

        if code !=MsgCodes.SUCCESS or code == MsgCodes.OTP_SENT:
            self.gui_state.set_state(StateKey.LOADING_STATUS, False)
            return

        self._update_user_states(data)
        is_admin = data.get(Contract.IS_ADMIN, 0)
        if is_admin:
            self.gui_state.set_state(StateKey.IS_ADMIN, 'בכיר')
        else:
            self.gui_state.set_state(StateKey.IS_ADMIN, 'סטנדרטית')

        if self._on_success_callback:
            self._on_success_callback()

        self.gui_state.set_state(StateKey.LOADING_STATUS, False)
        self.gui_state.set_state(StateKey.LOGGED_IN, True)

    def handle_auth_request(self, msg_type, data):
        if msg_type in [MsgType.LOGIN, MsgType.SIGNUP]:
            identity = data.pop(Contract.USERNAME, None) or \
                       data.pop(Contract.ID, None) or \
                       data.pop(Contract.EMAIL, None)
            data[Contract.IDENTITY] = identity
            data[Contract.ROLE] = self.gui_state.get_state(StateKey.ROLE)
        self.execute_auth_call(msg_type, data)

    def _update_user_states(self, payload):
        for p_key, (state_obj, s_key) in self.update_map.items():
            if (val := payload.get(p_key)) is not None:
                state_obj.set_state(s_key, val)

    def execute_auth_call(self, msg_type, data=None):
        self.gui_state.set_state(StateKey.LOADING_STATUS, True)

        payload = data or {}

        if msg_type in [MsgType.LOGIN, MsgType.SIGNUP, MsgType.FORGOT_PASSWORD, MsgType.RECONNECT, MsgType.VERIFY_OTP, MsgType.RESEND_OTP]:
            self.dispatcher.send_priority_msg(msg_type, payload)
            return
        self.dispatcher.send_msg(msg_type, payload)

    def reconnect(self, handshake_completed):
        if not handshake_completed:
            return

        session_token = self.user_state.get_state(StateKey.TOKEN)
        if not session_token:
            return

        payload = {
            Contract.TOKEN: session_token,
        }

        self.execute_auth_call(MsgType.RECONNECT, payload)