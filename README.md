# Sora Vault Cloud - Gemma 4 Good Hackathon

Sora Vault Cloud turns local AI-video folders into a private searchable library. The project uses a cloud dashboard plus a local connector so the browser never crawls the user's disk directly. The connector reads only approved folders, syncs structured metadata, and the app exposes a local Gemma 4 provider path through Ollama with `gemma4:e2b`.

## Demo

Narrated proof video: https://youtu.be/M9n9oJnlWFc

The video shows:

- a fresh account being created
- the real connector running while live sync output is visible
- the final dashboard with synced device, root, and clip metadata
- the local Gemma 4 provider configured as `gemma4:e2b`

## Contents

- `source/` - FastAPI app, browser UI, connector, storage, AI runtime, and config
- `gemma-4-good-hackathon-writeup.md` - submission writeup
- `sora-vault-gemma4-narrated-proof.mp4` - narrated demo video
- `narration.txt` - narration script used for the video

## Run Locally

```powershell
cd source
py -3 -m pip install -r requirements.txt
py -3 api.py
```

Open:

```text
http://127.0.0.1:8780/
```

Run the connector after creating an account in the UI:

```powershell
$env:SORA_VAULT_PASSWORD = "YOUR_PASSWORD"
py -3 connector.py `
  --api-url http://127.0.0.1:8780 `
  --email "you@example.com" `
  --password-env SORA_VAULT_PASSWORD `
  --device-name "My Desktop" `
  --folders "D:\SORA"
```

For local Gemma 4:

```powershell
ollama pull gemma4:e2b
$env:SORA_VAULT_AI_PROVIDER_DEFAULT = "local_gemma"
$env:SORA_VAULT_OLLAMA_MODEL = "gemma4:e2b"
```
