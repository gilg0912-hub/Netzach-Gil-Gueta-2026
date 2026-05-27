import customtkinter as ctk
from app_constants import StateKey
from PIL import Image


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