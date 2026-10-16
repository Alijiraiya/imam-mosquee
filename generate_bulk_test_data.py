# -*- coding: utf-8 -*-
"""
generate_bulk_test_data.py
----------------------------
Génère un JEU DE DONNÉES ALÉATOIRE COMPLET pour vérifier que TOUT le
logiciel fonctionne (et pas seulement la page Familles) :

    - 30 familles (profils variés : âge, revenu, santé, locataires,
      enfants dont certains orphelins -> alimente le score SVF, les
      2 boutons de filtre, et le camembert du tableau de bord)
    - ~50 donateurs
    - ~120 dons (espèce ET nature) RÉPARTIS sur les 6 derniers mois
      -> remplit l'histogramme "Entrées / Sorties" du tableau de bord
    - ~15 distributions réparties sur la même période
      -> remplit l'historique des distributions + les "sorties"

Toutes les familles et tous les donateurs créés commencent par "TEST - "
pour rester facilement identifiables et supprimables : une fois les
vérifications terminées, lance simplement :

    python cleanup_test_data.py

Utilisation manuelle (optionnelle) :
    python generate_bulk_test_data.py

Ce fichier est aussi importé automatiquement par main.py : au tout premier
lancement de l'application (base de données vide), generate() est appelée
une seule fois pour que le logiciel affiche directement des données
d'exemple au lieu d'un écran vide. Aucune donnée existante n'est jamais
modifiée ni supprimée : ce script ne fait qu'AJOUTER des enregistrements.
"""

import random
from datetime import datetime, timedelta

import database as db
from svf_calculator import SVFCalculator

# ── Données de base pour la génération aléatoire ────────────────────────────
MALE_FIRST = ["Ahmed", "Karim", "Rachid", "Sofiane", "Omar", "Yacine", "Bilal",
              "Amine", "Riyad", "Farid", "Nabil", "Samir", "Walid", "Adel",
              "Hocine", "Mourad", "Tarek", "Zakaria", "Djamel", "Anes"]
FEMALE_FIRST = ["Fatima", "Amina", "Yasmine", "Nadia", "Khadija", "Lila",
                "Souad", "Meriem", "Houda", "Sara", "Imane", "Nawel", "Samira",
                "Wafa", "Asma", "Chahinez", "Ines", "Rania", "Dounia", "Salima"]
LAST_NAMES = ["Bouzid", "Cherif", "Haddad", "Ziani", "Meziane", "Boumediene",
              "Amrani", "Guerroudj", "Belkacem", "Saadi", "Kaci", "Benali",
              "Rezki", "Bensalem", "Mansouri", "Larbi", "Ouali", "Ferhat",
              "Khelifi", "Bouras", "Aouadi", "Chaib", "Djellal", "Hamdi",
              "Idir", "Kaddour", "Lounis", "Merabet", "Naili", "Ouyahia"]

EMPLOYMENT = ["Ouvrier | عامل", "Sans emploi", "Fonctionnaire | موظف",
              "Retraité | متقاعد", "Journalier | عامل يومي",
              "Vendeur ambulant | بائع متجول", "Cadre | إطار",
              "Femme au foyer", "Artisan | حرفي"]
MARITAL = ["Marié | متزوج", "Veuf | أرمل(ة)", "Veuve | أرملة",
           "Divorcée | مطلقة", "Célibataire | أعزب"]
SOCIAL = ["Aucun", "Besoin Basique | حاجة أساسية", "Sans soutien | بدون معيل",
          "Famille d'Orphelins | عائلة أيتام", "Veuve | أرملة", "Divorcée | مطلقة"]
HEALTH = ["Bonne | جيدة", "Bonne | جيدة", "Bonne | جيدة",  # pondéré (majorité en bonne santé)
          "Maladie chronique | مرض مزمن", "Handicap | إعاقة"]
CHRONIC_NOTES = ["", "", "", "Diabète, suivi régulier", "Hypertension",
                  "Insuffisance rénale", "Asthme sévère"]
SCHOOLING = ["Non scolarisé | غير متمدرس", "Préscolaire | تحضيري",
             "Primaire | ابتدائي", "Moyen | متوسط", "Secondaire | ثانوي",
             "Université | جامعي", "Formation professionnelle | تكوين مهني"]
