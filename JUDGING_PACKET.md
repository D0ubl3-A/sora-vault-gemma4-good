# Judge Fast Path

## Submission

- Kaggle notebook: https://www.kaggle.com/code/illagency/sora-vault-gemma4-good
- Demo video: https://youtu.be/8uvVJT7DMls
- YouTube playlist: https://www.youtube.com/playlist?list=PLO0_Bzcc_TnqmS-_ml_4Nm4ICSzroB6iy
- GitHub repo: https://github.com/D0ubl3-A/sora-vault-gemma4-good

## One-Sentence Impact

Sora Vault Cloud gives community impact teams cloud-style search over sensitive local media archives without forcing them to upload or surrender the whole archive first.

## Prize-Track Positioning

- Main Track: working product proof with UI, API, connector, notebook, generated MP4 playback, mastered audio replacement, and YouTube publishing.
- Impact Track: privacy-sensitive local media support for education, journalism, legal aid, nonprofits, disaster response, accessibility, and small teams.
- Special Technology Track: local Gemma/Ollama command layer, tool-style routing, frame intelligence, audio policy/mastering, edge/cloud trust boundary, and multimodal video/audio workflow.

## Why It Matters

The project is framed as a civic evidence vault for nonprofits, educators, journalists, disaster-response teams, legal aid groups, and small organizations with privacy-sensitive media. These teams often have local video archives but lack enterprise media infrastructure.

## What Is Real

- Fresh account flow
- FastAPI backend
- SQLite metadata store
- PBKDF2 password hashing
- session tokens
- device registration
- local connector
- approved-folder sync
- large Sora vault mode for thousands of approved local clips
- clip metadata extraction
- dashboard metrics
- plan-aware device/root limits
- Gemma/Ollama search, assistant command routing, Viral Stitch planning, and grading summaries
- optional Groq transcription for voice input only
- input/output Viral Stitch manifest with timeline, captions, groove map, transitions, and stitched MP4 preview
- frame-intelligence route that samples video frames, saves understanding, and iterates to a score
- Gemma-directed audio policy that removes mismatched music or distracting dialogue, normalizes/masters the final mix, and replaces the video audio in one final MP4
- notebook inline playback of the final generated mastered MP4

## Demo Proof

The narrated video shows a new account, the connector running with visible live output, and the final dashboard with synced device/root/clip metadata.

## Gemma Input/Output Evidence

Search route:

```json
{
  "endpoint": "POST /api/library/search",
  "body": {
    "query": "cleaned sample clips",
    "provider": "local_gemma",
    "local_model": "gemma4:e2b",
    "limit": 20
  }
}
```

Output shape:

```json
{
  "intent": {
    "keywords": ["sample"],
    "categories": ["cleaned"],
    "characters": [],
    "cleaned_filter": "only_cleaned",
    "summary": "Find cleaned sample clips in the synced archive."
  },
  "results": [
    {
      "title_text": "sample watermarked.cleaned",
      "relative_path": "cleaned/sample-watermarked.cleaned.mp4",
      "category": "cleaned",
      "looks_cleaned": true,
      "duration_sec": 3.0
    }
  ]
}
```

Assistant route:

```json
{
  "endpoint": "POST /api/assistant",
  "body": {
    "message": "Show devices and synced folders",
    "provider": "local_gemma",
    "state": {
      "signed_in": true,
      "plan_id": "starter"
    }
  }
}
```

Output shape:

```json
{
  "reply": "Here are the connected devices and synced folders for this library.",
  "command": "show_devices",
  "args": {}
}
```

Optional voice-input route:

```json
{
  "endpoint": "POST /api/voice/transcribe",
  "body": {
    "audio_base64": "<webm audio bytes, base64 encoded>",
    "mime_type": "audio/webm",
    "language": "en"
  },
  "model": "whisper-large-v3-turbo"
}
```

Output shape:

```json
{
  "text": "show devices and synced folders",
  "model": "whisper-large-v3-turbo"
}
```

## Gemma 4 Role

Gemma 4 is the local/private provider path. The model is given a bounded role: convert natural-language intent into JSON filters, UI commands, stitch plans, frame-scoring summaries, and export manifests, then let the application operate on real synced metadata. This reduces hallucination risk and supports offline/privacy-sensitive workflows. Groq is limited to optional speech-to-text for voice input.

## Production Hardening Path

- Enterprise scale: managed Postgres, worker queues, cloud preview/object storage, RBAC, SSO, audit logs, token rotation, tenant isolation.
- Advanced video: color grading, object detection, scene/shot detection, multi-track audio mixing, and deeper clip-selection models.
- Broad formats: ProRes, BRAW sidecars, XML/EDL/FCPXML, Adobe Premiere, DaVinci Resolve, and proxy workflows.
- Hybrid latency: keep private frame work local, cache summaries, queue massive archives, and sync previews/metadata before full upload.
