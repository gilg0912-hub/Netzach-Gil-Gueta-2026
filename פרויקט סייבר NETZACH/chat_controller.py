
import customtkinter as ctk
from app_constants import MsgCodes
from navigation import NavSidebar, Menu
from chat_widgets import ChatRoom, ActionsScreen
from ui_components import ScrollableSectionFrame
from app_constants import StateKey, Contract, MsgType
from gui_state_mgmt import ResponseTranslator
from PIL import Image
from modals import load_ui_image, resize_image

"""
class ChatController(ctk.CTkFrame):
    def __init__(self, parent, gui_state, services):
        super().__init__(parent, fg_color='#0A1929')
        self.gui_state = gui_state
        self.chat_service = services['chat']
        self.rooms = {}
        self.current_room_id = None



        ctk.CTkFrame(self, fg_color="#1E4976", height=2).pack(fill="x")

        self.menu = Menu(self, self.gui_state)

        self.menu.add_btn("צ'אט👪", lambda: self.show_screen('chat'))
        self.menu.add_btn('הצטרפות👋', lambda: self.show_screen('actions'))
        self.menu.add_btn('צור קבוצה➕')
        self.menu.add_bottom_btn('פרופיל⚙')

        self.menu.pack(side='left', fill='y')

        ctk.CTkFrame(self, fg_color="#1E4976", width=2).pack(fill="y", padx=10, side="left")

        self.navigation_sidebar = NavSidebar(self, self.chat_service, self.gui_state, self.show_screen)
        self.navigation_sidebar.pack(side="left", fill="y", padx=(10, 5), pady=10)

        ctk.CTkFrame(self, fg_color="#1E4976", width=2).pack(fill="y", padx=10, side="left")

        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=20)
        self.main_container.pack(side="right", expand=True, fill="both", padx=(5, 10), pady=10)

        self.chat_header = ctk.CTkFrame(self.main_container, fg_color="transparent", height=60)
        self.chat_header.pack(fill="x", padx=20, pady=10)

        self.room_name_label = ctk.CTkLabel(self.chat_header, text="בחר שיחה מהתפריט",
                                            font=("Heebo", 20, "bold"), text_color="#B0903D")
        self.room_name_label.pack(side="right")

        self.chat_container = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=20)

        self.actions_container= ActionsScreen(self.main_container, self.gui_state, self.chat_service)
        self.current_screen = None
        self.screens = {
            'chat': self.chat_container,
            'actions': self.actions_container
        }


        self.message_view = ScrollableSectionFrame(self.chat_container, self.gui_state, self.chat_service,'קבוצה')
        self.message_view.pack(expand=True, fill="both", padx=15, pady=5)

        self.input_frame = ctk.CTkFrame(self.chat_container, fg_color="transparent", height=80)
        self.input_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.msg_entry = ctk.CTkEntry(self.input_frame, placeholder_text="הקלד הודעה...", font=("Heebo", 14),
                                      height=45, fg_color="#1A242F", border_width=0, justify="right")
        self.msg_entry.pack(side="right", expand=True, fill="x", padx=(10, 0))
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(self.input_frame, text="➤", width=60, height=45, font=("Arial", 30),
                                      fg_color="#B0903D", hover_color="#8C7230", text_color="#0A2140",
                                      command=self.send_message)

        self.send_btn.pack(side="left")

        self._handlers = {
            MsgType.JOIN_ROOM: self._handle_room_joined,
            MsgType.CREATE_CHAT_ROOM: self._handle_room_joined,
            MsgType.GET_OLDER_MESSAGES: self._handle_history,
            MsgType.RECEIVE_MSG: self._handle_new_chat_msg
        }

        for m_type in self._handlers.keys():
            self.chat_service.dispatcher.register(m_type, self._main_dispatch_gate)

        self._register_handlers()
        self.show_screen('chat')

    def show_screen(self, screen_name):
        if screen_name == self.current_screen or screen_name not in self.screens:
            return

        if self.current_screen:
            self.screens[self.current_screen].pack_forget()
        self.screens[screen_name].pack(fill="both", expand=True, padx=20, pady=10)
        self.current_screen = screen_name
    def _register_handlers(self):
        self._handlers = {
            MsgType.JOIN_ROOM: self._handle_room_joined,
            MsgType.CREATE_CHAT_ROOM: self._handle_room_joined,
            MsgType.RECEIVE_MSG: self._handle_new_chat_msg
        }
        for m_type in self._handlers.keys():
            self.chat_service.dispatcher.register(m_type, self._main_dispatch_gate)

    def send_message(self):
        text = self.msg_entry.get().strip()
        if text and self.current_room_id:
            payload = {Contract.ROOM_ID: self.current_room_id, 'content': text}
            self.chat_service.dispatcher.send_msg(MsgType.SEND_MSG, payload)
            self.msg_entry.delete(0, 'end')

    def _main_dispatch_gate(self, data, code):
        msg_type = self.gui_state.get_state(StateKey.LAST_MSG_TYPE)
        handler = self._handlers.get(msg_type)
        if handler:
            handler(data, code)
        else:
            print(f"Warning: No handler defined for {msg_type}")

    def _handle_room_joined(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        topic = data.get(Contract.TOPIC)
        if room_id and room_id not in self.rooms:
            new_room = ChatRoom(self.chat_container, self.chat_service, room_id, topic)
            self.rooms[room_id] = new_room
            self.switch_room(room_id)

    def _handle_history(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        if room_id in self.rooms:
            self.rooms[room_id].update_older_messages(data.get(Contract.MSGS, []))
            self.rooms[room_id].is_loading = False

    def _handle_new_chat_msg(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        if room_id in self.rooms:
            is_me = (data.get(Contract.SENDER_PID) == self.gui_state.get_state(StateKey.PUBLIC_ID))
            self.rooms[room_id].handle_incoming_message(
                sender=data.get(Contract.DISPLAY_NAME),
                text=data.get(Contract.CONTENT),
                is_me=is_me
            )

    def switch_room(self, room_id):
        if self.current_room_id in self.rooms:
            self.rooms[self.current_room_id].hide()
        self.current_room_id = room_id
        if room_id in self.rooms:
            self.rooms[room_id].show()
"""

