from enum import StrEnum
from auth_config import UserRole, ROLE_STYLES

class ChatUIKey(StrEnum):
    DASHBOARD_TITLE = "dashboard_title"
    CAN_CREATE_ROOM = "can_create_room"
    ROOM_CREATION_TYPE = "room_creation_type"
    HAS_INVITE_CODE_INPUT = "has_invite_code_input"
    HAS_AUTO_MATCH = "has_auto_match"
    ROOMS_FETCH_STRATEGY = "rooms_fetch_strategy",
    CAN_JOIN_ROOM = 'can_join_room'


class FetchStrategy(StrEnum):
    PUBLIC_AND_JOINED = "public_and_joined"
    JOINED_ONLY = "joined_only"
    OWNED_ONLY = "owned_only"


CHAT_ROLES_CONFIG = {
    UserRole.STANDARD: {
        ChatUIKey.DASHBOARD_TITLE: "לובי שיחות ציבורי",
        ChatUIKey.CAN_CREATE_ROOM: True,
        ChatUIKey.CAN_JOIN_ROOM: True,
        ChatUIKey.ROOM_CREATION_TYPE: "standard",
        ChatUIKey.HAS_INVITE_CODE_INPUT: True,
        ChatUIKey.HAS_AUTO_MATCH: True,
        "style": ROLE_STYLES[UserRole.STANDARD]
    },

    UserRole.STUDENT: {
        ChatUIKey.DASHBOARD_TITLE: "מרחב למידה - תלמיד",
        ChatUIKey.CAN_CREATE_ROOM: False,
        ChatUIKey.CAN_JOIN_ROOM: True,
        ChatUIKey.ROOM_CREATION_TYPE: None,
        ChatUIKey.HAS_INVITE_CODE_INPUT: True,
        ChatUIKey.HAS_AUTO_MATCH: False,
        "style": ROLE_STYLES[UserRole.STUDENT]
    },

    UserRole.TEACHER: {
        ChatUIKey.DASHBOARD_TITLE: "ניהול כיתות ומרחבי למידה",
        ChatUIKey.CAN_CREATE_ROOM: True,
        ChatUIKey.CAN_JOIN_ROOM: False,
        ChatUIKey.ROOM_CREATION_TYPE: "education",
        ChatUIKey.HAS_INVITE_CODE_INPUT: False,
        ChatUIKey.HAS_AUTO_MATCH: False,
        "style": ROLE_STYLES[UserRole.TEACHER]
    }
}


TOPIC_ACTIONS_REGISTRY = {
    UserRole.TEACHER: lambda topic: [
{
            'text': "צור קבוצה לדיון ➕",
            'fg_color': "#55446E", 'hover_color': "#6A558A",
            'action_key': 'CREATE'
        },

    ],
    UserRole.STANDARD: lambda topic: [
        {
            'text': "הצטרפות מהירה 👋",
            'fg_color': "#3D5A80", 'hover_color': "#293E59",
            'action_key': 'JOIN'
        },
        {
            'text': "פתח חדר חדש ➕",
            'fg_color': "#2E4057", 'hover_color': "#1F2D3E",
            'action_key': 'CREATE',
        }
    ],
    UserRole.STUDENT: lambda topic: [
        {
            'text': "הצטרף לדיון הפעיל 👋",
            'fg_color': "#3D5A80", 'hover_color': "#293E59",
            'action_key': 'JOIN'
        }
    ]
}