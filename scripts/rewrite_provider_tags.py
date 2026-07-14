import json
import os
import re
from typing import Dict, Any

CONFIG_PATH = os.path.expandvars(r"%USERPROFILE%\.config\opencode\opencode.jsonc")
ALIAS_PATH = ".omo/evidence/all-providers-tags/cross_provider_aliases.json"


def normalize_id(model_id: str) -> str:
    if not model_id:
        return ""
    if "/" in model_id:
        parts = model_id.split("/")
        if parts[0].lower() in [
            "openrouter",
            "nvidia",
            "google",
            "openai",
            "deepseek",
            "opencode",
        ]:
            model_id = "/".join(parts[1:])
    if model_id.endswith(":free"):
        model_id = model_id[:-5]
    return model_id


def infer_capability(norm_id: str, current_cap: str) -> str:
    if current_cap and current_cap != "UNKNOWN":
        return current_cap

    norm_id = norm_id.lower()
    # 1. Strongest Reasoning
    if any(
        kw in norm_id
        for kw in [
            "deep-research-max",
            "deep-research-pro",
            "research",
            "reasoning",
            "thinking",
        ]
    ):
        return "最強推理"
    # 2. Selected Reasoning
    if "preview" in norm_id:
        return "精選推理"
    # 3. Selected Coding (Fallback for Image, Embedding, etc.)
    return "精選編碼"


def get_payment_symbol(provider: str, model_id: str, current_name: str) -> str:
    if any(kw in current_name for kw in ["已停用", "汙染異常", "避用"]):
        return "⚠️"
    if provider == "google":
        return "🆓"
    if provider == "opencode":
        return "🆓" if ("free" in model_id.lower() or "🆓" in current_name) else "💰"
    if provider == "deepseek":
        return "💸"
    if provider == "nvidia":
        return "🆓"
    if provider == "openai":
        return "🔑"
    if provider == "openrouter":
        return "🆓" if ":free" in model_id else "💰"
    return "💰"


def get_modality_symbols(model_id: str, provider: str) -> str:
    symbols = ""
    norm_id = normalize_id(model_id)
    if any(kw in norm_id for kw in ["reasoning", "reasoner", "thinking"]):
        symbols += "🧠"
    if "pro" in norm_id and provider in ["google", "openai"]:
        symbols += "📖"
    if any(kw in norm_id for kw in ["image", "vision", "flux"]):
        symbols += "🎨"
    if "nemotron-3-super" in norm_id or "nemotron-3-ultra" in norm_id:
        symbols += "📖"
    if "gemini-3.1-pro" in norm_id:
        symbols += "📖"
    return symbols


def main():
    print(f"Loading config: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Loading alias map: {ALIAS_PATH}")
    with open(ALIAS_PATH, "r", encoding="utf-8") as f:
        alias_map = json.load(f)

    providers = ["google", "opencode", "deepseek", "nvidia", "openai", "openrouter"]

    for p_key in providers:
        print(f"Updating provider: {p_key}...")
        block_pattern = rf"\"{p_key}\"\s*:\s*\{{"
        match = re.search(block_pattern, content)
        if not match:
            continue

        start_idx = match.start()
        models_start_idx = content.find('"models": {', start_idx)
        if models_start_idx == -1:
            continue

        brace_count = 1
        idx = models_start_idx + 12
        while brace_count > 0 and idx < len(content):
            if content[idx] == "{":
                brace_count += 1
            elif content[idx] == "}":
                brace_count -= 1
            idx += 1

        models_json_str = content[models_start_idx:idx]
        cleaned_json = re.sub(r"//.*", "", models_json_str)
        cleaned_json = re.sub(r",\s*\}", "}", cleaned_json)
        cleaned_json = re.sub(r",\s*\]", "]", cleaned_json)

        try:
            models_dict = json.loads("{" + cleaned_json + "}")["models"]
        except Exception as e:
            print(f"  Error parsing {p_key} models: {e}")
            continue

        for m_id, m_info in models_dict.items():
            old_name = m_info.get("name", "")
            norm_id = normalize_id(m_id)

            # Resolve Capability (Use Inference if UNKNOWN)
            base_cap = alias_map.get(norm_id, {}).get("canonical_capability", "UNKNOWN")
            capability = infer_capability(norm_id, base_cap)

            payment = get_payment_symbol(p_key, m_id, old_name)
            modality = get_modality_symbols(m_id, p_key)

            cleaned_name = re.sub(r"\[[^\]]*\]", "", old_name).strip()
            cleaned_name = re.sub(r"\(.*?免費\)", "", cleaned_name).strip()

            m_info["name"] = f"[{payment}{modality}{capability}] {cleaned_name}"

        updated_models_str = json.dumps(models_dict, ensure_ascii=False, indent=4)
        final_block = '"models": ' + updated_models_str
        content = content[:models_start_idx] + final_block + content[idx:]

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("All providers updated successfully. UNKNOWN tags resolved.")


if __name__ == "__main__":
    main()
