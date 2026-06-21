import time
import weakref
from app_constants import MsgType, Contract, MsgCodes, StateKey, UIColors

class GUI_State:
    def __init__(self):
        # אתחול כל המצבים לערכי ברירת מחדל
        self.state = {
            StateKey.CONNECTED: False,
            StateKey.PUBLIC_ID: None,
            StateKey.LOGGED_IN: False,
            StateKey.HANDSHAKE_ESTABLISHED: False,
            StateKey.LOADING_STATUS: False,
            StateKey.FREEZE_SCREEN: False,
            StateKey.CODE: "",
            StateKey.DISPLAY_NAME: '',
            StateKey.IS_ADMIN: False,
            StateKey.SHOW_USER_INFO: False,

            # --- השינוי כאן: רק IDENTITY נשאר ---
            StateKey.IDENTITY: "",

            StateKey.EMAIL: "",
            StateKey.ROLE: "",
            StateKey.LAST_PAYLOAD: None,
            StateKey.LAST_MSG_TYPE: None,
            StateKey.TOKEN: None,
            StateKey.CURRENT_ROOM_ID: None,
            StateKey.SYNC_ROOMS: [],
            StateKey.SYNC_TOPICS: [],
            StateKey.SYNC_GROUPS: [],
            StateKey.SYNC_MESSAGES: [],
            StateKey.TOPICS_UI_SIGNAL: None,
            StateKey.ROOMS_UI_SIGNAL: None,
            StateKey.GROUPS_UI_SIGNAL: None,
            StateKey.MESSAGES_UI_SIGNAL: None,
            StateKey.RELEASE_BTNS: 'normal',
            StateKey.ACTIVE_CALL_ROOM_ID: None,
            StateKey.ACTIVE_MEDIA_KEY: None,
            StateKey.OPEN_CAMERA: False,
            StateKey.CALL_ESTABLISHED: None,
            StateKey.PENDING_UDP_TOKEN: None,
            StateKey.PUBLIC_CALL_KEY: None,
            StateKey.PRIVATE_CALL_KEY: None,
            StateKey.ROOM_VIDEO_STATUS: None,
            }
        # יצירת רשימת מאזינים לכל מפתח
        self.listeners = {k: [] for k in self.state.keys()}

    def get_state(self, key: StateKey):
        return self.state.get(key)

    def set_state(self, key: StateKey, value):
        if key in self.state:
            if self.state[key] != value:
                self.state[key] = value

                self._notify_listeners(key, value)
        else:
            print(f"Critcal Error: {key} is not defined in GUI_State!")

    def register(self, key: StateKey, listener):
        if key in self.state:
            self.listeners[key]= [r for r in self.listeners[key] if r()]
            ref = weakref.WeakMethod(listener)
            self.listeners[key].append(ref)

            listener(self.state[key])
        else:
            print(f"Warning: Cannot register to unknown key {key}")

    def _notify_listeners(self, key, value):
        still_alive = []
        for ref in self.listeners[key]:
            callback = ref()
            if callback:
                callback(value)
                still_alive.append(ref)
        self.listeners[key] = still_alive

    def unregister(self, key: StateKey, listener):
        if key in self.state:
            # בונה את הרשימה מחדש ומעיפה רק את הפונקציה הספציפית שביקשת
            self.listeners[key] = [r for r in self.listeners[key] if r() is not None and r() != listener]

SYSTEM_STATE_MAP = {
    MsgCodes.CONNECTION_LOST: {
        StateKey.CONNECTED: False,
        StateKey.LOADING_STATUS: False,
    },

    MsgCodes.CONNECTION_ESTABLISHED: {
        StateKey.CONNECTED: True,
    },

    MsgCodes.SESSION_EXPIRED: {
        StateKey.LOADING_STATUS: False,
        StateKey.CODE: MsgCodes.SESSION_EXPIRED
    },
}

class RequestFactory:
    """יצירת בקשות מהלקוח לשרת"""

    @staticmethod
    def create(msg_type: MsgType, data: dict = None):
        now = int(time.time())
        if not msg_type:
            return

        return {
            Contract.TYPE: msg_type,
            Contract.TIMESTAMP: now,
            Contract.DATA: data or {}
        }

class ResponseTranslator:
    _MESSAGES = {
        # הצלחות
        MsgCodes.PENDING: "...הבקשה בטיפול, אנא המתן",
        MsgCodes.OTP_SENT: ":קוד אימות נשלח לתיבת המייל שלך\n{email}",
        MsgCodes.SUCCESS: '',
        # שגיאות לקוח
        MsgCodes.INVALID_FIELDS: ".אחד או יותר מהשדות שהזנת אינם תקינים",
        MsgCodes.CONFLICT: ".שם המשתמש או האימייל כבר קיימים במערכת",
        MsgCodes.FLOOD_WARNING: ".קצב הפעולות מהיר מדי. נא להמתין: {expiry}",
        MsgCodes.TOO_MANY_ATTEMPTS: ".יותר מדי ניסיונות כושלים. החשבון ננעל זמנית",
        MsgCodes.SESSION_EXPIRED: ".פג התוקף של קוד האימות",
        MsgCodes.ACCESS_DENIED: "נחסמת! נסה שוב בעוד: {expiry}",
        MsgCodes.INVALID_OTP: ":קוד האימות שהזנת שגוי, נסה שוב\n{email}\n(ניסיון {attempts} מתוך 3)",
        MsgCodes.BLOCKED_EMAIL: "יותר מדי ניסיונות למייל זה. נסה שוב מאוחר יותר",
        MsgCodes.OTP_RESENT: ':קוד אימות נשלח מחדש למייל\n {email}',


        # שגיאות שרת
        MsgCodes.DATABASE_ERROR: ".שגיאה בגישה למסד הנתונים. נא לנסות מאוחר יותר",
        MsgCodes.INTERNAL_SERVER_ERROR: ".שגיאת שרת פנימית. הצוות הטכני עודכן",
        MsgCodes.NOT_FOUND: ".בקשה לא מוכרת נשלחה לשרת",
        MsgCodes.CONNECTION_ESTABLISHED: "חיבור חודש בהצלחה",
        MsgCodes.CONNECTION_LOST: '...החיבור אבד',

        MsgCodes.ROOM_NOT_FOUND: 'החדר המבוקש לא נמצא'

    }

    _COLOR_OVERRIDES = {
        MsgCodes.CONNECTION_LOST: UIColors.ERROR,
        MsgCodes.FLOOD_WARNING: UIColors.WARNING,
    }

    @classmethod
    def get_message(cls, code, **data):

        template = cls._MESSAGES.get(code, f" שגיאה לא ידועה ({code})")
        try:
            return template.format(**data)
        except (KeyError, ValueError):
            return template

    @classmethod
    def get_color(cls, code):
        if code in cls._COLOR_OVERRIDES:
            return cls._COLOR_OVERRIDES[code]
        range_map = {1: UIColors.INFO, 2: UIColors.SUCCESS, 4: UIColors.ERROR, 5: UIColors.ERROR}
        return range_map.get(code // 100, UIColors.TEXT_MUTED)