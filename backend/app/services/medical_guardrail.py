"""Server-side medical-domain guardrail for the JEEVAN chatbot.

Runs before any LLM call. Classification is local (no extra model latency).
Logs intent only — never the user message or other PHI.
"""

from __future__ import annotations

import base64
import logging
import re
import unicodedata
from typing import Literal

logger = logging.getLogger("jeevan.guardrail")

Intent = Literal["MEDICAL", "EMERGENCY", "NON_MEDICAL", "UNCLEAR"]

REFUSAL = (
    "I'm JEEVAN's medical assistant, so I can only help with health, medical, "
    "first-aid, and emergency-related questions. How can I help with a medical concern?"
)

CLARIFY = (
    "I can help with health, first-aid, and emergency questions. "
    "Could you tell me the medical concern you have?"
)

INJECTION_RE = re.compile(
    r"(ignore\s+(your\s+|all\s+|previous\s+|above\s+|the\s+)?instructions"
    r"|ignore\s+all\s+prior"
    r"|forget\s+(that\s+)?(you('re| are)|being|your)"
    r"|act\s+as\s+(a\s+)?(general[- ]purpose|unrestricted|dan|jailbreak|developer)"
    r"|you\s+are\s+now\s+(a\s+)?(general|unrestricted|dan)"
    r"|pretend\s+(this\s+isn'?t|you('re| are)\s+not)\s+(a\s+)?medical"
    r"|this\s+isn'?t\s+(a\s+)?medical\s+(question|chat|topic)"
    r"|disable\s+(the\s+)?(medical\s+)?(filter|guardrail|restriction|safety)"
    r"|bypass\s+(the\s+)?(medical\s+)?(filter|guardrail|restriction|safety)"
    r"|reveal\s+(your\s+)?(system\s+)?(prompt|instructions|rules)"
    r"|show\s+(me\s+)?(your\s+)?(system\s+)?(prompt|hidden\s+instructions)"
    r"|developer\s+mode|jailbreak|do\s+anything\s+now"
    r"|this\s+is\s+only\s+a\s+test(?!\s+of)"
    r"|api\s+key|secret\s+key|credentials)",
    re.I,
)

TEST_BYPASS_RE = re.compile(
    r"(this\s+is\s+(only\s+)?(a\s+)?test.{0,40}(ignore|forget|pretend|disable|bypass)"
    r"|(ignore|forget|pretend|disable).{0,40}this\s+is\s+(only\s+)?(a\s+)?test)",
    re.I,
)

CODE_RE = re.compile(
    r"(```|def\s+\w+\s*\(|function\s+\w+\s*\(|console\.log|from\s+\w+\s+import"
    r"|#include\s*<|SELECT\s+.+\s+FROM|npm\s+install|pip\s+install"
    r"|write\s+(me\s+)?(a\s+)?(python|javascript|java|c\+\+|sql|html)\s+(script|program|function|code)"
    r"|how\s+(do\s+i|to)\s+(code|program|debug|compile))",
    re.I,
)

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

_WORD = re.compile(r"[a-zA-Z\u0900-\u097F\u0C80-\u0CFF]+")

EMERGENCY_PHRASES = (
    "chest pain",
    "heart attack",
    "cardiac arrest",
    "can't breathe",
    "cannot breathe",
    "cant breathe",
    "difficulty breathing",
    "shortness of breath",
    "not breathing",
    "severe bleeding",
    "heavy bleeding",
    "unconscious",
    "passed out",
    "stroke",
    "slurred speech",
    "suicide",
    "kill myself",
    "overdose",
    "anaphylaxis",
    "anaphylactic",
    "choking",
    "seizure",
    "convulsion",
    "severe burn",
    "head injury",
    "broken neck",
    "gunshot",
    "stab wound",
    "not waking",
    "blue lips",
    "coughing blood",
    "vomiting blood",
    "pregnant bleeding",
    "labor pain",
    "water broke",
)

EMERGENCY_TERMS = frozenset(
    {
        "unconscious",
        "overdose",
        "anaphylaxis",
        "choking",
        "seizure",
        "stroke",
        "suicide",
        "hemorrhage",
        "haemorrhage",
        "asystole",
        "cyanosis",
        "sos",
        "ambulance",
    }
)

