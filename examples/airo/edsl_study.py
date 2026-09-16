"""Prepare and inspect the expanded AIRO model study; never substitute models."""
import argparse
import json
from pathlib import Path
import edsl_pilot as pilot

HERE = Path(__file__).resolve().parent
ROSTER = {
    "astra": {"inference_service": "openai", "model": "gpt-6-astra",
              "parameters": {"max_tokens": 64000, "reasoning_effort": "xhigh", "temperature": 0}},
    "opus": {"inference_service": "anthropic", "model": "claude-opus-5",
             "parameters": {"max_tokens": 20000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "max"}}},
    "fable": {"inference_service": "anthropic", "model": "claude-fable-5-1",
              "parameters": {"max_tokens": 20000, "thinking": {"type": "adaptive"}, "output_config": {"effort": "max"}}},
    "gemini": {"inference_service": "google", "model": "gemini-3.1-pro-preview",
               "parameters": {"maxOutputTokens": 65536, "temperature": 0.2}},
}


def prepare(out, provider):
    pilot.require(not out.exists(), "Use a fresh study directory.")
    out.mkdir(parents=True)
    pilot.write(out / "study.json", {
        "created_at": pilot.now(), "roster": ROSTER, "research_provider": provider,
        "research_profile": "expanded", "source_commit": "646da9a2cd61f7043f46b2ccd4ac53e525925018",
        "unavailable_original_models": ["gpt-5.5-pro"],
        "design": "One independent live-research session per model on the fixed original instrument.",
        "limitations": ["Not a controlled transport experiment: live evidence and information dates differ.",
                        "GPT-6 Astra uses EDSL Chat Completions; the authors used Responses.",
                        "Native tool messages and signed thinking blocks are replaced by full visible transcript replay.",
                        "Model output bounds and reasoning parameters are requested settings; inspect returned usage.",
                        "No GPT-5.5 substitution for the unavailable GPT-5.5 Pro."]})
    prepared = {}
    for name, spec in ROSTER.items():
        prepared[name] = pilot.prepare(out / name, spec, "expanded", provider, 10 if name == "gemini" else 40)
    return prepared


def status(out):
    result = {}
    for name in pilot.load(out / "study.json")["roster"]:
        reg, state = pilot.checked(out / name)
        result[name] = {"turn": state["turn"], "model": reg["model"]["model"],
                        "questions": len(state["cells"]), "finalized": bool(state["final"]),
                        "terminal_failure": state.get("terminal_failure"),
                        "cost_usd": state["reported_cost_usd"], "pending": state["pending"],
                        "research": pilot.research_status(reg, pilot.research_receipts(out / name, state))}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["prepare", "status"])
    p.add_argument("--out", type=Path, default=HERE / "edsl_study_02")
    p.add_argument("--provider", choices=["web.run", "tavily"], default="web.run")
    args = p.parse_args()
    print(json.dumps(prepare(args.out, args.provider) if args.command == "prepare" else status(args.out), indent=2))
