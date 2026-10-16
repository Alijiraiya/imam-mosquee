import tkinter as tk
from tkinter import messagebox
from theme import ThemeManager as TM
from widgets import separator
import database as db

# Mot de passe par défaut de l'Imam (utilisé uniquement si aucun mot de passe
# personnalisé n'a encore été enregistré dans les Paramètres)
DEFAULT_PASSWORD = "IMAM1234"

# Create a LoginWindow class that inherits from Toplevel 
class LoginWindow(tk.Toplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        # Set the window title 
        self.title("Connexion | تسجيل الدخول")
        # Set the background color 
        self.configure(bg=TM.get_color("bg"))
        # Disable window resizing 
        self.resizable(False, False)
        
        # Make this window modal, preventing interaction with the main window until closed 
        self.grab_set()
        
        # Store the callback function to execute upon successful login 
        self._on_success = on_success
        
        # Initialize failed login attempts counter 
        self._attempts = 0
        
        self._build()
        # Set the window dimensions 
        self.geometry("450x360")
        # center the window on the screen 
        self._center()

    # Method to calculate and center the window on any monitor 
    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # Method to construct the visual components of the window 
    def _build(self):
        tk.Label(self, text="🕌", font=("", 48), bg=TM.get_color("bg")).pack(pady=(20, 0))
        tk.Label(self, text="Système de Gestion des Dons | التبرعات ادارة نظام", font=("Georgia", 14, "bold"), fg=TM.get_color("accent"), bg=TM.get_color("bg")).pack()
        tk.Label(self, text="Mosquée | المسجد", font=TM.FONTS["body"], fg=TM.get_color("text_muted"), bg=TM.get_color("bg")).pack(pady=(0, 10))
        
        # Add a horizontal separator line 
        separator(self).pack(fill="x", padx=40, pady=10)

        # Create an inner frame to hold the input field and button 
        inner = tk.Frame(self, bg=TM.get_color("bg"))
        inner.pack(padx=50, pady=10, fill="x")
        
        tk.Label(inner, text="Mot de passe | كلمة المرور :", font=TM.FONTS["body"], fg=TM.get_color("text_muted"), bg=TM.get_color("bg"), anchor="w").pack(fill="x")
        
        self.v_pwd = tk.StringVar()
        
        e = tk.Entry(inner, textvariable=self.v_pwd, font=("Helvetica", 13), show="●", bg=TM.get_color("card"), fg=TM.get_color("text"), insertbackground=TM.get_color("text"), relief="flat", width=26, highlightthickness=2, highlightcolor=TM.get_color("accent"), highlightbackground=TM.get_color("border"))
        e.pack(fill="x", pady=8, ipady=6)
        
        e.bind("<Return>", lambda _: self._check())
    
        e.focus_set()
        
        # Label to display error messages, initially empty 
        self.err_lbl = tk.Label(inner, text="", font=TM.FONTS["small"], fg=TM.get_color("danger"), bg=TM.get_color("bg"))
        self.err_lbl.pack()
        
        # Login button that calls _check method when clicked 
        tk.Button(inner, text="Se connecter | دخول", font=TM.FONTS["button"], bg=TM.get_color("accent"), fg=TM.get_color("text_dark"), relief="flat", cursor="hand2", activebackground=TM.get_color("accent_hover"), activeforeground=TM.get_color("text"), padx=20, pady=8, command=self._check).pack(pady=8)

    # Method to validate the entered password 
    def _check(self):
        current_password = db.get_setting("app_password", DEFAULT_PASSWORD)
        if self.v_pwd.get() == current_password:
            self._on_success()
            self.destroy()
        else:
            self._attempts += 1
            self.err_lbl.config(text=f"❌ Mot de passe incorrect | كلمة المرور غير صحيحة ({self._attempts}/5)")
            self.v_pwd.set("")
            
            if self._attempts >= 5:
                messagebox.showerror("Accès bloqué | تم الحجب", "Trop de tentatives. Fermeture. | محاولات كثيرة. سيتم الإغلاق.", parent=self)
                self.master.destroy()