import customtkinter as ctk
from ui_components import TopicCard, RequiredEntry
import time
import datetime

from app_constants import StateKey, Contract, UserRole

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


class CreateScreen(ctk.CTkFrame):
    def __init__(self, parent, gui_state, chat_service, on_create_callback=None):
        super().__init__(parent, fg_color="transparent")
        self.gui_state = gui_state
        self.chat_service = chat_service

        self.all_topic_cards = []
        self.all_topics_downloaded = False
        self.is_waiting = False

        self.grid_rowconfigure(0, weight=0)  # אזור פעולה עליון
        self.grid_rowconfigure(1, weight=0)  # תפריט סינון קטגוריות
        self.grid_rowconfigure(2, weight=0)  # קו הפרדה
        self.grid_rowconfigure(3, weight=1)  # אזור נגלל
        self.grid_columnconfigure(0, weight=1)

        self.create_general_btn = ctk.CTkFrame(self, fg_color="transparent")
        self.create_blank_btn = ctk.CTkButton(
            self.create_general_btn,
            text="צור קבוצה חדשה מאפס ➕",
            font=("Heebo", 14, "bold"),
            fg_color="#D4AF37",
            hover_color="#B0903D",
            text_color="black",
            height=36,
        )

        if on_create_callback:
            self.create_blank_btn.configure(command=on_create_callback)
        self.create_blank_btn.pack(fill='x', padx=10)

        self.filter_menu = ctk.CTkSegmentedButton(
            self,
            fg_color=("#E9EDF3", "#151C2B"),
            selected_color=("#2F80ED", "#2F80ED"),
            selected_hover_color=("#256FD1", "#256FD1"),
            unselected_color=("#E9EDF3", "#151C2B"),
            unselected_hover_color=("#DCEBFF", "#1F2A44"),
            text_color=("#4B5563", "#D1D5DB"),
            text_color_disabled=("#9CA3AF", "#6B7280"),
            values=["הכל", "ביטחון", "מדיני", "חברה", "כלכלה", "חינוך"],
            command=self.filter_topics
        )
        self.filter_menu.grid(row=1, column=0, sticky="ew", padx=20, pady=(5, 5))
        self.filter_menu.set("הכל")

        self.divider = ctk.CTkFrame(self, fg_color="#30363D", height=2)
        self.divider.grid(row=2, column=0, sticky="ew", padx=25, pady=5)

        self.scrollable_area = ScrollScreen(self, self.gui_state, on_bottom_reach=self.load_more_data,
                                            fg_color="transparent", corner_radius=0)
        self.scrollable_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(5, 10))

    def filter_topics(self, selected_category):
        for card in self.all_topic_cards:
            card.pack_forget()


    def add_topic_card(self, id=None, title=None, summary=None, url=None, category=None, on_top=False, **kwargs):
        current_filter = self.filter_menu.get()
        should_show = (current_filter == "הכל" or category == current_filter)

        new_topic_card = TopicCard(self.scrollable_area, title=title, summary=summary, category=category, url=url,
                                   id=id, join_callback=self.chat_service.join_room, **kwargs)

        if on_top and self.all_topic_cards:
            if should_show:
                new_topic_card.pack(before=self.all_topic_cards[0], fill="x", padx=5, pady=5)
            self.all_topic_cards.insert(0, new_topic_card)
        else:
            if should_show:
                new_topic_card.pack(fill="x", padx=5, pady=5)
            self.all_topic_cards.append(new_topic_card)

    def release_scroll_lock(self):
        self.scrollable_area.reset_loading_state()

    def load_more_data(self):
        if self.all_topics_downloaded:
            self.scrollable_area.reset_loading_state()
            return

        if self.all_topic_cards:
            valid_ids = [card.id for card in self.all_topic_cards if card.id is not None]

            if valid_ids:
                oldest_id = min(valid_ids)
                self.chat_service.fetch_older_topics(oldest_id)
            else:
                self.scrollable_area.reset_loading_state()
        else:
            self.scrollable_area.reset_loading_state()