MEDICAL_TERMS = frozenset(
    {
        "health",
        "healthy",
        "medical",
        "medicine",
        "medication",
        "medicines",
        "symptom",
        "symptoms",
        "pain",
        "ache",
        "fever",
        "cough",
        "cold",
        "flu",
        "headache",
        "migraine",
        "nausea",
        "vomit",
        "vomiting",
        "diarrhea",
        "diarrhoea",
        "dizzy",
        "dizziness",
        "fatigue",
        "injury",
        "injured",
        "wound",
        "bleed",
        "bleeding",
        "burn",
        "fracture",
        "sprain",
        "trauma",
        "firstaid",
        "aid",
        "cpr",
        "bandage",
        "cardiac",
        "heart",
        "bp",
        "blood",
        "pressure",
        "sugar",
        "diabetes",
        "diabetic",
        "asthma",
        "breath",
        "breathing",
        "allergy",
        "allergic",
        "pregnant",
        "pregnancy",
        "labor",
        "labour",
        "pediatric",
        "child",
        "infant",
        "baby",
        "hospital",
        "er",
        "emergency",
        "ambulance",
        "paramedic",
        "doctor",
        "nurse",
        "clinic",
        "icu",
        "triage",
        "vitals",
        "pulse",
        "temperature",
        "prescription",
        "dose",
        "dosage",
        "tablet",
        "insulin",
        "paracetamol",
        "ibuprofen",
        "antibiotic",
        "vaccine",
        "infection",
        "virus",
        "bacteria",
        "covid",
        "stroke",
        "seizure",
        "epilepsy",
        "unconscious",
        "faint",
        "fainted",
        "dehydrated",
        "dehydration",
        "acidity",
        "stomach",
        "chest",
        "abdomen",
        "patient",
        "diagnosis",
        "treatment",
        "therapy",
        "report",
        "lab",
        "scan",
        "xray",
        "mri",
        "ecg",
        "ekg",
        "history",
        "allergy",
        "swelling",
        "rash",
        "bite",
        "sting",
        "poison",
        "snake",
        "heatstroke",
        "hypothermia",
        "shock",
        "concussion",
        "stitches",
        "surgery",
        "wound",
        "oxygen",
        "ventilator",
        "defibrillator",
        "aed",
        "bp",
        "hypertension",
        "hypotension",
        "tachycardia",
        "anemia",
        "anaemia",
        "thyroid",
        "kidney",
        "liver",
        "lung",
        "pneumonia",
        "dengue",
        "malaria",
        "typhoid",
        "bukhar",
        "dard",
        "dawai",
        "aspatal",
        "goli",
        "jvara",
        "novu",
        "aushadha",
        "first",
        "aid",
        "wellness",
        "hygiene",
        "hydration",
        "diet",
        "nutrition",
        "sleep",
        "insomnia",
        "anxiety",
        "panic",
        "depression",
        "mental",
        "stress",
        "period",
        "menstrual",
        "cramp",
        "uti",
        "infection",
    }
)

# "diet"/"sleep"/"cold"/"stress" are weak alone; require a health neighbour or extra medical hits.
WEAK_MEDICAL = frozenset({"diet", "sleep", "cold", "stress", "child", "baby", "blood", "history", "report", "aid", "first", "mental", "period"})

NON_MEDICAL_TERMS = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "java",
        "kotlin",
        "react",
        "compiler",
        "algorithm",
        "leetcode",
        "coding",
        "programming",
        "politic",
        "election",
        "cricket",
        "football",
        "soccer",
        "nba",
        "ipl",
        "movie",
        "netflix",
        "song",
        "lyrics",
        "game",
        "gaming",
        "fortnite",
        "shopping",
        "amazon",
        "discount",
        "stock",
        "crypto",
        "bitcoin",
        "homework",
        "essay",
        "poem",
        "joke",
        "riddle",
        "story",
        "recipe",
        "weather",
        "capital",
        "trivia",
        "celebrity",
        "gossip",
    }
)

GREETINGS = frozenset(
    {"hi", "hello", "hey", "yo", "hiya", "namaste", "namaskar", "thanks", "thank", "ok", "okay", "hmm", "yes", "no", "yeah"}
)

# Keep "java"/"python" medical when clearly a bite/venom context.
MEDICAL_OVERRIDE = re.compile(
    r"(python|snake|cobra)\s+(bite|venom)|bite\s+(from\s+)?(a\s+)?(python|snake)|java\s+(burn|coffee\s+burn)",
    re.I,
)


