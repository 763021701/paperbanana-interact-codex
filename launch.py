"""Run the bundled PaperBanana-Interact Gradio UI with the Codex provider."""

import argparse
import asyncio
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import os
from pathlib import Path
import sys

import gradio as gr
from google.genai import types

from codex_bridge import (
    BridgeError,
    DEFAULT_REASONING_EFFORT,
    IMAGE_MODEL,
    TEXT_MODEL,
    TEXT_MODEL_PREFIX,
    discover_codex_models,
    find_codex,
    model_response,
)

UPSTREAM = Path(__file__).resolve().parent / "vendor" / "paperbanana-interact"
BRIDGE_NOTICE = (
    "Uses the ChatGPT account already signed in to Codex. "
    "Leave API keys blank when using the Codex bridge. "
    "Paper text and attached figures are sent to ChatGPT."
)
DEFAULT_TEXT_CHOICES = (("Codex default", TEXT_MODEL),)
DEFAULT_EFFORT_CHOICES = {TEXT_MODEL: (DEFAULT_REASONING_EFFORT,)}
REQUEST_EFFORT = ContextVar("codex_request_effort", default=None)


async def codex_model_catalog():
    choices = list(DEFAULT_TEXT_CHOICES)
    efforts = dict(DEFAULT_EFFORT_CHOICES)
    models, default_model = await discover_codex_models()
    for entry in models:
        model_id = entry.get("model")
        if not model_id or not {"text", "image"}.issubset(entry.get("inputModalities") or []):
            continue
        label = entry.get("displayName") or model_id
        choice = TEXT_MODEL_PREFIX + model_id
        choices.append((label, choice))
        supported = tuple(
            item["reasoningEffort"]
            for item in entry.get("supportedReasoningEfforts", [])
            if item.get("reasoningEffort")
        )
        if supported:
            efforts[choice] = supported
            if model_id == default_model:
                efforts[TEXT_MODEL] = supported
    return choices, efforts


def reasoning_options(model, requested, efforts):
    if not model or (model != TEXT_MODEL and not model.startswith(TEXT_MODEL_PREFIX)):
        return (), None
    supported = efforts.get(model, DEFAULT_EFFORT_CHOICES[TEXT_MODEL])
    if requested in supported:
        return supported, requested
    if DEFAULT_REASONING_EFFORT in supported:
        return supported, DEFAULT_REASONING_EFFORT
    return supported, supported[0]


@contextmanager
def model_request(model, requested, efforts):
    _, effort = reasoning_options(model, requested, efforts)
    token = REQUEST_EFFORT.set(effort)
    try:
        yield
    finally:
        REQUEST_EFFORT.reset(token)


def model_fields(choices, efforts):
    main = gr.Dropdown(
        choices=choices,
        value=TEXT_MODEL,
        label="Main Model",
        info="Codex LLM for planning, critique and refinement.",
        allow_custom_value=True,
        scale=2,
    )
    available_efforts = gr.State(efforts)
    levels, initial_effort = reasoning_options(TEXT_MODEL, None, efforts)
    effort = gr.Dropdown(
        choices=levels,
        value=initial_effort,
        label="Reasoning Effort",
        info="Reasoning level for Codex planning, critique and refinement.",
        scale=1,
    )
    image = gr.Dropdown(
        choices=[("Codex built-in image generation (automatic)", IMAGE_MODEL)],
        value=IMAGE_MODEL,
        label="Image Model",
        info="Codex selects the built-in image model automatically.",
        allow_custom_value=True,
        scale=2,
    )
    refresh = gr.Button("Refresh Codex models", size="sm", scale=0)

    def update_effort(model, requested, supported):
        levels, value = reasoning_options(model, requested, supported)
        return gr.update(choices=list(levels), value=value, interactive=bool(levels))

    async def refresh_choices(selected, requested):
        try:
            available, supported = await codex_model_catalog()
        except (BridgeError, OSError, ValueError) as error:
            gr.Warning(f"Could not load the Codex model list: {error}")
            return gr.skip(), gr.skip(), gr.skip()
        if not selected or (
            selected.startswith(TEXT_MODEL_PREFIX) and selected not in {value for _, value in available}
        ):
            selected = TEXT_MODEL
        return gr.update(choices=available, value=selected), update_effort(selected, requested, supported), supported

    main.input(
        update_effort, [main, effort, available_efforts], effort,
        api_name="codex_reasoning_efforts", show_progress="hidden",
    )
    effort.change(lambda *_: None, effort, show_progress="hidden", api_name=False)
    refresh.click(
        refresh_choices, [main, effort], [main, effort, available_efforts],
        api_name="refresh_codex_models", show_progress="minimal",
    )
    return main, image, effort, available_efforts


