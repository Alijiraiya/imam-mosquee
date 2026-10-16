from tkinter import ttk

class ThemeManager:
    PALETTES = {
        "dark": {
            "bg": "#0F1923", "card": "#162030", "sidebar": "#0A1219",
            "accent": "#C9A84C", "accent_hover": "#1E7F6E",
            "text": "#EEE8DC", "text_muted": "#7A8899", "text_dark": "#0F1923",
            "danger": "#C0392B", "success": "#27AE60", "border": "#243040"
        },
        "light": {
            "bg": "#F0F2F5", "card": "#FFFFFF", "sidebar": "#DDE1E7",
            "accent": "#B8860B", "accent_hover": "#1E7F6E",
            "text": "#1A2332", "text_muted": "#5D6D7E", "text_dark": "#FFFFFF",
            "danger": "#E74C3C", "success": "#27AE60", "border": "#C0C8D0"
        }
    }

    FONTS = {
        "title":   ("Georgia", 22, "bold"),
        "h2":      ("Georgia", 16, "bold"),
        "heading": ("Georgia", 14, "bold"),
        "body":    ("Helvetica", 11),
        "body_b":  ("Helvetica", 11, "bold"),
        "small":   ("Helvetica", 9),
        "small_b": ("Helvetica", 9, "bold"),
        "button":  ("Helvetica", 10, "bold"),
        "mono":    ("Courier", 10),
    }

    SIZES = {"sidebar_w": 230, "pad": 16, "row_h": 32}
    current_theme = "dark"

    @classmethod
    def get_color(cls, color_name):
        return cls.PALETTES[cls.current_theme][color_name]

    @classmethod
    def toggle_theme(cls):
        cls.current_theme = "light" if cls.current_theme == "dark" else "dark"
        cls.apply_ttk_styles()

    @classmethod
    def apply_ttk_styles(cls):
        style = ttk.Style()
        style.theme_use("clam")
        bg_card    = cls.get_color("card")
        bg_sidebar = cls.get_color("sidebar")
        bg_main    = cls.get_color("bg")
        text_white = cls.get_color("text")
        text_muted = cls.get_color("text_muted")
        accent     = cls.get_color("accent")
        text_dark  = cls.get_color("text_dark")

        style.configure("Custom.Treeview",
            background=bg_card, foreground=text_white,
            fieldbackground=bg_card, rowheight=cls.SIZES["row_h"],
            font=cls.FONTS["body"])
        style.configure("Custom.Treeview.Heading",
            background=bg_sidebar, foreground=accent,
            font=cls.FONTS["body_b"], relief="flat")
        style.map("Custom.Treeview",
            background=[("selected", accent)],
            foreground=[("selected", text_dark)])
        style.configure("Custom.TCombobox",
            fieldbackground=bg_main, background=bg_main,
            foreground=text_white, selectbackground=accent,
            selectforeground=text_dark, arrowcolor=accent)
        style.configure("Custom.TNotebook", background=bg_main, borderwidth=0)
        style.configure("Custom.TNotebook.Tab",
            background=bg_sidebar, foreground=text_muted,
            font=cls.FONTS["body_b"], padding=[10, 5])
        style.map("Custom.TNotebook.Tab",
            background=[("selected", bg_card)],
            foreground=[("selected", accent)])