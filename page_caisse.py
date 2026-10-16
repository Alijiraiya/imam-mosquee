import tkinter as tk
from tkinter import ttk
from theme import ThemeManager as TM
from widgets import create_treeview, entry_row, separator, make_scrollable, create_stat_card
import database as db


class CaissePage(tk.Frame):
    """Journal de caisse détaillé : vue chronologique unifiée de TOUS les
    mouvements financiers (dons en espèce, distributions, dépenses mosquée,
    paiements aux bénéficiaires), avec solde cumulé après chaque opération,
    filtrage par période et recherche textuelle dans le libellé."""

    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._build()

    def _build(self):
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        tk.Label(wrap, text="🧾 Journal de Caisse | سجل الصندوق",
                 font=TM.FONTS["title"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", padx=32, pady=(16, 5))
        separator(wrap).pack(fill="x", padx=32, pady=4)

        # ── Widget solde en temps réel ──────────────────────────────────────
        self.cards_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        self.cards_frame.pack(fill="x", padx=32, pady=10)
        for i in range(4):
            self.cards_frame.columnconfigure(i, weight=1)

        # ── Filtres ──────────────────────────────────────────────────────────
        filt = tk.Frame(wrap, bg=TM.get_color("card"), padx=12, pady=10)
        filt.pack(fill="x", padx=32, pady=(0, 10))

        tk.Label(filt, text="Du :", font=TM.FONTS["body"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card")).pack(side="left")
        self.v_from = tk.StringVar()
        tk.Entry(filt, textvariable=self.v_from, width=12, font=TM.FONTS["body"],
                 bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                 insertbackground=TM.get_color("text")).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="Au :", font=TM.FONTS["body"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card")).pack(side="left")
        self.v_to = tk.StringVar()
        tk.Entry(filt, textvariable=self.v_to, width=12, font=TM.FONTS["body"],
                 bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                 insertbackground=TM.get_color("text")).pack(side="left", padx=(4, 12))

        tk.Label(filt, text="(AAAA-MM-JJ, laisser vide pour tout afficher)",
                 font=TM.FONTS["small"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card")).pack(side="left", padx=(0, 16))

        tk.Label(filt, text="Recherche :", font=TM.FONTS["body"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card")).pack(side="left")
        self.v_search = tk.StringVar()
        e_search = tk.Entry(filt, textvariable=self.v_search, width=20, font=TM.FONTS["body"],
                            bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                            insertbackground=TM.get_color("text"))
        e_search.pack(side="left", padx=(4, 12), fill="x", expand=True)
        e_search.bind("<Return>", lambda e: self._apply_filters())

        tk.Button(filt, text="🔍 Filtrer", font=TM.FONTS["small_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._apply_filters).pack(side="left", padx=(0, 6))
        tk.Button(filt, text="↺ Réinitialiser", font=TM.FONTS["small"],
                  bg=TM.get_color("bg"), fg=TM.get_color("text_muted"), relief="flat",
                  command=self._reset_filters).pack(side="left")

        # ── Totaux de la vue filtrée ─────────────────────────────────────────
        self.lbl_totals = tk.Label(wrap, text="", font=TM.FONTS["body_b"],
                                   fg=TM.get_color("text"), bg=TM.get_color("bg"), anchor="w")
        self.lbl_totals.pack(fill="x", padx=32)

        # ── Journal (tableau) ────────────────────────────────────────────────
        journal_card = tk.Frame(wrap, bg=TM.get_color("card"), highlightthickness=1,
                                highlightbackground=TM.get_color("border"))
        journal_card.pack(fill="both", expand=True, padx=32, pady=(6, 20))

        self.jc, self.tree = create_treeview(
            journal_card, ["date", "libelle", "entree", "sortie", "solde", "type"],
            ["Date", "Libellé", "Entrée (+)", "Sortie (−)", "Solde cumulé", "Type"],
            [130, 260, 110, 110, 120, 90], height=18)
        self.jc.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.tag_configure("in", foreground=TM.get_color("success"))
        self.tree.tag_configure("out", foreground=TM.get_color("danger"))

    def _apply_filters(self):
        self._load(self.v_from.get().strip() or None,
                   self.v_to.get().strip() or None,
                   self.v_search.get().strip())

    def _reset_filters(self):
        self.v_from.set(""); self.v_to.set(""); self.v_search.set("")
        self._load()

    def refresh(self):
        self._load_widget()
        self._load()

    def _load_widget(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        stats = db.get_caisse_widget_stats()
        arrow = "↑" if stats["variation_pct"] >= 0 else "↓"
        cards = [
            ("Solde disponible | الرصيد", f"{stats['solde']:,.0f} DA"),
            ("Entrées du mois | الدخول", f"{stats['entrees_mois']:,.0f} DA"),
            ("Sorties du mois | الخروج", f"{stats['sorties_mois']:,.0f} DA"),
            ("Variation vs mois précédent", f"{arrow} {abs(stats['variation_pct']):.0f}%"),
        ]
        for i, (title, value) in enumerate(cards):
            c = create_stat_card(self.cards_frame, title, value)
            c.grid(row=0, column=i, sticky="nsew", padx=5)

    def _load(self, date_from=None, date_to=None, search=""):
        for r in self.tree.get_children():
            self.tree.delete(r)
        rows = db.get_caisse_journal(date_from, date_to, search)
        total_in = total_out = 0.0
        type_labels = {"don": "Don", "distribution": "Distribution",
                       "depense": "Dépense", "paiement": "Paiement"}
        for date, libelle, entree, sortie, solde, mtype in rows:
            total_in += entree
            total_out += sortie
            tag = "in" if entree > 0 else "out"
            self.tree.insert("", "end", values=(
                date, libelle,
                f"{entree:,.0f} DA" if entree else "",
                f"{sortie:,.0f} DA" if sortie else "",
                f"{solde:,.0f} DA",
                type_labels.get(mtype, mtype)
            ), tags=(tag,))
        self.lbl_totals.config(
            text=f"Vue filtrée — {len(rows)} mouvement(s)  |  "
                 f"Total entrées : {total_in:,.0f} DA  |  "
                 f"Total sorties : {total_out:,.0f} DA  |  "
                 f"Net : {total_in - total_out:,.0f} DA")