def configure_provider(generation):
    original_text = generation.call_model_with_retry_async
    original_gemini = generation.call_gemini_with_retry_async
    original_openrouter = generation.call_openrouter_image_generation_with_retry_async

    @wraps(original_text)
    async def text(model_name, contents, config, *args, **kwargs):
        if model_name == TEXT_MODEL:
            selected_model = None
        elif model_name.startswith(TEXT_MODEL_PREFIX):
            selected_model = model_name.removeprefix(TEXT_MODEL_PREFIX).strip()
            if not selected_model:
                raise BridgeError("Select a Codex model")
        else:
            return await original_text(model_name, contents, config, *args, **kwargs)
        return_content = kwargs.get("return_content", args[3] if len(args) > 3 else False)
        results = []
        for _ in range(config.candidate_count or 1):
            answer = await model_response(
                config.system_instruction, contents, model=selected_model, effort=REQUEST_EFFORT.get()
            )
            if return_content:
                answer = types.Content(role="model", parts=[types.Part.from_text(text=answer)])
            results.append(answer)
        return results

    async def image(contents, instruction, ratio, size):
        result = await model_response(instruction, contents, image=True, ratio=ratio, size=size)
        return [base64.b64encode(result).decode("ascii")]

    @wraps(original_gemini)
    async def gemini(model_name, contents, config, *args, **kwargs):
        if model_name != IMAGE_MODEL:
            return await original_gemini(model_name, contents, config, *args, **kwargs)
        return await image(
            contents, config.system_instruction, config.image_config.aspect_ratio, config.image_config.image_size
        )

    @wraps(original_openrouter)
    async def openrouter(model_name, contents, config, *args, **kwargs):
        if model_name != IMAGE_MODEL:
            return await original_openrouter(model_name, contents, config, *args, **kwargs)
        return await image(contents, config.get("system_prompt"), config.get("aspect_ratio"), config.get("image_size"))

    generation.call_model_with_retry_async = text
    generation.call_gemini_with_retry_async = gemini
    generation.call_openrouter_image_generation_with_retry_async = openrouter


def build(choices=DEFAULT_TEXT_CHOICES, efforts=None):
    sys.path.insert(0, str(UPSTREAM))
    import app as upstream
    from utils import generation_utils

    configure_provider(generation_utils)
    upstream.DEFAULT_MAIN_MODEL = TEXT_MODEL
    upstream.DEFAULT_IMAGE_MODEL = IMAGE_MODEL
    ui = upstream.build_app(
        model_fields=lambda: model_fields(choices, efforts or DEFAULT_EFFORT_CHOICES),
        model_request=model_request,
    )
    for component in ui.blocks.values():
        label = getattr(component, "label", None)
        if label == "# Candidates":
            component.value = 1
        elif label == "Critic Rounds":
            component.value = 0
        elif isinstance(component, gr.Markdown) and component.value == "🔑 Gemini API Key":
            component.value = BRIDGE_NOTICE
    ui.config = ui.get_config_file()
    return ui, upstream.APP_CSS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=7861, help="Loopback port (default: 7861)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        find_codex()
    except BridgeError as error:
        parser.error(str(error))

    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    try:
        choices, efforts = asyncio.run(codex_model_catalog())
    except (BridgeError, OSError, ValueError) as error:
        print(f"Could not load the Codex model list: {error}", file=sys.stderr)
        choices, efforts = DEFAULT_TEXT_CHOICES, DEFAULT_EFFORT_CHOICES
    ui, css = build(choices, efforts)
    ui.launch(server_name="127.0.0.1", server_port=args.port, share=False, css=css)


if __name__ == "__main__":
    main()
