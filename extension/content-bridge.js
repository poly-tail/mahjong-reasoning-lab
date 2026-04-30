const BRIDGE_PROTOCOL_VERSION = "v4";
const PAGE_TO_EXTENSION = `TENHOU_UI_BRIDGE_FROM_PAGE_${BRIDGE_PROTOCOL_VERSION}`;
const EXTENSION_TO_PAGE = `TENHOU_UI_BRIDGE_TO_PAGE_${BRIDGE_PROTOCOL_VERSION}`;
const PAGE_REQUEST_TIMEOUT_MS = 3000;
const CONTENT_BRIDGE_INSTALLED_FLAG = "__TENHOU_UI_BRIDGE_CONTENT_INSTALLED_VERSION__";

if (window[CONTENT_BRIDGE_INSTALLED_FLAG] === BRIDGE_PROTOCOL_VERSION) {
  // Dynamic reinjection from the service worker must stay idempotent.
} else {
  window[CONTENT_BRIDGE_INSTALLED_FLAG] = BRIDGE_PROTOCOL_VERSION;

// This script intentionally stays in the isolated world. It should only relay commands between the
// extension runtime and the MAIN-world page bridge so page globals never leak into the extension side.
function ensureLocalBridgeConnection() {
  // Opening or reloading a Tenhou/mock page is a natural time to wake the MV3 service worker and
  // ask it to ensure the localhost WebSocket is connected. This keeps the documented
  // "app first -> page reload" flow reliable without requiring manual extension reload every time.
  try {
    chrome.runtime.sendMessage({ kind: "ENSURE_LOCAL_WS" }, () => {
      void chrome.runtime.lastError;
    });
  } catch (_error) {
    // If the runtime is momentarily unavailable during extension reload, the worker will still be
    // started by other lifecycle hooks. This warm-up call is best-effort only.
  }
}

function requestPage(payload, expectedKind, sendResponse) {
  const requestId = crypto.randomUUID();
  // Each extension request gets its own correlation id because multiple commands can be in-flight
  // while the page bridge still only communicates through window.postMessage.
  const timeoutId = setTimeout(() => {
    window.removeEventListener("message", handleMessage);
    sendResponse({
      ok: false,
      error: `PAGE_BRIDGE_TIMEOUT: ${expectedKind}`,
    });
  }, PAGE_REQUEST_TIMEOUT_MS);

  function handleMessage(event) {
    if (event.source !== window) {
      return;
    }
    const data = event.data;
    if (!data || data.type !== PAGE_TO_EXTENSION) {
      return;
    }
    const responsePayload = data.payload || {};
    if (responsePayload.requestId !== requestId || responsePayload.kind !== expectedKind) {
      return;
    }
    clearTimeout(timeoutId);
    window.removeEventListener("message", handleMessage);
    sendResponse(responsePayload.result ?? { ok: false, error: "EMPTY_PAGE_RESULT" });
  }

  window.addEventListener("message", handleMessage);
  // MAIN-world code owns all Tenhou globals and DOM details. This script only forwards envelopes.
  window.postMessage(
    {
      type: EXTENSION_TO_PAGE,
      payload: {
        ...payload,
        requestId,
      },
    },
    "*"
  );
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  // Keep the supported message surface explicit. The local app defines the command set, the
  // service worker forwards it, and this bridge only maps those known envelopes to page requests.
  if (message?.kind === "TENHOU_UI_SNAPSHOT") {
    requestPage({ kind: "GET_SNAPSHOT" }, "SNAPSHOT_RESULT", sendResponse);
    return true;
  }

  if (message?.kind === "TENHOU_EXECUTE") {
    // Command execution always stays data-driven: the isolated world does not decide how to click,
    // it only forwards the already-validated command payload into MAIN world.
    requestPage(
      {
        kind: "EXECUTE",
        command: message.command || {},
      },
      "EXECUTE_RESULT",
      sendResponse
    );
    return true;
  }

  return false;
});

ensureLocalBridgeConnection();
}
