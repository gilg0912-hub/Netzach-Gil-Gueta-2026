import customtkinter as ctk
import time
import os
import threading
import tkinter.filedialog as filedialog

import pythoncom
import win32com.client

from ui_components import TopicCard, RequiredEntry
from app_constants import StateKey, Contract, UserRole, MsgType

class RoomProfileWindow(ctk.CTkToplevel):
    def __init__(self, parent, room_data):
        super().__init__(parent)
        self.title("פרטי חדר")
        self.geometry("400x550")
        self.configure(fg_color="#0F172A")  # רקע כהה עמוק
        self.attributes("-topmost", True)

        # כותרת עם אפקט זוהר
        ctk.CTkLabel(self, text=room_data.display_name,
                     font=("Heebo", 24, "bold"), text_color="#38BDF8").pack(pady=(30, 20))

        # מיכל הנתונים - עיצוב כרטיס עם מסגרת מודגשת
        info_container = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=20, border_width=2,
                                      border_color="#334155")
        info_container.pack(fill="both", expand=True, padx=25, pady=(0, 30))

        # פונקציה פנימית ליצירת שורות מעוצבות (פתרון הנקודתיים)
        def create_row(label, value, is_status=False):
            row = ctk.CTkFrame(info_container, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=12)

            ctk.CTkLabel(row, text=str(value), font=("Heebo", 14), text_color="white").pack(side="left")

            if is_status:
                canvas = ctk.CTkCanvas(row, width=12, height=12, bg="#1E293B", highlightthickness=0)
                canvas.pack(side="right", padx=5)
                color = "#22C55E" if room_data.is_open else "#EF4444"
                canvas.create_oval(2, 2, 10, 10, fill=color, outline="")

            ctk.CTkLabel(row, text=f" :{label}", font=("Heebo", 14, "bold"), text_color="#94A3B8").pack(side="right")


        create_row("קטגוריה", room_data.category)
        create_row("קוד הזמנה", room_data.invite_code)
        create_row("סטטוס", "זמין" if room_data.is_open else "סגור", is_status=True)
        create_row("נוצר על ידי", room_data.created_by)
        create_row("תאריך", time.strftime('%d/%m/%Y', time.localtime(room_data.created_at)))
        create_row('תיאור הקבוצה', room_data.summary)

        # כפתור סגירה מעוצב
        ctk.CTkButton(self, text="סגור חלון", command=self.destroy,
                      width=200, height=45, corner_radius=12,
                      fg_color="#38BDF8", text_color="#0F172A", font=("Heebo", 16, "bold")).pack(pady=(0, 20))

