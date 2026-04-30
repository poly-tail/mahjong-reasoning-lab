const DEFAULT_WS_URL = "ws://127.0.0.1:8765";
const RECONNECT_MS = 1500;
const TARGET_TAB_CACHE_MS = 10000;
const PRIMARY_TARGET_HOST_PREFIXES = ["https://tenhou.net/", "https://ron2.jp/"];
const MOCK_TARGET_HOST_PREFIXES = ["http://127.0.0.1/", "http://localhost/"];
// The service worker is transport-only by design. It receives already-decided commands from the
// local visualizer and forwards them to the tab; it does not inspect game state or packet traffic.

let socket = null;
let reconnectTimer = null;
let targetTabCache = {
  tabId: null,
  resolvedAt: 0,
};
let lastStatus = {
  connected: false,
  url: DEFAULT_WS_URL,
  lastError: "",
  lastEvent: "boot",
  targetTabId: null,
  lastCommandType: "",
};

async function getWsUrl() {
  const { wsUrl } = await chrome.storage.local.get({ wsUrl: DEFAULT_WS_URL });
  return String(wsUrl || DEFAULT_WS_URL);
}

function orderMatchingTabs(tabs) {
  return tabs.slice().sort((left, right) => {
    const activeDelta = Number(Boolean(right.active)) - Number(Boolean(left.active));
    if (activeDelta !== 0) {
      return activeDelta;
    }
    const lastAccessedDelta = Number(right.lastAccessed || 0) - Number(left.lastAccessed || 0);
    if (lastAccessedDelta !== 0) {
      return lastAccessedDelta;
    }
    return Number(right.id || 0) - Number(left.id || 0);
  });
}

function getMatchingTabs(tabs, hostPrefixes) {
  return orderMatchingTabs(
    tabs.filter((tab) => {
      const url = String(tab.url || "");
      return hostPrefixes.some((prefix) => url.startsWith(prefix));
    })
  );
}

async function getCandidateTabs() {
  const tabs = await chrome.tabs.query({});
  // Prefer a real Tenhou tab over the mock page so local testing does not accidentally steer live
  // play, while still allowing localhost mock end-to-end checks when no Tenhou tab exists.
  const primaryTabs = getMatchingTabs(tabs, PRIMARY_TARGET_HOST_PREFIXES);
  if (primaryTabs.length > 0) {
    return primaryTabs;
  }
  return getMatchingTabs(tabs, MOCK_TARGET_HOST_PREFIXES);
}

function isTargetTabCacheFresh() {
  return (
    targetTabCache.tabId != null &&
    Date.now() - Number(targetTabCache.resolvedAt || 0) <= TARGET_TAB_CACHE_MS
  );
}

function rememberTargetTab(tabId) {
  if (tabId == null) {
    return;
  }
  targetTabCache = {
    tabId,
    resolvedAt: Date.now(),
  };
  lastStatus.targetTabId = tabId;
}

function clearTargetTabCache(tabId) {
  if (tabId != null && targetTabCache.tabId !== tabId) {
    return;
  }
  targetTabCache = {
    tabId: null,
    resolvedAt: 0,
  };
  if (tabId == null || lastStatus.targetTabId === tabId) {
    lastStatus.targetTabId = null;
  }
}

function prioritizeCachedTab(candidates) {
  if (!isTargetTabCacheFresh() || targetTabCache.tabId == null) {
    return candidates.slice();
  }
  const cachedIndex = candidates.findIndex((tab) => tab.id === targetTabCache.tabId);
  if (cachedIndex <= 0) {
    return candidates.slice();
  }
  const prioritized = candidates.slice();
  const [cachedTab] = prioritized.splice(cachedIndex, 1);
  prioritized.unshift(cachedTab);
  return prioritized;
}

function normalizeTabSendError(error) {
  const message = String(error || "");
  return `TAB_EXECUTE_FAILED: ${message}`;
}

async function injectBridgeScripts(tabId) {
  // Always inject the latest MAIN-world bridge before calling into the page. This avoids getting
  // stuck on stale logic that was already attached before an unpacked extension reload.
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["main-ui-bridge.js"],
    world: "MAIN",
  });
}

