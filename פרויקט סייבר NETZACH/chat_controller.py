import customtkinter as ctk
from app_constants import StateKey, Contract
from CHAT_config import *
from navigation import NavSidebar, Menu
from chat_widgets import ChatScreen, HotScreen, CreateScreen
from gui_state_mgmt import ResponseTranslator
from modals import UserDetailsOverlay


class ChatController(ctk.CTkFrame):
    def __init__(self, parent, gui_state, services):

        self.theme = {
            # Light: אפור-פסטל קריר ומרגיע (לא מסנוור). Dark: שחור-כחול עמוק.
            "main_bg": ("#F1F5F9", "#0D1117"),

            # Light: סיידבר וכותרת עליונה בלבן נקי כדי ליצור הפרדה.
            "sidebar_slate": ("#FFFFFF", "#161B22"),
            "header_bg": ("#F4E9D8", "#544E2C"),

            # Light: כרטיסיות בלבן טהור.
            "card_bg": ("#FFFFFF", "#21262D"),

            # Light: זהב כהה וברור שקריא על רקע בהיר. Dark: זהב מבריק.
            "gold": ("#8C6800", "#D4AF37"),

            # Light: טקסט באפור-ציפחה כמעט שחור לקריאות מושלמת.
            "text": ("#0F172A", "#C9D1D9"),

            # Light: מסגרות באפור עדין.
            "border": ("#E2E8F0", "#30363D")
        }

        super().__init__(parent, fg_color= self.theme['main_bg'], corner_radius=0)
        self.gui_state = gui_state
        self.chat_service= services['chat']
        self._is_in_penalty = False

        self.grid_columnconfigure(1, weight=7)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.header= ctk.CTkFrame(self, fg_color=self.theme['header_bg'], corner_radius=20, height=65)
        self.header.pack_propagate(False)
        self.header.grid(row=0, column=1, sticky='ew', padx=(0,10), pady=10)


        self.left_mask = ctk.CTkFrame(self.header, fg_color='transparent', corner_radius=0, width=30)
        self.left_mask.place(relx=0, rely=0, relheight=0.99)

        self.status_frame = ctk.CTkFrame(self.header, fg_color='transparent', corner_radius=0)
        self.status_frame.pack(side='right', padx=30)

        self.status_dot = ctk.CTkFrame(self.status_frame, corner_radius=30, fg_color= '#2ECC71', width=10, height=10)
        self.status_dot.pack(side='right', padx=10)
        self.status_label= ctk.CTkLabel(self.status_frame, text='מערכת פעילה',  anchor='e', font=('Heebo', 12, 'bold'), width=150)
        self.status_label.pack(fill='both', padx=10)

        self._timer_id = None

        self.title_label = ctk.CTkLabel(
            self.header,
            text='נצ"ח - להנצחת המורשת הישראלית',
            text_color='#B0903D',
            font=('Heebo', 35, 'bold'),
            anchor='e'
        )
        self.title_label.pack(side='right', padx=10)



        self.navigation_frame= ctk.CTkFrame(self, fg_color= self.theme['sidebar_slate'], corner_radius=20)
        self.navigation_frame.grid(column=0, row=1, sticky="nsew", padx=(20,0), pady=(0,50))

        self.switch_section = ctk.CTkFrame(self, fg_color= self.theme['sidebar_slate'], corner_radius=0, height=8)
        self.switch_section.grid(column=0, row=0, padx=(20,0), sticky="nsew", pady=0)

        self.appearance_mode_switch = ctk.CTkSwitch(
            self.switch_section,
            text="🌙",
            font= ('Heebo', 15, 'bold'),
            command=self.toggle_appearance_mode,
            fg_color=self.theme['gold'][1],
            progress_color=self.theme['gold'][1]
        )
        self.appearance_mode_switch.select()
        self.appearance_mode_switch.pack(pady=20, padx=5)

        self.sidebar= Menu(self.navigation_frame, self.gui_state, fg_color='transparent')

        self.sidebar.pack(side='top', fill='x')
        self.nav_sidebar= NavSidebar(self.navigation_frame, self.chat_service, self.gui_state)
        self.nav_sidebar.pack(fill='both', expand=True, padx=10, pady=10)

        self.screens = {
            'groups': ChatScreen(self, self.gui_state, self.chat_service),
            'join': HotScreen(self, self.gui_state, self.chat_service, on_create_callback=lambda: self.sidebar.handle_click(2, lambda: self.show_screen('create'))),
            'create': CreateScreen(self, self.gui_state, self.chat_service),
            'home': UserDetailsOverlay(self, self.gui_state),
        }
        self.current_screen = None

        self.gui_state.register(StateKey.CODE, self._update_status)
        self.gui_state.register(StateKey.ROOMS_UI_SIGNAL, self.sync_user_rooms)
        self.gui_state.register(StateKey.TOPICS_UI_SIGNAL, self.sync_user_topics)
        self.gui_state.register(StateKey.ROLE, self.setup_role_ui)

    def setup_role_ui(self, role):
        if not role:
            return

        config = CHAT_ROLES_CONFIG.get(role)
        if not config:
            return

        self.title_label.configure(text=config[ChatUIKey.DASHBOARD_TITLE])

        self.sidebar.add_btn("בית 🏠", lambda: self.show_screen('home'))
        self.sidebar.add_btn('קבוצות 👨‍👩‍👧', lambda: self.show_screen('groups'))

        if config[ChatUIKey.CAN_CREATE_ROOM]:
            self.sidebar.add_btn('צור קבוצה ➕', lambda: self.show_screen('create'))

        sidebar_text = "הצטרפות 👋" if role == UserRole.STUDENT else "מאגר נושאים 📚"
        self.sidebar.add_btn(sidebar_text, lambda: self.show_screen('join'))

    def handle_topic_action(self, action_key, topic):
        if action_key == 'JOIN':
            self.chat_service.join_room_by_category(topic.get('category'))

        elif action_key == 'CREATE':
            selected_title = topic.get('title')
            create_screen = self.screens['create']

            if selected_title:
                create_screen.topic_dropdown.set(selected_title)
                create_screen._on_topic_selection_changed(selected_title)

            self.sidebar.handle_click(2, self.show_screen('create'))

            print(f"[GUI Action] Template loaded. Moved to CreateScreen workspace.")

    def sync_user_rooms(self, payload):
        pass

    def sync_user_topics(self, payload):
        if not payload:
            return

        join_screen = self.screens['join']

        new_items = payload.get("items", [])
        on_top = payload.get("on_top", False)
        is_end = payload.get("end_of_data", False)

        print(f"[DEBUG-GUI] Received {len(new_items)} items from state. End of data? {is_end}")

        current_scroll_pos = join_screen.scrollable_area._parent_canvas.yview()

        current_role = self.gui_state.get_state(StateKey.ROLE)
        button_factory = TOPIC_ACTIONS_REGISTRY.get(current_role, lambda t: [])

        for topic in new_items:

            raw_buttons = button_factory(topic)
            live_buttons = []

            for btn_conf in raw_buttons:
                live_btn = btn_conf.copy()
                act_key = live_btn.pop('action_key')

                live_btn['command'] = lambda ak=act_key, t=topic: self.handle_topic_action(ak, t)
                live_buttons.append(live_btn)

            join_screen.add_topic_card(
                id=topic.get('id'),
                title=topic.get('title'),
                summary=topic.get('summary'),
                category=topic.get('category'),
                url=topic.get('url'),
                on_top=on_top,
                btn_configs=live_buttons
            )

        join_screen.update_idletasks()

        if is_end:
            join_screen.all_topics_downloaded = True
            print("[DEBUG-GUI] Download complete. Reached true end of database.")

        if on_top and new_items:
            join_screen.scrollable_area._parent_canvas.yview_moveto(current_scroll_pos[0])

        self.after(100, join_screen.release_scroll_lock)

    def show_screen(self, screen_name):
        if screen_name not in self.screens or self.current_screen == screen_name:
            return

        if self.current_screen:
            self.screens[self.current_screen].grid_remove()

        self.screens[screen_name].grid(row=1, column=1, sticky="nsew", pady= (0,50), padx=10)
        self.current_screen = screen_name

    def toggle_appearance_mode(self):
        if self.appearance_mode_switch.get() == 1:
            self.change_appearance_mode_event("dark")
            self.appearance_mode_switch.configure(text='🌙')
        else:
            self.change_appearance_mode_event("light")
            self.appearance_mode_switch.configure(text='☀️')

    def change_appearance_mode_event(self, new_mode):
        self.update_idletasks()
        ctk.set_appearance_mode(new_mode)
        self.update()

    def _update_status(self, code=None):
        if not code:
            return

        payload = self.gui_state.get_state(StateKey.LAST_PAYLOAD) or {}

        expiry = payload.get(Contract.EXPIRY)


        if self._is_in_penalty and expiry is None:
            return

        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        if expiry is not None:
            self._is_in_penalty = True
            self.status_dot.configure(fg_color="red")
            self._update_countdown(expiry, code)
            return

        display_text = ResponseTranslator.get_message(code, **payload)
        display_color = ResponseTranslator.get_color(code)

        self.status_dot.configure(fg_color=display_color)
        self.status_label.configure(text=display_text, text_color=display_color)

        self._timer_id = self.after(5000, self._reset_status)

    def _update_countdown(self, remaining, code):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        if remaining > 0:
            display_text = ResponseTranslator.get_message(code, expiry=remaining)
            self.status_label.configure(text=display_text, text_color="red")

            self._timer_id = self.after(1000, self._update_countdown, remaining - 1, code)
        else:
            self._reset_status()

    def _reset_status(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        # 🟢 שחרור המנעול הויזואלי קריטי כאן כדי לאפשר חזרה לשגרה
        self._is_in_penalty = False

        self.gui_state.set_state(StateKey.CODE, '')

        if self.gui_state.get_state(StateKey.CONNECTED):
            self.status_label.configure(text="מערכת פעילה", text_color="#B0903D")
            self.status_dot.configure(fg_color="#2ECC71")
        else:
            self.status_label.configure(text="מנותק מהשרת", text_color="red")
            self.status_dot.configure(fg_color="red")