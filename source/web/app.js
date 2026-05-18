const state = {
  token: localStorage.getItem("soraVaultCloudToken") || "",
  user: null,
  dashboard: null,
  providers: [],
  plans: [],
  ttsEnabled: true,
  recorder: null,
  stream: null,
  chunks: [],
};

const el = {
  sessionStatus: document.getElementById("session-status"),
  providerStatus: document.getElementById("provider-status"),
  heroMetrics: document.getElementById("hero-metrics"),
  registerForm: document.getElementById("register-form"),
  loginForm: document.getElementById("login-form"),
  authMessage: document.getElementById("auth-message"),
  plansGrid: document.getElementById("plans-grid"),
  dashboardStats: document.getElementById("dashboard-stats"),
  devicesList: document.getElementById("devices-list"),
  rootsList: document.getElementById("roots-list"),
  searchForm: document.getElementById("search-form"),
  searchQuery: document.getElementById("search-query"),
  providerSelect: document.getElementById("provider-select"),
  localModel: document.getElementById("local-model"),
  searchIntent: document.getElementById("search-intent"),
  searchResults: document.getElementById("search-results"),
  assistantLog: document.getElementById("assistant-log"),
  assistantForm: document.getElementById("assistant-form"),
  assistantMessage: document.getElementById("assistant-message"),
  assistantStatus: document.getElementById("assistant-status"),
  recordButton: document.getElementById("record-button"),
  stopButton: document.getElementById("stop-button"),
  connectorCommand: document.getElementById("connector-command"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Request failed");
  }
  return data;
}

function addAssistant(role, text) {
  const div = document.createElement("div");
  div.className = "assistant-item";
  div.innerHTML = `<strong>${escapeHtml(role)}</strong><div>${escapeHtml(text)}</div>`;
  el.assistantLog.appendChild(div);
  el.assistantLog.scrollTop = el.assistantLog.scrollHeight;
}