class ChatRoom:
    def __init__(self, room_id, category, total_participants, participants, display_name, invite_code, allowed_type, is_open, summary=None, created_by=None, created_at=None, **kwargs):
        self.room_id = str(room_id)
        self.category = category
        self.allowed_type = allowed_type
        self.display_name = display_name
        self.invite_code = invite_code
        self.is_open = is_open
        self.created_by = created_by
        self.created_at = created_at
        self.participants = participants
        self.total_participants = total_participants
        self.summary = summary
        print(self.summary, 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA')

        self.history_ended = False

    @classmethod
    def from_dict(cls, data: dict):
        if not data:
            return None
        return cls(
            room_id=data.get(Contract.ROOM_ID),
            category= data.get(Contract.CATEGORY),
            allowed_type=data.get(Contract.TYPE),
            invite_code=data.get(Contract.INVITE_CODE),
            is_open=data.get(Contract.IS_OPEN, True),
            created_by=data.get(Contract.CREATED_BY),
            created_at=data.get(Contract.CREATED_AT),
            display_name = data.get(Contract.DISPLAY_NAME),
            participants = data.get(Contract.PARTICIPANTS),
            total_participants = data.get(Contract.TOTAL_PARTICIPANTS),
            summary = data.get(Contract.SUMMARY)
        )

class BaseScreen(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

    def on_show(self):
        pass

    def finalize_load(self):
        pass

class ScrollScreen(ctk.CTkScrollableFrame):
    def __init__(self, parent, gui_state,
                 on_top_reach=None, on_bottom_reach=None, **kwargs):
        super().__init__(parent, fg_color= kwargs.pop('fg_color', ('white','#0F172A')), **kwargs)

        self.gui_state = gui_state

        self.on_top_reach = on_top_reach
        self.on_bottom_reach = on_bottom_reach

        self._is_loading = False

        self._original_scrollbar_set = self._scrollbar.set

        self._parent_canvas.configure(yscrollcommand=self._intercept_scroll_set)


    def _intercept_scroll_set(self, first, last):
        self._original_scrollbar_set(first, last)

        if not self.gui_state.get_state(StateKey.CONNECTED):
            return

        if self._is_loading:
            return

        current_top = float(first)
        current_bottom = float(last)

        if current_top == 0.0 and current_bottom == 1.0:
            return

        if current_top <= 0.05 and self.on_top_reach is not None:
            self._is_loading = True
            self.on_top_reach()

        elif current_bottom >= 0.95 and self.on_bottom_reach is not None:
            self._is_loading = True
            self.on_bottom_reach()

    def reset_loading_state(self):
        self._is_loading = False

class ChatArea(ScrollScreen):
    def __init__(self, parent, gui_state, chat_service, **kwargs):
        kwargs.setdefault('fg_color', ('#f8fafc', '#0F172A'))
        super().__init__(parent, gui_state, on_top_reach=self.on_top_reach, **kwargs)

        self.gui_state = gui_state
        self.chat_service = chat_service
        self.msg_frames = []


        self.current_room = None

        self.gui_state.register(StateKey.MESSAGES_UI_SIGNAL, self._on_messages_signal)
        self.gui_state.register(StateKey.CURRENT_ROOM_ID, self._on_room_switched)

    def on_top_reach(self):
        if not self.current_room or self.current_room.history_ended:
            self.reset_loading_state()
            return

        if self.msg_frames:
            oldest_msg_id = self.msg_frames[0].msg_id
            self.chat_service.fetch_older_messages(self.current_room.room_id, oldest_msg_id)
        else:
            self.reset_loading_state()

    def _on_room_switched(self, new_room_id):
        current_active_id = self.current_room.room_id if self.current_room else None
        if not new_room_id or str(new_room_id) == str(current_active_id):
            return

        self.clear_chat_ui()
        all_rooms = self.gui_state.get_state(StateKey.SYNC_ROOMS) or []

        matched_room = None
        for room in all_rooms:
            if str(room.room_id) == str(new_room_id):
                matched_room = room

        if not matched_room:
            self.current_room = None
            return

        self.current_room = matched_room
        self.reset_loading_state()

        all_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}
        room_messages = all_messages.get(str(new_room_id), [])

        for msg in room_messages:
            self._create_message_bubble(msg, scroll_to_bottom=False)

        self.after(50, self.scroll_to_bottom)

    def _on_messages_signal(self, signal_data):
        if not signal_data or not self.current_room:
            return

        if signal_data.get("is_refresh"):
            self.refresh_failed_messages_ui()
            return

        if str(signal_data.get(Contract.ROOM_ID)) != str(self.current_room.room_id):
            return

        if signal_data.get("is_confirmation"):
            tmp_id = signal_data.get("tmp_id")
            real_id = signal_data.get("real_id")
            server_time = signal_data.get("server_time")

            for frame in self.msg_frames:
                if str(frame.msg_id) == str(tmp_id):
                    frame.msg_id = real_id
                    frame.configure(fg_color=('#0284c7', '#1e3a8a'))
                    frame.time_label.configure(text=time.strftime('%H:%M', time.localtime(server_time)))
                    return
            return

        # חסימת אירועי רפאים בזמן עדכון הממשק
        self._is_loading = True

        items = signal_data.get(Contract.ITEMS, [])
        is_older = signal_data.get("is_older", False)
        end_of_data = signal_data.get("end_of_data", False)

        if end_of_data:
            self.current_room.history_ended = True

        if not items:
            self.reset_loading_state()
            return

        if is_older:
            is_initial_room_load = (len(self.msg_frames) == 0)

            if is_initial_room_load:
                self.load_historical_messages(items)

                # 🟢 הכרחת עדכון גבולות מיידי לקנבס לפני הגלילה
                self.update_idletasks()
                self._parent_canvas.configure(scrollregion=self._parent_canvas.bbox("all"))

                self.scroll_to_bottom()
                self.after(100, self.reset_loading_state)
            else:
                anchor_msg = self.msg_frames[0]
                self.load_historical_messages(items)

                # 🟢 1. חישוב מחודש של הגדלים (גורם לווידג'טים "להיתפס" פיזית למקומם החדש)
                self.update_idletasks()

                # 🟢 2. שורת הקסם (התיקון הקריטי):
                # אנו מעדכנים ידנית את ה-scrollregion. בלעדי זה, פקודת ה-yview מתבטלת!
                self._parent_canvas.configure(scrollregion=self._parent_canvas.bbox("all"))

                # 3. עכשיו כשהקנבס יודע בוודאות שהוא גדול יותר, הזזת ה-Scrollbar תעבוד
                new_height = self._parent_canvas.bbox("all")[3]
                if new_height:
                    fraction = anchor_msg.winfo_y() / new_height
                    safe_fraction = max(fraction, 0.05)
                    self._parent_canvas.yview_moveto(safe_fraction)

                self.after(100, self.reset_loading_state)
        else:
            for msg in items:
                self._create_message_bubble(msg, scroll_to_bottom=False)
            self.after(30, self.scroll_to_bottom)
            self.after(100, self.reset_loading_state)
    def load_historical_messages(self, messages_list):
        for msg in reversed(messages_list):
            self._create_message_bubble(msg, scroll_to_bottom=False, insert_at_top=True)

    def append_message(self, msg_data):
        self._create_message_bubble(msg_data, scroll_to_bottom=True)

    def _create_message_bubble(self, msg_data: dict, scroll_to_bottom=False, insert_at_top=False):
        msg_id = str(msg_data.get(Contract.MSG_ID, ""))
        sender = msg_data.get(Contract.SENDER_PID)
        content = msg_data.get(Contract.CONTENT)
        timestamp = msg_data.get(Contract.TIMESTAMP, time.time())

        is_pending = msg_id.startswith("tmp_")

        is_system = sender in [None, "System", "None"]

        is_me = False if is_system else (str(sender) == str(self.gui_state.get_state(StateKey.PUBLIC_ID)))

        sender_display_name = self.current_room.participants.get(sender, 'הודעת מערכת')

        if is_system:
            bubble_fg = ('#fef08a', '#ca8a04')
            text_color = ('#713f12', '#fefce8')
            align = 'center'
            padx_bubble = (10, 10)
            justify_val = 'center'
            msg_anchor = 'center'
            time_color = ('#a16207', '#fde047')
        elif is_me:
            bubble_fg = ('#7dd3fc', '#0c4a6e') if is_pending else ('#0284c7', '#1e3a8a')
            text_color = ('white', 'white')
            align = 'e'
            padx_bubble = (50, 15)
            justify_val = 'right'
            msg_anchor = 'e'
            time_color = ('#93c5fd', '#93c5fd')
        else:
            bubble_fg = ('#f1f5f9', '#1e293b')
            text_color = ('#0f172a', '#f8fafc')
            align = 'w'
            padx_bubble = (15, 50)
            justify_val = 'left'
            msg_anchor = 'w'
            time_color = ('#64748b', '#94a3b8')

        msg_frame = ctk.CTkFrame(self, fg_color=bubble_fg, corner_radius=12)
        msg_frame.msg_id = msg_id

        if not is_system and not is_me:
            ctk.CTkLabel(msg_frame, text=f"{sender_display_name} 👤", font=("Heebo", 11, "bold"),
                         text_color=('#0284c7', '#38bdf8')).pack(anchor='w', padx=12, pady=(6, 0))

        ctk.CTkLabel(msg_frame, text=content, font=("Heebo", 13), text_color=text_color, wraplength=280,
                     justify=justify_val).pack(anchor=msg_anchor, padx=12, pady=(4, 2))

        readable_time = time.strftime('%H:%M', time.localtime(timestamp))
        if is_pending:
            readable_time += " 🕒"

        time_anchor = 'center' if is_system else 'e'
        time_label = ctk.CTkLabel(msg_frame, text=readable_time, font=("Heebo", 9), text_color=time_color)
        time_label.pack(anchor=time_anchor, padx=12, pady=(0, 5))
        msg_frame.time_label = time_label

        if insert_at_top and self.msg_frames:
            msg_frame.pack(anchor=align, pady=4, padx=padx_bubble, fill='none', before=self.msg_frames[0])
            self.msg_frames.insert(0, msg_frame)
        else:
            msg_frame.pack(anchor=align, pady=4, padx=padx_bubble, fill='none')
            self.msg_frames.append(msg_frame)

        if scroll_to_bottom:
            self.after(30, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        self._parent_canvas.yview_moveto(1.0)

    def refresh_failed_messages_ui(self):
        all_messages = self.gui_state.get_state(StateKey.SYNC_MESSAGES) or {}
        room_messages = all_messages.get(str(self.current_room.room_id), [])

        failed_ids = {str(msg.get(Contract.MSG_ID)) for msg in room_messages if msg.get("status") == "failed"}

        for frame in self.msg_frames:
            if str(frame.msg_id) in failed_ids:
                frame.configure(fg_color=('#f87171', '#991b1b'))
                if hasattr(frame, 'time_label'):
                    frame.time_label.configure(text="שגיאה ❌", text_color=('#7f1d1d', '#fca5a5'))

    def clear_chat_ui(self):
        for frame in self.msg_frames:
            frame.pack_forget()
            frame.destroy()
        self.msg_frames.clear()

class ChatScreen(BaseScreen):
    def __init__(self, parent, gui_state, chat_service):  # הוספנו את chat_service כדי לאפשר שליחה
        super().__init__(parent, fg_color='transparent', corner_radius=20)

        self.gui_state = gui_state
        self.chat_service = chat_service
        self.chat_header = ChatHeader(self, gui_state, corner_radius=0)
        self.chat_header.pack(fill='x', side='top', padx=5, pady=5)

        # 1. אזור ההודעות הנגלל (תופס את כל המרכז)
        self.chat_area = ChatArea(self, gui_state, self.chat_service, corner_radius=0)
        self.chat_area.pack(fill="both", expand=True, pady=(0, 5), padx=5)

        # 2. 🟢 פאנל כתיבה ושליחה קבוע שנשאר תמיד בתחתית המסך
        self.chat_input = ChatInputFrame(self, chat_service, gui_state)
        self.chat_input.pack(fill='x', side='bottom', padx=5, pady=5)

class ChatInputFrame(ctk.CTkFrame):
    def __init__(self, parent, chat_service, gui_state, **kwargs):
        kwargs.setdefault('fg_color', ('#ffffff', '#151C2B'))
        kwargs.setdefault('height', 50)
        super().__init__(parent, **kwargs)

        self.chat_service = chat_service
        self.gui_state = gui_state
        self.pack_propagate(False)

        # כפתור שליחה
        self.send_btn = ctk.CTkButton(
            self, text="⚡ שלח", font=("Heebo", 13, "bold"),
            fg_color="#0284c7", hover_color="#0369a1", text_color="white",
            width=70, height=36, command=self.send_message
        )
        self.send_btn.pack(side="left", padx=10, pady=7)

        # תיבת קלט הטקסט
        self.textbox = ctk.CTkEntry(
            self, placeholder_text="...הקלד הודעה כאן",
            font=("Heebo", 13), justify="right", height=36
        )
        self.textbox.pack(side="right", fill="x", expand=True, padx=(10, 5), pady=7)

        # קישור מקש Enter לשליחה מהירה מהמקלדת
        self.textbox.bind("<Return>", lambda event: self.send_message())
        self.gui_state.register(StateKey.CURRENT_ROOM_ID, self._change_state)

    def _change_state(self, s):
        state = 'normal' if s else 'disabled'
        self.textbox.configure(state= state)
        self.send_btn.configure(state=state)

    def send_message(self):
        print('Hi')
        content = self.textbox.get().strip()
        current_room = self.gui_state.get_state(StateKey.CURRENT_ROOM_ID)
        print('current_room', current_room, 'content', content)
        if content and current_room:
            self.textbox.delete(0, 'end')
            self.chat_service.send_message(room_id=current_room, content=content)

class ChatHeader(ctk.CTkFrame):
    def __init__(self, parent, gui_state, **kwargs):
        kwargs.setdefault('fg_color', ('#e2e8f0', '#0f172a'))
        kwargs.setdefault('height', 60)
        super().__init__(parent, **kwargs)

        self.gui_state = gui_state
        self.pack_propagate(False)
        self.current_room_obj = None

        self.title_label = ctk.CTkLabel(self, text="...בחר חדר כדי להתחיל", font=("Heebo", 18, "bold"))
        self.title_label.pack(side="right", padx=20, pady=15)

        self.status_label = ctk.CTkLabel(self, text="", font=("Heebo", 12))
        self.status_label.pack(side="right", padx=5, pady=18)

        self.info_button = ctk.CTkButton(
            self, text="ℹ️ פרטי החדר", font=("Heebo", 12, "bold"),
            width=100, fg_color=('#0284c7', '#1e3a8a'), hover_color=('#0369a1', '#1d4ed8'),
            command=self._open_room_profile
        )

        self.gui_state.register(StateKey.CURRENT_ROOM_ID, self._on_room_changed)
        self.gui_state.register(StateKey.ROOMS_UI_SIGNAL, self._on_room_updated)

    def _open_room_profile(self):
        if self.current_room_obj:
            RoomProfileWindow(self, self.current_room_obj)

    def _on_room_changed(self, new_room_id):
        if not new_room_id:
            self.title_label.configure(text="...בחר חדר כדי להתחיל")
            self.status_label.configure(text="")
            self.current_room_obj = None
            self.info_button.pack_forget()
            return

        all_rooms = self.gui_state.get_state(StateKey.SYNC_ROOMS) or []

        for room_obj in all_rooms:
            if str(room_obj.room_id) == str(new_room_id):
                self.current_room_obj = room_obj
                self._update_labels(room_obj)
                self.info_button.pack(side="left", padx=20, pady=15)
                return

    def _on_room_updated(self, signal_data):
        if not signal_data or not signal_data.get(Contract.ITEMS):
            return

        current_room_id = self.gui_state.get_state(StateKey.CURRENT_ROOM_ID)
        if not current_room_id:
            return

        for room_obj in signal_data.get(Contract.ITEMS, []):
            if str(room_obj.room_id) == str(current_room_id):
                self.current_room_obj = room_obj
                self._update_labels(room_obj)
                return

    def _update_labels(self, room_obj):
        # גישה ישירה לתכונות האובייקט
        title = room_obj.display_name if room_obj.display_name else "חדר ללא נושא"
        is_open = room_obj.is_open

        self.title_label.configure(text=title)

        status_text = "🟢 פתוח לשיחה" if is_open else "🔴 החדר נעול"
        status_color = ("#16a34a", "#22c55e") if is_open else ("#dc2626", "#ef4444")
        self.status_label.configure(text=status_text, text_color=status_color)

class CreateScreen(BaseScreen):
    def __init__(self, parent, gui_state, chat_service):
        super().__init__(parent, fg_color="transparent")

        self.gui_state = gui_state
        self.chat_service = chat_service
        self.default_border = ("#E2E8F0", "#30363D")

        self.grid_columnconfigure(0, weight=1)
        self.setup_view()

    def setup_view(self):
        # 1. כותרות
        self.title_label = ctk.CTkLabel(
            self, text="ניהול ואירוח מרחב למידה חדש",
            text_color="#B0903D", font=("Heebo", 26, "bold")
        )
        self.title_label.grid(row=0, column=0, pady=(20, 5), sticky="ew")

        self.subtitle_label = ctk.CTkLabel(
            self, text="כמורה במערכת נצ\"ח, באפשרותך לפתוח קבוצת דיון לימודית מבוססת AI או להגדיר נושא ותקציר משלך.",
            text_color="#A0AEC0", font=("Heebo", 14)
        )
        self.subtitle_label.grid(row=1, column=0, pady=(0, 15), sticky="ew")

        # 2. פריים פנימי מרוכז לטופס
        self.form_frame = ctk.CTkFrame(self, fg_color=("#FFFFFF", "#161B22"), corner_radius=12, border_width=1,
                                       border_color="#30363D")
        self.form_frame.grid(row=2, column=0, padx=40, pady=5, sticky="nsew")
        self.form_frame.grid_columnconfigure(0, weight=1)

        # שדה קלט א': שם קבוצת הדיון
        self.name_label = ctk.CTkLabel(self.form_frame, text=":שם קבוצת הדיון", font=("Heebo", 15, "bold"),
                                       text_color=("#0D1117", "#FFFFFF"))
        self.name_label.grid(row=0, column=0, padx=25, pady=(10, 2), sticky="e")

        self.room_name_entry = RequiredEntry(
            self.form_frame, placeholder_text="לדוגמה: הכנה לבגרות בפיזיקה - קרינה וחומר",
            width=380, height=36, font=("Heebo", 14), justify="right",
        )
        self.room_name_entry.grid(row=1, column=0, padx=25, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(self.form_frame, text=":רמת פרטיות", font=("Heebo", 15, "bold")).grid(row=2, column=0, padx=25,
                                                                                           pady=(0, 2), sticky="e")
        self.privacy_toggle = ctk.CTkSegmentedButton(
            self.form_frame,
            values=["ציבורי (פתוח לכולם)", "פרטי (סגור לכיתה)"],
            font=("Heebo", 14, "bold"),
            selected_color="#B0903D", selected_hover_color="#C5A452"
        )
        self.privacy_toggle.set("פרטי (סגור לכיתה)")  # ברירת המחדל
        self.privacy_toggle.grid(row=2, column=0, padx=25, pady=(0, 10), sticky="ew")

        # שדה בחירה ב': מקור הנושא הלימודי
        self.topic_label = ctk.CTkLabel(self.form_frame, text=":בחר מקור לנושא הלימודי", font=("Heebo", 15, "bold"),
                                        text_color=("#0D1117", "#FFFFFF"))
        self.topic_label.grid(row=3, column=0, padx=25, pady=(0, 2), sticky="e")

        sync_topics = self.gui_state.get_state(StateKey.SYNC_TOPICS) or []
        self.topic_options = [topic.get('title') for topic in sync_topics if topic.get('title')]

        self.custom_option_text = "✍️ ...נושא מותאם אישית (הקלדה חופשית)"
        self.topic_options.insert(0, self.custom_option_text)

        self.topic_dropdown = ctk.CTkOptionMenu(
            self.form_frame, values=self.topic_options,
            width=380, height=36, font=("Heebo", 14),
            fg_color="#55446E", button_color="#6A558A", button_hover_color="#7B639F",
            dropdown_font=("Heebo", 13),
            command=self._on_topic_selection_changed
        )
        self.topic_dropdown.grid(row=4, column=0, padx=25, pady=(0, 10), sticky="ew")

        # שדה קלט ג': כותרת הנושא הלימודי (מוצג תמיד!)
        self.custom_topic_label = ctk.CTkLabel(self.form_frame, text=":כותרת הנושא הלימודי", font=("Heebo", 15, "bold"),
                                               text_color=("#0D1117", "#FFFFFF"))
        self.custom_topic_label.grid(row=5, column=0, padx=25, pady=(0, 2), sticky="e")

        self.custom_topic_entry = RequiredEntry(
            self.form_frame, placeholder_text="לדוגמה: מבצע יונתן והגבורה הלאומית",
            width=380, height=36, font=("Heebo", 14), justify="right",
        )
        self.custom_topic_entry.grid(row=6, column=0, padx=25, pady=(0, 10), sticky="ew")
        # שדה קלט ד': תקציר קבוצת הדיון (מוצג תמיד!)
        self.summary_label = ctk.CTkLabel(self.form_frame, text=":תקציר קבוצת הדיון", font=("Heebo", 15, "bold"),
                                          text_color=("#0D1117", "#FFFFFF"))
        self.summary_label.grid(row=7, column=0, padx=25, pady=(0, 2), sticky="e")

        self.summary_textbox = ctk.CTkTextbox(
            self.form_frame, width=380, height=80, font=("Heebo", 13),
            border_width=1, border_color=("#E2E8F0", "#30363D"),
            wrap="word", activate_scrollbars=True
        )
        self.summary_textbox.tag_config("right_align", justify="right")  # תגית יישור לימין
        self.summary_textbox.grid(row=8, column=0, padx=25, pady=(0, 15), sticky="ew")

        # 3. תווית הודעות סטטוס ושגיאה
        self.error_label = ctk.CTkLabel(self, text="", text_color="red", font=("Heebo", 14, "bold"))
        self.error_label.grid(row=3, column=0, pady=2)

        # 4. כפתור יצירת החדר
        self.create_btn = ctk.CTkButton(
            self, text="🚀 צור והפעל מרחב למידה",
            font=("Heebo", 18, "bold"), fg_color="#B0903D", hover_color="#C5A452", text_color="#0D1117",
            width=250, height=42, corner_radius=8,
            command=self.handle_create_room
        )
        self.gui_state.register(StateKey.RELEASE_BTNS, self.release_create_btn)
        self.create_btn.grid(row=4, column=0, pady=(5, 15))

        # אתחול המצב הראשוני
        self.topic_dropdown.set(self.custom_option_text)
        self._on_topic_selection_changed(self.custom_option_text)

    def _on_topic_selection_changed(self, choice):
        # משחררים את הנעילה ומנקים שדות
        self.custom_topic_entry.configure(state="normal")
        self.custom_topic_entry.delete(0, "end")

        self.summary_textbox.configure(state="normal")
        self.summary_textbox.delete("1.0", "end")

        if choice == self.custom_option_text:
            self.custom_topic_entry.focus()
        else:
            self.custom_topic_entry.insert(0, choice)

            sync_topics = self.gui_state.get_state(StateKey.SYNC_TOPICS) or []
            ai_summary = next((t.get('summary', '') for t in sync_topics if t.get('title') == choice), "")

            self.summary_textbox.insert("1.0", ai_summary, "right_align")

    def _clear_error_state(self, event, widget):
        widget.configure(border_color=self.default_border)

        if self.error_label.cget("text"):
            self.show_message("", "red")

    def handle_create_room(self):
        validations = [
            self.room_name_entry.check_validity(),
            self.custom_topic_entry.check_validity()
        ]

        if not all(validations):
            self.show_message(".שגיאה: חסרים שדות חובה", "red")
            return

        room_name = self.room_name_entry.get().strip()
        topic = self.custom_topic_entry.get().strip()
        room_summary = self.summary_textbox.get("1.0", "end").strip()
        is_public = (self.privacy_toggle.get() == "ציבורי (פתוח לכולם)")

        payload = {
            Contract.CATEGORY: topic,
            Contract.DISPLAY_NAME: room_name,
            Contract.IS_OPEN: 0 if is_public else 1,
            Contract.SUMMARY: room_summary
        }

        self.show_message("")
        self.chat_service.create_room(payload)

    def release_create_btn(self, state):
        self.create_btn.configure(state=state)

    def show_message(self, text, color='gray14'):
        self.error_label.configure(text=text, text_color=color)

    def _clear_fields(self):
        self.room_name_entry.delete(0, 'end')
        self.topic_dropdown.set(self.custom_option_text)
        self._on_topic_selection_changed(self.custom_option_text)

class DiscoveryBase(BaseScreen):
    def __init__(self, parent, gui_state, chat_service, fetch_callback):
        super().__init__(parent, fg_color="transparent")
        self.gui_state = gui_state
        self.chat_service = chat_service
        self.fetch_callback = fetch_callback
        self.all_cards = []
        self.initial_load_done = False
        self.categories = ["הכל", "ביטחון", "מדיני", "חברה", "כלכלה", "חינוך"]
        self.end_of_data_map = {cat: False for cat in self.categories}

        self.filter_menu = ctk.CTkSegmentedButton(self, values=self.categories, command=self.filter_cards)
        self.filter_menu.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 5))
        self.filter_menu.set("הכל")

        self.scrollable_area = ScrollScreen(
            self, self.gui_state, on_bottom_reach=self.load_more_data,
            fg_color="transparent", corner_radius=0
        )

    def add_card(self, id=None, title=None, summary=None, url=None, category=None, on_top=False, **kwargs):

        filter_val = self.filter_menu.get() if self.filter_menu else "הכל"
        should_show = (filter_val == "הכל" or category == filter_val)

        new_card = TopicCard(
            self.scrollable_area, title=title, summary=summary,
            category=category, url=url, id=id, **kwargs
        )

        if on_top and self.all_cards:
            if should_show:
                new_card.pack(before=self.all_cards[0], fill="x", padx=5, pady=5)
            self.all_cards.insert(0, new_card)
        else:
            if should_show:
                new_card.pack(fill="x", padx=5, pady=5)
            self.all_cards.append(new_card)

    def finalize_load(self):
        if not self.initial_load_done:
            self.initial_load_done = True
        self.release_scroll_lock()

    def filter_cards(self, selected_category):
        for card in self.all_cards:
            card.pack_forget()

        self.release_scroll_lock()

        cards_in_cat = [c for c in self.all_cards if selected_category == "הכל" or c.category == selected_category]


        is_finished = self.end_of_data_map.get(selected_category, False)

        is_loading = self.scrollable_area._is_loading

        if not cards_in_cat and not is_finished and not is_loading:
            self.load_more_data()

        for card in cards_in_cat:
            card.pack(pady=10, padx=10, fill="x")

        self.scrollable_area._parent_canvas.yview_moveto(0.0)

    def on_show(self):
        if not self.initial_load_done and not self.scrollable_area._is_loading:
            self.load_more_data()

    def load_more_data(self):

        current_filter = self.filter_menu.get() if self.filter_menu else "הכל"

        if self.end_of_data_map.get(current_filter, False):
            return

        self.scrollable_area._is_loading = True

        if current_filter == "הכל":
            valid_ids = [card.id for card in self.all_cards if card.id is not None]
        else:
            valid_ids = [card.id for card in self.all_cards if card.id is not None and card.category == current_filter]

        oldest_id = min(valid_ids) if valid_ids else None

        category_to_fetch = None if current_filter == "הכל" else current_filter

        if self.fetch_callback:
            self.fetch_callback(oldest_id, category_to_fetch)

    def release_scroll_lock(self):
        self.scrollable_area.reset_loading_state()

    def update_category_status(self, category, is_end):
        if is_end:
            if category is None or category == 'הכל':
                for card in self.end_of_data_map:
                    self.end_of_data_map[card] = True

            elif category in self.end_of_data_map:
                self.end_of_data_map[category] = is_end

class JoinScreen(DiscoveryBase):
    def __init__(self, parent, gui_state, chat_service):
        super().__init__(parent, gui_state, chat_service, chat_service.fetch_older_groups)
        self.is_waiting = False

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_ui()
        self.gui_state.register(StateKey.RELEASE_BTNS, self._release_btn)
        self.gui_state.register(StateKey.ROLE, self._update_role_view)

    def setup_ui(self):
        # 1. Action Bar (החלק העליון)
        self.actions_container = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))

        # הצטרפות עם קוד
        self.code_frame = ctk.CTkFrame(self.actions_container, fg_color="transparent")
        self.code_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(self.code_frame, text=":הצטרפות לקבוצה סגורה באמצעות קוד", font=("Heebo", 14, "bold"),
                     text_color="white").pack(side="right", padx=10)
        self.code_entry = ctk.CTkEntry(self.code_frame, placeholder_text=":הזן קוד", width=150, font=("Heebo", 13),
                                       height=32)
        self.code_entry.pack(side="right", padx=5)
        self.join_code_btn = ctk.CTkButton(self.code_frame, text="הצטרף", font=("Heebo", 13, "bold"),
                                           fg_color="#f59e0b", hover_color="#d97706", width=80, height=32,
                                           command=self.submit_invite_code)
        self.join_code_btn.pack(side="right", padx=5)

        # הצטרפות אקראית
        self.random_join_frame = ctk.CTkFrame(self.actions_container, fg_color="transparent")
        ctk.CTkLabel(self.random_join_frame, text=":או קפוץ לדיון אקראי בנושא", font=("Heebo", 14, "bold"),
                     text_color="white").pack(side="right", padx=10)
        self.category_dropdown = ctk.CTkOptionMenu(self.random_join_frame, values=self.categories, font=("Heebo", 13),
                                                   height=32)
        self.category_dropdown.pack(side="right", padx=5)
        self.random_join_btn = ctk.CTkButton(self.random_join_frame, text="הצטרף אקראית 🎲", font=("Heebo", 13, "bold"),
                                             width=120, height=32, fg_color="#10b981", hover_color="#059669",
                                             command=self.submit_random_join)
        self.random_join_btn.pack(side="right", padx=5)

        self.scrollable_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))

    def _update_role_view(self, role):
        if role == UserRole.STANDARD:
            self.random_join_frame.pack(fill="x", pady=(10, 0))
        else:
            self.random_join_frame.pack_forget()

    def _release_btn(self, new_state):
        self.join_code_btn.configure(state=new_state)
        self.random_join_btn.configure(state=new_state)

    def submit_invite_code(self):
        code = self.code_entry.get().strip()
        if code:
            self.code_entry.delete(0, 'end')
            self.chat_service.join_room(invite_code=code)

    def submit_random_join(self):
        category = self.category_dropdown.get()
        payload = {Contract.CATEGORY: None if category == "הכל" else category}
        self.chat_service.join_room(payload)

