"""Export query builder for the "Containers actifs" XLSX/CSV.

The 49-column export schema is the hard integration contract with the
operator's Power BI report. Column order matters and is set by `EXPORT_COLUMNS`.
Operators can pick a subset on the export page; we still use this canonical
order so downstream pivots keep working.

Public API:
    EXPORT_COLUMNS    : list[(alias, label)]   ordered, canonical
    SHIPMENT_FIELDS   : set[str]               aliases that live on shipments
    select_clause(picked) -> (sql, [(alias, label), ...])
    run_query(db_path, picked, filters) -> (labels, rows)
"""
from __future__ import annotations

from core.storage.db import get_connection


# Column registry — (sql_alias, display_label). Order is the export order.
EXPORT_COLUMNS: list[tuple[str, str]] = [
    ("container_number",     "N° Container"),
    ("tan",                  "N° TAN"),
    ("item_description",     "Item"),
    ("compagnie_maritime",   "Compagnie maritime"),
    ("port",                 "Port"),
    ("transitaire",          "Transitaire"),
    ("vessel",               "Navire"),
    ("etd",                  "Date shipment"),
    ("eta",                  "Date accostage"),
    ("status",               "Statut Expédition"),
    ("document_type",        "Type document"),
    ("statut_container",     "Statut Container"),
    ("size",                 "Container size"),
    ("seal_number",          "N° Seal"),
    ("date_livraison",       "Date livraison"),
    ("site_livraison",       "Site livraison"),
    ("livre_camion",         "Livré par (Camion)"),
    ("livre_chauffeur",      "Livré par (Chauffeur)"),
    ("date_depotement",      "Date dépotement"),
    ("date_debut_surestarie","Date début Surestarie"),
    ("date_restitution_estimative","Date restitution estimative"),
    ("nbr_jours_surestarie_estimes","Nbr jours surestarie estimés"),
    ("nbr_jours_perdu_douane","Nbr jours perdu en douane"),
    ("date_restitution",     "Date réstitution"),
    ("restitue_camion",      "Réstitué par (Camion)"),
    ("restitue_chauffeur",   "Réstitué par (Chauffeur)"),
    ("centre_restitution",   "Centre de réstitution"),
    ("montant_facture_check","Montant facturé (check)"),
    ("nbr_jour_surestarie_facture","Nbr jour surestarie Facturé"),
    ("montant_facture_da",   "Montant facturé (DA)"),
    ("taux_de_change",       "Taux de change"),
    ("n_facture_cm",         "N° Facture compagnie maritime"),
    ("commentaire",          "Commentaire"),
    ("date_declaration_douane","Date declaration douane"),
    ("date_liberation_douane","Date liberation douane"),
    ("source_file",          "Source"),
    ("created_at",           "Créé le"),
    ("modified_at",          "Modifié le"),
]

# Which aliases live on the `shipments` table (everything else is on `containers`).
# Used to pick the right table prefix when building the SELECT clause.
SHIPMENT_FIELDS: set[str] = {
    "tan", "item_description", "compagnie_maritime", "port", "transitaire",
    "vessel", "etd", "eta", "status", "document_type", "source_file",
}


def select_clause(picked: set[str]) -> tuple[str, list[tuple[str, str]]]:
    """Build the SELECT projection.

    Returns (sql_fragment, [(alias, label), ...]) — the second element is the
    column list in canonical order, filtered to what the operator picked.
    Empty `picked` falls back to the full schema.
    """
    chosen = [(a, lbl) for (a, lbl) in EXPORT_COLUMNS if a in picked]
    if not chosen:
        chosen = list(EXPORT_COLUMNS)
    parts = [
        f'{"s" if alias in SHIPMENT_FIELDS else "c"}.{alias} AS "{label}"'
        for alias, label in chosen
    ]
    return ",\n            ".join(parts), chosen


def run_query(db_path: str, picked: set[str], filters: dict):
    """Execute the export SELECT against `db_path` and return (labels, rows).

    Filters supported:
        status   -> containers.statut_container exact match
        carrier  -> shipments.compagnie_maritime exact match
        tan      -> shipments.tan LIKE %value% (substring match)
    """
    select_sql, chosen = select_clause(picked)
    where_clauses: list[str] = []
    params: list = []
    if filters.get("status"):
        where_clauses.append("c.statut_container = ?")
        params.append(filters["status"])
    if filters.get("carrier"):
        where_clauses.append("s.compagnie_maritime = ?")
        params.append(filters["carrier"])
    if filters.get("tan"):
        where_clauses.append("s.tan LIKE ?")
        params.append(f"%{filters['tan']}%")
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"""SELECT {select_sql}
                FROM containers c JOIN shipments s ON s.id = c.shipment_id
                {where_sql}
                ORDER BY c.id DESC""",
            params,
        ).fetchall()
        labels = [lbl for (_, lbl) in chosen]
        return labels, rows
    finally:
        conn.close()
