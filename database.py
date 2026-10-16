import sqlite3
import os
import shutil
import sys
from datetime import datetime, timedelta

def _get_base_dir():
    """Dossier où doit vivre charity.db, de façon STABLE quel que soit
    l'endroit depuis lequel l'appli est lancée (double-clic, raccourci,
    terminal ouvert ailleurs, VS Code, etc.) :
    - Application empaquetée (PyInstaller) : le dossier de l'exécutable
      (PAS le dossier temporaire d'extraction _MEIPASS, qui change à
      chaque lancement et ferait perdre les données à chaque fois).
    - Script Python normal : le dossier contenant ce fichier database.py.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(_get_base_dir(), "charity.db")

def connect():
    # timeout : le nombre de secondes que sqlite3 attend qu'un verrou se
    # libère avant de lever "database is locked" (par défaut : 5s, ce qui
    # est trop court si un rafraîchissement de graphique ou une sauvegarde
    # est en cours au même moment).
    conn = sqlite3.connect(DB_NAME, timeout=30)
    # WAL : permet aux lectures (dashboard, listes) de ne pas bloquer les
    # écritures (ajout d'une famille/enfant) et inversement.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def execute_query(query, params=()):
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()

def fetch_all(query, params=()):
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(query, params)
        return c.fetchall()
    finally:
        conn.close()

def fetch_one(query, params=()):
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(query, params)
        return c.fetchone()
    finally:
        conn.close()

def initialize_database():
    conn = connect()
    c = conn.cursor()

    # Schéma réel de la DB (23 colonnes : index 0-22)
    # [0]id [1]head_name [2]spouse_name [3]phone [4]address [5]postal_account
    # [6]monthly_income [7]rent_amount [8]employment_status [9]income_sources
    # [10]marital_status [11]total_members [12]social_status [13]health_status
    # [14]chronic_diseases [15]is_renting [16]housing_type [17]housing_surface
    # [18]rooms_count [19]housing_condition [20]svf_score [21]is_active [22]age
    c.execute("""CREATE TABLE IF NOT EXISTS family (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        head_name TEXT, spouse_name TEXT, phone TEXT, address TEXT, postal_account TEXT,
        monthly_income REAL, rent_amount REAL, employment_status TEXT, income_sources TEXT,
        marital_status TEXT, total_members INTEGER, social_status TEXT, health_status TEXT,
        chronic_diseases TEXT, is_renting TEXT, housing_type TEXT, housing_surface REAL,
        rooms_count INTEGER, housing_condition TEXT, svf_score REAL,
        is_active INTEGER DEFAULT 1, age INTEGER DEFAULT 0,
        registration_date TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS child (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER, name TEXT, birth_date TEXT, schooling_status TEXT, health_status TEXT,
        FOREIGN KEY(family_id) REFERENCES family(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS donor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, phone TEXT, email TEXT,
        is_active INTEGER DEFAULT 1, age INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS donation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id INTEGER, amount REAL, donation_type TEXT DEFAULT 'Cash',
        donation_date TEXT NOT NULL, notes TEXT DEFAULT '',
        category TEXT DEFAULT 'Espèce', item_name TEXT DEFAULT '', quantity REAL DEFAULT 0,
        unit TEXT DEFAULT 'unité(s)',
        FOREIGN KEY(donor_id) REFERENCES donor(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS distribution (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER, amount REAL, distribution_type TEXT DEFAULT 'Financiere',
        distribution_date TEXT NOT NULL, notes TEXT DEFAULT '',
        FOREIGN KEY(family_id) REFERENCES family(id)
    )""")

    # Table générique clé/valeur pour les paramètres configurables
    # (poids du calcul SVF, paramètres du Water-Filling, mot de passe, ...)
    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Documents justificatifs liés à une famille (certificat de décès, documents
    # médicaux, etc.). Le fichier lui-même est copié sur le disque, seul son
    # chemin est stocké ici.
    c.execute("""CREATE TABLE IF NOT EXISTS family_document (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id INTEGER,
        original_name TEXT,
        stored_path TEXT,
        added_date TEXT,
        FOREIGN KEY(family_id) REFERENCES family(id)
    )""")

    # ── Gestion des dépenses de la mosquée (femme de ménage, entretien, ...) ──
    # Catégories de dépenses, modifiables (ajout/suppression) depuis la
    # nouvelle fenêtre "Dépenses Mosquée".
    c.execute("""CREATE TABLE IF NOT EXISTS mosque_expense_category (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS mosque_expense (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        label TEXT,
        amount REAL DEFAULT 0,
        expense_date TEXT NOT NULL,
        notes TEXT DEFAULT '',
        FOREIGN KEY(category_id) REFERENCES mosque_expense_category(id)
    )""")

    # ── Gestion des Paiements (imam, muezzin, agents, artisans, ...) ───────────
    # Répertoire des bénéficiaires de paiements (module "Gestion des Paiements").
    c.execute("""CREATE TABLE IF NOT EXISTS payee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT DEFAULT '',
        payment_type TEXT DEFAULT 'Occasionnel',
        usual_amount REAL DEFAULT 0,
        payment_mode TEXT DEFAULT 'Espèces',
        contact TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS payment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payee_id INTEGER,
        amount REAL DEFAULT 0,
        payment_date TEXT NOT NULL,
        period_covered TEXT DEFAULT '',
        payment_mode TEXT DEFAULT 'Espèces',
        remark TEXT DEFAULT '',
        status TEXT DEFAULT 'Payé',
        FOREIGN KEY(payee_id) REFERENCES payee(id)
    )""")

    conn.commit()
    conn.close()

    _ensure_columns("payee", {
        "name": "TEXT", "role": "TEXT DEFAULT ''",
        "payment_type": "TEXT DEFAULT 'Occasionnel'", "usual_amount": "REAL DEFAULT 0",
        "payment_mode": "TEXT DEFAULT 'Espèces'", "contact": "TEXT DEFAULT ''",
        "is_active": "INTEGER DEFAULT 1",
    })
    _ensure_columns("payment", {
        "payee_id": "INTEGER", "amount": "REAL DEFAULT 0", "payment_date": "TEXT",
        "period_covered": "TEXT DEFAULT ''", "payment_mode": "TEXT DEFAULT 'Espèces'",
        "remark": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'Payé'",
        "envelope_id": "INTEGER",
    })

    # ── Enveloppes Budgétaires ──────────────────────────────────────────────
    conn2 = connect()
    c2 = conn2.cursor()
    c2.execute("""CREATE TABLE IF NOT EXISTS envelope (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        allocated_budget REAL DEFAULT 0,
        period TEXT DEFAULT 'Mensuelle',
        alert_threshold_pct REAL DEFAULT 20,
        description TEXT DEFAULT '',
        status TEXT DEFAULT 'Active',
        created_date TEXT DEFAULT ''
    )""")
    c2.execute("""CREATE TABLE IF NOT EXISTS envelope_transfer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_envelope_id INTEGER,
        target_envelope_id INTEGER,
        amount REAL DEFAULT 0,
        transfer_date TEXT NOT NULL,
        reason TEXT DEFAULT '',
        repaid_amount REAL DEFAULT 0,
        is_settled INTEGER DEFAULT 0,
        FOREIGN KEY(source_envelope_id) REFERENCES envelope(id),
        FOREIGN KEY(target_envelope_id) REFERENCES envelope(id)
    )""")
    conn2.commit()
    conn2.close()
    _ensure_columns("envelope", {
        "name": "TEXT", "allocated_budget": "REAL DEFAULT 0",
        "period": "TEXT DEFAULT 'Mensuelle'", "alert_threshold_pct": "REAL DEFAULT 20",
        "description": "TEXT DEFAULT ''", "status": "TEXT DEFAULT 'Active'",
        "created_date": "TEXT DEFAULT ''",
    })
    _ensure_columns("envelope_transfer", {
        "source_envelope_id": "INTEGER", "target_envelope_id": "INTEGER",
        "amount": "REAL DEFAULT 0", "transfer_date": "TEXT", "reason": "TEXT DEFAULT ''",
        "repaid_amount": "REAL DEFAULT 0", "is_settled": "INTEGER DEFAULT 0",
    })

    # ── Gestion des Stocks ───────────────────────────────────────────────────
    conn3 = connect()
    c3 = conn3.cursor()
    c3.execute("""CREATE TABLE IF NOT EXISTS stock_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'Autre',
        unit TEXT DEFAULT 'Unité',
        current_stock REAL DEFAULT 0,
        reorder_threshold REAL DEFAULT 0,
        usual_supplier TEXT DEFAULT '',
        last_updated TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )""")
    c3.execute("""CREATE TABLE IF NOT EXISTS stock_movement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        movement_type TEXT DEFAULT 'Entrée',
        quantity REAL DEFAULT 0,
        movement_date TEXT NOT NULL,
        notes TEXT DEFAULT '',
        FOREIGN KEY(item_id) REFERENCES stock_item(id)
    )""")
    conn3.commit()
    conn3.close()
    _ensure_columns("stock_item", {
        "name": "TEXT", "category": "TEXT DEFAULT 'Autre'", "unit": "TEXT DEFAULT 'Unité'",
        "current_stock": "REAL DEFAULT 0", "reorder_threshold": "REAL DEFAULT 0",
        "usual_supplier": "TEXT DEFAULT ''", "last_updated": "TEXT DEFAULT ''",
        "is_active": "INTEGER DEFAULT 1",
    })
    _ensure_columns("stock_movement", {
        "item_id": "INTEGER", "movement_type": "TEXT DEFAULT 'Entrée'",
        "quantity": "REAL DEFAULT 0", "movement_date": "TEXT", "notes": "TEXT DEFAULT ''",
    })

    # ── Gestion des Équipements ──────────────────────────────────────────────
    conn4 = connect()
    c4 = conn4.cursor()
    c4.execute("""CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'Autre',
        acquisition_date TEXT DEFAULT '',
        purchase_price REAL DEFAULT 0,
        condition TEXT DEFAULT 'Bon état',
        location TEXT DEFAULT '',
        photo_path TEXT DEFAULT '',
        serial_number TEXT DEFAULT '',
        warranty_expiry TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1
    )""")
    c4.execute("""CREATE TABLE IF NOT EXISTS equipment_issue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id INTEGER,
        description TEXT DEFAULT '',
        photo_path TEXT DEFAULT '',
        urgency TEXT DEFAULT 'Moyen',
        assigned_to TEXT DEFAULT '',
        status TEXT DEFAULT 'Signalé',
        reported_date TEXT NOT NULL,
        resolved_date TEXT DEFAULT '',
        repair_cost REAL DEFAULT 0,
        FOREIGN KEY(equipment_id) REFERENCES equipment(id)
    )""")
    conn4.commit()
    conn4.close()
    _ensure_columns("equipment", {
        "name": "TEXT", "category": "TEXT DEFAULT 'Autre'", "acquisition_date": "TEXT DEFAULT ''",
        "purchase_price": "REAL DEFAULT 0", "condition": "TEXT DEFAULT 'Bon état'",
        "location": "TEXT DEFAULT ''", "photo_path": "TEXT DEFAULT ''",
        "serial_number": "TEXT DEFAULT ''", "warranty_expiry": "TEXT DEFAULT ''",
        "is_active": "INTEGER DEFAULT 1",
    })
    _ensure_columns("equipment_issue", {
        "equipment_id": "INTEGER", "description": "TEXT DEFAULT ''", "photo_path": "TEXT DEFAULT ''",
        "urgency": "TEXT DEFAULT 'Moyen'", "assigned_to": "TEXT DEFAULT ''",
        "status": "TEXT DEFAULT 'Signalé'", "reported_date": "TEXT",
        "resolved_date": "TEXT DEFAULT ''", "repair_cost": "REAL DEFAULT 0",
    })

    # ── Enrichissement Dépenses : bénéficiaire, pièce jointe, validé par, enveloppe débitée ──
    _ensure_columns("mosque_expense", {
        "category_id": "INTEGER", "label": "TEXT", "amount": "REAL DEFAULT 0",
        "expense_date": "TEXT", "notes": "TEXT DEFAULT ''",
        "beneficiary": "TEXT DEFAULT ''", "attachment_path": "TEXT DEFAULT ''",
        "validated_by": "TEXT DEFAULT ''", "envelope_id": "INTEGER",
    })

    # Catégories de dépenses par défaut (une seule fois, à la création)
    if not fetch_all("SELECT id FROM mosque_expense_category"):
        for default_cat in ["Femme de ménage | عاملة النظافة",
                             "Entretien de la mosquée | صيانة المسجد",
                             "Électricité & Eau | كهرباء و ماء",
                             "Imam / Personnel | الإمام والموظفون",
                             "Autre | أخرى"]:
            execute_query("INSERT OR IGNORE INTO mosque_expense_category (name) VALUES (?)",
                          (default_cat,))

    # Migration : ajoute automatiquement TOUTE colonne manquante sur les
    # tables principales (utile pour les bases de données créées avec
    # d'anciennes versions de l'application, qui peuvent avoir plusieurs
    # colonnes en retard par rapport au schéma actuel).
    _ensure_columns("family", {
        "head_name": "TEXT", "spouse_name": "TEXT", "phone": "TEXT",
        "address": "TEXT", "postal_account": "TEXT",
        "monthly_income": "REAL DEFAULT 0", "rent_amount": "REAL DEFAULT 0",
        "employment_status": "TEXT", "income_sources": "TEXT",
        "marital_status": "TEXT", "total_members": "INTEGER DEFAULT 1",
        "social_status": "TEXT", "health_status": "TEXT",
        "chronic_diseases": "TEXT", "is_renting": "TEXT",
        "housing_type": "TEXT", "housing_surface": "REAL DEFAULT 0",
        "rooms_count": "INTEGER DEFAULT 0", "housing_condition": "TEXT",
        "svf_score": "REAL DEFAULT 0", "is_active": "INTEGER DEFAULT 1",
        "age": "INTEGER DEFAULT 0", "specific_needs": "TEXT DEFAULT ''",
        "emergency_contact": "TEXT DEFAULT ''",
        "registration_date": "TEXT DEFAULT ''",
    })
    # Familles déjà en base avant l'ajout de cette colonne : on ne connaît
    # pas leur vraie date d'enregistrement, donc on la fixe à aujourd'hui
    # plutôt que de les signaler à tort comme "en retard" dans l'alerte
    # "famille sans aide depuis longtemps".
    execute_query(
        "UPDATE family SET registration_date=? WHERE registration_date IS NULL OR registration_date=''",
        (datetime.now().strftime("%Y-%m-%d %H:%M"),)
    )
    _ensure_columns("child", {
        "family_id": "INTEGER", "name": "TEXT", "birth_date": "TEXT DEFAULT ''",
        "schooling_status": "TEXT DEFAULT ''", "health_status": "TEXT DEFAULT ''",
        "gender": "TEXT DEFAULT ''", "is_orphan": "INTEGER DEFAULT 0",
        "notes": "TEXT DEFAULT ''",
        # ── Situation socio-professionnelle du fils/de la fille ──────────
        "is_working": "INTEGER DEFAULT 0",           # Travaille (oui/non)
        "work_type": "TEXT DEFAULT ''",               # Temporaire / Saisonnier / Stable
        "monthly_revenue": "REAL DEFAULT 0",           # Revenu mensuel (s'il contribue au foyer)
        "marital_status": "TEXT DEFAULT ''",           # Célibataire / Marié(e) / Divorcé(e) / Veuf(ve)
        "has_children": "INTEGER DEFAULT 0",           # A des enfants (oui/non)
        "own_children_count": "INTEGER DEFAULT 0",     # Nombre de ses propres enfants
        "lives_with_family": "INTEGER DEFAULT 1",      # Vit avec la famille / a son propre foyer
        "is_dependent": "INTEGER DEFAULT 1",           # À charge de la famille
        "is_breadwinner": "INTEGER DEFAULT 0",         # Soutien de famille
        "dependency_level": "TEXT DEFAULT ''",         # Dépend entièrement / partiellement / Autonome
    })
    _ensure_columns("donor", {
        "name": "TEXT", "phone": "TEXT", "email": "TEXT",
        "is_active": "INTEGER DEFAULT 1", "age": "INTEGER DEFAULT 0",
    })
    _ensure_columns("donation", {
        "donor_id": "INTEGER", "amount": "REAL DEFAULT 0",
        "donation_type": "TEXT DEFAULT 'Cash'", "donation_date": "TEXT",
        "notes": "TEXT DEFAULT ''", "category": "TEXT DEFAULT 'Espèce'",
        "item_name": "TEXT DEFAULT ''", "quantity": "REAL DEFAULT 0",
        "unit": "TEXT DEFAULT 'unité(s)'",
    })
    _ensure_columns("distribution", {
        "family_id": "INTEGER", "amount": "REAL DEFAULT 0",
        "distribution_type": "TEXT DEFAULT 'Financiere'",
        "distribution_date": "TEXT", "notes": "TEXT DEFAULT ''",
    })

    # Certaines bases anciennes ont eu leurs colonnes ajoutées au fil du temps
    # via ALTER TABLE (ce qui les place toujours en FIN de table, dans l'ordre
    # d'ajout). Le code lit certaines lignes par position (SELECT *), donc si
    # l'ordre physique des colonnes ne correspond plus à l'ordre attendu, les
    # valeurs lues sont décalées (ex: l'âge affiché est en fait un autre champ).
    # Ces deux migrations reconstruisent les tables avec l'ordre correct,
    # sans perte de données (y compris les anciens champs "enfant" détaillés
    # d'anciennes versions de l'appli, conservés en fin de table).
    _normalize_family_table()
    _normalize_child_table()


def _normalize_family_table():
    """Reconstruit `family` avec l'ordre de colonnes attendu par le code,
    si nécessaire (ne fait rien si l'ordre est déjà correct)."""
    canonical = ["id", "head_name", "spouse_name", "phone", "address", "postal_account",
                 "monthly_income", "rent_amount", "employment_status", "income_sources",
                 "marital_status", "total_members", "social_status", "health_status",
                 "chronic_diseases", "is_renting", "housing_type", "housing_surface",
                 "rooms_count", "housing_condition", "svf_score", "is_active", "age",
                 "specific_needs", "emergency_contact", "registration_date"]
    conn = connect()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(family)")
        current = [r[1] for r in c.fetchall()]
        if current == canonical:
            return  # déjà dans le bon ordre, rien à faire
        c.execute("""CREATE TABLE family_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            head_name TEXT, spouse_name TEXT, phone TEXT, address TEXT, postal_account TEXT,
            monthly_income REAL, rent_amount REAL, employment_status TEXT, income_sources TEXT,
            marital_status TEXT, total_members INTEGER, social_status TEXT, health_status TEXT,
            chronic_diseases TEXT, is_renting TEXT, housing_type TEXT, housing_surface REAL,
            rooms_count INTEGER, housing_condition TEXT, svf_score REAL,
            is_active INTEGER DEFAULT 1, age INTEGER DEFAULT 0,
            specific_needs TEXT DEFAULT '', emergency_contact TEXT DEFAULT '',
            registration_date TEXT DEFAULT ''
        )""")
        cols = canonical[1:]
        c.execute(f"INSERT INTO family_new (id, {', '.join(cols)}) "
                  f"SELECT id, {', '.join(cols)} FROM family")
        c.execute("DROP TABLE family")
        c.execute("ALTER TABLE family_new RENAME TO family")
        conn.commit()
    finally:
        conn.close()


def _normalize_child_table():
    """Reconstruit `child` avec les colonnes attendues par le code, dans le
    bon ordre, en récupérant les données des anciens champs équivalents
    (date_of_birth -> birth_date, school_status -> schooling_status,
    is_orphan texte 'Oui'/'Non' -> entier 0/1) si présents. Les autres
    anciens champs détaillés (school_level, disease_type, allergies, ...)
    sont conservés tels quels en fin de table (non lus par l'appli, mais
    pas supprimés).

    IMPORTANT : le tableau canonique couvre maintenant TOUTES les colonnes
    lues par position ailleurs dans le code (jusqu'à dependency_level), pas
    seulement les 9 premières. Sur d'anciennes bases, des colonnes "orphelines"
    d'une version antérieure (date_of_birth, school_level, disease_type,
    allergies, ...) peuvent avoir été ajoutées par ALTER TABLE et se
    retrouver intercalées ENTRE `notes` et `is_working`. Si on ne vérifie que
    les 9 premières colonnes, ce décalage n'est jamais détecté : le code lit
    alors par erreur ces anciennes colonnes vides à la place de la situation
    professionnelle / matrimoniale / dépendance, qui elle est pourtant bien
    enregistrée en base (sous le bon nom de colonne, juste au mauvais
    endroit). Résultat : ces champs semblent "ne pas se sauvegarder" alors
    qu'ils sont juste mal affichés/relus, et une modification ultérieure de
    la fiche peut même écraser les vraies valeurs avec des valeurs par défaut
    vides."""
    canonical_core = ["id", "family_id", "name", "birth_date", "schooling_status",
                       "health_status", "gender", "is_orphan", "notes",
                       "is_working", "work_type", "monthly_revenue", "marital_status",
                       "has_children", "own_children_count", "lives_with_family",
                       "is_dependent", "is_breadwinner", "dependency_level"]
    conn = connect()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(child)")
        current = [r[1] for r in c.fetchall()]
        if current[:len(canonical_core)] == canonical_core:
            return  # déjà dans le bon ordre, rien à faire

        extra_cols = [col for col in current if col not in canonical_core and col != "id"]

        def pick(name):
            return name if name in current else None

        birth_new, birth_legacy = pick("birth_date"), pick("date_of_birth")
        if birth_new and birth_legacy:
            birth_expr = "COALESCE(NULLIF(birth_date,''), date_of_birth, '')"
        else:
            birth_expr = birth_new or birth_legacy or "''"

        school_new, school_legacy = pick("schooling_status"), pick("school_status")
        if school_new and school_legacy:
            school_expr = "COALESCE(NULLIF(schooling_status,''), school_status, '')"
        else:
            school_expr = school_new or school_legacy or "''"

        if "is_orphan" in current:
            orphan_expr = ("CASE WHEN is_orphan IN (1,'1') THEN 1 "
                            "WHEN is_orphan LIKE 'Oui%' THEN 1 ELSE 0 END")
        else:
            orphan_expr = "0"

        health_expr = "health_status" if "health_status" in current else "''"
        gender_expr = "gender" if "gender" in current else "''"
        notes_expr = "notes" if "notes" in current else "''"
        name_expr = "name" if "name" in current else "''"
        family_id_expr = "family_id" if "family_id" in current else "NULL"

        # ── Champs étendus (situation pro / matrimoniale / dépendance) ──
        # Repris par NOM (pas par position), donc même s'ils sont
        # actuellement décalés dans la table d'origine, leurs vraies valeurs
        # sont bien récupérées.
        working_expr = "is_working" if "is_working" in current else "0"
        work_type_expr = "work_type" if "work_type" in current else "''"
        revenue_expr = "monthly_revenue" if "monthly_revenue" in current else "0"
        marital_expr = "marital_status" if "marital_status" in current else "''"
        has_children_expr = "has_children" if "has_children" in current else "0"
        own_children_expr = "own_children_count" if "own_children_count" in current else "0"
        lives_expr = "lives_with_family" if "lives_with_family" in current else "1"
        dependent_expr = "is_dependent" if "is_dependent" in current else "1"
        breadwinner_expr = "is_breadwinner" if "is_breadwinner" in current else "0"
        dep_level_expr = "dependency_level" if "dependency_level" in current else "''"

        extra_defs = ", ".join(f'"{col}" TEXT' for col in extra_cols)
        c.execute(f"""CREATE TABLE child_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER, name TEXT, birth_date TEXT DEFAULT '',
            schooling_status TEXT DEFAULT '', health_status TEXT DEFAULT '',
            gender TEXT DEFAULT '', is_orphan INTEGER DEFAULT 0, notes TEXT DEFAULT '',
            is_working INTEGER DEFAULT 0, work_type TEXT DEFAULT '',
            monthly_revenue REAL DEFAULT 0, marital_status TEXT DEFAULT '',
            has_children INTEGER DEFAULT 0, own_children_count INTEGER DEFAULT 0,
            lives_with_family INTEGER DEFAULT 1, is_dependent INTEGER DEFAULT 1,
            is_breadwinner INTEGER DEFAULT 0, dependency_level TEXT DEFAULT ''
            {(', ' + extra_defs) if extra_defs else ''}
        )""")

        insert_cols = canonical_core[1:] + extra_cols
        select_exprs = [family_id_expr, name_expr, birth_expr, school_expr,
                         health_expr, gender_expr, orphan_expr, notes_expr,
                         working_expr, work_type_expr, revenue_expr, marital_expr,
                         has_children_expr, own_children_expr, lives_expr,
                         dependent_expr, breadwinner_expr, dep_level_expr] + extra_cols
        c.execute(f"INSERT INTO child_new ({', '.join(insert_cols)}) "
                  f"SELECT {', '.join(select_exprs)} FROM child")
        c.execute("DROP TABLE child")
        c.execute("ALTER TABLE child_new RENAME TO child")
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(table, columns):
    """Vérifie que `table` possède bien toutes les colonnes de `columns`
    (dict nom -> définition SQL type/défaut) et ajoute automatiquement
    celles qui manquent. Rend l'appli tolérante aux bases de données
    créées avec d'anciennes versions du schéma."""
    conn = connect()
    try:
        c = conn.cursor()
        c.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in c.fetchall()}
        for col_name, col_def in columns.items():
            if col_name not in existing_cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
        conn.commit()
    finally:
        conn.close()