class TopicTemplateScreen(DiscoveryBase):
    def __init__(self, parent, gui_state, chat_service, on_create_callback=None):
        super().__init__(parent, gui_state, chat_service,chat_service.fetch_older_topics)
        self.on_create_callback = on_create_callback

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_ui()

    def setup_ui(self):
        self.actions_container = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))

        self.create_btn = ctk.CTkButton(
            self.actions_container,
            text="צור קבוצה חדשה מאפס ➕",
            font=("Heebo", 16, "bold"),
            fg_color="#D4AF37",
            hover_color="#B0903D",
            text_color="black",
            height=40,
            command=self.on_create_callback if self.on_create_callback else lambda: None
        )
        self.create_btn.pack(fill='x', padx=10)

        # 3. רשימת התבניות/חדרים (מגיעה מהבסיס)
        self.scrollable_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))

class UserDetailsScreen(BaseScreen):
    def __init__(self, parent, gui_state, chat_service):
        super().__init__(parent,
                         fg_color= ("#FFE5CC", "#0D1117"),
                         bg_color='transparent',
                         corner_radius=20,
                         border_width=2,
                         border_color='#B0903D',
                         width=400,
                         height=650)

        self.gui_state = gui_state
        self.chat_service = chat_service


        self.pack_propagate(False)

        self.info_container = ctk.CTkFrame(self, fg_color="transparent")
        self.field_labels = {}

        fields = [
            ("שם תצוגה", StateKey.DISPLAY_NAME, "🆔"),
            ("אמצעי זיהוי", StateKey.IDENTITY, "👤"),
            ("סטטוס", StateKey.ROLE, "🛡"),
            ("מפתח ציבורי", StateKey.PUBLIC_ID, "🔑"),
            ("אימייל", StateKey.EMAIL, "📧"),
            ('רמת ההרשאה', StateKey.IS_ADMIN, "👔"),
        ]
        self.gui_state.register(StateKey.LOGGED_IN, self.refresh_data)

        self.upload_btn = ctk.CTkButton(self,
                                        text="ניהול מורשים מתקדם (אקסל) 🛡️",
                                        text_color="#0D1117",
                                        fg_color='#B0903D',
                                        hover_color="#C5A452",
                                        font=("Heebo", 14, "bold"),
                                        height=40,
                                        command=self._import_users_via_win32)

        self.action_btn = ctk.CTkButton(self,
                                        text="התנתק מהמערכת",
                                        text_color = "#B0903D",
                                        fg_color='transparent',
                                        hover_color="#C0392B",
                                        border_width=2,
                                        border_color='#B0903D',
                                        cursor= 'hand2',
                                        font=("Heebo", 14, "bold"),
                                        height=40,
                                        corner_radius=8)

        self._build_header()

        self.action_btn.pack(fill="x", padx=30, pady=10)

        self.info_container.pack(fill="both", expand=True, padx=30, pady=(10, 10))

        for label, key_name, icon in fields:
            self._add_row(label, key_name, icon)

    def _build_header(self):
        avatar_frame = ctk.CTkFrame(self, fg_color="transparent")
        avatar_frame.pack(pady=(15, 5))

        self.avatar_size = (120, 120)

        self.avatar_image_label = ctk.CTkFrame(
            avatar_frame,
            width=self.avatar_size[0],
            height=self.avatar_size[1],
            corner_radius=60,
            border_width=2,
            border_color='#B0903D',
            fg_color= 'transparent'
        )
        self.avatar_image_label.pack()

        icon_label = ctk.CTkLabel(self.avatar_image_label, text="👤", font=("Arial", 60), text_color = ("#0D1117", "#FFE5CC"))
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        self.title_label = ctk.CTkLabel(self,
                                        text="פרופיל משתמש",
                                        font=("Heebo", 30, "bold"),
                                        text_color="#B0903D")
        self.title_label.pack(pady=(0, 10))

    def _add_row(self, label, key_name, icon):
        row = ctk.CTkFrame(self.info_container, fg_color="transparent")
        row.pack(fill="x", pady=5)

        ctk.CTkLabel(row, text=f" :{label} {icon}", font=("Heebo", 20, "bold"),
                     text_color='#B0903D').pack(anchor='e')

        value_label = ctk.CTkLabel(row, text="", font=("Heebo", 18, 'bold'), text_color=('black', 'white'))
        value_label.pack(anchor='w')

        self.field_labels[key_name] = value_label

        line = ctk.CTkFrame(self.info_container, fg_color="#B0903D", height=2)
        line.pack(fill="x", pady=(2, 5))


    def refresh_data(self, val=None):
        if not val:
            return
        for key_name, label_widget in self.field_labels.items():
            new_value = str(self.gui_state.get_state(key_name) or "לא זמין")
            current_value = label_widget.cget("text")
            if current_value != new_value:
                label_widget.configure(text=new_value)

        if self.gui_state.get_state(StateKey.IS_ADMIN) == 'בכיר':
            self.upload_btn.pack(fill="x", padx=30, pady=(10, 0), before=self.action_btn)
        else:
            self.upload_btn.pack_forget()

    def _import_users_via_win32(self):
        file_path = filedialog.askopenfilename(
            title="בחר קובץ אקסל של מורשים",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if not file_path:
            return

        def parse_excel():
            pythoncom.CoInitialize()
            try:
                excel = win32com.client.Dispatch("Excel.Application")
                excel.Visible = False

                wb = excel.Workbooks.Open(os.path.abspath(file_path))
                ws = wb.Sheets(1)

                users_to_add = []
                row = 2  

                while ws.Cells(row, 1).Value is not None:
                    identity = str(ws.Cells(row, 1).Value).strip()
                    if identity.endswith('.0'): identity = identity[:-2]

                    role = str(ws.Cells(row, 2).Value).strip()
                    name = str(ws.Cells(row, 3).Value).strip()

                    users_to_add.append({
                        Contract.IDENTITY: identity,
                        Contract.ROLE: role,
                        Contract.FULL_NAME: name
                    })
                    row += 1

                wb.Close(False)
                excel.Quit()

                if users_to_add:
                    payload = {Contract.ITEMS: users_to_add}
                    self.chat_service.dispatcher.send_msg(MsgType.AUTH_UPLOAD, payload)
                    print(f"[Win32] Successfully parsed and sent {len(users_to_add)} users.")

            except Exception as e:
                print(f"[Win32 Error] Failed to parse Excel: {e}")
            finally:
                pythoncom.CoUninitialize()

        threading.Thread(target=parse_excel, daemon=True).start()
