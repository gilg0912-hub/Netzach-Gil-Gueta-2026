from enum import StrEnum
from app_constants import MsgType, Contract, Validator,MsgCodes


class UserRole(StrEnum):
    STANDARD = "standard"
    STUDENT = "student"
    TEACHER = "teacher"

class FieldType(StrEnum):
    USERNAME = 'username'
    PASSWORD = 'password'
    ID = 'id'
    EMAIL = 'email'
    OTP_CODE='otp_code'

class ScreensName(StrEnum):
    WELCOME = "welcome"
    GUEST_CHOICE = 'guest_choice'
    STANDARD_LOGIN = 'standard_login'
    STANDARD_SIGNUP = 'standard_signup'
    TEACHER_LOGIN = 'teacher_login'
    STUDENT_LOGIN = 'student_login'
    FORGOT_PW = 'forgot_pw'
    OTP = 'otp'

class UIKey(StrEnum):
    COLOR='color'
    TEXT='text'
    TEXT_COLOR='text_color'
    COMMAND='command'
    WAIT_TIME='wait_time'
    LOCK_LEVEL='lock_level'


BASE_STYLE = {
    'width': 220, 'height': 50, 'fg_color': "transparent",
    'corner_radius': 15, 'border_width': 2, 'font': ("David", 22, "bold"), 'cursor': "hand2"
}


STYLE_CTK= {'width':150,
            'height':35,
            'fg_color': "transparent",
            'corner_radius': 15,
            'border_width': 2,
            'font': ("David", 20, "bold")}

STYLE_LINK = {
    'fg_color': "transparent", UIKey.TEXT_COLOR: 'white', 'hover_color': "#051224",
    'width': 100, 'height': 25, 'font': ("David", 18, 'underline')
}

STYLE_NEUTRAL = {
    **BASE_STYLE, 'hover_color': "#454545", UIKey.TEXT_COLOR: "white", 'border_color': "gray50"
}

ROLE_STYLES = {
    UserRole.STANDARD: {**BASE_STYLE, 'hover_color': "#3D5A80", UIKey.TEXT_COLOR: "#98C1D9", 'border_color': "#98C1D9"},
    UserRole.STUDENT:  {**BASE_STYLE, 'hover_color': "#1C7F72", UIKey.TEXT_COLOR: "#66CCCC", 'border_color': "#66CCCC"},
    UserRole.TEACHER:  {**BASE_STYLE, 'hover_color': "#55446E", UIKey.TEXT_COLOR: "#9966FF", 'border_color': "#9966FF"}
}

# ==========================================
# 3. הגדרות שדות קלט (Field Definitions)
# ==========================================
FIELD_DEFS = {
    FieldType.USERNAME: {
        'label_conf': {'text': 'שם משתמש', 'font': ("Arial", 13, "bold")},
        'entry_conf': {'show': '', 'corner_radius': 0, 'border_width': 0},
        'emoji_conf': {'text': '👤'},
        'max_len': 20,
        'pattern': Validator.USERNAME_PATTERN,
        'show_eye': False,
    },
    FieldType.ID: {
        'label_conf': {'text': 'תעודת זהות', 'font': ("Arial", 13, "bold")},
        'entry_conf': {'show': '', 'corner_radius': 0, 'border_width': 0},
        'emoji_conf': {'text': '🛡'},
        'max_len': 9,
        'pattern': Validator.ID_PATTERN,
        'show_eye': False,
    },
    FieldType.PASSWORD: {
        'label_conf': {'text': 'סיסמה', 'font': ("Arial", 13, "bold")},
        'entry_conf': {'show': '•', 'corner_radius': 0, 'border_width': 0, 'placeholder_text': "Aa123..."},
        'emoji_conf': {'text': '🔑'},
        'max_len': 30,
        'show_eye': True,
        'pattern': Validator.PASS_PATTERN,
    },
    FieldType.EMAIL: {
        'label_conf': {'text': 'אימייל', 'font': ("Arial", 13, "bold")},
        'entry_conf': {'show': '', 'corner_radius': 0, 'border_width': 0, 'placeholder_text': "example@gmail.com"},
        'emoji_conf': {'text': '📧'},
        'max_len': 64,
        'show_eye': False,
        'pattern': Validator.EMAIL_PATTERN,
    },
    FieldType.OTP_CODE: {
        'label_conf': {'text': ':הזן קוד', 'font': ("Arial", 13, "bold")},
        'entry_conf': {'show': '', 'corner_radius': 0, 'border_width': 0, 'placeholder_text': ""},
        'emoji_conf': {'text': '⏳'},
        'max_len': 6,
        'show_eye': False,
        'pattern':Validator.OTP_CODE,
    }
}


class CommandKey(StrEnum):
    NAVIGATE = "navigate"
    SHOW_OTP = "show_otp"
    BACK = "back"

    # שליטת GUI
    LOCK_UI = "lock_ui"
    UNLOCK_UI = "unlock_ui"
    START_COOLDOWN = "start_cooldown"

    RESEND = "resend"
    HANDLE_AUTH = "handle_auth"
    FORGOT_PW= 'forgot_password'
    NONE = "none"
    BACK_SCREEN= 'back_screen'




class UIState(StrEnum):
    NORMAL = "normal"
    DISABLED = "disabled"
    READONLY = "readonly"

