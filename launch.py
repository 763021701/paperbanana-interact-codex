"""Run the bundled PaperBanana-Interact Gradio UI with the Codex provider."""

import argparse
import base64
from functools import wraps
import os
from pathlib import Path
import sys

import gradio as gr
from google.genai import types

from codex_bridge import BridgeError, IMAGE_MODEL, TEXT_MODEL, find_codex, model_response

UPSTREAM = Path(__file__).resolve().parent / "vendor" / "paperbanana-interact"
BRIDGE_NOTICE = (
    "Uses the ChatGPT account already signed in to Codex. "
    "Leave API keys blank when using codex and codex-image. "
    "Paper text and attached figures are sent to ChatGPT."
)


def configure_provider(generation):
    original_text = generation.call_model_with_retry_async
    original_gemini = generation.call_gemini_with_retry_async
    original_openrouter = generation.call_openrouter_image_generation_with_retry_async

    @wraps(original_text)
    async def text(model_name, contents, config, *args, **kwargs):
        if model_name != TEXT_MODEL:
            return await original_text(model_name, contents, config, *args, **kwargs)
        return_content = kwargs.get("return_content", args[3] if len(args) > 3 else False)
        results = []
        for _ in range(config.candidate_count or 1):
            answer = await model_response(config.system_instruction, contents)
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


def build():
    sys.path.insert(0, str(UPSTREAM))
    import app as upstream
    from utils import generation_utils

    configure_provider(generation_utils)
    upstream.DEFAULT_MAIN_MODEL = TEXT_MODEL
    upstream.DEFAULT_IMAGE_MODEL = IMAGE_MODEL
    ui = upstream.build_app()
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
    ui, css = build()
    ui.launch(server_name="127.0.0.1", server_port=args.port, share=False, css=css)


if __name__ == "__main__":
    main()
