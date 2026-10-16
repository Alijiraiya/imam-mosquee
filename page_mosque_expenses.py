import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from theme import ThemeManager as TM
from widgets import entry_row, create_treeview, separator, make_scrollable
import database as db


def _attachments_dir():
    base = os.path.dirname(db.DB_NAME) or "."
    path = os.path.join(base, "attachments")
    os.makedirs(path, exist_ok=True)
    return path


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


class MosqueExpensesPage(tk.Frame):
    """Gestion des dépenses de fonctionnement de la mosquée : salaire de la
    femme de ménage, entretien, électricité/eau, etc. Les catégories sont
    entièrement personnalisables (ajout et suppression depuis cette page).
    Chaque dépense peut être liée à un bénéficiaire, une pièce jointe
    (photo/scan du reçu), un responsable qui valide, et une enveloppe
    budgétaire débitée (avec alerte si le solde de l'enveloppe est insuffisant)."""

    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._attachment_path = ""
        self._build()

    def _build(self):
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        tk.Label(wrap, text="🕌 Dépenses de la Mosquée | مصاريف المسجد",
                 font=TM.FONTS["title"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(anchor="w", padx=32, pady=(16, 5))
        separator(wrap).pack(fill="x", padx=32, pady=4)

        # ── Résumé ────────────────────────────────────────────────────────
        top_card = tk.Frame(wrap, bg=TM.get_color("accent"), padx=15, pady=10)
        top_card.pack(fill="x", padx=32, pady=10)
        self.lbl_total = tk.Label(top_card, text="", font=TM.FONTS["h2"],
                                  fg="#ffffff", bg=TM.get_color("accent"))
        self.lbl_total.pack(side="left")

        body = tk.Frame(wrap, bg=TM.get_color("bg"))
        body.pack(fill="both", expand=True, padx=32, pady=5)

        # ── Catégories (ajout / suppression) ────────────────────────────
        cat_frame = tk.LabelFrame(body, text=" Catégories de dépenses | فئات المصاريف ",
                                  font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                                  bg=TM.get_color("bg"), padx=10, pady=10)
        cat_frame.pack(side="top", fill="x", pady=(0, 10))

        cat_row = tk.Frame(cat_frame, bg=TM.get_color("bg"))
        cat_row.pack(fill="x", pady=4)
        f, self.v_new_cat, _ = entry_row(cat_row, "Nouvelle catégorie :")
        f.pack(side="left", fill="x", expand=True)
        tk.Button(cat_row, text="＋ Ajouter", font=TM.FONTS["small"],
                  bg=TM.get_color("accent"), fg="#ffffff", relief="flat",
                  command=self._add_category).pack(side="left", padx=6)

        cat_list_row = tk.Frame(cat_frame, bg=TM.get_color("bg"))
        cat_list_row.pack(fill="x", pady=4)
        self.cat_listbox = tk.Listbox(cat_list_row, height=5, font=TM.FONTS["body"],
                                      bg=TM.get_color("card"), fg=TM.get_color("text"),
                                      selectbackground=TM.get_color("accent"),
                                      relief="flat", highlightthickness=1,
                                      highlightbackground=TM.get_color("border"))
        self.cat_listbox.pack(side="left", fill="both", expand=True)
        tk.Button(cat_list_row, text="🗑 Supprimer la catégorie sélectionnée",
                  font=TM.FONTS["small"], bg="#e74c3c", fg="#ffffff", relief="flat",
                  command=self._delete_category).pack(side="left", padx=6, anchor="n")

        # ── Enregistrer une dépense ──────────────────────────────────────
        exp_frame = tk.LabelFrame(body, text=" Enregistrer une dépense | تسجيل مصروف ",
                                  font=TM.FONTS["body_b"], fg=TM.get_color("text"),
                                  bg=TM.get_color("bg"), padx=10, pady=10)
        exp_frame.pack(side="top", fill="x", pady=(0, 10))

        f_cat = tk.Frame(exp_frame, bg=TM.get_color("bg"))
        f_cat.pack(fill="x", pady=3)
        tk.Label(f_cat, text="Catégorie | الفئة :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text"), width=25, anchor="w").pack(side="left")
        self.cb_category = ttk.Combobox(f_cat, state="readonly")
        self.cb_category.pack(side="left", fill="x", expand=True)

        f, self.v_label, _ = entry_row(exp_frame, "Motif (ex: Remplacement robinet) :")
        f.pack(fill="x", pady=3)
        f, self.v_amount, _ = entry_row(exp_frame, "Montant (DA) :", width=12)
        f.pack(fill="x", pady=3)
        self.v_amount.set("0")

        f_ben = tk.Frame(exp_frame, bg=TM.get_color("bg"))
        f_ben.pack(fill="x", pady=3)
        tk.Label(f_ben, text="Bénéficiaire | المستفيد :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text"), width=25, anchor="w").pack(side="left")
        self.cb_beneficiary = ttk.Combobox(f_ben, width=26)  # non-readonly : saisie libre + auto-complétion
        self.cb_beneficiary.pack(side="left", fill="x", expand=True)

        f_env = tk.Frame(exp_frame, bg=TM.get_color("bg"))
        f_env.pack(fill="x", pady=3)
        tk.Label(f_env, text="Enveloppe débitée (optionnel) :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text"), width=25, anchor="w").pack(side="left")
        self.cb_envelope = ttk.Combobox(f_env, state="readonly", width=26)
        self.cb_envelope.pack(side="left", fill="x", expand=True)

        f_val = tk.Frame(exp_frame, bg=TM.get_color("bg"))
        f_val.pack(fill="x", pady=3)
        tk.Label(f_val, text="Validé par | تحقق من طرف :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text"), width=25, anchor="w").pack(side="left")
        self.v_validated_by = tk.StringVar()
        tk.Entry(f_val, textvariable=self.v_validated_by, font=TM.FONTS["body"],
                 bg=TM.get_color("bg"), fg=TM.get_color("text"), relief="flat",
                 insertbackground=TM.get_color("text"), highlightthickness=1,
                 highlightcolor=TM.get_color("accent"),
                 highlightbackground=TM.get_color("border")).pack(side="left", fill="x", expand=True)

        f, self.v_notes, _ = entry_row(exp_frame, "Description :")
        f.pack(fill="x", pady=3)

        f_att = tk.Frame(exp_frame, bg=TM.get_color("bg"))
        f_att.pack(fill="x", pady=3)
        tk.Label(f_att, text="Pièce jointe (reçu/facture) :", bg=TM.get_color("bg"),
                 fg=TM.get_color("text"), width=25, anchor="w").pack(side="left")
        self.lbl_attachment = tk.Label(f_att, text="Aucun fichier", font=TM.FONTS["small"],
                                       fg=TM.get_color("text_muted"), bg=TM.get_color("bg"))
        self.lbl_attachment.pack(side="left", padx=(0, 8))
        tk.Button(f_att, text="📎 Joindre un fichier", font=TM.FONTS["small"],
                  bg=TM.get_color("card"), fg=TM.get_color("text"), relief="flat",
                  command=self._attach_file).pack(side="left")

        tk.Button(exp_frame, text="📥 Valider la dépense", font=TM.FONTS["body_b"],
                  bg=TM.get_color("accent"), fg="#ffffff", command=self._add_expense,
                  height=2).pack(fill="x", pady=10)

        # ── Historique ────────────────────────────────────────────────────
        hist_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        hist_frame.pack(fill="both", expand=True, padx=32, pady=(0, 20))
        h_top = tk.Frame(hist_frame, bg=TM.get_color("bg"))
        h_top.pack(fill="x")
        tk.Label(h_top, text="Historique des dépenses | المصاريف سجل",
                 font=TM.FONTS["heading"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(side="left", pady=5)
        tk.Button(h_top, text="📎 Voir la pièce jointe", font=TM.FONTS["small"],
                  bg=TM.get_color("card"), fg=TM.get_color("text"),
                  command=self._view_attachment).pack(side="right", pady=5, padx=(0, 6))
        tk.Button(h_top, text="🗑 Supprimer la dépense sélectionnée", font=TM.FONTS["small"],
                  bg="#e74c3c", fg="#ffffff",
                  command=self._delete_expense).pack(side="right", pady=5)

        self.hc, self.hist_tree = create_treeview(
            hist_frame, ["category", "label", "amount", "date", "beneficiary", "envelope", "validated"],
            ["Catégorie", "Motif", "Montant", "Date", "Bénéficiaire", "Enveloppe", "Validé par"],
            [150, 150, 100, 120, 130, 110, 110], height=10)
        self.hc.pack(fill="both", expand=True)
        self._expenses_cache = []

        self.refresh()

    def refresh(self):
        self._load_categories()
        self._load_beneficiaries()
        self._load_envelopes()
        self._load_expenses()
        total = db.get_total_mosque_expenses()
        self.lbl_total.config(text=f"💸 Total dépenses mosquée : {total:,.0f} DA")

    def _load_categories(self):
        self._categories = db.get_expense_categories()  # [(id, name), ...]
        names = [c[1] for c in self._categories]
        self.cat_listbox.delete(0, "end")
        for name in names:
            self.cat_listbox.insert("end", name)
        current = self.cb_category.get()
        self.cb_category.config(values=names)
        if names and current not in names:
            self.cb_category.set(names[0])
        elif not names:
            self.cb_category.set("")

    def _load_beneficiaries(self):
        self.cb_beneficiary.config(values=db.get_known_beneficiaries())

    def _load_envelopes(self):
        self._envelopes = db.get_all_envelopes()  # [(id, name, allocated, period, threshold, desc, status), ...]
        names = ["(Aucune)"] + [e[1] for e in self._envelopes]
        self.cb_envelope.config(values=names)
        if not self.cb_envelope.get():
            self.cb_envelope.set("(Aucune)")

    def _load_expenses(self):
        for r in self.hist_tree.get_children():
            self.hist_tree.delete(r)
        self._expenses_cache = db.get_all_mosque_expenses()
        for row in self._expenses_cache:
            # row: (id, category_name, label, amount, expense_date, notes,
            #       beneficiary, attachment_path, validated_by, envelope_name)
            self.hist_tree.insert("", "end", iid=str(row[0]),
                values=(row[1], row[2], f"{row[3]:,.0f} DA", row[4],
                        row[6] or "---", row[9] or "---", row[8] or "---"))

    def _add_category(self):
        name = self.v_new_cat.get().strip()
        if not name:
            return messagebox.showerror("Erreur", "Nom de catégorie obligatoire.")
        db.add_expense_category(name)
        self.v_new_cat.set("")
        self._load_categories()

    def _delete_category(self):
        sel = self.cat_listbox.curselection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez une catégorie à supprimer.")
        name = self.cat_listbox.get(sel[0])
        cat_id = next((c[0] for c in self._categories if c[1] == name), None)
        if cat_id is None:
            return
        if messagebox.askyesno("Confirmation",
                               f"Supprimer la catégorie « {name} » ?\n"
                               "Les dépenses déjà enregistrées avec cette catégorie "
                               "seront conservées dans l'historique."):
            db.delete_expense_category(cat_id)
            self._load_categories()

    def _attach_file(self):
        path = filedialog.askopenfilename(
            title="Choisir une pièce justificative (photo, scan, PDF...)",
            filetypes=[("Images et PDF", "*.jpg *.jpeg *.png *.pdf"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        dest_dir = _attachments_dir()
        filename = f"{os.path.basename(path)}"
        dest_path = os.path.join(dest_dir, filename)
        # Évite d'écraser un fichier existant du même nom
        base, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{base}_{i}{ext}")
            i += 1
        shutil.copy2(path, dest_path)
        self._attachment_path = dest_path
        self.lbl_attachment.config(text=os.path.basename(dest_path), fg=TM.get_color("success"))

    def _view_attachment(self):
        sel = self.hist_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez une dépense.")
        row = next((r for r in self._expenses_cache if r[0] == int(sel[0])), None)
        if not row or not row[7]:
            return messagebox.showinfo("Information", "Aucune pièce jointe pour cette dépense.")
        if not os.path.exists(row[7]):
            return messagebox.showerror("Erreur", "Le fichier joint est introuvable sur le disque.")
        _open_file(row[7])

    def _selected_envelope(self):
        name = self.cb_envelope.get()
        if not name or name == "(Aucune)":
            return None
        return next((e for e in self._envelopes if e[1] == name), None)

    def _propose_exceptional_transfer(self, target_envelope, missing_amount):
        """Ouvre une petite boîte de dialogue pour choisir l'enveloppe donatrice
        et enregistrer un prélèvement exceptionnel couvrant le manque."""
        others = [e for e in self._envelopes if e[0] != target_envelope[0]]
        if not others:
            messagebox.showwarning("Attention",
                "Aucune autre enveloppe disponible pour un prélèvement exceptionnel.")
            return False

        win = tk.Toplevel(self)
        win.title("Prélèvement exceptionnel")
        win.configure(bg=TM.get_color("bg"))
        win.grab_set()
        win.geometry("420x220")

        tk.Label(win, text=f"Solde insuffisant sur « {target_envelope[1]} ».\n"
                            f"Il manque environ {missing_amount:,.0f} DA.",
                 font=TM.FONTS["body_b"], fg=TM.get_color("danger"), bg=TM.get_color("bg"),
                 wraplength=380, justify="left").pack(padx=16, pady=(16, 8), anchor="w")

        f = tk.Frame(win, bg=TM.get_color("bg"))
        f.pack(fill="x", padx=16, pady=4)
        tk.Label(f, text="Prélever depuis :", bg=TM.get_color("bg"), fg=TM.get_color("text")).pack(side="left")
        cb = ttk.Combobox(f, state="readonly", values=[e[1] for e in others])
        cb.current(0)
        cb.pack(side="left", padx=6, fill="x", expand=True)

        result = {"confirmed": False}

        def confirm():
            src_name = cb.get()
            src = next(e for e in others if e[1] == src_name)
            db.add_envelope_transfer(src[0], target_envelope[0], missing_amount,
                                     "Dépense mosquée — dépassement de budget")
            result["confirmed"] = True
            win.destroy()

        btns = tk.Frame(win, bg=TM.get_color("bg"))
        btns.pack(fill="x", padx=16, pady=16)
        tk.Button(btns, text="✅ Confirmer le prélèvement", bg=TM.get_color("accent"),
                  fg="#ffffff", relief="flat", command=confirm).pack(side="left", padx=(0, 6))
        tk.Button(btns, text="Annuler", bg=TM.get_color("card"), fg=TM.get_color("text"),
                  relief="flat", command=win.destroy).pack(side="left")

        win.wait_window()
        return result["confirmed"]

    def _add_expense(self):
        cat_name = self.cb_category.get()
        if not cat_name:
            return messagebox.showerror("Erreur", "Créez d'abord au moins une catégorie.")
        cat_id = next((c[0] for c in self._categories if c[1] == cat_name), None)
        label = self.v_label.get().strip()
        if not label:
            return messagebox.showerror("Erreur", "Le motif est obligatoire.")
        try:
            amount = float(self.v_amount.get() or 0)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erreur", "Montant valide requis (> 0).")

        envelope = self._selected_envelope()
        envelope_id = None
        if envelope:
            envelope_id = envelope[0]
            summary = next((e for e in db.get_envelope_summary() if e["id"] == envelope[0]), None)
            if summary and amount > summary["remaining"]:
                missing = amount - summary["remaining"]
                proceed = messagebox.askyesno(
                    "Solde insuffisant",
                    f"Le solde de l'enveloppe « {envelope[1]} » est insuffisant "
                    f"({summary['remaining']:,.0f} DA restants).\n\n"
                    "Voulez-vous faire un prélèvement exceptionnel depuis une autre enveloppe ?")
                if proceed:
                    if not self._propose_exceptional_transfer(envelope, missing):
                        return  # annulé par l'utilisateur dans la boîte de dialogue
                # si "Non" : on enregistre quand même la dépense (l'enveloppe passera simplement négative)

        db.add_mosque_expense(cat_id, label, amount, self.v_notes.get().strip(),
                              beneficiary=self.cb_beneficiary.get().strip(),
                              attachment_path=self._attachment_path,
                              validated_by=self.v_validated_by.get().strip(),
                              envelope_id=envelope_id)

        self.v_label.set(""); self.v_amount.set("0"); self.v_notes.set("")
        self.cb_beneficiary.set(""); self.v_validated_by.set("")
        self._attachment_path = ""
        self.lbl_attachment.config(text="Aucun fichier", fg=TM.get_color("text_muted"))
        messagebox.showinfo("Succès", "Dépense enregistrée avec succès.")
        self.refresh()

    def _delete_expense(self):
        sel = self.hist_tree.selection()
        if not sel:
            return messagebox.showwarning("Attention", "Sélectionnez une dépense à supprimer.")
        if messagebox.askyesno("Confirmation",
                               "Supprimer cette dépense de l'historique ?\nCette action est définitive."):
            db.delete_mosque_expense(int(sel[0]))
            self.refresh()