UI_POLICIES = {
    MsgCodes.TOO_MANY_ATTEMPTS: {
        UIKey.TEXT_COLOR: "orange",
        "command": CommandKey.LOCK_UI,
        'keep_alerts': True,
    },
    MsgCodes.INVALID_FIELDS: {
        UIKey.TEXT_COLOR: "red",
    },
    MsgCodes.OTP_SENT: {
        UIKey.TEXT_COLOR: "green",
        "command": CommandKey.SHOW_OTP
    },
    MsgCodes.FLOOD_WARNING: {
        UIKey.TEXT_COLOR: 'orange',
        'command': CommandKey.LOCK_UI,
        UIKey.WAIT_TIME: 60,
        'keep_alerts': True,

    },
    MsgCodes.UNAUTHORIZED: {
        UIKey.TEXT_COLOR: "red",
        'command':CommandKey.BACK_SCREEN,

    },
    MsgCodes.BLOCKED_EMAIL: {
        UIKey.TEXT_COLOR: "orange",
        'command': CommandKey.BACK_SCREEN,
    },
    MsgCodes.INVALID_OTP: {
        UIKey.TEXT_COLOR: "yellow",
    },
    MsgCodes.OTP_RESENT: {
        UIKey.TEXT_COLOR: "green",
    },
    MsgCodes.SESSION_EXPIRED:
        {
            'command': CommandKey.BACK_SCREEN,
        },
}



AUTH_SCREENS = {
    ScreensName.WELCOME: {
        'title': "!ברוכים הבאים",
        'field_types': [],
        'extra_btns': [
            {'text': "🌍 כניסת משתמשים", 'target': ScreensName.GUEST_CHOICE, **ROLE_STYLES[UserRole.STANDARD]},
            {'text': "🎓 פורטל תלמידים", 'target': ScreensName.STUDENT_LOGIN, **ROLE_STYLES[UserRole.STUDENT]},
            {'text': "🏫 פורטל סגל הוראה", 'target': ScreensName.TEACHER_LOGIN, **ROLE_STYLES[UserRole.TEACHER]},
            {'text': "!אין חשבון? הירשמו", **STYLE_LINK, 'target': ScreensName.STANDARD_SIGNUP}
        ]
    },

    ScreensName.GUEST_CHOICE: {
        'title': "כניסת משתמשים",
        'field_types': [],
        'style': ROLE_STYLES[UserRole.STANDARD],
        'extra_btns': [
            {'text': 'התחברות', 'target': ScreensName.STANDARD_LOGIN, **ROLE_STYLES[UserRole.STANDARD]},
            {'text': 'הרשמה', 'target': ScreensName.STANDARD_SIGNUP, **ROLE_STYLES[UserRole.STANDARD]}
        ]
    },

    ScreensName.STUDENT_LOGIN: {
        'title': "פורטל תלמידים",
        'field_types': [FieldType.ID, FieldType.PASSWORD],
        'confirm_text': 'התחבר/י',
        'confirm_command': CommandKey.HANDLE_AUTH,
        Contract.TYPE: MsgType.LOGIN,
        'style': ROLE_STYLES[UserRole.STUDENT],
        Contract.ROLE: UserRole.STUDENT,
        'extra_btns': [{'text': '?שכחת סיסמה', **STYLE_LINK, 'target': ScreensName.FORGOT_PW}]
    },

    ScreensName.TEACHER_LOGIN: {
        'title': "פורטל סגל הוראה",
        'field_types': [FieldType.ID, FieldType.PASSWORD],
        'confirm_text': 'התחבר/י',
        'confirm_command': CommandKey.HANDLE_AUTH,
        Contract.TYPE: MsgType.LOGIN,
        'style': ROLE_STYLES[UserRole.TEACHER],
        Contract.ROLE: UserRole.TEACHER,
        'extra_btns': [{'text': '?שכחת סיסמה', **STYLE_LINK, 'target': ScreensName.FORGOT_PW}]
    },

    ScreensName.STANDARD_LOGIN: {
        'title': "התחברות",
        'field_types': [FieldType.USERNAME, FieldType.PASSWORD],
        'confirm_text': 'התחבר/י',
        'confirm_command': CommandKey.HANDLE_AUTH,
        Contract.TYPE: MsgType.LOGIN,
        'style': ROLE_STYLES[UserRole.STANDARD],
        Contract.ROLE: UserRole.STANDARD,
        'extra_btns': [
            {'text': '?שכחת סיסמה', **STYLE_LINK, 'target': ScreensName.FORGOT_PW},
            {'text': "!אין חשבון? הירשמו", **STYLE_LINK, 'target': ScreensName.STANDARD_SIGNUP}
        ]
    },

    ScreensName.STANDARD_SIGNUP: {
        'title': "הרשמה",
        'field_types': [FieldType.USERNAME, FieldType.PASSWORD, FieldType.EMAIL],
        'confirm_text': '!הירשמו',
        'confirm_command': CommandKey.HANDLE_AUTH,
        Contract.TYPE: MsgType.SIGNUP,
        'style': ROLE_STYLES[UserRole.STANDARD],
        Contract.ROLE: UserRole.STANDARD,
        'extra_btns': []
    },

    ScreensName.FORGOT_PW: {
        'title': "שחזור סיסמה",
        'field_types': [FieldType.EMAIL],
        'confirm_text': 'Get Code',
        'confirm_command': CommandKey.HANDLE_AUTH,
        'style': ROLE_STYLES[UserRole.STANDARD],
        Contract.TYPE: MsgType.FORGOT_PASSWORD,
        'extra_btns': []
    },
    ScreensName.OTP:
        {
        'title': " ",
        'field_types': [FieldType.OTP_CODE],
        'confirm_text': 'Send Code',
        'confirm_command': CommandKey.HANDLE_AUTH,
        'style': ROLE_STYLES[UserRole.STANDARD],
        Contract.TYPE: MsgType.VERIFY_OTP,
        'extra_btns': [{'text': 'שלח שוב', **STYLE_LINK, 'command': CommandKey.HANDLE_AUTH}],
        }
}