#0A1929
class ChatController(ctk.CTkFrame):
    def __init__(self, parent, gui_state, services):
        super().__init__(parent, fg_color='#0D1B2A')
        self.gui_state = gui_state
        self.chat_service = services['chat']
        self.rooms = {}
        self.current_room_id = None



        self.header = ctk.CTkFrame(self, fg_color='#0B131E', corner_radius=0)

        self.title = ctk.CTkLabel(self.header, fg_color='#0B131E', font = ('Hebbo', 24, 'bold'), text_color='#B0903D', text= "//נצ\"ח להנצחת המורשת הישראלית")
        self.title.pack(side='right', padx=10, pady=10)
        self.status_dot = ctk.CTkFrame(self.header, width=8, height=8, corner_radius=4, fg_color="#2ECC71")
        self.status_dot.pack(side="right", padx=(0, 12), pady=12)

        self.status_label = ctk.CTkLabel(
            self.header,
            text="מערכת פעילה",
            font=("Heebo", 15, "bold"),
            text_color="#B0903D"
        )
        self.status_label.pack(side="right", padx=8)
        self.header.grid(row=0, column=1, sticky='nsew')
        self._timer_id = None
        self.gui_state.register(StateKey.CODE, self._update_status_display)

        self.navigation = ctk.CTkFrame(self, fg_color='#0D1B2A', corner_radius=0, border_width=0)
        self.navigation.grid(row=1, column=0, sticky='nsew')

        self.menu = Menu(self.navigation, self.gui_state)
        self.menu.add_btn("בית 🏠")
        self.menu.add_btn('קבוצות 👨‍👩‍👧', lambda: self.show_screen('chat'))
        self.menu.add_btn('צור קבוצה ➕', lambda: self.show_screen('actions'))
        self.menu.add_btn('הצטרפות 👋', lambda: self.show_screen('actions'))
        self.menu.pack(side='top', fill='x')

        self.sidebar = NavSidebar(self.navigation, self.chat_service, self.gui_state, self.show_screen)
        self.sidebar.pack(fill= 'both', expand=True)

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)

        self.main_container = ctk.CTkFrame(self, fg_color="#0B131E", corner_radius=0)
        self.main_container.grid(row=1, column=1, sticky='nsew')

        self.display_screen = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
        self.display_screen.place(relx=0.5, rely=0.5, anchor="center", relwidth=1, relheight=1)
        self.label_name = ctk.CTkLabel(
            self.display_screen,
            text='ברוך הבא למערכת נצ"ח',
            font=('Heebo', 28, 'bold'),
            text_color='#B0903D'
        )
        self.label_name.pack(side='top', padx=(0, 12), pady=12)

        self.chat_container = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=20, bg_color= 'transparent')

        self.actions_container= ActionsScreen(self.main_container, self.gui_state, self.chat_service)

        self.current_screen = None
        self.screens = {
            'chat': self.chat_container,
            'actions': self.actions_container
        }

        self.main_container.pack_propagate(False)

        self.message_view = ScrollableSectionFrame(self.chat_container, self.gui_state, self.chat_service,'קבוצה')
        self.message_view.pack(expand=True, fill="both", padx=15, pady=5)

        self.input_frame = ctk.CTkFrame(self.chat_container, fg_color="transparent", height=80)
        self.input_frame.pack(fill="x", padx=15, pady=(5, 15))

        self.msg_entry = ctk.CTkEntry(self.input_frame, placeholder_text="...הקלד הודעה", font=("Heebo", 14),
                                      height=45, fg_color="#1A242F", border_width=0, justify="right")
        self.msg_entry.pack(side="right", expand=True, fill="x", padx=(10, 0))
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ctk.CTkButton(self.input_frame, text="➤", width=60, height=45, font=("Arial", 30),
                                      fg_color="#B0903D", hover_color="#8C7230", text_color="#0A2140", corner_radius=200,
                                      command=self.send_message)

        self.send_btn.pack(side="left")

        self._handlers = {
            MsgType.JOIN_ROOM: self._handle_room_joined,
            MsgType.CREATE_CHAT_ROOM: self._handle_room_joined,
            MsgType.GET_OLDER_MESSAGES: self._handle_history,
            MsgType.RECEIVE_MSG: self._handle_new_chat_msg
        }

        for m_type in self._handlers.keys():
            self.chat_service.dispatcher.register(m_type, self._main_dispatch_gate)

        self._register_handlers()
        self.gui_state.register(StateKey.DISPLAY_NAME, self._update_display_name)




    def show_screen(self, screen_name):
        if screen_name == self.current_screen or screen_name not in self.screens:
            return

        if self.current_screen:
            self.screens[self.current_screen].pack_forget()
        self.screens[screen_name].pack(fill="both", expand=True, padx=20, pady=10)
        self.current_screen = screen_name

    def _update_display_name(self, display_name):
        if display_name:
            log_text = ',ברוכים הבאים' if self.gui_state.get_state(StateKey.CODE)== MsgCodes.SIGNUP_SUCCESS else ',ברוכים השבים'
            self.label_name.configure(text=  f'{display_name} {log_text}')
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

    def _register_handlers(self):
        self._handlers = {
            MsgType.JOIN_ROOM: self._handle_room_joined,
            MsgType.CREATE_CHAT_ROOM: self._handle_room_joined,
            MsgType.RECEIVE_MSG: self._handle_new_chat_msg
        }
        for m_type in self._handlers.keys():
            self.chat_service.dispatcher.register(m_type, self._main_dispatch_gate)

    def send_message(self):
        text = self.msg_entry.get().strip()
        if text and self.current_room_id:
            payload = {Contract.ROOM_ID: self.current_room_id, 'content': text}
            self.chat_service.dispatcher.send_msg(MsgType.SEND_MSG, payload)
            self.msg_entry.delete(0, 'end')

    def _main_dispatch_gate(self, data, code):
        msg_type = self.gui_state.get_state(StateKey.LAST_MSG_TYPE)
        handler = self._handlers.get(msg_type)
        if handler:
            handler(data, code)
        else:
            print(f"Warning: No handler defined for {msg_type}")

    def _handle_room_joined(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        topic = data.get(Contract.TOPIC)
        if room_id and room_id not in self.rooms:
            new_room = ChatRoom(self.chat_container, self.chat_service, room_id, topic)
            self.rooms[room_id] = new_room
            self.switch_room(room_id)

    def _handle_history(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        if room_id in self.rooms:
            self.rooms[room_id].update_older_messages(data.get(Contract.MSGS, []))
            self.rooms[room_id].is_loading = False

    def _handle_new_chat_msg(self, data, code):
        room_id = data.get(Contract.ROOM_ID)
        if room_id in self.rooms:
            is_me = (data.get(Contract.SENDER_PID) == self.gui_state.get_state(StateKey.PUBLIC_ID))
            self.rooms[room_id].handle_incoming_message(
                sender=data.get(Contract.DISPLAY_NAME),
                text=data.get(Contract.CONTENT),
                is_me=is_me
            )

    def switch_room(self, room_id):
        if self.current_room_id in self.rooms:
            self.rooms[self.current_room_id].hide()
        self.current_room_id = room_id
        if room_id in self.rooms:
            self.rooms[room_id].show()




CHAT_THEMES = {
    "classic": ('#F2EAD6', '#e4f0d0'),
    "moreshet": ('#CB883A', '#FFF3B0'),
    "gray": ('brown', '#e4f0d0'),
    "design": ('#b4b4b4', '#F2F3F4'),
    "retro": ('#CB883A', '#e4f0d0'),
    "nature": ('#648B1A', '#C6E788'),
    "pink": ('#E7E4E6', 'white'),
    "Gilboa iris": ('#495993', '#778CC8'),
    "flower": ('#e4f0d0', '#fffcf7'),
    "hermon": ('#7097ab', '#d3e7ee'),
    "dark": ('#313647', '#435663'),
    "negev": ('#C1856D', '#E6CFA9'),
    "traditional spirit": ("#F5E6C8", 'gray86'),
    "yellow": ('#E1F089', '#EFFF92'),
    "green": ('#6ACBB4', '#98F3DE'),
    "jerusalem stone": ('#F5E6C8', '#dbdbb5'),
    'IDF': ('#4B5320', '#8B7355'),
    'Galil': ('#3B7A57', '#A7D88C'),
    'yehuda desert': ('#E1B87F', '#D1A66A'),
    'dead_sea': ('#F2F2E1', '#4A7D7C'),
    'Israel flag': ('#0038B8', '#FFFFFF')
    }