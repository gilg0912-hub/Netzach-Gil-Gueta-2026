import customtkinter as ctk
from app_constants import StateKey
from PIL import Image

class CreateConnectionWindow(ctk.CTkToplevel):
    def __init__(self, root, on_submit_callback):
        super().__init__(root)

        self.title("נצ\"ח - יצירת קשר חדש")
        self.geometry("400x320")
        self.resizable(False, False)
        self.on_submit_callback = on_submit_callback

        self.configure(fg_color='#0A2140')
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.transient(root)
        self.grab_set()

        self._center_window(root)

        # --- כותרת ---
        self.label = ctk.CTkLabel(
            self,
            text="התחלת שיחה חדשה",
            font=("Heebo", 20, "bold"),
            text_color="#B0903D"
        )
        self.label.pack(pady=(25, 10))

        # --- הסבר קצר ---
        self.sub_label = ctk.CTkLabel(
            self,
            text=":בחר את סוג הזיהוי והכנס את הפרטים",
            font=("Heebo", 12),
            text_color="white"
        )
        self.sub_label.pack(pady=(0, 15))

        # --- בורר מצבים (Segmented Button) ---
        self.type_var = ctk.StringVar(value="Public ID")
        self.segments = ctk.CTkSegmentedButton(
            self,
            values=["Public ID", "Topic"],
            command=self._update_placeholder,
            fg_color='#1A242F',
            variable=self.type_var,
            border_width=1,
            selected_color="#B0903D",
            unselected_color="#1A242F",
            font=("Heebo", 13, "bold"),
            selected_hover_color="#B0903D",
            unselected_hover_color="#1A242F",
            corner_radius=8,
        )
        self.segments.pack(pady=10, padx=40, fill="x")

        # --- שדה קלט (Entry) ---
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="...הזן מפתח ציבורי",
            height=45,
            fg_color="#051224",
            border_color="#B0903D",
            font=("Heebo", 14),
            justify="center"
        )
        self.entry.pack(pady=25, padx=40, fill="x")
        self.entry.bind("<Return>", lambda e: self._handle_submit())  # תמיכה במקש Enter

        # --- כפתור אישור ---
        self.submit_btn = ctk.CTkButton(
            self,
            text="צור קשר",
            font=("Heebo", 15, "bold"),
            command=self._handle_submit,
            fg_color="#B0903D",
            hover_color="#8C7230",
            text_color="#0A2140",
            height=40
        )
        self.submit_btn.pack(pady=(10, 20))

    def _center_window(self, root):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()

        x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
        y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)

        self.geometry(f"+{int(x)}+{int(y)}")

    def _update_placeholder(self, selected_type):
        if selected_type == "Public ID":
            self.entry.configure(placeholder_text="...הזן מפתח ציבורי")
        else:
            self.entry.configure(placeholder_text="...הזן שם נושא")

    def _handle_submit(self):
        value = self.entry.get().strip()
        if not value:
            self.entry.configure(border_color="red")
            self.after(1000, lambda: self.entry.configure(border_color="#B0903D"))
            return

        selected_type = self.type_var.get()
        self.on_submit_callback(selected_type, value)
        self.destroy()

    def _on_close(self):
        self.grab_release()
        self.destroy()


class UserDetailsOverlay(ctk.CTkFrame):
    def __init__(self, parent, gui_state, close_callback):
        super().__init__(parent,
                         fg_color='#0D131A',
                         bg_color='#051224',
                         corner_radius=5,
                         border_width=2,
                         border_color='#B0903D',
                         width=400,
                         height=520)

        self.gui_state = gui_state
        self.close_callback = close_callback
        self.pack_propagate(False)

        # --- כפתור סגירה ---
        self.close_btn = ctk.CTkButton(self,
                                       text="✕",
                                       width=30,
                                       height=30,
                                       fg_color="transparent",
                                       hover_color="#1A242F",
                                       text_color="white",
                                       command=self.close_callback)
        self.close_btn.place(x=10, y=10)

        self.info_container = ctk.CTkFrame(self, fg_color="transparent")
        self.field_labels = {}

        fields = [
            ("שם מלא", StateKey.DISPLAY_NAME, "🆔"),
            ("סטטוס", StateKey.ROLE, "🛡"),
            ("מפתח ציבורי", StateKey.PUBLIC_ID, "🔑"),
            ("אימייל", StateKey.GMAIL, "📧")
        ]

        self.action_btn = ctk.CTkButton(self,
                                        text="התנתק מהמערכת",
                                        fg_color="#E74C3C",
                                        hover_color="#C0392B",
                                        font=("Heebo", 14, "bold"),
                                        height=40,
                                        corner_radius=8)

        self._build_header()

        self.action_btn.pack(fill="x", padx=30, pady=10)

        self.info_container.pack(fill="both", expand=True, padx=30, pady=(10, 10))

        for label, key_name, icon in fields:
            self._add_row(label, key_name, icon)

    def _build_header(self):
        self.avatar_label = ctk.CTkLabel(self, text="👤", font=("Arial", 60))
        self.avatar_label.pack(pady=(10, 20))

        self.title_label = ctk.CTkLabel(self,
                                        text="פרופיל משתמש",
                                        font=("Heebo", 22, "bold"),
                                        text_color="#B0903D")
        self.title_label.pack(pady=(0, 10))

    def _add_row(self, label, key_name, icon):
        row = ctk.CTkFrame(self.info_container, fg_color="transparent")
        row.pack(fill="x", pady=5)

        ctk.CTkLabel(row, text=f" :{label} {icon}", font=("Heebo", 14, "bold"),
                     text_color="#B0903D").pack(anchor='e')

        value_label = ctk.CTkLabel(row, text="", font=("Heebo", 14), text_color="white")
        value_label.pack(anchor='w')

        self.field_labels[key_name] = value_label

        line = ctk.CTkFrame(self.info_container, fg_color="#B0903D", height=2)
        line.pack(fill="x", pady=(2, 5))

    def refresh_data(self):
        for key_name, label_widget in self.field_labels.items():
            new_value = self.gui_state.get_state(key_name) or "לא זמין"
            label_widget.configure(text=str(new_value))


def load_ui_image(file_name, size=(1200, 900)):
    try:



        # 1. פתיחת התמונה המקורית בעזרת PIL
        pil_image = Image.open(file_name)

        # 2. המרה ל-CTkImage המתאים ל-Dark/Light mode
        ctk_image = ctk.CTkImage(
            light_image=pil_image,
            dark_image=pil_image,
            size=size  # גודל ראשוני
        )

        return ctk_image
    except Exception as e:
        print(f"Could not load image: {e}")
        return

def resize_image(event, ctk_img):
    ctk_img.configure(size= (event.width, event.height))