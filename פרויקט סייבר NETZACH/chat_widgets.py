import customtkinter as ctk
from ui_components import ScrollableSectionFrame
from datetime import datetime
from PIL import Image
from app_constants import StateKey, Contract

class ChatRoom:
    def __init__(self, master, chat_service, room_id, topic):
        self.chat_service = chat_service
        self.room_id = room_id
        self.topic = topic

        self.chat_area = ChatArea(master, self.request_more_history)

        self.messages_history = []
        self.all_msgs_downloaded = False
        self.is_loading = False

    def handle_incoming_message(self, sender, text, is_me):
        self.messages_history.append({Contract.SENDER: sender, 'content': text})
        self.chat_area.add_message(sender, text, is_me)

    def request_more_history(self):
        if self.all_msgs_downloaded or self.is_loading:
            return

        if self.messages_history:
            oldest_id = self.messages_history[0].get(Contract.MSG_ID)

            self.is_loading = True
            self.chat_service.fetch_older_messages(self.room_id, oldest_id)

    def update_older_messages(self, older_messages):
        if not older_messages:
            self.all_msgs_downloaded = True
            return

        existing_ids = {msg[Contract.MSG_ID] for msg in self.messages_history}
        new_old_messages = [msg for msg in older_messages if msg[Contract.MSG_ID] not in existing_ids]

        if not new_old_messages:
            return

        self.messages_history = new_old_messages + self.messages_history

        for msg in reversed(new_old_messages):
            my_pid = self.chat_service.gui_state.get_state(StateKey.PUBLIC_ID)
            is_me = (msg.get(Contract.SENDER_PID) == my_pid)

            self.chat_area.add_message_to_top(
                sender=msg.get(Contract.DISPLAY_NAME, "Unknown"),
                text=msg.get('content', ""),
                is_me=is_me
            )


class ChatArea(ctk.CTkScrollableFrame):
    def __init__(self, parent, on_request_history, **kwargs):
        super().__init__(parent, fg_color="#1A242F", corner_radius=10, **kwargs)


        self.on_request_history = on_request_history
        self.columnconfigure(0, weight=1)

        self.messages = []

        self._parent_canvas.configure(yscrollcommand=self._on_scroll)

    def _on_scroll(self, *args):
        self._scrollbar.set(*args)

        current_pos = float(args[0])

        if current_pos <= 0.05:
            self.on_request_history()

    def add_message(self, sender, text, is_me=False):
        bubble_color = "#1f538d" if is_me else "#333333"
        anchor = "e" if is_me else "w"
        alignment = 1 if is_me else 0  # 0 לשמאל, 1 לימין

        # יצירת פריים קטן לבועה
        message_frame = ctk.CTkFrame(self, fg_color="transparent")
        message_frame.grid(row=len(self.messages), column=0, pady=5, padx=10, sticky=anchor)

        # שם השולח וזמן
        timestamp = datetime.now().strftime("%H:%M")
        info_text = f"{timestamp} - {sender}" if not is_me else f"אני - {timestamp}"

        info_label = ctk.CTkLabel(message_frame, text=info_text, font=("Arial", 10), text_color="gray")
        info_label.pack(side="top", anchor=anchor, padx=5)

        # בועת הטקסט עצמה
        bubble = ctk.CTkLabel(
            message_frame,
            text=text,
            fg_color=bubble_color,
            corner_radius=15,
            padx=15,
            pady=8,
            wraplength=300,  # שבירת שורות אוטומטית
            justify="right" if is_me else "left"
        )
        bubble.pack(side="top", anchor=anchor)

        self.messages.append(message_frame)

        # גלילה אוטומטית למטה כשמגיעה הודעה חדשה
        self.after(10, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        self._parent_canvas.yview_moveto(1.0)

    def clear_chat(self):
        for msg in self.messages:
            msg.destroy()
        self.messages = []

class ActionsScreen(ctk.CTkFrame):
    def __init__(self, parent, gui_state, chat_service, **kwargs):
        super().__init__(parent, fg_color='#0D1B2A', **kwargs)


        self.gui_state = gui_state
        self.chat_service = chat_service


        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)


        self.left_column = ctk.CTkFrame(self, fg_color="transparent")
        self.right_column = ctk.CTkFrame(self, fg_color="transparent")

        self.topic_container = ScrollableSectionFrame(self, self.gui_state, self.chat_service, 'הצטרפות באמצעות נושא')
        self.p_key_container = ScrollableSectionFrame(self, self.gui_state, self.chat_service, 'הצטרפות באמצעות קוד קבוצה')
        self.create_container = ScrollableSectionFrame(self, self.gui_state, self.chat_service, 'צור קבוצה')


        self.topic_container.pack(in_=self.left_column, fill='both', expand=True, padx=5, pady=5)
        self.p_key_container.pack(in_=self.right_column, side='top', fill='both', expand=True, padx=5, pady=5)
        self.create_container.pack(in_=self.right_column, side='top', fill='both', expand=True, padx=5, pady=5)


        self.left_column.grid(row=0, column=0, sticky='nsew')
        self.right_column.grid(row=0, column=1, sticky='nsew')



