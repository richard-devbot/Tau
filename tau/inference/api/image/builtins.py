# Lazy registry entries: each provider API is referenced by a "module:ClassName"
# path so its SDK (openai, google.genai, PIL, ...) is only imported when that
# provider is actually used, not at registry construction.
IMAGE_APIS = [
    ("openrouter-image", "tau.inference.api.image.openrouter:OpenRouterImageAPI"),
    ("openai-image",     "tau.inference.api.image.openai_image:OpenAIImageAPI"),
    ("gemini-image",     "tau.inference.api.image.gemini_image:GeminiImageAPI"),
]
