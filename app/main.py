import io
import yaml
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.io_utils import read_input_file, find_keyword_column
from app.rules import classify_keyword
from app.gpt_fallback import gpt_classify_batch

app = FastAPI(title="Keyword Categorizer")

def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

TAX = load_yaml("config/taxonomy.yaml")
LISTS = load_yaml("config/lists.yaml")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/classify")
async def classify(file: UploadFile = File(...), gpt_fallback: bool = True, gpt_batch_size: int = 80):
    content = await file.read()
    try:
        df = read_input_file(file.filename, content)
        kw_col = find_keyword_column(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    df = df.copy()
    df["keyword"] = df[kw_col].astype(str)

    # Rule pass
    results = df["keyword"].apply(lambda k: classify_keyword(k, LISTS))
    df["Primary Bucket ID"] = results.apply(lambda r: r.bucket_id)
    df["Intent (model)"] = results.apply(lambda r: r.intent)
    df["Stage (model)"] = results.apply(lambda r: r.stage)
    df["Paid Activation (suggested)"] = results.apply(lambda r: r.paid_activation)
    df["SEO Asset (suggested)"] = results.apply(lambda r: r.seo_asset)
    df["Is Negative (Y/N)"] = results.apply(lambda r: r.is_negative)
    df["Negative Type"] = results.apply(lambda r: r.negative_type)
    df["Negative Theme"] = results.apply(lambda r: r.negative_theme)
    df["Confidence"] = results.apply(lambda r: r.confidence)
    df["Notes"] = results.apply(lambda r: r.notes)

    # GPT fallback for low confidence / unclassified
    if gpt_fallback:
        mask = (df["Primary Bucket ID"] == "UNCLASSIFIED") | (df["Confidence"] < 0.5)
        todo = df.loc[mask, "keyword"].tolist()

        if todo:
            items_all = []
            for i in range(0, len(todo), gpt_batch_size):
                batch = todo[i:i+gpt_batch_size]
                items = gpt_classify_batch(
                    batch,
                    allowed_buckets=TAX["buckets"],
                    allowed_intents=TAX["intents"],
                    allowed_stages=TAX["stages"]
                )
                items_all.extend(items)

            # write back
            map_items = {it["keyword"]: it for it in items_all}
            for idx in df.index[mask]:
                kw = df.at[idx, "keyword"]
                it = map_items.get(kw)
                if not it:
                    continue
                df.at[idx, "Primary Bucket ID"] = it["bucket_id"]
                df.at[idx, "Intent (model)"] = it["intent"]
                df.at[idx, "Stage (model)"] = it["stage"]
                df.at[idx, "Is Negative (Y/N)"] = it["is_negative"]
                df.at[idx, "Negative Type"] = it["negative_type"]
                df.at[idx, "Negative Theme"] = it["negative_theme"]
                df.at[idx, "Notes"] = (df.at[idx, "Notes"] + "; " if df.at[idx, "Notes"] else "") + it["notes"]
                df.at[idx, "Confidence"] = max(df.at[idx, "Confidence"], 0.6)  # conservative bump

    # Output XLSX
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.drop(columns=["keyword"]).to_excel(writer, index=False, sheet_name="Categorized")
        df["Primary Bucket ID"].value_counts().rename_axis("Bucket").reset_index(name="Keywords").to_excel(writer, index=False, sheet_name="Summary_Bucket")
        df["Intent (model)"].value_counts().rename_axis("Intent").reset_index(name="Keywords").to_excel(writer, index=False, sheet_name="Summary_Intent")
    out.seek(0)

    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="categorized_output.xlsx"'}
    )