function speak(text) {
  if (!("speechSynthesis" in window) || !state.ttsEnabled) {
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.03;
  window.speechSynthesis.speak(utterance);
}

function renderProviders() {
  el.providerSelect.innerHTML = state.providers
    .map(
      (provider) =>
        `<option value="${escapeHtml(provider.id)}">${escapeHtml(provider.label)} (${escapeHtml(provider.default_model)})</option>`,
    )
    .join("");
  el.providerStatus.textContent = state.providers.length ? `${state.providers[0].label} first` : "Provider unavailable";
}

function renderHero() {
  if (!state.dashboard) {
    el.heroMetrics.innerHTML = "";
    return;
  }
  const summary = state.dashboard.summary || {};
  el.heroMetrics.innerHTML = [
    { label: "Clips", value: summary.clip_count || 0 },
    { label: "Roots", value: summary.root_count || 0 },
    { label: "Devices", value: summary.device_count || 0 },
    { label: "Plan", value: state.user?.plan_id || "starter" },
  ]
    .map(
      (item) =>
        `<div class="metric"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>`,
    )
    .join("");
}

function renderPlans() {
  el.plansGrid.innerHTML = state.plans
    .map(
      (plan) => `
        <article class="plan">
          <p class="eyebrow">${escapeHtml(plan.name)}</p>
          <h3>${escapeHtml(plan.description)}</h3>
          <div class="plan__price">${escapeHtml(plan.monthly_price_label)}</div>
          <div class="plan__features">
            ${plan.features.map((feature) => `<span>${escapeHtml(feature)}</span>`).join("")}
            <span>${escapeHtml(`${plan.device_limit} device limit`)}</span>
            <span>${escapeHtml(`${plan.root_limit} root limit`)}</span>
          </div>
          <button data-plan="${escapeHtml(plan.plan_id)}" ${plan.checkout_ready ? "" : "disabled"}>${plan.checkout_ready ? "Subscribe" : "Billing disabled"}</button>
        </article>
      `,
    )
    .join("");
}

function renderDashboard() {
  if (!state.dashboard) {
    return;
  }
  const summary = state.dashboard.summary || {};
  el.dashboardStats.innerHTML = [
    `Online clips: ${summary.clip_count || 0}`,
    `Synced roots: ${summary.root_count || 0}`,
    `Connected devices: ${summary.device_count || 0}`,
    `Stored bytes: ${summary.total_bytes || 0}`,
  ]
    .map((text) => `<span class="pill pill--muted">${escapeHtml(text)}</span>`)
    .join("");

  el.devicesList.innerHTML = (state.dashboard.devices || [])
    .map(
      (device) => `
        <div class="card">
          <strong>${escapeHtml(device.device_name)}</strong>
          <div class="card__meta">
            <span>${escapeHtml(device.connector_version)}</span>
            <span>Last seen ${escapeHtml(device.last_seen_at)}</span>
          </div>
        </div>
      `,
    )
    .join("");

  el.rootsList.innerHTML = (state.dashboard.roots || [])
    .map(
      (root) => `
        <div class="card">
          <strong>${escapeHtml(root.label)}</strong>
          <div class="card__meta">
            <span>${escapeHtml(`${root.clip_count} clips`)}</span>
            <span>${escapeHtml(root.device_name)}</span>
          </div>
          <div class="card__meta"><span>${escapeHtml(root.folder_path)}</span></div>
        </div>
      `,
    )
    .join("");
}

function renderConnectorCommand() {
  const email = state.user?.email || "you@example.com";
  el.connectorCommand.textContent =
    `$env:ILL_MOTION_PASSWORD = "YOUR_PASSWORD"\n` +
    `py -3 connector.py ` +
    `--api-url ${window.location.origin} ` +
    `--email "${email}" ` +
    `--password-env ILL_MOTION_PASSWORD ` +
    `--device-name "My Desktop" ` +
    `--folders "D:\\AI-Archive" "D:\\Generated-Video"`;
}

async function loadHealth() {
  const data = await api("/api/health");
  state.providers = data.providers || [];
  state.plans = data.plans || [];
  renderProviders();
  renderPlans();
}

async function loadMe() {
  if (!state.token) {
    el.sessionStatus.textContent = "Signed out";
    return;
  }
  const data = await api("/api/me", { headers: authHeaders() });
  state.user = data.user;
  state.dashboard = data.dashboard;
  state.providers = data.providers;
  state.plans = data.plans;
  el.sessionStatus.textContent = `${state.user.display_name} | ${state.user.plan_id}`;
  renderProviders();
  renderPlans();
  renderHero();
  renderDashboard();
  renderConnectorCommand();
}

async function handleAuth(path, form) {
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  const data = await api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.token = data.token;
  localStorage.setItem("soraVaultCloudToken", state.token);
  el.authMessage.textContent = `${data.user.email} is signed in.`;
  await loadMe();
}

async function searchLibrary(query) {
  const provider = el.providerSelect.value || "groq";
  const payload = await api("/api/library/search", {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit: 20,
      provider,
      local_model: el.localModel.value.trim() || null,
    }),
  });
  el.searchIntent.innerHTML = [
    ...(payload.intent.keywords || []),
    ...(payload.intent.categories || []),
    ...(payload.intent.characters || []),
    payload.intent.cleaned_filter || "any",
  ]
    .filter(Boolean)
    .map((value) => `<span class="pill pill--muted">${escapeHtml(value)}</span>`)
    .join("");
  el.searchResults.innerHTML = (payload.results || [])
    .map(
      (clip) => `
        <div class="result">
          <strong>${escapeHtml(clip.title_text)}</strong>
          <div class="result__meta">
            <span>${escapeHtml(clip.category || "uncategorized")}</span>
            <span>${escapeHtml(clip.character || "-")}</span>
            <span>${escapeHtml(clip.relative_path)}</span>
            <span>${escapeHtml(`score ${clip.score}`)}</span>
          </div>
        </div>
      `,
    )
    .join("");
}

