from app_constants import *
from gui_state_mgmt import *
import random

class ChatService:
    def __init__(self, dispatcher, gui_state):
        self.dispatcher = dispatcher
        self.gui_state = gui_state


    def fetch_older_messages(self, room_id, oldest_msg_id):
        payload = {
            Contract.ROOM_ID: room_id,
            Contract.ANCHOR_ID: oldest_msg_id,
        }
        self.dispatcher.dispatcher.send(MsgType.GET_OLDER_MESSAGES, payload)

    def send_message(self, room_id, content):

        client_nonce = str(random.randint(1000, 9999))

        payload = {
            Contract.ROOM_ID: room_id,
            Contract.CONTENT: content,
            Contract.NONCE: client_nonce
        }

        self.dispatcher.send_msg(MsgType.SEND_MSG, payload)
        return client_nonce

    def join_room(self, topic=None, room_id=None):
        payload = {}
        if room_id:
            payload[Contract.ROOM_ID] = room_id
        if topic:
            payload[Contract.TOPIC] = topic

        self.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def create_room(self, topic):
        payload = {
            Contract.TOPIC: topic
        }
        self.dispatcher.send_msg(MsgType.CREATE_CHAT_ROOM, payload)

class AuthService:
    def __init__(self, dispatcher, gui_state, user_state):
        self.dispatcher = dispatcher
        self.gui_state = gui_state
        self.user_state = user_state
        self._on_success_callback = None

        self.gui_state.register(StateKey.CONNECTED, self.reconnect)

        handlers = [
            MsgType.LOGIN,
            MsgType.SIGNUP,
            MsgType.FORGOT_PASSWORD,
            MsgType.VERIFY_OTP,
            MsgType.RESEND_OTP,
            MsgType.RECONNECT,
        ]
        for msg_type in handlers:
            self.dispatcher.register(msg_type, self.handle_auth_response)

        self.update_map = {
            Contract.DISPLAY_NAME: (self.gui_state, StateKey.DISPLAY_NAME),
            Contract.ROLE: (self.gui_state, StateKey.ROLE),
            Contract.PUBLIC_ID: (self.gui_state, StateKey.PUBLIC_ID),
            Contract.EMAIL: (self.gui_state, StateKey.GMAIL),
            Contract.TOKEN: (self.user_state, StateKey.TOKEN),
        }


    def handle_auth_response(self, data, code):
        if code not in [MsgCodes.SIGNUP_SUCCESS, MsgCodes.LOGIN_SUCCESS, MsgCodes.SUCCESS]:
            self.gui_state.set_state(StateKey.LOADING_STATUS, False)
            return

        self._update_user_states(data)

        if self._on_success_callback:
            self.gui_state.set_state(StateKey.LOGGED_IN, True)
            for k, v in data.items():
                try:
                    self.gui_state.set_state(k, v)
                except Exception as e:
                    pass
            self._on_success_callback()

        self.gui_state.set_state(StateKey.LOADING_STATUS, False)

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
            Contract.ROLE: self.gui_state.get_state(StateKey.ROLE)
        }

        self.execute_auth_call(MsgType.RECONNECT, payload)


