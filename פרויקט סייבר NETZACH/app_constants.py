from enum import StrEnum, Enum, IntEnum, auto
import time
import re

class AppScreens(StrEnum):
    AUTH = 'auth'
    CHAT = 'chat'


class StateKey(StrEnum):
    CONNECTED = "connected"
    IDENTIFIED = "identified"
    LOADING_STATUS = "loading_status"
    DISPLAY_NAME = "display_name"
    CODE = "code"
    PUBLIC_ID = "public_id"
    LAST_MSG_TYPE = "last_msg_type"
    LAST_PAYLOAD = "last_payload"
    TOKEN = "token"
    AUTHENTICATED = "authenticated"
    GMAIL = "gmail"
    ERROR_MSG = "error_msg"
    ROLE = "role"
    LOGGED_IN = "logged_in"
    IDENTITY = "identity"
    IS_ACTIVE = "is_active"
    USERNAME = "username"
    FREEZE_SCREEN = "freeze_screen"
    SHOW_USER_INFO = "show_user_info"
    CURRENT_ROOM_ID = "current_room_id"

    class RequestFactory:
        """יצירת בקשות מהלקוח לשרת"""

        @staticmethod
        def create(msg_type, data: dict = None):
            now = int(time.time())
            if not msg_type:
                return

            return {
                Contract.TYPE: msg_type,
                Contract.TIMESTAMP: now,
                Contract.DATA: data or {}
            }


class MsgType(StrEnum):
    """סוגי הפעולות שהשרת יודע לזהות"""
    LOGIN = "login"
    SIGNUP = "signup"
    VERIFY_OTP = "verify_otp"
    RESEND_OTP = "resend_otp"
    RECONNECT = "reconnect"
    FORGOT_PASSWORD = "forgot_password"
    GENERAL = "general"
    SYSTEM='system'

    CREATE_CHAT_ROOM = 'create_chat_room'
    SEND_MSG = "send_message"
    JOIN_ROOM = "join_room"
    ROOM_DETAILS = "room_details"
    RECEIVE_MSG = 'receive_message'

    GET_OLDER_MESSAGES = 'get_older_messages'


class ResponseUtils:
    @staticmethod
    def is_success(code):
        # 200-299 נחשב להצלחה בפרוטוקול שלנו
        return 200 <= code < 300


class UIColors:
    # צבעי מיתוג של Netzach
    ACCENT_GOLD = "#B0903D"  # הזהב המזוהה עם הפרויקט
    BG_DARK = "#0A1929"  # הכחול הכהה של הרקע

    # צבעי סטטוס (מבוסס על הלוגיקה של ה-Translator)
    SUCCESS = "#2ECC71"  # ירוק - לפעולות שהצליחו (2xx)
    ERROR = "#E74C3C"  # אדום - לשגיאות וחסימות (4xx, 5xx)
    WARNING = "#E67E22"  # כתום - לאזהרות והצפה (Flood)
    INFO = "#3498DB"  # כחול - למידע ועדכוני מערכת (1xx)

    # טקסט
    TEXT_MAIN = "#FFFFFF"
    TEXT_MUTED = "#808080"

class MsgCodes(IntEnum):
    # --- מידע ותשתית (1xx) ---
    CONNECTION_ESTABLISHED = 100
    CONNECTION_LOST = 101

    # --- הצלחות (2xx) ---
    SUCCESS = 200
    LOGIN_SUCCESS = 201
    SIGNUP_SUCCESS = 202
    OTP_SENT = 203
    EMAIL_VERIFIED = 204
    PASSWORD_RESET_SUCCESS = 205
    OTP_RESENT = 206
    PENDING = 207

    INVALID_FIELDS = 400
    UNAUTHORIZED = 401
    ACCESS_DENIED = 403
    NOT_FOUND = 404
    SESSION_EXPIRED = 419
    CONFLICT = 409
    BLOCKED_EMAIL = 410
    FLOOD_WARNING = 429

    INVALID_OTP = 444
    TOO_MANY_ATTEMPTS = 445


    INTERNAL_SERVER_ERROR = 500
    DATABASE_ERROR = 501
    SERVICE_UNAVAILABLE = 503


class Contract(StrEnum):
    TYPE = 'type'
    TIMESTAMP = 'timestamp'
    DATA = 'payload'
    CODE = 'code'
    STATUS = 'status'
    SUCCESS = 'success'
    FAILED = 'failed'

    IDENTITY = 'identity'
    USERNAME = 'username'
    ID = 'ID'
    PASSWORD = 'password'
    EMAIL = 'email'
    ROLE = 'role'
    TOKEN = 'session_token'
    PUBLIC_ID = 'public_id'
    DISPLAY_NAME = 'display_name'
    MSGS= 'messages'
    ANCHOR_ID = 'anchor_id'

    OTP_CODE = "otp_code"
    ATTEMPTS = 'attempts'

    TOPIC = 'topic'
    ROOM_ID = 'room_id'
    CONTENT = 'content'

    NATIONAL_ID = 'national_id'
    FULL_NAME = 'full_name'
    SENDER = 'sender_name'
    SENDER_PID = 'sender_p_id'
    ORG_TIME = 'origin_time'
    SERVER_TIME = 'server_time'

    NONCE = 'nonce'
    MSG_ID = 'msg_id'

    PARTICIPANTS = "participants"
    TOTAL_PARTICIPANTS = "total_participants"
    EVENT = 'event'
    USER = 'user'

    PURPOSE = 'purpose'
    EXPIRY = "expiry"

    IS_LOCKED = 'is_locked'
    CREATED_AT = 'created_at'


class Validator:
    EMAIL_PATTERN = r"(?i)^(?!.*\.{2})[a-z0-9!#$%&'*+/=?^_`{|}~.-]{2,64}@gmail\.com$"
    PASS_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,20}$"
    ID_PATTERN = r"^\d{9}$"
    USERNAME_PATTERN = r"^\S{3,15}$"
    OTP_CODE = r"\d{6}"

    @staticmethod
    def is_valid_email(email):
        return bool(re.match(Validator.EMAIL_PATTERN, email))