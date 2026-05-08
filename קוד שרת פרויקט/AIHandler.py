import sqlite3
import threading

from google import genai
from google.genai import types

from Protocol import UserRole
from RESOURCES import *
import json
import re
class AIHandler:

    def __init__(self, db, api_key):
        self.db = db
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'
        self.topics_lock = threading.Lock()
        self.current_topics = {}

    def get_topics_for_role(self, role):
        with self.topics_lock:
            return self.current_topics.get(role, [])

    def build_prompt(self, role):
        if role == UserRole.STUDENT:
            sources = STUDENT_SOURCES
        else:
            sources = STANDARD_SOURCES

        categories = list(sources.keys())

        all_urls = set()
        for urls in sources.values():
            all_urls.update(urls)

        return f"""
                    TASK: Extract 10 most trending news topics from the last 24 hours in Israel.
                    SOURCE DATA: Use the following categories and their respective fields: {categories}.
                    
                    SOURCE REPOSITORIES:
                    {all_urls}
            
                    STRICT RULES:
                    - Each topic must be categorized under one of these labels: {categories}.
                    - Each title must be between 3 to 5 words exactly.
                    - Focus ONLY on Israeli-related news from May 2026.
                    - Language: Hebrew.
                    - No introductory text or conversational filler.

                    FORMAT: Return ONLY a valid JSON list of objects.

                    EXPECTED OUTPUT EXAMPLE:
                    [
                      {{"category": "ביטחון", "title": "הגברת הכוננות בגבול הצפון"}},
                      {{"category": "כלכלה", "title": "עלייה במדד המחירים לצרכן"}},
                      {{"category": "חינוך", "title": "רפורמה חדשה במבחני הבגרות"}}
                    ]
            """

    def fetch_trending_topics(self, role):
        prompt = self.build_prompt(role)
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )

            clean_text = re.sub(r'```json | ```', '', response.text).strip()
            return json.loads(clean_text)
        except Exception as e:
            print(f"Error fetching AI topics: {e}")
            return []

    def update_topics_for_role(self, role, db_path=r"C:\Users\User\Documents\לימודים\neatzach_zionizm_project.sqbpro"):
        trending_topics = self.fetch_trending_topics(role)

        if not trending_topics or len(trending_topics) < 2:
            print(f"Update failed for {role}: Not enough topics found.")
            return False

        try:
            self.db.update_topics(topics=trending_topics)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()


            cursor.execute("DELETE FROM HotTopics WHERE role_type = ?", (role,))


            query = """
                INSERT INTO HotTopics (sub_category, title, role_type, date_added) 
                VALUES (?, ?, ?, datetime('now'))
            """

            for item in trending_topics:
                # שליפת הנתונים מהדיקט שה-AI החזיר
                sub_category = item.get("category", "כללי")
                title = item.get("title", "אין כותרת")

                # הרצת השאילתה עם הפרדה מלאה
                cursor.execute(query, (sub_category, title, role))
            conn.commit()
            conn.close()
            print(f"Database updated successfully for {role}!")
            return True

        except Exception as e:
            print(f"SQL Error: {e}")
            return False

