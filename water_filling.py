import database as db


class WaterFillingDistribution:
    """Distribution proportionnelle au score SVF, bornée par un montant
    min/max, avec une réserve d'urgence prélevée sur le budget total.

    Les valeurs par défaut (reserve, min_amt, max_amt) sont lues depuis la
    table `settings` (modifiables via la page Paramètres). Elles peuvent
    aussi être surchargées explicitement à la construction.
    """

    DEFAULTS = {
        "wf_reserve": 0.1,      # fraction du budget mise de côté (0.1 = 10%)
        "wf_min_amt": 1000,     # montant minimum par famille
        "wf_max_amt": 50000,    # montant maximum par famille
    }

    LABELS = {
        "wf_reserve": "Réserve d'urgence (fraction, ex: 0.1 = 10%)",
        "wf_min_amt": "Montant minimum par famille (DA)",
        "wf_max_amt": "Montant maximum par famille (DA)",
    }

    def __init__(self, total_budget, reserve=None, min_amt=None, max_amt=None):
        params = self.get_all_params()
        self.total_budget = total_budget
        self.reserve = reserve if reserve is not None else params["wf_reserve"]
        self.min_amt = min_amt if min_amt is not None else params["wf_min_amt"]
        self.max_amt = max_amt if max_amt is not None else params["wf_max_amt"]

        # Calculate net budget after deducting the emergency reserve
        self.net_budget = total_budget * (1 - self.reserve)

    @classmethod
    def get_all_params(cls):
        out = {}
        for k, default in cls.DEFAULTS.items():
            val = db.get_setting(k, default)
            try:
                out[k] = float(val)
            except (TypeError, ValueError):
                out[k] = default
        return out

    @classmethod
    def save_params(cls, params):
        db.set_settings({k: v for k, v in params.items() if k in cls.DEFAULTS})

    @classmethod
    def reset_defaults(cls):
        db.set_settings(cls.DEFAULTS)

    def calculate(self, families):
        # Validate input data
        if not families:
            return {'success': False, 'message': 'Aucune famille | لا توجد عائلات للقيام بالتوزيع'}

        # Prevent calculation on zero or negative budgets
        if self.total_budget <= 0:
            return {'success': False, 'message': 'Le budget doit être supérieur à 0.\nالميزانية يجب أن تكون أكبر من الصفر!'}

        # Ensure net budget covers the minimum amount for all families
        required_minimum = self.min_amt * len(families)
        if self.net_budget < required_minimum:
            return {'success': False, 'message': f'Le budget est trop faible pour le nombre de familles.\nالميزانية ضعيفة جداً! (الحد الأدنى لتوزيع المساعدات هو: {required_minimum:,.0f} دج)'}

        # Calculate the total SVF score denominator
        total_svf = sum(f.get('svf_score', 0) for f in families)

        # Prevent Division by Zero
        if total_svf == 0:
            return {'success': False, 'message': 'Somme SVF nulle | مجموع النقاط صفر'}

        distributions = []

        # Apply proportional allocation with Min/Max bounding
        for f in families:
            raw_amount = self.net_budget * (f.get('svf_score', 0) / total_svf)
            final_amount = max(self.min_amt, min(self.max_amt, raw_amount))

            distributions.append({
                'family_id': f['id'],
                'head_name': f['head_name'],
                'svf_score': f.get('svf_score', 0),
                'amount': round(final_amount, 2)
            })

        return {
            'success': True,
            'total_budget': self.total_budget,
            'net_budget': self.net_budget,
            'distributions': distributions
        }
