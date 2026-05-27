import customtkinter as ctk


# ==========================================
# Mocks & Dependencies (אובייקטים מדומים להרצה)
# ==========================================

class Contract:
    CATEGORY = "category"
    DISPLAY_NAME = "display_name"
    IS_OPEN = "is_open"
    SUMMARY = "summary"


class StateKey:
    SYNC_TOPICS = "sync_topics"
    RELEASE_BTNS = "release_btns"


class MockGuiState:
    def __init__(self):
        self._state = {
            StateKey.SYNC_TOPICS: [
                {"title": "מבצע יונתן", "summary": "סיפור הגבורה של שחרור החטופים באנטבה."},
                {"title": "מבוא לפייתון", "summary": "עקרונות בסיסיים בתכנות מונחה עצמים."},
                {"title": "המהפכה התעשייתית", "summary": "כיצד הטכנולוגיה שינתה את פני החברה במאה ה-19."}
            ]
        }

    def get_state(self, key):
        return self._state.get(key)

    def register(self, key, callback):
        pass  # מדמה רישום לאירועים


class MockChatService:
    def create_room(self, payload):
        print("\n--- Sending to Server ---")
        for k, v in payload.items():
            print(f"{k}: {v}")
        print("-------------------------\n")


class RequiredEntry(ctk.CTkEntry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_border = self.cget("border_color")
        self.bind("<KeyRelease>", self._clear_error)

    def check_validity(self):
        if not self.get().strip():
            self.configure(border_color="red")
            return False
        self.configure(border_color=self.default_border)
        return True

    def _clear_error(self, event):
        self.configure(border_color=self.default_border)


# ==========================================
# הממשק המקורי שלך
# ==========================================

class CreateScreen(ctk.CTkFrame):
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
            self.show_message("", "transparent")

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
            Contract.IS_OPEN: is_public,
            Contract.SUMMARY: room_summary
        }

        self.show_message("", "transparent")
        self.chat_service.create_room(payload)

    def release_create_btn(self, state):
        self.create_btn.configure(state=state)

    def show_message(self, text, color):
        self.error_label.configure(text=text, text_color=color)

    def _clear_fields(self):
        self.room_name_entry.delete(0, 'end')
        self.topic_dropdown.set(self.custom_option_text)
        self._on_topic_selection_changed(self.custom_option_text)


# ==========================================
# קוד ההרצה (TopLevel Wrapper)
# ==========================================
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Netzach - Create Room Tester")
    app.geometry("600x750")

    # מיקום חלון באמצע המסך
    app.eval('tk::PlaceWindow . center')

    gui_state_mock = MockGuiState()
    chat_service_mock = MockChatService()

    # יצירת מופע של המסך שלך והצגתו
    main_screen = CreateScreen(app, gui_state_mock, chat_service_mock)
    main_screen.pack(fill="both", expand=True, padx=20, pady=20)

    app.mainloop()