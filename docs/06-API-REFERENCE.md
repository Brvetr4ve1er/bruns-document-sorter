# 06 — API Reference

The Flask BI bridge in `core/api/server.py` exposes the SQLite databases as
paginated REST endpoints. Power BI, Tableau, Looker, Excel "Get Data > Web",
or any HTTP client can consume them.

## Server basics

| | |
|---|---|
| Default host | `0.0.0.0` (binds all interfaces — change to `127.0.0.1` for laptop-only) |
| Default port | `7845` |
| Override | `BRUNS_API_PORT=NNNN python -m core.api.server` |
| Data dir | `data/` (override with `BRUNS_DATA_DIR`) |
| CORS | Enabled on `/api/*`, origin `*` |
| Encoding | UTF-8 native (`JSON_AS_ASCII = False` — French chars survive) |
| Pagination cap | `page_size` is hard-capped to 200 to prevent BI tools dumping the whole DB |

Start it:

```bash
python -m core.api.server
```

Or via `START_BI_CONNECTOR.bat` on Windows.

## Common query parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int ≥ 1 | 1 | Page number |
| `page_size` | int 1–200 | 50 | Rows per page |

All endpoints return:

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 1234,
    "total_pages": 25,
    "has_next": true,
    "has_prev": false
  }
}
```

---

## System endpoints

### `GET /api/status`

Health check. Returns whether each domain database file exists.

**Response:**
```json
{
  "status": "online",
  "databases": {
    "logistics": "ok",
    "travel": "ok"
  }
}
```

Use this in BI tools as the connection-test endpoint.

---

## Logistics endpoints

### `GET /api/logistics/shipments`

Shipment-level rows. Best for BI dashboards that count shipments per carrier
or status.

**Filters:**
- `status` — exact match on `BOOKED`, `IN_TRANSIT`, etc.

**Example:**
```
GET /api/logistics/shipments?status=IN_TRANSIT&page=1&page_size=100
```

**Response (truncated):**
```json
{
  "data": [
    {
      "id": 234,
      "tan_number": "TAN/1234/2026",
      "vessel_name": "MSC LAUREN",
      "shipping_company": "MSC",
      "etd": "2026-03-11",
      "eta": "2026-03-25",
      "status": "IN_TRANSIT",
      "document_type": "DEPARTURE",
      "transitaire": "CEVA",
      "port": "Port d'Alger",
      ...
    }
  ],
  "pagination": {...}
}
```

### `GET /api/logistics/containers`

Container-level rows.

**Filters:**
- `status` — exact match on `containers.statut_container`
  (`Réservé`, `En transit`, `Arrivé`, `Livré`, `Dépoté`, `Restitué`)

**Example:**
```
GET /api/logistics/containers?status=En%20transit
```

### `GET /api/logistics/shipments_full` ⭐ Primary BI endpoint

Flat denormalized view. **One row per container**, all 49+ columns from the
"Containers actifs" Excel format. Use this for Power BI — no joins required
on the BI side.

**Filters:**
- `status` — `shipments.status`
- `carrier` — `shipments.shipping_company`
- `tan` — substring match on `shipments.tan` (LIKE `%tan%`)

**Example:**
```
GET /api/logistics/shipments_full?carrier=MSC&status=IN_TRANSIT
```

**Response sample fields** (all column names match the customer's Excel):
```json
{
  "data": [
    {
      "shipment_id": 234,
      "container_id": 891,
      "N° Container": "MSCU1234567",
      "N° TAN": "TAN/1234/2026",
      "Item": "Cargo description...",
      "Compagnie maritime": "MSC",
      "Port": "Port d'Alger",
      "Transitaire": "CEVA",
      "Navire": "MSC LAUREN",
      "Date shipment": "2026-03-11",
      "Date accostage": "2026-03-25",
      "Statut Expédition": "IN_TRANSIT",
      "Type document": "DEPARTURE",
      "Statut Container": "En transit",
      "Container size": "40 feet",
      "N° Seal": "SEAL12345",
      "Date livraison": null,
      "Site livraison": null,
      "Date dépotement": null,
      "Date début Surestarie": null,
      "Date restitution estimative": null,
      "Nbr jours surestarie estimés": 0,
      "Nbr jours perdu en douane": 0,
      "Date restitution estimative": null,
      "Date réstitution": null,
      "Réstitué par (Camion)": null,
      "Réstitué par (Chauffeur)": null,
      "Centre de réstitution": null,
      "Livré par (Camion)": null,
      "Livré par (Chauffeur)": null,
      "Montant facturé (check)": "No",
      "Nbr jour surestarie Facturé": 0,
      "Montant facturé (DA)": 0,
      "Taux de change": 0,
      "N° Facture compagnie maritime": null,
      "Commentaire": null,
      "Date declaration douane": null,
      "Date liberation douane": null,
      "Source": "booking_2026_03_11.pdf",
      "Créé le": "2026-03-12T10:23:45",
      "Modifié le": "2026-03-12T10:23:45"
    }
  ],
  "pagination": {...}
}
```

---

## Travel endpoints

### `GET /api/travel/persons`

**Filters:**
- `nationality` — exact match (3-letter ISO preferred)

**Example:**
```
GET /api/travel/persons?nationality=DZA
```

### `GET /api/travel/families`

No filters yet (will add `case_reference` lookup in P3).

### `GET /api/travel/documents`

**Filters:**
- `doc_type` — exact match on `PASSPORT`, `ID_CARD`, etc.

---

## Power BI connection recipe

1. Open Power BI Desktop → **Get Data > Web**.
2. URL: `http://localhost:7845/api/logistics/shipments_full?page_size=200`
3. Authentication: **Anonymous**.
4. In Power Query: expand the `data` column, then expand the records.
5. Set up incremental refresh: parameterize `page` and use Power BI's
   pagination handling.

For a one-shot full dump, page through with `?page=1`, `?page=2`, … until
`pagination.has_next == false`.

For very large datasets (>10k rows): use the Excel export instead — the BI
endpoint is designed for live freshness, not bulk extract. (Future:
`/api/logistics/shipments_full.parquet` — see roadmap.)

---

## Authentication and security

**Currently:** None. The server binds to `0.0.0.0`, so anyone on the same
LAN can hit it.

**Acceptable because:** The intended deployment is a single laptop, used by a
single operator, on a private LAN. The Power BI client is on the same machine
or LAN.

**To restrict to local only**, edit the last line of `core/api/server.py`:
```python
app.run(host="127.0.0.1", port=port, debug=False)
```

**For multi-tenant production deployments** — out of scope today. See
[09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md) for the auth roadmap.

---

## Future endpoints (not yet implemented)

These appear in [09-ROADMAP-IMPROVEMENTS.md](09-ROADMAP-IMPROVEMENTS.md):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/logistics/shipments_full.parquet` | Bulk export in Apache Parquet format (10× faster ingest in Power BI / Tableau) |
| `GET /api/logistics/shipments_full.jsonl` | JSONL stream for data lakes |
| `GET /api/logistics/odata/$metadata` | OData v4 service document for Excel/Power BI native OData connector |
| `GET /api/logistics/risk/demurrage` | Predicted demurrage exposure per active container |
| `POST /api/logistics/upload` | Upload a PDF for processing via the Flask UI (P2) |
| `GET /api/logistics/jobs/<job_id>` | HTMX polling endpoint for processing status (P2) |
