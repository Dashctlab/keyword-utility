import io
import pandas as pd

def read_input_file(filename: str, content: bytes) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(content))
    raise ValueError("Unsupported file type. Upload .csv or .xlsx")

def find_keyword_column(df: pd.DataFrame) -> str:
    # common column names
    candidates = ["keyword", "keywords", "query", "search term", "term"]
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    # fallback: if only one string column, use it
    str_cols = [c for c in df.columns if df[c].dtype == "object"]
    if len(str_cols) == 1:
        return str_cols[0]
    raise ValueError("Could not find keyword column. Please name it 'keyword' or 'query'.")
