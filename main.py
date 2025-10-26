# main.py
# Full FastAPI app implementing your emotion analysis API contract.
# Endpoints:
#   POST /analyze        -> returns JSON response (your contract)
#   POST /analyze/save   -> returns same JSON + saves it to ./out/<uuid>.json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List
from fastapi.middleware.cors import CORSMiddleware
import os, uuid, json, re, random

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


MODEL_TO_CANON = {
    # 💛 JOY / HAPPINESS
    "joy": "joy", "joyful": "joy", "happy": "joy", "happiness": "joy",
    "cheerful": "joy", "content": "joy", "contentment": "joy",
    "pleased": "joy", "satisfied": "joy", "delighted": "joy",
    "ecstatic": "joy", "elated": "joy", "enthusiastic": "joy",
    "excited": "joy", "grateful": "joy", "hopeful": "joy",
    "optimistic": "joy", "loving": "joy", "affectionate": "joy",
    "inspired": "joy", "proud": "joy", "playful": "joy", "peaceful": "joy",
    "amused": "joy", "blissful": "joy", "radiant": "joy",
    "thrilled": "joy", "joyous": "joy", "thankful": "joy",
    "curious": "joy", "serene": "joy", "wonder": "joy",

    # 💙 SADNESS / GRIEF
    "sad": "sad", "sadness": "sad", "unhappy": "sad", "heartbroken": "sad",
    "disappointed": "sad", "hurt": "sad", "lonely": "sad",
    "grief": "sad", "grieving": "sad", "gloomy": "sad", "hopeless": "sad",
    "miserable": "sad", "depressed": "sad", "downcast": "sad",
    "sorrow": "sad", "melancholy": "sad", "regretful": "sad",
    "guilt": "sad", "ashamed": "sad", "shame": "sad",
    "tired": "sad", "drained": "sad", "lost": "sad",
    "disheartened": "sad", "forlorn": "sad", "discouraged": "sad",
    "mourning": "sad", "blue": "sad", "heavy": "sad",

    # ❤️ ANGER / FRUSTRATION
    "anger": "anger", "angry": "anger", "furious": "anger",
    "annoyed": "anger", "irritated": "anger", "resentful": "anger",
    "frustrated": "anger", "rage": "anger", "bitter": "anger",
    "jealous": "anger", "envious": "anger", "offended": "anger",
    "disgusted": "anger", "hostile": "anger", "indignant": "anger",
    "vengeful": "anger", "agitated": "anger", "mad": "anger",
    "impatient": "anger", "hateful": "anger", "infuriated": "anger",
    "provoked": "anger", "irate": "anger", "irritation": "anger",

    # 💜 ANXIETY / FEAR
    "anxiety": "anxiety", "anxious": "anxiety", "worried": "anxiety",
    "fear": "anxiety", "fearful": "anxiety", "afraid": "anxiety",
    "terrified": "anxiety", "nervous": "anxiety", "uneasy": "anxiety",
    "tense": "anxiety", "stressed": "anxiety", "panicked": "anxiety",
    "insecure": "anxiety", "confused": "anxiety", "uncertain": "anxiety",
    "doubtful": "anxiety", "overwhelmed": "anxiety", "startled": "anxiety",
    "alarmed": "anxiety", "shaken": "anxiety", "worried": "anxiety",
    "apprehensive": "anxiety", "concerned": "anxiety", "distrustful": "anxiety",

    # 🩶 NEUTRAL / CALM / MIXED
    "neutral": "neutral", "calm": "neutral", "relaxed": "neutral",
    "peaceful": "neutral", "balanced": "neutral", "okay": "neutral",
    "fine": "neutral", "indifferent": "neutral", "apathetic": "neutral",
    "blank": "neutral", "bored": "neutral", "composed": "neutral",
    "collected": "neutral", "stable": "neutral", "rested": "neutral",
    "serene": "neutral", "quiet": "neutral", "still": "neutral",
    "nonchalant": "neutral", "content": "joy",  # optional crossmap
    "curious": "neutral", "pensive": "neutral", "accepting": "neutral",

    # 🧡 SURPRISE / MIXED STATES
    "surprised": "neutral", "shocked": "neutral", "amazed": "neutral",
    "astonished": "neutral", "startled": "anxiety", "perplexed": "anxiety",
    "intrigued": "joy", "confused": "anxiety", "uncertain": "anxiety",
    "wonder": "joy", "curiosity": "joy"
}


