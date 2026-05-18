from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import DEFAULT_HOST, DEFAULT_PORT, PLAN_CATALOG, WEB_DIR, ensure_data_dir, settings
from groq_runtime import AiRuntime
from security import hash_password, validate_email, verify_password, verify_stripe_signature
from shared_models import (
    AssistantRequest,
    BillingCheckoutRequest,
    DeviceRegisterRequest,
    LoginRequest,
    RegisterRequest,
    RootSyncRequest,
    SearchRequest,
    VoiceTranscriptionRequest,
)
from storage import Storage


ensure_data_dir()
storage = Storage()
ai_runtime = AiRuntime()
app = FastAPI(title="iLL Motion", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _strip_bearer(token: str | None) -> str | None:
    if not token:
        return None
    value = token.strip()
    if value.lower().startswith("bearer "):
        return value.split(" ", 1)[1].strip()
    return value


def current_user(authorization: str | None = Header(default=None)) -> dict:
    token = _strip_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing session token.")
    user = storage.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
    return user


def current_device(device_token: str | None = Header(default=None, alias="X-Device-Token")) -> dict:
    token = _strip_bearer(device_token) or device_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing device token.")
    device = storage.get_device_by_token(token)
    if not device:
        raise HTTPException(status_code=401, detail="Device token is invalid.")
    storage.touch_device(device["id"])
    return device


def serialize_user(user: dict) -> dict:
    plan_id = user.get("plan_id") or "starter"
    subscription_status = user.get("subscription_status") or "inactive"
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "plan_id": plan_id,
        "subscription_status": subscription_status,
        "current_period_end": user.get("current_period_end"),
    }


def current_plan(user: dict) -> Any:
    return PLAN_CATALOG.get(user.get("plan_id") or "starter", PLAN_CATALOG["starter"])


def serialize_plan(plan: Any) -> dict:
    return {
        "plan_id": plan.plan_id,
        "name": plan.name,
        "description": plan.description,
        "monthly_price_label": plan.monthly_price_label,
        "features": list(plan.features),
        "device_limit": plan.device_limit,
        "root_limit": plan.root_limit,
        "checkout_ready": bool(plan.stripe_price_id and settings.stripe_secret_key),
    }


def provider_failure(exc: Exception) -> HTTPException:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is not None:
            try:
                payload = response.json()
                detail = payload.get("error") or payload.get("detail") or response.text
            except ValueError:
                detail = response.text or str(exc)
            return HTTPException(status_code=502, detail=f"AI provider error: {detail}")
    if isinstance(exc, (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError)):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail="Unexpected provider failure.")


