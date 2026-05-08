from app_constants import *
from gui_state_mgmt import *

class MsgDispatcher:
    def __init__(self, gui_state, msg_manager):
        self.gui_state = gui_state
        self.msg_manager = msg_manager
        self._handlers = {}

        self._system_dispatch = {
            MsgType.SYSTEM: self._handle_system_msg,
            MsgType.GENERAL: self._handle_general_msg
        }

    # ... (send_msg ו-register נשארים ללא שינוי)

    def _dispatch(self, msg_type, msg):
        # 1. חילוץ נתונים מיידי
        code = msg.get(Contract.CODE)
        data = msg.get(Contract.DATA, {})

        # 2. עדכון הסטייט כבר כאן - ה-GUI מגיב מיד!
        self.gui_state.set_state(StateKey.LAST_MSG_TYPE, msg_type)
        self.gui_state.set_state(StateKey.LAST_PAYLOAD, data)
        self.gui_state.set_state(StateKey.CODE, code)


        handler = self._handlers.get(msg_type, self._system_dispatch.get(msg_type))

        if handler:
            try:
                handler(data, code)
            except TypeError as e:
                print(f"Dispatcher Error in {msg_type}: {e}")

    def _handle_general_msg(self, data, code):
        self.gui_state.set_state(StateKey.LOADING_STATUS, False)


    def send_msg(self, msg_type, data):

        formatted_msg = RequestFactory.create(msg_type, data)

        if formatted_msg:
            print(formatted_msg)
            self.msg_manager.send_msg(formatted_msg)

    def register(self, msg_type , handler):
        self._handlers[msg_type]=handler

    def send_priority_msg(self, msg_type=None, data=None):

        formatted_msg = RequestFactory.create(msg_type, data)

        if formatted_msg:
            print(formatted_msg)
            self.msg_manager.set_priority_msg(formatted_msg)
        else:
            self.msg_manager.clear_outgoing_queue()
            self.msg_manager.set_priority_msg()

        self.msg_manager.connection_active.set()


    def _handle_system_msg(self, msg, code):
        updates = SYSTEM_STATE_MAP.get(code, {})
        for key, value in updates.items():
            self.gui_state.set_state(key, value)

        state_updates = msg.get("update_state", {})
        for key, value in state_updates.items():
            self.gui_state.set_state(key, value)

    def _handle_unknown(self, msg_type, msg):
        print(f"Unknown message type received: {msg}")