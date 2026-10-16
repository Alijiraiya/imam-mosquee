import tkinter as tk
from tkinter import ttk, messagebox
from theme import ThemeManager as TM
from widgets import entry_row, separator
import database as db
from svf_calculator import SVFCalculator
from water_filling import WaterFillingDistribution


class SettingsPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._svf_vars = {}
        self._wf_vars = {}
        self._build()

    # ── Construction générale ────────────────────────────────────────────────
    def _build(self):
        tk.Label(self, text="⚙️ Paramètres | الإعدادات",
                 font=TM.FONTS["title"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", padx=32, pady=(16, 5))
        separator(self).pack(fill="x", padx=32, pady=4)

        nb = ttk.Notebook(self, style="Custom.TNotebook")
        nb.pack(fill="both", expand=True, padx=32, pady=15)

        t_svf = tk.Frame(nb, bg=TM.get_color("card"))
        t_wf  = tk.Frame(nb, bg=TM.get_color("card"))
        t_sec = tk.Frame(nb, bg=TM.get_color("card"))
        nb.add(t_svf, text="Calcul du Score SVF")
        nb.add(t_wf,  text="Water-Filling (Distribution)")
        nb.add(t_sec, text="Sécurité & Système")

        self._build_svf_tab(t_svf)
        self._build_wf_tab(t_wf)
        self._build_security_tab(t_sec)

    def refresh(self):
        self._load_svf_values()
        self._load_wf_values()
        if hasattr(self, "v_alert_days"):
            self.v_alert_days.set(str(db.get_setting("alert_no_donation_days", 60)))

    # ── Onglet SVF ───────────────────────────────────────────────────────────
    def _build_svf_tab(self, t):
        canvas = tk.Canvas(t, bg=TM.get_color("card"), highlightthickness=0)
        vsb = ttk.Scrollbar(t, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=TM.get_color("card"))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        vsb.pack(side="right", fill="y")

        tk.Label(inner, text="Points attribués selon les critères de vulnérabilité "
                              "(le score final est plafonné entre 0 et 100).",
                 font=TM.FONTS["small"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card"), wraplength=480, justify="left").pack(
                     anchor="w", pady=(0, 10))

        self._svf_vars = {}
        for key in SVFCalculator.DEFAULTS:
            f, var, _ = entry_row(inner, SVFCalculator.LABELS[key] + " :", width=10)
            f.pack(fill="x", pady=2)
            self._svf_vars[key] = var

        btns = tk.Frame(inner, bg=TM.get_color("card"))
        btns.pack(fill="x", pady=15)
        tk.Button(btns, text="💾 Enregistrer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._save_svf).pack(side="left", padx=4)
        tk.Button(btns, text="↺ Réinitialiser par défaut", font=TM.FONTS["body_b"],
                  bg=TM.get_color("card"), fg=TM.get_color("danger"), relief="flat",
                  highlightthickness=1, highlightbackground=TM.get_color("danger"),
                  command=self._reset_svf).pack(side="left", padx=4)

        self._load_svf_values()

    def _load_svf_values(self):
        params = SVFCalculator.get_all_params()
        for key, var in self._svf_vars.items():
            var.set(str(params.get(key, SVFCalculator.DEFAULTS[key])))

    def _save_svf(self):
        try:
            values = {k: float(v.get()) for k, v in self._svf_vars.items()}
        except ValueError:
            return messagebox.showerror("Erreur", "Toutes les valeurs doivent être numériques.")
        SVFCalculator.save_params(values)
        messagebox.showinfo("Succès", "Paramètres du calcul SVF enregistrés.\n"
                                       "Les scores seront recalculés à la prochaine "
                                       "modification/ajout de famille.")

    def _reset_svf(self):
        if messagebox.askyesno("Confirmation", "Réinitialiser les paramètres SVF par défaut ?"):
            SVFCalculator.reset_defaults()
            self._load_svf_values()

    # ── Onglet Water-Filling ─────────────────────────────────────────────────
    def _build_wf_tab(self, t):
        wrap = tk.Frame(t, bg=TM.get_color("card"), padx=20, pady=20)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Paramètres de l'algorithme de distribution automatique "
                             "des aides (Water-Filling), proportionnel au score SVF.",
                 font=TM.FONTS["small"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card"), wraplength=480, justify="left").pack(
                     anchor="w", pady=(0, 15))

        self._wf_vars = {}
        for key in WaterFillingDistribution.DEFAULTS:
            f, var, _ = entry_row(wrap, WaterFillingDistribution.LABELS[key] + " :", width=10)
            f.pack(fill="x", pady=4)
            self._wf_vars[key] = var

        btns = tk.Frame(wrap, bg=TM.get_color("card"))
        btns.pack(fill="x", pady=15)
        tk.Button(btns, text="💾 Enregistrer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._save_wf).pack(side="left", padx=4)
        tk.Button(btns, text="↺ Réinitialiser par défaut", font=TM.FONTS["body_b"],
                  bg=TM.get_color("card"), fg=TM.get_color("danger"), relief="flat",
                  highlightthickness=1, highlightbackground=TM.get_color("danger"),
                  command=self._reset_wf).pack(side="left", padx=4)

        self._load_wf_values()

    def _load_wf_values(self):
        params = WaterFillingDistribution.get_all_params()
        for key, var in self._wf_vars.items():
            var.set(str(params.get(key, WaterFillingDistribution.DEFAULTS[key])))

    def _save_wf(self):
        try:
            values = {k: float(v.get()) for k, v in self._wf_vars.items()}
        except ValueError:
            return messagebox.showerror("Erreur", "Toutes les valeurs doivent être numériques.")
        if not (0 <= values["wf_reserve"] < 1):
            return messagebox.showerror("Erreur", "La réserve doit être une fraction entre 0 et 1 (ex: 0.1).")
        if values["wf_min_amt"] > values["wf_max_amt"]:
            return messagebox.showerror("Erreur", "Le montant minimum ne peut pas dépasser le maximum.")
        WaterFillingDistribution.save_params(values)
        messagebox.showinfo("Succès", "Paramètres du Water-Filling enregistrés.")

    def _reset_wf(self):
        if messagebox.askyesno("Confirmation", "Réinitialiser les paramètres Water-Filling par défaut ?"):
            WaterFillingDistribution.reset_defaults()
            self._load_wf_values()

    # ── Onglet Sécurité & Système ────────────────────────────────────────────
    def _build_security_tab(self, t):
        wrap = tk.Frame(t, bg=TM.get_color("card"), padx=20, pady=20)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Mot de passe de connexion", font=TM.FONTS["heading"],
                 fg=TM.get_color("accent"), bg=TM.get_color("card")).pack(anchor="w")

        f, self.v_old_pwd, e1 = entry_row(wrap, "Mot de passe actuel :"); f.pack(fill="x", pady=4)
        f, self.v_new_pwd, e2 = entry_row(wrap, "Nouveau mot de passe :"); f.pack(fill="x", pady=4)
        f, self.v_new_pwd2, e3 = entry_row(wrap, "Confirmer le nouveau mot de passe :"); f.pack(fill="x", pady=4)
        for e in (e1, e2, e3):
            e.config(show="●")

        tk.Button(wrap, text="🔑 Changer le mot de passe", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._change_password).pack(anchor="w", pady=10)

        separator(wrap).pack(fill="x", pady=15)

        tk.Label(wrap, text="Alertes | التنبيهات", font=TM.FONTS["heading"],
                 fg=TM.get_color("accent"), bg=TM.get_color("card")).pack(anchor="w")
        tk.Label(wrap, text="Signale toute famille enregistrée depuis plus de X jours "
                             "et n'ayant encore reçu aucune aide.",
                 font=TM.FONTS["small"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card"), wraplength=480, justify="left").pack(
                     anchor="w", pady=(2, 8))
        f, self.v_alert_days, _ = entry_row(
            wrap, "Délai sans aide avant alerte (jours) :", width=6)
        f.pack(fill="x", pady=4)
        self.v_alert_days.set(str(db.get_setting("alert_no_donation_days", 60)))
        tk.Button(wrap, text="💾 Enregistrer le délai d'alerte", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._save_alert_days).pack(anchor="w", pady=(4, 10))

        separator(wrap).pack(fill="x", pady=15)

        tk.Label(wrap, text="Base de données", font=TM.FONTS["heading"],
                 fg=TM.get_color("accent"), bg=TM.get_color("card")).pack(anchor="w")
        tk.Label(wrap, text=f"Fichier actif : {db.DB_NAME}", font=TM.FONTS["small"],
                 fg=TM.get_color("text_muted"), bg=TM.get_color("card")).pack(anchor="w", pady=(4, 10))
        tk.Button(wrap, text="💾 Sauvegarder la base de données maintenant",
                  font=TM.FONTS["body_b"], bg=TM.get_color("card"), fg=TM.get_color("text"),
                  relief="flat", highlightthickness=1,
                  highlightbackground=TM.get_color("border"),
                  command=self._backup_now).pack(anchor="w")

    def _change_password(self):
        current_password = db.get_setting("app_password", "imam1234")
        if self.v_old_pwd.get() != current_password:
            return messagebox.showerror("Erreur", "Mot de passe actuel incorrect.")
        new_pwd = self.v_new_pwd.get().strip()
        if len(new_pwd) < 4:
            return messagebox.showerror("Erreur", "Le nouveau mot de passe doit contenir au moins 4 caractères.")
        if new_pwd != self.v_new_pwd2.get().strip():
            return messagebox.showerror("Erreur", "La confirmation ne correspond pas.")
        db.set_setting("app_password", new_pwd)
        self.v_old_pwd.set(""); self.v_new_pwd.set(""); self.v_new_pwd2.set("")
        messagebox.showinfo("Succès", "Mot de passe modifié avec succès.")

    def _save_alert_days(self):
        try:
            days = float(self.v_alert_days.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erreur", "Le délai doit être un nombre supérieur à 0.")
        db.set_setting("alert_no_donation_days", days)
        messagebox.showinfo("Succès", "Délai d'alerte enregistré avec succès.")

    def _backup_now(self):
        try:
            filepath = db.backup_database()
            messagebox.showinfo("Succès", f"Sauvegarde réussie :\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Échec de la sauvegarde :\n{e}")