# main.py
# Full FastAPI app implementing your emotion analysis API contract.
# Endpoints:
#   POST /analyze        -> returns JSON response (your contract)
#   POST /analyze/save   -> returns same JSON + saves it to ./out/<uuid>.json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List
import os, uuid, json, re, math

from transformers import pipeline
import torch

# ---------------------------
# API models (contract)
# ---------------------------
class AnalyzeIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)

class AnalyzeOut(BaseModel):
    emotion: str
    confidence: float
    scores: Dict[str, float]
    top_words: List[str]
    affirmation: str

# ---------------------------
# Config
# ---------------------------
# Canonical labels exposed by your API:
CANON_LABELS = ["joy", "sad", "anxiety", "anger", "neutral"]

# Map model labels -> your canonical labels.
# Using a solid public model: j-hartmann/emotion-english-distilroberta-base
# Model labels: anger, disgust, fear, joy, neutral, sadness, surprise
MODEL_TO_CANON = {
    "anger": "anger",
    "disgust": "neutral",   # map to neutral (or anger; adjust if you prefer)
    "fear": "anxiety",
    "joy": "joy",
    "neutral": "neutral",
    "sadness": "sad",
    "surprise": "neutral",  # map to neutral (or joy; adjust if you prefer)
}

AFFIRMATIONS = {
    "joy":      "Savor this feeling—you’ve earned it.",
    "sad":      "It’s okay to feel low; you won’t feel this way forever.",
    "anxiety":  "You’ve handled hard things before—this is another step.",
    "anger":    "Take a breath; your calm gives you control.",
    "neutral":  "You’re steady and present—nice foundation to build on.",
}

# Optionally override via env var
MODEL_ID = os.getenv("HF_MODEL_ID", "j-hartmann/emotion-english-distilroberta-base")

# ---------------------------
# App
# ---------------------------
app = FastAPI(title="Emotion Analysis API", version="1.0.0")

# Load the classifier once at startup
clf = pipeline(
    task="text-classification",
    model=MODEL_ID,
    tokenizer=MODEL_ID,
    return_all_scores=True,
    device_map="auto" if torch.cuda.is_available() else None,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else None,
)

# ---------------------------
# Utilities
# ---------------------------
STOP = set("""
a an the and or but if then else when while for to of in on at by with from up down out over under again further
this that these those is are was were be been being have has had do does did not no nor very can will just
i you he she it we they me him her us them my your his her its our their myself yourself himself herself itself
ourselves yourselves themselves as into about like so than too such only own same
""".split())

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")

def extract_top_words(text: str, k: int = 3) -> List[str]:
    counts: Dict[str, int] = {}
    for w in WORD_RE.findall(text.lower()):
        if w in STOP:
            continue
        counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0])))][:k]

def map_to_canonical(all_scores: List[Dict[str, float]]) -> Dict[str, float]:
    agg: Dict[str, float] = {lab: 0.0 for lab in CANON_LABELS}
    # HF returns e.g. [{"label":"joy","score":0.78}, ...]
    for item in all_scores:
        label = item["label"].lower()
        score = float(item["score"])
        if label in MODEL_TO_CANON:
            agg[MODEL_TO_CANON[label]] += score
        else:
            # Unknown labels -> neutral (adjust if desired)
            agg["neutral"] += score
    total = sum(agg.values()) or 1.0
    for k in agg:
        agg[k] = round(agg[k] / total, 4)
    return agg

def build_response_for_text(text: str) -> AnalyzeOut:
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must be non-empty.")

    raw = clf(text)  # may return [[...]] for batch, or [...] for single
    all_scores = raw[0] if (isinstance(raw, list) and raw and isinstance(raw[0], list)) else raw
    scores = map_to_canonical(all_scores)
    emotion = max(scores.items(), key=lambda kv: kv[1])[0]
    confidence = float(scores[emotion])
    top_words = extract_top_words(text, k=3)
    affirmation = AFFIRMATIONS.get(emotion, "You’re doing your best—keep going.")

    return AnalyzeOut(
        emotion=emotion,
        confidence=confidence,
        scores=scores,
        top_words=top_words,
        affirmation=affirmation,
    )

# ---------------------------
# Routes
# ---------------------------
@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs", "endpoints": ["/analyze", "/analyze/save"]}

@app.post("/analyze", response_model=AnalyzeOut)
def analyze(inp: AnalyzeIn):
    return build_response_for_text(inp.text)

@app.post("/analyze/save")
def analyze_and_save(inp: AnalyzeIn):
    res = build_response_for_text(inp.text)
    os.makedirs("out", exist_ok=True)
    fname = f"out/{uuid.uuid4().hex}.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(res.model_dump(), f, ensure_ascii=False, indent=2)
    return {"path": fname, "result": res}
