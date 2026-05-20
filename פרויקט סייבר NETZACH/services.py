from gui_state_mgmt import *
from abc import abstractmethod
from chat_widgets import ChatRoom
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
        self.dispatcher.register(MsgType.GET_OLDER_TOPICS, self.handle_older_topics)
        self.dispatcher.register(MsgType.CREATE_CHAT_ROOM, self.handle_new_room)
        self.dispatcher.register(MsgType.SEND_MSG, self.handle_send_msg_response)
        self.dispatcher.register(MsgType.RECEIVE_MSG, self.handle_receive_msg)

    def handle_sync_data(self, data, code):
        if code == MsgCodes.SUCCESS:

            if Contract.ROOMS in data:
                self._update_rooms_list(data[Contract.ROOMS])

            if Contract.TOPICS in data:
                self._update_topics_list(data[Contract.TOPICS])

        else:
            print(f"[ChatService] Sync Data failed with code: {code}")
    """
                if Contract.MESSAGES in data:
                    for msg in data[Contract.MESSAGES]:
                        self._update_messages_list(
                            room_id=msg.get(Contract.ROOM_ID),
                            messages_to_add=[msg],
                            is_older=False
                        )

    """

    def join_room_by_code(self, room_code):
        if not room_code:
            return
        payload = {Contract.INVITE_CODE: room_code}
        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def join_room_by_category(self, category):
        if not category:
            return
        payload = {Contract.CATEGORY: category}
        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def handle_receive_msg(self, data, code):
        if code == MsgCodes.SUCCESS:
            self._update_messages_list(
                room_id=data.get(Contract.ROOM_ID),
                messages_to_add=[data],
                is_older=False
            )

    def handle_older_messages_response(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        messages = data.get('items', [])
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
                "items": [],
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
            "items": new_items,
            "is_older": is_older,
            "end_of_data": end_of_data
        })

    def _update_rooms_list(self, rooms_to_update, at_top=False):
        if len(rooms_to_update) == 0 or not rooms_to_update[0]:
            return

        processed_items = []
        updated_room_ids = set()

        for room_dict in rooms_to_update:
            r_id = str(room_dict.get(Contract.ID))
            updated_room_ids.add(r_id)

            if r_id not in self.rooms:
                self.rooms[r_id] = ChatRoom.from_dict(room_dict)
            else:
                self.rooms[r_id].topic = room_dict.get(Contract.TOPIC, self.rooms[r_id].topic)
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
            "items": processed_items,
            "on_top": at_top
        })

    def handle_join_room_response(self, data, code):
        if code == MsgCodes.SUCCESS:
            self._update_rooms_list([data])

    def _update_topics_list(self, topics_to_add, at_top=False, end_of_data=False):
        if not topics_to_add and not end_of_data:
            return

        current_list = self.gui_state.get_state(StateKey.SYNC_TOPICS)
        if not isinstance(current_list, list):
            current_list = []

        existing_ids = {str(d.get(Contract.ID)) for d in current_list if d.get(Contract.ID) is not None}

        new_items = [t for t in topics_to_add if str(t.get(Contract.ID)) not in existing_ids]

        if not new_items:
            if end_of_data:
                self.gui_state.set_state(StateKey.TOPICS_UI_SIGNAL, {
                    "items": [],
                    "on_top": at_top,
                    "end_of_data": True
                })
            return

        if at_top:
            updated_list = new_items + current_list
        else:
            updated_list = current_list + new_items

        self.gui_state.set_state(StateKey.SYNC_TOPICS, updated_list)

        self.gui_state.set_state(StateKey.TOPICS_UI_SIGNAL, {
            "items": new_items,
            "on_top": at_top,
            "end_of_data": end_of_data
        })

    def handle_older_topics(self, data, code):
        topics = data.get('items', [])
        is_end = data.get('end_of_data', False)

        if code == MsgCodes.SUCCESS:
            self._update_topics_list(
                topics_to_add=topics,
                at_top=False,
                end_of_data=is_end
            )
        else:
            self.gui_state.set_state(StateKey.TOPICS_UI_SIGNAL, {
                "items": [],
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

        self.dispatcher.send_msg(MsgType.SEND_MSG, payload)
        return client_nonce

    def join_room(self, category=None, room_id=None):
        payload = {}
        if room_id:
            payload[Contract.ROOM_ID] = room_id
        if category:
            payload[Contract.CATEGORY] = category

        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def create_room(self, payload):
        self.dispatcher.send_msg(MsgType.CREATE_CHAT_ROOM, payload)

    def fetch_older_topics(self, last_topic_id):
        payload = {
            Contract.TOPIC_ID: last_topic_id,
        }
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




class AuthService(BaseService):
    def __init__(self, dispatcher, gui_state, user_state):
        super().__init__(dispatcher, gui_state)
        self.user_state = user_state
        self._on_success_callback = None

        self.gui_state.register(StateKey.CONNECTED, self.reconnect)

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
        self._on_success_callback()

        self.gui_state.set_state(StateKey.LOADING_STATUS, False)
        self.gui_state.set_state(StateKey.LOGGED_IN, True)

    def handle_auth_request(self, msg_type, data):
        if msg_type in [MsgType.LOGIN, MsgType.SIGNUP]:
            identity = data.pop(Contract.USERNAME, None) or \
                       data.pop(Contract.ID, None) or \
                       data.pop(Contract.EMAIL, None)
            data[Contract.IDENTITY] = identity
        self.execute_auth_call(msg_type, data)

    def _update_user_states(self, payload):
        for p_key, (state_obj, s_key) in self.update_map.items():
            if (val := payload.get(p_key)) is not None:
                state_obj.set_state(s_key, val)

    def execute_auth_call(self, msg_type, data=None):
        self.gui_state.set_state(StateKey.LOADING_STATUS, True)

        payload = data or {}

        if msg_type in [MsgType.LOGIN, MsgType.SIGNUP, MsgType.FORGOT_PASSWORD, MsgType.RECONNECT]:
            self.dispatcher.send_priority_msg(msg_type, payload)
            return
        self.dispatcher.send_msg(msg_type, payload)

    def reconnect(self, is_connected):
        if is_connected:
            return

        session_token = self.user_state.get_state(StateKey.TOKEN)
        if not session_token:
            return

        payload = {
            Contract.TOKEN: session_token,
        }

        self.execute_auth_call(MsgType.RECONNECT, payload)

