import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from theme import ThemeManager as TM
from widgets import entry_row, separator, make_scrollable, create_button
import database as db
import report_generator as rg


def _open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Erreur", f"Impossible d'ouvrir le fichier :\n{e}")


MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
             "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


class ReportsPage(tk.Frame):
    """Module « Rapports & Export » : génération en un clic des rapports PDF
    prévus au cahier des charges (mensuel, annuel, relevé de caisse, par
    enveloppe, par bénéficiaire), avec ouverture directe du fichier généré."""

    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._last_file = None
        self._build()

    def _build(self):
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        tk.Label(wrap, text="📄 Rapports & Export | التقارير والتصدير",
                 font=TM.FONTS["title"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", padx=32, pady=(16, 5))
        separator(wrap).pack(fill="x", padx=32, pady=4)

        self.status_label = tk.Label(wrap, text="", font=TM.FONTS["body_b"],
                                     fg=TM.get_color("success"), bg=TM.get_color("bg"),
                                     wraplength=700, justify="left")
        self.status_label.pack(fill="x", padx=32, pady=(6, 0))
        self.open_btn = tk.Button(wrap, text="📂 Ouvrir le dernier rapport généré",
                                  font=TM.FONTS["small_b"], bg=TM.get_color("accent"),
                                  fg="#ffffff", relief="flat", command=self._open_last, state="disabled")
        self.open_btn.pack(anchor="w", padx=32, pady=(4, 10))

        # ── Rapport mensuel ──────────────────────────────────────────────────
        m_box = tk.LabelFrame(wrap, text=" Rapport mensuel | تقرير شهري ",
                              font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                              bg=TM.get_color("bg"), padx=10, pady=10)
        m_box.pack(fill="x", padx=32, pady=(0, 10))
        f_m = tk.Frame(m_box, bg=TM.get_color("bg"))
        f_m.pack(fill="x", pady=3)
        tk.Label(f_m, text="Mois :", bg=TM.get_color("bg"), fg=TM.get_color("text")).pack(side="left")
        self.cb_month = ttk.Combobox(f_m, state="readonly", values=MONTHS_FR, width=14)
        self.cb_month.current(datetime.now().month - 1)
        self.cb_month.pack(side="left", padx=6)
        tk.Label(f_m, text="Année :", bg=TM.get_color("bg"), fg=TM.get_color("text")).pack(side="left", padx=(12, 0))
        self.v_month_year = tk.StringVar(value=str(datetime.now().year))
        tk.Entry(f_m, textvariable=self.v_month_year, width=8, font=TM.FONTS["body"],
                 bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
                 insertbackground=TM.get_color("text")).pack(side="left", padx=6)
        create_button(m_box, "📄 Générer le rapport mensuel", self._gen_monthly).pack(anchor="w", pady=6)

        # ── Rapport annuel ───────────────────────────────────────────────────
        a_box = tk.LabelFrame(wrap, text=" Rapport annuel | تقرير سنوي ",
                              font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                              bg=TM.get_color("bg"), padx=10, pady=10)
        a_box.pack(fill="x", padx=32, pady=(0, 10))
        f_a = tk.Frame(a_box, bg=TM.get_color("bg"))
        f_a.pack(fill="x", pady=3)
        tk.Label(f_a, text="Année :", bg=TM.get_color("bg"), fg=TM.get_color("text")).pack(side="left")
        self.v_year = tk.StringVar(value=str(datetime.now().year))
        tk.Entry(f_a, textvariable=self.v_year, width=8, font=TM.FONTS["body"],
                 bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
                 insertbackground=TM.get_color("text")).pack(side="left", padx=6)
        create_button(a_box, "📄 Générer le rapport annuel", self._gen_annual).pack(anchor="w", pady=6)

        # ── Relevé de caisse ─────────────────────────────────────────────────
        c_box = tk.LabelFrame(wrap, text=" Relevé de caisse (période) | كشف الصندوق ",
                              font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                              bg=TM.get_color("bg"), padx=10, pady=10)
        c_box.pack(fill="x", padx=32, pady=(0, 10))
        f, self.v_from, _ = entry_row(c_box, "Du (AAAA-MM-JJ, optionnel) :"); f.pack(fill="x", pady=2)
        f, self.v_to, _ = entry_row(c_box, "Au (AAAA-MM-JJ, optionnel) :"); f.pack(fill="x", pady=2)
        create_button(c_box, "📄 Générer le relevé de caisse", self._gen_caisse).pack(anchor="w", pady=6)



    def refresh(self):
        pass

    def _finish(self, filepath):
        self._last_file = filepath
        self.open_btn.config(state="normal")
        self.status_label.config(
            text=f"✅ Rapport généré avec succès : {filepath}")
        messagebox.showinfo("Succès", f"Rapport généré :\n{filepath}")

    def _open_last(self):
        if self._last_file and os.path.exists(self._last_file):
            _open_file(self._last_file)

    def _gen_monthly(self):
        try:
            year = int(self.v_month_year.get())
            month = self.cb_month.current() + 1
            filepath = rg.generate_monthly_report(year, month)
            self._finish(filepath)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de la génération du rapport :\n{e}")

    def _gen_annual(self):
        try:
            year = int(self.v_year.get())
            filepath = rg.generate_annual_report(year)
            self._finish(filepath)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de la génération du rapport :\n{e}")

    def _gen_caisse(self):
        try:
            date_from = self.v_from.get().strip() or None
            date_to = self.v_to.get().strip() or None
            filepath = rg.generate_caisse_statement(date_from, date_to)
            self._finish(filepath)
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de la génération du relevé :\n{e}")