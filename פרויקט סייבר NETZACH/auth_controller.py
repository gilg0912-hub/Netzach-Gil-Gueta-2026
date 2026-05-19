import customtkinter as ctk
from app_constants import StateKey, Contract, AppScreens, MsgType
from auth_config import (
    ScreensName, CommandKey, UIKey,
    AUTH_SCREENS, UI_POLICIES,
    STYLE_NEUTRAL
)
from ui_components import Screen
from gui_state_mgmt import ResponseTranslator


class AuthController(ctk.CTkFrame):
    def __init__(self, parent, gui_state, services):
        super().__init__(parent, fg_color="#051224", width=350, height=550,
                         corner_radius=15, border_width=1, border_color="white")

        self.gui_state = gui_state
        self.auth_service = services.get(AppScreens.AUTH)
        self.timer_id= None
        self.text_label = ctk.CTkLabel(self, text='', text_color='red', font=('hebbo', 14, 'bold'), fg_color='transparent', height=10)

        self.text_label.place(relx=0.5, rely=0.95, anchor='center')


        self.pack_propagate(False)

        self.screens = {}
        self.current_screen = None
        self.current_code= None
        self.state= True
        self.is_locked=False
        self.history = []
        self.show_alert=False
        self.back_btn = ctk.CTkButton(self, cursor="hand2", text="←", fg_color="#051224", hover_color="#0A2140",
                                      text_color="white", width=40, command=lambda: self.back_action())

        self.commands = {
            CommandKey.HANDLE_AUTH: self.handle_auth_request,
            CommandKey.FORGOT_PW: lambda: self.show_screen(ScreensName.FORGOT_PW),
            CommandKey.RESEND: self._resend_otp,
            CommandKey.SHOW_OTP: lambda: self.show_screen(ScreensName.OTP, False),
            CommandKey.LOCK_UI: self._handle_cooldown,
            CommandKey.BACK_SCREEN: self.back_action,
        }
        self.gui_state.register(StateKey.CODE, self.on_CODE_changed)
        self.gui_state.register(StateKey.CONNECTED, self.connection_lost)

        self._init_all_screens()


        self.show_screen(ScreensName.WELCOME, False)


    def _handle_cooldown(self):
        self.current_code= self.gui_state.get_state(StateKey.CODE)

        policy= UI_POLICIES.get(self.current_code, {})
        payload= self.gui_state.get_state(StateKey.LAST_PAYLOAD)
        seconds = payload.get(Contract.EXPIRY, 60)
        self.show_alert= policy.get('keep_alerts', False)

        self.change_screen_state(True)
        self._update_countdown(seconds)

    def change_screen_state(self, is_locked):
        self.is_locked = is_locked
        self.state = not is_locked

        screen = self.screens.get(self.current_screen)
        if not screen:
            return

        screen.lock = is_locked

        screen.check_valid_fields()

    def _update_countdown(self, remaining):
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None

        if remaining > 0:
            self.text_label.configure(text= ResponseTranslator.get_message(self.current_code, expiry=remaining))
            self.timer_id= self.after(1000, self._update_countdown, remaining - 1)
        else:
            self.change_screen_state(False)
            self.gui_state.set_state(StateKey.CODE, None)

    def on_CODE_changed(self, code):
        if not code:
            self.text_label.configure(text="")
            return

        if code < 200:
            return

        current_msg_type = self.gui_state.get_state(StateKey.LAST_MSG_TYPE)

        policy = UI_POLICIES.get((code, current_msg_type))

        if policy is None:
            policy = UI_POLICIES.get((code, None), {})

        command = policy.get(UIKey.COMMAND)
        if command != CommandKey.LOCK_UI:
            self.change_screen_state(is_locked=False)

        action_func = self.commands.get(command)
        if action_func:
            action_func()

        self.show_alert = policy.get('keep_alerts', False)
        self.text_label.configure(
            text=ResponseTranslator.get_message(code, **self.gui_state.get_state(StateKey.LAST_PAYLOAD) or {}),
            text_color=policy.get(UIKey.TEXT_COLOR, 'red')
        )

    def _init_all_screens(self):
        for name, conf in AUTH_SCREENS.items():
            fit_buttons = []
            for btn in conf.get('extra_btns'):
                b = btn.copy()
                if 'target' in b:
                    target_screen = b.pop('target')
                    b['command'] = lambda t=target_screen: self.show_screen(t)

                elif 'command' in b:
                    method_name = b.pop('command')
                    b['command'] = self.commands.get(method_name)

                fit_buttons.append(b)
            self.screens[name] = Screen(self,
                                        title=conf.get('title'),
                                        field_types=conf['field_types'],
                                        confirm_text=conf.get('confirm_text'),
                                        confirm_command= self.commands.get(conf.get('confirm_command')),
                                        extra_btns=fit_buttons,
                                        style=conf.get('style', STYLE_NEUTRAL))

    def show_screen(self, screen, add_to_history=True):
        if screen == self.current_screen:
            return

        if self.current_screen:
            self.screens[self.current_screen].pack_forget()

            if add_to_history and not self.history:
                self.back_btn.place(x=5, y=5)

            if add_to_history:
                self.history.append(self.current_screen)

            elif not self.history:
                self.back_btn.place_forget()


        conf= AUTH_SCREENS[screen]
        role= conf.get(Contract.ROLE)
        if role:
            self.gui_state.set_state(StateKey.ROLE, role)

        target_screen = self.screens[screen]
        target_screen.pack(pady=(5,20), padx=5, fill='both', expand=True)

        current_code = self.gui_state.get_state(StateKey.CODE)
        policy = UI_POLICIES.get(current_code, {})

        self.current_screen = screen
        self.change_screen_state(self.is_locked)
        self.text_label.lift()
        if self.history:
            self.back_btn.lift()

    def handle_auth_request(self):
        if not self.state or not self.current_screen:
            return

        screen=self.screens[self.current_screen]
        data_from_screen = screen.get_data()

        self.gui_state.set_state(StateKey.CODE, '')
        self.change_screen_state(is_locked=True)
        auth_action = AUTH_SCREENS[self.current_screen].get(Contract.TYPE)

        if auth_action == MsgType.SIGNUP:
            current_role = self.gui_state.get_state(StateKey.ROLE)
            if current_role:
                data_from_screen[Contract.ROLE] = current_role

        if self.auth_service:
            self.auth_service.handle_auth_request(auth_action, data_from_screen)

    def _resend_otp(self):
        if not self.state:
            return
        self.gui_state.set_state(StateKey.CODE, '')
        self.change_screen_state(is_locked=True)

        if self.auth_service:
            self.auth_service.handle_auth_request(MsgType.RESEND_OTP, {})
        else:
            self.change_screen_state(is_locked=False)

    def connection_lost(self, is_connected):
        if is_connected:
            return
        if self.current_screen == ScreensName.OTP:
            self.back_action()

    def back_action(self):
        if not self.history:
            return
        self.show_screen(self.history.pop(), False)

        if not self.show_alert:
            self.gui_state.set_state(StateKey.CODE, '')