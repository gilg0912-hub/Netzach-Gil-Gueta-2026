from enum import StrEnum, IntEnum, auto, Enum
import time
import secrets
import string
import re
from typing import NamedTuple, Optional

# ==========================================
# 1. פרוטוקול התקשורת (Contract)
# ==========================================
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
    PASSWORD = 'password'
    EMAIL = 'email'
    ROLE = 'role'
    TOKEN = 'session_token'
    PUBLIC_ID = 'public_id'
    DISPLAY_NAME = 'display_name'


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


class RoomEvent(IntEnum):
    USER_JOINED = 1
    USER_LEFT = 2
    USER_RECONNECTED = 3
    TOPIC_CHANGED = 4
    ROOM_CLOSED = 5

# ==========================================
# 2. קודי תגובה וסוגי הודעות
# ==========================================
class MsgType(StrEnum):
    LOGIN = "login"
    SIGNUP = "signup"
    VERIFY_OTP = "verify_otp"
    RESEND_OTP= 'resend_otp'
    RECONNECT = "reconnect"
    SYNC_DATA = 'sync_data'
    ERROR = "error"
    FORGOT_PASSWORD = "forgot_password"
    GENERAL = "general"

    CREATE_CHAT_ROOM = 'create_chat_room'
    SEND_MSG= "send_message"
    JOIN_ROOM = "join_room"
    ROOM_DETAILS = "room_details"
    RECEIVE_MSG= 'receive_message'


class MsgCodes(IntEnum):
    # הצלחה (2xx)
    SUCCESS = 200
    LOGIN_SUCCESS = 201
    SIGNUP_SUCCESS = 202
    OTP_SENT = 203
    OTP_RESENT = 204


    INVALID_FIELDS = 400
    AUTH_FAILED = 401
    NOT_FOUND = 404
    SESSION_EXPIRED = 401
    USER_ALREADY_EXISTS = 409
    BLOCKED_EMAIL = 410
    FLOOD_WARNING=429
    INVALID_OTP = 444
    TOO_MANY_ATTEMPTS = 445
    ACCESS_DENIED = 403

    DATABASE_ERROR = 306
    SERVER_ERROR = 500


# ==========================================
# 3. ניהול תפקידים (User Roles)
# ==========================================
class UserRole(StrEnum):
    STANDARD = ("standard", "Standards", "username", "username")
    TEACHER = ("teacher", "Teachers", "national_id", "full_name")
    STUDENT = ("student", "Students", "national_id", "full_name")

    def __new__(cls, value, table, id_field, display_name):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.table = table
        obj.id_field = id_field
        obj.display_name = display_name
        return obj

    @staticmethod
    def get_role_config(role_name):
        if not role_name: return None
        role_name_lower = str(role_name).lower()
        for role in UserRole:
            if role == role_name_lower:
                return role
        return None

class MonitorKey(Enum):
    """מפתחות לניהול הנתונים בתוך ה-Traffic Monitor"""
    COUNT = auto()            # מספר הודעות כללי
    START_TIME = auto()       # תחילת חלון זמן (קצב)
    LAST_BLIND_HASH = auto()        # Hash של התוכן האחרון
    LAST_LOGICAL_HASH = auto()        # Hash של התוכן האחרון
    DUPE_COUNT = auto()       # מונה הודעות זהות ברצף
    LAST_MSG_TIME = auto()    # זמן שליחת ההודעה האחרונה (לסליחה על כפילות)
    LAST_DUPE_TS= auto()
