from app_constants import *
from gui_state_mgmt import *
import threading
import traceback
import time


class MsgDispatcher:
    def __init__(self, gui_state, msg_manager):
        self.gui_state = gui_state
        self.msg_manager = msg_manager
        self._handlers = {}

        self.unban_time = 0
        self.unban_lock = threading.Lock()

        self._system_dispatch = {
            MsgType.SYSTEM: self._handle_system_msg,
            MsgType.GENERAL: self._handle_general_msg
        }

    def _dispatch(self, msg_type, msg):
        code = msg.get(Contract.CODE)
        data = msg.get(Contract.DATA, {})

        if msg_type in [MsgType.LOGIN, MsgType.SIGNUP, MsgType.RECONNECT] and code == MsgCodes.SUCCESS:
            print("Dispatcher: Auth success, unlocking queue.")
            self.msg_manager.is_authorized.set()

        self.gui_state.set_state(StateKey.LAST_MSG_TYPE, msg_type)
        self.gui_state.set_state(StateKey.LAST_PAYLOAD, data)
        self.gui_state.set_state(StateKey.CODE, code)

        handler = self._handlers.get(msg_type, self._system_dispatch.get(msg_type))

        if handler:
            try:
                keep_locked = handler(data, code)
                if not keep_locked:
                    self.gui_state.set_state(StateKey.RELEASE_BTNS, 'normal')


            except Exception as e:

                # 🟢 תיקון: תופסים כל שגיאה ולא רק TypeError

                print(f"[Dispatcher Critical Error] in {msg_type}: {e}")

                traceback.print_exc()
                self.gui_state.set_state(StateKey.RELEASE_BTNS, 'normal')

                self.gui_state.set_state(StateKey.LOADING_STATUS, False)

    def _handle_general_msg(self, data, code):
        self.gui_state.set_state(StateKey.LOADING_STATUS, False)

        if code == MsgCodes.ACCESS_DENIED:
            expiry = data.get(Contract.EXPIRY, 600)
            self.msg_manager.is_banned.set()
            self.msg_manager.clear_outgoing_queue()

            # תיקון: מעדכנים את unban_time כדי שטיימרים קצרים לא יבטלו ban ארוך
            with self.unban_lock:
                self.unban_time = time.time() + expiry

            # מפעילים טיימר שינקה את is_banned אחרי שהזמן עובר
            threading.Thread(target=self._cooldown_ui, args=(expiry,), daemon=True).start()
            return True

        elif code == MsgCodes.FLOOD_WARNING:
            expiry = data.get(Contract.EXPIRY, 5)
            self.gui_state.set_state(StateKey.RELEASE_BTNS, 'disabled')

            # תיקון: מעדכנים את unban_time גם כאן
            with self.unban_lock:
                self.unban_time = time.time() + expiry

            threading.Thread(target=self._cooldown_ui, args=(expiry,), daemon=True).start()
            return True  # נשאיר את הכפתורים נעולים — _cooldown_ui ישחרר בזמן

        return False

    def _cooldown_ui(self, expiry):
        time.sleep(expiry + 1.0)

        with self.unban_lock:
            if time.time() >= self.unban_time:
                self.gui_state.set_state(StateKey.RELEASE_BTNS, 'normal')
                self.msg_manager.is_banned.clear()
                print("[Dispatcher] Cooldown finished. UI and Network released.")
            else:
                print("[Dispatcher] Cooldown thread ignored: a longer ban is still active.")

    def send_msg(self, msg_type, data):
        self.gui_state.set_state(StateKey.RELEASE_BTNS, 'disabled')
        formatted_msg = RequestFactory.create(msg_type, data)

        if formatted_msg:
            print(formatted_msg)
            self.msg_manager.send_msg(formatted_msg)

    def register(self, msg_type, handler):
        self._handlers[msg_type] = handler

    def send_priority_msg(self, msg_type=None, data=None):
        formatted_msg = RequestFactory.create(msg_type, data)

        if formatted_msg:
            print(formatted_msg)
            self.msg_manager.set_priority_msg(formatted_msg)

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