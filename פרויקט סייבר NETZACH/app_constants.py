from enum import StrEnum, IntEnum, auto
import time
import re


class RoomEvent(IntEnum):
    USER_JOINED = 1
    USER_LEFT = 2
    USER_RECONNECTED = 3
    TOPIC_CHANGED = 4
    ROOM_CLOSED = 5

class AppScreens(StrEnum):
    AUTH = 'auth'
    CHAT = 'chat'

class StateKey(StrEnum):
    CONNECTED = "connected"
    LOADING_STATUS = "loading_status"
    DISPLAY_NAME = "display_name"
    CODE = "code"
    PUBLIC_ID = "public_id"
    HANDSHAKE_ESTABLISHED = "handshake_established"
    LAST_MSG_TYPE = "last_msg_type"
    LAST_PAYLOAD = "last_payload"
    TOKEN = "session_token"
    AUTHENTICATED = "authenticated"
    EMAIL = "email"
    ERROR_MSG = "error_msg"
    ROLE = "role"
    LOGGED_IN = "logged_in"
    IDENTITY = "identity"
    IS_ACTIVE = "is_active"
    IS_ADMIN = "is_admin"
    FREEZE_SCREEN = "freeze_screen"
    SHOW_USER_INFO = "show_user_info"
    CURRENT_ROOM_ID = "current_room_id"
    SYNC_ROOMS = 'sync_rooms'
    SYNC_TOPICS = 'sync_topics'
    SYNC_GROUPS = 'sync_groups'
    SYNC_MESSAGES = 'sync_messages'
    TOPICS_UI_SIGNAL = 'topics_ui_signal'
    ROOMS_UI_SIGNAL = 'rooms_ui_signal'
    MESSAGES_UI_SIGNAL = 'messages_ui_signal'
    GROUPS_UI_SIGNAL = 'groups_ui_signal'
    SUGGESTED_TOPIC = 'suggested_topic'
    SUGGESTED_TOPIC_ID = 'suggested_topic_id'
    RELEASE_BTNS = 'release_btn'
    ROOM_VIDEO_STATUS = 'room_video_status'

    PUBLIC_CALL_KEY = 'public_call_key'
    PRIVATE_CALL_KEY = 'private_call_key'

    OPEN_CAMERA = 'open_camera'
    CALL_ESTABLISHED = 'call_established'
    ACTIVE_CALL_ROOM_ID ='active_call_room_id'
    ACTIVE_MEDIA_KEY = 'active_media_key'
    PENDING_UDP_TOKEN = 'pending_udp_token'

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

    KEY_EXCHANGE = 'key_exchange'

    LOGIN = "login"
    SIGNUP = "signup"
    VERIFY_OTP = "verify_otp"
    RESEND_OTP = "resend_otp"
    RECONNECT = "reconnect"
    FORGOT_PASSWORD = "forgot_password"
    GENERAL = "general"
    SYSTEM='system'

    SYNC_DATA = 'sync_data'
    CREATE_CHAT_ROOM = 'create_chat_room'
    SEND_MSG = "send_message"
    JOIN_ROOM = "join_room"
    ROOM_DETAILS = "room_details"
    RECEIVE_MSG = 'receive_message'

    GET_OLDER_MESSAGES = 'get_older_messages'
    GET_OLDER_TOPICS = 'get_older_topics'
    GET_OLDER_GROUPS = 'get_older_groups'

    CALL_STATE = 'call_state'
    START_CALL = 'start_call'
    JOIN_CALL = 'join_call'
    USER_JOINED_CALL = 'user_joined_call'
    USER_LEFT_CALL = 'user_left_call'
    LEAVE_CALL = 'leave_call'
    CALL_ESTABLISHED = 'call_established'
    REQ_MEDIA_KEY = 'req_media_key'
    UPDATE_ROOM_MEDIA_KEY = 'update_room_media_key'
    DELIVER_CALL_MEDIA_KEY = 'deliver_call_media_key'



    LOGOUT = 'logout'

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


from enum import IntEnum


