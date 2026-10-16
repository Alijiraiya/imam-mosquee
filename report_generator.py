# -*- coding: utf-8 -*-
"""
report_generator.py
----------------------
Module « Rapports & Export ». Génère les rapports PDF prévus au cahier des
charges à partir des données de la base (via database.py) :

    - Rapport mensuel        : generate_monthly_report(year, month)
    - Rapport annuel         : generate_annual_report(year)
    - Relevé de caisse       : generate_caisse_statement(date_from, date_to)
    - Rapport par enveloppe  : generate_envelope_report(envelope_id)
    - Rapport bénéficiaire   : generate_payee_report(payee_id)

Chaque fonction retourne le chemin du fichier PDF généré, sauvegardé dans un
dossier "rapports/" à côté de la base de données, avec un nommage automatique
(ex: Rapport_Mosquee_Aout_2026.pdf).
"""

import os
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, PageBreak)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

import database as db

MOIS_FR = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

ACCENT = colors.HexColor("#B8860B")
DANGER = colors.HexColor("#C0392B")
SUCCESS = colors.HexColor("#27AE60")
MUTED = colors.HexColor("#5D6D7E")


def _clean(text):
    """Les libellés de l'application suivent la convention 'Français | العربية'.
    La police PDF par défaut ne sait afficher ni l'arabe ni les émojis (ils
    ressortent en rectangles noirs) : on ne garde que la partie française/latine."""
    if not text:
        return text
    text = str(text).split(" | ")[0].strip()
    return "".join(ch for ch in text if ord(ch) < 0x250) or str(text)


