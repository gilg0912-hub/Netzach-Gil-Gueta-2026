import customtkinter as ctk
import pywinstyles
from auth_config import *
import math
import re
from PIL import Image, ImageSequence
import webbrowser

class Field(ctk.CTkFrame):

    def __init__(self, parent, callback, field_type: FieldType):

        super().__init__(parent, fg_color='transparent')

        self.pack_propagate(True)
        self.callback = callback
        self.config = FIELD_DEFS[field_type]
        self.max_len = self.config.get('max_len', 999)
        self.min_len = self.config.get('min_len', 6)
        self.pattern = self.config.get('pattern', r'^.+$')

        self.btn = None
        self.timer_id = None
        self._arrange_widgets()

    def _arrange_widgets(self):
        ctk.CTkLabel(self, **self.config.get('label_conf'), text_color='white').pack(anchor='e', pady=5, padx=10)

        self.entry_frame = ctk.CTkFrame(self, fg_color="#051224", corner_radius=0)
        ctk.CTkLabel(self.entry_frame, **self.config.get('emoji_conf'), font=("Arial", 20), text_color='white').pack(side="left", padx=10)
        self.entry = ctk.CTkEntry(self.entry_frame, **self.config.get('entry_conf'),fg_color="#051224", text_color='white')
        self.entry.configure(validate="key", validatecommand=(self.register(self._on_input_change), "%P", "%S"))
        self.entry.pack(side="left", fill='x', expand=True)

        if self.config.get('show_eye'):
            self.btn = ctk.CTkButton(self.entry_frame, text="🙈", text_color='white', cursor="hand2", fg_color="#051224",
                                     border_width=0, width=5, command=self.entry_state, font=("Arial", 15), hover_color="#051224")
            self.btn.pack(side='right', padx=5)

        self.line= ctk.CTkFrame(self, fg_color='white', height=2)
        self.line.pack(fill='x', side='bottom', padx=10)



        self.entry_frame.pack(fill="x")

    def _update_visuals(self, color):
        current_color = self.line.cget("fg_color")

        if current_color != color:
            self.line.configure(fg_color=color)

    def _on_input_change(self, future_txt, chr_added):
        if chr_added ==" " or  len(future_txt) > self.max_len:
            return False

        self.after(10, lambda: self.callback())
        return True


    def is_valid(self, text= None):

        if text is None:
            text = self.entry.get() or ''


        length = len(text)

        if length == 0:
            self._update_visuals('white')
            return False

        if length < self.min_len:
            self._update_visuals('#FF5252')
            return False

        valid = bool(re.fullmatch(self.pattern, text))
        color = 'white' if valid else '#FF5252'
        self._update_visuals(color)

        return valid



    def _reset_visuals(self):
        self.line.configure(fg_color='white')
        self._error_timer = None

    def entry_state(self):
        if self.btn:
            if self.btn.cget("text") == "🐵":
                self.entry.configure(show="•")
                self.btn.configure(text="🙈")
            else:
                self.entry.configure(show="")
                self.btn.configure(text="🐵")

    def get(self):
        return self.entry.get()


