import customtkinter
import webbrowser

# הגדרות עיצוב כלליות לאפליקציה (Dark Mode מודרני)
customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")


class TopicCard(customtkinter.CTkFrame):

    def __init__(self, master, title, summary, url, topic_id, join_callback, **kwargs):
        super().__init__(master, corner_radius=15, fg_color="#1e293b", border_width=1, border_color="#334155", **kwargs)

        self.url = url
        self.topic_id = topic_id

        self.title_label = customtkinter.CTkLabel(
            self, text=title, font=("Heebo", 18, "bold"),
            text_color="#f8fafc", wraplength=300, justify="right"
        )
        self.title_label.pack(pady=(15, 5), padx=15, anchor="e")

        self.summary_label = customtkinter.CTkLabel(
            self, text=summary, font=("Heebo", 14),
            text_color="#cbd5e1", wraplength=300, justify="right"
        )
        self.summary_label.pack(pady=5, padx=15, anchor="e")

        self.link_btn = customtkinter.CTkButton(
            self, text="קרא עוד באתר המקור...", font=("Heebo", 12, "underline"),
            fg_color="transparent", text_color="#38bdf8", hover_color="#334155",
            cursor="hand2", height=20, command=self.open_link
        )
        self.link_btn.pack(pady=5, padx=10, anchor="w")

        self.join_btn = customtkinter.CTkButton(
            self, text="הצטרף לשיח", font=("Heebo", 14, "bold"),
            fg_color="#f59e0b", hover_color="#d97706", text_color="white",
            corner_radius=8, command=lambda: join_callback(self.topic_id)
        )
        self.join_btn.pack(pady=(10, 15), padx=15, fill="x")

    def open_link(self):
        if self.url:
            webbrowser.open_new_tab(self.url)


class App(customtkinter.CTk):
    """
    מחלקת האפליקציה הראשית
    """

    def __init__(self):
        super().__init__()

        self.title("נצ\"ח - נושאים חמים")
        self.geometry("450x650")

        # כותרת ראשית במסך
        self.header = customtkinter.CTkLabel(
            self, text="אקטואליה בזמן אמת", font=("Heebo", 24, "bold"), text_color="#f59e0b"
        )
        self.header.pack(pady=(20, 10))

        # יצירת פאנל גלילה עבור הכרטיסיות
        self.scrollable_frame = customtkinter.CTkScrollableFrame(
            self, fg_color="transparent", scrollbar_button_color="#475569"
        )
        self.scrollable_frame.pack(padx=20, pady=10, fill="both", expand=True)

        # רשימת נתונים לדוגמה (סימולציה של JSON שמגיע מהשרת דרך Gemini)
        mock_topics = [
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 101,
                "title": "חוק הגיוס: מתווה חדש על השולחן",
                "summary": "דיון סביב ההצעה החדשה לשילוב חרדים בצה\"ל ובשירות הלאומי. מהן ההשלכות על החברה הישראלית?",
                "url": "https://www.ynet.co.il"
            },
            {
                "id": 102,
                "title": "היערכות העורף להסלמה בצפון",
                "summary": "הנחיות פיקוד העורף המעודכנות ודיון על החוסן האזרחי ביישובי קו העימות אל מול האיום הגובר.",
                "url": "https://www.mako.co.il"
            },
            {
                "id": 103,
                "title": "שילוב בינה מלאכותית במערכת החינוך",
                "summary": "האם טכנולוגיות AI יעצימו את התלמידים או יפגעו ביכולות הלמידה העצמאיות? דיון פדגוגי.",
                "url": "https://www.haaretz.co.il"
            }
        ]

        # ייצור הכרטיסיות בלולאה והכנסתן לפאנל הגלילה
        for topic in mock_topics:
            card = TopicCard(
                master=self.scrollable_frame,
                title=topic["title"],
                summary=topic["summary"],
                url=topic["url"],
                topic_id=topic["id"],
                join_callback=self.handle_join_chat
            )
            # pack מוסיף את הכרטיסייה לפריים. fill="x" גורם לה להתרחב לרוחב המסך
            card.pack(pady=10, fill="x", padx=5)

    def handle_join_chat(self, topic_id):
        """
        פונקציית CallBack שתופעל כשמשתמש לוחץ 'הצטרף לשיח'
        כאן תכניס את הלוגיקה של שליחת JSON לשרת דרך ה-Socket
        """
        print(f"[Client] Sending JSON to Server: Requesting to join room ID {topic_id}")
        # דוגמה לחיווי למשתמש:
        # self.status_label.configure(text=f"מתחבר לחדר {topic_id}...")


if __name__ == "__main__":
    app = App()
    app.mainloop()