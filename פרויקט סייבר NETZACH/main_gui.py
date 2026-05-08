import customtkinter as ctk
from PIL import Image
import pywinstyles
from app_constants import AppScreens, StateKey, MsgType
from auth_controller import AuthController
from chat_controller import ChatController
from modals import UserDetailsOverlay
from ui_components import AnimatedGifLabel, Loading
from modals import resize_image, load_ui_image


class Chat_GUI(ctk.CTk):
    def __init__(self, user_state, gui_state, services):
        super().__init__()
        self.protocol("WM_DELETE_WINDOW", self.client_disconnects)
        self.user_state = user_state
        self.gui_state = gui_state


        self.header = Header(self, self.gui_state)
        self.app_body = AppBody(self, self.gui_state, services)
        self.footer_label= ctk.CTkLabel(self, text= '© 2026 NETZACH | נצ"ח ישראל לא ישקר – שומרים על קשר, שומרים על המורשת', font=("Heebo", 15), text_color= '#B0903D', fg_color='#0A2140')


        self.title("What's Burning")
        self.geometry("1200x900")

        self._set_appearance_mode("dark")
        ctk.set_appearance_mode("dark")


        self.grid_configure(self, [1, 8], [1])
        self.header.grid(row=0, column=0, sticky="nsew")
        self.app_body.grid(row=1, column=0, sticky="nsew")
        self.footer_label.grid(row=3, column=0, sticky="nsew")

        self.gui_state.register(StateKey.LOGGED_IN, self._handle_login_success)

    def run(self):
        self.mainloop()

    def _handle_login_success(self, is_logged_in):
        if is_logged_in:
            self.header.grid_remove()
            self.footer_label.grid_remove()

            # נותנים ל-AppBody (שורה 1) את כל המקום
            self.grid_rowconfigure(0, weight=0)
            self.grid_rowconfigure(1, weight=1)
            self.grid_rowconfigure(3, weight=0)  # שורת ה-Footer

            print("[UI] Finalized Login: Screen cleared for Chat mode.")
        else:
            self.header.grid()
            self.footer_label.grid()

            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(1, weight=8)
            self.grid_rowconfigure(3, weight=1)

            print("[UI] Logged out: Layout restored to Auth mode.")

    def client_disconnects(self):
        self.user_state.set_state(StateKey.IS_ACTIVE, False)
        self.destroy()

    def grid_configure(self, container, row_weights=None, column_weights=None):
        for i, w in enumerate(row_weights):
            container.grid_rowconfigure(i, weight=w)



        for i, w in enumerate(column_weights):
            container.grid_columnconfigure(i, weight=w)

class Header(ctk.CTkFrame):
    def __init__(self, parent, gui_state, gif_path=r"the_project_final_gif.gif"):
        super().__init__(parent, fg_color='#0A2140', corner_radius=0, bg_color='transparent')
        self.gui_state = gui_state
        self.bg_image = load_ui_image('the_final_top_background_fixed.png', size=(1200, 223))
        if self.bg_image:
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bind("<Configure>", lambda e: resize_image(e, self.bg_image) if self.bg_image else None)


        self.logo = AnimatedGifLabel(self, gif_path=gif_path, fg_color='white', bg_color='transparent')
        self.loading_ui = Loading(self, width=70, height=50)

        self.grid_rowconfigure(0, weight=1, uniform='top')
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.gui_state.register(StateKey.CONNECTED, self._sync_state)
        self.gui_state.register(StateKey.LOADING_STATUS, self._sync_state)


        self._arrange_widgets()


    def _arrange_widgets(self):
        self.loading_ui.grid(row=0, column=0, sticky="nsew")
        self.logo.grid(row=1, column=0, sticky='n')

    def _sync_state(self, _=None):
        is_logged= self.gui_state.get_state(StateKey.LOGGED_IN)
        if is_logged:
            return
        conn= self.gui_state.get_state(StateKey.CONNECTED)
        loading= self.gui_state.get_state(StateKey.LOADING_STATUS)

        if not conn:
            self.loading_ui.update_view(text='Connecting To Server...' , text_color='red')
        elif loading:
            self.loading_ui.update_view(text='Loading...')
        else:
            self.loading_ui.update_view(text='Connected')

    def show_guest_header(self, is_logged):
        if is_logged:
            self.loading_ui._stop_animation()