CHILD_HEALTH = ["Bonne | جيدة", "Bonne | جيدة", "Bonne | جيدة",
                "Maladie chronique | مرض مزمن", "Handicap | إعاقة"]

CASH_TYPES = ["Cash | نقداً", "Chèque", "Sadaqa Jariya", "Zakat Al-Maal", "Zakat Al-Fitr"]
NATURE_TYPES = ["Cartables | حقائب مدرسية", "Vêtements | ملابس", "Nourriture | طعام",
                "Matériel scolaire | مستلزمات مدرسية", "Médicaments | أدوية",
                "Meubles | أثاث", "Autre | أخرى"]
UNITS = ["unité(s) | قطعة", "kg", "L", "carton(s)", "sac(s)"]
DIST_TYPES = ["Manuelle | يدوي", "Water-Filling | خوارزمية"]


def random_phone():
    return "05" + str(random.randint(50, 79)) + str(random.randint(100000, 999999))


def random_past_date(max_days_back=180):
    """Date aléatoire dans les X derniers jours (pour étaler les dons /
    distributions sur ~6 mois et remplir l'histogramme du tableau de bord)."""
    d = datetime.now() - timedelta(days=random.randint(0, max_days_back),
                                    hours=random.randint(0, 23))
    return d.strftime("%Y-%m-%d %H:%M")


def random_child(head_age):
    gender = random.choice(["Masculin | ذكر", "Féminin | أنثى"])
    first = random.choice(MALE_FIRST if gender.startswith("Masculin") else FEMALE_FIRST)
    last = random.choice(LAST_NAMES)
    child_age = random.randint(0, max(1, min(17, head_age - 18)))
    birth_year = datetime.now().year - child_age
    birth = f"{random.randint(1,28):02d}/{random.randint(1,12):02d}/{birth_year}"
    is_orphan = 1 if random.random() < 0.15 else 0  # ~15% d'orphelins
    return (f"{first} {last}", birth, random.choice(SCHOOLING),
            random.choice(CHILD_HEALTH), gender, is_orphan)


def insert_donation_dated(donor_id, amount, donation_type, notes, category,
                           item_name, quantity, unit, date_str):
    """Comme db.add_donation, mais avec une date choisie (pour étaler les
    dons sur plusieurs mois et alimenter l'histogramme du tableau de bord)."""
    db.execute_query(
        """INSERT INTO donation (donor_id, amount, donation_type, donation_date,
           notes, category, item_name, quantity, unit) VALUES (?,?,?,?,?,?,?,?,?)""",
        (donor_id, amount, donation_type, date_str, notes, category, item_name, quantity, unit)
    )


def insert_distribution_dated(family_id, amount, dist_type, notes, date_str):
    db.execute_query(
        """INSERT INTO distribution (family_id, amount, distribution_type,
           distribution_date, notes) VALUES (?,?,?,?,?)""",
        (family_id, amount, dist_type, date_str, notes)
    )


