# DOSM Data Directory

Place DOSM (Department of Statistics Malaysia) CSV files here for ingestion into the RAG pipeline.

## Expected CSV format

Each CSV should contain at minimum these columns:

| Column | Description |
|--------|-------------|
| `content` | The text content to be embedded and retrieved |
| `dataset` | Dataset name (e.g., "Population by State 2020") |
| `year` | Publication year |
| `ministry` | Producing ministry (default: "DOSM") |
| `url` | Source URL on data.gov.my or dosm.gov.my |

## Data sources

Download open data from:
- https://data.gov.my — Malaysia's official open data portal
- https://www.dosm.gov.my — DOSM publications and census data

## Ingestion

After placing CSVs here, run the ingestion script (to be added):

```bash
cd apps/api
python -m scripts.ingest --dir data/dosm/
```
