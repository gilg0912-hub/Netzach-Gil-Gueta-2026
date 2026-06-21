import customtkinter as ctk
from app_constants import StateKey, Contract, MsgType

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
            font=("Heebo", 20, "bold"),
            text_color=("#475569", "#8B949E"),
            anchor="e"
        )
        self.list_header.pack(fill="x", padx=10, pady=(15, 5))

        self.rooms_scroll = RoomsListFrame(
            self,
            gui_state=gui_state,
            chat_service=chat_service,
            fg_color="transparent",
            border_width=2,
            border_color=("#E2E8F0", "#30363D"),
            scrollbar_button_color=("#f59e0b", "#D4AF37"),
            scrollbar_button_hover_color=("#d97706", "#B0903D"),
            corner_radius=15,
        )
        self.rooms_scroll.pack(fill="both", expand=True, pady=5, padx=10)

    def _on_room_click(self, room_id):
        self.gui_state.set_state(StateKey.CURRENT_ROOM_ID, room_id)



class Menu(ctk.CTkFrame):
    def __init__(self, parent, gui_state, **kwargs):
        super().__init__(parent, corner_radius=0, border_width=0, **kwargs)

        self.gui_state = gui_state
        self.buttons = []
        self.indicators = []
        self.pressed = None

        self.rows = 0

        self.grid_columnconfigure(0, minsize=4)
        self.grid_columnconfigure(1, weight=1)

    def add_btn(self, text, command_func=None):
        indicator = ctk.CTkFrame(self, width=4, height=20, fg_color="transparent", corner_radius=0)
        btn = ctk.CTkButton(
            self,
            text=text,
            text_color=("#0F172A", "#C9D1D9"),
            height=20,
            fg_color="transparent",
            hover_color=("#F1F5F9", "#475569"),
            font=('Heebo', 18),
            command=lambda i=self.rows, f=command_func: self.handle_click(i, f)
        )

        indicator.grid(row=self.rows, column=0, pady=5, sticky="ns")
        btn.grid(row=self.rows, column=1, pady=5, padx=30, sticky="ew")

        self.indicators.append(indicator)
        self.buttons.append(btn)

        self.rows += 1

    def handle_click(self, row, command_func):
        if self.pressed == row:
            return

        if self.pressed is not None:
            self.indicators[self.pressed].configure(fg_color="transparent")
            # חזרה לצבע טקסט רגיל (כהה ב-Light, בהיר ב-Dark)
            self.buttons[self.pressed].configure(text_color=("#0F172A", "#C9D1D9"))

        # שימוש בצבע הזהב העמוק (שקריא בשני המצבים) לסימון בחירה
        self.indicators[row].configure(fg_color=("#f59e0b", "#D4AF37"))
        self.buttons[row].configure(text_color=("#f59e0b", "#D4AF37"))

        if command_func:
            command_func()
        self.pressed = row


class RoomsListFrame(ctk.CTkScrollableFrame):
    def __init__(self, parent, gui_state, chat_service, **kwargs):
        super().__init__(parent, **kwargs)
        self._scrollbar.grid_configure(padx=10)
        self.gui_state = gui_state
        self.chat_service = chat_service

        self.room_buttons = {}

        self._load_initial_rooms()
        self.gui_state.register(StateKey.ROOMS_UI_SIGNAL, self._on_rooms_updated)

    def _load_initial_rooms(self):
        initial_rooms = self.gui_state.get_state(StateKey.SYNC_ROOMS) or []
        for room_obj in initial_rooms:
            self._add_or_update_room_button(room_obj, on_top=False)

    def _on_rooms_updated(self, signal_data):
        if not signal_data:
            return

        items = signal_data.get("rooms", [])
        on_top = signal_data.get("on_top", False)

        for room_obj in items:
            self._add_or_update_room_button(room_obj, on_top=on_top)

    def _add_or_update_room_button(self, room_obj, on_top=False):
        r_id = str(room_obj.room_id)
        topic = room_obj.display_name if room_obj.display_name else "חדר ללא נושא"
        is_open = room_obj.is_open

        symbol = "🟢" if is_open else "🔒"
        display_text = f"{topic}  {symbol}"

        if r_id in self.room_buttons:
            btn = self.room_buttons[r_id]
            btn.configure(text=display_text)

            if on_top:
                btn.pack_forget()
                self._pack_button_at_top(btn)
        else:
            btn = ctk.CTkButton(
                self,
                text=display_text,
                anchor="e",
                fg_color="transparent",
                hover_color=("#F1F5F9", "#132F4C"),
                height=42,
                corner_radius=8,
                font=("Heebo", 13),
                text_color=("#334155", "#CED4DA"),
                command=lambda current_room=room_obj: self._on_room_click(current_room)
            )

            self.room_buttons[r_id] = btn

            if on_top:
                self._pack_button_at_top(btn)
            else:
                btn.pack(fill="x", pady=2)

    def _pack_button_at_top(self, btn):
        active_children = [
            child for child in self.winfo_children()
            if isinstance(child, ctk.CTkButton)
               and child != btn
               and child.winfo_manager() == 'pack'
        ]

        if active_children:
            btn.pack(fill="x", pady=2, before=active_children[0])
        else:
            btn.pack(fill="x", pady=2)

    def _on_room_click(self, room_obj):
        self.chat_service.switch_to_room(room_obj)
