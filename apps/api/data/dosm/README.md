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
| `source_title` | Human-readable title (falls back to `dataset`) |

## Example CSV

```csv
content,dataset,year,ministry,url
"Malaysia's population reached 32.7 million in 2022.",Population Estimates,2022,DOSM,https://www.dosm.gov.my/v2/
"The labour force participation rate was 69.2% in Q3 2023.",Labour Force Survey,2023,DOSM,https://www.dosm.gov.my/v2/
```

## Data sources

Download open data from:
- https://data.gov.my — Malaysia's official open data portal
- https://www.dosm.gov.my — DOSM publications and census data

## Ingestion

After placing CSVs here, run:

```bash
cd apps/api

# Ingest all CSVs in data/dosm/
python -m scripts.ingest --dir data/dosm/

# Ingest a single file
python -m scripts.ingest --file data/dosm/population.csv

# Dry-run: embed but don't write to Supabase
python -m scripts.ingest --dir data/dosm/ --dry-run

# Custom batch size (default 100)
python -m scripts.ingest --dir data/dosm/ --batch-size 50
```