# Map model labels -> your canonical labels.
# Using a solid public model: j-hartmann/emotion-english-distilroberta-base
# Model labels: anger, disgust, fear, joy, neutral, sadness, surprise


AFFIRMATIONS = {
    "joy": [
        "Savor this feeling—you’ve earned it.",
        "Let yourself enjoy this moment without hesitation.",
        "Your light helps others find theirs.",
        "You deserve this peace and happiness.",
        "Stay open to joy—it reminds you what’s good in life.",
        "Keep this warmth close; you can return to it anytime.",
        "Gratitude deepens happiness; notice what’s right today.",
        "Happiness isn’t fragile—you’re allowed to feel good.",
        "Let your smile linger—it’s healing in itself.",
        "Be proud of how far you’ve come."
    ],
    "sad": [
        "It’s okay to feel low; you won’t feel this way forever.",
        "Tears are proof of your capacity to care.",
        "You’re healing, even if it feels slow.",
        "You’re not alone—others have felt this too.",
        "Gentleness with yourself is strength, not weakness.",
        "You’re allowed to rest; growth happens quietly too.",
        "This sadness will pass, but your depth will remain.",
        "Even in loss, you carry love forward.",
        "Your softness is not a flaw—it’s a superpower.",
        "Take this time to breathe and rebuild."
    ],
    "anger": [
        "Take a breath; your calm gives you control.",
        "Anger is information—listen to what it’s telling you.",
        "You have every right to feel this, but you choose peace.",
        "Your fire can fuel change, not destruction.",
        "Breathe before you act; power doesn’t need noise.",
        "Transform frustration into focus.",
        "You’re learning to respond, not just react.",
        "It’s okay to step away; calm is wisdom.",
        "You’re not your anger—you’re the awareness behind it.",
        "Let the storm pass before you steer."
    ],
    "anxiety": [
        "You’ve handled hard things before—this is another step.",
        "You are safe right now; breathe and notice your body.",
        "It’s okay to pause before you decide.",
        "You don’t have to have every answer today.",
        "Even uncertainty has room for peace.",
        "Breathe deeply—each exhale lets go of tension.",
        "You are capable of handling what’s ahead.",
        "Let thoughts float by; not all deserve your energy.",
        "It’s okay to take things one minute at a time.",
        "You’re not failing—you’re adapting."
    ],
    "neutral": [
        "You’re steady and present—a good place to be.",
        "Peace is a quiet kind of happiness.",
        "You don’t always need intensity; calm is beautiful too.",
        "Stillness is the soil where clarity grows.",
        "You’re centered, balanced, and enough.",
        "Not every moment needs meaning—this one simply is.",
        "Appreciate the calm before the next wave.",
        "Neutral moments can be grounding—stay with them.",
        "You’re recharging, even if it feels uneventful.",
        "This is your pause before progress."
    ]
}


# Optionally override via env var
MODEL_ID = os.getenv("HF_MODEL_ID", "j-hartmann/emotion-english-distilroberta-base")

# ---------------------------
# App
# ---------------------------
app = FastAPI(title="Emotion Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5001","http://localhost:5001"],
    allow_credentials=True,
    allow_methods=["POST","OPTIONS"],
    allow_headers=["*"],
)

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
    affirmation = pick_affirmation(emotion)

    return AnalyzeOut(
        emotion=emotion,
        confidence=confidence,
        scores=scores,
        top_words=top_words,
        affirmation=affirmation,
    )

def pick_affirmation(emotion: str) -> str:
    opts = AFFIRMATIONS.get(emotion)
    if isinstance(opts, list) and opts:
        return random.choice(opts)
    # fallback if emotion missing or list empty
    return "Error, System Missing Response"

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
