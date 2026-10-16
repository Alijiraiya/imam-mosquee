import tkinter as tk
from theme import ThemeManager as TM
from widgets import create_stat_card, section_title, separator, make_scrollable
import database as db

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class DashboardPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=TM.get_color("bg"))
        self._build()

    def _build(self):
        
        outer, wrap = make_scrollable(self)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(wrap, bg=TM.get_color("bg"))
        header.pack(fill="x", padx=32, pady=(16, 5))
        tk.Label(header, text="Tableau de bord | التحكم لوحة ",
                 font=TM.FONTS["title"], fg=TM.get_color("accent"),
                 bg=TM.get_color("bg")).pack(side="left")
        tk.Label(header, text=" الرحيم الرحمان الله بسم",
                 font=("Georgia", 13, "italic"), fg=TM.get_color("text_muted"),
                 bg=TM.get_color("bg")).pack(side="right")

        separator(wrap).pack(fill="x", padx=32, pady=4)

        self.cards_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        self.cards_frame.pack(fill="x", padx=32, pady=10)
        for i in range(6):
            self.cards_frame.columnconfigure(i, weight=1)

        # ── Bannière d'alerte : familles sans aide depuis trop longtemps ────
        # (pas de .pack() ici : affichée seulement si des familles sont concernées,
        # voir _update_alert_banner)
        self.alert_banner = tk.Label(wrap, text="", font=TM.FONTS["small_b"],
                                     fg="#ffffff", bg=TM.get_color("danger"),
                                     anchor="w", padx=10, pady=6)

        self.balance_label = tk.Label(wrap, text="",
                                      font=("Georgia", 14, "bold"),
                                      fg=TM.get_color("success"), bg=TM.get_color("bg"))
        self.balance_label.pack(fill="x", padx=32, pady=4)

        # ── Zone graphiques (camembert + histogramme) ──────────────────────
        charts_frame = tk.Frame(wrap, bg=TM.get_color("bg"))
        charts_frame.pack(fill="both", expand=True, padx=32, pady=6)
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)

        card_bg = TM.get_color("card")
        text_col = TM.get_color("text")

        pie_card = tk.Frame(charts_frame, bg=card_bg, highlightthickness=1,
                            highlightbackground=TM.get_color("border"))
        pie_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        bar_card = tk.Frame(charts_frame, bg=card_bg, highlightthickness=1,
                            highlightbackground=TM.get_color("border"))
        bar_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.fig_pie = Figure(figsize=(4.2, 2.8), dpi=90, facecolor=card_bg)
        self.ax_pie = self.fig_pie.add_subplot(111)
        self.canvas_pie = FigureCanvasTkAgg(self.fig_pie, master=pie_card)
        self.canvas_pie.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        self.fig_bar = Figure(figsize=(4.2, 2.8), dpi=90, facecolor=card_bg)
        self.ax_bar = self.fig_bar.add_subplot(111)
        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=bar_card)
        self.canvas_bar.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)

        self._chart_text_color = text_col
        self._card_bg = card_bg

        act_frame = tk.Frame(wrap, bg=TM.get_color("card"),
                             highlightthickness=1,
                             highlightbackground=TM.get_color("border"))
        act_frame.pack(fill="both", expand=True, padx=32, pady=10)
        section_title(act_frame, "Activité récente | الأخير النشاط ").pack(
            fill="x", padx=16, pady=(10, 4))
        self.activity_text = tk.Text(act_frame, bg=TM.get_color("card"),
                                     fg=TM.get_color("text"), font=TM.FONTS["mono"],
                                     relief="flat", state="disabled", height=7,
                                     highlightthickness=0)
        self.activity_text.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    def refresh(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()

        stats = db.get_stats()

        for i, (title, key) in enumerate([
            ("Familles | العائلات",   "families"),
            ("Enfants | الأطفال",     "children"),
            ("Donateurs | المتبرعون", "donors"),
            ("Dons | التبرعات",       "donations"),
            ("Dons en nature | عيني", "donations_nature"),
            ("Dépenses mosquée | مصاريف", "total_mosque_expenses"),
        ]):
            value = stats[key]
            display = f"{value:,.0f} DA" if key == "total_mosque_expenses" else value
            c = create_stat_card(self.cards_frame, title, display)
            c.grid(row=0, column=i, sticky="nsew", padx=5)

        bal = stats["balance"]
        self.balance_label.config(
            fg=TM.get_color("success") if bal >= 0 else TM.get_color("danger"),
            text=(f"💰 Entrées : {stats['total_in']:,.0f} DA   ||   "
                  f"📤 Sorties (distributions {stats['total_distributions']:,.0f} DA "
                  f"+ mosquée {stats['total_mosque_expenses']:,.0f} DA "
                  f"+ paiements {stats['total_payments']:,.0f} DA) : "
                  f"{stats['total_out']:,.0f} DA   ||   "
                  f"⚖️ Solde : {bal:,.0f} DA"))

        self._update_alert_banner()

        self._draw_pie_chart()
        self._draw_bar_chart()

        lines = []
        for r in db.get_all_donations()[:6]:
            # r: (id, donor_name, amount, donation_type, donation_date, notes,
            #     category, item_name, quantity, unit)
            category = r[6] or "Espèce"
            if category == "Espèce":
                lines.append(f"➕ Don de {r[1]} : {r[2]:,.0f} DA ({r[4]})")
            else:
                qty = r[8] or 0
                unit = r[9] or "unité(s)"
                lines.append(f"➕ Don de {r[1]} : {qty:g} {unit} de {r[7] or r[3]} ({r[4]})")
        for r in db.get_all_distributions()[:6]:
            # r: (id, head_name, amount, distribution_type, distribution_date, notes)
            lines.append(f"➖ Aide à {r[1]} : {r[2]:,.0f} DA ({r[4]})")
        lines.sort(reverse=True)

        self.activity_text.config(state="normal")
        self.activity_text.delete("1.0", "end")
        self.activity_text.insert("end",
            "\n".join(lines[:12]) if lines else "Aucune activité récente | لا يوجد نشاط")
        self.activity_text.config(state="disabled")

    def _update_alert_banner(self):
        overdue = db.get_families_overdue_without_help()
        days = db.get_setting("alert_no_donation_days", 60)
        if overdue:
            self.alert_banner.config(
                text=f"⚠ {len(overdue)} famille(s) enregistrée(s) depuis plus de "
                     f"{days} jours sans avoir reçu la moindre aide — voir la page Familles")
            self.alert_banner.pack(fill="x", padx=32, pady=(0, 4), before=self.balance_label)
        else:
            self.alert_banner.pack_forget()

    def _draw_pie_chart(self):
        self.ax_pie.clear()
        data = db.get_social_status_distribution()
        text_col = self._chart_text_color
        self.ax_pie.set_facecolor(self._card_bg)
        if data:
            labels = [d[0] for d in data]
            sizes = [d[1] for d in data]
            colors = ["#C9A84C", "#1E7F6E", "#C0392B", "#27AE60", "#7A8899", "#8E44AD"]
            wedges, _, autotexts = self.ax_pie.pie(
                sizes, labels=None, autopct="%1.0f%%", textprops={"fontsize": 8, "color": text_col},
                colors=colors[:len(sizes)])
            self.ax_pie.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5),
                               fontsize=7, facecolor=self._card_bg, labelcolor=text_col,
                               frameon=False)
        else:
            self.ax_pie.text(0.5, 0.5, "Aucune donnée", ha="center", va="center", color=text_col)
        self.ax_pie.set_title("Familles par situation sociale | حسب الوضع الاجتماعي",
                              fontsize=9, color=text_col)
        self.fig_pie.tight_layout()
        self.canvas_pie.draw()

    def _draw_bar_chart(self):
        self.ax_bar.clear()
        text_col = self._chart_text_color
        self.ax_bar.set_facecolor(self._card_bg)
        rows = db.get_monthly_financial_summary(6)
        if rows:
            months = [r[0] for r in rows]
            ins = [r[1] for r in rows]
            outs = [r[2] for r in rows]
            x = range(len(months))
            width = 0.35
            self.ax_bar.bar([i - width / 2 for i in x], ins, width,
                            label="Entrées", color="#27AE60")
            self.ax_bar.bar([i + width / 2 for i in x], outs, width,
                            label="Sorties", color="#C0392B")
            self.ax_bar.set_xticks(list(x))
            self.ax_bar.set_xticklabels(months, fontsize=7, rotation=30, color=text_col)
            self.ax_bar.tick_params(axis="y", labelsize=7, colors=text_col)
            self.ax_bar.legend(fontsize=7, facecolor=self._card_bg, labelcolor=text_col, frameon=False)
        else:
            self.ax_bar.text(0.5, 0.5, "Aucune donnée", ha="center", va="center", color=text_col)
        self.ax_bar.set_title("Entrées / Sorties (6 derniers mois) | آخر 6 أشهر",
                              fontsize=9, color=text_col)
        for spine in self.ax_bar.spines.values():
            spine.set_color(TM.get_color("border"))
        self.fig_bar.tight_layout()
        self.canvas_bar.draw()