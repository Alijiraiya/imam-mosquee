import tkinter as tk
from tkinter import ttk, messagebox
import database as db
from theme import ThemeManager as TM
from widgets import entry_row, create_treeview, make_scrollable

CASH_TYPES = ["Cash | نقداً", "Chèque", "Sadaqa Jariya", "Zakat Al-Maal", "Zakat Al-Fitr"]
NATURE_TYPES = ["Cartables | حقائب مدرسية", "Vêtements | ملابس", "Nourriture | طعام",
                "Matériel scolaire | مستلزمات مدرسية", "Médicaments | أدوية",
                "Meubles | أثاث", "Autre | أخرى"]
UNITS = ["unité(s) | قطعة", "kg", "g", "L", "ml", "carton(s)", "sac(s)", "paquet(s)"]

# ── Historique des dons : une liste séparée par catégorie (Argent, Vêtements,
# Nourriture, ...) plutôt qu'une seule liste mélangeant tout. La clé "cash"
# regroupe tous les dons en Espèce ; chaque type d'objet en Nature a sa
# propre clé "nature:<type>".
NATURE_ICONS = {
    "Cartables | حقائب مدرسية": "🎒",
    "Vêtements | ملابس": "👕",
    "Nourriture | طعام": "🍞",
    "Matériel scolaire | مستلزمات مدرسية": "📚",
    "Médicaments | أدوية": "💊",
    "Meubles | أثاث": "🛋️",
    "Autre | أخرى": "📦",
}
DONATION_CATEGORY_TABS = [("cash", "💰 Argent | نقدي")] + [
    (f"nature:{t}", f"{NATURE_ICONS.get(t, '📦')} {t}") for t in NATURE_TYPES
]

class DonationsPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._build()

    def _build(self):
        # Page défilante (ascenseur + molette).
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        # Balance bar (caisse en argent uniquement, les dons en nature n'y figurent pas)
        top_card = tk.Frame(wrap, bg=TM.get_color("accent"), padx=15, pady=10)
        top_card.pack(fill="x", padx=15, pady=10)
        _, _, solde = db.get_financial_summary()
        self.lbl_solde = tk.Label(top_card, text=f"Caisse Actuelle : {solde:,.0f} DA",
                                  font=TM.FONTS["h2"], fg="#ffffff", bg=TM.get_color("accent"))
        self.lbl_solde.pack(side="left")

        body = tk.Frame(wrap, bg=TM.get_color("bg"))
        body.pack(fill="both", expand=True, padx=15, pady=5)

        # ── Donateurs (en haut, plutôt qu'à gauche) ──
        left = tk.LabelFrame(body, text=" Donateurs | المانحون ",
                             font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                             bg=TM.get_color("bg"), padx=10, pady=10)
        left.pack(side="top", fill="both", expand=True, pady=(0, 10))

        dform = tk.Frame(left, bg=TM.get_color("bg"))
        dform.pack(side="bottom", fill="x", pady=4)
        f, self.v_dname,  _ = entry_row(dform, "Nom | الاسم :"); f.pack(fill="x", pady=2)
        f, self.v_dphone, _ = entry_row(dform, "Tél | الهاتف :"); f.pack(fill="x", pady=2)
        f, self.v_dage,   _ = entry_row(dform, "Âge | السن :", width=6); f.pack(fill="x", pady=2)
        self.v_dage.set("0")
        tk.Button(dform, text="＋ Enregistrer Donateur", font=TM.FONTS["small"],
                  bg=TM.get_color("card"), fg=TM.get_color("text"),
                  command=self._add_donor).pack(fill="x", pady=4)
        tk.Button(dform, text="🗑 Supprimer le donateur sélectionné", font=TM.FONTS["small"],
                  bg="#e74c3c", fg="#ffffff",
                  command=self._delete_donor).pack(fill="x", pady=2)

        self.df_c, self.donor_tree = create_treeview(
            left, ["id","name","phone","age"],
            ["#","Nom","Téléphone","Âge"], [40,140,100,40], height=8)
        self.df_c.pack(side="top", fill="both", expand=True)

        # ── Enregistrer un Don (en dessous, plutôt qu'à droite) ──
        right = tk.LabelFrame(body, text=" Enregistrer un Don | تسجيل هبة ",
                              font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                              bg=TM.get_color("bg"), padx=10, pady=10)
        right.pack(side="top", fill="both", expand=True)

        # Catégorie du don : Espèce (argent) ou Nature (objets)
        f_cat = tk.Frame(right, bg=TM.get_color("bg"))
        f_cat.pack(fill="x", pady=3)
        tk.Label(f_cat, text="Catégorie | فئة الهبة :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text")).pack(side="left")
        self.cb_category = ttk.Combobox(f_cat,
                                        values=["Espèce | نقدي", "Nature (Objets) | عيني"],
                                        state="readonly")
        self.cb_category.set("Espèce | نقدي")
        self.cb_category.pack(side="left", padx=5)
        self.cb_category.bind("<<ComboboxSelected>>", lambda e: self._on_category_change())

        # Conteneur qui bascule entre le formulaire "argent" et "nature"
        self.form_container = tk.Frame(right, bg=TM.get_color("bg"))
        self.form_container.pack(fill="x", pady=3)

        # -- Sous-formulaire : don en argent --
        self.cash_frame = tk.Frame(self.form_container, bg=TM.get_color("bg"))
        f, self.v_amount, _ = entry_row(self.cash_frame, "Montant (DA) | المبلغ :"); f.pack(fill="x", pady=3)
        self.v_amount.set("0")
        f_type = tk.Frame(self.cash_frame, bg=TM.get_color("bg"))
        f_type.pack(fill="x", pady=3)
        tk.Label(f_type, text="Type | النوع :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text")).pack(side="left")
        self.cb_type = ttk.Combobox(f_type, values=CASH_TYPES, state="readonly")
        self.cb_type.set(CASH_TYPES[0])
        self.cb_type.pack(side="left", padx=5)

        # -- Sous-formulaire : don en nature (cartables, vêtements, nourriture...) --
        self.nature_frame = tk.Frame(self.form_container, bg=TM.get_color("bg"))
        f_type_n = tk.Frame(self.nature_frame, bg=TM.get_color("bg"))
        f_type_n.pack(fill="x", pady=3)
        tk.Label(f_type_n, text="Type | النوع :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text")).pack(side="left")
        self.cb_type_nature = ttk.Combobox(f_type_n, values=NATURE_TYPES, state="readonly")
        self.cb_type_nature.set(NATURE_TYPES[0])
        self.cb_type_nature.pack(side="left", padx=5)

        f, self.v_item_name, _ = entry_row(self.nature_frame,
                                           "Désignation | البيان :"); f.pack(fill="x", pady=3)

        # Quantité + Unité (kg, g, L, unité, carton...) côte à côte
        f_qty = tk.Frame(self.nature_frame, bg=TM.get_color("card"))
        f_qty.pack(fill="x", pady=3)
        tk.Label(f_qty, text="Quantité | الكمية :", font=TM.FONTS["body"],
                 fg=TM.get_color("text_muted"), bg=TM.get_color("card"),
                 width=25, anchor="w").pack(side="left")
        self.v_quantity = tk.StringVar(value="1")
        tk.Entry(f_qty, textvariable=self.v_quantity, font=TM.FONTS["body"],
                 bg=TM.get_color("bg"), fg=TM.get_color("text"),
                 insertbackground=TM.get_color("text"), relief="flat", width=8,
                 highlightthickness=1, highlightcolor=TM.get_color("accent"),
                 highlightbackground=TM.get_color("border")).pack(side="left", padx=(4, 4))
        self.cb_unit = ttk.Combobox(f_qty, values=UNITS, state="readonly", width=10)
        self.cb_unit.set(UNITS[0])
        self.cb_unit.pack(side="left", fill="x", expand=True)

        f, self.v_est_value, _ = entry_row(self.nature_frame,
                                           "Valeur estimée (DA, optionnel) :"); f.pack(fill="x", pady=3)
        self.v_est_value.set("0")

        self.cash_frame.pack(fill="x")  # vue par défaut : Espèce

        f, self.v_notes, _ = entry_row(right, "Notes / Description :"); f.pack(fill="x", pady=3)

        tk.Button(right, text="📥 Valider l'entrée du Don", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", command=self._add_donation,
                  height=2).pack(fill="x", pady=15)

        # ── Historique des dons : une liste distincte par catégorie ──
        hist_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        hist_frame.pack(fill="both", expand=False, padx=15, pady=(0, 10))
        tk.Label(hist_frame, text="Historique des Dons par catégorie | حسب الفئة الهبات سجل ",
                 font=TM.FONTS["heading"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", pady=5)

        self.hist_notebook = ttk.Notebook(hist_frame, style="Custom.TNotebook")
        self.hist_notebook.pack(fill="both", expand=True)

        # Une clé -> un tableau : "cash" pour l'argent, "nature:<type>" pour
        # chaque catégorie d'objets (Vêtements, Nourriture, ...).
        self.category_trees = {}
        for key, label in DONATION_CATEGORY_TABS:
            tab = tk.Frame(self.hist_notebook, bg=TM.get_color("card"), padx=8, pady=8)
            self.hist_notebook.add(tab, text=label)

            tab_top = tk.Frame(tab, bg=TM.get_color("card"))
            tab_top.pack(fill="x")
            tk.Button(tab_top, text="🗑 Supprimer le don sélectionné", font=TM.FONTS["small"],
                      bg="#e74c3c", fg="#ffffff",
                      command=lambda k=key: self._delete_donation(k)).pack(side="right", pady=(0, 5))

            container, tree = create_treeview(
                tab, ["donor", "detail", "date"],
                ["Donateur", "Détail", "Date"], [180, 300, 130], height=7)
            container.pack(fill="both", expand=True)
            self.category_trees[key] = tree

        self.load_data()

    def _on_category_change(self):
        is_nature = self.cb_category.get().startswith("Nature")
        if is_nature:
            self.cash_frame.pack_forget()
            self.nature_frame.pack(fill="x")
        else:
            self.nature_frame.pack_forget()
            self.cash_frame.pack(fill="x")

    def refresh(self):
        self.load_data()

    def load_data(self):
        _, _, solde = db.get_financial_summary()
        self.lbl_solde.config(text=f"Caisse Actuelle : {solde:,.0f} DA")

        for r in self.donor_tree.get_children():
            self.donor_tree.delete(r)
        for row in db.get_all_donors():
            # row: (id, name, phone, age)
            self.donor_tree.insert("", "end", iid=str(row[0]),
                                   values=(row[0], row[1], row[2], row[3]))

        for tree in self.category_trees.values():
            for r in tree.get_children():
                tree.delete(r)
        for row in db.get_all_donations():
            # row: (id, donor_name, amount, donation_type, donation_date, notes,
            #       category, item_name, quantity, unit)
            category = row[6] or "Espèce"
            if category == "Espèce":
                key = "cash"
                detail = f"{row[2]:,.0f} DA ({row[3]})"
            else:
                key = f"nature:{row[3]}"
                qty = row[8] or 0
                unit = row[9] or "unité(s)"
                detail = f"{qty:g} {unit} de {row[7] or row[3]}"
                if row[2]:
                    detail += f" (~{row[2]:,.0f} DA)"
            tree = self.category_trees.get(key)
            if tree is None:
                # Type en nature non reconnu (ex: donnée existante avant l'ajout
                # d'une nouvelle catégorie) -> classé par défaut dans "Autre".
                tree = self.category_trees.get(f"nature:{NATURE_TYPES[-1]}")
            tree.insert("", "end", iid=str(row[0]), values=(row[1], detail, row[4]))

    def _add_donor(self):
        name = self.v_dname.get().strip()
        if not name:
            return messagebox.showerror("Erreur", "Nom obligatoire.")
        try:
            age = int(self.v_dage.get() or 0)
        except ValueError:
            return messagebox.showerror("Erreur", "L'âge doit être un entier.")
        db.add_donor(name, self.v_dphone.get().strip(), "", age)
        self.v_dname.set(""); self.v_dphone.set(""); self.v_dage.set("0")
        self.load_data()

    def _delete_donor(self):
        sel = self.donor_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un donateur à supprimer.")
        if messagebox.askyesno("Confirmation",
                               "Supprimer ce donateur ?\nSon historique de dons sera conservé."):
            db.delete_donor(int(sel[0]))
            self.load_data()

    def _add_donation(self):
        sel = self.donor_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un donateur.")

        is_nature = self.cb_category.get().startswith("Nature")
        notes = self.v_notes.get().strip()

        if not is_nature:
            try:
                amt = float(self.v_amount.get() or 0)
                if amt <= 0: raise ValueError
            except ValueError:
                return messagebox.showerror("Erreur", "Montant valide requis (> 0).")
            db.add_donation(int(sel[0]), amt, self.cb_type.get(), notes,
                            category="Espèce")
            self.v_amount.set("0")
        else:
            item_name = self.v_item_name.get().strip()
            if not item_name:
                return messagebox.showerror("Erreur", "Désignation obligatoire (ex: Riz, Cartables).")
            try:
                qty = float(self.v_quantity.get() or 0)
                if qty <= 0: raise ValueError
            except ValueError:
                return messagebox.showerror("Erreur", "Quantité valide requise (> 0).")
            try:
                est_value = float(self.v_est_value.get() or 0)
            except ValueError:
                est_value = 0
            db.add_donation(int(sel[0]), est_value, self.cb_type_nature.get(), notes,
                            category="Nature", item_name=item_name, quantity=qty,
                            unit=self.cb_unit.get())
            self.v_item_name.set(""); self.v_quantity.set("1"); self.v_est_value.set("0")

        self.v_notes.set("")
        messagebox.showinfo("Succès", "Don enregistré avec succès.")
        self.load_data()

    def _delete_donation(self, key):
        tree = self.category_trees.get(key)
        if tree is None:
            return
        sel = tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un don à supprimer.")
        if messagebox.askyesno("Confirmation", "Supprimer ce don de l'historique ?\nCette action est définitive."):
            db.delete_donation(int(sel[0]))
            self.load_data()