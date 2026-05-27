from gui_state_mgmt import *
from abc import abstractmethod
from chat_widgets import ChatRoom
from app_constants import Contract, RoomEvent
import random


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
        self.dispatcher.register(MsgType.SYNC_DATA, self.handle_sync_data)
        self.dispatcher.register(MsgType.JOIN_ROOM, self.handle_join_room_response)
        self.dispatcher.register(MsgType.GET_OLDER_MESSAGES, self.handle_older_messages_response)
        self.dispatcher.register(MsgType.GET_OLDER_TOPICS, self.handle_older_topics),
        self.dispatcher.register(MsgType.GET_OLDER_GROUPS, self.handle_older_groups)
        self.dispatcher.register(MsgType.CREATE_CHAT_ROOM, self.handle_new_room)
        self.dispatcher.register(MsgType.SEND_MSG, self.handle_send_msg_response)
        self.dispatcher.register(MsgType.RECEIVE_MSG, self.handle_receive_msg)
        self.gui_state.register(StateKey.CONNECTED, self._on_connection_changed)

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
