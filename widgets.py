import tkinter as tk
from tkinter import ttk
from theme import ThemeManager as TM

# Dynamically creates customized buttons
def create_button(parent, text, command, style_type="primary", width=None):
    bg_color = TM.get_color("danger") if style_type == "danger" else TM.get_color("accent")
    fg_color = TM.get_color("text") if style_type == "danger" else TM.get_color("text_dark")
    
    btn = tk.Button(parent, text=text, command=command, bg=bg_color, fg=fg_color,
                    font=TM.FONTS["button"], relief="flat", cursor="hand2", 
                    activebackground=TM.get_color("accent_hover"), activeforeground=TM.get_color("text"), padx=12, pady=5)
    
    if width: btn.config(width=width)
    return btn

# Creates statistical display cards for the dashboard
def create_stat_card(parent, title, value):
    card = tk.Frame(parent, bg=TM.get_color("card"), padx=20, pady=14, highlightthickness=1, highlightbackground=TM.get_color("accent"))
    
    tk.Label(card, text=title, font=TM.FONTS["small"], fg=TM.get_color("text_muted"), bg=TM.get_color("card")).pack()
    tk.Label(card, text=str(value), font=("Georgia", 24, "bold"), fg=TM.get_color("accent"), bg=TM.get_color("card")).pack()
    
    return card

# Generates a Treeview data table with a vertical scrollbar
def create_treeview(parent, columns, headings, col_widths, height=14):
    frame = tk.Frame(parent, bg=TM.get_color("bg"))
    
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=height, style="Custom.Treeview")
    
    for col, head, w in zip(columns, headings, col_widths):
        tree.heading(col, text=head)
        tree.column(col, width=w, minwidth=50, stretch=tk.YES, anchor="center")
        
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    
    return frame, tree

# Creates a standard input row (Label + Entry)
def entry_row(parent, label_text, width=28):
    b = TM.get_color("card")
    f = tk.Frame(parent, bg=b)
    
    tk.Label(f, text=label_text, font=TM.FONTS["body"], fg=TM.get_color("text_muted"), bg=b, width=25, anchor="w").pack(side="left")
    
    var = tk.StringVar()
    e = tk.Entry(f, textvariable=var, font=TM.FONTS["body"], bg=TM.get_color("bg"), fg=TM.get_color("text"), insertbackground=TM.get_color("text"), relief="flat", width=width, highlightthickness=1, highlightcolor=TM.get_color("accent"), highlightbackground=TM.get_color("border"))
    e.pack(side="left", padx=(4, 0), fill="x", expand=True)
    
    return f, var, e

# Creates a dropdown menu row (Label + Combobox)
def combo_row(parent, label_text, values, width=26):
    b = TM.get_color("card")
    f = tk.Frame(parent, bg=b)
    
    tk.Label(f, text=label_text, font=TM.FONTS["body"], fg=TM.get_color("text_muted"), bg=b, width=25, anchor="w").pack(side="left")
    
    var = tk.StringVar(value=values[0] if values else "")
    cb = ttk.Combobox(f, textvariable=var, values=values, font=TM.FONTS["body"], width=width, state="readonly", style="Custom.TCombobox")
    cb.pack(side="left", padx=(4, 0), fill="x", expand=True)
    
    return f, var, cb

# Enveloppe le contenu d'une page (ou d'un onglet) dans une zone défilante :
# ascenseur vertical + molette de la souris (activée uniquement quand le
# curseur survole la zone, pour ne pas interférer avec d'autres widgets).
# Utilisation :
#   outer, wrap = make_scrollable(self)
#   outer.pack(fill="both", expand=True)
#   ... construire tout le contenu de la page dans `wrap` au lieu de `self` ...
def make_scrollable(parent, bg=None):
    if bg is None:
        bg = TM.get_color("bg")
    outer = tk.Frame(parent, bg=bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0)
    vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    wrap = tk.Frame(canvas, bg=bg)
    wrap.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=wrap, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    # Molette de la souris : uniquement quand le curseur est sur cette zone,
    # pour ne pas capturer le défilement d'autres zones (ex : une autre
    # zone défilante imbriquée, comme un onglet à l'intérieur d'une page).
    def _on_wheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    return outer, wrap


# Draws a horizontal separator line
def separator(parent):
    return tk.Frame(parent, bg=TM.get_color("border"), height=1)

# Creates a section title with an adjacent decorative line
def section_title(parent, text):
    b = TM.get_color("card")
    f = tk.Frame(parent, bg=b)
    
    tk.Label(f, text=text, font=TM.FONTS["heading"], fg=TM.get_color("accent"), bg=b).pack(side="left")
    tk.Frame(f, bg=TM.get_color("accent"), height=2).pack(side="left", fill="x", expand=True, padx=10, pady=8)
    
    return f