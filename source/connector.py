from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import requests


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


def require_cv2():
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - local runtime guard
        raise RuntimeError(
            "OpenCV is required for the local connector. Install it with "
            "`py -3 -m pip install -r requirements-connector.txt`."
        ) from exc
    return cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync local Sora-style folders to Sora Vault Cloud.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8780", help="Base URL for the cloud API.")
    parser.add_argument("--email", required=True, help="Account email.")
    parser.add_argument("--password", default=None, help="Account password. Prefer --password-env for repeatable runs.")
    parser.add_argument(
        "--password-env",
        default="SORA_VAULT_PASSWORD",
        help="Environment variable containing the account password.",
    )
    parser.add_argument("--device-name", required=True, help="Human-friendly machine name.")
    parser.add_argument("--folders", nargs="+", required=True, help="One or more local folders to sync.")
    parser.add_argument("--interval-sec", type=int, default=0, help="Repeat sync every N seconds. 0 runs once.")
    parser.add_argument(
        "--state-file",
        default=str(Path(__file__).resolve().parent / "data" / "connector-state.json"),
        help="Path to the connector state file.",
    )
    parser.add_argument("--connector-version", default="1.0.0", help="Connector version label.")
    parser.add_argument("--chunk-size", type=int, default=400, help="Clip records per sync request.")
    args = parser.parse_args()
    if not args.password and not os.getenv(args.password_env):
        parser.error("Provide --password or set the environment variable named by --password-env.")
    return args


def normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def discover_videos(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            yield path


def format_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    from math import gcd

    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def parse_title_text(path: Path) -> str:
    text = path.stem
    for marker in ["-attachment-", "__", "_", "-"]:
        text = text.replace(marker, " ")
    return normalize_text(text)


def derive_category(root: Path, relative_path: Path) -> str:
    if len(relative_path.parts) >= 2:
        return relative_path.parts[0]
    return root.name


def derive_character(relative_path: Path) -> str:
    parts = list(relative_path.parts)
    if parts and parts[0] == "sora_v2_characters" and len(parts) >= 3:
        return normalize_text(parts[1].replace("_", " "))
    if parts and parts[0] == "sora_v2_cameos":
        return "cameo"
    if parts and parts[0] == "sora_v2_cameo_drafts":
        return "cameo draft"
    return ""


def inspect_video(path: Path) -> tuple[int | None, int | None, float | None, int | None, float | None]:
    cv2 = require_cv2()
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None, None, None, None, None
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0) or None
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0) or None
        duration_sec = round(frames / fps, 3) if fps and frames else None
        return width, height, round(fps, 3) if fps else None, frames, duration_sec
    finally:
        capture.release()


def build_clip(root: Path, path: Path) -> dict:
    relative_path = path.relative_to(root)
    width, height, fps, frames, duration_sec = inspect_video(path)
    category = derive_category(root, relative_path)
    character = derive_character(relative_path)
    title_text = parse_title_text(path)
    search_text = normalize_text(
        " ".join(
            [
                category.replace("_", " "),
                character,
                title_text,
                str(relative_path.parent).replace("\\", " ").replace("_", " "),
                path.name.replace("_", " "),
            ]
        )
    )
    stat = path.stat()
    source_hash = hashlib.sha1(
        f"{path.name}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()
    return {
        "relative_path": str(relative_path),
        "title_text": title_text or path.name,
        "category": category,
        "character": character,
        "filename": path.name,
        "extension": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 3),
        "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)),
        "width": width,
        "height": height,
        "fps": fps,
        "frames": frames,
        "duration_sec": duration_sec,
        "aspect_ratio": format_ratio(width, height),
        "looks_cleaned": ".cleaned." in path.name.lower() or "no watermarks" in str(root).lower(),
        "search_text": search_text,
        "source_hash": source_hash,
    }


def chunked(items: list[dict], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


class ConnectorClient:
    def __init__(self, api_url: str, email: str, password: str, device_name: str, connector_version: str, state_path: Path):
        self.api_url = api_url.rstrip("/")
        self.email = email
        self.password = password
        self.device_name = device_name
        self.connector_version = connector_version
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _session(self) -> str:
        response = requests.post(
            f"{self.api_url}/api/auth/login",
            json={"email": self.email, "password": self.password},
            timeout=60,
        )
        if response.status_code == 401:
            raise RuntimeError("Login failed. Create the account in the web app first, then rerun the connector.")
        response.raise_for_status()
        return response.json()["token"]

    def _device_token(self, session_token: str) -> str:
        saved = self.state.get("device_token")
        if saved:
            return saved
        response = requests.post(
            f"{self.api_url}/api/devices/register",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"device_name": self.device_name, "connector_version": self.connector_version},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        self.state["device_token"] = payload["device_token"]
        self.state["device_id"] = payload["device_id"]
        self._save_state()
        return payload["device_token"]

    def sync_folder(self, folder: Path, chunk_size: int) -> None:
        session_token = self._session()
        device_token = self._device_token(session_token)
        clips = [build_clip(folder, path) for path in discover_videos(folder)]
        if not clips:
            print(f"No clips found under {folder}", flush=True)
            return
        print(f"Syncing {len(clips)} clips from {folder}", flush=True)
        for index, clip_chunk in enumerate(chunked(clips, chunk_size)):
            response = requests.post(
                f"{self.api_url}/api/connectors/sync-root",
                headers={"X-Device-Token": device_token},
                json={
                    "device_token": device_token,
                    "label": folder.name,
                    "folder_path": str(folder),
                    "clips": clip_chunk,
                    "reset": index == 0,
                    "finalize": index == (len(clips) - 1) // chunk_size,
                },
                timeout=180,
            )
            response.raise_for_status()
            print(f"  uploaded chunk {index + 1} with {len(clip_chunk)} clips", flush=True)


def run_sync(args: argparse.Namespace) -> int:
    password = args.password or os.getenv(args.password_env, "")
    client = ConnectorClient(
        api_url=args.api_url,
        email=args.email,
        password=password,
        device_name=args.device_name,
        connector_version=args.connector_version,
        state_path=Path(args.state_file).expanduser().resolve(),
    )
    folders = [Path(folder).expanduser().resolve() for folder in args.folders]
    for folder in folders:
        if not folder.exists():
            raise SystemExit(f"Folder does not exist: {folder}")
    while True:
        for folder in folders:
            client.sync_folder(folder, args.chunk_size)
        if args.interval_sec <= 0:
            break
        print(f"Sleeping {args.interval_sec} seconds before next sync cycle.", flush=True)
        time.sleep(args.interval_sec)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_sync(parse_args()))
