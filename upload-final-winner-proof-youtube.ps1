$ErrorActionPreference = "Stop"

$videoPath = "C:\Users\aaron\.barz\artifacts\gemma4-submit-video\sora-vault-gemma4-final-winner-proof-mastered.mp4"
$tokenPath = "C:\Users\aaron\.barz\artifacts\youtube-schedule\token.json"
$secretPath = "C:\Users\aaron\.barz\secrets\youtube-client-secret.json"
$playlistId = "PLO0_Bzcc_TnqmS-_ml_4Nm4ICSzroB6iy"

$token = Get-Content $tokenPath -Raw | ConvertFrom-Json
$secret = Get-Content $secretPath -Raw | ConvertFrom-Json
$client = $secret.installed

$fresh = Invoke-RestMethod -Method Post -Uri $client.token_uri -Body @{
  client_id = $client.client_id
  client_secret = $client.client_secret
  refresh_token = $token.refresh_token
  grant_type = "refresh_token"
}
$accessToken = $fresh.access_token
$authHeaders = @{ Authorization = "Bearer $accessToken" }

$description = @"
Sora Vault + AI Stitcher is a Gemma-first AI video system for the Gemma 4 Good Hackathon.

This corrected narrated proof shows the actual product working:
- Fresh account creation
- Real local connector syncing approved Sora/video folders
- Live connector output while it is working
- Final dashboard with synced device, root, and clip metadata
- Gemma/Ollama command paths for search, assistant routing, stitch planning, frame summaries, grading, and export planning
- Viral Stitch input data and output manifest
- Timeline cards, captions, groove map, speed ramps, fades/dissolves, title system, and generated stitched MP4 playback
- Frame intelligence that samples video frames, saves understanding, grades clips, and iterates to a perfect-score export plan
- Gemma-directed audio policy that mutes mismatched music, ducks or removes distracting commercial/dialogue audio, prevents clipping, normalizes loudness, masters the final mix, and replaces the video audio with the mastered system output
- YouTube publishing flow that uploads this final mastered MP4, applies metadata, and places it into a playlist

Groq is used only as an optional voice input/transcription lane. The core intelligence path is Gemma 4 through Ollama, currently configured as gemma4:e2b.

Why it matters:
Nonprofits, educators, journalists, legal aid groups, disaster response teams, and creators often have sensitive media trapped in local folders. Sora Vault gives them cloud-style search, frame understanding, and AI stitch planning without forcing them to upload the whole archive first.

Prize-track fit:
- Main Track: complete working product proof with UI, API, connector, notebook, generated MP4 playback, mastered audio replacement, public repo, and YouTube publishing.
- Impact Track: privacy-first local media workflows for educators, journalists, nonprofits, disaster response teams, legal aid groups, and accessibility teams.
- Special Technology Track: local Gemma/Ollama command layer, frame intelligence, audio policy/mastering, edge/cloud trust boundary, and multimodal video/audio workflow.

Kaggle notebook:
https://www.kaggle.com/code/illagency/sora-vault-gemma4-good

GitHub:
https://github.com/D0ubl3-A/sora-vault-gemma4-good

#Gemma4 #Gemma4Good #SoraVault #AIStitcher #LocalAI #Ollama #AIVideo #ViralStitch #PrivacyAI #CivicTech #AIForGood #Hackathon
"@

$metadata = @{
  snippet = @{
    title = "Sora Vault + AI Stitcher: Gemma 4 Turns Local Clips Into Viral Evidence Cuts"
    description = $description
    tags = @(
      "Gemma 4",
      "Gemma 4 Good",
      "Sora Vault",
      "AI Stitcher",
      "AI for Good",
      "local AI",
      "Ollama",
      "AI video",
      "viral stitch",
      "privacy AI",
      "civic tech",
      "journalism tools",
      "nonprofit tools",
      "frame intelligence",
      "hackathon"
    )
    categoryId = "28"
  }
  status = @{
    privacyStatus = "public"
    selfDeclaredMadeForKids = $false
  }
} | ConvertTo-Json -Depth 8

$videoLength = (Get-Item $videoPath).Length
$initResponse = Invoke-WebRequest `
  -Method Post `
  -Uri "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status" `
  -Headers ($authHeaders + @{
    "Content-Type" = "application/json; charset=UTF-8"
    "X-Upload-Content-Type" = "video/mp4"
    "X-Upload-Content-Length" = $videoLength
  }) `
  -Body $metadata

$uploadUrl = $initResponse.Headers.Location
if (-not $uploadUrl) {
  throw "YouTube did not return a resumable upload URL."
}

$bytes = [System.IO.File]::ReadAllBytes($videoPath)
$result = Invoke-RestMethod `
  -Method Put `
  -Uri $uploadUrl `
  -Headers ($authHeaders + @{
    "Content-Type" = "video/mp4"
    "Content-Length" = $videoLength
  }) `
  -Body $bytes

$videoId = $result.id
if (-not $videoId) {
  throw "Upload completed without a video id."
}

$playlistItemPayload = @{
  snippet = @{
    playlistId = $playlistId
    resourceId = @{
      kind = "youtube#video"
      videoId = $videoId
    }
  }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod `
  -Method Post `
  -Uri "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet" `
  -Headers ($authHeaders + @{ "Content-Type" = "application/json" }) `
  -Body $playlistItemPayload | Out-Null

$out = @{
  video_id = $videoId
  video_url = "https://youtu.be/$videoId"
  playlist_id = $playlistId
  playlist_url = "https://www.youtube.com/playlist?list=$playlistId"
  privacy = "public"
  uploaded_at = (Get-Date).ToString("o")
  title = "Sora Vault + AI Stitcher: Gemma 4 Turns Local Clips Into Viral Evidence Cuts"
}

$out | ConvertTo-Json -Depth 6 | Set-Content "C:\Users\aaron\.barz\artifacts\gemma4-submit-video\youtube-final-winner-proof-result.json"
$out | ConvertTo-Json -Depth 6
