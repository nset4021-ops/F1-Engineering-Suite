"use strict";

const DARK = "plotly_dark";

// ---- module tab switching ----
document.querySelectorAll(".module-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".module-tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".module-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(tab.dataset.module).classList.add("active");
  });
});

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = JSON.stringify(body.detail || body);
    } catch (_) {
      /* keep statusText */
    }
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json();
}

function makeMetric(label, value) {
  const wrap = document.createElement("div");
  wrap.className = "metric";
  const l = document.createElement("div");
  l.className = "label";
  l.textContent = label;
  const v = document.createElement("div");
  v.className = "value";
  v.textContent = value;
  wrap.append(l, v);
  return wrap;
}

function showError(container, message) {
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = message;
  container.replaceChildren(box);
}

// ---- Module 1: Strategy ----
async function runStrategy() {
  const driver = document.getElementById("strategy-driver").value;
  const session = document.getElementById("strategy-session").value;
  const caption = document.getElementById("strategy-caption");
  const warning = document.getElementById("strategy-warning");
  const metrics = document.getElementById("strategy-metrics");
  metrics.replaceChildren();
  warning.classList.add("hidden");

  let data;
  try {
    data = await getJSON(`/api/strategy?driver_number=${driver}&session_key=${session}`);
  } catch (err) {
    caption.textContent = "";
    showError(metrics, err.message);
    Plotly.purge("strategy-chart");
    return;
  }

  if (!data.laps || data.laps.length === 0) {
    caption.textContent = "No lap data available for strategy simulation.";
    Plotly.purge("strategy-chart");
    return;
  }

  caption.textContent = `Data source: ${data.data_source}`;
  metrics.append(
    makeMetric("Current Compound", data.current_compound),
    makeMetric("Latest Lap Time (s)", data.latest_lap_time.toFixed(3)),
    makeMetric("Theoretical Grip (%)", data.latest_grip.toFixed(1))
  );

  if (data.pit_recommended) {
    // textContent avoids HTML injection from the API-derived compound value.
    warning.textContent = `BOX BOX: Tyre grip low. Recommend Pit Stop for ${data.current_compound}.`;
    warning.classList.remove("hidden");
  }

  Plotly.newPlot(
    "strategy-chart",
    [
      {
        x: data.laps.map((l) => l.lap_number),
        y: data.laps.map((l) => l.lap_time),
        mode: "lines+markers",
        type: "scatter",
      },
    ],
    {
      template: DARK,
      title: "Real Lap Time Trend",
      xaxis: { title: "Lap" },
      yaxis: { title: "Lap Time (s)" },
    },
    { responsive: true }
  );
}

// ---- Module 2: Suspension ----
async function runSuspension() {
  const roll = document.getElementById("susp-roll").value;
  const length = document.getElementById("susp-length").value;
  document.getElementById("susp-roll-val").textContent = Number(roll).toFixed(1);
  document.getElementById("susp-length-val").textContent = length;
  const metrics = document.getElementById("susp-metrics");

  let data;
  try {
    data = await getJSON(`/api/suspension?roll_angle=${roll}&wishbone_length=${length}`);
  } catch (err) {
    showError(metrics, err.message);
    return;
  }

  metrics.replaceChildren(
    makeMetric("Resulting Camber Angle Change (°)", data.camber_change.toFixed(2))
  );

  Plotly.newPlot(
    "susp-geometry",
    [
      {
        x: data.geometry.map((p) => p.x),
        y: data.geometry.map((p) => p.y),
        mode: "lines+markers",
        type: "scatter",
        line: { width: 4, color: "#22d3ee" },
        marker: { size: 10, color: "#f97316" },
      },
    ],
    {
      template: DARK,
      title: "Double-Wishbone Geometry (2D Schematic)",
      xaxis: { title: "Lateral Position" },
      yaxis: { title: "Vertical Position", scaleanchor: "x", scaleratio: 1 },
      showlegend: false,
    },
    { responsive: true }
  );

  Plotly.newPlot(
    "susp-curve",
    [
      {
        x: data.camber_curve.map((p) => p.roll_angle),
        y: data.camber_curve.map((p) => p.camber_change),
        mode: "lines",
        type: "scatter",
      },
    ],
    {
      template: DARK,
      title: "Camber Change vs. Roll Angle",
      xaxis: { title: "Roll Angle" },
      yaxis: { title: "Camber Change" },
    },
    { responsive: true }
  );
}

// ---- Module 3: Telemetry ----
async function runTelemetry() {
  const driver = document.getElementById("tel-driver").value;
  const session = document.getElementById("tel-session").value;
  const caption = document.getElementById("tel-caption");

  let data;
  try {
    data = await getJSON(`/api/telemetry?driver_number=${driver}&session_key=${session}`);
  } catch (err) {
    caption.textContent = "";
    showError(caption.parentElement, err.message);
    Plotly.purge("tel-trend");
    Plotly.purge("tel-track");
    return;
  }

  const samples = data.samples || [];
  if (samples.length === 0) {
    caption.textContent = "Unable to align telemetry and location data.";
    Plotly.purge("tel-trend");
    Plotly.purge("tel-track");
    return;
  }

  caption.textContent = `Data source: ${data.data_source}`;
  const ts = samples.map((s) => new Date(s.ts));

  Plotly.newPlot(
    "tel-trend",
    ["speed", "throttle", "brake"].map((sig) => ({
      x: ts,
      y: samples.map((s) => s[sig]),
      mode: "lines",
      type: "scatter",
      name: sig,
    })),
    {
      template: DARK,
      title: "Speed, Throttle, and Braking Over Time",
    },
    { responsive: true }
  );

  Plotly.newPlot(
    "tel-track",
    [
      {
        x: samples.map((s) => s.x),
        y: samples.map((s) => s.y),
        mode: "markers",
        type: "scatter",
        marker: {
          size: 8,
          opacity: 0.85,
          color: samples.map((s) => s.velocity_state),
          colorscale: [
            [0.0, "#ef4444"],
            [0.5, "#fbbf24"],
            [1.0, "#22c55e"],
          ],
        },
      },
    ],
    {
      template: DARK,
      title: "Track Map (Red = Braking, Green = Acceleration)",
      yaxis: { scaleanchor: "x", scaleratio: 1 },
    },
    { responsive: true }
  );
}

// ---- wiring ----
document.getElementById("strategy-run").addEventListener("click", runStrategy);
document.getElementById("tel-run").addEventListener("click", runTelemetry);
document.getElementById("susp-roll").addEventListener("input", runSuspension);
document.getElementById("susp-length").addEventListener("input", runSuspension);

// initial render
runStrategy();
runSuspension();
