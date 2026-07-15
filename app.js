const state = {
  pitwall: null,
  suspension: null,
  telemetry: null,
  control: {
    driver: "Apex One",
    team: "Astral Works",
    car: "Balanced",
    track: "monza",
    weather: "dry",
  },
  simulatorActive: false,
};

const selectors = {
  apiStatus: document.getElementById("apiStatus"),
  apiHint: document.getElementById("apiHint"),
  modeMetric: document.getElementById("modeMetric"),
  weatherMetric: document.getElementById("weatherMetric"),
  trackMetric: document.getElementById("trackMetric"),
  driverSelect: document.getElementById("driverSelect"),
  teamSelect: document.getElementById("teamSelect"),
  carSelect: document.getElementById("carSelect"),
  trackSelect: document.getElementById("trackSelect"),
  weatherSelect: document.getElementById("weatherSelect"),
  syncButton: document.getElementById("syncButton"),
  pitwallSource: document.getElementById("pitwallSource"),
  pitwallCompound: document.getElementById("pitwallCompound"),
  pitwallLap: document.getElementById("pitwallLap"),
  pitwallGrip: document.getElementById("pitwallGrip"),
  pitwallSession: document.getElementById("pitwallSession"),
  pitwallWarning: document.getElementById("pitwallWarning"),
  pitwallWarningShell: document.getElementById("pitwallWarningShell"),
  suspensionSource: document.getElementById("suspensionSource"),
  camberOutput: document.getElementById("camberOutput"),
  rollSlider: document.getElementById("rollSlider"),
  wishboneSlider: document.getElementById("wishboneSlider"),
  rollValue: document.getElementById("rollValue"),
  wishboneValue: document.getElementById("wishboneValue"),
  suspensionMetrics: document.getElementById("suspensionMetrics"),
  telemetrySource: document.getElementById("telemetrySource"),
  telemetryCount: document.getElementById("telemetryCount"),
  suspensionCanvas: document.getElementById("suspensionCanvas"),
};

const constants = {
  drivers: ["Apex One", "Nova Rhea", "Orion Vale", "Lyra Bolt"],
  teams: ["Astral Works", "Nebula GP", "Solaris Racing", "Andromeda Speed"],
  cars: ["Balanced", "Light", "Downforce", "Weight"],
  tracks: ["monza", "silverstone", "spa", "baku", "default"],
  weather: ["dry", "damp", "wet"],
};

function formatRound(value, decimals = 1) {
  return Number.isFinite(value) ? value.toFixed(decimals) : "-";
}

function apiUrl(path) {
  const params = new URLSearchParams({ session_key: "9839", driver_number: "44" });
  return `${path}?${params.toString()}`;
}

function controlUrl() {
  const params = new URLSearchParams(state.control);
  return `/api/control?${params.toString()}`;
}

async function fetchJSON(path) {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }
  return response.json();
}