class Screen(ctk.CTkFrame):
    def __init__(self, parent, title: str, field_types: list[FieldType], confirm_text: str = "Confirm", confirm_command=None, extra_btns=[], style :dict = ROLE_STYLES[UserRole.STANDARD]):
        super().__init__(parent, fg_color='transparent')

        self.is_valid_state=False
        self.lock=False
        self.title_label = ctk.CTkLabel(self, text=title, font=("hebbo", 30, "bold"), text_color= style.get(UIKey.TEXT_COLOR))
        self.title_label.pack(pady=20, fill='x')

        self.fields = {ft: Field(self, self.check_valid_fields, ft) for ft in field_types}
        self.confirm_btn=None
        for field in self.fields.values():
            field.pack(pady=15, padx=25, fill="x")

        for btn_conf in extra_btns:
            ctk.CTkButton(self, **btn_conf).pack(pady=10)

        if confirm_command:
            self.confirm_btn= ctk.CTkButton(self,**STYLE_CTK, state= 'disabled', text_color= style.get(UIKey.TEXT_COLOR), border_color= style.get('border_color'), hover_color= style.get('hover_color'), text= confirm_text, command=confirm_command )
            self.confirm_btn.pack(pady=20)

    def check_valid_fields(self):
        if not self.confirm_btn:
            return

        validations = [field.is_valid() for field in self.fields.values()]

        self.is_valid_state = all(validations)

        should_be_disabled = self.lock or not self.is_valid_state

        current_state = self.confirm_btn.cget('state')

        if should_be_disabled and current_state != 'disabled':
            self.confirm_btn.configure(state='disabled')

        elif not should_be_disabled and current_state != 'normal':
            self.confirm_btn.configure(state='normal')



    def get_data(self):
        return {field_type: f.get() for field_type, f in self.fields.items()}