class MsgCodes(IntEnum):
    # --- מידע ותשתית כללית (10x) ---
    CONNECTION_ESTABLISHED = 100
    CONNECTION_LOST = 102

    # --- תשתית הצפנה ולחיצת יד (11x) ---
    RSA_KEY = 110
    SESSION_KEY = 111
    HANDSHAKE_ESTABLISHED = 112

    # --- הצלחות (2xx) ---
    SUCCESS = 200
    LOGIN_SUCCESS = 201
    SIGNUP_SUCCESS = 202
    OTP_SENT = 203
    OTP_RESENT = 204
    PASSWORD_RESET_SUCCESS = 205
    PENDING = 207

    # --- שגיאות לקוח (4xx) ---
    INVALID_FIELDS = 400
    SESSION_EXPIRED = 401
    ACCESS_DENIED = 403
    NOT_FOUND = 404
    CONFLICT = 409
    BLOCKED_EMAIL = 410
    FLOOD_WARNING = 429
    INVALID_OTP = 444
    TOO_MANY_ATTEMPTS = 445
    ROOM_NOT_FOUND = 460

    # --- שגיאות שרת (5xx) ---
    INTERNAL_SERVER_ERROR = 500
    DATABASE_ERROR = 501
    SERVICE_UNAVAILABLE = 503

class Contract(StrEnum):
    TYPE = 'type'
    ALLOWED_TYPE = 'allowed_type'
    TIMESTAMP = 'timestamp'
    DATA = 'payload'
    CODE = 'code'
    STATUS = 'status'
    SUCCESS = 'success'
    FAILED = 'failed'

    IDENTITY = 'identity'
    USERNAME = 'username'
    ID = 'id'
    PASSWORD = 'password'
    EMAIL = 'email'
    ROLE = 'role'
    TOKEN = 'session_token'
    PUBLIC_ID = 'public_id'
    DISPLAY_NAME = 'display_name'
    MSGS= 'messages'
    ANCHOR_ID = 'anchor_id'
    ITEMS = 'items'
    IS_ADMIN ='is_admin'
    OTP_CODE = "otp_code"
    ATTEMPTS = 'attempts'

    CATEGORY = 'category'
    TOPIC ='topic'
    TOPIC_ID = 'topic_id'
    ROOM_ID = 'room_id'
    ROOM_CODE ='room_code'
    CONTENT = 'content'
    ROOMS = 'rooms'
    TOPICS = 'topics'

    NATIONAL_ID = 'national_id'
    FULL_NAME = 'full_name'
    SENDER = 'sender_name'
    SENDER_PID = 'sender_p_id'
    ORG_TIME = 'origin_time'
    SERVER_TIME = 'server_time'
    NAME = 'name'
    SUMMARY = 'summary'

    NONCE = 'nonce'
    MSG_ID = 'msg_id'

    PARTICIPANTS = "participants"
    TOTAL_PARTICIPANTS = "total_participants"
    EVENT = 'event'
    USER = 'user'

    PURPOSE = 'purpose'
    EXPIRY = "expiry"

    IS_OPEN = 'is_open'
    CREATED_AT = 'created_at'
    CREATED_BY = 'created_by'
    INVITE_CODE = 'invite_code'

    DISTRIBUTOR_ID = 'distributor_id'
    IS_CALL_ACTIVE = 'is_call_active'
    PUBLIC_CALL_KEY = 'public_call_key'
    MEDIA_KEY = 'media_key'
    ACTIVE_MEDIA_KEY = 'active_call_media_key'
    UDP_TOKEN = 'udp_token'
    CALL_STATE = 'call_state'


class Validator:
    EMAIL_PATTERN = r"(?i)^(?!.*\.{2})[a-z0-9!#$%&'*+/=?^_`{|}~.-]{2,64}@gmail\.com$"
    PASS_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,20}$"
    ID_PATTERN = r"^\d{9}$"
    USERNAME_PATTERN = r"^(?=.*[a-zA-Z])[a-zA-Z0-9]{3,15}$"
    OTP_CODE = r"\d{6}"

    @staticmethod
    def is_valid_email(email):
        return bool(re.match(Validator.EMAIL_PATTERN, email))

class UserRole(StrEnum):
    STANDARD = "standard"
    STUDENT = "student"
    TEACHER = "teacher"