async function fetchControlJSON() {
  const response = await fetch(controlUrl(), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Sandbox request failed with ${response.status}`);
  }
  return response.json();
}

function setStatus(message, subtle = false) {
  selectors.apiStatus.textContent = message;
  selectors.apiHint.textContent = subtle
    ? "Switching to deterministic fallback data keeps the dashboard responsive during API outages."
    : "Public OpenF1 data is flowing into the suite.";
}

function populateSelect(select, values) {
  select.innerHTML = values.map((value) => `<option value="${value}">${value}</option>`).join("");
}

function syncThemeMetrics() {
  selectors.modeMetric.textContent = state.simulatorActive ? "Sandbox" : "OpenF1";
  selectors.weatherMetric.textContent = state.control.weather.charAt(0).toUpperCase() + state.control.weather.slice(1);
  selectors.trackMetric.textContent = state.control.track.charAt(0).toUpperCase() + state.control.track.slice(1);
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab-button"));
  const panels = Array.from(document.querySelectorAll(".panel"));

  function activate(tabName) {
    tabs.forEach((button) => button.classList.toggle("active", button.dataset.tab === tabName));
    panels.forEach((panel) => panel.classList.toggle("active", panel.id === tabName));
    window.requestAnimationFrame(() => {
      ["pitwallChart", "suspensionChart", "telemetryChart", "trackChart"].forEach((chartId) => {
        const target = document.getElementById(chartId);
        if (target && target.offsetParent !== null && window.Plotly) {
          Plotly.Plots.resize(target);
        }
      });
    });
  }

  tabs.forEach((button) => button.addEventListener("click", () => activate(button.dataset.tab)));
}

function initControlPanel() {
  populateSelect(selectors.driverSelect, constants.drivers);
  populateSelect(selectors.teamSelect, constants.teams);
  populateSelect(selectors.carSelect, constants.cars);
  populateSelect(selectors.trackSelect, constants.tracks);
  populateSelect(selectors.weatherSelect, constants.weather);

  selectors.driverSelect.value = state.control.driver;
  selectors.teamSelect.value = state.control.team;
  selectors.carSelect.value = state.control.car;
  selectors.trackSelect.value = state.control.track;
  selectors.weatherSelect.value = state.control.weather;

  const updateControl = () => {
    state.control = {
      driver: selectors.driverSelect.value,
      team: selectors.teamSelect.value,
      car: selectors.carSelect.value,
      track: selectors.trackSelect.value,
      weather: selectors.weatherSelect.value,
    };
    syncThemeMetrics();
  };

  [selectors.driverSelect, selectors.teamSelect, selectors.carSelect, selectors.trackSelect, selectors.weatherSelect].forEach((element) => {
    element.addEventListener("change", updateControl);
  });

  selectors.syncButton.addEventListener("click", async () => {
    state.simulatorActive = true;
    syncThemeMetrics();
    await refreshDashboard();
  });
}

function buildPitwallChart(data, progress = data.length) {
  const slice = data.slice(0, Math.max(1, progress));
  const laps = slice.map((row) => row.lap_number);
  const lapTimes = slice.map((row) => row.lap_time);
  const grips = slice.map((row) => row.grip);

  const traces = [
    {
      x: laps,
      y: lapTimes,
      mode: "lines+markers",
      name: "Lap Time (s)",
      line: { width: 3, color: "#4fa3ff" },
      marker: { size: 8, color: "#4fa3ff" },
    },
    {
      x: laps,
      y: grips,
      mode: "lines+markers",
      name: "Grip (%)",
      yaxis: "y2",
      line: { width: 3, color: "#ff7b61" },
      marker: { size: 8, color: "#ff7b61" },
    },
  ];

  const layout = {
    margin: { l: 55, r: 45, t: 10, b: 50 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    xaxis: { title: "Lap", gridcolor: "rgba(120,120,120,0.16)" },
    yaxis: { title: "Lap Time (s)", gridcolor: "rgba(120,120,120,0.16)" },
    yaxis2: {
      title: "Grip (%)",
      overlaying: "y",
      side: "right",
      range: [0, 100],
      gridcolor: "rgba(120,120,120,0.16)",
    },
    legend: { orientation: "h", y: 1.12, x: 0 },
    transition: { duration: 220 },
    shapes: [
      {
        type: "line",
        x0: laps[0] ?? 0,
        x1: laps[laps.length - 1] ?? 1,
        y0: 45,
        y1: 45,
        line: { color: "#ff4b4b", width: 1.5, dash: "dot" },
      },
    ],
  };

  Plotly.react("pitwallChart", traces, layout, { responsive: true, displayModeBar: false });

  const currentGrip = grips[grips.length - 1] ?? 100;
  const latestLap = laps[laps.length - 1] ?? 0;
  const compound = slice[slice.length - 1]?.compound ?? "UNKNOWN";

  selectors.pitwallLap.textContent = String(latestLap);
  selectors.pitwallGrip.textContent = `${formatRound(currentGrip, 1)}%`;
  selectors.pitwallCompound.textContent = `Compound: ${compound}`;
  selectors.pitwallWarning.textContent = currentGrip < 45 ? "BOX BOX: grip below race threshold" : "Tyre delta is under control";
  selectors.pitwallWarningShell.classList.toggle("flash-warning", currentGrip < 45);

  return currentGrip;
}

function animatePitwall(data) {
  let frame = 1;
  const maxFrame = Math.max(data.length, 1);

  buildPitwallChart(data, frame);

  const timer = window.setInterval(() => {
    frame += 1;
    const grip = buildPitwallChart(data, Math.min(frame, maxFrame));
    if (frame >= maxFrame) {
      window.clearInterval(timer);
      if (grip < 45) {
        selectors.pitwallWarningShell.classList.add("flash-warning");
      }
    }
  }, 420);
}

async function refreshDashboard() {
  const useSandbox = state.simulatorActive;
  let pitwallPayload;
  let suspensionPayload;
  let telemetryPayload;

  if (useSandbox) {
    const control = await fetchControlJSON();
    pitwallPayload = control.pitwall;
    suspensionPayload = {
      source: control.suspension.source,
      defaults: {
        roll_angle_deg: 0,
        wishbone_length_mm: 420,
        chassis_half_width_mm: 220,
        upright_height_mm: 165,
      },
      summary: {
        average_speed: Number(control.track_profile.base_speed.toFixed(2)),
        peak_brake: Number((100 - control.weather_profile.grip * 10).toFixed(2)),
        mean_throttle: Number((80 - (control.car_profile.mass - 800) * 0.4).toFixed(2)),
        sample_count: control.telemetry.data.length,
      },
    };
    telemetryPayload = control.telemetry;
  } else {
    const [pitwall, suspension, telemetry] = await Promise.allSettled([
      fetchJSON("/api/pitwall"),
      fetchJSON("/api/suspension"),
      fetchJSON("/api/telemetry"),
    ]);

    if (pitwall.status === "fulfilled") pitwallPayload = pitwall.value;
    if (suspension.status === "fulfilled") suspensionPayload = suspension.value;
    if (telemetry.status === "fulfilled") telemetryPayload = telemetry.value;
  }

  if (pitwallPayload) {
    state.pitwall = pitwallPayload;
    selectors.pitwallSource.textContent = `Source: ${state.pitwall.source}`;
    selectors.pitwallSession.textContent = String(state.pitwall.session_key ?? 9839);
    selectors.pitwallCompound.textContent = `Compound: ${state.pitwall.compound ?? "UNKNOWN"}`;
    animatePitwall(state.pitwall.data);
  }

  if (suspensionPayload) {
    state.suspension = suspensionPayload;
    selectors.suspensionSource.textContent = `Source: ${state.suspension.source}`;
    renderSuspension(state.suspension);
  }

  if (telemetryPayload) {
    state.telemetry = telemetryPayload;
    selectors.telemetrySource.textContent = `Source: ${state.telemetry.source?.car_data ?? state.telemetry.source ?? "sandbox"}`;
    renderTelemetry(state.telemetry);
  }

  if (useSandbox) {
    setStatus("Sandbox simulator engaged. OpenF1 requests paused.", false);
  } else {
    setStatus("Live feeds ready with local cache protection.", false);
  }
}

function updateSuspensionMetrics(payload, camber) {
  const summary = payload.summary ?? {};
  selectors.camberOutput.textContent = `Camber: ${formatRound(camber, 2)}°`;
  selectors.suspensionMetrics.innerHTML = `
    <div class="summary-card"><span>Average Speed</span><strong>${formatRound(summary.average_speed, 1)} km/h</strong></div>
    <div class="summary-card"><span>Peak Brake</span><strong>${formatRound(summary.peak_brake, 1)}%</strong></div>
    <div class="summary-card"><span>Mean Throttle</span><strong>${formatRound(summary.mean_throttle, 1)}%</strong></div>
    <div class="summary-card"><span>Samples</span><strong>${summary.sample_count ?? 0}</strong></div>
  `;
}

function drawSuspensionCanvas(payload) {
  const canvas = selectors.suspensionCanvas;
  const context = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const deviceRatio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * deviceRatio);
  canvas.height = Math.floor(Math.max(rect.height, 420) * deviceRatio);
  context.setTransform(deviceRatio, 0, 0, deviceRatio, 0, 0);

  const width = rect.width;
  const height = Math.max(rect.height, 420);
  const centerX = width * 0.52;
  const centerY = height * 0.5;
  const roll = Number(selectors.rollSlider.value) * Math.PI / 180;
  const wishbone = Number(selectors.wishboneSlider.value);
  const scale = wishbone / 4.2;
  const upperOffset = { x: Math.cos(roll) * scale, y: -Math.sin(roll) * scale * 0.6 };
  const lowerOffset = { x: Math.cos(roll + 0.12) * scale * 1.05, y: Math.sin(roll + 0.12) * scale * 0.55 };
  const uprightTop = { x: centerX + Math.sin(roll) * 64, y: centerY - 106 };
  const uprightBottom = { x: centerX - Math.sin(roll) * 40, y: centerY + 104 };
  const glow = selectors.pitwallWarningShell.classList.contains("flash-warning") ? 1 : 0.35;

  context.clearRect(0, 0, width, height);
  context.fillStyle = getComputedStyle(document.body).getPropertyValue("--bg-canvas").trim();
  context.fillRect(0, 0, width, height);

  context.strokeStyle = "rgba(94, 255, 248, 0.12)";
  for (let x = 0; x < width; x += 32) {
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }
  for (let y = 0; y < height; y += 32) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  const drawLink = (from, to, color, lineWidth = 4) => {
    context.shadowBlur = 18;
    context.shadowColor = color;
    context.strokeStyle = color;
    context.lineWidth = lineWidth;
    context.beginPath();
    context.moveTo(from.x, from.y);
    context.lineTo(to.x, to.y);
    context.stroke();
  };

  const baseTopLeft = { x: centerX - 180, y: centerY - 130 };
  const baseTopRight = { x: centerX + 180, y: centerY - 130 };
  const baseBottomLeft = { x: centerX - 180, y: centerY + 130 };
  const baseBottomRight = { x: centerX + 180, y: centerY + 130 };

  drawLink(baseTopLeft, { x: centerX - 36, y: centerY - 28 }, `rgba(94, 255, 248, ${0.85 + glow * 0.15})`);
  drawLink(baseTopRight, { x: centerX + 38, y: centerY - 26 }, `rgba(255, 182, 67, ${0.9})`);
  drawLink(baseBottomLeft, { x: centerX - 40, y: centerY + 28 }, `rgba(255, 182, 67, ${0.9})`);
  drawLink(baseBottomRight, { x: centerX + 36, y: centerY + 30 }, `rgba(94, 255, 248, ${0.85 + glow * 0.15})`);
  drawLink({ x: centerX - 36, y: centerY - 28 }, uprightTop, `rgba(94, 255, 248, ${0.95})`, 5);
  drawLink({ x: centerX + 38, y: centerY - 26 }, uprightTop, `rgba(255, 182, 67, ${0.95})`, 5);
  drawLink({ x: centerX - 40, y: centerY + 28 }, uprightBottom, `rgba(255, 182, 67, ${0.95})`, 5);
  drawLink({ x: centerX + 36, y: centerY + 30 }, uprightBottom, `rgba(94, 255, 248, ${0.95})`, 5);

  context.shadowBlur = 28;
  context.shadowColor = "rgba(94,255,248,0.9)";
  context.strokeStyle = "rgba(220,245,255,0.88)";
  context.lineWidth = 8;
  context.beginPath();
  context.moveTo(uprightTop.x, uprightTop.y);
  context.lineTo(uprightBottom.x, uprightBottom.y);
  context.stroke();

  context.fillStyle = "rgba(0, 0, 0, 0.28)";
  context.strokeStyle = "rgba(94, 255, 248, 0.85)";
  context.lineWidth = 2;
  [baseTopLeft, baseTopRight, baseBottomLeft, baseBottomRight, uprightTop, uprightBottom].forEach((point) => {
    context.beginPath();
    context.arc(point.x, point.y, 8, 0, Math.PI * 2);
    context.fill();
    context.stroke();
  });

  context.fillStyle = selectors.pitwallWarningShell.classList.contains("flash-warning") ? "rgba(255, 68, 68, 0.95)" : "rgba(94, 255, 248, 0.9)";
  context.font = '700 18px "IBM Plex Mono", monospace';
  context.fillText(`Camber ${formatRound(Number(selectors.camberOutput.textContent.replace(/[^0-9.-]/g, "")) || 0, 2)}°`, 22, 34);
  context.fillText(`Wishbone ${wishbone.toFixed(0)} mm`, 22, 58);

  updateSuspensionMetrics(payload, Number(selectors.camberOutput.textContent.replace(/[^0-9.-]/g, "")) || 0);
}

function computeSuspensionGeometry(rollAngleDeg, wishboneLengthMm, defaults = {}) {
  const rollRad = (rollAngleDeg * Math.PI) / 180;
  const chassisHalfWidth = defaults.chassis_half_width_mm ?? 220;
  const uprightHeight = defaults.upright_height_mm ?? 165;
  const wheelShift = wishboneLengthMm * Math.sin(rollRad) * 0.45;
  const camberDeg = -(Math.atan2(wheelShift, wishboneLengthMm) * 180) / Math.PI;
  const wheelCenterX = wheelShift;
  const wheelCenterY = uprightHeight;

  const leftChassis = { x: -chassisHalfWidth, y: 0 };
  const rightChassis = { x: chassisHalfWidth, y: 0 };
  const upperInner = { x: -chassisHalfWidth * 0.38, y: 108 };
  const upperOuter = { x: wheelCenterX, y: wheelCenterY + 36 };
  const lowerInner = { x: -chassisHalfWidth * 0.42, y: 38 };
  const lowerOuter = { x: wheelCenterX, y: wheelCenterY - 44 };

  return {
    camberDeg,
    traces: [
      {
        x: [leftChassis.x, rightChassis.x],
        y: [leftChassis.y, rightChassis.y],
        mode: "lines+markers",
        name: "Chassis",
        line: { width: 4, color: "#7ab7ff" },
        marker: { size: 9, color: "#7ab7ff" },
      },
      {
        x: [upperInner.x, upperOuter.x],
        y: [upperInner.y, upperOuter.y],
        mode: "lines+markers",
        name: "Upper Wishbone",
        line: { width: 4, color: "#ff7b61" },
        marker: { size: 9, color: "#ff7b61" },
      },
      {
        x: [lowerInner.x, lowerOuter.x],
        y: [lowerInner.y, lowerOuter.y],
        mode: "lines+markers",
        name: "Lower Wishbone",
        line: { width: 4, color: "#18b37e" },
        marker: { size: 9, color: "#18b37e" },
      },
      {
        x: [wheelCenterX, wheelCenterX],
        y: [wheelCenterY - 66, wheelCenterY + 66],
        mode: "lines+markers",
        name: "Upright",
        line: { width: 5, color: "#f4d35e" },
        marker: { size: 9, color: "#f4d35e" },
      },
      {
        x: [wheelCenterX],
        y: [wheelCenterY],
        mode: "markers",
        name: "Wheel Center",
        marker: { size: 15, color: "#ffffff", line: { width: 2, color: "#1f7aec" } },
      },
    ],
    layout: {
      margin: { l: 45, r: 20, t: 10, b: 45 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
      xaxis: { title: "Lateral Position", zeroline: false, gridcolor: "rgba(120,120,120,0.16)" },
      yaxis: { title: "Vertical Position", zeroline: false, gridcolor: "rgba(120,120,120,0.16)", scaleanchor: "x", scaleratio: 1 },
      legend: { orientation: "h", y: 1.08, x: 0 },
    },
  };
}

function renderSuspension(payload) {
  const defaults = payload.defaults ?? {};
  const initialRoll = Number(defaults.roll_angle_deg ?? 0);
  const initialWishbone = Number(defaults.wishbone_length_mm ?? 420);

  selectors.rollSlider.value = String(initialRoll);
  selectors.wishboneSlider.value = String(initialWishbone);
  selectors.rollValue.textContent = `${formatRound(initialRoll, 1)}°`;
  selectors.wishboneValue.textContent = `${formatRound(initialWishbone, 0)} mm`;
  selectors.suspensionSource.textContent = `Source: ${payload.source ?? "real"}`;

  const draw = () => {
    const roll = Number(selectors.rollSlider.value);
    const wishbone = Number(selectors.wishboneSlider.value);
    const geometry = computeSuspensionGeometry(roll, wishbone, defaults);
    selectors.rollValue.textContent = `${formatRound(roll, 1)}°`;
    selectors.wishboneValue.textContent = `${formatRound(wishbone, 0)} mm`;
    selectors.camberOutput.textContent = `Camber: ${formatRound(geometry.camberDeg, 2)}°`;
    drawSuspensionCanvas({ ...payload, camber: geometry.camberDeg });
  };

  selectors.rollSlider.addEventListener("input", draw);
  selectors.wishboneSlider.addEventListener("input", draw);
  draw();
}

function renderTelemetry(payload) {
  const rows = payload.data ?? [];
  const dates = rows.map((row) => row.date);
  const speed = rows.map((row) => row.speed);
  const throttle = rows.map((row) => row.throttle);
  const brake = rows.map((row) => row.brake);
  const x = rows.map((row) => row.x);
  const y = rows.map((row) => row.y);

  selectors.telemetrySource.textContent = `Source: ${payload.source?.car_data ?? "real"} / ${payload.source?.location ?? "real"}`;
  selectors.telemetryCount.textContent = `Samples: ${rows.length}`;

  const traces = [
    {
      x: dates,
      y: speed,
      type: "scatter",
      mode: "lines",
      name: "Speed",
      xaxis: "x",
      yaxis: "y",
      line: { color: "#4fa3ff", width: 3 },
    },
    {
      x: dates,
      y: throttle,
      type: "scatter",
      mode: "lines",
      name: "Throttle",
      xaxis: "x2",
      yaxis: "y2",
      line: { color: "#18b37e", width: 3 },
    },
    {
      x: dates,
      y: brake,
      type: "scatter",
      mode: "lines",
      name: "Brake",
      xaxis: "x3",
      yaxis: "y3",
      line: { color: "#ff7b61", width: 3 },
    },
  ];

  const telemetryLayout = {
    margin: { l: 60, r: 30, t: 10, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    showlegend: false,
    xaxis: {
      domain: [0, 1],
      anchor: "y",
      showticklabels: false,
      gridcolor: "rgba(120,120,120,0.16)",
    },
    yaxis: {
      domain: [0.72, 1],
      title: "Speed",
      gridcolor: "rgba(120,120,120,0.16)",
    },
    xaxis2: {
      domain: [0, 1],
      anchor: "y2",
      matches: "x",
      showticklabels: false,
      gridcolor: "rgba(120,120,120,0.16)",
    },
    yaxis2: {
      domain: [0.37, 0.62],
      title: "Throttle",
      gridcolor: "rgba(120,120,120,0.16)",
    },
    xaxis3: {
      domain: [0, 1],
      anchor: "y3",
      matches: "x",
      gridcolor: "rgba(120,120,120,0.16)",
    },
    yaxis3: {
      domain: [0, 0.26],
      title: "Brake",
      gridcolor: "rgba(120,120,120,0.16)",
    },
    annotations: [
      { text: "Speed", x: 0.01, y: 1, xref: "paper", yref: "paper", showarrow: false, font: { size: 12 } },
      { text: "Throttle", x: 0.01, y: 0.63, xref: "paper", yref: "paper", showarrow: false, font: { size: 12 } },
      { text: "Brake", x: 0.01, y: 0.27, xref: "paper", yref: "paper", showarrow: false, font: { size: 12 } },
    ],
    height: 640,
    shapes: [
      {
        type: "line",
        x0: dates[0],
        x1: dates[dates.length - 1],
        y0: 0,
        y1: 0,
        xref: "x",
        yref: "y3",
        line: { color: "rgba(94,255,248,0.12)", width: 1, dash: "dot" },
      },
    ],
  };

  Plotly.react("telemetryChart", traces, telemetryLayout, { responsive: true, displayModeBar: false });

  const maxSpeed = Math.max(...speed, 1);
  const trackTrace = {
    x,
    y,
    type: "scatter",
    mode: "markers+lines",
    marker: {
      size: 8,
      color: speed,
      colorscale: [
        [0, "#ff6b6b"],
        [0.5, "#f4d35e"],
        [1, "#18b37e"],
      ],
      cmin: 0,
      cmax: maxSpeed,
      colorbar: { title: "Velocity" },
    },
    line: { color: "rgba(255,255,255,0.2)", width: 2 },
    hovertemplate: "x=%{x:.1f}<br>y=%{y:.1f}<br>speed=%{marker.color:.1f}<extra></extra>",
  };

  const trackLayout = {
    margin: { l: 45, r: 20, t: 10, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    xaxis: { title: "X Position", gridcolor: "rgba(120,120,120,0.16)" },
    yaxis: { title: "Y Position", gridcolor: "rgba(120,120,120,0.16)", scaleanchor: "x", scaleratio: 1 },
  };

  Plotly.react("trackChart", [trackTrace], trackLayout, { responsive: true, displayModeBar: false });
}

async function initializeDashboard() {
  initControlPanel();
  initTabs();
  await refreshDashboard();
}

window.addEventListener("resize", () => {
  ["pitwallChart", "suspensionChart", "telemetryChart", "trackChart"].forEach((chartId) => {
    const target = document.getElementById(chartId);
    if (target && window.Plotly) {
      Plotly.Plots.resize(target);
    }
  });
  if (selectors.suspensionCanvas) {
    drawSuspensionCanvas(state.suspension ?? { summary: {} });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  initializeDashboard().catch((error) => {
    setStatus(`Dashboard boot failed: ${error.message}`, true);
  });
});