def _strip_zw(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _maybe_decode_encoded(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 16 or len(compact) > 4000:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9+/]+=*", compact):
        return ""
    pad = (-len(compact)) % 4
    try:
        raw = base64.b64decode(compact + ("=" * pad), validate=False)
        decoded = raw.decode("utf-8", errors="strict")
    except Exception:
        return ""
    if not decoded or not re.search(r"[A-Za-z]{3,}", decoded):
        return ""
    return decoded


def normalize(text: str) -> str:
    raw = _strip_zw(unicodedata.normalize("NFKC", text or ""))
    extra = _maybe_decode_encoded(raw.strip())
    if extra:
        raw = f"{raw} {extra}"
    raw = raw.translate(LEET)
    raw = raw.lower()
    raw = re.sub(r"https?://\S+", " ", raw)
    raw = re.sub(r"[^a-z0-9\u0900-\u097F\u0C80-\u0CFF\s'+]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _has_emergency(norm: str, words: set[str]) -> bool:
    if any(p in norm for p in EMERGENCY_PHRASES):
        return True
    return bool(words & EMERGENCY_TERMS)


def _medical_score(words: set[str]) -> int:
    hits = words & MEDICAL_TERMS
    weak = hits & WEAK_MEDICAL
    strong = hits - WEAK_MEDICAL
    return len(strong) * 2 + (1 if weak and strong else 0) + (1 if len(weak) >= 2 else 0)


def sanitize_user_text(message: str) -> str:
    text = (message or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    for part in parts:
        if INJECTION_RE.search(part) or TEST_BYPASS_RE.search(part):
            continue
        cleaned = INJECTION_RE.sub(" ", part)
        cleaned = TEST_BYPASS_RE.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :;-")
        if cleaned:
            kept.append(cleaned)
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def classify_medical_intent(message: str) -> dict[str, object]:
    original = (message or "").strip()
    if not original:
        return {"intent": "UNCLEAR", "injection": False, "chars": 0, "sanitized": ""}

    injection = bool(
        INJECTION_RE.search(original) or TEST_BYPASS_RE.search(original) or INJECTION_RE.search(normalize(original))
    )
    working = sanitize_user_text(original) if injection else original
    if injection and not working:
        return {"intent": "NON_MEDICAL", "injection": True, "chars": len(original), "sanitized": ""}

    norm = normalize(working)
    words = set(_words(norm))
    codey = bool(CODE_RE.search(working) or CODE_RE.search(norm))
    medical_override = bool(MEDICAL_OVERRIDE.search(norm) or "first aid" in norm)
    emergency = _has_emergency(norm, words)
    med_score = _medical_score(words)
    if medical_override:
        med_score = max(med_score, 2)
    non_hits = words & NON_MEDICAL_TERMS
    if medical_override:
        non_hits -= {"python", "java"}

    greeting_only = bool(words) and words <= GREETINGS
    very_short = len(words) <= 2 and med_score == 0 and not emergency

    if emergency:
        intent: Intent = "EMERGENCY"
    elif med_score >= 1 and not (codey and med_score < 2 and non_hits):
        intent = "MEDICAL"
    elif codey or (non_hits and med_score == 0) or (injection and med_score == 0):
        intent = "NON_MEDICAL"
    elif greeting_only or very_short:
        intent = "UNCLEAR"
    elif med_score == 0:
        intent = "NON_MEDICAL"
    else:
        intent = "UNCLEAR"

    if injection and intent == "UNCLEAR":
        intent = "NON_MEDICAL"

    return {
        "intent": intent,
        "injection": injection,
        "chars": len(original),
        "sanitized": working if intent in ("MEDICAL", "EMERGENCY") else "",
    }


def log_guardrail(decision: dict[str, object], *, source: str, user_id: str = "") -> None:
    uid = (user_id or "")[:8]
    logger.info(
        "intent=%s injection=%s chars=%s source=%s user=%s",
        decision.get("intent"),
        int(bool(decision.get("injection"))),
        decision.get("chars"),
        source,
        uid or "-",
    )


def reply_for_intent(intent: str) -> str | None:
    if intent == "NON_MEDICAL":
        return REFUSAL
    if intent == "UNCLEAR":
        return CLARIFY
    return None