# ── FAMILLES ──────────────────────────────────────────────────────────────────
# Index map : [0]id [1]head_name [2]spouse_name [3]phone [4]address [5]postal_account
#             [6]monthly_income [7]rent_amount [8]employment_status [9]income_sources
#             [10]marital_status [11]total_members [12]social_status [13]health_status
#             [14]chronic_diseases [15]is_renting [16]housing_type [17]housing_surface
#             [18]rooms_count [19]housing_condition [20]svf_score [21]is_active [22]age

def get_all_families():
    return fetch_all("SELECT * FROM family WHERE is_active=1 ORDER BY id DESC")

def add_family(head_name, spouse_name, phone, address, postal_account,
               monthly_income, rent_amount, employment_status, income_sources,
               marital_status, total_members, social_status, health_status,
               chronic_diseases, is_renting, housing_type, housing_surface,
               rooms_count, housing_condition, svf_score, age=0,
               specific_needs="", emergency_contact="", registration_date=None):
    # Date d'enregistrement : utilisée par l'alerte "famille sans aide depuis
    # plus de X mois". Auto-remplie à aujourd'hui si non fournie.
    if not registration_date:
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    return execute_query("""INSERT INTO family (
        head_name, spouse_name, phone, address, postal_account,
        monthly_income, rent_amount, employment_status, income_sources,
        marital_status, total_members, social_status, health_status,
        chronic_diseases, is_renting, housing_type, housing_surface,
        rooms_count, housing_condition, svf_score, age,
        specific_needs, emergency_contact, registration_date
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (head_name, spouse_name, phone, address, postal_account,
     monthly_income, rent_amount, employment_status, income_sources,
     marital_status, total_members, social_status, health_status,
     chronic_diseases, is_renting, housing_type, housing_surface,
     rooms_count, housing_condition, svf_score, age,
     specific_needs, emergency_contact, registration_date))

def update_family(fid, head_name, spouse_name, phone, address, postal_account,
                  monthly_income, rent_amount, employment_status, income_sources,
                  marital_status, total_members, social_status, health_status,
                  chronic_diseases, is_renting, housing_type, housing_surface,
                  rooms_count, housing_condition, svf_score, age=0,
                  specific_needs="", emergency_contact=""):
    execute_query("""UPDATE family SET
        head_name=?, spouse_name=?, phone=?, address=?, postal_account=?,
        monthly_income=?, rent_amount=?, employment_status=?, income_sources=?,
        marital_status=?, total_members=?, social_status=?, health_status=?,
        chronic_diseases=?, is_renting=?, housing_type=?, housing_surface=?,
        rooms_count=?, housing_condition=?, svf_score=?, age=?,
        specific_needs=?, emergency_contact=?
        WHERE id=?""",
    (head_name, spouse_name, phone, address, postal_account,
     monthly_income, rent_amount, employment_status, income_sources,
     marital_status, total_members, social_status, health_status,
     chronic_diseases, is_renting, housing_type, housing_surface,
     rooms_count, housing_condition, svf_score, age,
     specific_needs, emergency_contact, fid))

def delete_family(fid):
    execute_query("UPDATE family SET is_active=0 WHERE id=?", (fid,))

# ── DOCUMENTS JUSTIFICATIFS ────────────────────────────────────────────────────
def get_family_documents(family_id):
    return fetch_all("SELECT * FROM family_document WHERE family_id=? ORDER BY id", (family_id,))

def add_family_document(family_id, original_name, stored_path):
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    return execute_query(
        "INSERT INTO family_document (family_id, original_name, stored_path, added_date) VALUES (?,?,?,?)",
        (family_id, original_name, stored_path, date_str)
    )

def delete_family_document(doc_id):
    execute_query("DELETE FROM family_document WHERE id=?", (doc_id,))

# ── ENFANTS ───────────────────────────────────────────────────────────────────
# Schéma : [0]id [1]family_id [2]name [3]birth_date [4]schooling_status
#          [5]health_status [6]gender [7]is_orphan [8]notes
#          [9]is_working [10]work_type [11]monthly_revenue [12]marital_status
#          [13]has_children [14]own_children_count [15]lives_with_family
#          [16]is_dependent [17]is_breadwinner [18]dependency_level

def get_children_by_family(family_id):
    return fetch_all("SELECT * FROM child WHERE family_id=? ORDER BY id", (family_id,))

def get_children_count(family_id):
    row = fetch_one("SELECT COUNT(*) FROM child WHERE family_id=?", (family_id,))
    return row[0] if row else 0

def get_orphan_children_count(family_id):
    """Nombre d'enfants marqués comme orphelins pour cette famille."""
    row = fetch_one("SELECT COUNT(*) FROM child WHERE family_id=? AND is_orphan=1", (family_id,))
    return row[0] if row else 0

def family_is_renting(family_row):
    """Interprète la colonne is_renting (stockée en TEXT, valeurs possibles :
    0/1, '0'/'1', ou 'Oui | نعم') et renvoie un booléen fiable."""
    return str(family_row).strip() in ("1", "Oui | نعم", "Oui")

def add_child(family_id, name, birth_date, schooling_status, health_status,
              gender="", is_orphan=0, notes="",
              is_working=0, work_type="", monthly_revenue=0,
              marital_status="", has_children=0, own_children_count=0,
              lives_with_family=1, is_dependent=1, is_breadwinner=0,
              dependency_level=""):
    execute_query("""INSERT INTO child (
        family_id, name, birth_date, schooling_status, health_status,
        gender, is_orphan, notes,
        is_working, work_type, monthly_revenue, marital_status,
        has_children, own_children_count, lives_with_family,
        is_dependent, is_breadwinner, dependency_level
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (family_id, name, birth_date, schooling_status, health_status,
     gender, is_orphan, notes,
     is_working, work_type, monthly_revenue, marital_status,
     has_children, own_children_count, lives_with_family,
     is_dependent, is_breadwinner, dependency_level))

def update_child(cid, name, birth_date, schooling_status, health_status,
                 gender="", is_orphan=0, notes="",
                 is_working=0, work_type="", monthly_revenue=0,
                 marital_status="", has_children=0, own_children_count=0,
                 lives_with_family=1, is_dependent=1, is_breadwinner=0,
                 dependency_level=""):
    execute_query("""UPDATE child SET
        name=?, birth_date=?, schooling_status=?, health_status=?,
        gender=?, is_orphan=?, notes=?,
        is_working=?, work_type=?, monthly_revenue=?, marital_status=?,
        has_children=?, own_children_count=?, lives_with_family=?,
        is_dependent=?, is_breadwinner=?, dependency_level=?
        WHERE id=?""",
    (name, birth_date, schooling_status, health_status,
     gender, is_orphan, notes,
     is_working, work_type, monthly_revenue, marital_status,
     has_children, own_children_count, lives_with_family,
     is_dependent, is_breadwinner, dependency_level, cid))

def delete_child(cid):
    execute_query("DELETE FROM child WHERE id=?", (cid,))

def _parse_range(term):
    """Découpe une chaîne 'min|max' (utilisée par les critères de recherche
    « entre X et Y ») en deux float. Renvoie (None, None) si invalide."""
    try:
        lo_str, hi_str = str(term).split("|")
        lo, hi = float(lo_str), float(hi_str)
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi
    except (ValueError, AttributeError):
        return None, None


# Champs sans valeur requise (le critère seul suffit à filtrer, ex: "Enfant
# qui travaille") : la recherche doit s'exécuter même si `term` est vide.
NO_VALUE_FIELDS = ('revenu_smic', 'child_working')


def search_families(term, field='all'):
    if not term and field not in NO_VALUE_FIELDS:
        return get_all_families()
    if field == 'all':
        q = "SELECT * FROM family WHERE is_active=1 AND (head_name LIKE ? OR phone LIKE ? OR address LIKE ?)"
        return fetch_all(q, (f"%{term}%", f"%{term}%", f"%{term}%"))
    elif field in ['head_name', 'phone', 'social_status', 'employment_status', 'marital_status',
                   'spouse_name', 'address', 'postal_account', 'emergency_contact']:
        return fetch_all(f"SELECT * FROM family WHERE is_active=1 AND {field} LIKE ?", (f"%{term}%",))
    elif field == 'chronic_diseases':
        return fetch_all("SELECT * FROM family WHERE is_active=1 AND (chronic_diseases LIKE ? OR health_status LIKE ?)",
                         (f"%{term}%", f"%{term}%"))
    elif field == 'chronic_diseases_only':
        return fetch_all("SELECT * FROM family WHERE is_active=1 AND chronic_diseases LIKE ?", (f"%{term}%",))
    elif field == 'monthly_income':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND monthly_income <= ?", (float(term),))
        except ValueError: return get_all_families()
    elif field == 'monthly_income_range':
        lo, hi = _parse_range(term)
        if lo is None: return get_all_families()
        return fetch_all("SELECT * FROM family WHERE is_active=1 AND monthly_income BETWEEN ? AND ?", (lo, hi))
    elif field == 'revenu_smic':
        return fetch_all("SELECT * FROM family WHERE is_active=1 AND monthly_income < 20000", ())
    elif field == 'rent_amount_ge':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND rent_amount >= ?", (float(term),))
        except ValueError: return get_all_families()
    elif field == 'is_renting':
        want_yes = str(term).strip().startswith("Oui")
        return [r for r in get_all_families() if family_is_renting(r[15]) == want_yes]
    elif field == 'svf_score':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND svf_score >= ?", (float(term),))
        except ValueError: return get_all_families()
    elif field == 'svf_score_le':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND svf_score <= ?", (float(term),))
        except ValueError: return get_all_families()
    elif field == 'svf_score_range':
        lo, hi = _parse_range(term)
        if lo is None: return get_all_families()
        return fetch_all("SELECT * FROM family WHERE is_active=1 AND svf_score BETWEEN ? AND ?", (lo, hi))
    elif field == 'total_members':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND total_members = ?", (int(term),))
        except ValueError: return get_all_families()
    elif field == 'age':
        try: return fetch_all("SELECT * FROM family WHERE is_active=1 AND age = ?", (int(term),))
        except ValueError: return get_all_families()
    elif field == 'child_name':
        q = """SELECT * FROM family WHERE is_active=1 AND id IN
               (SELECT family_id FROM child WHERE name LIKE ?)"""
        return fetch_all(q, (f"%{term}%",))
    elif field == 'children_count_ge':
        try: n = int(term)
        except ValueError: return get_all_families()
        q = """SELECT * FROM family WHERE is_active=1 AND id IN
               (SELECT family_id FROM child GROUP BY family_id HAVING COUNT(*) >= ?)"""
        return fetch_all(q, (n,))
    elif field == 'orphans_count_ge':
        try: n = int(term)
        except ValueError: return get_all_families()
        q = """SELECT * FROM family WHERE is_active=1 AND id IN
               (SELECT family_id FROM child WHERE is_orphan=1 GROUP BY family_id HAVING COUNT(*) >= ?)"""
        return fetch_all(q, (n,))
    elif field == 'child_schooling':
        not_schooled = "Non scolarisé | غير متمدرس"
        if str(term).startswith("Non"):
            q = """SELECT * FROM family WHERE is_active=1 AND id IN
                   (SELECT family_id FROM child WHERE schooling_status = ?)"""
            return fetch_all(q, (not_schooled,))
        else:
            q = """SELECT * FROM family WHERE is_active=1 AND id IN
                   (SELECT family_id FROM child WHERE schooling_status != '' AND schooling_status != ?)"""
            return fetch_all(q, (not_schooled,))
    elif field == 'child_working':
        q = """SELECT * FROM family WHERE is_active=1 AND id IN
               (SELECT family_id FROM child WHERE is_working=1)"""
        return fetch_all(q, ())
    elif field == 'child_schooling_level':
        q = """SELECT * FROM family WHERE is_active=1 AND id IN
               (SELECT family_id FROM child WHERE schooling_status LIKE ?)"""
        return fetch_all(q, (f"%{term}%",))
    return get_all_families()

# ── DONATEURS ─────────────────────────────────────────────────────────────────
def get_all_donors():
    return fetch_all("SELECT id, name, phone, age FROM donor WHERE is_active=1 ORDER BY id DESC")

def add_donor(name, phone, email, age=0):
    execute_query("INSERT INTO donor (name, phone, email, age) VALUES (?,?,?,?)", (name, phone, email, age))

def delete_donor(did):
    execute_query("UPDATE donor SET is_active=0 WHERE id=?", (did,))

# ── DONS ──────────────────────────────────────────────────────────────────────
def get_all_donations():
    """→ (id, donor_name, amount, donation_type, donation_date, notes, category, item_name, quantity, unit)"""
    return fetch_all("""
        SELECT d.id, dn.name, d.amount, d.donation_type, d.donation_date, d.notes,
               d.category, d.item_name, d.quantity, d.unit
        FROM donation d JOIN donor dn ON d.donor_id = dn.id
        ORDER BY d.donation_date DESC
    """)

def add_donation(donor_id, amount, donation_type, notes="", category="Espèce",
                  item_name="", quantity=0, unit="unité(s)"):
    """category : 'Espèce' (don en argent) ou 'Nature' (don en objets : cartables,
    vêtements, nourriture, matériel scolaire, etc.). Pour un don en nature,
    `amount` est optionnel (valeur estimée, peut être 0) et `item_name`/`quantity`/`unit`
    décrivent les objets donnés (ex: 5 kg de Riz, 10 unité(s) de Cartables)."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        """INSERT INTO donation (donor_id, amount, donation_type, donation_date,
           notes, category, item_name, quantity, unit) VALUES (?,?,?,?,?,?,?,?,?)""",
        (donor_id, amount, donation_type, date_str, notes, category, item_name, quantity, unit)
    )

def delete_donation(did):
    execute_query("DELETE FROM donation WHERE id=?", (did,))

# ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────
def get_all_distributions():
    """→ (id, head_name, amount, distribution_type, distribution_date, notes)"""
    return fetch_all("""
        SELECT d.id, f.head_name, d.amount, d.distribution_type, d.distribution_date, d.notes
        FROM distribution d JOIN family f ON d.family_id = f.id
        ORDER BY d.distribution_date DESC
    """)

def add_distribution(family_id, amount, dist_type, notes=""):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        "INSERT INTO distribution (family_id, amount, distribution_type, distribution_date, notes) VALUES (?,?,?,?,?)",
        (family_id, amount, dist_type, date_str, notes)
    )

def delete_distribution(did):
    execute_query("DELETE FROM distribution WHERE id=?", (did,))

def get_families_with_distributions_summary():
    """Familles ayant bénéficié d'au moins une distribution (aide reçue) :
    → [(family_id, head_name, nb_distributions, montant_total), ...]
    triées par montant total décroissant."""
    return fetch_all("""
        SELECT f.id, f.head_name, COUNT(d.id) AS nb_dist, COALESCE(SUM(d.amount), 0) AS total
        FROM family f
        JOIN distribution d ON d.family_id = f.id
        WHERE f.is_active = 1
        GROUP BY f.id
        ORDER BY total DESC
    """)

def get_families_without_distributions():
    """Familles actives n'ayant JAMAIS reçu de distribution (aide) :
    → [(family_id, head_name, phone, svf_score), ...] triées par score SVF décroissant
    (les plus vulnérables d'abord, pour prioriser)."""
    return fetch_all("""
        SELECT f.id, f.head_name, f.phone, f.svf_score
        FROM family f
        WHERE f.is_active = 1
          AND f.id NOT IN (SELECT DISTINCT family_id FROM distribution WHERE family_id IS NOT NULL)
        ORDER BY f.svf_score DESC
    """)

def get_families_overdue_without_help(days=None):
    """Familles actives enregistrées depuis plus de `days` jours (paramètre
    configurable dans Paramètres, clé 'alert_no_donation_days', 60 par défaut)
    et n'ayant JAMAIS reçu de distribution (aide) depuis leur enregistrement.
    → [(family_id, head_name, phone, registration_date, svf_score), ...]
    triées par score SVF décroissant (les plus vulnérables d'abord)."""
    if days is None:
        try:
            days = float(get_setting("alert_no_donation_days", 60))
        except (TypeError, ValueError):
            days = 60
    return fetch_all("""
        SELECT f.id, f.head_name, f.phone, f.registration_date, f.svf_score
        FROM family f
        WHERE f.is_active = 1
          AND f.registration_date != ''
          AND julianday('now') - julianday(f.registration_date) >= ?
          AND f.id NOT IN (SELECT DISTINCT family_id FROM distribution WHERE family_id IS NOT NULL)
        ORDER BY f.svf_score DESC
    """, (days,))


def get_working_children(term=""):
    """Enfants qui travaillent, avec le nom du chef de famille (le "père" /
    responsable du foyer), filtrables par nom de famille (head_name).
    → [(child_id, child_name, work_type, monthly_revenue, family_id, head_name), ...]"""
    if term:
        return fetch_all("""
            SELECT c.id, c.name, c.work_type, c.monthly_revenue, f.id, f.head_name
            FROM child c JOIN family f ON c.family_id = f.id
            WHERE c.is_working = 1 AND f.is_active = 1 AND f.head_name LIKE ?
            ORDER BY f.head_name
        """, (f"%{term}%",))
    return fetch_all("""
        SELECT c.id, c.name, c.work_type, c.monthly_revenue, f.id, f.head_name
        FROM child c JOIN family f ON c.family_id = f.id
        WHERE c.is_working = 1 AND f.is_active = 1
        ORDER BY f.head_name
    """)


# ── DÉPENSES MOSQUÉE (femme de ménage, entretien, ...) ────────────────────────
def get_expense_categories():
    """→ [(id, name), ...]"""
    return fetch_all("SELECT id, name FROM mosque_expense_category ORDER BY name")

def add_expense_category(name):
    name = name.strip()
    if not name:
        return None
    return execute_query("INSERT OR IGNORE INTO mosque_expense_category (name) VALUES (?)", (name,))

def delete_expense_category(cat_id):
    """Supprime une catégorie. Les dépenses déjà enregistrées avec cette
    catégorie sont conservées (leur category_id devient orphelin, affiché
    comme "Catégorie supprimée")."""
    execute_query("DELETE FROM mosque_expense_category WHERE id=?", (cat_id,))

def get_all_mosque_expenses():
    """→ (id, category_name, label, amount, expense_date, notes, beneficiary,
    attachment_path, validated_by, envelope_name)"""
    return fetch_all("""
        SELECT e.id, COALESCE(c.name, 'Catégorie supprimée | فئة محذوفة'),
               e.label, e.amount, e.expense_date, e.notes,
               COALESCE(e.beneficiary, ''), COALESCE(e.attachment_path, ''),
               COALESCE(e.validated_by, ''), COALESCE(env.name, '')
        FROM mosque_expense e
        LEFT JOIN mosque_expense_category c ON e.category_id = c.id
        LEFT JOIN envelope env ON e.envelope_id = env.id
        ORDER BY e.expense_date DESC
    """)

def add_mosque_expense(category_id, label, amount, notes="", beneficiary="",
                        attachment_path="", validated_by="", envelope_id=None):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        """INSERT INTO mosque_expense (category_id, label, amount, expense_date, notes,
           beneficiary, attachment_path, validated_by, envelope_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (category_id, label, amount, date_str, notes, beneficiary,
         attachment_path, validated_by, envelope_id)
    )

def delete_mosque_expense(exp_id):
    execute_query("DELETE FROM mosque_expense WHERE id=?", (exp_id,))

def get_total_mosque_expenses():
    return fetch_one("SELECT SUM(amount) FROM mosque_expense")[0] or 0.0

def get_known_beneficiaries():
    """Noms de bénéficiaires déjà utilisés (dépenses passées + répertoire des
    paiements), pour l'auto-complétion du champ Bénéficiaire."""
    names = set()
    for (name,) in fetch_all(
            "SELECT DISTINCT beneficiary FROM mosque_expense WHERE beneficiary != ''"):
        names.add(name)
    for (name,) in fetch_all("SELECT name FROM payee WHERE is_active=1"):
        names.add(name)
    return sorted(names)


# ── PAIEMENTS (imam, muezzin, agents d'entretien, artisans, prestataires) ─────
ROLES_PAYEE = ["Imam | إمام", "Muezzin | مؤذن", "Agent d'entretien | عامل نظافة",
               "Artisan | حرفي", "Fournisseur | مورد", "Autre | أخرى"]
PAYMENT_TYPES = ["Régulier | دوري", "Occasionnel | مناسباتي"]
PAYMENT_MODES = ["Espèces | نقداً", "Virement | تحويل", "Chèque | صك"]

def get_all_payees(active_only=True):
    """→ [(id, name, role, payment_type, usual_amount, payment_mode, contact), ...]"""
    q = "SELECT id, name, role, payment_type, usual_amount, payment_mode, contact FROM payee"
    if active_only:
        q += " WHERE is_active=1"
    return fetch_all(q + " ORDER BY name")

def add_payee(name, role, payment_type, usual_amount, payment_mode, contact=""):
    return execute_query(
        """INSERT INTO payee (name, role, payment_type, usual_amount, payment_mode, contact)
           VALUES (?,?,?,?,?,?)""",
        (name, role, payment_type, usual_amount, payment_mode, contact)
    )

def update_payee(payee_id, name, role, payment_type, usual_amount, payment_mode, contact=""):
    execute_query(
        """UPDATE payee SET name=?, role=?, payment_type=?, usual_amount=?,
           payment_mode=?, contact=? WHERE id=?""",
        (name, role, payment_type, usual_amount, payment_mode, contact, payee_id)
    )

def delete_payee(payee_id):
    """Suppression douce : conserve l'historique des paiements déjà effectués."""
    execute_query("UPDATE payee SET is_active=0 WHERE id=?", (payee_id,))

def get_all_payments():
    """→ (id, payee_name, role, amount, payment_date, period_covered, payment_mode, remark, status, payee_id, envelope_name)"""
    return fetch_all("""
        SELECT pay.id, p.name, p.role, pay.amount, pay.payment_date, pay.period_covered,
               pay.payment_mode, pay.remark, pay.status, pay.payee_id, COALESCE(env.name, '')
        FROM payment pay JOIN payee p ON pay.payee_id = p.id
        LEFT JOIN envelope env ON pay.envelope_id = env.id
        ORDER BY pay.payment_date DESC
    """)

def get_payments_for_payee(payee_id):
    """→ (id, amount, payment_date, period_covered, payment_mode, remark, status) pour un bénéficiaire."""
    return fetch_all("""
        SELECT id, amount, payment_date, period_covered, payment_mode, remark, status
        FROM payment WHERE payee_id=? ORDER BY payment_date DESC
    """, (payee_id,))

def add_payment(payee_id, amount, period_covered, payment_mode, remark="", status="Payé",
                date_str=None, envelope_id=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        """INSERT INTO payment (payee_id, amount, payment_date, period_covered,
           payment_mode, remark, status, envelope_id) VALUES (?,?,?,?,?,?,?,?)""",
        (payee_id, amount, date_str, period_covered, payment_mode, remark, status, envelope_id)
    )

def delete_payment(payment_id):
    execute_query("DELETE FROM payment WHERE id=?", (payment_id,))

def get_total_payments():
    return fetch_one("SELECT SUM(amount) FROM payment WHERE status='Payé'")[0] or 0.0

def get_payee_total_paid(payee_id):
    return fetch_one("SELECT SUM(amount) FROM payment WHERE payee_id=? AND status='Payé'",
                      (payee_id,))[0] or 0.0

def get_payment_alerts():
    """Calcule les échéances pour les bénéficiaires 'Régulier' à partir de leur
    dernier paiement (+ ~1 mois). Retourne deux listes :
    - reminders : échéance dans les 3 prochains jours (rappel J-3)
    - overdue   : échéance dépassée d'au moins 1 jour sans paiement depuis (J+1)
    → {'reminders': [(payee_id, name, due_date), ...], 'overdue': [(payee_id, name, due_date), ...]}"""
    reminders, overdue = [], []
    today = datetime.now()
    for pid, name, role, ptype, usual, mode, contact in get_all_payees():
        if not ptype.startswith("Régulier"):
            continue
        last = fetch_one(
            "SELECT payment_date FROM payment WHERE payee_id=? ORDER BY payment_date DESC LIMIT 1",
            (pid,))
        if last is None:
            continue  # jamais payé : pas d'échéance calculable, apparaît plutôt en historique vide
        try:
            last_date = datetime.strptime(last[0][:10], "%Y-%m-%d")
        except ValueError:
            continue
        # Échéance approximative : 1 mois (30 jours) après le dernier versement
        due_date = last_date + timedelta(days=30)
        delta_days = (due_date - today).days
        if 0 <= delta_days <= 3:
            reminders.append((pid, name, due_date.strftime("%Y-%m-%d")))
        elif delta_days < 0:
            overdue.append((pid, name, due_date.strftime("%Y-%m-%d")))
    return {"reminders": reminders, "overdue": overdue}

def get_upcoming_payments(days=7):
    """Échéances des `days` prochains jours pour les bénéficiaires réguliers
    (widget 'Prochains paiements' du tableau de bord).
    → [(payee_id, name, usual_amount, due_date), ...] triées par date."""
    out = []
    today = datetime.now()
    for pid, name, role, ptype, usual, mode, contact in get_all_payees():
        if not ptype.startswith("Régulier"):
            continue
        last = fetch_one(
            "SELECT payment_date FROM payment WHERE payee_id=? ORDER BY payment_date DESC LIMIT 1",
            (pid,))
        if last is None:
            continue
        try:
            last_date = datetime.strptime(last[0][:10], "%Y-%m-%d")
        except ValueError:
            continue
        due_date = last_date + timedelta(days=30)
        delta_days = (due_date - today).days
        if 0 <= delta_days <= days:
            out.append((pid, name, usual, due_date.strftime("%Y-%m-%d")))
    out.sort(key=lambda r: r[3])
    return out


# ── ENVELOPPES BUDGÉTAIRES ────────────────────────────────────────────────────
ENVELOPE_PERIODS = ["Mensuelle | شهرية", "Trimestrielle | فصلية", "Annuelle | سنوية",
                     "Ponctuelle | لمرة واحدة"]
ENVELOPE_STATUSES = ["Active | نشطة", "Suspendue | معلقة", "Clôturée | مغلقة"]

def get_all_envelopes(active_only=True):
    """→ [(id, name, allocated_budget, period, alert_threshold_pct, description, status), ...]"""
    q = """SELECT id, name, allocated_budget, period, alert_threshold_pct, description, status
           FROM envelope"""
    if active_only:
        q += " WHERE status = 'Active | نشطة'"
    return fetch_all(q + " ORDER BY name")

def add_envelope(name, allocated_budget, period, alert_threshold_pct, description=""):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return execute_query(
        """INSERT INTO envelope (name, allocated_budget, period, alert_threshold_pct,
           description, status, created_date) VALUES (?,?,?,?,?,?,?)""",
        (name, allocated_budget, period, alert_threshold_pct, description,
         "Active | نشطة", date_str)
    )

def update_envelope(envelope_id, name, allocated_budget, period, alert_threshold_pct,
                     description, status):
    execute_query(
        """UPDATE envelope SET name=?, allocated_budget=?, period=?, alert_threshold_pct=?,
           description=?, status=? WHERE id=?""",
        (name, allocated_budget, period, alert_threshold_pct, description, status, envelope_id)
    )

def close_envelope(envelope_id):
    execute_query("UPDATE envelope SET status='Clôturée | مغلقة' WHERE id=?", (envelope_id,))

def get_envelope_spent(envelope_id):
    """Total dépensé sur une enveloppe : dépenses mosquée + paiements qui lui
    sont imputés."""
    spent_exp = fetch_one(
        "SELECT SUM(amount) FROM mosque_expense WHERE envelope_id=?", (envelope_id,))[0] or 0.0
    spent_pay = fetch_one(
        "SELECT SUM(amount) FROM payment WHERE envelope_id=? AND status='Payé'",
        (envelope_id,))[0] or 0.0
    return spent_exp + spent_pay

def get_envelope_debt_adjustment(envelope_id):
    """Ajustement du budget effectif dû aux prélèvements exceptionnels non
    remboursés : positif si l'enveloppe a EMPRUNTÉ (budget effectif augmenté),
    négatif si elle a PRÊTÉ à une autre enveloppe (budget effectif réduit)."""
    borrowed = fetch_one(
        """SELECT SUM(amount - repaid_amount) FROM envelope_transfer
           WHERE target_envelope_id=? AND is_settled=0""", (envelope_id,))[0] or 0.0
    lent = fetch_one(
        """SELECT SUM(amount - repaid_amount) FROM envelope_transfer
           WHERE source_envelope_id=? AND is_settled=0""", (envelope_id,))[0] or 0.0
    return borrowed - lent

def get_envelope_summary():
    """→ liste enrichie pour affichage carte : dict avec allocated, spent,
    effective_budget (ajusté des dettes), remaining, pct_used, level
    ('ok'/'warning'/'critical'), last_movement."""
    out = []
    for eid, name, allocated, period, threshold, desc, status in get_all_envelopes(active_only=True):
        spent = get_envelope_spent(eid)
        adjustment = get_envelope_debt_adjustment(eid)
        effective = allocated + adjustment
        remaining = effective - spent
        pct_remaining = (remaining / effective * 100) if effective > 0 else 0
        if pct_remaining < threshold:
            level = "critical"
        elif pct_remaining < 50:
            level = "warning"
        else:
            level = "ok"
        last = fetch_one(
            """SELECT MAX(d) FROM (
                 SELECT expense_date AS d FROM mosque_expense WHERE envelope_id=?
                 UNION ALL SELECT payment_date FROM payment WHERE envelope_id=?
               )""", (eid, eid))[0]
        out.append({
            "id": eid, "name": name, "allocated": allocated, "period": period,
            "threshold": threshold, "description": desc, "status": status,
            "spent": spent, "effective_budget": effective, "remaining": remaining,
            "pct_remaining": pct_remaining, "level": level, "last_movement": last or "—",
        })
    return out

def add_envelope_transfer(source_id, target_id, amount, reason=""):
    """Prélèvement exceptionnel : l'enveloppe source prête `amount` à
    l'enveloppe cible. Crée une dette inter-enveloppes à rembourser."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return execute_query(
        """INSERT INTO envelope_transfer (source_envelope_id, target_envelope_id, amount,
           transfer_date, reason) VALUES (?,?,?,?,?)""",
        (source_id, target_id, amount, date_str, reason)
    )

def get_unsettled_debts():
    """→ [(id, source_name, target_name, amount, repaid_amount, remaining, date, reason), ...]"""
    return fetch_all("""
        SELECT t.id, s.name, tg.name, t.amount, t.repaid_amount,
               t.amount - t.repaid_amount, t.transfer_date, t.reason
        FROM envelope_transfer t
        JOIN envelope s ON t.source_envelope_id = s.id
        JOIN envelope tg ON t.target_envelope_id = tg.id
        WHERE t.is_settled = 0
        ORDER BY t.transfer_date
    """)

def repay_envelope_transfer(transfer_id, repay_amount):
    row = fetch_one("SELECT amount, repaid_amount FROM envelope_transfer WHERE id=?", (transfer_id,))
    if not row:
        return
    amount, repaid = row
    new_repaid = min(amount, repaid + repay_amount)
    settled = 1 if new_repaid >= amount else 0
    execute_query(
        "UPDATE envelope_transfer SET repaid_amount=?, is_settled=? WHERE id=?",
        (new_repaid, settled, transfer_id)
    )

def get_total_unsettled_debts():
    return fetch_one(
        "SELECT SUM(amount - repaid_amount) FROM envelope_transfer WHERE is_settled=0"
    )[0] or 0.0

def get_envelopes_to_replenish():
    """→ {'critical': [...], 'warning': [...], 'debts': [...]} pour l'écran/
    widget 'Enveloppes à réapprovisionner'."""
    summary = get_envelope_summary()
    return {
        "critical": [e for e in summary if e["level"] == "critical"],
        "warning": [e for e in summary if e["level"] == "warning"],
        "debts": get_unsettled_debts(),
    }

def get_envelope_movements(envelope_id):
    """Toutes les dépenses/paiements imputés à une enveloppe.
    → [(date, libelle, amount, type), ...] triés par date décroissante."""
    rows = []
    for date, label, amount, cat in fetch_all(
            """SELECT e.expense_date, e.label, e.amount, COALESCE(c.name,'')
               FROM mosque_expense e LEFT JOIN mosque_expense_category c ON e.category_id=c.id
               WHERE e.envelope_id=?""", (envelope_id,)):
        rows.append((date, f"Dépense — {label or cat}", amount, "Dépense"))
    for date, name, amount, period in fetch_all(
            """SELECT pay.payment_date, p.name, pay.amount, pay.period_covered
               FROM payment pay JOIN payee p ON pay.payee_id=p.id
               WHERE pay.envelope_id=? AND pay.status='Payé'""", (envelope_id,)):
        rows.append((date, f"Paiement — {name}" + (f" ({period})" if period else ""), amount, "Paiement"))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows

def get_all_envelope_transfers():
    """→ [(id, source_name, target_name, amount, repaid_amount, transfer_date, reason, is_settled), ...]
    Historique complet (réglées + en cours), pour le rapport annuel."""
    return fetch_all("""
        SELECT t.id, s.name, tg.name, t.amount, t.repaid_amount, t.transfer_date,
               t.reason, t.is_settled
        FROM envelope_transfer t
        JOIN envelope s ON t.source_envelope_id = s.id
        JOIN envelope tg ON t.target_envelope_id = tg.id
        ORDER BY t.transfer_date DESC
    """)


# ── GESTION DES STOCKS ────────────────────────────────────────────────────────
STOCK_CATEGORIES = ["Nettoyage | تنظيف", "Hygiène | نظافة", "Électricité | كهرباء",
                    "Bureau | مكتب", "Culte | عبادة", "Autre | أخرى"]
STOCK_UNITS = ["Litre", "Unité", "Carton", "Kg", "Rouleau"]

def get_all_stock_items(active_only=True):
    """→ [(id, name, category, unit, current_stock, reorder_threshold, usual_supplier, last_updated), ...]"""
    q = """SELECT id, name, category, unit, current_stock, reorder_threshold,
                  usual_supplier, last_updated FROM stock_item"""
    if active_only:
        q += " WHERE is_active=1"
    return fetch_all(q + " ORDER BY name")

def add_stock_item(name, category, unit, reorder_threshold, usual_supplier="", initial_stock=0):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return execute_query(
        """INSERT INTO stock_item (name, category, unit, current_stock, reorder_threshold,
           usual_supplier, last_updated) VALUES (?,?,?,?,?,?,?)""",
        (name, category, unit, initial_stock, reorder_threshold, usual_supplier, date_str)
    )

def update_stock_item(item_id, name, category, unit, reorder_threshold, usual_supplier):
    execute_query(
        """UPDATE stock_item SET name=?, category=?, unit=?, reorder_threshold=?,
           usual_supplier=? WHERE id=?""",
        (name, category, unit, reorder_threshold, usual_supplier, item_id)
    )

def delete_stock_item(item_id):
    """Suppression douce : conserve l'historique des mouvements déjà enregistrés."""
    execute_query("UPDATE stock_item SET is_active=0 WHERE id=?", (item_id,))

def add_stock_movement(item_id, movement_type, quantity, notes=""):
    """movement_type : 'Entrée' (+qty), 'Sortie' (-qty), 'Inventaire' (fixe le
    stock directement à `quantity`, avec justification dans `notes`)."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        """INSERT INTO stock_movement (item_id, movement_type, quantity, movement_date, notes)
           VALUES (?,?,?,?,?)""",
        (item_id, movement_type, quantity, date_str, notes)
    )
    current = fetch_one("SELECT current_stock FROM stock_item WHERE id=?", (item_id,))[0] or 0
    if movement_type == "Entrée":
        new_stock = current + quantity
    elif movement_type == "Sortie":
        new_stock = max(0, current - quantity)
    else:  # Inventaire : correction manuelle directe
        new_stock = quantity
    execute_query("UPDATE stock_item SET current_stock=?, last_updated=? WHERE id=?",
                  (new_stock, date_str, item_id))

def get_stock_movements(item_id):
    """→ [(id, movement_type, quantity, movement_date, notes), ...]"""
    return fetch_all(
        """SELECT id, movement_type, quantity, movement_date, notes
           FROM stock_movement WHERE item_id=? ORDER BY movement_date DESC""", (item_id,))

def get_low_stock_items():
    """→ {'critical': [...], 'warning': [...]} — critique : stock=0 ou < seuil ;
    attention : entre le seuil et 2× le seuil."""
    critical, warning = [], []
    for row in get_all_stock_items():
        _id, name, cat, unit, stock, threshold, supplier, updated = row
        if stock <= 0 or (threshold > 0 and stock < threshold):
            critical.append(row)
        elif threshold > 0 and stock < 2 * threshold:
            warning.append(row)
    return {"critical": critical, "warning": warning}

def get_shopping_list():
    """Articles à commander (critiques + attention), pour la liste de courses."""
    low = get_low_stock_items()
    return low["critical"] + low["warning"]


# ── GESTION DES ÉQUIPEMENTS ───────────────────────────────────────────────────
EQUIPMENT_CATEGORIES = ["Climatisation | تكييف", "Mobilier | أثاث", "Sonorisation | صوتيات",
                        "Éclairage | إنارة", "Sanitaire | صحي", "Sécurité | أمن", "Autre | أخرى"]
EQUIPMENT_CONDITIONS = ["Bon état | حالة جيدة", "Usé | مستعمل", "En panne | معطل",
                        "Hors service | خارج الخدمة"]
EQUIPMENT_LOCATIONS = ["Salle principale | القاعة الرئيسية", "Salle d'ablution | قاعة الوضوء",
                       "Bureau | مكتب", "Bibliothèque | مكتبة", "Salle d'activités | قاعة الأنشطة"]
ISSUE_URGENCY = ["Faible | منخفض", "Moyen | متوسط", "Urgent | عاجل"]
ISSUE_STATUSES = ["Signalé | تم الإبلاغ", "En cours | قيد المعالجة", "Résolu | تم الحل"]

def get_all_equipment(active_only=True):
    """→ [(id, name, category, acquisition_date, purchase_price, condition,
    location, photo_path, serial_number, warranty_expiry), ...]"""
    q = """SELECT id, name, category, acquisition_date, purchase_price, condition,
                  location, photo_path, serial_number, warranty_expiry FROM equipment"""
    if active_only:
        q += " WHERE is_active=1"
    return fetch_all(q + " ORDER BY name")

def add_equipment(name, category, acquisition_date, purchase_price, condition,
                  location, photo_path="", serial_number="", warranty_expiry=""):
    return execute_query(
        """INSERT INTO equipment (name, category, acquisition_date, purchase_price, condition,
           location, photo_path, serial_number, warranty_expiry)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (name, category, acquisition_date, purchase_price, condition, location,
         photo_path, serial_number, warranty_expiry)
    )

def update_equipment_condition(equipment_id, condition):
    execute_query("UPDATE equipment SET condition=? WHERE id=?", (condition, equipment_id))

def delete_equipment(equipment_id):
    """Suppression douce : conserve l'historique des signalements."""
    execute_query("UPDATE equipment SET is_active=0 WHERE id=?", (equipment_id,))

def get_equipment_in_panne():
    return [e for e in get_all_equipment()
            if e[5] in ("En panne | معطل", "Hors service | خارج الخدمة")]

def get_equipment_warranty_soon(days=30):
    today = datetime.now()
    out = []
    for e in get_all_equipment():
        expiry = e[9]
        if not expiry:
            continue
        try:
            exp_date = datetime.strptime(expiry[:10], "%Y-%m-%d")
        except ValueError:
            continue
        delta = (exp_date - today).days
        if 0 <= delta <= days:
            out.append(e)
    return out

def add_equipment_issue(equipment_id, description, urgency, assigned_to="", photo_path=""):
    """Signale un problème sur un équipement. Le statut initial est 'Signalé'."""
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return execute_query(
        """INSERT INTO equipment_issue (equipment_id, description, photo_path, urgency,
           assigned_to, status, reported_date) VALUES (?,?,?,?,?,?,?)""",
        (equipment_id, description, photo_path, urgency, assigned_to, ISSUE_STATUSES[0], date_str)
    )

def get_issues_for_equipment(equipment_id):
    return fetch_all(
        """SELECT id, description, urgency, assigned_to, status, reported_date,
                  resolved_date, repair_cost
           FROM equipment_issue WHERE equipment_id=? ORDER BY reported_date DESC""",
        (equipment_id,))

def get_all_open_issues():
    """→ signalements non résolus, tous équipements confondus, pour le tableau
    de bord équipements."""
    return fetch_all("""
        SELECT i.id, e.name, i.description, i.urgency, i.status, i.reported_date
        FROM equipment_issue i JOIN equipment e ON i.equipment_id = e.id
        WHERE i.status != 'Résolu | تم الحل'
        ORDER BY i.reported_date DESC
    """)

def update_issue_status(issue_id, status, repair_cost=None, category_id_for_expense=None,
                        validated_by=""):
    """Met à jour le statut d'un signalement. Si le statut passe à 'Résolu' et
    qu'un coût de réparation est fourni, celui-ci est ENREGISTRÉ COMME DÉPENSE
    liée à l'équipement (règle métier du cahier des charges 6.2)."""
    resolved_date = ""
    if status == ISSUE_STATUSES[2]:  # Résolu
        resolved_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    execute_query(
        "UPDATE equipment_issue SET status=?, resolved_date=?, repair_cost=? WHERE id=?",
        (status, resolved_date, repair_cost or 0, issue_id)
    )
    if status == ISSUE_STATUSES[2] and repair_cost and repair_cost > 0:
        row = fetch_one(
            """SELECT e.name, i.description FROM equipment_issue i
               JOIN equipment e ON i.equipment_id = e.id WHERE i.id=?""", (issue_id,))
        if row:
            eq_name, desc = row
            if category_id_for_expense is None:
                cat_row = fetch_one(
                    "SELECT id FROM mosque_expense_category WHERE name LIKE 'Réparation%'")
                if cat_row:
                    category_id_for_expense = cat_row[0]
                else:
                    category_id_for_expense = add_expense_category("Réparation équipement | إصلاح المعدات")
            add_mosque_expense(category_id_for_expense, f"Réparation — {eq_name}",
                               repair_cost, desc, validated_by=validated_by)


# ── JOURNAL DE CAISSE (détaillé) ──────────────────────────────────────────────
def get_caisse_journal(date_from=None, date_to=None, search=""):
    """Reconstitue le journal de caisse complet et chronologique en unifiant
    toutes les sources de mouvements : dons en espèce (entrées), distributions
    aux familles + dépenses mosquée + paiements aux bénéficiaires (sorties).
    Le solde cumulé est calculé sur TOUT l'historique (pour rester exact), puis
    le résultat est filtré sur la période/le texte demandés.
    → [(date, libelle, entree, sortie, solde_cumule, type), ...] triés par date."""
    rows = []
    for date, name, amount, dtype in fetch_all(
            """SELECT d.donation_date, dn.name, d.amount, d.donation_type
               FROM donation d JOIN donor dn ON d.donor_id = dn.id
               WHERE d.category='Espèce'"""):
        rows.append((date, f"Don de {name} ({dtype})", amount or 0.0, 0.0, "don"))
    for date, name, amount in fetch_all(
            """SELECT dist.distribution_date, f.head_name, dist.amount
               FROM distribution dist JOIN family f ON dist.family_id = f.id"""):
        rows.append((date, f"Aide versée à {name}", 0.0, amount or 0.0, "distribution"))
    for date, cat, amount, label in fetch_all(
            """SELECT e.expense_date, COALESCE(c.name, 'Autre'), e.amount, e.label
               FROM mosque_expense e LEFT JOIN mosque_expense_category c ON e.category_id = c.id"""):
        libelle = f"Dépense {cat}" + (f" — {label}" if label else "")
        rows.append((date, libelle, 0.0, amount or 0.0, "depense"))
    for date, name, amount, period in fetch_all(
            """SELECT pay.payment_date, p.name, pay.amount, pay.period_covered
               FROM payment pay JOIN payee p ON pay.payee_id = p.id
               WHERE pay.status='Payé'"""):
        libelle = f"Paiement à {name}" + (f" ({period})" if period else "")
        rows.append((date, libelle, 0.0, amount or 0.0, "paiement"))

    rows.sort(key=lambda r: r[0])

    full = []
    balance = 0.0
    for date, libelle, entree, sortie, mtype in rows:
        balance += entree - sortie
        full.append((date, libelle, entree, sortie, balance, mtype))

    result = full
    if date_from:
        result = [r for r in result if r[0][:10] >= date_from]
    if date_to:
        result = [r for r in result if r[0][:10] <= date_to]
    if search:
        s = search.lower()
        result = [r for r in result if s in r[1].lower()]
    return list(reversed(result))  # le plus récent en premier, comme l'historique du reste de l'appli

def get_caisse_widget_stats():
    """Solde actuel, entrées/sorties du mois en cours, et variation (%) par
    rapport au mois précédent (basée sur le solde net entrées-sorties)."""
    rows = get_monthly_financial_summary(2)
    this_month = rows[-1] if rows else (None, 0.0, 0.0)
    prev_month = rows[-2] if len(rows) > 1 else (None, 0.0, 0.0)
    net_this = this_month[1] - this_month[2]
    net_prev = prev_month[1] - prev_month[2]
    if net_prev != 0:
        variation = ((net_this - net_prev) / abs(net_prev)) * 100
    else:
        variation = 0.0 if net_this == 0 else 100.0
    _, _, solde = get_financial_summary()
    return {
        "solde": solde,
        "entrees_mois": this_month[1],
        "sorties_mois": this_month[2],
        "variation_pct": variation,
    }


# ── AGRÉGATIONS POUR LES RAPPORTS ─────────────────────────────────────────────
def get_balance_before(date_str):
    """Solde cumulé de la caisse juste AVANT le début de `date_str` (AAAA-MM-JJ).
    Utilisé pour le 'solde d'ouverture' d'un rapport mensuel."""
    journal = get_caisse_journal()  # déjà trié du plus récent au plus ancien
    for date, libelle, entree, sortie, solde, mtype in journal:
        if date[:10] < date_str:
            return solde
    return 0.0

def get_balance_at_end(date_str):
    """Solde cumulé de la caisse à la fin de `date_str` (dernier mouvement
    dont la date est <= date_str). Utilisé pour le 'solde de clôture'."""
    journal = get_caisse_journal()
    for date, libelle, entree, sortie, solde, mtype in journal:
        if date[:10] <= date_str:
            return solde
    return 0.0

def get_donations_breakdown_by_source(date_from=None, date_to=None):
    """→ [(source, total), ...] des dons en espèce, groupés par type/source,
    sur la période donnée."""
    q = "SELECT donation_type, SUM(amount) FROM donation WHERE category='Espèce'"
    params = []
    if date_from:
        q += " AND donation_date >= ?"; params.append(date_from)
    if date_to:
        q += " AND donation_date <= ?"; params.append(date_to + " 23:59")
    q += " GROUP BY donation_type ORDER BY 2 DESC"
    return fetch_all(q, tuple(params))

def get_expenses_breakdown_by_category(date_from=None, date_to=None):
    """→ [(category_name, total), ...] des dépenses mosquée, sur la période."""
    q = """SELECT COALESCE(c.name, 'Autre'), SUM(e.amount)
           FROM mosque_expense e LEFT JOIN mosque_expense_category c ON e.category_id=c.id
           WHERE 1=1"""
    params = []
    if date_from:
        q += " AND e.expense_date >= ?"; params.append(date_from)
    if date_to:
        q += " AND e.expense_date <= ?"; params.append(date_to + " 23:59")
    q += " GROUP BY c.name ORDER BY 2 DESC"
    return fetch_all(q, tuple(params))

def get_payments_in_period(date_from=None, date_to=None):
    """→ [(payee_name, amount, date), ...] paiements versés sur la période."""
    q = """SELECT p.name, pay.amount, pay.payment_date FROM payment pay
           JOIN payee p ON pay.payee_id = p.id WHERE pay.status='Payé'"""
    params = []
    if date_from:
        q += " AND pay.payment_date >= ?"; params.append(date_from)
    if date_to:
        q += " AND pay.payment_date <= ?"; params.append(date_to + " 23:59")
    q += " ORDER BY pay.payment_date DESC"
    return fetch_all(q, tuple(params))

def get_yearly_monthly_summary(year):
    """→ [(mois 'YYYY-MM', total_in, total_out), ...] pour les 12 mois de
    l'année donnée (0 si aucun mouvement), pour le rapport annuel."""
    rows_in = fetch_all(
        "SELECT substr(donation_date,1,7) m, SUM(amount) FROM donation "
        "WHERE category='Espèce' AND substr(donation_date,1,4)=? GROUP BY m", (str(year),))
    rows_out_dist = fetch_all(
        "SELECT substr(distribution_date,1,7) m, SUM(amount) FROM distribution "
        "WHERE substr(distribution_date,1,4)=? GROUP BY m", (str(year),))
    rows_out_exp = fetch_all(
        "SELECT substr(expense_date,1,7) m, SUM(amount) FROM mosque_expense "
        "WHERE substr(expense_date,1,4)=? GROUP BY m", (str(year),))
    rows_out_pay = fetch_all(
        "SELECT substr(payment_date,1,7) m, SUM(amount) FROM payment "
        "WHERE status='Payé' AND substr(payment_date,1,4)=? GROUP BY m", (str(year),))
    data = {f"{year}-{m:02d}": [0.0, 0.0] for m in range(1, 13)}
    for m, total in rows_in:
        if m in data: data[m][0] = total or 0.0
    for src in (rows_out_dist, rows_out_exp, rows_out_pay):
        for m, total in src:
            if m in data: data[m][1] += total or 0.0
    return [(m, v[0], v[1]) for m, v in sorted(data.items())]

def get_top_expense_categories(date_from=None, date_to=None, n=5):
    return get_expenses_breakdown_by_category(date_from, date_to)[:n]


# ── STATS DASHBOARD ───────────────────────────────────────────────────────────
def get_stats():
    total_in = fetch_one("SELECT SUM(amount) FROM donation WHERE category='Espèce'")[0] or 0.0
    total_dist = fetch_one("SELECT SUM(amount) FROM distribution")[0] or 0.0
    total_mosque = get_total_mosque_expenses()
    total_payments = get_total_payments()
    total_out = total_dist + total_mosque + total_payments
    return {
        "families":  fetch_one("SELECT COUNT(*) FROM family WHERE is_active=1")[0] or 0,
        "children":  fetch_one("SELECT COUNT(*) FROM child")[0] or 0,
        "donors":    fetch_one("SELECT COUNT(*) FROM donor WHERE is_active=1")[0] or 0,
        "donations": fetch_one("SELECT COUNT(*) FROM donation")[0] or 0,
        "donations_nature": fetch_one("SELECT COUNT(*) FROM donation WHERE category='Nature'")[0] or 0,
        "total_in":  total_in,
        "total_out": total_out,
        "total_distributions": total_dist,
        "total_mosque_expenses": total_mosque,
        "total_payments": total_payments,
        "balance":   total_in - total_out,
    }

def get_financial_summary():
    """Ne prend en compte que les dons en argent (category='Espèce') pour la caisse.
    Les dons en nature (cartables, vêtements, ...) ne modifient pas le solde monétaire.
    Les sorties incluent les distributions aux familles, les dépenses de la
    mosquée (femme de ménage, entretien, ...) ET les paiements aux bénéficiaires
    (imam, muezzin, artisans, ...)."""
    total_in  = fetch_one("SELECT SUM(amount) FROM donation WHERE category='Espèce'")[0] or 0.0
    total_out = ((fetch_one("SELECT SUM(amount) FROM distribution")[0] or 0.0)
                 + get_total_mosque_expenses() + get_total_payments())
    return total_in, total_out, total_in - total_out

def get_social_status_distribution():
    """Répartition des familles actives par situation sociale (pour le graphique en rond)."""
    return fetch_all("""SELECT COALESCE(NULLIF(social_status,''),'Non précisé'), COUNT(*)
                         FROM family WHERE is_active=1 GROUP BY 1 ORDER BY 2 DESC""")

def get_monthly_financial_summary(n_months=6):
    """Retourne [(mois 'YYYY-MM', total_entrées, total_sorties), ...] triés du plus
    ancien au plus récent, sur les n_months derniers mois où une activité existe."""
    rows_in = fetch_all("""SELECT substr(donation_date,1,7) AS m, SUM(amount)
                            FROM donation WHERE category='Espèce'
                            GROUP BY m""")
    rows_out = fetch_all("""SELECT substr(distribution_date,1,7) AS m, SUM(amount)
                             FROM distribution GROUP BY m""")
    rows_mosque = fetch_all("""SELECT substr(expense_date,1,7) AS m, SUM(amount)
                                FROM mosque_expense GROUP BY m""")
    rows_payment = fetch_all("""SELECT substr(payment_date,1,7) AS m, SUM(amount)
                                 FROM payment WHERE status='Payé' GROUP BY m""")
    data = {}
    for m, total in rows_in:
        data.setdefault(m, [0.0, 0.0])[0] = total or 0.0
    for m, total in rows_out:
        data.setdefault(m, [0.0, 0.0])[1] += total or 0.0
    for m, total in rows_mosque:
        data.setdefault(m, [0.0, 0.0])[1] += total or 0.0
    for m, total in rows_payment:
        data.setdefault(m, [0.0, 0.0])[1] += total or 0.0
    months_sorted = sorted(data.keys())[-n_months:]
    return [(m, data[m][0], data[m][1]) for m in months_sorted]

# ── PARAMÈTRES (settings clé/valeur) ──────────────────────────────────────────
def get_setting(key, default=None):
    row = fetch_one("SELECT value FROM settings WHERE key=?", (key,))
    return row[0] if row is not None else default

def set_setting(key, value):
    execute_query(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, str(value))
    )

def set_settings(mapping):
    for k, v in mapping.items():
        set_setting(k, v)

# ── SAUVEGARDE ────────────────────────────────────────────────────────────────
def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"charity_backup_{timestamp}.db"
    shutil.copy2(DB_NAME, backup_path)
    return backup_path