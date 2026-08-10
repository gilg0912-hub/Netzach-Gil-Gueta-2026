import threading
import json
import re
from google import genai
from google.genai import types
from Protocol import UserRole
from RESOURCES import *


class AIHandler:
    def __init__(self, db, api_key):
        self.db = db
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash'
        self.topics_lock = threading.Lock()

        self.allowed_categories = ["ביטחון", "חינוך", "כלכלה", "כללי", "פוליטי"]
        self.current_topics = {}
        for role in [UserRole.STANDARD, UserRole.TEACHER]:
            self.current_topics[role] = self.db.get_topics_paged(role, limit=15)
            print(self.current_topics[role])

    def get_topics_for_role(self, role):
        with self.topics_lock:
            return self.current_topics.get(role, [])

    def build_prompt(self):
        categories_str = ", ".join(self.allowed_categories)

        # יצירת מחרוזת המקורות המאושרים מתוך הרשימות שיובאו
        sources_context = f"""
        APPROVED SOURCES PER ROLE:
        - TEACHERS: {', '.join(TEACHER_SOURCES)}
        - STANDARD: {', '.join(STANDARD_SOURCES)}
        """

        return f"""
        Act as a professional news analyst and data engineer for an Israeli educational platform.

        {sources_context}

        IMPORTANT: Return ONLY the JSON object. Do not include any analysis, introductory text, or markdown code blocks like ```json. 
        Just start with '{{' and end with '}}'.

        Your task: Identify 5 trending news topics in Israel for each role (TEACHERS, STANDARD), based STRICTLY on the approved sources.

        OUTPUT FORMAT:
        Return ONLY a valid JSON object. No markdown tags.
        Structure: {{"TEACHERS": [...], "STANDARD": [...]}}
        Each topic object MUST contain EXACTLY these keys: "title", "summary", "url", "category".

        CATEGORY CONSTRAINT:
        You MUST classify each topic into EXACTLY one of these categories: {categories_str}.

        CRITICAL CONSTRAINTS:
        - All visible Hebrew text must be grammatically perfect and formal.
        - Ensure the URL is a direct link to the article from the approved sources.
        """

    def fetch_trending_topics(self):
        prompt = self.build_prompt()
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )

            raw_text = response.text

            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}

        except Exception as e:
            print(f"[AI-Handler] Error during fetch: {e}")
            return {}

    def update_all_topics(self):
        all_data = self.fetch_trending_topics()
        if not all_data:
            return False

        for role_name, topics in all_data.items():
            if not isinstance(topics, list):
                continue

            success = self.db.save_hot_topics(topics, role_name)

            if success:
                with self.topics_lock:
                    self.current_topics[role_name] = topics

        print(f"Update completed for: {', '.join(all_data.keys())}")
        return True