def _reports_dir():
    base = os.path.dirname(db.DB_NAME) or "."
    path = os.path.join(base, "rapports")
    os.makedirs(path, exist_ok=True)
    return path


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("MosqueTitle", parent=styles["Title"], textColor=ACCENT, fontSize=18))
    styles.add(ParagraphStyle("MosqueH2", parent=styles["Heading2"], textColor=ACCENT, fontSize=13,
                              spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle("MosqueMuted", parent=styles["Normal"], textColor=MUTED, fontSize=9))
    return styles


def _header(story, styles, title, period_label):
    story.append(Paragraph("Système de Gestion des Dons — Mosquée", styles["MosqueMuted"]))
    story.append(Paragraph(title, styles["MosqueTitle"]))
    story.append(Paragraph(f"Période : {period_label}  ·  Généré le "
                           f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["MosqueMuted"]))
    story.append(Spacer(1, 12))


def _simple_table(headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _pie_drawing(data_pairs, width=320, height=160):
    """data_pairs: [(label, value), ...]"""
    data_pairs = [d for d in data_pairs if d[1] > 0]
    if not data_pairs:
        return None
    d = Drawing(width, height)
    pie = Pie()
    pie.x, pie.y = 20, 10
    pie.width, pie.height = 130, 130
    pie.data = [v for _, v in data_pairs]
    pie.labels = None
    palette = [ACCENT, colors.HexColor("#1E7F6E"), DANGER, SUCCESS,
               colors.HexColor("#7A8899"), colors.HexColor("#8E44AD")]
    for i in range(len(data_pairs)):
        pie.slices[i].fillColor = palette[i % len(palette)]
    d.add(pie)
    legend = Legend()
    legend.x, legend.y = 170, 130
    legend.dx, legend.dy = 8, 8
    legend.fontSize = 8
    legend.alignment = "left"
    legend.colorNamePairs = [(palette[i % len(palette)], f"{lbl} ({val:,.0f})")
                             for i, (lbl, val) in enumerate(data_pairs)]
    d.add(legend)
    return d


def _alerts_section(story, styles):
    story.append(Paragraph("Alertes actives", styles["MosqueH2"]))
    lines = []
    pay_alerts = db.get_payment_alerts()
    for pid, name, due in pay_alerts["overdue"]:
        lines.append(f"[RETARD] Paiement en retard : {_clean(name)} (échéance {due})")
    for pid, name, due in pay_alerts["reminders"]:
        lines.append(f"[RAPPEL] Paiement à venir : {_clean(name)} (échéance {due})")
    replenish = db.get_envelopes_to_replenish()
    for e in replenish["critical"]:
        lines.append(f"[CRITIQUE] Enveloppe : {_clean(e['name'])} ({e['pct_remaining']:.0f}% restant)")
    for e in replenish["warning"]:
        lines.append(f"[ATTENTION] Enveloppe : {_clean(e['name'])} ({e['pct_remaining']:.0f}% restant)")
    for d_ in replenish["debts"]:
        lines.append(f"[DETTE] {_clean(d_[1])} -> {_clean(d_[2])} : {d_[5]:,.0f} DA restants")
    low_stock = db.get_low_stock_items()
    for row in low_stock["critical"]:
        lines.append(f"[CRITIQUE] Stock : {_clean(row[1])} ({row[4]:g} {row[3]} restant)")
    for row in low_stock["warning"]:
        lines.append(f"[ATTENTION] Stock : {_clean(row[1])} ({row[4]:g} {row[3]} restant)")
    for e in db.get_equipment_in_panne():
        lines.append(f"[PANNE] Équipement : {_clean(e[1])}")
    for e in db.get_equipment_warranty_soon(30):
        lines.append(f"[GARANTIE] {_clean(e[1])} expire le {e[9][:10]}")
    if not lines:
        lines = ["Aucune alerte active."]
    for line in lines:
        story.append(Paragraph(line, getSampleStyleSheet()["Normal"]))
    story.append(Spacer(1, 8))


# ── RAPPORT MENSUEL ────────────────────────────────────────────────────────────
def generate_monthly_report(year, month):
    styles = _styles()
    date_from = f"{year:04d}-{month:02d}-01"
    last_day = 31 if month == 12 else (datetime(year, month + 1, 1) - timedelta(days=1)).day
    date_to = f"{year:04d}-{month:02d}-{last_day:02d}"

    filename = f"Rapport_Mosquee_{MOIS_FR[month]}_{year}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, "Rapport Mensuel", f"{MOIS_FR[month]} {year}")

    opening = db.get_balance_before(date_from)
    closing = db.get_balance_at_end(date_to)
    story.append(_simple_table(
        ["Solde d'ouverture", "Solde de clôture", "Variation"],
        [[f"{opening:,.0f} DA", f"{closing:,.0f} DA", f"{closing - opening:+,.0f} DA"]]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Entrées par source", styles["MosqueH2"]))
    entrees = db.get_donations_breakdown_by_source(date_from, date_to)
    if entrees:
        story.append(_simple_table(["Source", "Montant"],
                                   [[_clean(s), f"{t:,.0f} DA"] for s, t in entrees]))
    else:
        story.append(Paragraph("Aucune entrée sur la période.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Dépenses par catégorie", styles["MosqueH2"]))
    depenses = db.get_expenses_breakdown_by_category(date_from, date_to)
    if depenses:
        depenses_clean = [(_clean(c), t) for c, t in depenses]
        story.append(_simple_table(["Catégorie", "Montant"],
                                   [[c, f"{t:,.0f} DA"] for c, t in depenses_clean]))
        pie = _pie_drawing(depenses_clean)
        if pie:
            story.append(Spacer(1, 6))
            story.append(pie)
    else:
        story.append(Paragraph("Aucune dépense sur la période.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Détail des paiements", styles["MosqueH2"]))
    payments = db.get_payments_in_period(date_from, date_to)
    if payments:
        story.append(_simple_table(["Bénéficiaire", "Montant", "Date"],
                                   [[_clean(n), f"{a:,.0f} DA", d[:10]] for n, a, d in payments]))
    else:
        story.append(Paragraph("Aucun paiement sur la période.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Situation des enveloppes budgétaires", styles["MosqueH2"]))
    envelopes = db.get_envelope_summary()
    if envelopes:
        story.append(_simple_table(
            ["Enveloppe", "Alloué", "Consommé", "Restant", "État"],
            [[_clean(e["name"]), f"{e['allocated']:,.0f} DA", f"{e['spent']:,.0f} DA",
              f"{e['remaining']:,.0f} DA",
              {"ok": "Sain", "warning": "À surveiller", "critical": "Critique"}[e["level"]]]
             for e in envelopes]))
    else:
        story.append(Paragraph("Aucune enveloppe créée.", styles["Normal"]))
    story.append(Spacer(1, 10))

    _alerts_section(story, styles)

    doc.build(story)
    return filepath


# ── RAPPORT ANNUEL ─────────────────────────────────────────────────────────────
def generate_annual_report(year):
    styles = _styles()
    filename = f"Rapport_Annuel_Mosquee_{year}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, "Rapport Annuel", str(year))

    story.append(Paragraph("Évolution mensuelle des recettes et dépenses", styles["MosqueH2"]))
    monthly = db.get_yearly_monthly_summary(year)
    story.append(_simple_table(
        ["Mois", "Entrées", "Sorties", "Net"],
        [[m, f"{i:,.0f} DA", f"{o:,.0f} DA", f"{i - o:+,.0f} DA"] for m, i, o in monthly]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Bilan des enveloppes (alloué vs consommé)", styles["MosqueH2"]))
    envelopes = db.get_envelope_summary()
    if envelopes:
        story.append(_simple_table(
            ["Enveloppe", "Alloué", "Consommé", "Taux d'utilisation"],
            [[_clean(e["name"]), f"{e['allocated']:,.0f} DA", f"{e['spent']:,.0f} DA",
              f"{(e['spent'] / e['allocated'] * 100) if e['allocated'] else 0:.0f}%"]
             for e in envelopes]))
    else:
        story.append(Paragraph("Aucune enveloppe créée.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Top 5 des postes de dépenses de l'année", styles["MosqueH2"]))
    top5 = db.get_top_expense_categories(f"{year}-01-01", f"{year}-12-31", 5)
    if top5:
        story.append(_simple_table(["Catégorie", "Total"], [[_clean(c), f"{t:,.0f} DA"] for c, t in top5]))
    else:
        story.append(Paragraph("Aucune dépense sur l'année.", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Prélèvements exceptionnels inter-enveloppes", styles["MosqueH2"]))
    transfers = db.get_all_envelope_transfers()
    if transfers:
        story.append(_simple_table(
            ["Donatrice", "Bénéficiaire", "Montant", "Remboursé", "Date", "Statut"],
            [[_clean(s), _clean(t), f"{a:,.0f} DA", f"{r:,.0f} DA", d[:10], "Réglée" if settled else "En cours"]
             for _id, s, t, a, r, d, reason, settled in transfers]))
    else:
        story.append(Paragraph("Aucun prélèvement exceptionnel sur la période.", styles["Normal"]))

    doc.build(story)
    return filepath


# ── RELEVÉ DE CAISSE ─────────────────────────────────────────────────────────
def generate_caisse_statement(date_from=None, date_to=None):
    styles = _styles()
    period_label = f"du {date_from} au {date_to}" if date_from or date_to else "Historique complet"
    suffix = f"{date_from}_au_{date_to}" if date_from or date_to else datetime.now().strftime("%Y%m%d")
    filename = f"Releve_Caisse_{suffix}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, "Relevé de Caisse", period_label)

    journal = db.get_caisse_journal(date_from, date_to)
    rows = [[d[:10], _clean(lib), f"{e:,.0f}" if e else "", f"{s:,.0f}" if s else "", f"{sol:,.0f} DA"]
            for d, lib, e, s, sol, mtype in journal]
    story.append(_simple_table(
        ["Date", "Libellé", "Entrée (+)", "Sortie (−)", "Solde"], rows,
        col_widths=[2.2 * cm, 6.5 * cm, 2.5 * cm, 2.5 * cm, 3 * cm]))

    total_in = sum(e for d, lib, e, s, sol, mtype in journal)
    total_out = sum(s for d, lib, e, s, sol, mtype in journal)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"Total entrées : {total_in:,.0f} DA   ·   Total sorties : {total_out:,.0f} DA   ·   "
        f"Net : {total_in - total_out:,.0f} DA", styles["Normal"]))

    doc.build(story)
    return filepath


# ── RAPPORT PAR ENVELOPPE ──────────────────────────────────────────────────────
def generate_envelope_report(envelope_id):
    styles = _styles()
    summary = next((e for e in db.get_envelope_summary() if e["id"] == envelope_id), None)
    if not summary:
        raise ValueError("Enveloppe introuvable ou clôturée.")

    filename = f"Rapport_Enveloppe_{summary['name'].split(' | ')[0].replace(' ', '_')}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, f"Rapport d'Enveloppe — {_clean(summary['name'])}",
           datetime.now().strftime("%d/%m/%Y"))

    story.append(_simple_table(
        ["Alloué", "Dépensé", "Restant", "État"],
        [[f"{summary['allocated']:,.0f} DA", f"{summary['spent']:,.0f} DA",
          f"{summary['remaining']:,.0f} DA",
          {"ok": "Sain", "warning": "À surveiller", "critical": "Critique"}[summary["level"]]]]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Détail des dépenses imputées", styles["MosqueH2"]))
    movements = db.get_envelope_movements(envelope_id)
    if movements:
        story.append(_simple_table(["Date", "Libellé", "Montant", "Type"],
                                   [[d[:10], _clean(lib), f"{a:,.0f} DA", t] for d, lib, a, t in movements]))
    else:
        story.append(Paragraph("Aucun mouvement enregistré.", styles["Normal"]))

    doc.build(story)
    return filepath


# ── RAPPORT BÉNÉFICIAIRE / FOURNISSEUR ────────────────────────────────────────
def generate_payee_report(payee_id):
    styles = _styles()
    payee = next((p for p in db.get_all_payees(active_only=False) if p[0] == payee_id), None)
    if not payee:
        raise ValueError("Bénéficiaire introuvable.")
    _, name, role, ptype, usual, mode, contact = payee

    filename = f"Rapport_Beneficiaire_{name.replace(' ', '_')}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, f"Rapport Bénéficiaire — {name}", datetime.now().strftime("%d/%m/%Y"))

    story.append(_simple_table(
        ["Rôle", "Type", "Montant habituel", "Mode habituel"],
        [[_clean(role), _clean(ptype), f"{usual:,.0f} DA", _clean(mode)]]))
    story.append(Spacer(1, 10))

    total = db.get_payee_total_paid(payee_id)
    story.append(Paragraph(f"Total cumulé versé : {total:,.0f} DA", styles["MosqueH2"]))

    history = db.get_payments_for_payee(payee_id)
    if history:
        story.append(_simple_table(
            ["Date", "Montant", "Période", "Mode", "Statut"],
            [[d[:10], f"{a:,.0f} DA", per or "---", _clean(mode), status]
             for _id, a, d, per, mode, remark, status in history]))
    else:
        story.append(Paragraph("Aucun paiement enregistré.", styles["Normal"]))

    doc.build(story)
    return filepath


# ── LISTE DE COURSES (STOCKS) ──────────────────────────────────────────────────
def generate_shopping_list():
    styles = _styles()
    filename = f"Liste_Courses_{datetime.now().strftime('%Y%m%d')}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, "Liste de Courses", datetime.now().strftime("%d/%m/%Y"))

    items = db.get_shopping_list()
    if items:
        story.append(_simple_table(
            ["Article", "Catégorie", "Stock actuel", "Seuil", "Fournisseur habituel"],
            [[_clean(i[1]), _clean(i[2]), f"{i[4]:g} {i[3]}", f"{i[5]:g} {i[3]}", i[6] or "---"]
             for i in items]))
    else:
        story.append(Paragraph("Aucun article à commander pour le moment.", styles["Normal"]))

    doc.build(story)
    return filepath


# ── INVENTAIRE DES ÉQUIPEMENTS ─────────────────────────────────────────────────
def generate_equipment_inventory():
    styles = _styles()
    filename = f"Inventaire_Equipements_{datetime.now().strftime('%Y%m%d')}.pdf"
    filepath = os.path.join(_reports_dir(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = []
    _header(story, styles, "Registre des Équipements", datetime.now().strftime("%d/%m/%Y"))

    equipment = db.get_all_equipment()
    if equipment:
        story.append(_simple_table(
            ["Désignation", "Catégorie", "État", "Localisation", "Acquisition", "Prix", "Garantie"],
            [[_clean(e[1]), _clean(e[2]), _clean(e[5]), _clean(e[6]), e[3][:10] if e[3] else "---",
              f"{e[4]:,.0f} DA" if e[4] else "---", e[9][:10] if e[9] else "---"]
             for e in equipment],
            col_widths=[3.2 * cm, 2.2 * cm, 2 * cm, 2.5 * cm, 2 * cm, 2 * cm, 2 * cm]))
    else:
        story.append(Paragraph("Aucun équipement enregistré.", styles["Normal"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Signalements ouverts", styles["MosqueH2"]))
    open_issues = db.get_all_open_issues()
    if open_issues:
        story.append(_simple_table(
            ["Équipement", "Description", "Urgence", "Statut", "Date"],
            [[_clean(eq), _clean(desc), _clean(urg), _clean(status), date[:10]]
             for _id, eq, desc, urg, status, date in open_issues]))
    else:
        story.append(Paragraph("Aucun signalement ouvert.", styles["Normal"]))

    doc.build(story)
    return filepath