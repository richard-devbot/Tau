# Inference Providers

This page documents all supported LLM inference providers and their setup.

## Supported Providers

Tau supports the following inference providers:

| Provider | Auth Type | Free Tier | Setup |
|----------|-----------|-----------|-------|
| Anthropic | API Key | Limited | [Link](#anthropic) |
| OpenAI | API Key | No | [Link](#openai) |
| Google Gemini | API Key | Yes | [Link](#google-gemini) |
| Mistral AI | API Key | Limited | [Link](#mistral-ai) |
| Ollama | None | Yes | [Link](#ollama-local) |
| Azure OpenAI | API Key | No | [Link](#azure-openai) |

## Anthropic

Anthropic provides Claude models with best-in-class reasoning and code generation.

**Models**: `claude-3-5-sonnet`, `claude-3-opus`, `claude-3-haiku`, `claude-3-5-haiku`

### Setup

1. Create an account at [Anthropic Console](https://console.anthropic.com)
2. Generate an API key in the API keys section
3. Set the environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Verify

```bash
tau --model anthropic/claude-3-5-sonnet -p "Say hello"
```

## OpenAI

OpenAI provides GPT models optimized for a wide range of tasks.

**Models**: `gpt-4`, `gpt-4-turbo`, `gpt-4o`, `gpt-3.5-turbo`

### Setup

1. Create an account at [OpenAI Platform](https://platform.openai.com)
2. Generate an API key in the API keys section
3. Set the environment variable:

```bash
export OPENAI_API_KEY=sk-...
```

### Verify

```bash
tau --model openai/gpt-4o -p "Say hello"
```

## Google Gemini

Google provides Gemini models with multimodal capabilities.

**Models**: `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash`

### Setup

1. Visit [Google AI Studio](https://aistudio.google.com)
2. Create an API key (no account creation needed)
3. Set the environment variable:

```bash
export GEMINI_API_KEY=...
```

### Verify

```bash
tau --model google/gemini-2.0-flash -p "Say hello"
```

## Mistral AI

Mistral offers efficient open-source-based models.

**Models**: `mistral-large`, `mistral-medium`, `mistral-small`

### Setup

1. Create an account at [Mistral Console](https://console.mistral.ai)
2. Generate an API key
3. Set the environment variable:

```bash
export MISTRAL_API_KEY=...
```

### Verify

```bash
tau --model mistral/mistral-large -p "Say hello"
```

## Ollama (Local)

Run open-source models locally without API keys or internet.

**Models**: `llama2`, `mistral`, `neural-chat`, and [others](https://ollama.ai/library)

### Setup

1. Install [Ollama](https://ollama.ai)
2. Pull a model:

```bash
ollama pull mistral
```

3. Start the Ollama server:

```bash
ollama serve
```

4. Set the endpoint (default works if running locally):

```bash
export OLLAMA_BASE_URL=http://localhost:11434
```

### Verify

```bash
tau --model ollama/mistral -p "Say hello"
```

## Azure OpenAI

Use OpenAI models hosted on Azure infrastructure.

**Models**: Same as OpenAI (gpt-4, gpt-3.5-turbo, etc.)

### Setup

1. Create an Azure OpenAI resource in the Azure Portal
2. Deploy a model (e.g., gpt-4)
3. Set environment variables:

```bash
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_BASE_URL=https://your-resource.openai.azure.com
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
```

### Verify

```bash
tau --model azure/gpt-4 -p "Say hello"
```

## Switching Providers

### Command Line

Use a specific provider for a single session:

```bash
tau --provider anthropic
tau --model openai/gpt-4o
tau --provider ollama/mistral
```

### Interactive

Press **Ctrl+L** during a session to switch models.

### Default

Set your default provider in `~/.tau/settings.json`:

```json
{
  "defaultProvider": "anthropic",
  "defaultModel": "claude-3-5-sonnet"
}
```

## Model Listing

List all available models:

```bash
tau --list-models
```

Filter by provider:

```bash
tau --list-models anthropic
tau --list-models openai
```

## Troubleshooting

### Provider Not Found

If a provider is not listed in `tau --list-models`, check:

1. **API key is set**: `env | grep API_KEY`
2. **Provider is supported**: Verify it's in the list above
3. **Credentials are valid**: Test with a curl request to the provider's API

### Connection Timeout

If tau cannot reach a provider:

1. Check your internet connection
2. Verify the provider's API is not down
3. Check for network firewalls or proxies blocking the connection

### Rate Limits

If you hit rate limits from a provider:

1. Wait before retrying
2. Consider upgrading your account tier
3. Use a different provider with higher limits

## Next Steps

- [Quickstart](quickstart.md) - Set up your first provider
- [Settings](settings.md) - Configure default provider behavior
- [Installation](installation.md) - Detailed authentication setup
