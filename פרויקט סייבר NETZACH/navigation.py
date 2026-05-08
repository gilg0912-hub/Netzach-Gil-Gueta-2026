import customtkinter as ctk
from app_constants import StateKey, Contract, MsgType
from gui_state_mgmt import ResponseTranslator
from modals import CreateConnectionWindow

class NavSidebar(ctk.CTkFrame):
    def __init__(self, parent, chat_service, gui_state, callback_show_screen=None):
        super().__init__(parent, fg_color='transparent', corner_radius=0, width=280)
        self.pack_propagate(False)

        self.callback_show_screen = callback_show_screen
        self.gui_state = gui_state
        self.chat_service = chat_service

        self.list_header = ctk.CTkLabel(
            self,
            text="ערוצים פעילים",
            font=("Heebo", 15, "bold"),
            text_color="#4A6076",
            anchor="e"
        )
        self.list_header.pack(fill="x", padx=25, pady=(15, 5))

        self.rooms_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            border_width=1,
            border_color="#1E4976",
            scrollbar_button_color="#1E4976",
            scrollbar_button_hover_color="#B0903D",
            corner_radius=20
        )

        self.rooms_scroll._scrollbar.grid_configure(padx=(0, 10))
        self.rooms_scroll.pack(fill="both", expand=True, pady =5 , padx=10)

        self.gui_state.register(StateKey.CODE, self._update_status_display)
        self._add_mock_rooms()

    def _switch_screen(self, screen_name):
        if screen_name == 'chat':
            self.chat_btn.configure(state='disabled')
            self.action_area.configure(state='normal')
        else:
            self.chat_btn.configure(state='normal')
            self.action_area.configure(state='disabled')
        self.callback_show_screen(screen_name)
    def _update_status_display(self, code):
        if 200<=code<300:
            return
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        color_theme= ResponseTranslator.get_color(code)
        self.status_dot.configure(fg_color=color_theme)
        self.status_label.configure(text=ResponseTranslator.get_message(code), text_color=color_theme)
        self._timer_id= self.after(5000, self._reset_status)

    def _reset_status(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
        self._timer_id = None

        if self.gui_state.get_state(StateKey.CONNECTED):
            self.status_label.configure(text="מערכת פעילה", text_color="#B0903D")
            self.status_dot.configure(fg_color="#2ECC71")

    def _on_create_click(self):
        pass

    def _open_connection_dialog(self):
       pass

    def _on_dialog_submit(self, conn_type, value):
        payload = {Contract.ROOM_ID: value} if conn_type == Contract.ROOM_ID else {Contract.TOPIC: value}
        self.chat_service.dispatcher.send_msg(MsgType.JOIN_ROOM, payload)

    def _add_mock_rooms(self):
        sample_rooms = [
            ("Cyber Security", "12", True),
            ("General Chat", "45", False),
            ("Physics 101", "3", False),
            ("Hardware", "1", True),
            ("Global Dev", "8", False)
        ]
        for name, count, locked in sample_rooms:
            symbol = "🔒" if locked else "#"
            btn = ctk.CTkButton(
                self.rooms_scroll,
                text=f"{name}  {symbol}",
                anchor="e",
                fg_color="transparent",
                hover_color="#132F4C",
                height=42,
                corner_radius=8,
                font=("Heebo", 13),
                text_color="#CED4DA"
            )
            btn.pack(fill="x", pady=1)


class Menu(ctk.CTkFrame):
    def __init__(self, parent, gui_state):
        super().__init__(parent, fg_color='transparent', corner_radius=0, border_width=0)

        self.gui_state = gui_state
        self.buttons = []
        self.indicators = []
        self.pressed = None

        self.rows = 0

        self.grid_columnconfigure(0, minsize=4)
        self.grid_columnconfigure(1, weight=1)

    def add_btn(self, text, command_func = None):

        indicator = ctk.CTkFrame(self, width=4, height=24, fg_color="transparent", corner_radius=0)
        btn = ctk.CTkButton(
            self,
            text=text,
            text_color='white',
            height=24,
            fg_color="transparent",
            hover_color="#0D1B2A",
            font=('Hebbo', 18),
            command=lambda i=self.rows, f=command_func: self.handle_click(i, f)
        )

        indicator.grid(row=self.rows, column=0, pady=10, sticky="ns")
        btn.grid(row=self.rows, column=1, pady=10, padx=(10, 0), sticky="ew")

        self.indicators.append(indicator)
        self.buttons.append(btn)

        self.rows += 1


    def handle_click(self, row, command_func):
        if self.pressed == row:
            return

        if self.pressed is not None:
            self.indicators[self.pressed].configure(fg_color="transparent")
            self.buttons[self.pressed].configure(text_color="white")

        self.indicators[row].configure(fg_color="#B0903D")
        self.buttons[row].configure(text_color="#B0903D")

        if command_func:
            command_func()
        self.pressed = row