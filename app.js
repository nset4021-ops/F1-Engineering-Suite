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
  pilotClass: "fictional", // "fictional" or "real"
  database: null // Cached specifications payload
};

const galacticPilots = [
  { value: "Apex One", text: "Apex One (Artificial Humanoid)" },
  { value: "Red Leader", text: "Red Leader (Veteran Ace)" },
  { value: "Vader", text: "Darth Vader (Sith Lord Pacemaker)" },
  { value: "Solo", text: "Han Solo (Smuggler Velocity)" }
];

const realPilots = [
  { value: "44", text: "Lewis Hamilton (No. 44)" },
  { value: "3", text: "Max Verstappen (No. 03)" },
  { value: "16", text: "Charles Leclerc (No. 16)" }
];

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
  pilotClassToggle: document.getElementById("pilotClassToggle"),
  simLabel: document.getElementById("simLabel"),
  realLabel: document.getElementById("realLabel"),
  pitwallSource: document.getElementById("pitwallSource"),
  pitwallCompound: document.getElementById("pitwallCompound"),
  pitwallLap: document.getElementById("pitwallLap"),
  pitwallGrip: document.getElementById("pitwallGrip"),
  pitwallSession: document.getElementById("pitwallSession"),
  pitwallWarning: document.getElementById("pitwallWarning"),
  pitwallWarningShell: document.getElementById("pitwallWarningShell"),
  suspensionSource: document.getElementById("suspensionSource"),
  camberSlider: document.getElementById("camberSlider"),
  chassisHeightSlider: document.getElementById("chassisHeightSlider"),
  suspensionMetrics: document.getElementById("suspensionMetrics"),
  telemetrySource: document.getElementById("telemetrySource"),
  telemetryCount: document.getElementById("telemetryCount"),
  pilotDossier: document.getElementById("pilotDossierBlock"),
  constructorBlueprint: document.getElementById("constructorBlueprintBlock"),
  suspensionCanvas: document.getElementById("suspensionCanvas"),
  camberOutput: document.getElementById("camberOutput"),
  heightOutput: document.getElementById("heightOutput")
};

function populateDrivers() {
  selectors.driverSelect.innerHTML = "";
  const list = state.pilotClass === "fictional" ? galacticPilots : realPilots;
  list.forEach(pilot => {
    const opt = document.createElement("option");
    opt.value = pilot.value;
    opt.textContent = pilot.text;
    selectors.driverSelect.appendChild(opt);
  });
  state.control.driver = list[0].value;
}

function handlePilotClassToggle() {
  if (selectors.pilotClassToggle.checked) {
    state.pilotClass = "real";
    selectors.realLabel.classList.add("active-opt");
    selectors.simLabel.classList.remove("active-opt");
  } else {
    state.pilotClass = "fictional";
    selectors.simLabel.classList.add("active-opt");
    selectors.realLabel.classList.remove("active-opt");
  }
  populateDrivers();
  updateDatabaseUI();
}

async function fetchDatabaseSpecs() {
  try {
    const response = await fetch("/api/specs");
    if (response.ok) {
      state.database = await response.json();
      updateDatabaseUI();
    }
  } catch (error) {
    console.error("Database sync failure:", error);
  }
}

function updateDatabaseUI() {
  if (!state.database) return;

  const activeDriver = state.control.driver;
  const activeTeam = state.control.team;

  const dSpecs = state.database.drivers[activeDriver] || {
    real_name: "Pro Professional",
    experience: "F1 Grid Experience",
    reflexes: "94/100",
    patience: "90/100",
    profile: "Elite championship contender mapping dynamic grip strategies."
  };

  const tSpecs = state.database.teams[activeTeam] || {
    engine: "F1 Specification V6 Engine Unit (1,000+ HP)",
    aero_drag: "High Efficiency",
    downforce_index: "9.0/10",
    specialty: "High structural velocity balance",
    lore: "Top-tier operational racing team competing for the ultimate constructors championship."
  };

  if (selectors.pilotDossier) {
    selectors.pilotDossier.innerHTML = `
      <div class="spec-item"><strong>Designation Label:</strong> <span>${activeDriver}</span></div>
      <div class="spec-item"><strong>Physical Matrix Identity:</strong> <span>${dSpecs.real_name}</span></div>
      <div class="spec-item"><strong>Active Career Cycles:</strong> <span>${dSpecs.experience}</span></div>
      <div class="spec-item"><strong>Synaptic Reflex Velocity:</strong> <span>${dSpecs.reflexes}</span></div>
      <div class="spec-item"><strong>Tactical Strategic Focus:</strong> <span>${dSpecs.patience}</span></div>
      <div class="spec-desc-block">
        <strong>Cognitive Tactical Profile:</strong>
        <p>${dSpecs.profile}</p>
      </div>
    `;
  }

  if (selectors.constructorBlueprint) {
    selectors.constructorBlueprint.innerHTML = `
      <div class="spec-item"><strong>Active Design Syndicate:</strong> <span>${activeTeam}</span></div>
      <div class="spec-item"><strong>Propulsion Core:</strong> <span>${tSpecs.engine}</span></div>
      <div class="spec-item"><strong>Aerodynamic Form Drag:</strong> <span>${tSpecs.aero_drag}</span></div>
      <div class="spec-item"><strong>System Wide Grip Load:</strong> <span>${tSpecs.downforce_index}</span></div>
      <div class="spec-item"><strong>Engineering Blueprint:</strong> <span>${tSpecs.specialty}</span></div>
      <div class="spec-desc-block">
        <strong>Syndicate Log:</strong>
        <p>${tSpecs.lore}</p>
      </div>
    `;
  }
}

