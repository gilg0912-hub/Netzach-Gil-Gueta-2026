from enum import StrEnum, IntEnum, auto, Enum
import time
import secrets
import string
import re
from typing import NamedTuple, Optional


class Contract(StrEnum):
    TYPE = 'type'
    TIMESTAMP = 'timestamp'
    DATA = 'payload'
    CODE = 'code'
    STATUS = 'status'
    SUCCESS = 'success'
    FAILED = 'failed'


    IDENTITY = 'identity'
    ID =    'id'
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
    TOPIC_ID = 'topic_id'
    CATEGORY = 'category'
    SUMMARY='summary'
    ROOM_ID = 'room_id'
    ROOMS = 'rooms'
    TOPICS = 'topics'
    CONTENT = 'content'


    NATIONAL_ID = 'national_id'
    FULL_NAME = 'full_name'
    SENDER = 'sender_name'
    SENDER_PID = 'sender_p_id'
    ORG_TIME = 'origin_time'
    SERVER_TIME = 'server_time'


    NONCE = 'nonce'
    MSG_ID = 'msg_id'
    ANCHOR_ID = 'anchor_id'


    PARTICIPANTS = "participants"
    TOTAL_PARTICIPANTS = "total_participants"
    EVENT = 'event'
    USER = 'user'


    PURPOSE = 'purpose'
    EXPIRY = "expiry"

    IS_LOCKED = 'is_locked'
    IS_OPEN = 'is_open'
    CREATED_AT = 'created_at'
    NAME = 'name'
    INVITE_CODE = 'invite_code'

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

    GET_OLDER_MESSAGES = 'get_older_messages'
    GET_OLDER_TOPICS = 'get_older_topics'


class MsgCodes(IntEnum):
    SUCCESS = 200
    OTP_SENT = 203
    OTP_RESENT = 204


    INVALID_FIELDS = 400
    AUTH_FAILED = 401

    NOT_FOUND = 404
    ROOM_NOT_FOUND = 460

    SESSION_EXPIRED = 401
    USER_ALREADY_EXISTS = 409
    BLOCKED_EMAIL = 410
    FLOOD_WARNING=429
    INVALID_OTP = 444
    TOO_MANY_ATTEMPTS = 445
    ACCESS_DENIED = 403

    DATABASE_ERROR = 306
    SERVER_ERROR = 500


class UserRole(StrEnum):

    STANDARD = ("standard", Contract.USERNAME, None, "identity")
    TEACHER = ("teacher", Contract.ID, "teachers", "full_name")
    STUDENT = ("student", Contract.ID, "students", "full_name")

    def __new__(cls, value, id_field, child_table, display_field):
        obj = str.__new__(cls, value)
        obj._value_ = value

        obj.id_field = id_field
        obj.child_table = child_table
        obj.display_field = display_field

        return obj

    @staticmethod
    def get_role_config(role_name):
        if not role_name:
            return None
        role_name_lower = str(role_name).lower()
        for role in UserRole:
            if role == role_name_lower:
                return role
        return None

class MonitorKey(Enum):

    COUNT = auto()
    START_TIME = auto()
    LAST_BLIND_HASH = auto()
    LAST_LOGICAL_HASH = auto()
    DUPE_COUNT = auto()
    LAST_MSG_TIME = auto()
    LAST_DUPE_TS= auto()

class MsgStructures:

    SENSITIVE_FIELDS = {
        Contract.PASSWORD,
        "hashed_password",
        "salt",
        "internal_id"
    }

    _REQUESTS = {
        MsgType.LOGIN: [{Contract.IDENTITY, Contract.PASSWORD}],
        MsgType.SIGNUP: [{Contract.IDENTITY, Contract.PASSWORD, Contract.ROLE, Contract.EMAIL}, {Contract.IDENTITY, Contract.PASSWORD, Contract.ROLE, Contract.EMAIL}],
        MsgType.VERIFY_OTP: [{Contract.OTP_CODE}],
        MsgType.RECONNECT: [{Contract.TOKEN}],
        MsgType.JOIN_ROOM: [
            {Contract.ROOM_ID},
            {Contract.CATEGORY}
        ],
        MsgType.CREATE_CHAT_ROOM: [{Contract.DISPLAY_NAME, Contract.CATEGORY, Contract.SUMMARY, Contract.IS_OPEN, Contract.TYPE}],
        MsgType.GET_OLDER_TOPICS: [{Contract.TOPIC_ID}],
        MsgType.SEND_MSG: [{Contract.ROOM_ID, Contract.CONTENT, Contract.NONCE}],
        MsgType.GET_OLDER_MESSAGES: [{Contract.ROOM_ID, Contract.ANCHOR_ID}],
    }

    @staticmethod
    def get_allowed_structures(msg_type: MsgType):
        return MsgStructures._REQUESTS.get(msg_type, [set()])

    @staticmethod
    def clean_sensitive_fields(raw_data):
        return {
            k: v for k, v in raw_data.items()
            if k not in MsgStructures.SENSITIVE_FIELDS
        }

class ResponseFactory:
    @staticmethod
    def create(msg_type: MsgType, code: MsgCodes, raw_data: dict = {}):
        raw_data = raw_data or {}

        status = Contract.SUCCESS if 200 <= code < 300 else Contract.FAILED

        payload = MsgStructures.clean_sensitive_fields(raw_data)

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

class Validator:
    _PATTERNS = {
        Contract.EMAIL: r"(?i)^(?!.*\.{2})[a-z0-9!#$%&'*+/=?^_`{|}~.-]{2,64}@gmail\.com$",
        Contract.PASSWORD: r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,20}$",
        Contract.USERNAME: r"^(?=.*[a-zA-Z])[a-zA-Z0-9]{3,15}$",
        Contract.ID: r"^\d{9}$",
        Contract.OTP_CODE: r"^\d{6}$"
    }

    @staticmethod
    def validate_structure(msg_type, payload):
        if not isinstance(payload, dict): return False

        payload_keys = set(payload.keys())
        optional_structures = MsgStructures.get_allowed_structures(msg_type)
        print(any(payload_keys == required_set for required_set in optional_structures), 'a')
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