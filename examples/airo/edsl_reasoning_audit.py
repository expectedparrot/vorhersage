"""Reproduce the local Astra parameter omission and write a reviewable EDSL patch.

This script does not change the installed EDSL package or remote workers.
"""
import argparse
import asyncio
import difflib
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def streaming_patch(out):
    from edsl.inference_services.services import anthropic_service
    source = Path(anthropic_service.__file__).read_text()
    old = "                response = await client.messages.create(**create_kwargs)"
    new = """                if self.max_tokens > 20000:
                    async with client.messages.stream(**create_kwargs) as stream:
                        response = await stream.get_final_message()
                else:
                    response = await client.messages.create(**create_kwargs)"""
    assert source.count(old) == 1
    candidate = source.replace(old, new)
    # Exercise the actual patched method with a fake SDK client. This checks
    # that streaming preserves model settings and returns the final message.
    namespace = {"__name__": "edsl.inference_services.services._airo_stream_probe",
                 "__package__": "edsl.inference_services.services"}
    exec(compile(candidate, "<candidate Anthropic adapter>", "exec"), namespace)
    response = {"content": [{"type": "text", "text": "{}"}], "stop_reason": "end_turn", "usage": {"output_tokens": 3}}
    message = SimpleNamespace(model_dump=lambda: response)

    async def check(tokens):
        final = AsyncMock(return_value=message)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=SimpleNamespace(get_final_message=final))
        context.__aexit__ = AsyncMock(return_value=False)
        messages = SimpleNamespace(create=AsyncMock(return_value=message), stream=MagicMock(return_value=context))
        namespace["AsyncAnthropic"] = lambda **kwargs: SimpleNamespace(messages=messages)
        model = namespace["AnthropicService"].create_model("claude-opus-5")(
            max_tokens=tokens, thinking={"type": "adaptive"}, output_config={"effort": "max"})
        with patch.object(type(model), "api_token", property(lambda self: "test-key")):
            result = await model.async_execute_model_call("Forecast research request", "System")
        assert result == response
        call = messages.stream if tokens > 20000 else messages.create
        call.assert_called_once()
        assert call.call_args.kwargs["max_tokens"] == tokens
        assert call.call_args.kwargs["output_config"] == {"effort": "max"}
        assert call.call_args.kwargs["thinking"] == {"type": "adaptive"}
        if tokens > 20000:
            messages.create.assert_not_called()
            final.assert_awaited_once()
        else:
            messages.stream.assert_not_called()
    asyncio.run(check(20000))
    asyncio.run(check(64000))
    relative = "edsl/inference_services/services/anthropic_service.py"
    diff = "".join(difflib.unified_diff(source.splitlines(True), candidate.splitlines(True), fromfile="a/"+relative, tofile="b/"+relative))
    (out / "anthropic-streaming.patch").write_text(diff)
    return {"mock_sdk_checks_passed": True, "tested_token_limits": [20000, 64000], "deployed": False,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest()}


def audit(out):
    from edsl.inference_services.services import open_ai_service as service
    from edsl.inference_services.services import service_enums
    spec = {"model": "gpt-6-astra", "messages": [], "max_tokens": 64000, "reasoning_effort": "xhigh", "temperature": 0}
    before = service.OpenAIParameterBuilder.build_params(**spec)
    with patch.object(service, "OPENAI_REASONING_MODELS", [*service.OPENAI_REASONING_MODELS, "gpt-6"]):
        after = service.OpenAIParameterBuilder.build_params(**spec)
        assert after["reasoning_effort"] == "xhigh"
        assert service.OpenAIParameterBuilder.build_params(model="gpt-4o", messages=[]) .get("reasoning_effort") is None
    source_path = Path(service_enums.__file__)
    source = source_path.read_text()
    candidate = source if '"gpt-6"' in source.split("def ")[0] else source.replace('    "gpt-5.6",', '    "gpt-5.6",\n    "gpt-6",')
    assert candidate != source or before.get("reasoning_effort") == "xhigh"
    relative = "edsl/inference_services/services/service_enums.py"
    diff = "".join(difflib.unified_diff(source.splitlines(True), candidate.splitlines(True), fromfile="a/"+relative, tofile="b/"+relative))
    out.mkdir(parents=True, exist_ok=True)
    (out / "astra-reasoning.patch").write_text(diff)
    result = {"local_edsl_source": str(source_path), "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "requested_effort": "xhigh", "local_outgoing_effort": before.get("reasoning_effort"),
              "patch_check_outgoing_effort": after["reasoning_effort"], "patch_regression_checks_passed": True,
              "deployed": False, "limitation": "Local adapter audit; remote worker request bodies are not exposed. A saved xhigh parameter does not establish that the provider received it."}
    result["anthropic_streaming_patch"] = streaming_patch(out)
    (out / "reasoning-audit.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "edsl_study_02")
    args = p.parse_args()
    print(json.dumps(audit(args.out), indent=2))
