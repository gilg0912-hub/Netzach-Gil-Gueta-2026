import customtkinter

# --- 1. הגדרת מאגר העיצובים ---
THEMES = {
    "Ocean Blue": {
        "fg_color": "#1F6AA5",
        "hover_color": "#144870",
        "text_color": "white"
    },
    "Forest Green": {
        "fg_color": "#2D5A27",
        "hover_color": "#1E3D1A",
        "text_color": "#E0E0E0"
    },
    "Cyberpunk": {
        "fg_color": "#FF00FF",
        "hover_color": "#BC00BC",
        "text_color": "black"
    },
    "Dark Mode": {
        "fg_color": "#3D3D3D",
        "hover_color": "#2B2B2B",
        "text_color": "white"
    }
}

# רשימה גלובלית שתחזיק את כל הווידג'טים שצריכים להתעדכן
all_dynamic_widgets = []


# --- 2. יצירת רכיבים "חכמים" ---
class MyButton(customtkinter.CTkButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        all_dynamic_widgets.append(self)

    def destroy(self):
        if self in all_dynamic_widgets:
            all_dynamic_widgets.remove(self)
        super().destroy()


# --- 3. פונקציית העדכון הגלובלית ---
def change_system_theme(theme_name):
    if theme_name in THEMES:
        style = THEMES[theme_name]
        for widget in all_dynamic_widgets:
            try:
                widget.configure(
                    fg_color=style["fg_color"],
                    hover_color=style["hover_color"],
                    text_color=style["text_color"]
                )
            except Exception:
                pass


# --- 4. בניית הממשק ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Global Theme Switcher")
        self.geometry("400x300")

        self.grid_columnconfigure(0, weight=1)

        # כותרת
        self.label = customtkinter.CTkLabel(self, text="בחר עיצוב למערכת:", font=("Arial", 16, "bold"))
        self.label.pack(pady=20)

        # תפריט בחירה (OptionMenu)
        self.theme_menu = customtkinter.CTkOptionMenu(
            self,
            values=list(THEMES.keys()),
            command=change_system_theme  # הפונקציה שנקראת בכל שינוי
        )
        self.theme_menu.pack(pady=10)

        # יצירת כמה כפתורים לדוגמה (שים לב שמשתמשים ב-MyButton)
        self.btn1 = MyButton(self, text="כפתור אישור")
        self.btn1.pack(pady=10)

        self.btn2 = MyButton(self, text="ביטול")
        self.btn2.pack(pady=10)

        self.btn3 = MyButton(self, text="הגדרות נוספות")
        self.btn3.pack(pady=10)

        # הגדרת עיצוב ראשוני
        self.theme_menu.set("Ocean Blue")
        change_system_theme("Ocean Blue")


if __name__ == "__main__":
    app = App()
    app.mainloop()