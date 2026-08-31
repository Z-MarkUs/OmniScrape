"use strict";

const form = document.querySelector("#extract-form");
const result = document.querySelector("#result code");
const submitButton = document.querySelector("#submit-button");
const requestState = document.querySelector("#request-state");
const copyButton = document.querySelector("#copy-button");
const timing = document.querySelector("#timing");
const mode = document.querySelector("#mode");
const render = document.querySelector("#render");
const renderHelp = document.querySelector("#render-help");
const warningCopy = document.querySelector("#warning-copy");
let latestJson = "";

function renderJson(value) {
  latestJson = JSON.stringify(value, null, 2);
  result.textContent = latestJson;
  copyButton.disabled = false;
}

function updateWarning() {
  const notes = ["The server will request the trusted, authorized public URL above."];
  if (render.checked) {
    notes.push("Browser mode executes target JavaScript; use it only for trusted, authorized targets in an externally resource-limited deployment.");
  }
  if (mode.value === "llm") {
    notes.push("AI mode sends the fetched page content to the configured provider and may incur usage charges.");
  } else if (mode.value === "auto") {
    notes.push("Auto mode may send page content to the configured AI provider—and incur usage charges—when local completeness is low.");
  }
  warningCopy.textContent = notes.join(" ");
}

function setRendererCapability(status, help, available) {
  const rendererStatus = document.querySelector("#renderer-status");
  const renderLabel = render.closest(".switch-label");
  render.disabled = !available;
  if (!available) render.checked = false;
  renderLabel.classList.toggle("is-disabled", !available);
  renderHelp.textContent = help;
  rendererStatus.textContent = status;
  rendererStatus.classList.remove("ok", "off");
  rendererStatus.classList.add(available ? "ok" : "off");
  updateWarning();
}

async function checkHealth() {
  const service = document.querySelector("#service-status");
  const llm = document.querySelector("#llm-status");
  try {
    const response = await fetch("/health", { headers: { "Accept": "application/json" } });
    if (!response.ok) throw new Error("Health request failed");
    const health = await response.json();
    service.textContent = "Service online";
    service.classList.add("ok");
    if (health.llm_available) {
      llm.textContent = "AI fallback ready";
      llm.classList.add("ok");
    } else if (health.llm_configured) {
      llm.textContent = "AI SDK unavailable";
      llm.classList.add("off");
    } else {
      llm.textContent = "AI fallback off";
      llm.classList.add("off");
    }
    if (!health.renderer_enabled) {
      setRendererCapability(
        "Browser rendering disabled",
        "Disabled by the server's API policy.",
        false,
      );
    } else if (health.renderer_available) {
      setRendererCapability(
        "Browser renderer ready",
        "Trusted, authorized targets only; rendering uses additional compute.",
        true,
      );
    } else {
      setRendererCapability(
        "Browser renderer unavailable",
        "Enabled by policy, but the browser runtime is not ready.",
        false,
      );
    }
    document.querySelector("#version").textContent = `v${health.version}`;
  } catch (_) {
    service.textContent = "Service unavailable";
    service.classList.add("off");
    llm.textContent = "AI status unavailable";
    setRendererCapability(
      "Renderer status unavailable",
      "Rendering stays disabled until the server policy can be verified.",
      false,
    );
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const started = performance.now();
  const apiKey = document.querySelector("#api-key").value;
  const payload = {
    url: document.querySelector("#url").value,
    kind: new FormData(form).get("kind"),
    mode: mode.value,
    render: render.checked,
  };
  const headers = { "Content-Type": "application/json", "Accept": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  submitButton.disabled = true;
  requestState.textContent = "Extracting…";
  requestState.className = "request-state working";
  timing.textContent = "Request in progress…";
  try {
    const response = await fetch("/v1/extract", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    let body;
    try {
      body = await response.json();
    } catch (_) {
      body = { success: false, error: { code: "invalid_response", message: "The server returned a non-JSON response." } };
    }
    renderJson(body);
    requestState.textContent = response.ok ? "Complete" : `Error ${response.status}`;
    requestState.className = response.ok ? "request-state" : "request-state error";
    timing.textContent = `${Math.round(performance.now() - started)} ms round trip · HTTP ${response.status}`;
  } catch (_) {
    renderJson({ success: false, error: { code: "network_error", message: "The service could not be reached." } });
    requestState.textContent = "Network error";
    requestState.className = "request-state error";
    timing.textContent = `${Math.round(performance.now() - started)} ms before failure`;
  } finally {
    submitButton.disabled = false;
  }
});

copyButton.addEventListener("click", async () => {
  if (!latestJson) return;
  try {
    await navigator.clipboard.writeText(latestJson);
    copyButton.textContent = "Copied";
    window.setTimeout(() => { copyButton.textContent = "Copy JSON"; }, 1400);
  } catch (_) {
    copyButton.textContent = "Copy failed";
  }
});

mode.addEventListener("change", updateWarning);
render.addEventListener("change", updateWarning);
updateWarning();
checkHealth();
