(function () {
  // This mock intentionally mirrors only the page-side pieces the bridge needs: hand-slot layout,
  // known control IDs, and action logging. It does not try to simulate packet state or Tenhou rules.
  const HAND_BASE_X = 150;
  const HAND_BASE_Y = 560;
  const TILE_WIDTH = 48;
  const TILE_HEIGHT = 64;
  const TILE_STACK_GAP_Y = 8;
  const SLOT_COUNT = 14;
  const CANVAS_WIDTH = 960;
  const CANVAS_HEIGHT = 720;
  const TRACE_PATH = "/__bridge_trace__";

  const CONTROL_SPECS = [
    { controlId: 2359814, label: "Riichi", visible: true },
    { controlId: 2360328, label: "Skip", visible: true },
    { controlId: 401412, label: "Kan", visible: true },
    { controlId: 409606, label: "Chi", visible: false },
    { controlId: 409610, label: "Pon", visible: false },
    { controlId: 2098693, label: "Main", visible: false },
  ];

  const state = {
    // Keep the mock state tiny and UI-focused so manual end-to-end checks stay predictable.
    selectedHandIndex: null,
    handLabels: ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p"],
    controls: CONTROL_SPECS.map((spec) => ({ ...spec })),
  };

  function setupTenhouGlobals(canvas) {
    // The real bridge reads these page-owned globals to translate handIndex into a click point.
    window.W = { Ka: 0, cb: 1 };
    window.U = [];
    window.U[window.W.Ka] = HAND_BASE_X;
    window.U[window.W.cb] = HAND_BASE_Y;
    window.Q = {
      I: { 4: TILE_WIDTH },
      J: { 4: TILE_HEIGHT },
      Y: { 4: TILE_STACK_GAP_Y },
    };
    window.kc = {
      P: {
        canvas,
      },
    };
    window.__TENHOU_UI_BRIDGE_MOCK__ = {
      handBaseX: HAND_BASE_X,
      handBaseY: HAND_BASE_Y,
      tileWidth: TILE_WIDTH,
      tileHeight: TILE_HEIGHT,
      // The real Tenhou page should never emit extra network traffic for bridge tracing. The mock
      // page opts in explicitly so the local mock server can print page-side requests to stdout.
      traceUrl: TRACE_PATH,
    };
  }

  function drawTable(canvas) {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

    context.fillStyle = "#1e446a";
    context.fillRect(64, 72, 832, 576);

    context.strokeStyle = "#6f8bb0";
    context.lineWidth = 2;
    context.strokeRect(64, 72, 832, 576);

    context.fillStyle = "#dce8f7";
    context.font = "16px Consolas";
    context.fillText("Bridge mock table", 80, 100);
    context.fillText("Self hand area", HAND_BASE_X, HAND_BASE_Y - 20);

    for (let index = 0; index < SLOT_COUNT; index += 1) {
      const left = HAND_BASE_X + index * TILE_WIDTH;
      const top = HAND_BASE_Y;
      context.fillStyle = state.selectedHandIndex === index ? "#facc15" : "#f4f7fb";
      context.fillRect(left, top, TILE_WIDTH - 2, TILE_HEIGHT);
      context.strokeStyle = "#2c3e55";
      context.strokeRect(left, top, TILE_WIDTH - 2, TILE_HEIGHT);
      context.fillStyle = "#182537";
      context.font = "13px Consolas";
      context.fillText(state.handLabels[index] || "?", left + 10, top + 36);
      context.fillStyle = "#8aa0bc";
      context.font = "10px Consolas";
      context.fillText(String(index), left + 16, top + 54);
    }
  }

  function appendLog(message) {
    const logList = document.getElementById("action-log");
    const item = document.createElement("li");
    item.textContent = message;
    logList.prepend(item);
    while (logList.children.length > 24) {
      logList.removeChild(logList.lastChild);
    }
    document.getElementById("last-action").textContent = `Last action: ${message}`;
  }

  function handIndexFromCanvasPoint(canvas, clientX, clientY) {
    // The mock page intentionally uses the same "visible slot index" contract as the real bridge.
    // That makes it useful for verifying handIndex behavior without any packet-side state.
    const rect = canvas.getBoundingClientRect();
    const localX = clientX - rect.left;
    const localY = clientY - rect.top;
    if (localY < HAND_BASE_Y || localY > HAND_BASE_Y + TILE_HEIGHT) {
      return null;
    }
    const rawIndex = Math.floor((localX - HAND_BASE_X) / TILE_WIDTH);
    if (rawIndex < 0 || rawIndex >= SLOT_COUNT) {
      return null;
    }
    const slotLeft = HAND_BASE_X + rawIndex * TILE_WIDTH;
    if (localX > slotLeft + TILE_WIDTH - 2) {
      return null;
    }
    return rawIndex;
  }

  function renderControls() {
    const controlsRoot = document.getElementById("mock-controls");
    const togglesRoot = document.getElementById("control-toggles");
    controlsRoot.innerHTML = "";
    togglesRoot.innerHTML = "";

    state.controls.forEach((control) => {
      // The extension looks for `m${controlId}` text nodes. Keep that structure here so the mock
      // page exercises the same selector path as the real page.
      const button = document.createElement("button");
      button.className = "control-button";
      button.type = "button";
      button.dataset.controlId = String(control.controlId);
      button.hidden = !control.visible;
      button.innerHTML = `<span id="m${control.controlId}">${control.label}</span>`;
      button.addEventListener("click", () => {
        appendLog(`control ${control.controlId} ${control.label}`);
      });
      controlsRoot.appendChild(button);

      const label = document.createElement("label");
      label.className = "control-toggle";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = control.visible;
      checkbox.addEventListener("change", () => {
        control.visible = checkbox.checked;
        renderControls();
      });
      const text = document.createElement("span");
      text.textContent = `${control.controlId} ${control.label}`;
      label.appendChild(checkbox);
      label.appendChild(text);
      togglesRoot.appendChild(label);
    });
  }

  function rotateHand() {
    // Rotating the visible hand order helps verify that the bridge obeys handIndex rather than
    // assuming a fixed tile identity to slot mapping.
    const first = state.handLabels.shift();
    if (first) {
      state.handLabels.push(first);
    }
  }

  function bindCanvas(canvas) {
    canvas.addEventListener("click", (event) => {
      // Clicking the mock canvas simulates a discard result, so manual testing can confirm that the
      // bridge hit the intended hand slot after coordinate conversion.
      const handIndex = handIndexFromCanvasPoint(canvas, event.clientX, event.clientY);
      if (handIndex == null) {
        appendLog(`canvas click ${Math.round(event.clientX)},${Math.round(event.clientY)}`);
        return;
      }
      state.selectedHandIndex = handIndex;
      appendLog(`discard handIndex=${handIndex} tile=${state.handLabels[handIndex]}`);
      drawTable(canvas);
    });
  }

  function initialize() {
    const canvas = document.getElementById("tenhou-bridge-mock-canvas");
    setupTenhouGlobals(canvas);
    bindCanvas(canvas);
    renderControls();
    drawTable(canvas);

    document.getElementById("layout-status").textContent = [
      `canvas=${CANVAS_WIDTH}x${CANVAS_HEIGHT}`,
      `handBase=(${HAND_BASE_X}, ${HAND_BASE_Y})`,
      `tile=${TILE_WIDTH}x${TILE_HEIGHT}`,
    ].join(" ");

    document.getElementById("reset-log").addEventListener("click", () => {
      document.getElementById("action-log").innerHTML = "";
      document.getElementById("last-action").textContent = "Last action: none";
      state.selectedHandIndex = null;
      drawTable(canvas);
    });

    document.getElementById("rotate-hand").addEventListener("click", () => {
      rotateHand();
      appendLog("hand order rotated");
      drawTable(canvas);
    });

    appendLog("mock page ready");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