class AppBody(ctk.CTkFrame):
    def __init__(self, parent, gui_state, services):
        super().__init__(parent, fg_color='#0A2140', corner_radius=0, bg_color='#051224')

        self.gui_state = gui_state
        self.services = services
        self.screen_manager = ScreenManager(self.gui_state, self.services)

        self.screen_manager.add_screen(AppScreens.AUTH, AuthController)
        self.screen_manager.add_screen(AppScreens.CHAT, ChatController)

        if 'auth' in self.services:
            self.services['auth']._on_success_callback = lambda: self._handle_auth_navigation()



        self.block_screen= ctk.CTkFrame(self, corner_radius=0, bg_color='#0A2140', fg_color='#10161D')
        pywinstyles.apply_style(self.block_screen, "transparent")
        pywinstyles.set_opacity(self.block_screen, color="#0A2140", value=0.2)

        self._modal_shield = ctk.CTkFrame(self, fg_color="#000000")
        pywinstyles.set_opacity(self._modal_shield, value=0.5)

        self._user_overlay = UserDetailsOverlay(
            parent=self,
            gui_state=self.gui_state,
            close_callback=self._close_profile
        )

        self.gui_state.register(StateKey.LOADING_STATUS, self.block_screen_state)
        self.gui_state.register(StateKey.CONNECTED, self.refresh_block_state)
        self.gui_state.register(StateKey.SHOW_USER_INFO, self._toggle_user_profile)

        self.bg_image = load_ui_image('bottom_final_background.png', size=(1200, 640))
        if self.bg_image:
            self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bind("<Configure>", lambda e: resize_image(e, self.bg_image) if self.bg_image else None)
        self.screen_manager.show_screen(self, AppScreens.AUTH, side='top')

    def block_screen_state(self, is_loading):
        if is_loading:
            self.block_screen.place(x=0, y=0, relwidth=1, relheight=1)
            self.block_screen.lift()
        else:
            self.block_screen.place_forget()


    def refresh_block_state(self, _=None):
        is_loading = self.gui_state.get_state(StateKey.LOADING_STATUS)
        is_connected = self.gui_state.get_state(StateKey.CONNECTED)

        if is_loading and is_connected:
            self.block_screen.place(x=0, y=0, relwidth=1, relheight=1)
            self.block_screen.lift()
        else:
            self.block_screen.place_forget()


    def _toggle_user_profile(self, should_show):
        if should_show:
            self._user_overlay.refresh_data()
            self._modal_shield.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._modal_shield.lift()

            self._user_overlay.place(relx=0.5, rely=0.5, anchor='center')
            self._user_overlay.lift()
            self._user_overlay.grab_set()
        else:
            self._close_profile()

    def _close_profile(self):
        self._user_overlay.grab_release()
        self._user_overlay.place_forget()
        self._modal_shield.place_forget()

        if self.gui_state.get_state(StateKey.SHOW_USER_INFO):
            self.gui_state.set_state(StateKey.SHOW_USER_INFO, False)


    def _handle_auth_navigation(self):
        last_type = self.gui_state.get_state(StateKey.LAST_MSG_TYPE)

        if last_type in [MsgType.LOGIN, MsgType.SIGNUP]:
            self.screen_manager.show_screen(self, AppScreens.CHAT)

class ScreenManager:
    def __init__(self, gui_state, services):
        self.gui_state = gui_state
        self.services = services

        self.active_screen_instance = None
        self.screen_classes = {}

    def add_screen(self, name, screen_class):
        self.screen_classes[name] = screen_class

    def show_screen(self, container, name, **pack_params):
        if name not in self.screen_classes:
            print(f"Error: Screen {name} not registered")
            return

        if self.active_screen_instance:
            self.active_screen_instance.destroy()
            self.active_screen_instance = None
            import gc
            gc.collect()

        screen_class = self.screen_classes[name]

        self.active_screen_instance = screen_class(
            container,
            self.gui_state,
            self.services
        )

        # --- שלב 3: הצגה (האריזה) ---
        if not pack_params:
            self.active_screen_instance.pack(fill="both", expand=True)
        else:
            self.active_screen_instance.pack(**pack_params)