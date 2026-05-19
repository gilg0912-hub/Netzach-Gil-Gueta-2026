import customtkinter as ctk
from app_constants import StateKey
from PIL import Image

class UserDetailsOverlay(ctk.CTkFrame):
    def __init__(self, parent, gui_state):
        super().__init__(parent,
                         fg_color= ("#FFE5CC", "#0D1117"),
                         bg_color='transparent',
                         corner_radius=20,
                         border_width=2,
                         border_color='#B0903D',
                         width=400,
                         height=650)

        self.gui_state = gui_state
        self.pack_propagate(False)

        self.info_container = ctk.CTkFrame(self, fg_color="transparent")
        self.field_labels = {}

        fields = [
            ("שם תצוגה", StateKey.DISPLAY_NAME, "🆔"),
            ("אמצעי זיהוי", StateKey.IDENTITY, "👤"),
            ("סטטוס", StateKey.ROLE, "🛡"),
            ("מפתח ציבורי", StateKey.PUBLIC_ID, "🔑"),
            ("אימייל", StateKey.EMAIL, "📧")
        ]
        self.gui_state.register(StateKey.LOGGED_IN, self.refresh_data)

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
        avatar_frame.pack(pady=(20, 10))

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
        self.avatar_image_label.pack(pady=(5, 10))

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