async function askAssistant(message) {
  const provider = el.providerSelect.value || "groq";
  addAssistant("You", message);
  el.assistantStatus.textContent = "Thinking...";
  const payload = await api("/api/assistant", {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      provider,
      local_model: el.localModel.value.trim() || null,
      state: {
        signed_in: Boolean(state.user),
        plan_id: state.user?.plan_id || "starter",
      },
    }),
  });
  addAssistant("Atlas", payload.reply);
  speak(payload.reply);
  el.assistantStatus.textContent = "Mic idle";
  if (payload.command === "search_library" && payload.args?.query) {
    el.searchQuery.value = payload.args.query;
    await searchLibrary(payload.args.query);
  } else if (payload.command === "show_devices") {
    window.scrollTo({ top: document.querySelector(".dashboard").offsetTop - 20, behavior: "smooth" });
  } else if (payload.command === "show_billing") {
    window.scrollTo({ top: document.querySelector(".plans").offsetTop - 20, behavior: "smooth" });
  } else if (payload.command === "show_connector_help") {
    window.scrollTo({ top: document.querySelector(".connector").offsetTop - 20, behavior: "smooth" });
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const parts = String(reader.result || "").split(",", 2);
      resolve(parts[1] || "");
    };
    reader.onerror = () => reject(new Error("Could not read microphone recording."));
    reader.readAsDataURL(blob);
  });
}

async function startRecording() {
  state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.chunks = [];
  state.recorder = new MediaRecorder(state.stream);
  state.recorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
      state.chunks.push(event.data);
    }
  };
  state.recorder.onstop = async () => {
    try {
      const blob = new Blob(state.chunks, { type: state.recorder.mimeType || "audio/webm" });
      const audioBase64 = await blobToBase64(blob);
      const payload = await api("/api/voice/transcribe", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ audio_base64: audioBase64, mime_type: blob.type || "audio/webm", language: "en" }),
      });
      if (payload.text) {
        await askAssistant(payload.text);
      }
    } catch (error) {
      el.assistantStatus.textContent = error.message;
    } finally {
      state.stream.getTracks().forEach((track) => track.stop());
      state.recorder = null;
      el.recordButton.disabled = false;
      el.stopButton.disabled = true;
    }
  };
  state.recorder.start();
  el.assistantStatus.textContent = "Recording...";
  el.recordButton.disabled = true;
  el.stopButton.disabled = false;
}

function stopRecording() {
  if (state.recorder && state.recorder.state !== "inactive") {
    state.recorder.stop();
  }
}

async function createCheckout(planId) {
  const payload = await api("/api/billing/checkout-session", {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({
      plan_id: planId,
      success_url: `${window.location.origin}/?checkout=success`,
      cancel_url: `${window.location.origin}/?checkout=cancelled`,
    }),
  });
  window.location.href = payload.checkout_url;
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-plan]");
  if (button) {
    if (button.disabled) {
      el.authMessage.textContent = "Billing is controlled by the server owner and is not enabled on this deployment yet.";
      return;
    }
    if (!state.token) {
      el.authMessage.textContent = "Sign in before starting a subscription.";
      return;
    }
    try {
      await createCheckout(button.dataset.plan);
    } catch (error) {
      el.authMessage.textContent = error.message;
    }
  }
});

el.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth("/api/auth/register", el.registerForm);
  } catch (error) {
    el.authMessage.textContent = error.message;
  }
});

el.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await handleAuth("/api/auth/login", el.loginForm);
  } catch (error) {
    el.authMessage.textContent = error.message;
  }
});

el.searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.token) {
    el.authMessage.textContent = "Sign in before searching the library.";
    return;
  }
  try {
    await searchLibrary(el.searchQuery.value.trim());
  } catch (error) {
    el.searchResults.innerHTML = `<div class="result">${escapeHtml(error.message)}</div>`;
  }
});

el.assistantForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.token) {
    el.authMessage.textContent = "Sign in before using the assistant.";
    return;
  }
  try {
    const message = el.assistantMessage.value.trim();
    if (!message) {
      return;
    }
    el.assistantMessage.value = "";
    await askAssistant(message);
  } catch (error) {
    el.assistantStatus.textContent = error.message;
  }
});

el.recordButton.addEventListener("click", async () => {
  try {
    await startRecording();
  } catch (error) {
    el.assistantStatus.textContent = error.message;
  }
});

el.stopButton.addEventListener("click", () => stopRecording());

async function init() {
  await loadHealth();
  if (state.token) {
    try {
      await loadMe();
    } catch (error) {
      localStorage.removeItem("soraVaultCloudToken");
      state.token = "";
      el.authMessage.textContent = error.message;
    }
  }
  renderConnectorCommand();
  addAssistant("Atlas", "Ready to onboard devices, search the library, and start subscriptions.");
}

init().catch((error) => {
  el.authMessage.textContent = error.message;
});
