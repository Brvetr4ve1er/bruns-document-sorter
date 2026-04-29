from typing import List, Optional
from pydantic import BaseModel, field_validator
from .base import AuditMixin
from ..normalization.codes import (
    container_number, normalize_size, normalize_seal, 
    shipping_co, normalize_tan, clean_str
)
from ..normalization.dates import date_normalize

class Container(AuditMixin):
    id: Optional[int] = None
    shipment_id: Optional[int] = None
    container_number: str
    size: str = "40 feet"
    seal_number: Optional[str] = None
    statut_container: Optional[str] = None
    
    # Operational fields
    date_livraison: Optional[str] = None
    site_livraison: Optional[str] = None
    date_depotement: Optional[str] = None
    date_debut_surestarie: Optional[str] = None
    date_restitution_estimative: Optional[str] = None
    nbr_jours_surestarie_estimes: int = 0
    nbr_jours_perdu_douane: int = 0
    date_restitution: Optional[str] = None
    restitue_camion: Optional[str] = None
    restitue_chauffeur: Optional[str] = None
    centre_restitution: Optional[str] = None
    livre_camion: Optional[str] = None
    livre_chauffeur: Optional[str] = None
    montant_facture_check: str = 'No'
    nbr_jour_surestarie_facture: int = 0
    montant_facture_da: float = 0.0
    n_facture_cm: Optional[str] = None
    commentaire: Optional[str] = None
    date_declaration_douane: Optional[str] = None
    date_liberation_douane: Optional[str] = None
    taux_de_change: float = 0.0

    @field_validator("container_number", mode="before")
    @classmethod
    def norm_cnum(cls, v):
        return container_number(v)

    @field_validator("size", mode="before")
    @classmethod
    def norm_size(cls, v):
        return normalize_size(v)

    @field_validator("seal_number", mode="before")
    @classmethod
    def norm_seal(cls, v):
        return normalize_seal(v)

class Shipment(AuditMixin):
    id: Optional[int] = None
    document_id: Optional[int] = None
    document_type: str = "UNKNOWN"
    tan_number: Optional[str] = None
    item_description: Optional[str] = None
    shipping_company: Optional[str] = None
    port: Optional[str] = "Port d'Alger"
    transitaire: Optional[str] = None
    vessel_name: Optional[str] = None
    etd: Optional[str] = None
    eta: Optional[str] = None
    status: str = "UNKNOWN"
    source_file: Optional[str] = None
    containers: List[Container] = []

    @field_validator("vessel_name", mode="before")
    @classmethod
    def upper_vessel(cls, v):
        return str(v).strip().upper() if v else None

    @field_validator("shipping_company", mode="before")
    @classmethod
    def norm_company(cls, v):
        return shipping_co(v)

    @field_validator("tan_number", mode="before")
    @classmethod
    def norm_tan(cls, v):
        return normalize_tan(v)

    @field_validator("etd", "eta", mode="before")
    @classmethod
    def norm_date(cls, v):
        return date_normalize(v)

    @field_validator("item_description", "transitaire", "port", mode="before")
    @classmethod
    def clean(cls, v):
        return clean_str(v)
