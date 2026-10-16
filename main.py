import tkinter as tk
from tkinter import messagebox
from theme import ThemeManager as TM
import database as db
from login import LoginWindow
from page_dashboard import DashboardPage
from page_families import FamiliesPage
from page_donations import DonationsPage
from page_distributions import DistributionsPage
from page_settings import SettingsPage
from page_mosque_expenses import MosqueExpensesPage
from page_caisse import CaissePage
from page_reports import ReportsPage
import generate_bulk_test_data

class CharityApp(tk.Tk):
    PAGES = [
        ("🏠 Accueil | لوحة التحكم",          "dashboard"),
        ("👨‍👩‍👧 Familles | العائلات",            "families"),
        ("💰 Dons | التبرعات",                 "donations"),
        ("📤 Distributions | توزيع المساعدات", "distributions"),
        ("🧾 Journal de Caisse | سجل الصندوق", "caisse"),
        ("🕌 Dépenses Mosquée | مصاريف المسجد", "mosque_expenses"),
        ("📄 Rapports | التقارير",              "reports"),
        ("⚙️ Paramètres | الإعدادات",          "settings"),
    ]

    def __init__(self):
        super().__init__()
        self.title("Logiciel de l'Imam | برنامج الإمام لإدارة التبرعات")
        self.geometry("1024x720")
        self.minsize(900, 600)
        try:
            self.state('zoomed')
        except:
            self.attributes('-zoomed', True)

        self.configure(bg=TM.get_color("bg"))
        db.initialize_database()
        self._seed_demo_data_if_empty()

        self._pages = {}
        self._current = None

        self._build_shell()
        self.withdraw()
        self.after(100, lambda: LoginWindow(self, self._on_auth))

    # ── Données de démonstration (premier lancement) ───────────────────────
    def _seed_demo_data_if_empty(self):
        """Si la base de données est totalement vide (aucune famille), on la
        remplit automatiquement avec un jeu de données fictif complet, pour
        que l'interface ne s'affiche jamais vide au premier lancement.
        Ne s'exécute qu'une seule fois (marqueur enregistré dans settings) et
        ne touche JAMAIS à des données déjà présentes."""
        try:
            already_seeded = db.get_setting("demo_data_seeded", "0") == "1"
            has_families = len(db.get_all_families()) > 0
            if already_seeded or has_families:
                return
            generate_bulk_test_data.generate(verbose=False)
            db.set_setting("demo_data_seeded", "1")
        except Exception as e:
            # Ne doit jamais empêcher le démarrage de l'application.
            print(f"Avertissement : génération des données de démo échouée : {e}")

    # ── Shell (sidebar + content frame) ──────────────────────────────────────
    def _build_shell(self):
        # PanedWindow horizontal : la barre entre le menu et le contenu peut
        # être glissée à la souris pour élargir/rétrécir le menu (et donc
        # agrandir le tableau à droite), au lieu d'une largeur figée.
        self.paned = tk.PanedWindow(self, orient="horizontal",
                                    bg=TM.get_color("border"),
                                    sashwidth=6, sashrelief="raised",
                                    sashpad=0, showhandle=False,
                                    borderwidth=0, opaqueresize=False)
        self.paned.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(self.paned, bg=TM.get_color("sidebar"))
        self.sidebar.pack_propagate(False)
        self.paned.add(self.sidebar, width=TM.SIZES["sidebar_w"], minsize=160)

        self.lbl_logo = tk.Label(self.sidebar, text="🕌", font=("", 34),
                                 bg=TM.get_color("sidebar"), fg=TM.get_color("accent"))
        self.lbl_logo.pack(pady=(24, 0))

        self.lbl_title = tk.Label(self.sidebar,
                                  text="Gestion des Dons\n التبرعات إدارة ",
                                  font=TM.FONTS["heading"],
                                  fg=TM.get_color("accent"),
                                  bg=TM.get_color("sidebar"))
        self.lbl_title.pack(pady=(4, 20))

        self._nav_buttons = {}
        for lbl, key in self.PAGES:
            btn = tk.Button(self.sidebar, text=lbl,
                            font=TM.FONTS["body_b"],
                            fg=TM.get_color("text_muted"),
                            bg=TM.get_color("sidebar"),
                            relief="flat", cursor="hand2",
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", pady=2)
            self._nav_buttons[key] = btn

        self.theme_btn = tk.Button(self.sidebar, text="🌓 Thème | المظهر",
                                   font=TM.FONTS["small"],
                                   fg=TM.get_color("text_muted"),
                                   bg=TM.get_color("sidebar"),
                                   relief="flat", command=self.toggle_theme)
        self.theme_btn.pack(side="bottom", pady=4)

        self.backup_btn = tk.Button(self.sidebar, text="💾 Sauvegarde | نسخ احتياطي",
                                    font=TM.FONTS["small"],
                                    fg=TM.get_color("text_muted"),
                                    bg=TM.get_color("sidebar"),
                                    relief="flat", command=self._backup)
        self.backup_btn.pack(side="bottom", pady=4)

        self.quit_btn = tk.Button(self.sidebar, text="⏻ Quitter | خروج",
                                  font=TM.FONTS["small"],
                                  fg=TM.get_color("danger"),
                                  bg=TM.get_color("sidebar"),
                                  relief="flat", command=self.destroy)
        self.quit_btn.pack(side="bottom", pady=8)

        self.content = tk.Frame(self.paned, bg=TM.get_color("bg"))
        self.paned.add(self.content, minsize=400, stretch="always")

    # ── Après login ──────────────────────────────────────────────────────────
    def _on_auth(self):
        self.deiconify()
        TM.apply_ttk_styles()
        self._build_pages()
        self.show_page("dashboard")

    # ── Construction des pages ───────────────────────────────────────────────
    def _build_pages(self):
        # Détruire les anciennes pages
        for p in self._pages.values():
            p.destroy()

        # S'assurer que content a la bonne couleur de fond
        self.content.configure(bg=TM.get_color("bg"))

        self._pages = {
            "dashboard":     DashboardPage(self.content),
            "families":      FamiliesPage(self.content),
            "donations":     DonationsPage(self.content),
            "distributions": DistributionsPage(self.content),
            "caisse":        CaissePage(self.content),
            "mosque_expenses": MosqueExpensesPage(self.content),
            "reports":       ReportsPage(self.content),
            "settings":      SettingsPage(self.content),
        }
        for page in self._pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

    # ── Navigation ───────────────────────────────────────────────────────────
    def show_page(self, key):
        if self._current == key:
            return
        for k, btn in self._nav_buttons.items():
            btn.config(
                fg=TM.get_color("accent") if k == key else TM.get_color("text_muted"),
                bg=TM.get_color("card")   if k == key else TM.get_color("sidebar")
            )
        self._pages[key].refresh()
        self._pages[key].lift()
        self._current = key

    # ── Changement de thème ──────────────────────────────────────────────────
    def toggle_theme(self):
        TM.toggle_theme()

        # Mettre à jour le shell
        self.config(bg=TM.get_color("bg"))
        self.paned.config(bg=TM.get_color("border"))
        self.content.config(bg=TM.get_color("bg"))
        self.sidebar.config(bg=TM.get_color("sidebar"))
        self.lbl_logo.config(bg=TM.get_color("sidebar"), fg=TM.get_color("accent"))
        self.lbl_title.config(bg=TM.get_color("sidebar"), fg=TM.get_color("accent"))
        self.theme_btn.config(bg=TM.get_color("sidebar"), fg=TM.get_color("text_muted"))
        self.backup_btn.config(bg=TM.get_color("sidebar"), fg=TM.get_color("text_muted"))
        self.quit_btn.config(bg=TM.get_color("sidebar"), fg=TM.get_color("danger"))
        for btn in self._nav_buttons.values():
            btn.config(bg=TM.get_color("sidebar"), fg=TM.get_color("text_muted"))

        # Forcer le reset de la page courante AVANT de reconstruire
        current = self._current
        self._current = None

        # Reconstruire toutes les pages avec le nouveau thème
        self._build_pages()

        # Réafficher la bonne page
        self.show_page(current or "dashboard")

    # ── Sauvegarde ───────────────────────────────────────────────────────────
    def _backup(self):
        try:
            filepath = db.backup_database()
            messagebox.showinfo("Succès | نجاح",
                                f"Sauvegarde réussie :\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erreur | خطأ",
                                 f"Échec de la sauvegarde :\n{e}")


if __name__ == "__main__":
    app = CharityApp()
    app.mainloop()

    