async function requestAPI(endpoint, params = {}) {
  const query = new URLSearchParams(params).toString();
  const url = `/api/${endpoint}?${query}`;
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP Matrix error ${response.status}`);
    return await response.json();
  } catch (error) {
    console.warn(`Fallback active for payload: ${endpoint}`, error);
    return null;
  }
}

async function updateDashboardData() {
  const driverNum = isNaN(state.control.driver) ? 44 : parseInt(state.control.driver, 10);

  const [pw, tele, susp] = await Promise.all([
    requestAPI("pitwall", { driver_number: driverNum }),
    requestAPI("telemetry", {
      driver_number: driverNum,
      track_id: state.control.track,
      car_type: state.control.car,
      weather_type: state.control.weather
    }),
    requestAPI("suspension", { driver_number: driverNum })
  ]);

  if (pw) {
    state.pitwall = pw;
    renderPitwallUI();
  }
  if (tele) {
    state.telemetry = tele;
    renderTelemetryUI();
  }
  if (susp) {
    state.suspension = susp;
    updateSuspensionMetricsUI();
  }

  updateDatabaseUI();
  updateStatusBanner();
}

function renderPitwallUI() {
  const data = state.pitwall;
  selectors.pitwallSource.textContent = `SOURCE: ${data.source.toUpperCase()}`;
  selectors.pitwallCompound.textContent = data.compound;
  selectors.pitwallLap.textContent = data.lap_number;
  selectors.pitwallGrip.textContent = `${data.grip_level}%`;
  selectors.pitwallSession.textContent = `KEY: ${data.session_key}`;

  const laps = Array.from({ length: 45 }, (_, i) => i + 1);
  const compoundGrip = [];
  const startGrip = 100;
  
  let baseRate = 3.3;
  if (data.compound === "SOFT") baseRate = 4.8;
  else if (data.compound === "HARD") baseRate = 2.3;
  else if (data.compound === "INTERMEDIATE") baseRate = 3.8;
  else if (data.compound === "WET") baseRate = 4.2;

  laps.forEach(lap => {
    compoundGrip.push(Math.max(10, startGrip - (lap * baseRate)));
  });

  const gripTrace = {
    x: laps,
    y: compoundGrip,
    type: "scatter",
    mode: "lines",
    name: `${data.compound} Model`,
    line: { color: "cyan", width: 3, shape: "spline" }
  };

  const currentLapTrace = {
    x: [data.lap_number],
    y: [data.grip_level],
    type: "scatter",
    mode: "markers",
    name: "Telemetry Anchor",
    marker: { color: "red", size: 12, line: { color: "white", width: 2 } }
  };

  const layout = {
    margin: { l: 45, r: 20, t: 10, b: 40 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    xaxis: { title: "Laps Over Circuit", gridcolor: "rgba(120,120,120,0.16)" },
    yaxis: { title: "Grip Coeff (%)", gridcolor: "rgba(120,120,120,0.16)" },
    showlegend: false
  };

  Plotly.react("pitwallChart", [gripTrace, currentLapTrace], layout, { responsive: true, displayModeBar: false });

  if (data.grip_level < 45.0) {
    selectors.pitwallWarningShell.style.display = "block";
    selectors.pitwallWarning.classList.add("danger-neon-glow");
  } else {
    selectors.pitwallWarningShell.style.display = "none";
    selectors.pitwallWarning.classList.remove("danger-neon-glow");
  }
}

function updateSuspensionMetricsUI() {
  if (!state.suspension || !selectors.suspensionMetrics) return;
  selectors.suspensionSource.textContent = `SOURCE: ${state.suspension.source.toUpperCase()}`;
  selectors.suspensionMetrics.innerHTML = `
    <div class="metric-card">
      <p class="metric-label">Proxy Camber Factor</p>
      <h2>${state.suspension.camber_proxy}°</h2>
    </div>
  `;
}

function initSuspensionLab() {
  const canvas = selectors.suspensionCanvas;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  function drawSuspension() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const chInput = parseFloat(selectors.chassisHeightSlider.value);
    const cbInput = parseFloat(selectors.camberSlider.value) / 100.0;
    const baseChassisHeight = 220;
    const chassisY = baseChassisHeight + chInput;

    selectors.camberOutput.textContent = cbInput.toFixed(2);
    selectors.heightOutput.textContent = chInput.toFixed(0);

    // Draw grid background
    ctx.strokeStyle = "rgba(120, 120, 120, 0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    const chassisLeftX = 350;
    const chassisRightX = 630;
    const chassisTopY = chassisY - 80;
    const chassisBottomY = chassisY + 80;

    // Ground line
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    ctx.beginPath();
    ctx.moveTo(0, 480);
    ctx.lineTo(canvas.width, 480);
    ctx.stroke();

    // Chassis core block
    ctx.fillStyle = "rgba(12, 24, 48, 0.72)";
    ctx.strokeStyle = "cyan";
    ctx.lineWidth = 3;
    ctx.shadowColor = "cyan";
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.rect(chassisLeftX, chassisTopY, chassisRightX - chassisLeftX, chassisBottomY - chassisTopY);
    ctx.fill();
    ctx.stroke();

    // Inner lines inside chassis
    ctx.strokeStyle = "rgba(0, 255, 255, 0.25)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(chassisLeftX, chassisTopY);
    ctx.lineTo(chassisRightX, chassisBottomY);
    ctx.moveTo(chassisRightX, chassisTopY);
    ctx.lineTo(chassisLeftX, chassisBottomY);
    ctx.stroke();

    // Wishbone Links and Hub connections (Left/Right assembly lines)
    ctx.strokeStyle = "#ffbf00"; // Fixed: hex color instead of "amber"
    ctx.shadowColor = "#ffbf00";
    ctx.lineWidth = 4;
    
    // Left Assembly
    ctx.beginPath();
    ctx.moveTo(chassisLeftX, chassisTopY + 20); ctx.lineTo(180, 260); // Top wishbone
    ctx.moveTo(chassisLeftX, chassisBottomY - 20); ctx.lineTo(180, 370); // Bottom wishbone
    ctx.stroke();

    // Right Assembly
    ctx.beginPath();
    ctx.moveTo(chassisRightX, chassisTopY + 20); ctx.lineTo(800, 260);
    ctx.moveTo(chassisRightX, chassisBottomY - 20); ctx.lineTo(800, 370);
    ctx.stroke();

    // Draw Hubs with dynamic rotation based on Camber Slider input
    ctx.save();
    ctx.translate(180, 315);
    ctx.rotate(cbInput * Math.PI / 180);
    ctx.fillStyle = "#ff8a3d";
    ctx.fillRect(-15, -60, 30, 120);
    ctx.restore();

    ctx.save();
    ctx.translate(800, 315);
    ctx.rotate(-cbInput * Math.PI / 180);
    ctx.fillStyle = "#ff8a3d";
    ctx.fillRect(-15, -60, 30, 120);
    ctx.restore();

    // Turn off shadow blurs for text updates
    ctx.shadowBlur = 0;
  }

  selectors.camberSlider.addEventListener("input", drawSuspension);
  selectors.chassisHeightSlider.addEventListener("input", drawSuspension);
  drawSuspension();
}

function renderTelemetryUI() {
  const data = state.telemetry;
  selectors.telemetrySource.textContent = `SOURCE: ${data.source.toUpperCase()}`;
  selectors.telemetryCount.textContent = `SAMPLES: ${data.data.length}`;

  const speedTrace = {
    x: data.data.map(d => d.loop),
    y: data.data.map(d => d.speed),
    type: 'scatter',
    name: 'Speed (km/h)',
    line: { color: '#23d5ff' }
  };

  const throttleTrace = {
    x: data.data.map(d => d.loop),
    y: data.data.map(d => d.throttle),
    type: 'scatter',
    name: 'Throttle (%)',
    yaxis: 'y2',
    line: { color: '#2ed58f' }
  };

  const brakeTrace = {
    x: data.data.map(d => d.loop),
    y: data.data.map(d => d.brake),
    type: 'scatter',
    name: 'Brake (%)',
    yaxis: 'y3',
    line: { color: '#ffb14a' }
  };

  const layout = {
    grid: { rows: 3, columns: 1, pattern: 'coupled' },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    margin: { l: 50, r: 20, t: 10, b: 40 },
    xaxis: { gridcolor: "rgba(120,120,120,0.16)", title: "Time Frame Indices" },
    yaxis: { gridcolor: "rgba(120,120,120,0.16)", domain: [0.68, 1] },
    yaxis2: { gridcolor: "rgba(120,120,120,0.16)", domain: [0.34, 0.62] },
    yaxis3: { gridcolor: "rgba(120,120,120,0.16)", domain: [0, 0.28] }
  };

  Plotly.react("telemetryChart", [speedTrace, throttleTrace, brakeTrace], layout, { responsive: true, displayModeBar: false });

  // Draw 2D Route Plot
  const trackTrace = {
    x: data.data.map(d => d.x),
    y: data.data.map(d => d.y),
    type: 'scatter',
    mode: 'markers+lines',
    marker: {
      color: data.data.map(d => d.velocity_state),
      colorscale: [
        [0, '#ef4444'],
        [0.5, '#fbbf24'],
        [1, '#22c55e']
      ]
    },
    line: { color: 'rgba(255,255,255,0.15)' }
  };

  const trackLayout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: getComputedStyle(document.body).getPropertyValue("--text-primary").trim() },
    margin: { l: 40, r: 20, t: 10, b: 40 },
    xaxis: { gridcolor: "rgba(120,120,120,0.16)" },
    yaxis: { gridcolor: "rgba(120,120,120,0.16)", scaleanchor: "x", scaleratio: 1 }
  };

  Plotly.react("trackChart", [trackTrace], trackLayout, { responsive: true, displayModeBar: false });
}

function updateStatusBanner() {
  const activeSource = (state.pitwall?.source === "real" || state.telemetry?.source === "real") ? "Real Matrix Feed" : "Simulated Sandbox";
  selectors.apiHint.textContent = `Connected Link: ${activeSource}`;
  selectors.modeMetric.textContent = (state.pitwall?.source === "real") ? "Telemetry Active" : "Sandbox";
  selectors.weatherMetric.textContent = state.control.weather.toUpperCase();
  selectors.trackMetric.textContent = state.control.track.toUpperCase();
}

function initControlPanel() {
  populateDrivers();
  
  selectors.pilotClassToggle.addEventListener("change", handlePilotClassToggle);
  selectors.driverSelect.addEventListener("change", (e) => {
    state.control.driver = e.target.value;
    updateDatabaseUI();
  });
  selectors.teamSelect.addEventListener("change", (e) => {
    state.control.team = e.target.value;
    updateDatabaseUI();
  });
  selectors.carSelect.addEventListener("change", (e) => {
    state.control.car = e.target.value;
  });
  selectors.trackSelect.addEventListener("change", (e) => {
    state.control.track = e.target.value;
  });
  selectors.weatherSelect.addEventListener("change", (e) => {
    state.control.weather = e.target.value;
  });

  selectors.syncButton.addEventListener("click", () => {
    selectors.syncButton.textContent = "SYNCHRONIZING FEED CORRELATION...";
    selectors.syncButton.disabled = true;
    setTimeout(async () => {
      await updateDashboardData();
      selectors.syncButton.textContent = "INITIATE MATRIX HYPERSYNC";
      selectors.syncButton.disabled = false;
    }, 600);
  });
}

function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".panel");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      // Remove 'active' from all tab buttons and all layout panels
      tabs.forEach(t => t.classList.remove("active"));
      panels.forEach(p => p.classList.remove("active"));

      // Add 'active' to the clicked button
      tab.classList.add("active");
      
      // Reveal the exact targeted panel matching the dataset target attribute
      const target = tab.getAttribute("data-target");
      const activePanel = document.getElementById(target);
      if (activePanel) {
        activePanel.classList.add("active");
      }
      
      // Force Plotly graphics to resize inside their newly visible containers
      window.requestAnimationFrame(() => {
        ["pitwallChart", "telemetryChart", "trackChart"].forEach(chartId => {
          const el = document.getElementById(chartId);
          if (el && el.offsetParent !== null) {
            Plotly.Plots.resize(el);
          }
        });
        // Force the suspension lab layout to update its canvas drawing bounds
        if (target === "suspensionPanel") {
          initSuspensionLab();
        }
      });
    });
  });
}