def billing_checkout_session(user: dict, request: BillingCheckoutRequest) -> dict:
    if request.plan_id not in PLAN_CATALOG:
        raise HTTPException(status_code=400, detail="Unknown plan.")
    plan = PLAN_CATALOG[request.plan_id]
    if not settings.stripe_secret_key or not plan.stripe_price_id:
        raise HTTPException(
            status_code=503,
            detail="Billing is not enabled on this deployment yet. Stripe stays in server environment variables only.",
        )

    stripe_headers = {"Authorization": f"Bearer {settings.stripe_secret_key}"}
    stripe_customer_id = user.get("stripe_customer_id")
    if not stripe_customer_id:
        customer_response = requests.post(
            "https://api.stripe.com/v1/customers",
            headers=stripe_headers,
            data={"email": user["email"], "name": user["display_name"]},
            timeout=60,
        )
        try:
            customer_response.raise_for_status()
        except requests.HTTPError as exc:
            raise provider_failure(exc) from exc
        customer_payload = customer_response.json()
        stripe_customer_id = customer_payload["id"]
        storage.set_stripe_customer_id(user["id"], stripe_customer_id)

    checkout_response = requests.post(
        "https://api.stripe.com/v1/checkout/sessions",
        headers=stripe_headers,
        data={
            "mode": "subscription",
            "customer": stripe_customer_id,
            "success_url": request.success_url,
            "cancel_url": request.cancel_url,
            "line_items[0][price]": plan.stripe_price_id,
            "line_items[0][quantity]": "1",
            "allow_promotion_codes": "true",
            "metadata[user_id]": user["id"],
            "metadata[plan_id]": request.plan_id,
        },
        timeout=60,
    )
    try:
        checkout_response.raise_for_status()
    except requests.HTTPError as exc:
        raise provider_failure(exc) from exc
    payload = checkout_response.json()
    return {"checkout_url": payload["url"], "session_id": payload["id"]}


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "providers": ai_runtime.available_providers(),
        "plans": [serialize_plan(plan) for plan in PLAN_CATALOG.values()],
    }


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict:
    email = validate_email(payload.email)
    if storage.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account already exists for that email.")
    password_hash = hash_password(payload.password)
    user = storage.create_user(email=email, display_name=payload.display_name.strip(), password_hash=password_hash)
    token = storage.create_session(user["id"], settings.session_ttl_hours)
    return {"token": token, "user": serialize_user(storage.get_user(user["id"]))}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    email = validate_email(payload.email)
    user = storage.get_user_by_email(email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    token = storage.create_session(user["id"], settings.session_ttl_hours)
    return {"token": token, "user": serialize_user(storage.get_user(user["id"]))}


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    dashboard = storage.get_dashboard(user["id"])
    return {
        "user": serialize_user(user),
        "dashboard": dashboard,
        "providers": ai_runtime.available_providers(),
        "plans": [serialize_plan(plan) for plan in PLAN_CATALOG.values()],
    }


@app.post("/api/devices/register")
def register_device(payload: DeviceRegisterRequest, user: dict = Depends(current_user)) -> dict:
    plan = current_plan(user)
    existing_device = storage.get_device_by_user_and_name(user["id"], payload.device_name.strip())
    if not existing_device and storage.count_devices(user["id"]) >= plan.device_limit:
        raise HTTPException(
            status_code=403,
            detail=f"{plan.name} allows {plan.device_limit} device(s). Upgrade to connect another machine.",
        )
    device = storage.register_device(
        user_id=user["id"],
        device_name=payload.device_name.strip(),
        connector_version=payload.connector_version,
    )
    return device


@app.post("/api/connectors/sync-root")
def sync_root(payload: RootSyncRequest, device: dict = Depends(current_device)) -> dict:
    if payload.device_token != device["device_token"]:
        raise HTTPException(status_code=401, detail="Device token payload does not match the authenticated device.")
    user = storage.get_user(device["user_id"])
    plan = current_plan(user)
    existing_root = storage.get_root_by_device_and_path(device["id"], payload.folder_path)
    if not existing_root and storage.count_roots(device["user_id"]) >= plan.root_limit:
        raise HTTPException(
            status_code=403,
            detail=f"{plan.name} allows {plan.root_limit} synced folder(s). Upgrade to add another root.",
        )
    root_id = storage.upsert_library_root(
        user_id=device["user_id"],
        device_id=device["id"],
        label=payload.label,
        folder_path=payload.folder_path,
    )
    if payload.reset:
        storage.clear_root_clips(root_id)
    storage.insert_clips(device["user_id"], device["id"], root_id, [clip.model_dump() for clip in payload.clips])
    return {"ok": True, "root_id": root_id, "clip_count": len(payload.clips), "finalize": payload.finalize}


@app.post("/api/library/search")
def search_library(payload: SearchRequest, user: dict = Depends(current_user)) -> dict:
    dashboard = storage.get_dashboard(user["id"])
    categories = dashboard.get("categories", [])
    characters = dashboard.get("characters", [])
    try:
        intent = ai_runtime.parse_search_query(
            payload.query,
            categories=categories,
            characters=characters,
            provider=payload.provider,
            local_model=payload.local_model,
        )
    except Exception as exc:  # pragma: no cover - surfaced to client for operator visibility
        raise provider_failure(exc) from exc
    keywords = [str(value).strip().lower() for value in intent.get("keywords", []) if str(value).strip()]
    category_filters = [value for value in intent.get("categories", []) if isinstance(value, str)]
    character_filters = [value for value in intent.get("characters", []) if isinstance(value, str)]
    cleaned_filter = str(intent.get("cleaned_filter", "any"))
    results = storage.search_clips(
        user["id"],
        keywords=keywords,
        categories=category_filters,
        characters=character_filters,
        cleaned_filter=cleaned_filter,
        limit=payload.limit,
    )
    return {
        "provider": payload.provider,
        "intent": intent,
        "results": results,
    }


@app.post("/api/assistant")
def assistant(payload: AssistantRequest, user: dict = Depends(current_user)) -> dict:
    commands = [
        {"name": "search_library", "description": "Run a library search.", "parameters": {"query": "search text"}},
        {"name": "show_billing", "description": "Open plan and billing information.", "parameters": {}},
        {"name": "show_devices", "description": "Show connected devices and synced roots.", "parameters": {}},
        {"name": "show_connector_help", "description": "Explain how to connect a local machine.", "parameters": {}},
    ]
    try:
        response = ai_runtime.route_assistant(
            payload.message,
            commands=commands,
            state=payload.state,
            provider=payload.provider,
            local_model=payload.local_model,
        )
    except Exception as exc:  # pragma: no cover - surfaced to client for operator visibility
        raise provider_failure(exc) from exc
    if "reply" not in response:
        response["reply"] = "I can help with billing, device setup, and library search."
    if "command" not in response:
        response["command"] = ""
    if "args" not in response or not isinstance(response["args"], dict):
        response["args"] = {}
    return response


@app.post("/api/voice/transcribe")
def voice_transcribe(payload: VoiceTranscriptionRequest, user: dict = Depends(current_user)) -> dict:
    try:
        return ai_runtime.transcribe_audio(payload.audio_base64, payload.mime_type, payload.language)
    except Exception as exc:  # pragma: no cover - surfaced to client for operator visibility
        raise provider_failure(exc) from exc


@app.post("/api/billing/checkout-session")
def create_checkout(payload: BillingCheckoutRequest, user: dict = Depends(current_user)) -> dict:
    return billing_checkout_session(user, payload)


@app.post("/api/billing/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    if not verify_stripe_signature(payload, signature, settings.stripe_webhook_secret):
        raise HTTPException(status_code=400, detail="Webhook signature could not be verified.")
    event = json.loads(payload.decode("utf-8"))
    event_type = event.get("type", "")
    data_object = event.get("data", {}).get("object", {})
    customer_id = data_object.get("customer")
    user = storage.get_user_by_stripe_customer(customer_id) if customer_id else None
    if user and event_type in {"checkout.session.completed", "customer.subscription.updated", "customer.subscription.created"}:
        metadata = data_object.get("metadata", {}) if isinstance(data_object.get("metadata", {}), dict) else {}
        plan_id = metadata.get("plan_id") or PLAN_CATALOG["starter"].plan_id
        subscription_id = data_object.get("subscription") or data_object.get("id")
        price_id = None
        items = data_object.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
        current_period_end = None
        if data_object.get("current_period_end"):
            current_period_end = str(data_object["current_period_end"])
        storage.set_subscription(
            user["id"],
            plan_id=plan_id,
            status="active",
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id,
            current_period_end=current_period_end,
        )
    elif user and event_type in {"customer.subscription.deleted"}:
        storage.set_subscription(
            user["id"],
            plan_id="starter",
            status="canceled",
            stripe_subscription_id=data_object.get("id"),
            stripe_price_id=None,
            current_period_end=None,
        )
    return JSONResponse({"received": True})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(WEB_DIR / "app.js")


@app.get("/styles.css")
def styles_css() -> FileResponse:
    return FileResponse(WEB_DIR / "styles.css")


if __name__ == "__main__":
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)
