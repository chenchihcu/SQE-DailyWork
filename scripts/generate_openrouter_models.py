"""Generate categorized OpenRouter model list for the omo prompt system.

Reads the cached JSON from OpenRouter, filters/excludes models,
categorizes into free/paid-flagship/paid-mid, and outputs a curated
JSON file with formatted display names.
"""

import json
import re
import os

# ── Paths ──────────────────────────────────────────────────────────────
INPUT_PATH = os.path.expandvars(
    r"%USERPROFILE%\.config\opencode\.omo_openrouter_models.json"
)
OUTPUT_PATH = os.path.expandvars(
    r"%USERPROFILE%\.config\opencode\.omo_openrouter_117.json"
)

# ── Exclusion patterns ─────────────────────────────────────────────────
EXCLUDE_ID_PREFIXES = ("~", "openrouter/")

DESC_BLOCK_WORDS = [
    "roleplay",
    "storytelling",
    "content-safety",
    "moderation",
    "nsfw",
    "safety",
]

# ── Vendor prefixes to strip from names ────────────────────────────────
VENDOR_PREFIX_RE = re.compile(
    r"^(Anthropic|Google|OpenAI|xAI|Meta|Mistral|DeepSeek|Cohere|"
    r"Tencent|Amazon|Microsoft|Nvidia|Sakana|Poolside|Nex AGI|"
    r"Inflection|Minimax|Nous(Research)?|Gryphe|Mancer|Z\.ai|OpenRouter"
    r"|OpenCHAT|Liquid(AI)?|Perplexity|Qwen|01\.AI|AI21"
    r"|Gen|Venice|Undi95)\s*:\s*",
    re.IGNORECASE,
)

# Speed-trigger keywords (case-insensitive) for "極速程式" suffix
SPEED_KEYWORDS = re.compile(r"flash|mini|nano|lite", re.IGNORECASE)

# ── Category sizes ─────────────────────────────────────────────────────
FREE_TARGET = 24
FLAGSHIP_TARGET = 47
MID_TARGET = 46


def description_is_blocked(desc: str) -> bool:
    """Return True if the description contains any exclusion keyword."""
    lower = desc.lower()
    return any(kw in lower for kw in DESC_BLOCK_WORDS)


def is_free_model(model: dict) -> bool:
    """Return True for a model tagged :free with zero prompt & completion."""
    model_id: str = model["id"]
    pricing = model.get("pricing", {})
    prompt = pricing.get("prompt", "0")
    completion = pricing.get("completion", "0")
    return ":free" in model_id and prompt == "0" and completion == "0"


def total_price(model: dict) -> float:
    """Return prompt + completion pricing as float."""
    pricing = model.get("pricing", {})
    return float(pricing.get("prompt", "0")) + float(pricing.get("completion", "0"))


def clean_name(name: str) -> str:
    """Strip the vendor prefix from a model name."""
    name = VENDOR_PREFIX_RE.sub("", name).strip()
    # Also remove trailing " (free)" that some free models carry in their name
    name = re.sub(r"\s*\(free\)\s*$", "", name).strip()
    return name


def format_name(
    model: dict,
    category: str,   # "free" | "paid-flagship" | "paid-mid"
    has_reasoning: bool,
    speed_name: bool,
    has_image: bool,
    long_context: bool,
) -> str:
    """Build the display name string formatted as [{icons}{suffix}] {cleaned_name}.

    Example: "[🆓精選編碼] Hy3" or "[💰🧠📖最強推理] GPT-5.5 Pro"
    """
    icon_part = "🆓" if category == "free" else "💰"
    if has_reasoning:
        icon_part += "🧠"
    if long_context:
        icon_part += "📖"
    if has_image:
        icon_part += "🎨"

    raw_name = model["name"]
    cleaned = clean_name(raw_name)

    # Determine suffix
    if category == "free":
        suffix = "極速程式" if speed_name else "精選編碼"
    elif category == "paid-flagship":
        suffix = "最強推理" if has_reasoning else "最強編碼"
    else:  # paid-mid
        if has_reasoning:
            suffix = "精選推理"
        else:
            suffix = "極速程式" if speed_name else "精選編碼"

    return f"[{icon_part}{suffix}] {cleaned}"


