(function () {
  const BRIDGE_PROTOCOL_VERSION = "v4";
  const MAIN_WORLD_INSTALLED_FLAG = "__TENHOU_UI_BRIDGE_MAIN_WORLD_INSTALLED_VERSION__";
  const MAIN_WORLD_API_KEY = "__TENHOU_UI_BRIDGE_MAIN_API__";
  if (window[MAIN_WORLD_INSTALLED_FLAG] === BRIDGE_PROTOCOL_VERSION) {
    return;
  }
  window[MAIN_WORLD_INSTALLED_FLAG] = BRIDGE_PROTOCOL_VERSION;
  const PAGE_TO_EXTENSION = `TENHOU_UI_BRIDGE_FROM_PAGE_${BRIDGE_PROTOCOL_VERSION}`;
  const EXTENSION_TO_PAGE = `TENHOU_UI_BRIDGE_TO_PAGE_${BRIDGE_PROTOCOL_VERSION}`;
  const DEFAULT_LAYOUT_CANVAS_WIDTH = 960;
  const DEFAULT_LAYOUT_CANVAS_HEIGHT = 720;
  const DEFAULT_HAND_BASE_X_RATIO = 150 / DEFAULT_LAYOUT_CANVAS_WIDTH;
  const DEFAULT_HAND_TILE_WIDTH_RATIO = 48 / DEFAULT_LAYOUT_CANVAS_WIDTH;
  const DEFAULT_HAND_CENTER_Y_RATIO = (560 + Math.floor(64 / 2)) / DEFAULT_LAYOUT_CANVAS_HEIGHT;
  const HAND_DETECTION_LEFT_RATIO = 0.08;
  const HAND_DETECTION_RIGHT_RATIO = 0.92;
  const HAND_DETECTION_TOP_RATIO = 0.78;
  const HAND_DETECTION_BOTTOM_RATIO = 0.998;
  const HAND_DETECTION_COLOR_DISTANCE_THRESHOLD = 58;
  const HAND_DETECTION_COLUMN_ACTIVE_PIXEL_RATIO = 0.08;
  const HAND_DETECTION_GAP_FILL_PX = 4;
  const HAND_DETECTION_MIN_SEGMENT_WIDTH_RATIO = 0.012;
  const HAND_DETECTION_SPLIT_WIDTH_RATIO = 1.55;
  const HAND_DETECTION_BOTTOM_CLUSTER_GAP_PX = 3;
  const HAND_DETECTION_CLICK_Y_RATIO = 0.62;
  const INTERNAL_STATE_KEY = "__TENHOU_UI_BRIDGE_INTERNAL_STATE__";
  const ASSIGN_HOOK_FLAG_KEY = "__TENHOU_UI_BRIDGE_ASSIGN_HOOK_INSTALLED__";
  const DEBUG_MARKER_ID = "__tenhou_ui_bridge_debug_marker__";
  const DEBUG_MARKER_TTL_MS = 1400;

  // Keep the MAIN-world bridge intentionally narrow. It only reports which known buttons are
  // visible and executes clicks from already-decided commands sent by the local visualizer.
  const CONTROL_IDS = [
    2360326,
    2098693,
    3670533,
    3671045,
    409606,
    409607,
    409604,
    409610,
    409609,
    409608,
    409614,
    409613,
    409612,
    401412,
    401416,
    401417,
    401414,
    401415,
    401418,
    401419,
    2359814,
    2359815,
    2359816,
    2360328,
    1574917,
    1574918,
    1572868,
  ];
  const APP_TOGGLE_CONTROL_IDS = [1183750, 1183752, 1183753, 1183749];
  const APP_TOGGLE_CONTROL_ID_SET = new Set(APP_TOGGLE_CONTROL_IDS);
  const APP_TOGGLE_CONTROL_LABELS = new Map([
    [1183750, "自動理牌"],
    [1183752, "自動和了"],
    [1183753, "ツモ切り"],
    [1183749, "鳴き無し"],
  ]);
  const INTERNAL_CONTROL_EXECUTOR_CONTROL_IDS = new Set([
    2098693,
    409606,
    409607,
    409604,
    409610,
    409609,
    409608,
    409614,
    409613,
    409612,
    401412,
    401416,
    401417,
    401414,
    401415,
    401418,
    401419,
    2359814,
    2359815,
    2359816,
    2360328,
  ]);

  function getInternalState() {
    if (!window[INTERNAL_STATE_KEY]) {
      window[INTERNAL_STATE_KEY] = {
        capturedAtTs: 0,
      };
    }
    return window[INTERNAL_STATE_KEY];
  }

  function captureInternalReference(name, value) {
    if (!value || (typeof value !== "object" && typeof value !== "function")) {
      return;
    }
    const internalState = getInternalState();
    internalState[name] = value;
    internalState.capturedAtTs = Date.now();
  }

  function maybeCaptureAssignedTarget(target, source) {
    if (!source || typeof source !== "object") {
      return;
    }
    const sourceKeys = Object.keys(source);
    if (!sourceKeys.length) {
      return;
    }
    if (
      sourceKeys.includes("zg") &&
      sourceKeys.includes("T") &&
      sourceKeys.includes("D") &&
      sourceKeys.includes("N") &&
      typeof source.zg === "function"
    ) {
      captureInternalReference("z", target);
    }
    if (sourceKeys.includes("ca") && sourceKeys.includes("Fd") && Array.isArray(target?.Xa)) {
      captureInternalReference("U", target);
    }
    if (sourceKeys.includes("b") && sourceKeys.includes("ca") && sourceKeys.includes("Ab")) {
      captureInternalReference("qc", target);
    }
    if (sourceKeys.includes("ek") && sourceKeys.includes("gg")) {
      captureInternalReference("zc", target);
    }
    if (sourceKeys.includes("xb") && sourceKeys.includes("kg") && sourceKeys.includes("vg")) {
      captureInternalReference("rc", target);
    }
    if (sourceKeys.includes("Ma") && sourceKeys.includes("sa") && sourceKeys.includes("ca")) {
      captureInternalReference("L", target);
    }
    if (
      sourceKeys.includes("P") &&
      sourceKeys.includes("Yc") &&
      sourceKeys.includes("gb") &&
      target?.P?.canvas
    ) {
      captureInternalReference("kc", target);
    }
    if (sourceKeys.includes("ok") && sourceKeys.includes("exit") && sourceKeys.includes("cfg")) {
      captureInternalReference("P", target);
    }
  }

  function installInternalAssignHook() {
    if (window[ASSIGN_HOOK_FLAG_KEY]) {
      return;
    }
    window[ASSIGN_HOOK_FLAG_KEY] = true;
    const nativeAssign = Object.assign;
    if (typeof nativeAssign !== "function") {
      return;
    }
    Object.assign = function tenhouUiBridgeAssignHook(target, ...sources) {
      const result = nativeAssign.apply(Object, [target, ...sources]);
      try {
        for (const source of sources) {
          maybeCaptureAssignedTarget(result, source);
        }
      } catch (_error) {
        // The hook is best-effort. Failing to inspect one assignment must not break Tenhou itself.
      }
      return result;
    };
  }

  installInternalAssignHook();

  function getMockTraceUrl() {
    const traceUrl = window.__TENHOU_UI_BRIDGE_MOCK__?.traceUrl;
    return typeof traceUrl === "string" && traceUrl ? traceUrl : null;
  }

  function getInternalReference(name, requiredMethods) {
    const internalState = getInternalState();
    const normalizedRequiredMethods = Array.isArray(requiredMethods) ? requiredMethods : [requiredMethods];
    const candidates = [internalState[name], window[name]];
    for (const candidate of candidates) {
      if (
        candidate &&
        normalizedRequiredMethods.every(
          (methodName) => typeof candidate[methodName] === "function"
        )
      ) {
        captureInternalReference(name, candidate);
        return candidate;
      }
    }
    return null;
  }

  function getCapturedWindowObject(name) {
    const internalState = getInternalState();
    const candidates = [internalState[name], window[name]];
    for (const candidate of candidates) {
      if (candidate && (typeof candidate === "object" || typeof candidate === "function")) {
        captureInternalReference(name, candidate);
        return candidate;
      }
    }
    return null;
  }

  function getDirectDiscardExecutor() {
    return getInternalReference("z", "zg");
  }

  function getInternalControlDispatcher() {
    return getInternalReference("L", "Ma");
  }

  function getInternalControlExecutor() {
    return getInternalReference("zc", "gg");
  }

  function getInternalSkipExecutor() {
    return getInternalReference("rc", "kg");
  }

  function normalizeVisibleHandCount(visibleHandCount) {
    if (Number.isInteger(visibleHandCount)) {
      return visibleHandCount;
    }
    const parsedVisibleHandCount = Number.parseInt(visibleHandCount, 10);
    return Number.isInteger(parsedVisibleHandCount) ? parsedVisibleHandCount : null;
  }

  function assertDiscardTimingReady(visibleHandCount) {
    const normalizedVisibleHandCount = normalizeVisibleHandCount(visibleHandCount);
    if (
      Number.isInteger(normalizedVisibleHandCount) &&
      normalizedVisibleHandCount > 0 &&
      normalizedVisibleHandCount % 3 !== 2
    ) {
      throw new Error(
        `VISIBLE_HAND_NOT_ACTIONABLE: visibleHandCount=${normalizedVisibleHandCount}`
      );
    }
    return normalizedVisibleHandCount;
  }

  function shouldUseDirectDiscardExecutor(visibleHandCount) {
    const normalizedVisibleHandCount = normalizeVisibleHandCount(visibleHandCount);
    if (!Number.isInteger(normalizedVisibleHandCount) || normalizedVisibleHandCount <= 0) {
      return true;
    }
    // `z.zg(handIndex)` already maps the displayed hand slot into Tenhou's current tile id array
    // and performs the same discard gating/cleanup that the normal mouse path uses. Prefer that
    // route for both closed and open hands; the synthetic canvas fallback is only for pages where
    // the internal executor is unavailable.
    return true;
  }

  function emitMockTrace(eventType, detail) {
    const traceUrl = getMockTraceUrl();
    if (!traceUrl || typeof window.fetch !== "function") {
      return;
    }
    // This hook is mock-only by construction. Real Tenhou pages do not define `traceUrl`, so the
    // executor stays network-silent outside local testing while still giving stdout visibility in
    // the mock environment.
    const payload = {
      detail,
      eventType,
      pageUrl: window.location.href,
      ts: Date.now(),
    };
    void window
      .fetch(traceUrl, {
        body: JSON.stringify(payload),
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        keepalive: true,
        method: "POST",
      })
      .catch(() => {});
  }

  function describeElement(target) {
    if (!target) {
      return "null";
    }
    const tagName = String(target.tagName || "node").toLowerCase();
    const idPart = target.id ? `#${target.id}` : "";
    const className =
      typeof target.className === "string"
        ? target.className
            .trim()
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 3)
            .join(".")
        : "";
    const classPart = className ? `.${className}` : "";
    return `${tagName}${idPart}${classPart}`;
  }

  function showDebugMarker(x, y, label, accentColor) {
    let marker = document.getElementById(DEBUG_MARKER_ID);
    if (!marker) {
      marker = document.createElement("div");
      marker.id = DEBUG_MARKER_ID;
      marker.style.pointerEvents = "none";
      marker.style.position = "fixed";
      marker.style.zIndex = "2147483647";
      marker.style.width = "18px";
      marker.style.height = "18px";
      marker.style.borderRadius = "999px";
      marker.style.border = "2px solid #ffffff";
      marker.style.boxShadow = "0 0 0 2px rgba(15, 23, 42, 0.45)";
      marker.style.transform = "translate(-50%, -50%)";
      marker.style.font = "700 11px/1.2 sans-serif";
      marker.style.color = "#ffffff";
      marker.style.textShadow = "0 1px 2px rgba(0, 0, 0, 0.85)";
      marker.style.display = "flex";
      marker.style.alignItems = "center";
      marker.style.justifyContent = "center";
      document.documentElement.appendChild(marker);
    }
    marker.style.left = `${x}px`;
    marker.style.top = `${y}px`;
    marker.style.background = accentColor || "#ef4444";
    marker.textContent = String(label || "");
    const previousTimer = Number(marker.dataset.hideTimerId || 0);
    if (previousTimer) {
      window.clearTimeout(previousTimer);
    }
    const hideTimerId = window.setTimeout(() => {
      if (marker) {
        marker.remove();
      }
    }, DEBUG_MARKER_TTL_MS);
    marker.dataset.hideTimerId = String(hideTimerId);
  }

  function isVisible(el) {
    if (!el) {
      return false;
    }
    // Visibility checks stay conservative because `ui_snapshot` should only report controls the
    // user could actually click right now.
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function getControlElement(controlId) {
    const labelNode = document.getElementById(`m${controlId}`);
    if (!labelNode) {
      return null;
    }
    // Tenhou often wraps the visible text node in a larger clickable parent, so prefer the parent
    // when present. The bridge should hit the same target a real user would.
    return labelNode.parentElement || labelNode;
  }

  function enumerateKnownControlIds() {
    const controlIds = new Set(CONTROL_IDS);
    const internalControlDispatcher = getInternalControlDispatcher();
    const container = internalControlDispatcher?.b instanceof Element ? internalControlDispatcher.b : null;
    const candidateNodes = container
      ? container.querySelectorAll("[id^='m']")
      : document.querySelectorAll("[id^='m']");
    for (const node of candidateNodes) {
      const matched = String(node.id || "").match(/^m(\d+)$/);
      if (!matched) {
        continue;
      }
      const controlId = Number.parseInt(matched[1], 10);
      if (Number.isInteger(controlId)) {
        controlIds.add(controlId);
      }
    }
    return Array.from(controlIds.values()).sort((left, right) => left - right);
  }

  function readControls() {
    return enumerateKnownControlIds()
      .map((controlId) => {
        if (APP_TOGGLE_CONTROL_ID_SET.has(controlId)) {
          return null;
        }
        const controlElement = getControlElement(controlId);
        const text = (document.getElementById(`m${controlId}`)?.textContent || "").trim();
        return {
          controlId,
          visible: isVisible(controlElement),
          text,
        };
      })
      .filter((control) => control && control.visible);
  }

  function readToggleControls() {
    const internalControlDispatcher = getInternalControlDispatcher();
    const toggleState = internalControlDispatcher && internalControlDispatcher.u ? internalControlDispatcher.u : null;
    const readToggleActiveFromDom = (controlId) => {
      const labelNode = document.getElementById(`m${controlId}`);
      if (!labelNode) {
        return false;
      }
      const stateNode = labelNode.querySelector("span") || labelNode;
      const inlineStyleText = String(stateNode.getAttribute("style") || "").replace(/\s+/g, "").toLowerCase();
      if (inlineStyleText.includes("color:#888")) {
        return false;
      }
      const innerHtmlText = String(labelNode.innerHTML || "").replace(/\s+/g, "").toLowerCase();
      if (innerHtmlText.includes("color:#888")) {
        return false;
      }
      return true;
    };
    return APP_TOGGLE_CONTROL_IDS.map((controlId) => {
      const controlElement = getControlElement(controlId);
      const text =
        (document.getElementById(`m${controlId}`)?.textContent || "").trim() ||
        APP_TOGGLE_CONTROL_LABELS.get(controlId) ||
        "";
      const hasInternalToggleState =
        Boolean(toggleState) && Object.prototype.hasOwnProperty.call(toggleState, controlId);
      return {
        controlId,
        visible: isVisible(controlElement),
        available: Boolean(internalControlDispatcher || controlElement),
        active: hasInternalToggleState ? Boolean(toggleState[controlId]) : readToggleActiveFromDom(controlId),
        text,
      };
    });
  }

  function getCapturedLayoutCanvas() {
    const internalKc = getInternalState().kc;
    return internalKc?.P?.canvas || null;
  }

  function getMainCanvas() {
    const capturedLayoutCanvas = getCapturedLayoutCanvas();
    if (capturedLayoutCanvas) {
      return capturedLayoutCanvas;
    }
    const candidates = Array.from(document.querySelectorAll("canvas"));
    if (!candidates.length) {
      return null;
    }
    // Tenhou can create several canvases. Picking the largest visible canvas is more resilient than
    // pinning to one exact DOM order, while still keeping the bridge logic UI-only.
    const visibleCandidates = candidates.filter(isVisible);
    const rankedCandidates = (visibleCandidates.length ? visibleCandidates : candidates).slice();
    rankedCandidates.sort((left, right) => {
      const leftRect = left.getBoundingClientRect();
      const rightRect = right.getBoundingClientRect();
      return rightRect.width * rightRect.height - leftRect.width * leftRect.height;
    });
    return rankedCandidates[0] || null;
  }

  function getLayoutCanvas() {
    // `window.kc.P.canvas` is the page's own primary layout canvas when available. Fall back to a
    // DOM search so the mock page and partial-load states can still be tested safely.
    return getCapturedLayoutCanvas() || window.kc?.P?.canvas || getMainCanvas();
  }

  function getLayoutGlobalsState() {
    const missingGlobals = [];
    if (typeof window.U === "undefined") {
      missingGlobals.push("U");
    }
    if (typeof window.W === "undefined") {
      missingGlobals.push("W");
    }
    if (typeof window.Q === "undefined") {
      missingGlobals.push("Q");
    }
    if (typeof window.kc === "undefined" && !getInternalState().kc) {
      missingGlobals.push("kc");
    }
    return {
      globalsReady: missingGlobals.length === 0,
      missingGlobals,
    };
  }

  function getHeuristicHandSlotCenter(handIndex) {
    const layoutCanvas = getLayoutCanvas();
    if (!layoutCanvas) {
      throw new Error("MAIN_CANVAS_NOT_FOUND");
    }
    const rect = layoutCanvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      throw new Error("MAIN_CANVAS_NOT_VISIBLE");
    }

    // Current Tenhou pages may hide the historical `U / W / Q / kc` globals from the page-global
    // namespace. Keep a conservative fixed-layout fallback so handIndex-based discard can still
    // work on the standard self-hand strip when the canvas aspect matches the classic table.
    const xRatio =
      DEFAULT_HAND_BASE_X_RATIO +
      DEFAULT_HAND_TILE_WIDTH_RATIO * handIndex +
      DEFAULT_HAND_TILE_WIDTH_RATIO / 2;
    return {
      x: rect.left + rect.width * xRatio,
      y: rect.top + rect.height * DEFAULT_HAND_CENTER_Y_RATIO,
    };
  }

  function getCanvasHandDetection(expectedVisibleHandCount) {
    const layoutCanvas = getLayoutCanvas();
    if (!layoutCanvas || typeof layoutCanvas.getContext !== "function") {
      return null;
    }
    const canvasWidth = Number(layoutCanvas.width || 0);
    const canvasHeight = Number(layoutCanvas.height || 0);
    if (canvasWidth <= 0 || canvasHeight <= 0) {
      return null;
    }
    const context = layoutCanvas.getContext("2d", { willReadFrequently: true });
    if (!context || typeof context.getImageData !== "function") {
      return null;
    }

    const roiLeft = Math.max(0, Math.floor(canvasWidth * HAND_DETECTION_LEFT_RATIO));
    const roiRight = Math.min(canvasWidth, Math.ceil(canvasWidth * HAND_DETECTION_RIGHT_RATIO));
    const roiTop = Math.max(0, Math.floor(canvasHeight * HAND_DETECTION_TOP_RATIO));
    const roiBottom = Math.min(canvasHeight, Math.ceil(canvasHeight * HAND_DETECTION_BOTTOM_RATIO));
    const roiWidth = roiRight - roiLeft;
    const roiHeight = roiBottom - roiTop;
    if (roiWidth <= 0 || roiHeight <= 0) {
      return null;
    }

    let imageData;
    try {
      imageData = context.getImageData(roiLeft, roiTop, roiWidth, roiHeight);
    } catch (_error) {
      // Some browser/canvas combinations may block pixel reads. Fall back to the older heuristic
      // instead of failing the whole bridge command.
      return null;
    }
    const pixels = imageData.data;
    if (!pixels || pixels.length < roiWidth * roiHeight * 4) {
      return null;
    }

    const backgroundSamples = [];
    const sampleXs = [
      Math.floor(roiWidth * 0.02),
      Math.floor(roiWidth * 0.05),
      Math.floor(roiWidth * 0.95),
      Math.floor(roiWidth * 0.98),
    ];
    const sampleYs = [
      Math.floor(roiHeight * 0.25),
      Math.floor(roiHeight * 0.5),
      Math.floor(roiHeight * 0.75),
    ];
    for (const sampleX of sampleXs) {
      for (const sampleY of sampleYs) {
        const offset = (sampleY * roiWidth + sampleX) * 4;
        backgroundSamples.push({
          r: pixels[offset],
          g: pixels[offset + 1],
          b: pixels[offset + 2],
        });
      }
    }
    if (!backgroundSamples.length) {
      return null;
    }
    const backgroundColor = backgroundSamples.reduce(
      (accumulator, sample) => ({
        r: accumulator.r + sample.r,
        g: accumulator.g + sample.g,
        b: accumulator.b + sample.b,
      }),
      { r: 0, g: 0, b: 0 }
    );
    backgroundColor.r /= backgroundSamples.length;
    backgroundColor.g /= backgroundSamples.length;
    backgroundColor.b /= backgroundSamples.length;

    const foregroundMask = new Uint8Array(roiWidth * roiHeight);
    const activeColumns = new Array(roiWidth).fill(false);
    const activeThreshold = Math.max(4, Math.floor(roiHeight * HAND_DETECTION_COLUMN_ACTIVE_PIXEL_RATIO));
    for (let x = 0; x < roiWidth; x += 1) {
      let foregroundCount = 0;
      for (let y = 0; y < roiHeight; y += 1) {
        const offset = (y * roiWidth + x) * 4;
        const alpha = pixels[offset + 3];
        if (alpha < 16) {
          continue;
        }
        const colorDistance =
          Math.abs(pixels[offset] - backgroundColor.r) +
          Math.abs(pixels[offset + 1] - backgroundColor.g) +
          Math.abs(pixels[offset + 2] - backgroundColor.b);
        if (colorDistance < HAND_DETECTION_COLOR_DISTANCE_THRESHOLD) {
          continue;
        }
        foregroundMask[y * roiWidth + x] = 1;
        foregroundCount += 1;
      }
      activeColumns[x] = foregroundCount >= activeThreshold;
    }

    // Fill tiny inter-column gaps caused by tile art or antialiasing so one tile stays one run.
    for (let start = 0; start < activeColumns.length; start += 1) {
      if (activeColumns[start]) {
        continue;
      }
      let end = start;
      while (end < activeColumns.length && !activeColumns[end]) {
        end += 1;
      }
      const gapLength = end - start;
      if (
        start > 0 &&
        end < activeColumns.length &&
        activeColumns[start - 1] &&
        activeColumns[end] &&
        gapLength <= HAND_DETECTION_GAP_FILL_PX
      ) {
        for (let x = start; x < end; x += 1) {
          activeColumns[x] = true;
        }
      }
      start = end - 1;
    }

    const minSegmentWidth = Math.max(6, Math.floor(canvasWidth * HAND_DETECTION_MIN_SEGMENT_WIDTH_RATIO));
    const expectedTileWidth = Math.max(10, canvasWidth * DEFAULT_HAND_TILE_WIDTH_RATIO);
    const rawSegments = [];
    for (let x = 0; x < activeColumns.length; x += 1) {
      if (!activeColumns[x]) {
        continue;
      }
      let end = x;
      while (end + 1 < activeColumns.length && activeColumns[end + 1]) {
        end += 1;
      }
      rawSegments.push({ start: x, end });
      x = end;
    }

    const normalizedSegments = [];
    for (const segment of rawSegments) {
      const width = segment.end - segment.start + 1;
      if (width < minSegmentWidth) {
        continue;
      }
      const splitCount =
        width >= expectedTileWidth * HAND_DETECTION_SPLIT_WIDTH_RATIO
          ? Math.max(2, Math.round(width / expectedTileWidth))
          : 1;
      if (splitCount === 1) {
        normalizedSegments.push(segment);
        continue;
      }
      const splitWidth = width / splitCount;
      for (let index = 0; index < splitCount; index += 1) {
        const splitStart = Math.round(segment.start + splitWidth * index);
        const splitEnd = Math.round(segment.start + splitWidth * (index + 1)) - 1;
        if ((splitEnd - splitStart + 1) < minSegmentWidth) {
          continue;
        }
        normalizedSegments.push({ start: splitStart, end: splitEnd });
      }
    }

    if (!normalizedSegments.length) {
      return null;
    }

    const slotCenters = normalizedSegments
      .map((segment) => {
        const rowCounts = new Array(roiHeight).fill(0);
        for (let x = segment.start; x <= segment.end; x += 1) {
          for (let y = 0; y < roiHeight; y += 1) {
            if (!foregroundMask[y * roiWidth + x]) {
              continue;
            }
            rowCounts[y] += 1;
          }
        }
        let bottomY = -1;
        for (let y = roiHeight - 1; y >= 0; y -= 1) {
          if (rowCounts[y] > 0) {
            bottomY = y;
            break;
          }
        }
        let clusterTopY = Math.floor(roiHeight * 0.2);
        let clusterBottomY = Math.floor(roiHeight * 0.8);
        if (bottomY >= 0) {
          clusterBottomY = bottomY;
          clusterTopY = bottomY;
          let gapCount = 0;
          for (let y = bottomY; y >= 0; y -= 1) {
            if (rowCounts[y] > 0) {
              clusterTopY = y;
              gapCount = 0;
              continue;
            }
            gapCount += 1;
            if (gapCount > HAND_DETECTION_BOTTOM_CLUSTER_GAP_PX) {
              break;
            }
          }
        }
        let sumX = 0;
        let pixelCount = 0;
        for (let x = segment.start; x <= segment.end; x += 1) {
          for (let y = clusterTopY; y <= clusterBottomY; y += 1) {
            if (!foregroundMask[y * roiWidth + x]) {
              continue;
            }
            sumX += x;
            pixelCount += 1;
          }
        }
        const xCenter = pixelCount > 0 ? sumX / pixelCount : (segment.start + segment.end) / 2;
        const yCenter = clusterTopY + (clusterBottomY - clusterTopY) * HAND_DETECTION_CLICK_Y_RATIO;
        return {
          xDevice: roiLeft + xCenter,
          yDevice: roiTop + yCenter,
        };
      })
      .sort((left, right) => left.xDevice - right.xDevice);

    let finalSlotCenters = slotCenters;
    let slotStrategy = "segments";
    const normalizedExpectedCount = Number.isInteger(expectedVisibleHandCount)
      ? expectedVisibleHandCount
      : Number.parseInt(expectedVisibleHandCount, 10);
    if (
      Number.isInteger(normalizedExpectedCount) &&
      normalizedExpectedCount > 0 &&
      slotCenters.length > 0 &&
      slotCenters.length !== normalizedExpectedCount
    ) {
      const averageYDevice =
        slotCenters.reduce((sum, center) => sum + center.yDevice, 0) / slotCenters.length;
      const unionStart = normalizedSegments[0].start;
      const unionEnd = normalizedSegments[normalizedSegments.length - 1].end;
      const unionWidth = Math.max(1, unionEnd - unionStart + 1);
      const slotStride = unionWidth / normalizedExpectedCount;
      finalSlotCenters = Array.from({ length: normalizedExpectedCount }, (_unusedValue, index) => ({
        xDevice: roiLeft + unionStart + slotStride * (index + 0.5),
        yDevice: averageYDevice,
      }));
      slotStrategy = "even_split";
    }

    return {
      detectedRawSlotCount: slotCenters.length,
      slotCenters: finalSlotCenters,
      slotCount: finalSlotCenters.length,
      slotStrategy,
    };
  }

  function getLayoutExecutionState() {
    const layoutCanvas = getLayoutCanvas();
    const globalsState = getLayoutGlobalsState();
    if (globalsState.globalsReady) {
      return {
        layoutMode: "globals",
        missingGlobals: [],
        ready: true,
        hasCanvas: Boolean(layoutCanvas),
      };
    }
    const canvasDetection = getCanvasHandDetection();
    if (canvasDetection && canvasDetection.slotCount >= 2) {
      return {
        layoutMode: "canvas_detect",
        missingGlobals: globalsState.missingGlobals,
        ready: true,
        hasCanvas: Boolean(layoutCanvas),
        detectedHandSlotCount: canvasDetection.slotCount,
        slotStrategy: canvasDetection.slotStrategy,
      };
    }
    return {
      layoutMode: layoutCanvas ? "heuristic" : "unavailable",
      missingGlobals: globalsState.missingGlobals,
      ready: Boolean(layoutCanvas),
      hasCanvas: Boolean(layoutCanvas),
      detectedHandSlotCount: 0,
    };
  }

  function getHandSlotCenter(handIndex, expectedVisibleHandCount) {
    if (!Number.isInteger(handIndex) || handIndex < 0 || handIndex > 13) {
      throw new Error(`INVALID_HAND_INDEX: ${handIndex}`);
    }

    const layoutCanvas = getLayoutCanvas();
    if (!layoutCanvas) {
      throw new Error("MAIN_CANVAS_NOT_FOUND");
    }
    const rect = layoutCanvas.getBoundingClientRect();
    const canvasWidth = Number(layoutCanvas.width || 0);
    const canvasHeight = Number(layoutCanvas.height || 0);
    const layoutState = getLayoutExecutionState();
    if (!layoutState.ready) {
      throw new Error("TENHOU_LAYOUT_NOT_READY");
    }
    if (layoutState.layoutMode === "canvas_detect") {
      const canvasDetection = getCanvasHandDetection(expectedVisibleHandCount);
      if (canvasDetection && handIndex < canvasDetection.slotCenters.length) {
        const detectedSlotCenter = canvasDetection.slotCenters[handIndex];
        const scaleX = canvasWidth > 0 ? rect.width / canvasWidth : 1;
        const scaleY = canvasHeight > 0 ? rect.height / canvasHeight : 1;
        return {
          x: rect.left + detectedSlotCenter.xDevice * scaleX,
          y: rect.top + detectedSlotCenter.yDevice * scaleY,
        };
      }
    }
    if (layoutState.layoutMode !== "globals") {
      return getHeuristicHandSlotCenter(handIndex);
    }

    // These globals belong to the page itself, so the coordinate conversion must stay in MAIN
    // world. The local app only sends "which displayed hand slot should be clicked".
    const xBase = window.U[window.W.Ka];
    const yBase = window.U[window.W.cb];
    const tileWidth = window.Q.I[4];
    const tileHeight = window.Q.J[4] + window.Q.Y[4];
    // The page stores layout positions in canvas/device coordinates, while DOM hit testing uses
    // CSS pixels. Scale through the actual canvas rect instead of assuming DPR alone.
    const scaleX = canvasWidth > 0 ? rect.width / canvasWidth : 1;
    const scaleY = canvasHeight > 0 ? rect.height / canvasHeight : 1;
    const xDevice = xBase + tileWidth * handIndex + Math.floor(tileWidth / 2);
    const yDevice = yBase + Math.floor(tileHeight / 2);

    return {
      x: rect.left + xDevice * scaleX,
      y: rect.top + yDevice * scaleY,
    };
  }

  function dispatchPointerSequence(target, x, y) {
    if (typeof target.focus === "function") {
      try {
        target.focus({ preventScroll: true });
      } catch (_error) {
        try {
          target.focus();
        } catch (_innerError) {}
      }
    }
    const mouseOpts = {
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0,
      buttons: 1,
    };

    // Tenhou's UI reacts more reliably when the hover/down/up sequence looks like a real pointer
    // path instead of one raw `.click()`.
    if (typeof PointerEvent === "function") {
      const pointerOpts = {
        ...mouseOpts,
        pointerId: 1,
        pointerType: "mouse",
        isPrimary: true,
      };
      target.dispatchEvent(new PointerEvent("pointermove", { ...pointerOpts, buttons: 0 }));
      target.dispatchEvent(new PointerEvent("pointerdown", pointerOpts));
      target.dispatchEvent(new PointerEvent("pointerup", { ...pointerOpts, buttons: 0 }));
    }
    target.dispatchEvent(new MouseEvent("mousemove", { ...mouseOpts, buttons: 0 }));
    target.dispatchEvent(new MouseEvent("mousedown", mouseOpts));
    target.dispatchEvent(new MouseEvent("mouseup", { ...mouseOpts, buttons: 0 }));
    target.dispatchEvent(new MouseEvent("click", { ...mouseOpts, buttons: 0 }));
  }

  function discardByIndex(handIndex, expectedVisibleHandCount) {
    const layoutCanvas = getLayoutCanvas();
    if (!layoutCanvas) {
      throw new Error("MAIN_CANVAS_NOT_FOUND");
    }
    const normalizedExpectedVisibleHandCount = assertDiscardTimingReady(expectedVisibleHandCount);
    const layoutState = getLayoutExecutionState();
    const directDiscardExecutor = getDirectDiscardExecutor();
    const useDirectDiscardExecutor =
      Boolean(directDiscardExecutor) && shouldUseDirectDiscardExecutor(normalizedExpectedVisibleHandCount);
    let point = null;
    try {
      point = getHandSlotCenter(handIndex, normalizedExpectedVisibleHandCount);
    } catch (_error) {
      point = null;
    }
    if (useDirectDiscardExecutor) {
      if (point) {
        showDebugMarker(point.x, point.y, String(handIndex), "#16a34a");
      }
      // Mirror Tenhou's normal hand-click path. Passing the forced second argument skips the
      // page-side countdown/timer cleanup (`rc.xb()/xc()`), which leaves the action UI stuck.
      directDiscardExecutor.zg(handIndex);
      return {
        ok: true,
        action: "discard_by_index",
        handIndex,
        layoutMode: "internal_zg",
        dispatchTarget: "tenhou:z.zg",
        hitTarget: point ? describeElement(document.elementFromPoint(point.x, point.y)) : "n/a",
        point,
      };
    }
    const canvasDetection =
      layoutState.layoutMode === "canvas_detect"
        ? getCanvasHandDetection(normalizedExpectedVisibleHandCount)
        : null;
    if (!point) {
      point = getHeuristicHandSlotCenter(handIndex);
    }
    const hitTarget = document.elementFromPoint(point.x, point.y);
    // Discard execution should favor the layout canvas itself. The page often renders the whole
    // table into one canvas, and intermediate overlay elements found by `elementFromPoint()` do
    // not necessarily own the real input handlers.
    const target = layoutCanvas;
    showDebugMarker(point.x, point.y, String(handIndex), "#ef4444");
    dispatchPointerSequence(target, point.x, point.y);
    const canvasRect = layoutCanvas.getBoundingClientRect();
    return {
      ok: true,
      action: "discard_by_index",
      handIndex,
      layoutMode: layoutState.layoutMode,
      detectedHandSlotCount: Number(canvasDetection?.slotCount || layoutState.detectedHandSlotCount || 0),
      slotStrategy: String(canvasDetection?.slotStrategy || layoutState.slotStrategy || ""),
      dispatchTarget: describeElement(target),
      hitTarget: describeElement(hitTarget),
      canvasRect: {
        left: canvasRect.left,
        top: canvasRect.top,
        width: canvasRect.width,
        height: canvasRect.height,
      },
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      point,
    };
  }

  function clickControl(controlId) {
    const normalizedControlId = Number.parseInt(controlId, 10);
    const controlElement = getControlElement(normalizedControlId);
    const controlText =
      (document.getElementById(`m${normalizedControlId}`)?.textContent || "").trim() ||
      APP_TOGGLE_CONTROL_LABELS.get(normalizedControlId) ||
      "";
    const internalControlDispatcher = getInternalControlDispatcher();
    const canUseHiddenInternalToggle =
      APP_TOGGLE_CONTROL_ID_SET.has(normalizedControlId) && Boolean(internalControlDispatcher);

    if (!controlElement || !isVisible(controlElement)) {
      if (canUseHiddenInternalToggle) {
        internalControlDispatcher.Ma(normalizedControlId);
        return {
          ok: true,
          action: "click_control",
          controlId: normalizedControlId,
          text: controlText,
          dispatchTarget: "tenhou:L.Ma",
          hitTarget: "hidden_toggle",
          point: null,
        };
      }
      if (!controlElement) {
        throw new Error(`CONTROL_NOT_FOUND: ${normalizedControlId}`);
      }
      throw new Error(`CONTROL_NOT_VISIBLE: ${normalizedControlId}`);
    }

    const rect = controlElement.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const target = document.elementFromPoint(x, y) || controlElement;
    showDebugMarker(x, y, "C", "#2563eb");

    if (APP_TOGGLE_CONTROL_ID_SET.has(normalizedControlId) && internalControlDispatcher) {
      internalControlDispatcher.Ma(normalizedControlId);
      return {
        ok: true,
        action: "click_control",
        controlId: normalizedControlId,
        text: controlText,
        dispatchTarget: "tenhou:L.Ma",
        hitTarget: describeElement(target),
        point: { x, y },
      };
    }

    // Candidate buttons are safest through Tenhou's own DOM event path. Some call buttons are
    // intermediate UI states rather than direct websocket payloads, so bypassing the click flow via
    // internal helpers can leave the browser and local app out of sync after chi/pon decisions.
    dispatchPointerSequence(target, x, y);
    return {
      ok: true,
      action: "click_control",
      controlId: normalizedControlId,
      text: controlText,
      dispatchTarget: describeElement(target),
      point: { x, y },
    };
  }

  function getSnapshot() {
    const layoutState = getLayoutExecutionState();
    const directDiscardReady = Boolean(getDirectDiscardExecutor());
    // `tenhouReady` means the page has enough UI-side information for the bridge to compute a
    // discard click point. Prefer page globals when exposed, but allow a standard-layout canvas
    // fallback so the local app can still drive Tenhou when those globals are not visible.
    return {
      ok: true,
      controls: readControls(),
      toggleControls: readToggleControls(),
      hasCanvas: layoutState.hasCanvas,
      tenhouReady: layoutState.ready || directDiscardReady,
      layoutMode: layoutState.layoutMode,
      missingGlobals: layoutState.missingGlobals,
      detectedHandSlotCount: Number(layoutState.detectedHandSlotCount || 0),
      slotStrategy: String(layoutState.slotStrategy || ""),
      directDiscardReady,
    };
  }

  function normalizeIntegerArray(value, minValue, maxValue) {
    if (!value || typeof value[Symbol.iterator] !== "function") {
      return [];
    }
    const normalized = [];
    for (const item of value) {
      const numericValue = Number(item);
      if (!Number.isInteger(numericValue)) {
        continue;
      }
      if (numericValue < minValue || numericValue > maxValue) {
        continue;
      }
      normalized.push(numericValue);
    }
    return normalized;
  }

  function normalizeScoreArray(value) {
    const scores = normalizeIntegerArray(value, -1000000, 1000000).slice(0, 4);
    if (scores.length < 4) {
      return [];
    }
    const maxAbsScore = scores.reduce(
      (currentMax, score) => Math.max(currentMax, Math.abs(Number(score) || 0)),
      0
    );
    if (maxAbsScore <= 1000) {
      return scores.map((score) => score * 100);
    }
    return scores;
  }

  function readTableRiverEntriesBySeat(riverState, seat) {
    const entries = [];
    const normalizedSeat = Number(seat) | 0;
    const tsumogiriBit = Number(window.X?.Aa || 0);
    for (let slotIndex = 0; slotIndex < 32; slotIndex += 1) {
      const slot = riverState?.[3072 | (normalizedSeat << 8) | slotIndex];
      if (!slot || typeof slot !== "object") {
        continue;
      }
      const tile34Index = Number(slot?.s?.Ie);
      if (!Number.isInteger(tile34Index) || tile34Index < 0 || tile34Index > 33) {
        continue;
      }
      const slotOwner = Number(slot?.L);
      entries.push({
        tile34Index,
        tsumogiri: tsumogiriBit > 0 ? Boolean(Number(slot?.la || 0) & tsumogiriBit) : false,
        riichiMarkerBefore: Number.isInteger(slotOwner) ? slotOwner !== normalizedSeat : false,
      });
    }
    return entries;
  }

  function getTableSnapshot() {
    const layoutState = getLayoutExecutionState();
    const roundState = getCapturedWindowObject("z");
    const handState = getCapturedWindowObject("q");
    const riverState = getCapturedWindowObject("U");
    const missingGlobals = [];
    if (!roundState) {
      missingGlobals.push("z");
    }
    if (!handState) {
      missingGlobals.push("q");
    }
    if (!riverState) {
      missingGlobals.push("U");
    }
    if (missingGlobals.length > 0) {
      return {
        ok: false,
        error: `TABLE_STATE_NOT_READY:${missingGlobals.join(",")}`,
        layoutMode: layoutState.layoutMode,
        tenhouReady: layoutState.ready,
      };
    }

    const seed = normalizeIntegerArray(roundState?.ia, 0, 135);
    const handTiles136 = normalizeIntegerArray(handState?.[32], 0, 135);
    const doraIndicators136 = seed.slice(5);
    const playerNames = Array.isArray(roundState?.O)
      ? roundState.O.slice(0, 4).map((value) => String(value || ""))
      : [];
    const riverEntriesBySeat = Array.from({ length: 4 }, (_unused, seat) =>
      readTableRiverEntriesBySeat(riverState, seat)
    );

    return {
      ok: true,
      handTiles136,
      doraIndicators136,
      playerNames,
      scores: normalizeScoreArray(roundState?.Na),
      kyokuIndex: Number.isInteger(Number(seed[0])) ? Number(seed[0]) : null,
      honba: Number.isInteger(Number(seed[1])) ? Number(seed[1]) : null,
      kyotaku: Number.isInteger(Number(seed[2])) ? Number(seed[2]) : null,
      oya: Number.isInteger(Number(roundState?.Ea)) ? Number(roundState.Ea) : null,
      riverEntriesBySeat,
      layoutMode: layoutState.layoutMode,
      tenhouReady: layoutState.ready || Boolean(getDirectDiscardExecutor()),
    };
  }

  function reply(payload) {
    window.postMessage(
      {
        type: PAGE_TO_EXTENSION,
        payload,
      },
      "*"
    );
  }

  function serializeError(error) {
    if (error instanceof Error) {
      return error.message || String(error);
    }
    return String(error);
  }

  function executeCommand(command) {
    // Keep the executor narrow and explicit. Adding a new UI operation should be a deliberate code
    // change here, not an arbitrary string accepted from the extension/service worker.
    if (command.type === "discard_by_index") {
      return discardByIndex(command.handIndex, command.visibleHandCount);
    }
    if (command.type === "click_control") {
      return clickControl(command.controlId);
    }
    throw new Error(`UNKNOWN_EXECUTE_TYPE: ${String(command.type)}`);
  }

  window[MAIN_WORLD_API_KEY] = {
    execute: executeCommand,
    getSnapshot,
    getTableSnapshot,
    version: BRIDGE_PROTOCOL_VERSION,
  };

  window.addEventListener("message", (event) => {
    if (event.source !== window) {
      return;
    }
    const data = event.data;
    if (!data || data.type !== EXTENSION_TO_PAGE) {
      return;
    }

    const payload = data.payload || {};
    if (payload.kind === "GET_SNAPSHOT") {
      emitMockTrace("get_snapshot_request", {
        kind: payload.kind,
        requestId: payload.requestId,
      });
      const result = getSnapshot();
      emitMockTrace("snapshot_result", {
        kind: "SNAPSHOT_RESULT",
        requestId: payload.requestId,
        result,
      });
      reply({
        kind: "SNAPSHOT_RESULT",
        requestId: payload.requestId,
        result,
      });
      return;
    }

    if (payload.kind === "EXECUTE") {
      const command = payload.command || {};
      emitMockTrace("execute_request", {
        command,
        kind: payload.kind,
        requestId: payload.requestId,
      });
      try {
        const result = executeCommand(command);
        emitMockTrace("execute_result", {
          kind: "EXECUTE_RESULT",
          requestId: payload.requestId,
          result,
        });
        reply({
          kind: "EXECUTE_RESULT",
          requestId: payload.requestId,
          result,
        });
      } catch (error) {
        const result = {
          ok: false,
          error: serializeError(error),
        };
        emitMockTrace("execute_error", {
          command,
          kind: "EXECUTE_RESULT",
          requestId: payload.requestId,
          result,
        });
        reply({
          kind: "EXECUTE_RESULT",
          requestId: payload.requestId,
          result,
        });
      }
    }
  });
})();