async function sendMessageToTab(tabId, message) {
  try {
    await injectBridgeScripts(tabId);
    const results = await chrome.scripting.executeScript({
      args: [message],
      func: (request) => {
        const api = window.__TENHOU_UI_BRIDGE_MAIN_API__;
        const serializeError = (error) => {
          if (error instanceof Error) {
            return error.message || String(error);
          }
          return String(error);
        };
        if (!api || typeof api !== "object") {
          return { ok: false, error: "MAIN_BRIDGE_API_NOT_READY" };
        }
        try {
          if (request?.kind === "TENHOU_UI_SNAPSHOT") {
            if (typeof api.getSnapshot !== "function") {
              return { ok: false, error: "MAIN_BRIDGE_GET_SNAPSHOT_UNAVAILABLE" };
            }
            return api.getSnapshot();
          }
          if (request?.kind === "TENHOU_TABLE_SNAPSHOT") {
            if (typeof api.getTableSnapshot !== "function") {
              return { ok: false, error: "MAIN_BRIDGE_GET_TABLE_SNAPSHOT_UNAVAILABLE" };
            }
            return api.getTableSnapshot();
          }
          if (request?.kind === "TENHOU_EXECUTE") {
            if (typeof api.execute !== "function") {
              return { ok: false, error: "MAIN_BRIDGE_EXECUTE_UNAVAILABLE" };
            }
            return api.execute(request.command || {});
          }
          return { ok: false, error: `UNKNOWN_TAB_MESSAGE_KIND: ${String(request?.kind || "")}` };
        } catch (error) {
          return { ok: false, error: serializeError(error) };
        }
      },
      target: { tabId },
      world: "MAIN",
    });
    return results?.[0]?.result ?? { ok: false, error: "EMPTY_PAGE_RESULT" };
  } catch (error) {
    return {
      ok: false,
      error: normalizeTabSendError(error),
    };
  }
}

function countVisibleSnapshotEntries(result, key) {
  const entries = Array.isArray(result?.[key]) ? result[key] : [];
  return entries.filter((entry) => {
    if (!entry || typeof entry !== "object") {
      return false;
    }
    if ("visible" in entry) {
      return Boolean(entry.visible);
    }
    if ("available" in entry) {
      return Boolean(entry.available);
    }
    return true;
  }).length;
}

function scoreSnapshotResult(tab, result) {
  let score = 0;
  const url = String(tab?.url || "");
  if (url.includes("/3/")) {
    score += 20;
  }
  if (tab?.active) {
    score += 15;
  }
  if (!result || typeof result !== "object") {
    return score;
  }
  if (result.ok === true) {
    score += 100;
  }
  if (result.hasCanvas) {
    score += 300;
  }
  if (result.tenhouReady) {
    score += 500;
  }
  score += Math.min(100, countVisibleSnapshotEntries(result, "controls") * 10);
  score += Math.min(20, countVisibleSnapshotEntries(result, "toggleControls") * 2);
  return score;
}

async function probeBestSnapshotTab(candidates) {
  let best = null;
  for (const tab of prioritizeCachedTab(candidates)) {
    const result = await sendMessageToTab(tab.id, { kind: "TENHOU_UI_SNAPSHOT" });
    const score = scoreSnapshotResult(tab, result);
    if (!best || score > best.score) {
      best = {
        result,
        score,
        tab,
      };
    }
    if (result?.ok === true && result.tenhouReady) {
      break;
    }
  }
  if (best?.tab?.id != null) {
    rememberTargetTab(best.tab.id);
  }
  return best;
}

function shouldRetargetAfterResult(result) {
  if (result?.ok === true) {
    return false;
  }
  const errorText = String(result?.error || "");
  return (
    errorText.includes("MAIN_CANVAS_NOT_FOUND") ||
    errorText.includes("MAIN_CANVAS_NOT_VISIBLE") ||
    errorText.includes("PAGE_BRIDGE_TIMEOUT") ||
    errorText.includes("MAIN_BRIDGE_API_NOT_READY") ||
    errorText.includes("TAB_EXECUTE_FAILED")
  );
}