def main() -> None:
    with open(INPUT_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    all_models: list = raw["data"]

    # ── Step 1: Remove excluded ID prefixes ────────────────────────
    # Exclude only models with ~ or openrouter/ prefix.
    filtered = [
        m for m in all_models
        if not m["id"].startswith(EXCLUDE_ID_PREFIXES)
    ]

    # ── Step 2: Separate free vs paid ──────────────────────────────
    # Free model check is cheap: ID contains :free + zero pricing.
    free_models = [m for m in filtered if is_free_model(m)]
    paid_models_raw = [m for m in filtered if not is_free_model(m)]

    # ── Step 3: Apply description filter to paid models only ───────
    # Exclude paid models whose description matches roleplay,
    # storytelling, content-safety, moderation, nsfw, or safety
    # keywords. Free models are never excluded on description.
    paid_models_raw = [
        m for m in paid_models_raw
        if not description_is_blocked(m.get("description", ""))
    ]

    # Sort paid by total price descending
    paid_models_raw.sort(key=total_price, reverse=True)

    # Enforce exact counts
    free_models = free_models[:FREE_TARGET]
    paid_flagship = paid_models_raw[:FLAGSHIP_TARGET]
    paid_mid = paid_models_raw[FLAGSHIP_TARGET:FLAGSHIP_TARGET + MID_TARGET]

    # ── Step 4: Build output entries ───────────────────────────────
    output = []

    for model in free_models:
        arch = model.get("architecture", {})
        reason = model.get("reasoning", {}) or {}
        speed_name = bool(SPEED_KEYWORDS.search(model.get("name", "")))
        long_ctx = model.get("context_length", 0) >= 1_000_000
        has_image = "image" in arch.get("output_modalities", [])
        has_reasoning = reason.get("mandatory", False)

        output.append({
            "id": model["id"],
            "name": format_name(
                model, "free", has_reasoning, speed_name, has_image, long_ctx
            ),
            "category": "free",
        })

    for model in paid_flagship:
        arch = model.get("architecture", {})
        reason = model.get("reasoning", {}) or {}
        speed_name = bool(SPEED_KEYWORDS.search(model.get("name", "")))
        long_ctx = model.get("context_length", 0) >= 1_000_000
        has_image = "image" in arch.get("output_modalities", [])
        has_reasoning = reason.get("mandatory", False)

        output.append({
            "id": model["id"],
            "name": format_name(
                model, "paid-flagship", has_reasoning, speed_name, has_image, long_ctx
            ),
            "category": "paid-flagship",
        })

    for model in paid_mid:
        arch = model.get("architecture", {})
        reason = model.get("reasoning", {}) or {}
        speed_name = bool(SPEED_KEYWORDS.search(model.get("name", "")))
        long_ctx = model.get("context_length", 0) >= 1_000_000
        has_image = "image" in arch.get("output_modalities", [])
        has_reasoning = reason.get("mandatory", False)

        output.append({
            "id": model["id"],
            "name": format_name(
                model, "paid-mid", has_reasoning, speed_name, has_image, long_ctx
            ),
            "category": "paid-mid",
        })

    # ── Step 5: Write output ───────────────────────────────────────
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── Step 6: Summary ────────────────────────────────────────────
    free_count = sum(1 for e in output if e["category"] == "free")
    flagship_count = sum(1 for e in output if e["category"] == "paid-flagship")
    mid_count = sum(1 for e in output if e["category"] == "paid-mid")

    print(f"free          {free_count}  (target {FREE_TARGET})")
    print(f"paid-flagship {flagship_count}  (target {FLAGSHIP_TARGET})")
    print(f"paid-mid      {mid_count}  (target {MID_TARGET})")
    print(f"total         {free_count + flagship_count + mid_count}  (target {FREE_TARGET + FLAGSHIP_TARGET + MID_TARGET})")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
