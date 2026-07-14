import json, os, re

CONFIG_PATH = os.path.expandvars(r"%USERPROFILE%\.config\opencode\opencode.jsonc")
ALIAS_PATH = ".omo/evidence/all-providers-tags/cross_provider_aliases.json"
DISCOVERY_PATH = ".omo/evidence/all-providers-tags/discovered_models.json"


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
    if "preview" in norm_id:
        return "精選推理"
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
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    with open(ALIAS_PATH, "r", encoding="utf-8") as f:
        alias_map = json.load(f)
    with open(DISCOVERY_PATH, "r", encoding="utf-8") as f:
        discovered = json.load(f)

    cleaned = re.sub(
        r"(\".*?\"|'.*?')|//.*", lambda m: m.group(1) if m.group(1) else "", content
    )
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
    data = json.loads(cleaned)

    providers_data = data.get("provider", {})

    for p_key, discovered_models in discovered.items():
        if p_key not in providers_data:
            providers_data[p_key] = {"options": {}, "models": {}}

        models_dict = providers_data[p_key].get("models", {})

        for m_id in discovered_models:
            # Get existing info or create new
            m_info = models_dict.get(m_id, {"name": m_id})
            old_name = m_info.get("name", m_id)
            norm_id = normalize_id(m_id)

            base_cap = alias_map.get(norm_id, {}).get("canonical_capability", "UNKNOWN")
            capability = infer_capability(norm_id, base_cap)
            payment = get_payment_symbol(p_key, m_id, old_name)
            modality = get_modality_symbols(m_id, p_key)

            cleaned_name = re.sub(r"\[[^\]]*\]", "", old_name).strip()
            cleaned_name = re.sub(r"\(.*?免費\)", "", cleaned_name).strip()
            if not cleaned_name:
                cleaned_name = m_id

            m_info["name"] = f"[{payment}{modality}{capability}] {cleaned_name}"
            models_dict[m_id] = m_info

        providers_data[p_key]["models"] = models_dict

    # Final write: Preserve original structure as much as possible
    # Since we changed the dictionary, we rewrite the provider block
    final_json = json.dumps(data, ensure_ascii=False, indent=2)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(final_json)
    print("Success: All discovered models synchronized and labeled.")


if __name__ == "__main__":
    main()