async function sendToTab(message) {
  const candidates = await getCandidateTabs();
  if (!candidates.length) {
    clearTargetTabCache();
    return { ok: false, error: "TENHOU_TAB_NOT_FOUND" };
  }

  if (message?.kind === "TENHOU_UI_SNAPSHOT") {
    const prioritizedCandidates = prioritizeCachedTab(candidates);
    if (prioritizedCandidates.length === 1) {
      const onlyTab = prioritizedCandidates[0];
      rememberTargetTab(onlyTab.id);
      return await sendMessageToTab(onlyTab.id, message);
    }
    if (isTargetTabCacheFresh() && targetTabCache.tabId != null) {
      const cachedTab = prioritizedCandidates.find((tab) => tab.id === targetTabCache.tabId);
      if (cachedTab) {
        const cachedResult = await sendMessageToTab(cachedTab.id, message);
        if (cachedResult?.ok === true && (cachedResult.tenhouReady || cachedResult.hasCanvas)) {
          rememberTargetTab(cachedTab.id);
          return cachedResult;
        }
        clearTargetTabCache(cachedTab.id);
      }
    }
    const bestSnapshot = await probeBestSnapshotTab(candidates);
    return bestSnapshot?.result ?? { ok: false, error: "TENHOU_TAB_NOT_FOUND" };
  }

  let targetTab = prioritizeCachedTab(candidates)[0] || null;
  if (!targetTab) {
    clearTargetTabCache();
    return { ok: false, error: "TENHOU_TAB_NOT_FOUND" };
  }
  if (candidates.length > 1 && !isTargetTabCacheFresh()) {
    const bestSnapshot = await probeBestSnapshotTab(candidates);
    if (bestSnapshot?.tab) {
      targetTab = bestSnapshot.tab;
    }
  } else {
    rememberTargetTab(targetTab.id);
  }

  let result = await sendMessageToTab(targetTab.id, message);
  if (shouldRetargetAfterResult(result) && candidates.length > 1) {
    clearTargetTabCache(targetTab.id);
    const otherCandidates = candidates.filter((tab) => tab.id !== targetTab.id);
    const bestSnapshot = await probeBestSnapshotTab(otherCandidates);
    if (bestSnapshot?.tab) {
      result = await sendMessageToTab(bestSnapshot.tab.id, message);
    }
  }
  return result;
}

function replyWs(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }
  socket.send(JSON.stringify(payload));
}

async function handleLocalCommand(raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch (error) {
    replyWs({
      type: "command_result",
      result: { ok: false, error: `INVALID_JSON: ${String(error)}` },
    });
    return;
  }
  const requestId = message?.requestId ?? null;
  const commandType = String(message?.type || "");
  lastStatus.lastCommandType = commandType;
  lastStatus.lastEvent = `command:${commandType || "unknown"}`;
  // This command switch intentionally mirrors the documented protocol instead of accepting arbitrary
  // page operations. The local app should stay the only place that decides what action is legal.

  if (commandType === "ping") {
    replyWs({ type: "pong", requestId, ts: Date.now() });
    return;
  }

  if (commandType === "ui_snapshot") {
    const result = await sendToTab({ kind: "TENHOU_UI_SNAPSHOT" });
    replyWs({
      type: "ui_snapshot_result",
      requestId,
      result,
    });
    return;
  }

  if (commandType === "table_snapshot") {
    const result = await sendToTab({ kind: "TENHOU_TABLE_SNAPSHOT" });
    replyWs({
      type: "table_snapshot_result",
      requestId,
      result,
    });
    return;
  }

  if (commandType === "discard_by_index") {
    const result = await sendToTab({
      kind: "TENHOU_EXECUTE",
      command: {
        type: "discard_by_index",
        handIndex: message?.handIndex,
        visibleHandCount: message?.visibleHandCount,
      },
    });
    replyWs({
      type: "command_result",
      requestId,
      result,
    });
    return;
  }

  if (commandType === "click_control") {
    const result = await sendToTab({
      kind: "TENHOU_EXECUTE",
      command: {
        type: "click_control",
        controlId: message?.controlId,
      },
    });
    replyWs({
      type: "command_result",
      requestId,
      result,
    });
    return;
  }

  if (commandType === "set_ws_url") {
    const nextUrl = String(message?.url || "").trim();
    if (!nextUrl) {
      replyWs({
        type: "command_result",
        requestId,
        result: { ok: false, error: "EMPTY_URL" },
      });
      return;
    }
    await chrome.storage.local.set({ wsUrl: nextUrl });
    replyWs({
      type: "command_result",
      requestId,
      result: { ok: true, wsUrl: nextUrl },
    });
    disconnectAndReconnect();
    return;
  }

  replyWs({
    type: "command_result",
    requestId,
    result: { ok: false, error: `UNKNOWN_COMMAND: ${commandType}` },
  });
}

