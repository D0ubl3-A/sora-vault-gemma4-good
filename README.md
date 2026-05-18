# Sora Vault Cloud - Gemma 4 Good Hackathon

Sora Vault + AI Stitcher turns local Sora/video folders into a private searchable library and export-ready stitch planner. The project uses a cloud dashboard plus a local connector so the browser never crawls the user's disk directly. The connector reads only approved folders, syncs structured metadata, and the app exposes a local Gemma 4 provider path through Ollama with `gemma4:e2b`.

## Demo

Narrated proof video: https://youtu.be/8uvVJT7DMls

YouTube playlist: https://www.youtube.com/playlist?list=PLO0_Bzcc_TnqmS-_ml_4Nm4ICSzroB6iy

The video shows:

- a fresh account being created
- the real connector running while live sync output is visible
- large Sora vault mode for approved folders with thousands of clips
- the final dashboard with synced device, root, and clip metadata
- the local Gemma 4 provider configured as `gemma4:e2b`
- input brief/transcript becoming Viral Stitch output JSON, timeline, captions, groove map, speed ramps, transitions, and stitched MP4 preview
- frame intelligence sampling video frames, saving understanding, grading clips, and iterating to a target score
- audio policy removing mismatched music/talking when needed, then normalizing, mastering, and replacing the video audio in one final MP4
- inline playback of the final generated mastered MP4 in the notebook

## Track Fit

- Main Track: complete working app, notebook, public repo, demo video, and YouTube publishing flow.
- Impact Track: privacy-first media workflows for educators, journalists, nonprofits, legal aid, disaster response, and accessibility teams.
- Special Technology Track: local Gemma/Ollama command layer, frame intelligence, audio policy/mastering, generated-video playback, and edge/cloud trust boundary.

## Contents

- `source/` - FastAPI app, browser UI, connector, storage, AI runtime, and config
- `gemma-4-good-hackathon-writeup.md` - submission writeup
- `sora-vault-gemma4-output-proof.mp4` - narrated demo video
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
