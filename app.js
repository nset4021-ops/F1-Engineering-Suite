const state = {
  pitwall: null,
  suspension: null,
  telemetry: null,
};

const selectors = {
  apiStatus: document.getElementById("apiStatus"),
  apiHint: document.getElementById("apiHint"),
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
};

function formatRound(value, decimals = 1) {
  return Number.isFinite(value) ? value.toFixed(decimals) : "-";
}

function apiUrl(path) {
  return `${path}?session_key=9839&driver_number=44`;
}

async function fetchJSON(path) {
  const response = await fetch(apiUrl(path), { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }
  return response.json();
}

function setStatus(message, subtle = false) {
  selectors.apiStatus.textContent = message;
  selectors.apiHint.textContent = subtle
    ? "Switching to deterministic fallback data keeps the dashboard responsive during API outages."
    : "Public OpenF1 data is flowing into the suite.";
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
    Plotly.react("suspensionChart", geometry.traces, geometry.layout, { responsive: true, displayModeBar: false });
    updateSuspensionMetrics(payload, geometry.camberDeg);
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
  initTabs();

  const [pitwall, suspension, telemetry] = await Promise.allSettled([
    fetchJSON("/api/pitwall"),
    fetchJSON("/api/suspension"),
    fetchJSON("/api/telemetry"),
  ]);

  if (pitwall.status === "fulfilled") {
    state.pitwall = pitwall.value;
    selectors.pitwallSource.textContent = `Source: ${state.pitwall.source}`;
    selectors.pitwallSession.textContent = String(state.pitwall.session_key);
    selectors.apiStatus.textContent = "Connected to OpenF1 + mock fallback backend";
    animatePitwall(state.pitwall.data);
  } else {
    setStatus("Using fallback pit wall data", true);
  }

  if (suspension.status === "fulfilled") {
    state.suspension = suspension.value;
    renderSuspension(state.suspension);
  } else {
    selectors.suspensionSource.textContent = "Source: fallback";
  }

  if (telemetry.status === "fulfilled") {
    state.telemetry = telemetry.value;
    renderTelemetry(state.telemetry);
  } else {
    selectors.telemetrySource.textContent = "Source: fallback";
  }

  if (pitwall.status === "rejected" || suspension.status === "rejected" || telemetry.status === "rejected") {
    setStatus("One or more feeds used fallback data", true);
  } else {
    setStatus("Live feeds ready", false);
  }
}

window.addEventListener("resize", () => {
  ["pitwallChart", "suspensionChart", "telemetryChart", "trackChart"].forEach((chartId) => {
    const target = document.getElementById(chartId);
    if (target && window.Plotly) {
      Plotly.Plots.resize(target);
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  initializeDashboard().catch((error) => {
    setStatus(`Dashboard boot failed: ${error.message}`, true);
  });
});