function scheduleReconnect() {
  if (reconnectTimer != null) {
    clearTimeout(reconnectTimer);
  }
  // MV3 workers are transient, so reconnect must be self-healing without relying on a visible UI.
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectLocalWs().catch((error) => {
      lastStatus.connected = false;
      lastStatus.lastError = String(error);
      lastStatus.lastEvent = "reconnect_failed";
      scheduleReconnect();
    });
  }, RECONNECT_MS);
}

function disconnectAndReconnect() {
  if (socket) {
    try {
      socket.close();
    } catch (_error) {
      // Chrome may already be tearing the socket down; reconnect logic still runs.
    }
  }
  socket = null;
  lastStatus.connected = false;
  lastStatus.lastEvent = "reconnecting";
  scheduleReconnect();
}

async function connectLocalWs() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const url = await getWsUrl();
  lastStatus = {
    ...lastStatus,
    connected: false,
    url,
    lastError: "",
    lastEvent: "connecting",
  };

  try {
    socket = new WebSocket(url);
  } catch (error) {
    lastStatus.connected = false;
    lastStatus.lastError = String(error);
    lastStatus.lastEvent = "connect_failed";
    scheduleReconnect();
    return;
  }

  socket.addEventListener("open", () => {
    lastStatus.connected = true;
    lastStatus.lastError = "";
    lastStatus.lastEvent = "connected";
    // Notify the local app that the browser-side executor is ready. This is transport readiness
    // only, not proof that Tenhou itself is loaded or in a playable state.
    replyWs({ type: "extension_ready", ts: Date.now() });
  });

  socket.addEventListener("message", async (event) => {
    try {
      await handleLocalCommand(event.data);
    } catch (error) {
      replyWs({
        type: "command_result",
        result: { ok: false, error: `COMMAND_EXCEPTION: ${String(error)}` },
      });
    }
  });

  socket.addEventListener("close", () => {
    lastStatus.connected = false;
    lastStatus.lastEvent = "closed";
    scheduleReconnect();
  });

  socket.addEventListener("error", (event) => {
    lastStatus.connected = false;
    lastStatus.lastError = String(event?.type || "ws_error");
    lastStatus.lastEvent = "error";
  });
}

chrome.runtime.onInstalled.addListener(() => {
  connectLocalWs().catch(() => {
    scheduleReconnect();
  });
});

chrome.runtime.onStartup.addListener(() => {
  connectLocalWs().catch(() => {
    scheduleReconnect();
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.kind === "GET_BRIDGE_STATUS") {
    sendResponse(lastStatus);
    return false;
  }
  if (message?.kind === "ENSURE_LOCAL_WS") {
    connectLocalWs()
      .then(() => {
        sendResponse({ ok: true, status: lastStatus });
      })
      .catch((error) => {
        lastStatus.connected = false;
        lastStatus.lastError = String(error);
        lastStatus.lastEvent = "ensure_failed";
        sendResponse({ ok: false, error: String(error), status: lastStatus });
      });
    return true;
  }
  if (message?.kind === "RECONNECT_LOCAL_WS") {
    disconnectAndReconnect();
    sendResponse({ ok: true });
    return false;
  }
  return false;
});

connectLocalWs().catch(() => {
  scheduleReconnect();
});