# ==========================================
# 4. מבני הודעות (Payload Validation)
# ==========================================
class MsgStructures:
    # הגדרת שדות חובה לכל סוג בקשה שמגיעה מהלקוח


    # הגדרת שדות שיחזרו בתגובה ללקוח (whitelist)
    _RESPONSES = {
        MsgCodes.LOGIN_SUCCESS: [Contract.PUBLIC_ID, Contract.USERNAME, Contract.TOKEN, Contract.ROLE, Contract.DISPLAY_NAME, Contract.EMAIL],
        MsgCodes.SIGNUP_SUCCESS: [Contract.PUBLIC_ID, Contract.EMAIL, Contract.DISPLAY_NAME, Contract.EMAIL],
        MsgCodes.OTP_SENT: [Contract.EMAIL],
        MsgCodes.OTP_RESENT: [Contract.EMAIL, Contract.ATTEMPTS],
    }

    _REQUESTS = {
        MsgType.LOGIN: [{Contract.IDENTITY, Contract.PASSWORD, Contract.ROLE}],
        MsgType.SIGNUP: [{Contract.IDENTITY, Contract.PASSWORD, Contract.ROLE, Contract.EMAIL}],
        MsgType.VERIFY_OTP: [{Contract.OTP_CODE}],
        MsgType.RECONNECT: [{Contract.TOKEN, Contract.ROLE}],
        MsgType.JOIN_ROOM: [
            {Contract.ROOM_ID},
            {Contract.TOPIC}
        ]
    }

    @staticmethod
    def get_allowed_structures(msg_type: MsgType):
        return MsgStructures._REQUESTS.get(msg_type, [])

    @staticmethod
    def get_response_fields(code: MsgCodes):
        # מחזיר שדות לפי הקוד (כי המבנה תלוי בתוצאה, לא רק בסוג ההודעה)
        return MsgStructures._RESPONSES.get(code, [])


# ==========================================
# 5. מנוע התגובות (Response Factory)
# ==========================================
class ResponseFactory:
    @staticmethod
    def create(msg_type: MsgType, code: MsgCodes, raw_data: dict = {}):
        raw_data = raw_data or {}

        status = Contract.SUCCESS if 200 <= code < 300 else Contract.FAILED

        allowed_fields = MsgStructures.get_response_fields(code)

        if status == Contract.SUCCESS:
            payload = {f: raw_data[f] for f in allowed_fields if f in raw_data}
        else:
            payload = raw_data


        return {
            Contract.TYPE: msg_type,
            Contract.STATUS: status,
            Contract.CODE: int(code),
            Contract.TIMESTAMP: int(time.time()),
            Contract.DATA: payload,
        }
    @staticmethod
    def error(msg_type: MsgType=MsgType.ERROR, code: MsgCodes=MsgCodes.SERVER_ERROR, raw_data: dict = None):
        return ResponseFactory.create(msg_type, code, raw_data)


# ==========================================
# 6. שירותים נוספים (Validator & OTP)
# ==========================================
class Validator:
    _PATTERNS = {
        Contract.EMAIL: r"(?i)^(?!.*\.{2})[a-z0-9!#$%&'*+/=?^_`{|}~.-]{2,64}@gmail\.com$",
        Contract.PASSWORD: r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,20}$",
        Contract.USERNAME: r"^[a-zA-Z0-9]{3,15}$",  # 3-15 תווים אלפא-נומריים
        Contract.NATIONAL_ID: r"^\d{9}$",  # 9 ספרות בדיוק
        Contract.OTP_CODE: r"^\d{6}$"
    }

    @staticmethod
    def validate_structure(msg_type, payload):
        if not isinstance(payload, dict): return False

        payload_keys = set(payload.keys())
        optional_structures = MsgStructures.get_allowed_structures(msg_type)
        return any(payload_keys == required_set for required_set in optional_structures)

    @staticmethod
    def is_valid_field(field, value):
        pattern= Validator._PATTERNS.get(field)

        return re.match(pattern, value)

class OTPService:
    @staticmethod
    def generate_code(length=6):
        return ''.join(secrets.choice(string.digits) for _ in range(length))


class PolicyAction(NamedTuple):
    response: Optional[dict] = None
    should_block: bool = False
    stop_processing: bool = False
    wait_time: int = 0