class JoinScreen(ctk.CTkFrame):
    def __init__(self, parent, gui_state, chat_service):
        super().__init__(parent, fg_color="transparent")
        self.gui_state = gui_state
        self.chat_service = chat_service
        self.controller = parent

        self.all_group_cards = []
        self.all_topics_downloaded = False
        self.is_waiting = False

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_view()

        self.gui_state.register(StateKey.RELEASE_BTNS, self._release_btn)
        self.gui_state.register(StateKey.ROLE, self._update_role_view)

    def setup_view(self):
        self.actions_container = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 10))

        self.code_frame = ctk.CTkFrame(self.actions_container, fg_color="transparent")
        self.code_frame.pack(fill="x", pady=5)

        self.invite_label = ctk.CTkLabel(
            self.code_frame, text=":הצטרפות לקבוצה סגורה באמצעות קוד",
            font=("Heebo", 14, "bold"), text_color="white"
        )
        self.invite_label.pack(side="right", padx=10)

        self.code_entry = ctk.CTkEntry(
            self.code_frame, placeholder_text=":הזן קוד",
            width=200, font=("Heebo", 13), height=32, justify="right"
        )
        self.code_entry.pack(side="right", padx=5)

        self.join_code_btn = ctk.CTkButton(
            self.code_frame, text="הצטרף",
            font=("Heebo", 13, "bold"), fg_color="#f59e0b", hover_color="#d97706",
            text_color="white", width=80, height=32, command=self.submit_invite_code
        )
        self.join_code_btn.pack(side="right", padx=5)

        self.random_join_frame = ctk.CTkFrame(self.actions_container, fg_color="transparent")

        self.match_label = ctk.CTkLabel(
            self.random_join_frame, text=":או קפוץ לדיון אקראי בנושא",
            font=("Heebo", 14, "bold"), text_color="white"
        )
        self.match_label.pack(side="right", padx=10)

        categories = ["הכל", "ביטחון", "מדיני", "חברה", "כלכלה", "חינוך"]

        self.category_dropdown = ctk.CTkOptionMenu(
            self.random_join_frame, values=categories,
            font=("Heebo", 13), height=32, justify="right"
        )
        self.category_dropdown.pack(side="right", padx=5)

        self.random_join_btn = ctk.CTkButton(
            self.random_join_frame, text="הצטרף אקראית 🎲",
            font=("Heebo", 13, "bold"), width=120, height=32,
            fg_color="#10b981", hover_color="#059669", command=self.submit_random_join
        )
        self.random_join_btn.pack(side="right", padx=5)

        self.filter_menu = ctk.CTkSegmentedButton(
            self, fg_color=("#E9EDF3", "#151C2B"), selected_color=("#2F80ED", "#2F80ED"),
            selected_hover_color=("#256FD1", "#256FD1"), unselected_color=("#E9EDF3", "#151C2B"),
            unselected_hover_color=("#DCEBFF", "#1F2A44"), text_color=("#4B5563", "#D1D5DB"),
            text_color_disabled=("#9CA3AF", "#6B7280"), values=categories, command=self.filter_topics
        )
        self.filter_menu.grid(row=1, column=0, sticky="ew", padx=20, pady=(15, 5))
        self.filter_menu.set("הכל")

        self.divider = ctk.CTkFrame(self, fg_color="#30363D", height=2)
        self.divider.grid(row=2, column=0, sticky="ew", padx=25, pady=5)

        self.scrollable_area = ScrollScreen(
            self, self.gui_state, on_bottom_reach=self.load_more_data,
            fg_color="transparent", corner_radius=0
        )
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
        if self.is_waiting:
            return

        code = self.code_entry.get().strip()
        if not code:
            return

        self.code_entry.delete(0, 'end')
        self.chat_service.join_room_by_code(code)

    def submit_random_join(self):
        if self.is_waiting:
            return

        category = self.category_dropdown.get()
        payload = {Contract.CATEGORY: None if category == "הכל" else category}
        self.chat_service.join_room(payload)

    def add_topic_card(self, id=None, title=None, summary=None, url=None, category=None, on_top=False, **kwargs):
        current_filter = self.filter_menu.get()
        should_show = (current_filter == "הכל" or category == current_filter)

        new_topic_card = TopicCard(
            self.scrollable_area, title=title, summary=summary,
            category=category, url=url, id=id,
            join_callback=self.chat_service.join_room, **kwargs
        )

        if on_top and self.all_group_cards:
            if should_show:
                new_topic_card.pack(before=self.all_group_cards[0], fill="x", padx=5, pady=5)
            self.all_group_cards.insert(0, new_topic_card)
        else:
            if should_show:
                new_topic_card.pack(fill="x", padx=5, pady=5)
            self.all_group_cards.append(new_topic_card)

    def filter_topics(self, selected_category):
        for card in self.all_group_cards:
            card.pack_forget()

        for card in self.all_group_cards:
            if selected_category == "הכל" or card.category == selected_category:
                card.pack(pady=10, padx=10, fill="x")

        self.scrollable_area._parent_canvas.yview_moveto(0.0)

    def release_scroll_lock(self):
        self.scrollable_area.reset_loading_state()

    def load_more_data(self):
        if self.all_topics_downloaded:
            self.scrollable_area.reset_loading_state()
            return

        if self.all_group_cards:
            valid_ids = [card.id for card in self.all_group_cards if card.id is not None]
            if valid_ids:
                oldest_id = min(valid_ids)
                self.chat_service.fetch_older_topics(oldest_id)
            else:
                self.scrollable_area.reset_loading_state()
        else:
            self.scrollable_area.reset_loading_state()


class DiscoveryBase(ScrollScreen):
    def __init__(self, parent, gui_state, chat_service):
        super().__init__(parent, gui_state, fg_color="transparent")
        self.chat_service = chat_service
        self.all_topic_cards = []
        self.all_topics_downloaded = False

        # לוגיקת הסינון המשותפת
        self.filter_menu = None  # יוגדר במחלקות היורשות

    def add_topic_card(self, id=None, title=None, summary=None, url=None, category=None, on_top=False, **kwargs):
        current_filter = self.filter_menu.get() if self.filter_menu else "הכל"
        should_show = (current_filter == "הכל" or category == current_filter)

        new_card = TopicCard(
            self, title=title, summary=summary, category=category,
            url=url, id=id, join_callback=self.chat_service.join_room, **kwargs
        )

        if on_top and self.all_topic_cards:
            if should_show: new_card.pack(before=self.all_topic_cards[0], fill="x", padx=5, pady=5)
            self.all_topic_cards.insert(0, new_card)
        else:
            if should_show: new_card.pack(fill="x", padx=5, pady=5)
            self.all_topic_cards.append(new_card)

    def filter_topics(self, selected_category):
        for card in self.all_topic_cards: card.pack_forget()
        for card in self.all_topic_cards:
            if selected_category == "הכל" or card.category == selected_category:
                card.pack(pady=10, padx=10, fill="x")
        self._parent_canvas.yview_moveto(0.0)

    def load_more_data(self):
        if self.all_topics_downloaded:
            self.reset_loading_state()
            return

        valid_ids = [card.id for card in self.all_topic_cards if card.id is not None]
        if valid_ids:
            self.chat_service.fetch_older_topics(min(valid_ids))
        else:
            self.reset_loading_state()