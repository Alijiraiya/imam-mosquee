import os
import shutil
import datetime
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import database as db
from theme import ThemeManager as TM
from widgets import entry_row, create_treeview, section_title, make_scrollable
from svf_calculator import SVFCalculator

# Dossier où sont copiés les documents joints (certificats de décès, documents
# médicaux, etc.). Le chemin est stocké en base via database.add_family_document.
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents_familles")

SCHOOLING_OPTIONS = ["Non scolarisé | غير متمدرس", "Préscolaire | تحضيري",
                     "Primaire | ابتدائي", "Moyen | متوسط", "Secondaire | ثانوي",
                     "Université | جامعي", "Formation professionnelle | تكوين مهني"]
CHILD_HEALTH_OPTIONS = ["Bonne | جيدة", "Maladie chronique | مرض مزمن", "Handicap | إعاقة"]
GENDER_OPTIONS = ["Masculin | ذكر", "Féminin | أنثى"]

# ── Nouvelles options : situation socio-professionnelle du fils/de la fille ──
WORK_TYPE_OPTIONS = ["Temporaire | مؤقت", "Saisonnier | موسمي", "Stable | مستقر"]
CHILD_MARITAL_OPTIONS = ["Célibataire | أعزب", "Marié(e) | متزوج(ة)",
                          "Divorcé(e) | مطلق(ة)", "Veuf/Veuve | أرمل(ة)"]
DEPENDENCY_OPTIONS = ["Dépend entièrement | يعتمد كلياً",
                       "Dépend partiellement | يعتمد جزئياً",
                       "Autonome | مستقل"]

# ── Critères de recherche disponibles pour la page Familles ─────────────────
# label affiché -> (clé passée à db.search_families, type de saisie, choix)
#   type "text"   -> une seule zone de texte libre
#   type "range"  -> deux zones de texte (min / max), reliées par "et"
#   type "choice" -> une liste déroulante (valeurs figées)
#   type "none"   -> aucune saisie requise, le critère seul suffit
SEARCH_FIELDS = {
    "Tout":                             ("all", "text", None),
    "Nom du Chef":                      ("head_name", "text", None),
    "Nom du conjoint(e)":               ("spouse_name", "text", None),
    "Téléphone":                        ("phone", "text", None),
    "Adresse":                          ("address", "text", None),
    "Compte CCP":                       ("postal_account", "text", None),
    "Contact d'urgence":                ("emergency_contact", "text", None),
    "Revenu (<= valeur)":               ("monthly_income", "text", None),
    "Revenu (entre X et Y)":            ("monthly_income_range", "range", None),
    "Revenu < SMIC (20k)":              ("revenu_smic", "none", None),
    "Montant du loyer (>= valeur)":     ("rent_amount_ge", "text", None),
    "Situation Sociale":                ("social_status", "text", None),
    "Situation Familiale":              ("marital_status", "text", None),
    "Type d'emploi":                    ("employment_status", "text", None),
    "Maladie / Santé":                  ("chronic_diseases", "text", None),
    "Maladies chroniques (texte libre)":("chronic_diseases_only", "text", None),
    "Locataire (Oui/Non)":              ("is_renting", "choice", ["Oui | نعم", "Non | لا"]),
    "Âge du Chef":                      ("age", "text", None),
    "Score SVF (>= valeur)":            ("svf_score", "text", None),
    "Score SVF (<= valeur)":            ("svf_score_le", "text", None),
    "Score SVF (entre X et Y)":         ("svf_score_range", "range", None),
    "Nombre de membres":                ("total_members", "text", None),
    "Nom d'un enfant":                  ("child_name", "text", None),
    "Nombre d'enfants (>= valeur)":     ("children_count_ge", "text", None),
    "Nombre d'orphelins (>= valeur)":   ("orphans_count_ge", "text", None),
    "Enfant scolarisé / non scolarisé": ("child_schooling", "choice",
                                          ["Scolarisé | متمدرس", "Non scolarisé | غير متمدرس"]),
    "Enfant qui travaille":             ("child_working", "none", None),
    "Niveau de scolarité d'un enfant":  ("child_schooling_level", "choice", SCHOOLING_OPTIONS),
}


def calc_age_from_birth_date(birth_str):
    """Calcule l'âge (en années) à partir d'une date de naissance 'JJ/MM/AAAA'.
    Renvoie '---' si la date est vide ou invalide."""
    if not birth_str:
        return "---"
    birth_str = birth_str.strip()
    parsed = None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.datetime.strptime(birth_str, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return "---"
    today = datetime.date.today()
    if parsed > today:
        return "---"
    years = today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day))
    return years


def create_toggle_switch(parent, label, initial=0):
    """Bouton à bascule remplaçant tk.Checkbutton (dont l'indicateur est
    quasi invisible sur le thème sombre de l'application). L'état est
    montré sans ambiguïté par le texte (OUI/NON) ET la couleur de fond
    (doré = coché, neutre = décoché). Se met aussi à jour automatiquement
    si la valeur est modifiée par programme (ex: préremplissage d'un
    formulaire d'édition), pas seulement au clic.
    Retourne (bouton, IntVar)."""
    var = tk.IntVar(value=initial)

    def _refresh(*_args):
        if var.get():
            btn.config(text=f"☑  {label} :  OUI | نعم",
                       bg=TM.get_color("accent"), fg="#ffffff",
                       highlightbackground=TM.get_color("accent"))
        else:
            btn.config(text=f"☐  {label} :  NON | لا",
                       bg=TM.get_color("card"), fg=TM.get_color("text_muted"),
                       highlightbackground=TM.get_color("border"))

    def _toggle():
        var.set(0 if var.get() else 1)

    btn = tk.Button(parent, font=TM.FONTS["body_b"], relief="flat",
                     cursor="hand2", anchor="w", padx=12, pady=8,
                     highlightthickness=2, command=_toggle)
    # Se rafraîchit à chaque changement de la variable, qu'il vienne du
    # clic ci-dessus ou d'un .set() fait ailleurs (ex: _prefill).
    var.trace_add("write", _refresh)
    _refresh()
    return btn, var


class FamiliesPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        # États des filtres rapides (boutons "Orphelins" / "Locataires")
        self.filter_orphans = False
        self.filter_renters = False
        self._build()

    def _build(self):
        # Page défilante (ascenseur + molette) : avec la barre de recherche,
        # les filtres et le tableau, le contenu peut dépasser la hauteur
        # visible sur les petits écrans.
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        top = tk.Frame(wrap, bg=TM.get_color("bg"))
        top.pack(fill="x", padx=15, pady=10)
        tk.Label(top, text=" Gestion des Familles | العائلات إدارة",
       
                 font=TM.FONTS["h2"], fg=TM.get_color("text"), bg=TM.get_color("bg")).pack(side="left")
        tk.Button(top, text="＋ Ajouter une Famille", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self.open_add_form).pack(side="right")

        search_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        search_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(search_frame, text="🔍 Filtrer par :", font=TM.FONTS["body"],
                 fg=TM.get_color("text_muted"), bg=TM.get_color("bg")).pack(side="left")
        self.search_field = ttk.Combobox(search_frame, values=list(SEARCH_FIELDS.keys()),
                                         state="readonly", width=30)
        self.search_field.set("Tout")
        self.search_field.pack(side="left", padx=5)
        self.search_field.bind("<<ComboboxSelected>>", lambda e: self._on_search_field_change())

        # Zone de saisie de la valeur : son contenu change selon le type du
        # critère choisi ci-dessus (texte libre / plage min-max / liste
        # déroulante / aucune saisie nécessaire).
        self.search_value_frame = tk.Frame(search_frame, bg=TM.get_color("bg"))
        self.search_value_frame.pack(side="left", padx=5, fill="x", expand=True)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.do_search())
        self.search_var2 = tk.StringVar()
        self.search_var2.trace_add("write", lambda *a: self.do_search())
        self.search_choice = tk.StringVar()
        self.search_choice.trace_add("write", lambda *a: self.do_search())

        self.entry_single = tk.Entry(self.search_value_frame, textvariable=self.search_var,
                                     font=TM.FONTS["body"], width=30)
        self.entry_range_min = tk.Entry(self.search_value_frame, textvariable=self.search_var,
                                        font=TM.FONTS["body"], width=10)
        self.lbl_range_sep = tk.Label(self.search_value_frame, text=" et ",
                                      font=TM.FONTS["body"], fg=TM.get_color("text_muted"),
                                      bg=TM.get_color("bg"))
        self.entry_range_max = tk.Entry(self.search_value_frame, textvariable=self.search_var2,
                                        font=TM.FONTS["body"], width=10)
        self.combo_choice = ttk.Combobox(self.search_value_frame, textvariable=self.search_choice,
                                         state="readonly", width=28)

        self._on_search_field_change()

        act_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        act_frame.pack(fill="x", padx=15, pady=2)
        tk.Button(act_frame, text="Modifier sélectionnée", font=TM.FONTS["small"],
                  bg=TM.get_color("card"), fg=TM.get_color("text"),
                  command=self.open_edit_form).pack(side="left", padx=2)
        tk.Button(act_frame, text="Supprimer", font=TM.FONTS["small"],
                  bg="#e74c3c", fg="#ffffff", command=self.delete_family).pack(side="left", padx=2)

        # Boutons de filtre rapide (bascule on/off à chaque clic)
        self.btn_filter_orphans = tk.Button(
            act_frame, text="👶 Familles avec orphelins", font=TM.FONTS["small"],
            bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
            command=self.toggle_filter_orphans)
        self.btn_filter_orphans.pack(side="left", padx=(12, 2))

        self.btn_filter_renters = tk.Button(
            act_frame, text="🏠 Familles locataires", font=TM.FONTS["small"],
            bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
            command=self.toggle_filter_renters)
        self.btn_filter_renters.pack(side="left", padx=2)

        self.filter_overdue = False
        self.btn_filter_overdue = tk.Button(
            act_frame, text="⏰ Sans aide depuis longtemps", font=TM.FONTS["small"],
            bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
            command=self.toggle_filter_overdue)
        self.btn_filter_overdue.pack(side="left", padx=2)

        tk.Button(act_frame, text="👨‍👦 Enfants travailleurs", font=TM.FONTS["small"],
                  bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
                  command=self.open_working_children_window).pack(side="left", padx=(12, 2))

        # ── Bannière d'alerte : familles sans aide depuis trop longtemps ────
        self.alert_banner = tk.Label(wrap, text="", font=TM.FONTS["small_b"],
                                     fg="#ffffff", bg=TM.get_color("danger"),
                                     anchor="w", padx=10, pady=6, cursor="hand2")
        self.alert_banner.bind("<Button-1>", lambda e: self._activate_overdue_filter())
        # Pas de .pack() ici : affichée seulement quand des familles sont concernées.

        cols    = ["id","name","spouse","phone","health","income","members",
                   "children","orphans","renting","svf","age"]
        headers = ["#","Nom du Chef | اسم رب الأسرة","Conjoint(e) | الزوج(ة)",
                   "Téléphone | الهاتف","État de Santé | الحالة الصحية",
                   "Revenu | الدخل","Membres","Enfants","Orphelins","Locataire",
                   "Score SVF","Âge"]
        widths  = [40, 150, 130, 95, 130, 85, 55, 55, 65, 75, 75, 50]
        self.container, self.tree = create_treeview(wrap, cols, headers, widths, height=18)
        self.container.pack(fill="both", expand=True, padx=15, pady=10)
        # Double-clic sur une ligne : ouvre la fiche complète en lecture seule
        self.tree.bind("<Double-1>", self.on_row_double_click)
        self.load_families(db.get_all_families())

    def load_families(self, rows):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for r in rows:
            # DB schema: [0]id [1]head_name [2]spouse_name [3]phone [6]income
            #            [11]members [13]health_status [15]is_renting [20]svf [22]age
            age = r[22] if len(r) > 22 else "---"
            spouse = r[2] or "---"
            health = r[13] or "---"
            children_count = db.get_children_count(r[0])
            orphan_count = db.get_orphan_children_count(r[0])
            renting_txt = "Oui | نعم" if db.family_is_renting(r[15]) else "Non | لا"
            self.tree.insert("", "end", iid=str(r[0]),
                             values=(r[0], r[1], spouse, r[3], health,
                                     f"{r[6]:,.0f} DA", r[11], children_count,
                                     orphan_count, renting_txt,
                                     f"{r[20]}%", age))

    def refresh(self):
        self.do_search()
        self._update_alert_banner()

    def _update_alert_banner(self):
        overdue = db.get_families_overdue_without_help()
        days = db.get_setting("alert_no_donation_days", 60)
        if overdue:
            self.alert_banner.config(
                text=f"⚠ {len(overdue)} famille(s) enregistrée(s) depuis plus de "
                     f"{days} jours sans avoir reçu la moindre aide — cliquer pour voir")
            self.alert_banner.pack(fill="x", padx=15, pady=(0, 4), before=self.container)
        else:
            self.alert_banner.pack_forget()

    def _activate_overdue_filter(self):
        if not self.filter_overdue:
            self.toggle_filter_overdue()

    def toggle_filter_overdue(self):
        """Active/désactive le filtre 'Familles sans aide depuis plus de X mois'."""
        self.filter_overdue = not self.filter_overdue
        self.btn_filter_overdue.config(
            bg=TM.get_color("accent") if self.filter_overdue else TM.get_color("card"),
            fg="#ffffff" if self.filter_overdue else TM.get_color("text"))
        self.do_search()

    def open_working_children_window(self):
        WorkingChildrenWindow(self)

    def toggle_filter_orphans(self):
        """Active/désactive le filtre 'Familles avec au moins un enfant orphelin'."""
        self.filter_orphans = not self.filter_orphans
        self.btn_filter_orphans.config(
            bg=TM.get_color("accent") if self.filter_orphans else TM.get_color("card"),
            fg="#ffffff" if self.filter_orphans else TM.get_color("text"))
        self.do_search()

    def toggle_filter_renters(self):
        """Active/désactive le filtre 'Familles locataires'."""
        self.filter_renters = not self.filter_renters
        self.btn_filter_renters.config(
            bg=TM.get_color("accent") if self.filter_renters else TM.get_color("card"),
            fg="#ffffff" if self.filter_renters else TM.get_color("text"))
        self.do_search()

    def _on_search_field_change(self):
        """Affiche la bonne zone de saisie (texte simple / plage / liste
        déroulante / aucune) selon le critère choisi dans le menu."""
        label = self.search_field.get()
        _, ftype, choices = SEARCH_FIELDS.get(label, ("all", "text", None))

        for w in self.search_value_frame.winfo_children():
            w.pack_forget()

        # On coupe temporairement les traces pour ne pas déclencher plusieurs
        # recherches inutiles pendant la réinitialisation des valeurs.
        self.search_var.set("")
        self.search_var2.set("")

        if ftype == "text":
            self.entry_single.pack(side="left")
        elif ftype == "range":
            self.entry_range_min.pack(side="left")
            self.lbl_range_sep.pack(side="left")
            self.entry_range_max.pack(side="left")
        elif ftype == "choice":
            self.combo_choice.config(values=choices or [])
            self.search_choice.set(choices[0] if choices else "")
            self.combo_choice.pack(side="left")
        # ftype == "none" -> aucune zone de saisie affichée

        self.do_search()

    def do_search(self):
        if not hasattr(self, "tree"):
            return  # widgets encore en construction (appel déclenché par une trace)
        label = self.search_field.get()
        field_db, ftype, _ = SEARCH_FIELDS.get(label, ("all", "text", None))

        if ftype == "range":
            term = f"{self.search_var.get().strip()}|{self.search_var2.get().strip()}"
        elif ftype == "choice":
            term = self.search_choice.get()
        elif ftype == "none":
            term = ""
        else:
            term = self.search_var.get().strip()

        rows = db.search_families(term, field_db)

        # Application des filtres rapides (cumulables avec la recherche ci-dessus)
        if self.filter_orphans:
            rows = [r for r in rows if db.get_orphan_children_count(r[0]) > 0]
        if self.filter_renters:
            rows = [r for r in rows if db.family_is_renting(r[15])]
        if self.filter_overdue:
            overdue_ids = {row[0] for row in db.get_families_overdue_without_help()}
            rows = [r for r in rows if r[0] in overdue_ids]

        self.load_families(rows)

    def on_row_double_click(self, event):
        """Double-clic sur une famille : ouvre la fiche complète en lecture seule
        (aucune modification possible depuis cette fenêtre)."""
        sel = self.tree.selection()
        if not sel:
            return
        FamilyViewWindow(self, int(sel[0]))

    def open_add_form(self):
        def _persist(data):
            new_id = db.add_family(*data)
            self.do_search()
            return new_id
        FamilyForm(self, "Ajouter une Famille", None, _persist)

    def open_edit_form(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez une famille.")
        fid = int(sel[0])
        family_data = db.fetch_one("SELECT * FROM family WHERE id=?", (fid,))
        def _persist(data):
            db.update_family(fid, *data)
            self.do_search()
            return fid
        FamilyForm(self, "Modifier la Famille", family_data, _persist)

    def delete_family(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez une famille.")
        if messagebox.askyesno("Confirmation", "Supprimer cette famille ?"):
            db.delete_family(int(sel[0]))
            self.do_search()


class FamilyViewWindow(tk.Toplevel):
    """Fenêtre affichant TOUTES les informations d'une famille (identité,
    situation sociale/financière, enfants, documents) en lecture seule.
    Aucun champ n'est modifiable ici : pour éditer, il faut utiliser
    « Modifier sélectionnée »."""

    def __init__(self, parent, family_id):
        super().__init__(parent)
        self.title("Fiche Famille | العائلة بطاقة")
        self.geometry("820x700")
        # Contrôle total sur la taille : agrandissable ET réductible
        # (bouton agrandir/plein écran de la barre de titre inclus),
        # avec une taille minimale pour ne pas casser la mise en page.
        self.resizable(True, True)
        self.minsize(680, 480)
        self.configure(bg=TM.get_color("bg"))
        self.transient(parent)
        self.grab_set()
        self._family_id = family_id
        self._p = db.fetch_one("SELECT * FROM family WHERE id=?", (family_id,))
        self._build()

    def _build(self):
        if not self._p:
            tk.Label(self, text="Famille introuvable | العائلة غير موجودة",
                     font=TM.FONTS["body_b"], fg=TM.get_color("danger"),
                     bg=TM.get_color("bg")).pack(pady=30)
            tk.Button(self, text="Fermer", command=self.destroy).pack(pady=10)
            return

        p = self._p

        tk.Label(self, text=f"👤 {p[1]}", font=TM.FONTS["title"],
                 fg=TM.get_color("accent"), bg=TM.get_color("bg")).pack(
                     anchor="w", padx=15, pady=(12, 4))

        nb = ttk.Notebook(self, style="Custom.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        t1 = tk.Frame(nb, bg=TM.get_color("card"), padx=12, pady=12)
        t2 = tk.Frame(nb, bg=TM.get_color("card"), padx=12, pady=12)
        t3 = tk.Frame(nb, bg=TM.get_color("card"), padx=12, pady=12)
        nb.add(t1, text="Identité & Contact")
        nb.add(t2, text="Situation Sociale & Financière")
        nb.add(t3, text="Enfants | الأطفال")

        renting_txt = "Oui | نعم" if db.family_is_renting(p[15]) else "Non | لا"
        age = p[22] if len(p) > 22 else "---"
        emergency = p[24] if len(p) > 24 else "---"
        needs = p[23] if len(p) > 23 and p[23] else "---"
        registration_date = p[25] if len(p) > 25 and p[25] else "---"

        identity_fields = [
            ("Nom complet du chef", p[1] or "---"),
            ("Nom du conjoint(e)", p[2] or "---"),
            ("Âge du chef", age),
            ("N° Téléphone", p[3] or "---"),
            ("Contact d'urgence", emergency or "---"),
            ("Adresse", p[4] or "---"),
            ("Compte CCP", p[5] or "---"),
            ("Enregistrée depuis le", registration_date),
        ]
        self._render_fields(t1, identity_fields)

        orphan_count = db.get_orphan_children_count(self._family_id)
        children = db.get_children_by_family(self._family_id)
        household_income = SVFCalculator.compute_household_income(p, children)
        social_fields = [
            ("Revenu du chef de famille (DA)", f"{(p[6] or 0):,.0f} DA"),
            ("Revenu total du foyer (chef + enfants travailleurs) (DA)",
             f"{household_income:,.0f} DA"),
            ("Montant loyer (DA)", f"{(p[7] or 0):,.0f} DA"),
            ("Est locataire", renting_txt),
            ("Nombre de membres", p[11]),
            ("Enfants (dont orphelins)", f"{db.get_children_count(self._family_id)} ({orphan_count})"),
            ("Situation familiale", p[10] or "---"),
            ("Situation sociale", p[12] or "---"),
            ("État de santé", p[13] or "---"),
            ("Détails maladies / cas spécifiques", p[14] or "---"),
            ("Emploi / métier du chef", p[8] or "---"),
            ("Sources secondaires de revenus", p[9] or "---"),
            ("Score SVF", f"{p[20]}%"),
            ("Besoins spécifiques", needs),
        ]
        self._render_fields(t2, social_fields)

        docs = db.get_family_documents(self._family_id)
        doc_frame = tk.Frame(t2, bg=TM.get_color("card"))
        doc_frame.pack(fill="x", pady=(10, 0))
        tk.Label(doc_frame, text=f"📎 Documents joints ({len(docs)})",
                 font=TM.FONTS["body_b"], fg=TM.get_color("accent"),
                 bg=TM.get_color("card"), anchor="w").pack(fill="x")
        if docs:
            for d in docs:
                tk.Label(doc_frame, text=f"  • {d[2]}", font=TM.FONTS["small"],
                         fg=TM.get_color("text_muted"), bg=TM.get_color("card"),
                         anchor="w").pack(fill="x")
        else:
            tk.Label(doc_frame, text="  Aucun document", font=TM.FONTS["small"],
                     fg=TM.get_color("text_muted"), bg=TM.get_color("card"),
                     anchor="w").pack(fill="x")

        cols = ["id","name","gender","birth","age","schooling","health","orphan","work","marital"]
        headers = ["#","Nom","Genre","Naissance","Âge","Scolarité","Santé","Orphelin",
                   "Travaille","État civil"]
        widths = [35, 140, 75, 95, 45, 140, 130, 80, 80, 130]
        container, tree = create_treeview(t3, cols, headers, widths, height=10)
        container.pack(fill="both", expand=True)
        for c in db.get_children_by_family(self._family_id):
            # c: [0]id [1]family_id [2]name [3]birth_date [4]schooling_status
            #    [5]health_status [6]gender [7]is_orphan [8]notes
            #    [9]is_working [10]work_type [11]monthly_revenue [12]marital_status
            #    [13]has_children [14]own_children_count [15]lives_with_family
            #    [16]is_dependent [17]is_breadwinner [18]dependency_level
            orphan = "Oui | نعم" if c[7] else "Non | لا"
            child_age = calc_age_from_birth_date(c[3])
            working = "Oui | نعم" if len(c) > 9 and c[9] else "Non | لا"
            marital = c[12] if len(c) > 12 and c[12] else "---"
            tree.insert("", "end", iid=str(c[0]),
                        values=(c[0], c[2], c[6] or "---", c[3] or "---",
                                child_age, c[4] or "---", c[5] or "---", orphan,
                                working, marital))

        tk.Button(self, text="Fermer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self.destroy).pack(fill="x", padx=15, pady=10)

    def _render_fields(self, parent, fields):
        """Affiche une liste de paires (libellé, valeur) en lecture seule,
        sous forme de lignes Label + Label (pas de champ éditable)."""
        for label, value in fields:
            row = tk.Frame(parent, bg=TM.get_color("card"))
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"{label} :", font=TM.FONTS["body_b"],
                     fg=TM.get_color("text_muted"), bg=TM.get_color("card"),
                     width=30, anchor="w", justify="left").pack(side="left", anchor="n")
            tk.Label(row, text=str(value), font=TM.FONTS["body"],
                     fg=TM.get_color("text"), bg=TM.get_color("card"),
                     anchor="w", justify="left", wraplength=320).pack(
                         side="left", fill="x", expand=True)


class WorkingChildrenWindow(tk.Toplevel):
    """Liste tous les enfants qui travaillent avec le nom du chef de famille
    (le "père" / responsable du foyer), filtrable par nom de famille."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Enfants travailleurs | العاملون الأبناء")
        self.geometry("720x520")
        self.resizable(True, True)
        self.minsize(560, 380)
        self.configure(bg=TM.get_color("bg"))
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self):
        tk.Label(self, text="👨‍👦 Enfants travailleurs, par nom de famille",
                 font=TM.FONTS["h2"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", padx=15, pady=(12, 4))

        search_row = tk.Frame(self, bg=TM.get_color("bg"))
        search_row.pack(fill="x", padx=15, pady=5)
        tk.Label(search_row, text="🔍 Nom de famille (chef) :", font=TM.FONTS["body"],
                 fg=TM.get_color("text_muted"), bg=TM.get_color("bg")).pack(side="left")
        self.v_search = tk.StringVar()
        self.v_search.trace_add("write", lambda *a: self._load())
        tk.Entry(search_row, textvariable=self.v_search, font=TM.FONTS["body"],
                 bg=TM.get_color("card"), fg=TM.get_color("text"),
                 insertbackground=TM.get_color("text"), relief="flat",
                 highlightthickness=1, highlightcolor=TM.get_color("accent"),
                 highlightbackground=TM.get_color("border")).pack(
                     side="left", padx=6, fill="x", expand=True)

        cols = ["family", "child", "work_type", "revenue"]
        headers = ["Nom de famille (chef) | اسم رب الأسرة", "Enfant qui travaille",
                   "Type de travail", "Revenu mensuel"]
        widths = [220, 180, 140, 120]
        self.container, self.tree = create_treeview(self, cols, headers, widths, height=14)
        self.container.pack(fill="both", expand=True, padx=15, pady=10)

        tk.Button(self, text="Fermer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self.destroy).pack(fill="x", padx=15, pady=10)

        self._load()

    def _load(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        term = self.v_search.get().strip()
        for child_id, child_name, work_type, revenue, family_id, head_name in db.get_working_children(term):
            self.tree.insert("", "end", iid=str(child_id),
                values=(head_name, child_name, work_type or "---",
                        f"{(revenue or 0):,.0f} DA"))


class FamilyForm(tk.Toplevel):
    def __init__(self, parent, title, profile_data, on_save):
        super().__init__(parent)
        self.title(title)
        self.geometry("720x760")
        # Contrôle total sur la taille : agrandissable ET réductible
        self.resizable(True, True)
        self.minsize(620, 500)
        self.configure(bg=TM.get_color("bg"))
        self._p = profile_data
        self._family_id = profile_data[0] if profile_data else None
        self._on_save = on_save
        # Enfants ajoutés avant que la famille existe encore en base (nouvelle famille) :
        # ils sont enregistrés automatiquement dès que la famille est créée.
        self._pending_children = []
        # Documents (PDF/photos) joints : items "pending" (pas encore sur le disque/en base)
        # ou "saved" (déjà copiés + enregistrés, avec la ligne family_document correspondante).
        self._documents = []
        self.transient(parent)
        self.grab_set()
        self._build_tabs()

    def _build_tabs(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        t1 = tk.Frame(self.nb, bg=TM.get_color("card"), padx=10, pady=10)
        t2 = tk.Frame(self.nb, bg=TM.get_color("card"), padx=10, pady=10)
        t3 = tk.Frame(self.nb, bg=TM.get_color("card"), padx=10, pady=10)
        self.nb.add(t1, text="Identité & Contact")
        self.nb.add(t2, text="Situation Sociale & Financière")
        self.nb.add(t3, text="Enfants | الأطفال")
        self._tab_identity(t1)
        self._tab_social(t2)
        self._tab_children(t3)
        tk.Button(self, text="💾 Enregistrer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", command=self._save,
                  height=2, relief="flat").pack(fill="x", padx=15, pady=10)
        if self._p:
            self._prefill()
        if self._family_id is not None:
            for row in db.get_family_documents(self._family_id):
                self._documents.append({"status": "saved", "row": row})
            self._refresh_documents_list()

    def _r(self, parent, lbl, w=20):
        return entry_row(parent, lbl, width=w)

    def _pk(self, f):
        f.pack(side="top", fill="x", pady=3)

    def _tab_identity(self, t):
        f, self.v_head_name,  _ = self._r(t, "Nom complet du chef | الاسم الكامل :"); self._pk(f)
        f, self.v_spouse_name,_ = self._r(t, "Nom du conjoint(e) :"); self._pk(f)
        f, self.v_age,        _ = self._r(t, "Âge chef | السن :", 6); self._pk(f); self.v_age.set("0")
        f, self.v_phone,      _ = self._r(t, "N° Téléphone :"); self._pk(f)
        f, self.v_emergency,  _ = self._r(t, "Contact d'urgence (nom + tél) :"); self._pk(f)
        f, self.v_address,    _ = self._r(t, "Adresse :"); self._pk(f)
        f, self.v_postal,     _ = self._r(t, "Compte CCP :"); self._pk(f)

    def _tab_social(self, t):
        f, self.v_income,  _ = self._r(t, "Revenu Mensuel (DA) :", 12); self._pk(f); self.v_income.set("0")
        f, self.v_rent,    _ = self._r(t, "Montant Loyer :", 12); self._pk(f); self.v_rent.set("0")
        f, self.v_members, _ = self._r(t, "Nombre de membres :", 6); self._pk(f); self.v_members.set("1")

        f_cb = tk.Frame(t, bg=TM.get_color("card"))
        f_cb.pack(fill="x", pady=5)

        tk.Label(f_cb, text="Situation Familiale :", bg=TM.get_color("card"),
                 fg=TM.get_color("text")).grid(row=0, column=0, sticky="w", pady=2)
        self.cb_marital = ttk.Combobox(f_cb, values=["Marié | متزوج","Veuf | أرمل(ة)",
                                                       "Veuve | أرملة","Divorcée | مطلقة",
                                                       "Célibataire | أعزب"], state="readonly")
        self.cb_marital.set("Marié | متزوج")
        self.cb_marital.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(f_cb, text="Situation Sociale :", bg=TM.get_color("card"),
                 fg=TM.get_color("text")).grid(row=1, column=0, sticky="w", pady=2)
        self.cb_social = ttk.Combobox(f_cb, values=["Aucun","Besoin Basique | حاجة أساسية",
                                                      "Sans soutien | بدون معيل",
                                                      "Famille d'Orphelins | عائلة أيتام",
                                                      "Veuve | أرملة","Divorcée | مطلقة"], state="readonly")
        self.cb_social.set("Aucun")
        self.cb_social.grid(row=1, column=1, padx=5, pady=2)

        tk.Label(f_cb, text="État de Santé :", bg=TM.get_color("card"),
                 fg=TM.get_color("text")).grid(row=2, column=0, sticky="w", pady=2)
        self.cb_health = ttk.Combobox(f_cb, values=["Bonne | جيدة",
                                                      "Maladie chronique | مرض مزمن",
                                                      "Handicap | إعاقة"], state="readonly")
        self.cb_health.set("Bonne | جيدة")
        self.cb_health.grid(row=2, column=1, padx=5, pady=2)

        doc_frame = tk.LabelFrame(t, text=" Documents justificatifs ",
                                   font=TM.FONTS["body"], fg=TM.get_color("text"), bg=TM.get_color("card"))
        doc_frame.pack(fill="x", pady=(10, 8))

        self.docs_listbox = tk.Listbox(doc_frame, height=4, font=TM.FONTS["body"],
                                        bg=TM.get_color("bg"), fg=TM.get_color("text"),
                                        selectbackground=TM.get_color("accent"),
                                        relief="flat", highlightthickness=1,
                                        highlightbackground=TM.get_color("border"))
        self.docs_listbox.pack(fill="x", padx=5, pady=(5, 2))

        doc_btns = tk.Frame(doc_frame, bg=TM.get_color("card"))
        doc_btns.pack(fill="x", padx=5, pady=(0, 5))
        tk.Button(doc_btns, text="📎 Ajouter (PDF / Image)", font=TM.FONTS["small"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._add_document).pack(side="left", padx=2)
        tk.Button(doc_btns, text="👁 Ouvrir", font=TM.FONTS["small"],
                  bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                  command=self._open_document).pack(side="left", padx=2)
        tk.Button(doc_btns, text="🗑 Retirer", font=TM.FONTS["small"],
                  bg="#e74c3c", fg="#ffffff", relief="flat",
                  command=self._remove_document).pack(side="left", padx=2)

        f, self.v_chronic,    _ = self._r(t, "Détails Maladies / Cas spécifiques :"); self._pk(f)
        f, self.v_employment, _ = self._r(t, "Emploi / Métier du chef :"); self._pk(f)
        f, self.v_src,        _ = self._r(t, "Sources secondaires de revenus :"); self._pk(f)

        self.btn_renting, self.v_renting = create_toggle_switch(
            t, "🏠 Est locataire", 0)
        self.btn_renting.pack(fill="x", pady=8)

        tk.Label(t, text="Besoins spécifiques (matériel, soins, urgences...) :",
                 font=TM.FONTS["body"], fg=TM.get_color("text_muted"),
                 bg=TM.get_color("card"), anchor="w").pack(fill="x", pady=(10, 2))
        self.txt_needs = tk.Text(t, height=4, font=TM.FONTS["body"],
                                 bg=TM.get_color("bg"), fg=TM.get_color("text"),
                                 insertbackground=TM.get_color("text"), relief="flat",
                                 highlightthickness=1, highlightcolor=TM.get_color("accent"),
                                 highlightbackground=TM.get_color("border"))
        self.txt_needs.pack(fill="x")

    def _refresh_documents_list(self):
        self.docs_listbox.delete(0, "end")
        for doc in self._documents:
            if doc["status"] == "saved":
                name = doc["row"][2]
                self.docs_listbox.insert("end", f"✅ {name}")
            else:
                self.docs_listbox.insert("end", f"⏳ {doc['name']} (sera enregistré)")

    def _add_document(self):
        path = filedialog.askopenfilename(
            title="Choisir un document ",
            filetypes=[("Documents (PDF / Images)", "*.pdf *.png *.jpg *.jpeg *.bmp *.tiff"),
                       ("PDF", "*.pdf"),
                       ("Images", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                       ("Tous les fichiers", "*.*")]
        )
        if not path:
            return
        if self._family_id is not None:
            self._store_document(self._family_id, path)
        else:
            self._documents.append({"status": "pending", "path": path, "name": os.path.basename(path)})
        self._refresh_documents_list()

    def _store_document(self, family_id, source_path):
        """Copie le fichier choisi dans le dossier documents_familles et l'enregistre en base."""
        try:
            os.makedirs(DOCS_DIR, exist_ok=True)
            original_name = os.path.basename(source_path)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S%f")
            _, ext = os.path.splitext(original_name)
            stored_name = f"famille_{family_id}_{ts}{ext}"
            stored_path = os.path.join(DOCS_DIR, stored_name)
            shutil.copy2(source_path, stored_path)
            doc_id = db.add_family_document(family_id, original_name, stored_path)
            self._documents.append({"status": "saved",
                                     "row": (doc_id, family_id, original_name, stored_path, "")})
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer le document :\n{e}")

    def _remove_document(self):
        sel = self.docs_listbox.curselection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un document.")
        idx = sel[0]
        doc = self._documents[idx]
        if not messagebox.askyesno("Confirmation", "Retirer ce document ?"):
            return
        if doc["status"] == "saved":
            doc_id, _, _, stored_path, _ = doc["row"]
            db.delete_family_document(doc_id)
            try:
                if os.path.exists(stored_path):
                    os.remove(stored_path)
            except OSError:
                pass
        del self._documents[idx]
        self._refresh_documents_list()

    def _open_document(self):
        sel = self.docs_listbox.curselection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un document.")
        doc = self._documents[sel[0]]
        path = doc["row"][3] if doc["status"] == "saved" else doc["path"]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, path])
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir ce fichier :\n{e}")

    def _tab_children(self, t):
        self._children_tab = t

        if self._family_id is None:
            tk.Label(t, text="ℹ️ Les enfants ajoutés ici seront enregistrés automatiquement "
                             "avec la famille au moment où vous cliquerez sur « Enregistrer ».",
                     font=TM.FONTS["small"], fg=TM.get_color("text_muted"),
                     bg=TM.get_color("card"), justify="left", wraplength=580).pack(fill="x", pady=(0, 8))

        top = tk.Frame(t, bg=TM.get_color("card"))
        top.pack(fill="x", pady=(0, 8))
        tk.Button(top, text="＋ Ajouter un enfant", font=TM.FONTS["small"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._add_child).pack(side="left", padx=2)
        tk.Button(top, text="Modifier", font=TM.FONTS["small"],
                  bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                  command=self._edit_child).pack(side="left", padx=2)
        tk.Button(top, text="🗑 Supprimer", font=TM.FONTS["small"],
                  bg="#e74c3c", fg="#ffffff", relief="flat",
                  command=self._delete_child).pack(side="left", padx=2)

        cols = ["id","name","gender","birth","age","schooling","health","orphan","work","marital"]
        headers = ["#","Nom","Genre","Naissance","Âge","Scolarité","Santé","Orphelin",
                   "Travaille","État civil"]
        widths = [30, 120, 65, 85, 45, 115, 110, 70, 75, 120]
        self.children_container, self.children_tree = create_treeview(
            t, cols, headers, widths, height=10)
        self.children_container.pack(fill="both", expand=True)
        self._load_children()

    def _load_children(self):
        for r in self.children_tree.get_children():
            self.children_tree.delete(r)
        if self._family_id is not None:
            for c in db.get_children_by_family(self._family_id):
                # c: [0]id [1]family_id [2]name [3]birth_date [4]schooling_status
                #    [5]health_status [6]gender [7]is_orphan [8]notes
                #    [9]is_working [10]work_type [11]monthly_revenue [12]marital_status
                #    [13]has_children [14]own_children_count [15]lives_with_family
                #    [16]is_dependent [17]is_breadwinner [18]dependency_level
                orphan = "Oui | نعم" if c[7] else "Non | لا"
                age = calc_age_from_birth_date(c[3])
                working = "Oui | نعم" if len(c) > 9 and c[9] else "Non | لا"
                marital = c[12] if len(c) > 12 and c[12] else "---"
                self.children_tree.insert("", "end", iid=str(c[0]),
                    values=(c[0], c[2], c[6] or "---", c[3] or "---", age,
                            c[4] or "---", c[5] or "---", orphan, working, marital))
        else:
            # Famille pas encore enregistrée : les enfants sont en attente en mémoire.
            # c: (name, birth_date, schooling_status, health_status, gender, is_orphan,
            #     notes, is_working, work_type, monthly_revenue, marital_status,
            #     has_children, own_children_count, lives_with_family,
            #     is_dependent, is_breadwinner, dependency_level)
            for idx, c in enumerate(self._pending_children):
                orphan = "Oui | نعم" if c[5] else "Non | لا"
                age = calc_age_from_birth_date(c[1])
                working = "Oui | نعم" if len(c) > 7 and c[7] else "Non | لا"
                marital = c[10] if len(c) > 10 and c[10] else "---"
                self.children_tree.insert("", "end", iid=f"pending_{idx}",
                    values=(f"#{idx + 1}", c[0], c[4] or "---", c[1] or "---", age,
                            c[2] or "---", c[3] or "---", orphan, working, marital))

    def _add_child(self):
        if self._family_id is not None:
            def _persist(data):
                db.add_child(self._family_id, *data)
                # Le revenu du nouvel enfant peut changer le revenu du foyer
                # (s'il travaille et est célibataire) -> recalcul du score SVF.
                SVFCalculator.recalculate_and_save(self._family_id)
                self._load_children()
            ChildForm(self, "Ajouter un enfant", None, _persist)
        else:
            def _store_pending(data):
                self._pending_children.append(data)
                self._load_children()
            ChildForm(self, "Ajouter un enfant", None, _store_pending)

    def _edit_child(self):
        sel = self.children_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un enfant.")
        iid = sel[0]
        if self._family_id is not None:
            cid = int(iid)
            child_data = db.fetch_one("SELECT * FROM child WHERE id=?", (cid,))
            def _persist(data):
                db.update_child(cid, *data)
                # Statut professionnel/marital modifié -> recalcul du score SVF.
                SVFCalculator.recalculate_and_save(self._family_id)
                self._load_children()
            ChildForm(self, "Modifier l'enfant", child_data, _persist)
        else:
            idx = int(iid.split("_")[1])
            old = self._pending_children[idx]
            # Reconstruit un tuple compatible avec ChildForm._prefill :
            # [0]id [1]family_id puis [2..18] = old (name, birth, schooling, health,
            # gender, orphan, notes, is_working, work_type, monthly_revenue,
            # marital_status, has_children, own_children_count, lives_with_family,
            # is_dependent, is_breadwinner, dependency_level)
            fake_row = (None, None) + tuple(old)
            def _update_pending(data):
                self._pending_children[idx] = data
                self._load_children()
            ChildForm(self, "Modifier l'enfant", fake_row, _update_pending)

    def _delete_child(self):
        sel = self.children_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez un enfant.")
        if not messagebox.askyesno("Confirmation", "Supprimer cet enfant ?"):
            return
        iid = sel[0]
        if self._family_id is not None:
            db.delete_child(int(iid))
            # Un enfant en moins peut changer le revenu du foyer -> recalcul.
            SVFCalculator.recalculate_and_save(self._family_id)
        else:
            idx = int(iid.split("_")[1])
            del self._pending_children[idx]
        self._load_children()

    def _prefill(self):
        p = self._p
        # DB: [1]head_name [2]spouse_name [3]phone [4]address [5]postal_account
        #     [6]income [7]rent [8]employment [9]income_sources [10]marital [11]members
        #     [12]social [13]health [14]chronic [15]is_renting [20]svf [22]age
        #     [23]specific_needs [24]emergency_contact
        self.v_head_name.set(p[1] or "")
        self.v_spouse_name.set(p[2] or "")
        self.v_phone.set(p[3] or "")
        self.v_address.set(p[4] or "")
        self.v_postal.set(p[5] or "")
        self.v_income.set(str(p[6] or 0))
        self.v_rent.set(str(p[7] or 0))
        self.v_employment.set(p[8] or "")
        self.v_src.set(p[9] or "")
        self.cb_marital.set(p[10] or "Marié | متزوج")
        self.v_members.set(str(p[11] or 1))
        self.cb_social.set(p[12] or "Aucun")
        self.cb_health.set(p[13] or "Bonne | جيدة")
        self.v_chronic.set(p[14] or "")
        # is_renting peut être "Oui | نعم" ou 0/1
        renting_val = p[15]
        self.v_renting.set(1 if str(renting_val) in ["1", "Oui | نعم", "Oui"] else 0)
        self.v_age.set(str(p[22] if len(p) > 22 else 0))
        if len(p) > 23 and p[23]:
            self.txt_needs.insert("1.0", p[23])
        if len(p) > 24:
            self.v_emergency.set(p[24] or "")

    def _save(self):
        try:
            age     = int(self.v_age.get() or 0)
            income  = float(self.v_income.get() or 0)
            rent    = float(self.v_rent.get() or 0)
            members = int(self.v_members.get() or 1)
        except ValueError:
            return messagebox.showerror("Erreur", "Champs numériques incorrects.")

        head_name    = self.v_head_name.get().strip()
        spouse_name  = self.v_spouse_name.get().strip()
        phone        = self.v_phone.get().strip()
        emergency    = self.v_emergency.get().strip()
        address      = self.v_address.get().strip()
        postal       = self.v_postal.get().strip()
        employment   = self.v_employment.get().strip()
        src          = self.v_src.get().strip()
        marital      = self.cb_marital.get()
        social       = self.cb_social.get()
        health       = self.cb_health.get()
        chronic      = self.v_chronic.get().strip()
        renting      = self.v_renting.get()
        needs        = self.txt_needs.get("1.0", "end").strip()

        if not head_name:
            return messagebox.showerror("Erreur", "Le nom du chef de famille est obligatoire.")

        if self._family_id:
            children_count = db.get_children_count(self._family_id)
        elif self._pending_children:
            children_count = len(self._pending_children)
        else:
            children_count = max(members - 1, 0)

        try:
            svf_score = SVFCalculator.calculate({
                'monthly_income': income, 'children_count': children_count,
                'social_status': social, 'health_status': health,
                'is_renting': renting, 'benefit_count': 0, 'age': age
            })

            # Matches add_family / update_family signature
            data = (head_name, spouse_name, phone, address, postal,
                    income, rent, employment, src, marital,
                    members, social, health, chronic, renting,
                    "", 0.0, 1, "", svf_score, age, needs, emergency)

            is_new = self._family_id is None
            result = self._on_save(data)
        except Exception as e:
            # Avant, une erreur ici passait inaperçue (la fenêtre restait ouverte
            # sans aucun message) : le bouton « Enregistrer » semblait ne rien faire.
            return messagebox.showerror(
                "Erreur d'enregistrement",
                f"La famille n'a pas pu être enregistrée :\n{e}"
            )

        if is_new:
            new_id = result
            if not new_id:
                messagebox.showwarning(
                    "Attention",
                    "La famille a été enregistrée, mais son identifiant n'a pas pu être "
                    "récupéré : les enfants et documents en attente n'ont pas pu être liés "
                    "automatiquement. Rouvrez la famille via « Modifier sélectionnée » pour "
                    "les ajouter."
                )
            else:
                for child_data in self._pending_children:
                    try:
                        db.add_child(new_id, *child_data)
                    except Exception as e:
                        messagebox.showwarning("Attention", f"Un enfant n'a pas pu être enregistré :\n{e}")
                for doc in self._documents:
                    if doc["status"] == "pending":
                        self._store_document(new_id, doc["path"])
                # Recalcule le score SVF avec le revenu du FOYER (chef +
                # fils/filles célibataires qui travaillent), maintenant que
                # tous les enfants en attente sont bien enregistrés en base.
                # Le score calculé plus haut (svf_score) ne tenait compte que
                # du revenu du chef ; celui-ci le remplace par la version
                # correcte via SVFCalculator.recalculate_and_save.
                SVFCalculator.recalculate_and_save(new_id)
        else:
            # Famille existante : le revenu du chef ou la situation des
            # enfants a pu changer -> on recalcule avec le revenu du foyer.
            SVFCalculator.recalculate_and_save(self._family_id)

        if hasattr(self.master, "do_search"):
            self.master.do_search()
        messagebox.showinfo("Succès", "Famille enregistrée avec succès.")
        self.destroy()


class ChildForm(tk.Toplevel):
    def __init__(self, parent, title, child_data, on_save):
        super().__init__(parent)
        self.title(title)
        # Contrôle total sur la taille : agrandissable ET réductible
        self.resizable(True, True)
        self.minsize(420, 420)
        self.configure(bg=TM.get_color("bg"))
        self._c = child_data
        self._on_save = on_save
        self.transient(parent)
        self.grab_set()
        self._build()
        if child_data:
            self._prefill()
        # La taille par défaut est calculée d'après l'écran (et non fixée en dur) :
        # sur un écran bas en résolution, une fenêtre trop haute pousserait le
        # bouton "Enregistrer" hors de la zone visible. Le contenu du formulaire
        # reste accessible grâce à l'ascenseur de la zone défilante.
        self._size_and_center()

    def _size_and_center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(520, sw - 60)
        h = min(720, sh - 100)
        x = (sw - w) // 2
        y = max(10, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # Zone défilante : le formulaire contient beaucoup de champs (identité,
        # situation professionnelle, matrimoniale, dépendance...) qui ne
        # tiennent pas toujours sur un seul écran sans ascenseur.
        outer = tk.Frame(self, bg=TM.get_color("bg"))
        outer.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        canvas = tk.Canvas(outer, bg=TM.get_color("card"), highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        wrap = tk.Frame(canvas, bg=TM.get_color("card"), padx=15, pady=15)
        wrap.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=wrap, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Molette de la souris (en plus de l'ascenseur), active seulement
        # quand le curseur survole le formulaire.
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # ── Identité de base ─────────────────────────────────────────────
        f, self.v_name, _ = entry_row(wrap, "Nom complet :"); f.pack(fill="x", pady=4)
        f, self.v_birth, _ = entry_row(wrap, "Date de naissance (JJ/MM/AAAA) :"); f.pack(fill="x", pady=4)

        self.lbl_age = tk.Label(wrap, text="Âge : ---", font=TM.FONTS["small"],
                                 fg=TM.get_color("text_muted"), bg=TM.get_color("card"), anchor="w")
        self.lbl_age.pack(fill="x", pady=(0, 4))
        self.v_birth.trace_add("write", lambda *a: self._update_age_label())

        f_g = tk.Frame(wrap, bg=TM.get_color("card")); f_g.pack(fill="x", pady=4)
        tk.Label(f_g, text="Genre :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_gender = ttk.Combobox(f_g, values=GENDER_OPTIONS, state="readonly")
        self.cb_gender.set(GENDER_OPTIONS[0])
        self.cb_gender.pack(side="left", fill="x", expand=True)

        f_s = tk.Frame(wrap, bg=TM.get_color("card")); f_s.pack(fill="x", pady=4)
        tk.Label(f_s, text="Scolarité :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_schooling = ttk.Combobox(f_s, values=SCHOOLING_OPTIONS, state="readonly")
        self.cb_schooling.set(SCHOOLING_OPTIONS[0])
        self.cb_schooling.pack(side="left", fill="x", expand=True)

        f_h = tk.Frame(wrap, bg=TM.get_color("card")); f_h.pack(fill="x", pady=4)
        tk.Label(f_h, text="État de santé :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_health = ttk.Combobox(f_h, values=CHILD_HEALTH_OPTIONS, state="readonly")
        self.cb_health.set(CHILD_HEALTH_OPTIONS[0])
        self.cb_health.pack(side="left", fill="x", expand=True)

        self.btn_orphan, self.v_orphan = create_toggle_switch(
            wrap, "👶 Enfant orphelin", 0)
        self.btn_orphan.pack(fill="x", pady=(8, 12))

        # ── Situation socio-professionnelle ──────────────────────────────
        section_title(wrap, "Situation professionnelle").pack(fill="x", pady=(4, 8))

        self.btn_working, self.v_working = create_toggle_switch(
            wrap, "💼 Travaille", 0)
        self.btn_working.pack(fill="x", pady=4)
        self.v_working.trace_add("write", lambda *a: self._toggle_work_fields())

        self.work_fields = tk.Frame(wrap, bg=TM.get_color("card"))
        f_wt = tk.Frame(self.work_fields, bg=TM.get_color("card")); f_wt.pack(fill="x", pady=4)
        tk.Label(f_wt, text="Type de travail :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_work_type = ttk.Combobox(f_wt, values=WORK_TYPE_OPTIONS, state="readonly")
        self.cb_work_type.set(WORK_TYPE_OPTIONS[0])
        self.cb_work_type.pack(side="left", fill="x", expand=True)

        f, self.v_revenue, _ = entry_row(self.work_fields,
            "Revenu mensuel (DA) :", width=12); f.pack(fill="x", pady=4)
        self.v_revenue.set("0")

        # ── Situation matrimoniale ───────────────────────────────────────
        section_title(wrap, "Situation matrimoniale").pack(fill="x", pady=(12, 8))

        f_m = tk.Frame(wrap, bg=TM.get_color("card")); f_m.pack(fill="x", pady=4)
        tk.Label(f_m, text="État civil :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_marital = ttk.Combobox(f_m, values=CHILD_MARITAL_OPTIONS, state="readonly")
        self.cb_marital.set(CHILD_MARITAL_OPTIONS[0])
        self.cb_marital.pack(side="left", fill="x", expand=True)

        self.btn_has_children, self.v_has_children = create_toggle_switch(
            wrap, "👶 A des enfants", 0)
        self.btn_has_children.pack(fill="x", pady=4)
        self.v_has_children.trace_add("write", lambda *a: self._toggle_children_fields())

        self.children_fields = tk.Frame(wrap, bg=TM.get_color("card"))
        f, self.v_own_children, _ = entry_row(self.children_fields,
            "Nombre d'enfants :", width=6); f.pack(fill="x", pady=4)
        self.v_own_children.set("0")

        self.btn_lives_with_family, self.v_lives_with_family = create_toggle_switch(
            wrap, "🏠 Vit avec la famille", 1)
        self.btn_lives_with_family.pack(fill="x", pady=4)

        # ── Dépendance / rôle dans la famille ────────────────────────────
        section_title(wrap, "Dépendance & rôle dans la famille").pack(fill="x", pady=(12, 8))

        self.btn_dependent, self.v_dependent = create_toggle_switch(
            wrap, "📌 À charge de la famille", 1)
        self.btn_dependent.pack(fill="x", pady=4)

        self.btn_breadwinner, self.v_breadwinner = create_toggle_switch(
            wrap, "💪 Soutien de famille", 0)
        self.btn_breadwinner.pack(fill="x", pady=4)

        f_d = tk.Frame(wrap, bg=TM.get_color("card")); f_d.pack(fill="x", pady=4)
        tk.Label(f_d, text="Niveau de dépendance :", bg=TM.get_color("card"), fg=TM.get_color("text"),
                 width=25, anchor="w").pack(side="left")
        self.cb_dependency = ttk.Combobox(f_d, values=DEPENDENCY_OPTIONS, state="readonly")
        self.cb_dependency.set(DEPENDENCY_OPTIONS[0])
        self.cb_dependency.pack(side="left", fill="x", expand=True)

        f, self.v_notes, _ = entry_row(wrap, "Notes / besoins particuliers :"); f.pack(fill="x", pady=(12, 4))

        self._toggle_work_fields()
        self._toggle_children_fields()

        tk.Button(self, text="💾 Enregistrer", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", command=self._save,
                  height=2, relief="flat").pack(fill="x", padx=15, pady=10)

    def _toggle_work_fields(self):
        if self.v_working.get():
            self.work_fields.pack(fill="x", pady=2, after=self.btn_working)
        else:
            self.work_fields.pack_forget()

    def _toggle_children_fields(self):
        if self.v_has_children.get():
            self.children_fields.pack(fill="x", pady=2, after=self.btn_has_children)
        else:
            self.children_fields.pack_forget()

    def _update_age_label(self):
        age = calc_age_from_birth_date(self.v_birth.get())
        self.lbl_age.config(text=f"Âge : {age} an(s)" if age != "---" else "Âge : ---")

    def _prefill(self):
        c = self._c
        # c: [0]id [1]family_id [2]name [3]birth_date [4]schooling_status
        #    [5]health_status [6]gender [7]is_orphan [8]notes
        #    [9]is_working [10]work_type [11]monthly_revenue [12]marital_status
        #    [13]has_children [14]own_children_count [15]lives_with_family
        #    [16]is_dependent [17]is_breadwinner [18]dependency_level
        self.v_name.set(c[2] or "")
        self.v_birth.set(c[3] or "")
        if c[4]:
            self.cb_schooling.set(c[4])
        if c[5]:
            self.cb_health.set(c[5])
        if len(c) > 6 and c[6]:
            self.cb_gender.set(c[6])
        if len(c) > 7:
            self.v_orphan.set(1 if c[7] else 0)
        if len(c) > 8:
            self.v_notes.set(c[8] or "")
        if len(c) > 9:
            self.v_working.set(1 if c[9] else 0)
        if len(c) > 10 and c[10]:
            self.cb_work_type.set(c[10])
        if len(c) > 11 and c[11]:
            self.v_revenue.set(str(c[11]))
        if len(c) > 12 and c[12]:
            self.cb_marital.set(c[12])
        if len(c) > 13:
            self.v_has_children.set(1 if c[13] else 0)
        if len(c) > 14 and c[14]:
            self.v_own_children.set(str(c[14]))
        if len(c) > 15:
            self.v_lives_with_family.set(1 if c[15] else 0)
        if len(c) > 16:
            self.v_dependent.set(1 if c[16] else 0)
        if len(c) > 17:
            self.v_breadwinner.set(1 if c[17] else 0)
        if len(c) > 18 and c[18]:
            self.cb_dependency.set(c[18])
        self._toggle_work_fields()
        self._toggle_children_fields()

    def _save(self):
        name = self.v_name.get().strip()
        if not name:
            return messagebox.showerror("Erreur", "Le nom de l'enfant est obligatoire.")
        try:
            revenue = float(self.v_revenue.get() or 0)
        except ValueError:
            return messagebox.showerror("Erreur", "Le revenu mensuel doit être un nombre.")
        try:
            own_children = int(self.v_own_children.get() or 0)
        except ValueError:
            return messagebox.showerror("Erreur", "Le nombre d'enfants doit être un entier.")

        data = (name, self.v_birth.get().strip(), self.cb_schooling.get(),
                self.cb_health.get(), self.cb_gender.get(), self.v_orphan.get(),
                self.v_notes.get().strip(),
                self.v_working.get(), self.cb_work_type.get(), revenue,
                self.cb_marital.get(),
                self.v_has_children.get(), own_children,
                self.v_lives_with_family.get(),
                self.v_dependent.get(), self.v_breadwinner.get(),
                self.cb_dependency.get())
        try:
            self._on_save(data)
        except Exception as e:
            return messagebox.showerror(
                "Erreur d'enregistrement",
                f"L'enfant n'a pas pu être enregistré :\n{e}"
            )
        self.destroy()