def generate(seed=42, n_families=30, n_donors=50, n_distributions=15, verbose=True):
    """Génère le jeu de données fictif complet et l'insère dans charity.db.
    N'écrase ni ne supprime jamais de données existantes : ajoute uniquement.
    Retourne un résumé (dict) du nombre d'enregistrements créés."""
    random.seed(seed)  # résultats reproductibles à chaque exécution
    db.initialize_database()

    def log(msg):
        if verbose:
            print(msg)

    # ── 1) Génération des familles ──────────────────────────────────────
    log(f"Création de {n_families} familles...")
    family_ids = []
    for i in range(n_families):
        gender_head = random.choice(["M", "F"])
        first = random.choice(MALE_FIRST if gender_head == "M" else FEMALE_FIRST)
        last = random.choice(LAST_NAMES)
        head_name = f"TEST - {first} {last}"
        spouse_name = (random.choice(FEMALE_FIRST if gender_head == "M" else MALE_FIRST)
                       + " " + random.choice(LAST_NAMES)) if random.random() < 0.7 else None

        age = random.randint(20, 80)
        income = random.choice([0, 8000, 12000, 15000, 18000, 22000, 28000, 35000,
                                 45000, 60000, 90000, 120000])
        is_renting = 1 if random.random() < 0.4 else 0
        rent = random.randint(8000, 25000) if is_renting else 0
        employment = random.choice(EMPLOYMENT)
        marital = random.choice(MARITAL)
        members = random.randint(1, 8)
        social = random.choice(SOCIAL)
        health = random.choice(HEALTH)
        chronic = random.choice(CHRONIC_NOTES) if health != "Bonne | جيدة" else ""

        n_children = random.randint(0, min(5, max(0, members - 1)))
        children = [random_child(age) for _ in range(n_children)]
        children_count = len(children)

        svf_score = SVFCalculator.calculate({
            'monthly_income': income, 'children_count': children_count,
            'social_status': social, 'health_status': health,
            'is_renting': is_renting, 'benefit_count': random.randint(0, 2), 'age': age
        })

        fid = db.add_family(
            head_name, spouse_name, random_phone(), "Adresse test, Alger", "",
            income, rent, employment, "", marital, members, social, health,
            chronic, is_renting, "", 0.0, 1, "", svf_score, age, "", ""
        )
        family_ids.append(fid)

        for c in children:
            name, birth, schooling, c_health, gender, is_orphan = c
            db.add_child(fid, name, birth, schooling, c_health, gender, is_orphan, "")

    log(f"  -> {len(family_ids)} familles créées.")

    # ── 2) Génération des donateurs ─────────────────────────────────────
    log(f"Création de {n_donors} donateurs...")
    donor_ids = []
    for i in range(n_donors):
        gender = random.choice(["M", "F"])
        first = random.choice(MALE_FIRST if gender == "M" else FEMALE_FIRST)
        last = random.choice(LAST_NAMES)
        name = f"TEST - {first} {last}"
        db.add_donor(name, random_phone(), "", random.randint(20, 70))
        donor_ids.append(db.fetch_one(
            "SELECT id FROM donor WHERE name=? ORDER BY id DESC LIMIT 1", (name,))[0])

    log(f"  -> {len(donor_ids)} donateurs créés.")

    # ── 3) Génération des dons (espèce + nature), étalés sur 6 mois ────
    log("Création des dons (répartis sur les 6 derniers mois)...")
    n_donations = 0
    for did in donor_ids:
        for _ in range(random.randint(1, 4)):
            date_str = random_past_date(180)
            if random.random() < 0.75:  # 75% des dons en espèce
                amount = random.choice([2000, 5000, 8000, 10000, 15000, 20000, 30000, 50000])
                insert_donation_dated(did, amount, random.choice(CASH_TYPES), "",
                                       "Espèce", "", 0, "unité(s)", date_str)
            else:  # 25% des dons en nature
                item = random.choice(["Riz", "Semoule", "Huile", "Cartables",
                                       "Vêtements d'hiver", "Couvertures", "Lait"])
                qty = random.randint(5, 100)
                insert_donation_dated(did, random.choice([0, 3000, 5000]),
                                       random.choice(NATURE_TYPES), "", "Nature",
                                       item, qty, random.choice(UNITS), date_str)
            n_donations += 1

    log(f"  -> {n_donations} dons créés.")

    # ── 4) Génération des distributions, étalées sur 6 mois ────────────
    log("Création des distributions (réparties sur les 6 derniers mois)...")
    n_dist = 0
    for _ in range(n_distributions):
        fid = random.choice(family_ids)
        amount = random.choice([1000, 3000, 5000, 8000, 10000, 15000, 20000])
        date_str = random_past_date(180)
        insert_distribution_dated(fid, amount, random.choice(DIST_TYPES),
                                   "Distribution test", date_str)
        n_dist += 1

    log(f"  -> {n_dist} distributions créées.")
    log("\n✅ Base de données de test générée avec succès :")
    log(f"   - {len(family_ids)} familles")
    log(f"   - {len(donor_ids)} donateurs")
    log(f"   - {n_donations} dons")
    log(f"   - {n_dist} distributions")

    return {
        "families": len(family_ids),
        "donors": len(donor_ids),
        "donations": n_donations,
        "distributions": n_dist,
    }


if __name__ == "__main__":
    generate()
    print("\nOuvre l'application : le tableau de bord, les familles, les dons et")
    print("les distributions doivent maintenant être remplis.")
    print("\nPour tout supprimer ensuite : python cleanup_test_data.py")