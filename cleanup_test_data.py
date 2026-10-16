# -*- coding: utf-8 -*-
"""
cleanup_test_data.py
----------------------
Supprime TOUTES les données de démonstration/test générées par
generate_bulk_test_data.py (tout ce qui commence par "TEST - " dans les
familles et les donateurs), ainsi que leurs enfants/dons/distributions liés.

Les données réelles (qui ne commencent pas par "TEST - ") ne sont jamais
touchées.

Utilisation :
    python cleanup_test_data.py
"""

import database as db


def cleanup():
    families = db.fetch_all("SELECT id FROM family WHERE head_name LIKE 'TEST - %'")
    donors = db.fetch_all("SELECT id FROM donor WHERE name LIKE 'TEST - %'")

    n_fam = len(families)
    n_donors = len(donors)
    n_children = 0
    n_donations = 0
    n_distributions = 0

    for (fid,) in families:
        n_children += db.fetch_one("SELECT COUNT(*) FROM child WHERE family_id=?", (fid,))[0]
        n_distributions += db.fetch_one(
            "SELECT COUNT(*) FROM distribution WHERE family_id=?", (fid,))[0]
        db.execute_query("DELETE FROM child WHERE family_id=?", (fid,))
        db.execute_query("DELETE FROM distribution WHERE family_id=?", (fid,))
        db.execute_query("DELETE FROM family WHERE id=?", (fid,))

    for (did,) in donors:
        n_donations += db.fetch_one("SELECT COUNT(*) FROM donation WHERE donor_id=?", (did,))[0]
        db.execute_query("DELETE FROM donation WHERE donor_id=?", (did,))
        db.execute_query("DELETE FROM donor WHERE id=?", (did,))

    # Permet de régénérer des données de démo plus tard si souhaité.
    db.set_setting("demo_data_seeded", "0")

    print("✅ Nettoyage terminé :")
    print(f"   - {n_fam} familles supprimées ({n_children} enfants)")
    print(f"   - {n_donors} donateurs supprimés ({n_donations} dons)")
    print(f"   - {n_distributions} distributions supprimées")

    return {
        "families": n_fam, "children": n_children, "donors": n_donors,
        "donations": n_donations, "distributions": n_distributions,
    }


if __name__ == "__main__":
    db.initialize_database()
    cleanup()