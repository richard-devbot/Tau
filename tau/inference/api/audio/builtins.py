# Lazy registry entries: each provider API is referenced by a "module:ClassName"
# path so its SDK is only imported when that provider is actually used, not at
# registry construction.
#
# openai-audio:     OpenAI-compatible — works for OpenAI, Groq, and any provider
#                   that implements /v1/audio/speech and /v1/audio/transcriptions.
# gemini-audio:     Gemini generate_content with response_modalities=["AUDIO"] (TTS only).
# sarvam-audio:     Sarvam AI proprietary REST API — Indian language TTS + STT.
# elevenlabs-audio: ElevenLabs proprietary REST API — voice_id in URL path, xi-api-key auth.
AUDIO_APIS = [
    ("openai-audio",     "tau.inference.api.audio.openai_audio:OpenAIAudioAPI"),
    ("gemini-audio",     "tau.inference.api.audio.gemini_audio:GeminiAudioAPI"),
    ("sarvam-audio",     "tau.inference.api.audio.sarvam_audio:SarvamAudioAPI"),
    ("elevenlabs-audio", "tau.inference.api.audio.elevenlabs_audio:ElevenLabsAudioAPI"),
]
