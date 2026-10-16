import database as db


class SVFCalculator:
    """Calcule le Score de Vulnérabilité Familiale (SVF).

    Tous les poids/seuils sont configurables depuis la page Paramètres
    (stockés dans la table `settings`). Les valeurs ci-dessous ne sont
    utilisées que si aucun réglage personnalisé n'a été enregistré.
    """

    DEFAULTS = {
        "svf_smig": 20000,
        "svf_pts_income_t1": 40,   # revenu < SMIG
        "svf_pts_income_t2": 25,   # revenu < 2×SMIG
        "svf_pts_income_t3": 10,   # revenu < 3×SMIG
        "svf_pts_per_child": 5,
        "svf_max_children_pts": 20,
        "svf_pts_social_widow_divorced": 15,
        "svf_pts_social_no_support": 20,
        "svf_pts_health_disability": 15,
        "svf_pts_health_chronic": 10,
        "svf_pts_renting": 10,
        "svf_malus_per_benefit": 8,
        "svf_max_malus": 25,
        "svf_age_senior_threshold": 65,
        "svf_pts_age_senior": 10,
        "svf_age_young_threshold": 25,
        "svf_pts_age_young": 5,
    }

    LABELS = {
        "svf_smig": "Seuil SMIG (DA)",
        "svf_pts_income_t1": "Points si revenu < SMIG",
        "svf_pts_income_t2": "Points si revenu < 2×SMIG",
        "svf_pts_income_t3": "Points si revenu < 3×SMIG",
        "svf_pts_per_child": "Points par enfant à charge",
        "svf_max_children_pts": "Plafond des points 'enfants'",
        "svf_pts_social_widow_divorced": "Points si Veuve(f) / Divorcée",
        "svf_pts_social_no_support": "Points si Sans soutien",
        "svf_pts_health_disability": "Points si Handicap",
        "svf_pts_health_chronic": "Points si Maladie chronique",
        "svf_pts_renting": "Points si Locataire",
        "svf_malus_per_benefit": "Malus par aide déjà reçue",
        "svf_max_malus": "Plafond du malus",
        "svf_age_senior_threshold": "Âge seuil senior",
        "svf_pts_age_senior": "Points si chef senior",
        "svf_age_young_threshold": "Âge seuil jeune chef",
        "svf_pts_age_young": "Points si jeune chef de famille",
    }

    @classmethod
    def get_param(cls, key):
        val = db.get_setting(key, cls.DEFAULTS[key])
        try:
            f = float(val)
            return int(f) if f.is_integer() else f
        except (TypeError, ValueError):
            return cls.DEFAULTS[key]

    @classmethod
    def get_all_params(cls):
        return {k: cls.get_param(k) for k in cls.DEFAULTS}

    @classmethod
    def save_params(cls, params):
        db.set_settings({k: v for k, v in params.items() if k in cls.DEFAULTS})

    @classmethod
    def reset_defaults(cls):
        db.set_settings(cls.DEFAULTS)

    @classmethod
    def compute_household_income(cls, family_row, children):
        """Revenu total du foyer pris en compte pour le score SVF :
        revenu du chef de famille + revenu de chaque fils/fille qui TRAVAILLE
        ET est CÉLIBATAIRE (ou divorcé/veuf).
        Un fils/fille MARIÉ(E) est considéré comme ayant fondé son propre
        foyer financier : son revenu n'est PAS ajouté à celui de la famille,
        même s'il travaille.
        """
        income = family_row[6] or 0  # [6] = monthly_income du chef de famille
        for c in children:
            # c: [9]is_working [11]monthly_revenue [12]marital_status
            is_working = len(c) > 9 and c[9]
            if not is_working:
                continue
            marital = c[12] if len(c) > 12 and c[12] else ""
            if str(marital).startswith("Marié"):
                continue  # marié(e) -> foyer séparé, revenu non comptabilisé
            revenue = c[11] if len(c) > 11 and c[11] else 0
            income += revenue
        return income

    @classmethod
    def recalculate_and_save(cls, family_id):
        """Recalcule le score SVF d'une famille déjà enregistrée (en tenant
        compte du revenu des fils/filles célibataires qui travaillent) et
        enregistre immédiatement le résultat en base. À appeler chaque fois
        que la famille OU l'un de ses enfants est ajouté/modifié/supprimé."""
        family_row = db.fetch_one("SELECT * FROM family WHERE id=?", (family_id,))
        if not family_row:
            return None
        children = db.get_children_by_family(family_id)
        total_income = cls.compute_household_income(family_row, children)
        score = cls.calculate({
            'monthly_income': total_income,
            'children_count': len(children),
            'social_status': family_row[12],
            'health_status': family_row[13],
            'is_renting': 1 if db.family_is_renting(family_row[15]) else 0,
            'benefit_count': 0,
            'age': family_row[22] if len(family_row) > 22 else 0,
        })
        db.execute_query("UPDATE family SET svf_score=? WHERE id=?", (score, family_id))
        return score

    @classmethod
    def calculate(cls, family_data):
        p = cls.get_all_params()
        score = 0
        income = family_data.get('monthly_income', 0)
        age = family_data.get('age', 0)
        social = family_data.get('social_status', "Aucun")
        health = family_data.get('health_status', "Bonne")
        is_renting = family_data.get('is_renting', 0)
        children = family_data.get('children_count', 0)
        benefits = family_data.get('benefit_count', 0)
        smig = p['svf_smig']

        # 1. Revenu mensuel
        if income < smig: score += p['svf_pts_income_t1']
        elif income < 2 * smig: score += p['svf_pts_income_t2']
        elif income < 3 * smig: score += p['svf_pts_income_t3']

        # 2. Enfants à charge / Orphelins
        score += min(children * p['svf_pts_per_child'], p['svf_max_children_pts'])

        # 3. Situation Sociale
        if social in ["Veuve | أرملة", "Divorcée | مطلقة"]:
            score += p['svf_pts_social_widow_divorced']
        elif social == "Sans soutien | بدون معيل":
            score += p['svf_pts_social_no_support']

        # 4. État de Santé
        if health == "Handicap | إعاقة":
            score += p['svf_pts_health_disability']
        elif health == "Maladie chronique | مرض مزمن":
            score += p['svf_pts_health_chronic']

        # 5. Logement Location
        if is_renting == 1:
            score += p['svf_pts_renting']

        # 6. Historique d'aide récente (Malus d'équité)
        score -= min(benefits * p['svf_malus_per_benefit'], p['svf_max_malus'])

        # 7. Âge du chef de famille (Bénéficiaire)
        if age >= p['svf_age_senior_threshold']:
            score += p['svf_pts_age_senior']
        elif 0 < age < p['svf_age_young_threshold']:
            score += p['svf_pts_age_young']

        return round(min(max(score, 0), 100), 2)