class Loading(ctk.CTkFrame):
    def __init__(self, parent, **params):
        super().__init__(parent, fg_color='#0A2140',
                         width=params.get('width', 300),
                         height=params.get('height', 50))

        self._after_id = None


        # יצירת הגלגל
        self.wheel = Spin(self, int(self.cget('height')) // 20,
                          width=int(self.cget('height')),
                          height=int(self.cget('height')))

        self.label = ctk.CTkLabel(self, text='', text_color="white",
                                  font=('hebbo', int(self.cget('height') * 0.4)))

        self.wheel.pack(side='left', padx=5)
        self.label.pack(side='left', padx=5)

        self.apply_style()

    def update_view(self, text: str= '', text_color='green'):
        if text!= self.label.cget('text'):
            self._show(text, text_color)

    def _show(self, value, text_color):
        self.label.configure(text=value, text_color=text_color)

        if not self._after_id:
            self.grid(row=0, column=0, sticky="nsew")
            self._animate()

    def _animate(self):
        self.wheel.animation()
        self._after_id = self.after(100, self._animate)

    def _stop_animation(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

    def apply_style(self):
        pywinstyles.apply_style(self, "transparent")
        pywinstyles.set_opacity(self, color="#0A2140")

class Spin(ctk.CTkCanvas):
    def __init__(self, parent, dot_size, **params):
        super().__init__(parent, bg="#0A2140", highlightthickness=0, width= params.get('width', 100), height=params.get('height', 100))
        self.dots = []
        self.dot_num = 10
        self.dot_radius = dot_size
        self.radius = int(self.cget('height')) // 5
        self.center = (int(self.cget('width')) // 2, int(self.cget('height')) // 2)
        self.angle_offset = 0
        self._build_dots()

    def _build_dots(self):
        for i in range(self.dot_num):
            angle = i * (360 / self.dot_num)
            x_center, y_center = self.get_coords(angle)
            dot = self.create_oval(x_center - self.dot_radius, y_center - self.dot_radius, x_center + self.dot_radius,
                                   y_center + self.dot_radius, fill='#4a90e2')
            self.dots.append(dot)

    def animation(self):
        for i, dot in enumerate(self.dots):
            clarity = int(255 * ((i + self.angle_offset) % self.dot_num / self.dot_num))
            color = f'#{clarity:02x}{clarity:02x}{clarity:02x}'
            self.itemconfig(dot, fill=color)

        self.angle_offset = (self.angle_offset + 1) % self.dot_num

    def get_coords(self, angle):
        angle = math.radians(angle)
        x = self.center[0] + self.radius * math.cos(angle)
        y = self.center[1] - self.radius * math.sin(angle)
        return x, y

class AnimatedGifLabel(ctk.CTkLabel):
    def __init__(self, master, gif_path, size=(500, 150), **kwargs):
        # טעינת ה-GIF
        self.img = Image.open(gif_path)
        self.frames = []
        self.durations = []

        for frame in ImageSequence.Iterator(self.img):

            frame_rgba = frame.copy().convert("RGBA")
            self.frames.append(ctk.CTkImage(light_image=frame_rgba, size=size))

        super().__init__(master, image=self.frames[0], text="", **kwargs)

        self.frame_index = 0
        self.direction=1
        self.apply_style()

    def apply_style(self):
        pywinstyles.apply_style(self, "transparent")

        pywinstyles.set_opacity(self, color="#0A2140")

    def _animate(self):
        try:

            self.configure(image=self.frames[self.frame_index])

            if self.direction==1 and self.frame_index == len(self.frames) - self.direction:
                self.direction = -1
                self.frame_index += self.direction
                self.after(10000, self._animate)
            elif self.direction==-1 and self.frame_index==0:
                    self.direction = 1
                    self.after(10, self._animate)
            else:
                if self.frame_index < 45:
                    delay = 17
                else:
                    delay = 60
                self.frame_index += self.direction
                self.after(delay, self._animate)

        except Exception as e:
            pass

    def _reverse(self):
        try:
            self.configure(image=self.frames[self.frame_index])
            if self.frame_index == 0:
                self._animate()
            else:
                delay = self.durations[self.frame_index]
                self.frame_index -= 1
                self.after(delay, self._reverse)

        except Exception as e:
            pass



    def grid(self, **kwargs):
        super().grid(**kwargs)
        self._animate()

class TopicCard(ctk.CTkFrame):
    def __init__(self, master, title=None, summary=None, url=None, id =None,category=None, btn_configs=None, **kwargs):
        super().__init__(master, corner_radius=15, fg_color=('white', "#1e293b"), border_width=2, border_color="#334155")

        self.category = category
        self.url = url
        self.id = id
        print(self.category)
        self.cat_label = ctk.CTkLabel(
            self, text=category, font=("Heebo", 10, "bold"),
            fg_color=("#F1F5F9", "#334155"), text_color="#38bdf8", corner_radius=10
        )
        self.cat_label.pack(pady=(10, 0), padx=15, anchor="e")

        self.title_label = ctk.CTkLabel(
            self, text=title, font=("Heebo", 18, "bold"),
            text_color="#f8fafc", wraplength=300, justify="right"
        )
        self.title_label.pack(pady=(15, 5), padx=15, anchor="e")

        self.summary_label = ctk.CTkLabel(
            self, text=summary, font=("Heebo", 14), text_color= ('black', "white"),
            wraplength=300, justify="right"
        )
        self.summary_label.pack(pady=5, padx=15, anchor="e")

        self.link_btn = ctk.CTkButton(
            self, text="...קרא עוד באתר המקור", font=("Heebo", 12, "underline"),
            fg_color="transparent", text_color="#38bdf8", hover_color=('white',"#334155"),
            cursor="hand2", height=20, command=self.open_link
        )
        self.link_btn.pack(pady=5, padx=10, anchor="w")

        print('A')
        if btn_configs:
            print('B')
            self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.btn_frame.pack(side="bottom", pady=(0, 12), padx=15, fill="x")

            for btn_conf in btn_configs:
                btn = ctk.CTkButton(
                    self.btn_frame,
                    text=btn_conf.get('text', 'פעולה'),
                    command=btn_conf.get('command'),
                    fg_color=btn_conf.get('fg_color', '#3D5A80'),
                    hover_color=btn_conf.get('hover_color', '#293E59'),
                    font=('Heebo', 12, 'bold'),
                    height=32
                )
                btn.pack(side="right", expand=True, fill="x", padx=4)
        else:
            print('C')
    def open_link(self):
        if self.url:
            webbrowser.open_new_tab(self.url)


class RequiredEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._default_border = self.cget("border_color")


        vcmd = (self.register(self._auto_clear_on_type), '%P')
        self.configure(validate="key", validatecommand=vcmd)

    def _auto_clear_on_type(self, current_text):
        if current_text.strip():
            self.configure(border_color=self._default_border)
        return True

    def check_validity(self):
        if not self.get().strip():
            self.configure(border_color="red")
            return False
        return True