// ── SOCKET ──────────────────────────────────────────────
const socket = io();

function sendTyped() {
  const inp = document.getElementById("type-input");
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = "";
  addChat("user", txt);
  socket.emit("typed_message", { text: txt });
}

function wakeUpManual() {
  socket.emit("manual_wake", {});
}

socket.on("connect",    () => setDebug("E.D.I.T.H. backend connected"));
socket.on("disconnect", () => setDebug("Backend connection lost"));

socket.on("state_change",  d => updateState(d.state, d.message));
socket.on("chat_message",  d => { addChat(d.role, d.text); addMapChat(d.role, d.text); });
socket.on("debug",         d => { setDebug(d.text); });
socket.on("mic_level",     d => updateMic(d.value, d.threshold));
socket.on("waveform_data", d => renderWaveform(d.samples));
socket.on("sysinfo",       d => updateSysInfo(d));
socket.on("weather_data",  d => showWeather(d));
socket.on("map_search",    d => openMap(d.query));
socket.on("map_cmd",       d => {
  if (!edithMap) return;
  if (d.action === "zoom_in") edithMap.zoomIn(d.level || 1);
  if (d.action === "zoom_out") edithMap.zoomOut(d.level || 1);
  if (d.action.startsWith("pan_")) {
    const dir = d.action.split("_")[1];
    const amt = 200;
    if (dir === "up") edithMap.panBy([0, -amt]);
    if (dir === "down") edithMap.panBy([0, amt]);
    if (dir === "left") edithMap.panBy([-amt, 0]);
    if (dir === "right") edithMap.panBy([amt, 0]);
  }
});
socket.on("close_map",     () => closeMap());
socket.on("note_event",    d => handleNote(d.action, d.data));
socket.on("timer_event",   d => handleTimer(d.action, d.seconds, d.label));
socket.on("alarm_data",    d => setAlarm(d.time, d.label));
socket.on("phone_mode_status", handlePhoneModeStatus);

// ── STATE SYSTEM ─────────────────────────────────────────
var alarms = [];
var killModeActive = false;
var phoneModeActive = false;
var timerInterval = null;
var timerRemaining = 0;
var currentMicLevel = 0;

const STATE_CFG = {
  sleeping:  { dot: "#1a3a5c", text: "#1a3a5c", orb: "#0d1a2a", label: "STANDBY"  },
  listening: { dot: "#b4dff5", text: "#b4dff5", orb: "#5ab0e2", label: "LISTENING"},
  thinking:  { dot: "#ffffff", text: "#ffffff", orb: "#a2cde2", label: "PROCESSING"},
  speaking:  { dot: "#b4dff5", text: "#b4dff5", orb: "#5ab0e2", label: "OUTPUT"   },
};

var currentState = "sleeping";
var orbColor = "#0d1a2a";

function updateState(name, msg) {
  currentState = name;
  const c = STATE_CFG[name] || STATE_CFG.sleeping;
  const dot  = document.getElementById("status-dot");
  const txt  = document.getElementById("status-text");
  if(dot) {
    dot.style.background = c.dot;
    dot.style.boxShadow  = `0 0 10px ${c.dot}`;
  }
  if(txt) {
    txt.style.color      = c.text;
    txt.textContent      = c.label;
  }
  orbColor = killModeActive ? "#c0392b" : c.orb;

  // Update classes on #main container to morph HUD theme
  const mainEl = document.getElementById("main");
  const stateMap  = { sleeping: "", listening: "state-listening", thinking: "state-thinking", speaking: "state-speaking" };
  if (mainEl) {
    // Clear previous state classes
    Object.values(stateMap).forEach(cls => {
      if (cls) mainEl.classList.remove(cls);
    });
    const activeClass = stateMap[name];
    if (activeClass) mainEl.classList.add(activeClass);
  }

  const sleepOverlay = document.getElementById("sleep-overlay");
  if (sleepOverlay) {
    if (name === "sleeping") {
      sleepOverlay.classList.remove("waking");
      sleepOverlay.classList.add("active");
      const scanline = document.getElementById("transition-scanline");
      if (scanline) scanline.classList.remove("scanline-anim");
      
      // Close all panels on sleep
      document.getElementById("left-panel")?.classList.remove("active");
      document.getElementById("toggle-system-btn")?.classList.remove("active");
      document.getElementById("right-panel")?.classList.remove("active");
      document.getElementById("toggle-chat-btn")?.classList.remove("active");
      document.getElementById("spotify-widget")?.classList.add("spotify-widget-hidden");
      document.getElementById("toggle-music-btn")?.classList.remove("active");
      document.getElementById("memory-panel")?.classList.add("memory-panel-hidden");
      document.getElementById("toggle-memory-bar-btn")?.classList.remove("active");
      stopSpotifyTimer();
    } else {
      if (sleepOverlay.classList.contains("active") && !sleepOverlay.classList.contains("waking")) {
        // Trigger video 95 wake up sequence
        triggerWakeUpSequence(sleepOverlay);
      }
    }
  }

  const indClap = document.getElementById("ind-clap");
  const indWake = document.getElementById("ind-wake");
  const indVoice = document.getElementById("ind-voice");
  const indWeb = document.getElementById("ind-web");
  
  if(indClap) indClap.classList.toggle("active", name !== "sleeping");
  if(indWake) indWake.classList.toggle("active", name !== "sleeping");
  if(indVoice) indVoice.classList.toggle("active", name === "speaking");
  if(indWeb) indWeb.classList.toggle("active", name === "thinking");

  // Update bottom icon bar active classes
  document.getElementById("toggle-system-btn")?.classList.toggle("active", name !== "sleeping" && document.getElementById("left-panel")?.classList.contains("active"));
  document.getElementById("toggle-chat-btn")?.classList.toggle("active", name !== "sleeping" && document.getElementById("right-panel")?.classList.contains("active"));

  // Update reactive EDITH name element
  const nameEl    = document.getElementById("edith-name");
  const subEl     = document.getElementById("edith-subtitle");
  const subtitles = {
    sleeping:  "EVEN DEAD I'M THE HERO",
    listening: "VOICE INPUT ACTIVE",
    thinking:  "NEURAL PROCESSING...",
    speaking:  "AUDIO OUTPUT ENGAGED",
  };
  if(nameEl) nameEl.className = stateMap[name] || "";
  if(subEl && !killModeActive) {
    subEl.textContent = subtitles[name] || subtitles.sleeping;
  }

  if (msg) setDebug(msg);
}

// ── CLOCK & DATE ──────────────────────────────────────────
const startTime = Date.now();
function updateClock() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2,"0");
  const m = String(now.getMinutes()).padStart(2,"0");
  const s = String(now.getSeconds()).padStart(2,"0");
  const clockEl = document.getElementById("clock");
  if(clockEl) clockEl.textContent = h + ":" + m + ":" + s;

  const sleepClock = document.getElementById("sleep-clock");
  if(sleepClock) sleepClock.textContent = h + ":" + m + ":" + s;

  const days = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
  const months = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
  
  const daysFull = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"];
  const monthsFull = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

  const dateEl = document.getElementById("date-text");
  if(dateEl) {
    dateEl.textContent =
      days[now.getDay()] + " " + String(now.getDate()).padStart(2,"0") + " " +
      months[now.getMonth()] + " " + now.getFullYear();
  }

  const sleepDate = document.getElementById("sleep-date");
  if(sleepDate) {
    sleepDate.textContent =
      daysFull[now.getDay()] + " " + String(now.getDate()).padStart(2,"0") + " " +
      monthsFull[now.getMonth()] + " " + now.getFullYear();
  }

  // Uptime
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const uh = String(Math.floor(elapsed / 3600)).padStart(2,"0");
  const um = String(Math.floor((elapsed % 3600) / 60)).padStart(2,"0");
  const us = String(elapsed % 60).padStart(2,"0");
  const uptimeEl = document.getElementById("stat-uptime");
  if(uptimeEl) uptimeEl.textContent = uh + ":" + um + ":" + us;

  // Check alarms
  checkAlarms(h + ":" + m);
}
setInterval(updateClock, 1000);
updateClock();

// ── DEBUG ─────────────────────────────────────────────────
function setDebug(text) {
  const el = document.getElementById("debug-text");
  if(!el) return;
  el.textContent = "> " + text;
  el.style.animation = "none";
  void el.offsetHeight;
  el.style.animation = "slideUp 0.3s ease";
}

// ── CHAT ──────────────────────────────────────────────────
function addChat(role, text) {
  const log = document.getElementById("chat-log");
  if(!log) return;
  const d   = document.createElement("div");
  d.className = "msg " + role;
  const prefix = role === "user" ? "$ " : "> ";
  d.innerHTML = `<span class="chat-prefix">${prefix}</span><span class="chat-text">${escHtml(text)}</span>`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function escHtml(s) {
  if(!s) return "";
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── MIC ───────────────────────────────────────────────────
function updateMic(val, thr) {
  currentMicLevel = val;
  const MAX = 5000;
  const pct    = Math.min(100, (val / MAX) * 100);
  const thrPct = Math.min(100, (thr / MAX) * 100);
  const hit    = val >= thr;

  const fill = document.getElementById("mic-fill");
  if(fill) {
    fill.style.width      = pct + "%";
    fill.style.background = hit
      ? "linear-gradient(90deg,#c0392b,#e74c3c)"
      : "linear-gradient(90deg,#1a8fd1,#00d4ff)";
    fill.style.boxShadow  = hit ? "0 0 10px rgba(231,76,60,0.7)" : "0 0 8px rgba(0,212,255,0.5)";
  }

  const thrLine = document.getElementById("mic-threshold-line");
  if(thrLine) thrLine.style.left = thrPct + "%";
  
  const valTxt = document.getElementById("mic-val-text");
  if(valTxt) valTxt.textContent = val;
  
  const thrTxt = document.getElementById("mic-thr-text");
  if(thrTxt) thrTxt.textContent = "THR: " + thr;
  
  const debugMicFill = document.getElementById("debug-mic-fill");
  if(debugMicFill) debugMicFill.style.width = pct + "%";
}

// ── WAVEFORM ──────────────────────────────────────────────
const wfCanvas  = document.getElementById("waveform-canvas");
const wfCtx     = wfCanvas ? wfCanvas.getContext("2d") : null;
var wfSamples   = new Array(64).fill(0);
var wfAnimFrame = 0;

function renderWaveform(samples) {
  const norm = samples.map(s => s / 32768);
  wfSamples = [...wfSamples.slice(norm.length), ...norm];
}

function hexToRgbaStr(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function drawWaveform() {
  if(!wfCtx) return;
  requestAnimationFrame(drawWaveform);
  const W = wfCanvas.width  = wfCanvas.offsetWidth;
  const H = wfCanvas.height = wfCanvas.offsetHeight;
  wfCtx.clearRect(0, 0, W, H);

  const mid  = H / 2;
  const stateColors = {
    sleeping:  "#1a3a5c",
    listening: "#b4dff5",
    thinking:  "#ffffff",
    speaking:  "#b4dff5",
  };
  const col = killModeActive ? "#e74c3c" : (stateColors[currentState] || "#1a3a5c");

  if (currentState === "sleeping") {
    wfCtx.beginPath();
    wfCtx.strokeStyle = "#1a3a5c";
    wfCtx.lineWidth = 1;
    wfCtx.shadowBlur = 0;
    for (let i = 0; i < W; i += 2) {
      const y = mid + Math.sin((i / W) * Math.PI * 6 + wfAnimFrame * 0.03) * 1.5;
      i === 0 ? wfCtx.moveTo(i, y) : wfCtx.lineTo(i, y);
    }
    wfCtx.stroke();
  } else {
    // 3 overlapping siri-like wave sinusoids
    const layers = [
      { amp: 0.85, freq: 0.04, speed: 0.12, opacity: 0.8, width: 2 },
      { amp: 0.5, freq: 0.07, speed: -0.08, opacity: 0.4, width: 1.2 },
      { amp: 0.25, freq: 0.02, speed: 0.18, opacity: 0.2, width: 0.8 }
    ];

    layers.forEach(l => {
      wfCtx.beginPath();
      wfCtx.strokeStyle = hexToRgbaStr(col, l.opacity);
      wfCtx.lineWidth   = l.width;
      wfCtx.shadowColor = col;
      wfCtx.shadowBlur  = l.width >= 1.5 ? 5 : 0;

      for (let i = 0; i < W; i += 2) {
        const sampleIdx = Math.floor((i / W) * wfSamples.length);
        const sampleVal = wfSamples[sampleIdx] || 0;
        const volumeScale = Math.max(0.15, Math.abs(sampleVal));
        const y = mid + Math.sin(i * l.freq + wfAnimFrame * l.speed) * (mid * l.amp) * volumeScale;
        i === 0 ? wfCtx.moveTo(i, y) : wfCtx.lineTo(i, y);
      }
      wfCtx.stroke();
    });
  }

  wfAnimFrame++;
}
if(wfCtx) drawWaveform();

// ── ORB CANVAS ────────────────────────────────────────────
const orbCanvas = document.getElementById("orb-canvas");
const orbCtx    = orbCanvas ? orbCanvas.getContext("2d") : null;
var W_orb, H_orb, cx, cy, particles = [];
var frame = 0;

class Particle {
  constructor() { this.reset(true); }
  reset(init) {
    const angle  = Math.random() * Math.PI * 2;
    const radius = init ? Math.random() * 150 + 20 : 0;
    this.x     = cx + Math.cos(angle) * radius;
    this.y     = cy + Math.sin(angle) * radius;
    this.vx    = (Math.random() - 0.5) * 0.5;
    this.vy    = (Math.random() - 0.5) * 0.5;
    this.life  = Math.random();
    this.maxLife = 0.6 + Math.random() * 0.4;
    this.size  = Math.random() * 1.8 + 0.4;
    this.angle = angle;
    this.orbitR = 55 + Math.random() * 120;
    this.speed  = 0.003 + Math.random() * 0.007;
    this.orbit  = Math.random() > 0.35;
  }
  update(mult) {
    if (killModeActive) {
      // Explosive sparks flying outward
      this.x += this.vx * 3.5;
      this.y += this.vy * 3.5;
      this.life += 0.008;
      if (this.life > this.maxLife) this.reset(false);
      return;
    }

    if (currentState === "listening") {
      // Swirling vortex: pull inward towards center + expand based on mic input
      const micBonus = Math.min(100, (currentMicLevel / 5000) * 110);
      this.orbitR = Math.max(25, this.orbitR - 0.3);
      if (this.orbitR <= 25) this.orbitR = 120 + Math.random() * 60;
      this.angle += this.speed * 1.8 * mult;
      this.x = cx + Math.cos(this.angle) * (this.orbitR + micBonus);
      this.y = cy + Math.sin(this.angle) * (this.orbitR + micBonus);
      this.life += 0.003 * mult;
    } else if (this.orbit) {
      this.angle += this.speed * mult;
      const p = 1 + Math.sin(Date.now() * 0.0012) * 0.07;
      this.x = cx + Math.cos(this.angle) * this.orbitR * p;
      this.y = cy + Math.sin(this.angle) * this.orbitR * p;
      this.life += 0.004 * mult;
    } else {
      this.x += this.vx * mult;
      this.y += this.vy * mult;
      this.life += 0.004 * mult;
    }
    if (this.life > this.maxLife) this.reset(false);
  }
  draw(col) {
    if(!orbCtx) return;
    const alpha = Math.sin((this.life / this.maxLife) * Math.PI);
    
    if (killModeActive) {
      // Draw trails for sparks
      orbCtx.beginPath();
      orbCtx.moveTo(this.x - this.vx * 5, this.y - this.vy * 5);
      orbCtx.lineTo(this.x, this.y);
      orbCtx.strokeStyle = col + Math.floor(alpha * 180).toString(16).padStart(2,"0");
      orbCtx.lineWidth = this.size;
      orbCtx.stroke();
      return;
    }

    orbCtx.beginPath();
    orbCtx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    const hex = Math.floor(alpha * 200).toString(16).padStart(2,"0");
    orbCtx.fillStyle = col + hex;
    orbCtx.fill();
  }
}

function resizeOrb() {
  if(!orbCanvas) return;
  W_orb = orbCanvas.width  = orbCanvas.offsetWidth;
  H_orb = orbCanvas.height = orbCanvas.offsetHeight;
  cx = W_orb / 2; cy = H_orb / 2;
}

if(orbCanvas) {
  for (let i = 0; i < 200; i++) particles.push(new Particle());
}

function hexToRgb(hex) {
  const h = hex.replace("#","");
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
}

var currentOrbColor = [13,26,42];

function animateOrb() {
  if(!orbCtx) return;
  requestAnimationFrame(animateOrb);
  orbCtx.clearRect(0, 0, W_orb, H_orb);
  frame++;

  const targetRgb = hexToRgb(orbColor || "#0d1a2a");
  currentOrbColor = currentOrbColor.map((c,i) => c + (targetRgb[i] - c) * 0.05);
  const col = "#" + currentOrbColor.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2,"0")).join("");

  const speedMap = { sleeping: 0.3, listening: 1.1, thinking: 2.2, speaking: 1.7 };
  const mult = speedMap[currentState] || 0.3;

  const coreR = currentState === "thinking" ? 50 + Math.sin(frame * 0.12) * 10
              : currentState === "speaking"  ? 45 + Math.sin(frame * 0.09) * 12
              : currentState === "listening" ? 42 + Math.sin(frame * 0.07) * 7
              : 32 + Math.sin(frame * 0.02) * 4;

  const g = orbCtx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 3);
  g.addColorStop(0,   col + "40");
  g.addColorStop(0.4, col + "18");
  g.addColorStop(1,   "transparent");
  orbCtx.beginPath();
  orbCtx.arc(cx, cy, coreR * 3, 0, Math.PI * 2);
  orbCtx.fillStyle = g;
  orbCtx.fill();

  const cg = orbCtx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
  cg.addColorStop(0,   col + "cc");
  cg.addColorStop(0.5, col + "55");
  cg.addColorStop(1,   col + "00");
  orbCtx.beginPath();
  orbCtx.arc(cx, cy, coreR, 0, Math.PI * 2);
  orbCtx.fillStyle = cg;
  orbCtx.fill();

  // Draw concentric ripples expanding from center if speaking
  if (currentState === "speaking") {
    const sampleVal = Math.max(...wfSamples.map(Math.abs)) || 0.15;
    const rippleCount = 3;
    for (let r = 0; r < rippleCount; r++) {
      const radius = ((frame * 1.2 + r * 50) % 140);
      const alpha = 1 - (radius / 140);
      orbCtx.beginPath();
      orbCtx.arc(cx, cy, radius * (1 + sampleVal * 0.35), 0, Math.PI * 2);
      orbCtx.strokeStyle = hexToRgbaStr(col, alpha * 0.35);
      orbCtx.lineWidth = 1.2;
      orbCtx.stroke();
    }
  }

  // Draw slow-drifting cosmic nebula gradient behind orb if sleeping
  if (currentState === "sleeping") {
    const nebulaRadius = 130 + Math.sin(frame * 0.015) * 12;
    const ng = orbCtx.createRadialGradient(cx, cy, 0, cx, cy, nebulaRadius);
    ng.addColorStop(0, hexToRgbaStr(col, 0.22));
    ng.addColorStop(0.5, hexToRgbaStr(col, 0.07));
    ng.addColorStop(1, "transparent");
    orbCtx.beginPath();
    orbCtx.arc(cx, cy, nebulaRadius, 0, Math.PI * 2);
    orbCtx.fillStyle = ng;
    orbCtx.fill();
  }

  if (currentState !== "sleeping") {
    [90, 140, 185].forEach((r, ri) => {
      orbCtx.save();
      orbCtx.translate(cx, cy);
      orbCtx.rotate(frame * (ri % 2 === 0 ? 0.003 : -0.002) * (ri + 1));
      orbCtx.beginPath();
      orbCtx.arc(0, 0, r, 0, Math.PI * 2);
      orbCtx.strokeStyle = col + (ri === 0 ? "33" : ri === 1 ? "22" : "15");
      orbCtx.lineWidth = ri === 0 ? 1.5 : 1;
      orbCtx.stroke();

      if (ri === 0) {
        for (let t = 0; t < 12; t++) {
          const ta = (t / 12) * Math.PI * 2;
          const inner = t % 3 === 0 ? r - 10 : r - 5;
          orbCtx.beginPath();
          orbCtx.moveTo(Math.cos(ta) * inner, Math.sin(ta) * inner);
          orbCtx.lineTo(Math.cos(ta) * r, Math.sin(ta) * r);
          orbCtx.strokeStyle = col + (t % 3 === 0 ? "55" : "25");
          orbCtx.lineWidth = t % 3 === 0 ? 1.5 : 0.8;
          orbCtx.stroke();
        }
      }
      orbCtx.restore();
    });
  }

  for (const p of particles) {
    p.update(mult);
    p.draw(col);
  }

  if (currentState === "thinking" || currentState === "speaking") {
    orbCtx.lineWidth = 0.3;
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx*dx + dy*dy);
        if (d < 60) {
          orbCtx.beginPath();
          orbCtx.moveTo(particles[i].x, particles[i].y);
          orbCtx.lineTo(particles[j].x, particles[j].y);
          const a = Math.floor((1 - d/60) * 50).toString(16).padStart(2,"0");
          orbCtx.strokeStyle = col + a;
          orbCtx.stroke();
        }
      }
    }
  }
}

window.addEventListener("resize", resizeOrb);
resizeOrb();
if(orbCtx) animateOrb();

function updateSysInfo(d) {
  const cpuVal = document.getElementById("cpu-val");
  const cpuFill = document.getElementById("cpu-fill");
  const ramVal = document.getElementById("ram-val");
  const ramFill = document.getElementById("ram-fill");
  const diskVal = document.getElementById("disk-val");
  const diskFill = document.getElementById("disk-fill");
  
  if(cpuVal) cpuVal.textContent  = d.cpu + "%";
  if(cpuFill) cpuFill.style.width = d.cpu + "%";
  if(ramVal) ramVal.textContent  = d.ram_used + " / " + d.ram_total + " GB";
  if(ramFill) ramFill.style.width = d.ram_pct + "%";
  if(diskVal) diskVal.textContent = d.disk_pct + "%";
  if(diskFill) diskFill.style.width = d.disk_pct + "%";

  // Dynamic Network & Core UI Updates
  if(d.is_online !== undefined) {
    const netDot = document.getElementById("net-status-dot");
    const netTxt = document.getElementById("net-status-text");
    if(netDot && netTxt) {
      if(d.is_online) {
        netDot.style.background = "var(--cyan)";
        netDot.style.boxShadow = "0 0 5px var(--cyan)";
        netTxt.textContent = "ONLINE";
        netTxt.style.color = "var(--cyan)";
      } else {
        netDot.style.background = "#e74c3c";
        netDot.style.boxShadow = "0 0 8px #e74c3c";
        netTxt.textContent = "OFFLINE";
        netTxt.style.color = "#e74c3c";
      }
    }
  }

  if(d.active_model) {
    const topModel = document.getElementById("stat-model");
    const hudModel = document.getElementById("net-model-text");
    const textStr = String(d.active_model).toUpperCase();
    if(topModel) topModel.textContent = textStr;
    if(hudModel) hudModel.textContent = textStr;
  }
}

// ── WEATHER ───────────────────────────────────────────────
function showWeather(d) {
  const placeholder = document.getElementById("weather-placeholder");
  if(placeholder) placeholder.style.display = "none";
  const main = document.getElementById("weather-main");
  if(main) main.style.display = "flex";
  
  const temp = document.getElementById("w-temp");
  const city = document.getElementById("w-city");
  const desc = document.getElementById("w-desc");
  const wind = document.getElementById("w-wind");
  
  if(temp) temp.textContent = d.temp + "°C";
  if(city) city.textContent = d.city;
  if(desc) desc.textContent = d.desc;
  if(wind) wind.textContent = "Wind: " + d.wind + " km/h";
}

// ── MAP (Leaflet dark network map — fullscreen overlay) ───
const NETWORK_CITIES = [
  {name:"LONDON",lat:51.505,lng:-0.09},{name:"NEW YORK",lat:40.712,lng:-74.006},
  {name:"TOKYO",lat:35.689,lng:139.692},{name:"PARIS",lat:48.856,lng:2.352},
  {name:"DUBAI",lat:25.204,lng:55.270},{name:"SYDNEY",lat:-33.868,lng:151.209},
  {name:"MOSCOW",lat:55.755,lng:37.617},{name:"BEIJING",lat:39.904,lng:116.407},
  {name:"MUMBAI",lat:19.076,lng:72.877},{name:"SAO PAULO",lat:-23.549,lng:-46.633},
  {name:"CHICAGO",lat:41.878,lng:-87.630},{name:"BERLIN",lat:52.520,lng:13.405},
  {name:"SINGAPORE",lat:1.352,lng:103.819},{name:"TORONTO",lat:43.651,lng:-79.347},
  {name:"CAPE TOWN",lat:-33.924,lng:18.424},
];
var edithMap=null, mapNodeMarkers=[], mapPolylines=[], mapInitialized=false;

function _initMap() {
  if (mapInitialized) return;
  mapInitialized = true;
  edithMap = L.map('edith-map', {
    zoomControl:false, attributionControl:true, dragging:true,
    scrollWheelZoom:true, doubleClickZoom:true, keyboard:false,
  }).setView([20, 10], 2);
  L.tileLayer('/api/tile/{z}/{x}/{y}.png?v=2', {
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom:19,
  }).addTo(edithMap);
  NETWORK_CITIES.forEach(c => _addCityNode(c, false));
  _drawNetworkLines();
  edithMap.on('mousemove', e => {
    const coords = document.getElementById('map-hud-coords');
    if(coords) coords.textContent =
      'LAT '+e.latlng.lat.toFixed(3)+'  \u00b7  LON '+e.latlng.lng.toFixed(3);
  });
}

function _addCityNode(city, isTarget) {
  const cls = isTarget?'target':'';
  const icon = L.divIcon({className:'map-node',html:'<div class="map-node-dot '+cls+'"></div>',iconSize:[8,8],iconAnchor:[4,4]});
  const m = L.marker([city.lat,city.lng],{icon,interactive:false}).addTo(edithMap);
  m.bindTooltip('<span class="map-node-label '+cls+'">'+city.name+'</span>',{permanent:true,direction:'bottom',offset:[0,6],className:'map-lbl-tip',opacity:1});
  mapNodeMarkers.push(m);
  return m;
}

function _drawNetworkLines() {
  mapPolylines.forEach(p=>p.remove()); mapPolylines=[];
  for (let i=0;i<NETWORK_CITIES.length;i++) {
    const dists=[];
    for (let j=0;j<NETWORK_CITIES.length;j++) {
      if(i===j)continue;
      const d=L.latLng(NETWORK_CITIES[i].lat,NETWORK_CITIES[i].lng).distanceTo(L.latLng(NETWORK_CITIES[j].lat,NETWORK_CITIES[j].lng));
      dists.push({j,d:d});
    }
    dists.sort((a,b)=>a.d-b.d);
    dists.slice(0,2).forEach(({j})=>{
      const line=L.polyline([[NETWORK_CITIES[i].lat,NETWORK_CITIES[i].lng],[NETWORK_CITIES[j].lat,NETWORK_CITIES[j].lng]],
        {color:'rgba(0,180,220,0.18)',weight:1,dashArray:'4 6',interactive:false}).addTo(edithMap);
      mapPolylines.push(line);
    });
  }
}

function openMap(query) {
  try {
    const overlay = document.getElementById('map-overlay');
    if(!overlay) return;
    
    // Toggle behavior when clicked from the bottom dock button (passes 'London' by default)
    if (overlay.classList.contains('active') && query === 'London') {
      closeMap();
      return;
    }
    
    overlay.classList.add('active');
    document.body.classList.add('map-active');
    const toggleBtn = document.getElementById('toggle-map-btn');
    if (toggleBtn) toggleBtn.classList.add('active');
    
    // Automatically open the chat widget (Right Panel) in map mode
    const rightPanel = document.getElementById('right-panel');
    if (rightPanel && !rightPanel.classList.contains('active')) {
      rightPanel.classList.add('active');
      const chatBtn = document.getElementById('toggle-chat-btn');
      if (chatBtn) chatBtn.classList.add('active');
    }
    
    const hudLabel = document.getElementById('map-hud-label');
    if(hudLabel) hudLabel.textContent = 'TACTICAL GRID \u00b7 SEARCHING...';
    
    const sd = document.getElementById('map-status-dot');
    const st = document.getElementById('map-status-text');
    if(sd) { sd.style.background='#ffffff'; sd.style.boxShadow='0 0 8px #ffffff'; }
    if(st) { st.style.color='#ffffff'; st.textContent='SEARCHING'; }
    
    // Fetch immediately in parallel via local proxy
    const geocodePromise = fetch('/api/geocode?q='+encodeURIComponent(query))
      .then(r=>{if(!r.ok) throw new Error('HTTP error'); return r.json();});
      
    // Initialize map after a short delay to let the overlay become visible
    setTimeout(() => {
      if (!overlay.classList.contains('active')) return;
      
      if (!mapInitialized) { _initMap(); }
      edithMap.invalidateSize();
      
      // Re-invalidate after the full fade transition completes (800ms)
      setTimeout(() => {
        if (overlay.classList.contains('active')) edithMap.invalidateSize();
      }, 850);
      
      geocodePromise.then(results => {
        if(!results||results.length===0){setDebug('Location not found: '+query); if(st) st.textContent='NOT FOUND'; return;}
        const r=results[0], lat=parseFloat(r.lat), lng=parseFloat(r.lon);
        const label=(r.display_name||query).split(',')[0].toUpperCase();
        if(edithMap._targetMarker) edithMap._targetMarker.remove();
        const icon=L.divIcon({className:'map-node',html:'<div class="map-node-dot target"></div>',iconSize:[11,11],iconAnchor:[5,5]});
        const tm=L.marker([lat,lng],{icon,interactive:false}).addTo(edithMap);
        tm.bindTooltip('<span class="map-node-label target">'+label+'</span>',{permanent:true,direction:'bottom',offset:[0,6],className:'map-lbl-tip',opacity:1});
        edithMap._targetMarker=tm;
        if(edithMap._targetLines) edithMap._targetLines.forEach(l=>l.remove());
        edithMap._targetLines=[];
        NETWORK_CITIES.map(c=>({c,d:L.latLng(lat,lng).distanceTo(L.latLng(c.lat,c.lng))})).sort((a,b)=>a.d-b.d).slice(0,4).forEach(({c})=>{
          const line=L.polyline([[lat,lng],[c.lat,c.lng]],{color:'rgba(200,168,75,0.35)',weight:1.2,dashArray:'6 5',interactive:false}).addTo(edithMap);
          edithMap._targetLines.push(line);
        });
        edithMap.flyTo([lat,lng],13,{duration:1.8,easeLinearity:0.3});
        const coords = document.getElementById('map-hud-coords');
        if(coords) coords.textContent='LAT '+lat.toFixed(4)+'  \u00b7  LON '+lng.toFixed(4);
        if(hudLabel) hudLabel.textContent='\u2b21 TARGET: '+label;
        if(sd) { sd.style.background='#27ae60'; sd.style.boxShadow='0 0 8px #27ae60'; }
        if(st) { st.style.color='#27ae60'; st.textContent='LOCKED: '+label; }
        setDebug('Map locked: '+label);
      }).catch((err)=>{setDebug('Map geocode failed: ' + err.message); if(st) st.textContent='ERROR';});
    }, 50);
  } catch(err) {
    const hudLabel = document.getElementById('map-hud-label');
    if(hudLabel) hudLabel.textContent = 'ERROR: ' + err.message;
  }
}

function closeMap() {
  const overlay = document.getElementById('map-overlay');
  if(overlay) overlay.classList.remove('active');
  document.body.classList.remove('map-active');
  const toggleBtn = document.getElementById('toggle-map-btn');
  if (toggleBtn) toggleBtn.classList.remove('active');
  
  // Automatically close the chat widget (Right Panel) when exiting map mode
  const rightPanel = document.getElementById('right-panel');
  if (rightPanel && rightPanel.classList.contains('active')) {
    rightPanel.classList.remove('active');
    const chatBtn = document.getElementById('toggle-chat-btn');
    if (chatBtn) chatBtn.classList.remove('active');
  }
  
  setDebug('Map closed — returned to main view');
}

function addMapChat(role, text) {
  const log = document.getElementById('map-chat-log');
  if (!log) return;
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  const prefix = role === 'user' ? '$ ' : '> ';
  d.innerHTML = `<span class="chat-prefix">${prefix}</span><span class="chat-text">${escHtml(text)}</span>`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function sendMapTyped() {
  const inp = document.getElementById('map-type-input');
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';
  addChat('user', txt);
  addMapChat('user', txt);
  socket.emit('typed_message', { text: txt });
}

// ── NOTES ─────────────────────────────────────────────────
function handleNote(action, data) {
  if (action === "add") addNoteToUI(data);
}

function addNoteToUI(note) {
  const list = document.getElementById("notes-list");
  if(!list) return;
  const d    = document.createElement("div");
  d.className = "note-item";
  d.dataset.id = note.id;
  const timeStr = note.time ? note.time.slice(11,16) : "";
  d.innerHTML = `<div class="note-text">${escHtml(note.text)}</div><div class="note-time">${timeStr}</div>`;
  list.appendChild(d);
  list.scrollTop = list.scrollHeight;
}

// ── TIMER ─────────────────────────────────────────────────
function handleTimer(action, secs, label) {
  if (action === "start") {
    timerRemaining = secs;
    const display = document.getElementById("timer-display");
    const lbl = document.getElementById("timer-label-text");
    if(display) display.style.display = "block";
    if(lbl) lbl.textContent = label;
    
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      timerRemaining--;
      updateTimerDisplay();
      if (timerRemaining <= 0) {
        clearInterval(timerInterval);
        if(display) display.textContent = "DONE";
        setDebug("Timer complete: " + label);
        let f = 0;
        const fl = setInterval(() => {
          if(display) display.style.opacity = (f++ % 2 === 0) ? "0.2" : "1";
          if (f > 8) { 
            clearInterval(fl); 
            if(display) display.style.opacity = "1"; 
          }
        }, 300);
      }
    }, 1000);
    updateTimerDisplay();
  }
}

function updateTimerDisplay() {
  const display = document.getElementById("timer-display");
  if(!display) return;
  const m = String(Math.floor(timerRemaining / 60)).padStart(2,"0");
  const s = String(timerRemaining % 60).padStart(2,"0");
  display.textContent = m + ":" + s;
}

// ── ALARM ─────────────────────────────────────────────────
function setAlarm(time, label) {
  alarms.push({ time, label, fired: false });
  setDebug("Alarm armed for " + time);
}

function checkAlarms(currentTime) {
  alarms.forEach((a, i) => {
    if (a.time === currentTime && !a.fired) {
      a.fired = true;
      const banner = document.getElementById("alarm-banner");
      if(banner) {
        banner.textContent = "⚠ " + (a.label || "ALARM") + " — " + a.time + " — CLICK TO DISMISS ⚠";
        banner.style.display = "block";
      }
      setDebug("ALARM FIRING: " + a.time);
    }
  });
}

function dismissAlarm() {
  const banner = document.getElementById("alarm-banner");
  if(banner) banner.style.display = "none";
}

function toggleKillMode() {
  socket.emit("kill_mode_toggle", { active: !killModeActive });
}

function togglePhoneMode() {
  socket.emit("phone_mode_toggle", { active: !phoneModeActive });
}

function handlePhoneModeStatus(d) {
  phoneModeActive = d.active;
  const btn = document.getElementById("phone-mode-btn");
  if (btn) {
    btn.classList.toggle("active", phoneModeActive);
  }
  const toggleBtn = document.getElementById("toggle-phone-btn");
  if (toggleBtn) {
    toggleBtn.classList.toggle("active", phoneModeActive);
  }
  const panel = document.getElementById("phone-panel");
  if (panel) {
    if (phoneModeActive) {
      panel.classList.remove("phone-panel-hidden");
      setDebug("Phone Mode Engaged: routing audio to mobile client");
      if (!panel.style.left && !panel.style.top) {
        panel.style.top = "50%";
        panel.style.left = "50%";
        panel.style.transform = "translate(-50%, -50%)";
        panel.style.right = "auto";
        panel.style.bottom = "auto";
      }
    } else {
      panel.classList.add("phone-panel-hidden");
      setDebug("Phone Mode Disengaged: standard routing active");
    }
  }
}

// ── INSTANT KILL PROTOCOL ─────────────────────────────────
socket.on("kill_mode", function(d) {
  killModeActive = d.active;
  const body = document.body;
  const subEl  = document.getElementById("edith-subtitle");
  const btn = document.getElementById("kill-btn");
  if (btn) btn.classList.toggle("active", killModeActive);
  const toggleBtn = document.getElementById("toggle-kill-btn");
  if (toggleBtn) toggleBtn.classList.toggle("active", killModeActive);

  if (killModeActive) {
    body.classList.add("kill-mode");
    if(subEl) subEl.textContent = "INSTANT KILL PROTOCOL";
    orbColor = "#c0392b";
    setDebug("⚠ INSTANT KILL PROTOCOL ENGAGED ⚠");
  } else {
    body.classList.remove("kill-mode");
    if(subEl) subEl.textContent = "EVEN DEAD I'M THE HERO";
    orbColor = (STATE_CFG[currentState] || STATE_CFG.sleeping).orb;
    setDebug("Standard protocol restored");
  }
});

// ── WORLD BRIEFING PROTOCOL ─────────────────────────────────
var briefingActive = false;
var nvdaChartInstance = null;
var f1Data = null;
var currentF1View = 0;

const NEWS_CHANNELS = {
  sky: "https://www.youtube.com/embed/YDvsBbKfLPA?autoplay=1&mute=1",
  abc: "https://www.youtube.com/embed/iipR5yUp36o?autoplay=1&mute=1",
  bloomberg: "https://www.youtube.com/embed/iEpJwprxDdk?autoplay=1&mute=1",
  kerala: "https://www.youtube.com/embed/1wECsnGZcfc?autoplay=1&mute=1"
};

socket.on("world_briefing", function(data) {
  openBriefing(data);
});

socket.on("close_world_briefing", function() {
  closeBriefing(true);
});

function openBriefing(data) {
  const overlay = document.getElementById("briefing-overlay");
  if (!overlay) return;
  
  briefingActive = true;
  overlay.classList.add("active");
  setDebug("Tactical Briefing Core engaged. Initializing live streams...");

  // 1. Update News Channel URLs with dynamically resolved IDs
  if (data.news_streams) {
    Object.keys(data.news_streams).forEach(key => {
      const videoId = data.news_streams[key];
      if (videoId) {
        NEWS_CHANNELS[key] = `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1`;
      }
    });
  }

  // 2. Load Live News Feed
  switchChannel('sky');

  // 2. Load NVDA Stock
  if (data.stock) {
    const priceEl = document.getElementById("nvda-price");
    const changeEl = document.getElementById("nvda-change");
    
    if (priceEl) priceEl.textContent = `$${data.stock.currentPrice.toFixed(2)}`;
    
    if (changeEl) {
      const sign = data.stock.change >= 0 ? "+" : "";
      changeEl.textContent = `${sign}$${data.stock.change.toFixed(2)} (${sign}${data.stock.changePercent.toFixed(2)}%)`;
      
      changeEl.className = "stock-val";
      if (data.stock.change >= 0) {
        changeEl.classList.add("positive");
      } else {
        changeEl.classList.add("negative");
      }
    }

    if (data.stock.history) {
      renderNvdaChart(data.stock.history.dates, data.stock.history.prices);
    }
  }

  // 3. Load F1 Data
  if (data.f1) {
    f1Data = data.f1;
    currentF1View = 0;
    renderF1View();
  }
}

function closeBriefing(fromServer = false) {
  const overlay = document.getElementById("briefing-overlay");
  if (overlay) overlay.classList.remove("active");
  
  briefingActive = false;
  
  // Clear news player to stop audio
  const player = document.getElementById("live-news-player");
  if (player) player.src = "";
  
  setDebug("Tactical briefing shut down — returned to core system HUD");
  
  if (!fromServer) {
    // Notify backend to close out
    socket.emit("typed_message", { text: "close briefing" });
  }
}

function switchChannel(channelKey) {
  const player = document.getElementById("live-news-player");
  if (!player) return;
  
  const src = NEWS_CHANNELS[channelKey];
  if (src) {
    player.src = src;
  }
  
  // Update button active state
  const btnIds = { sky: "chan-sky", abc: "chan-abc", bloomberg: "chan-bloomberg", kerala: "chan-kerala" };
  Object.keys(btnIds).forEach(key => {
    const btn = document.getElementById(btnIds[key]);
    if (btn) {
      if (key === channelKey) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    }
  });
}

function cycleF1View() {
  if (!f1Data) return;
  currentF1View = (currentF1View + 1) % 4;
  renderF1View();
}

function renderF1View() {
  const header = document.getElementById("f1-panel-header");
  const contentArea = document.getElementById("f1-content-area");
  if (!header || !contentArea) return;

  if (currentF1View === 0) {
    header.innerHTML = `Formula 1 Driver Standings <span style="font-size: 0.8em; color: var(--cyan); float: right;">↻</span>`;
    const drivers = f1Data.drivers || [];
    contentArea.innerHTML = `
      <table class="briefing-table">
        <thead>
          <tr>
            <th>POS</th>
            <th>DRIVER</th>
            <th>TEAM</th>
            <th>WINS</th>
            <th>PTS</th>
          </tr>
        </thead>
        <tbody>
          ${drivers.map(item => `
            <tr class="${item.position === 1 ? 'leader' : ''}">
              <td>${item.position}</td>
              <td style="font-weight:600;">${item.driverName} (${item.driverCode})</td>
              <td>${item.constructor}</td>
              <td>${item.wins}</td>
              <td style="color:var(--cyan); text-shadow:0 0 4px rgba(0,212,255,0.4);">${item.points}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (currentF1View === 1) {
    header.innerHTML = `Formula 1 Constructor Standings <span style="font-size: 0.8em; color: var(--cyan); float: right;">↻</span>`;
    const constructors = f1Data.constructors || [];
    contentArea.innerHTML = `
      <table class="briefing-table">
        <thead>
          <tr>
            <th>POS</th>
            <th>CONSTRUCTOR</th>
            <th>WINS</th>
            <th>PTS</th>
          </tr>
        </thead>
        <tbody>
          ${constructors.map(item => `
            <tr class="${item.position === 1 ? 'leader' : ''}">
              <td>${item.position}</td>
              <td style="font-weight:600;">${item.constructorName}</td>
              <td>${item.wins}</td>
              <td style="color:var(--cyan); text-shadow:0 0 4px rgba(0,212,255,0.4);">${item.points}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (currentF1View === 2) {
    const last = f1Data.last_race || {};
    const raceName = last.raceName || "Last Race";
    header.innerHTML = `${raceName} Results <span style="font-size: 0.8em; color: var(--cyan); float: right;">↻</span>`;
    const results = last.results || [];
    contentArea.innerHTML = `
      <table class="briefing-table">
        <thead>
          <tr>
            <th>POS</th>
            <th>DRIVER</th>
            <th>TEAM</th>
            <th>PTS</th>
          </tr>
        </thead>
        <tbody>
          ${results.map(item => `
            <tr class="${item.position === 1 ? 'leader' : ''}">
              <td>${item.position}</td>
              <td style="font-weight:600;">${item.driverName} (${item.driverCode})</td>
              <td>${item.constructor}</td>
              <td style="color:var(--cyan); text-shadow:0 0 4px rgba(0,212,255,0.4);">${item.points}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } else if (currentF1View === 3) {
    const next = f1Data.next_race || {};
    const raceName = next.raceName || "Next Race";
    header.innerHTML = `Next Race: ${raceName} <span style="font-size: 0.8em; color: var(--cyan); float: right;">↻</span>`;
    
    let formattedDateTime = "TBD";
    if (next.date) {
      const dtStr = next.time ? `${next.date}T${next.time}` : next.date;
      try {
        const dt = new Date(dtStr);
        formattedDateTime = dt.toLocaleString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        formattedDateTime = `${next.date} ${next.time || ''}`;
      }
    }

    contentArea.innerHTML = `
      <div style="padding: 15px; display: flex; flex-direction: column; gap: 10px; height: 100%; box-sizing: border-box; justify-content: center; align-items: center; text-align: center; font-family: 'Share Tech Mono', monospace;">
        <div style="font-size: 1.25em; font-weight: 700; color: var(--cyan); text-shadow: 0 0 8px rgba(0,212,255,0.3); margin-bottom: 5px;">
          ${raceName}
        </div>
        <div style="font-size: 1.05em; font-weight: 600; color: #fff;">
          🏢 ${next.circuitName || 'TBD'}
        </div>
        <div style="font-size: 0.95em; color: #ccc;">
          📍 ${next.locality || ''}, ${next.country || ''}
        </div>
        <div style="font-size: 0.9em; font-weight: 600; color: #fff; border: 1px solid rgba(0,212,255,0.3); padding: 8px 15px; border-radius: 4px; background: rgba(0,212,255,0.05); margin-top: 5px;">
          📅 ${formattedDateTime}
        </div>
      </div>
    `;
  }
}


function renderNvdaChart(labels, prices) {
  const ctx = document.getElementById("nvda-chart");
  if (!ctx) return;

  if (nvdaChartInstance) {
    nvdaChartInstance.destroy();
  }

  // Neon Stark Blue styling
  const isKill = document.body.classList.contains("kill-mode");
  const themeColor = isKill ? "#ff4444" : "#00d4ff";
  const themeColorBg = isKill ? "rgba(255, 68, 68, 0.05)" : "rgba(0, 212, 255, 0.05)";
  const themeColorGrid = isKill ? "rgba(255, 68, 68, 0.08)" : "rgba(0, 212, 255, 0.08)";

  nvdaChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "NVDA Price (USD)",
        data: prices,
        borderColor: themeColor,
        borderWidth: 1.5,
        pointBackgroundColor: themeColor,
        pointBorderColor: "rgba(0,0,0,0)",
        pointRadius: 2.5,
        pointHoverRadius: 4,
        fill: true,
        backgroundColor: themeColorBg,
        tension: 0.25
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: "rgba(2, 11, 24, 0.9)",
          titleFont: { family: "Orbitron", size: 9 },
          bodyFont: { family: "Share Tech Mono", size: 10 },
          borderColor: themeColor,
          borderWidth: 1,
          displayColors: false,
          callbacks: {
            label: function(context) {
              return `PRICE: $${context.parsed.y.toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: themeColorGrid, drawTicks: false },
          ticks: {
            color: "rgba(255,255,255,0.4)",
            font: { family: "Share Tech Mono", size: 8 },
            maxTicksLimit: 7
          }
        },
        y: {
          grid: { color: themeColorGrid, drawTicks: false },
          ticks: {
            color: "rgba(255,255,255,0.4)",
            font: { family: "Share Tech Mono", size: 8 }
          }
        }
      }
    }
  });
}

// ── NEURAL MEMORY CORE (CHROMADB EDITOR) ───────────────────
var allMemoryData = { facts: [], notes: [], corrections: [], conversations: [] };
var currentMemoryTab = "facts";

function toggleMemoryPanel() {
  const panel = document.getElementById("memory-panel");
  if (!panel) return;
  
  const isHidden = panel.classList.contains("memory-panel-hidden");
  const btn = document.getElementById("toggle-memory-bar-btn");
  if (isHidden) {
    panel.classList.remove("memory-panel-hidden");
    if (btn) btn.classList.add("active");
    loadMemoryData();
    
    // Restore default position if not dragged
    if (!panel.style.left && !panel.style.top) {
      panel.style.top = "120px";
      panel.style.left = "calc(50% - 160px)";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    }
  } else {
    panel.classList.add("memory-panel-hidden");
    if (btn) btn.classList.remove("active");
  }
}

function loadMemoryData() {
  const listEl = document.getElementById("memory-items-list");
  if (listEl && allMemoryData[currentMemoryTab].length === 0) {
    listEl.innerHTML = '<div class="memory-empty-state">Establishing neural link to ChromaDB...</div>';
  }

  fetch("/api/memory")
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        console.error("Memory Core Error:", data.error);
        if (listEl) {
          listEl.innerHTML = `<div class="memory-empty-state" style="color:var(--red2)">Error: ${escHtml(data.error)}</div>`;
        }
        return;
      }
      
      allMemoryData = {
        facts: data.facts || [],
        notes: data.notes || [],
        corrections: data.corrections || [],
        conversations: data.conversations || []
      };
      renderMemoryItems();
    })
    .catch(err => {
      console.error("Fetch Memory Error:", err);
      if (listEl) {
        listEl.innerHTML = '<div class="memory-empty-state" style="color:var(--red2)">Neural link failed to connect.</div>';
      }
    });
}

function renderMemoryItems() {
  const listEl = document.getElementById("memory-items-list");
  if (!listEl) return;
  
  const searchInput = document.getElementById("memory-search-input");
  const filterText = searchInput ? searchInput.value.toLowerCase().trim() : "";
  
  const items = allMemoryData[currentMemoryTab] || [];
  const filtered = items.filter(item => {
    return item.text && item.text.toLowerCase().includes(filterText);
  });
  
  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="memory-empty-state">No matching memories found in ${currentMemoryTab.toUpperCase()}.</div>`;
    return;
  }
  
  // Map internal api tab names to display type names for API requests
  const typeMap = {
    facts: "fact",
    notes: "note",
    corrections: "correction",
    conversations: "convo"
  };
  const apiType = typeMap[currentMemoryTab];

  listEl.innerHTML = "";
  filtered.forEach(item => {
    const card = document.createElement("div");
    card.className = "memory-item-card";
    
    const textEl = document.createElement("div");
    textEl.className = "memory-item-text";
    textEl.textContent = item.text;
    
    const delBtn = document.createElement("button");
    delBtn.className = "memory-item-delete-btn";
    delBtn.innerHTML = "×";
    delBtn.title = "Delete this memory from vector space";
    delBtn.onclick = function() {
      if (confirm(`Are you sure you want to delete this item from memory?`)) {
        deleteMemoryItem(apiType, item.id);
      }
    };
    
    card.appendChild(textEl);
    card.appendChild(delBtn);
    listEl.appendChild(card);
  });
}

function switchMemoryTab(tabName) {
  currentMemoryTab = tabName;
  
  // Update active class on tab buttons
  const tabs = ["facts", "notes", "corrections", "conversations"];
  tabs.forEach(t => {
    const tabEl = document.getElementById(`tab-${t}`);
    if (tabEl) {
      if (t === tabName) {
        tabEl.classList.add("active");
      } else {
        tabEl.classList.remove("active");
      }
    }
  });
  
  renderMemoryItems();
}

function deleteMemoryItem(type, id) {
  fetch(`/api/memory/${type}/${encodeURIComponent(id)}`, {
    method: "DELETE"
  })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        setDebug(`Deleted ${type} memory item successfully`);
        loadMemoryData();
      } else {
        console.error("Delete Error:", res.error);
        alert(`Delete failed: ${res.error}`);
      }
    })
    .catch(err => {
      console.error("Delete request error:", err);
      alert("Error sending delete request.");
    });
}

function filterMemories() {
  renderMemoryItems();
}

// ── TOGGLE FUNCTIONS FOR FLOATING WIDGETS ──────────────────
function toggleLeftPanel() {
  const panel = document.getElementById("left-panel");
  const btn = document.getElementById("toggle-system-btn");
  if (!panel) return;
  
  const isActive = panel.classList.contains("active");
  if (isActive) {
    panel.classList.remove("active");
    if (btn) btn.classList.remove("active");
  } else {
    panel.classList.add("active");
    if (btn) btn.classList.add("active");
    
    // Restore default position if not dragged
    if (!panel.style.left && !panel.style.top) {
      panel.style.top = "100px";
      panel.style.left = "50px";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    }
  }
}

function toggleRightPanel() {
  const panel = document.getElementById("right-panel");
  const btn = document.getElementById("toggle-chat-btn");
  if (!panel) return;
  
  const isActive = panel.classList.contains("active");
  if (isActive) {
    panel.classList.remove("active");
    if (btn) btn.classList.remove("active");
  } else {
    panel.classList.add("active");
    if (btn) btn.classList.add("active");
    
    // Restore default position if not dragged
    if (!panel.style.left && !panel.style.top) {
      panel.style.top = "100px";
      panel.style.right = "50px";
      panel.style.left = "auto";
      panel.style.bottom = "auto";
    }
  }
}

function toggleMusicWidget() {
  const panel = document.getElementById("spotify-widget");
  const btn = document.getElementById("toggle-music-btn");
  if (!panel) return;
  
  const isHidden = panel.classList.contains("spotify-widget-hidden");
  if (!isHidden) {
    panel.classList.add("spotify-widget-hidden");
    if (btn) btn.classList.remove("active");
  } else {
    panel.classList.remove("spotify-widget-hidden");
    if (btn) btn.classList.add("active");
    
    // Restore default center position if not dragged
    if (!panel.style.left && !panel.style.top) {
      panel.style.top = "50%";
      panel.style.left = "50%";
      panel.style.transform = "translate(-50%, -50%)";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    }
  }
}

// ── SPOTIFY SIMULATOR ──────────────────────────────────────
var spotifyPlaying = false;
var spotifyTime = 124; // start at 2:04 (124s)
const spotifyDuration = 216; // 3:36 in seconds (216s)
var spotifyInterval = null;

function togglePlayPause() {
  const widget = document.getElementById("spotify-widget");
  const playBtnSvg = document.getElementById("play-pause-svg");
  if (!widget) return;

  spotifyPlaying = !spotifyPlaying;
  widget.classList.toggle("spotify-playing", spotifyPlaying);

  const overlayEl = widget.querySelector(".spotify-art-overlay");
  if (overlayEl) {
    overlayEl.textContent = spotifyPlaying ? "PLAYING" : "IDLE";
  }

  if (spotifyPlaying) {
    if (playBtnSvg) {
      playBtnSvg.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="currentColor"/>';
    }
    setDebug("Still into You - Paramore playing");
    spotifyInterval = setInterval(() => {
      spotifyTime++;
      if (spotifyTime >= spotifyDuration) {
        spotifyTime = 0;
      }
      updateSpotifyProgress();
    }, 1000);
  } else {
    if (playBtnSvg) {
      playBtnSvg.innerHTML = '<path d="M8 5v14l11-7z" fill="currentColor"/>';
    }
    setDebug("Spotify player paused");
    stopSpotifyTimer();
  }
}

function stopSpotifyTimer() {
  if (spotifyInterval) {
    clearInterval(spotifyInterval);
    spotifyInterval = null;
  }
  spotifyPlaying = false;
  const widget = document.getElementById("spotify-widget");
  if (widget) {
    widget.classList.remove("spotify-playing");
    const overlayEl = widget.querySelector(".spotify-art-overlay");
    if (overlayEl) {
      overlayEl.textContent = "IDLE";
    }
  }
  const playBtnSvg = document.getElementById("play-pause-svg");
  if (playBtnSvg) {
    playBtnSvg.innerHTML = '<path d="M8 5v14l11-7z" fill="currentColor"/>';
  }
}

function updateSpotifyProgress() {
  const timeEl = document.getElementById("spotify-time");
  const fillEl = document.getElementById("spotify-fill");
  if (timeEl) {
    const mins = Math.floor(spotifyTime / 60);
    const secs = String(spotifyTime % 60).padStart(2, "0");
    timeEl.textContent = `${mins}:${secs}`;
  }
  if (fillEl) {
    const pct = (spotifyTime / spotifyDuration) * 100;
    fillEl.style.width = pct + "%";
  }
}

socket.on("play_music", d => {
  const widget = document.getElementById("spotify-widget");
  if (!widget) return;
  widget.classList.remove("spotify-widget-hidden");
  
  const btn = document.getElementById("toggle-music-btn");
  if (btn) btn.classList.add("active");
  
  const trackName = document.querySelector(".spotify-track-name");
  if (trackName) trackName.textContent = d.title;
  
  const artistName = document.querySelector(".spotify-artist");
  if (artistName) artistName.textContent = "YouTube Audio";
  
  const artContainer = document.querySelector(".spotify-album-art");
  if (artContainer) {
    artContainer.innerHTML = `<iframe style="width:100%; height:100%; border:none; border-radius: 8px;" src="https://www.youtube.com/embed/${d.video_id}?autoplay=1" allow="autoplay; encrypted-media"></iframe>`;
  }
  
  spotifyPlaying = true;
  widget.classList.add("spotify-playing");
  
  const playBtnSvg = document.getElementById("play-pause-svg");
  if (playBtnSvg) {
    playBtnSvg.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="currentColor"/>';
  }
  
  setDebug("Playing: " + d.title);
});

// ── DRAG AND DROP UTILITY ──────────────────────────────────
let activeZIndex = 1000;

function makeDraggable(elmnt, handleEl) {
  let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

  if (handleEl) {
    handleEl.addEventListener("mousedown", dragMouseDown);
    handleEl.addEventListener("touchstart", dragTouchStart, {passive: false});
  } else {
    elmnt.addEventListener("mousedown", dragMouseDown);
    elmnt.addEventListener("touchstart", dragTouchStart, {passive: false});
  }

  function dragMouseDown(e) {
    if (e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea')) return;
    e.preventDefault();
    
    activeZIndex++;
    elmnt.style.setProperty("z-index", activeZIndex, "important");
    
    if (elmnt.style.transform || window.getComputedStyle(elmnt).transform !== 'none') {
      const rect = elmnt.getBoundingClientRect();
      elmnt.style.setProperty("transform", "none", "important");
      elmnt.style.setProperty("top", rect.top + "px", "important");
      elmnt.style.setProperty("left", rect.left + "px", "important");
      elmnt.style.setProperty("right", "auto", "important");
      elmnt.style.setProperty("bottom", "auto", "important");
      elmnt.style.setProperty("margin", "0", "important");
    }

    pos3 = e.clientX;
    pos4 = e.clientY;
    document.addEventListener("mouseup", closeDragElement);
    document.addEventListener("mousemove", elementDrag);
  }

  function elementDrag(e) {
    e.preventDefault();
    pos1 = pos3 - e.clientX;
    pos2 = pos4 - e.clientY;
    pos3 = e.clientX;
    pos4 = e.clientY;
    
    elmnt.style.setProperty("top", (elmnt.offsetTop - pos2) + "px", "important");
    elmnt.style.setProperty("left", (elmnt.offsetLeft - pos1) + "px", "important");
    elmnt.style.setProperty("right", "auto", "important");
    elmnt.style.setProperty("bottom", "auto", "important");
    elmnt.style.setProperty("margin", "0", "important");
  }

  function closeDragElement() {
    document.removeEventListener("mouseup", closeDragElement);
    document.removeEventListener("mousemove", elementDrag);
  }

  function dragTouchStart(e) {
    if (e.target.closest('button') || e.target.closest('input') || e.target.closest('textarea')) return;
    e.preventDefault();
    
    activeZIndex++;
    elmnt.style.setProperty("z-index", activeZIndex, "important");
    
    if (elmnt.style.transform || window.getComputedStyle(elmnt).transform !== 'none') {
      const rect = elmnt.getBoundingClientRect();
      elmnt.style.setProperty("transform", "none", "important");
      elmnt.style.setProperty("top", rect.top + "px", "important");
      elmnt.style.setProperty("left", rect.left + "px", "important");
      elmnt.style.setProperty("right", "auto", "important");
      elmnt.style.setProperty("bottom", "auto", "important");
      elmnt.style.setProperty("margin", "0", "important");
    }

    const touch = e.touches[0];
    pos3 = touch.clientX;
    pos4 = touch.clientY;
    document.addEventListener("touchend", closeTouchDrag);
    document.addEventListener("touchmove", touchDrag, {passive: false});
  }

  function touchDrag(e) {
    e.preventDefault();
    const touch = e.touches[0];
    pos1 = pos3 - touch.clientX;
    pos2 = pos4 - touch.clientY;
    pos3 = touch.clientX;
    pos4 = touch.clientY;
    
    elmnt.style.setProperty("top", (elmnt.offsetTop - pos2) + "px", "important");
    elmnt.style.setProperty("left", (elmnt.offsetLeft - pos1) + "px", "important");
    elmnt.style.setProperty("right", "auto", "important");
    elmnt.style.setProperty("bottom", "auto", "important");
    elmnt.style.setProperty("margin", "0", "important");
  }

  function closeTouchDrag() {
    document.removeEventListener("touchend", closeTouchDrag);
    document.removeEventListener("touchmove", touchDrag);
  }
}

function initDraggable() {
  const leftPanel = document.getElementById("left-panel");
  const leftHandle = leftPanel ? leftPanel.querySelector(".widget-header-handle") : null;
  if (leftPanel) makeDraggable(leftPanel, leftHandle);

  const rightPanel = document.getElementById("right-panel");
  const rightHandle = rightPanel ? rightPanel.querySelector(".widget-header-handle") : null;
  if (rightPanel) makeDraggable(rightPanel, rightHandle);

  const memoryPanel = document.getElementById("memory-panel");
  const memoryHandle = memoryPanel ? memoryPanel.querySelector(".widget-header-handle") : null;
  if (memoryPanel) makeDraggable(memoryPanel, memoryHandle);

  const spotifyWidget = document.getElementById("spotify-widget");
  const spotifyHandle = spotifyWidget ? spotifyWidget.querySelector(".widget-header-handle") : null;
  if (spotifyWidget) makeDraggable(spotifyWidget, spotifyHandle);

  const phonePanel = document.getElementById("phone-panel");
  const phoneHandle = phonePanel ? phonePanel.querySelector(".widget-header-handle") : null;
  if (phonePanel) makeDraggable(phonePanel, phoneHandle);
}

// Initialize draggability when DOM content is fully loaded
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDraggable);
} else {
  initDraggable();
}

function triggerWakeUpSequence(overlay) {
  const border = overlay.querySelector('.sleep-border-glow');
  const center = overlay.querySelector('.sleep-center-container');
  
  // Step 1: Start the glitch effect
  if (center) center.classList.add('glitch-active');
  
  // Step 2: After 200ms of glitching, start the wipe and black out the screen
  setTimeout(() => {
    overlay.classList.add("waking");
    if (border) border.style.opacity = '0';
    if (center) {
      center.style.opacity = '0';
      center.classList.remove('glitch-active');
    }
    
    // Trigger scanline wipe (takes 0.6s)
    const scanline = document.getElementById("transition-scanline");
    if (scanline) {
      scanline.classList.remove("scanline-anim");
      void scanline.offsetWidth; // trigger reflow
      scanline.classList.add("scanline-anim");
    }
    
    // Step 3: Once the scanline wipe finishes (0.6s after starting), fade in the main screen and reactor
    setTimeout(() => {
      overlay.classList.remove("active");
      overlay.classList.remove("waking");
      if (border) border.style.opacity = '1';
      if (center) center.style.opacity = '1';
      if (scanline) scanline.classList.remove("scanline-anim");
      
      // Trigger reactor power-up scale-from-zero animation
      const reactor = document.querySelector('.main-reactor-container');
      if (reactor) {
        reactor.classList.add('reactor-power-up');
        setTimeout(() => {
          reactor.classList.remove('reactor-power-up');
        }, 500); // duration of reactor-power-up animation
      }
    }, 600); // 600ms wipe duration
  }, 200); // 200ms glitch duration
}

// ── WIDGET UTILITIES (Chat Image Input Upload Mocking) ─────
function triggerImgUpload() {
  const fileInput = document.getElementById("chat-file-input");
  if (fileInput) fileInput.click();
}

function handleChatFileSelect(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    addChat("user", `[uploaded image: ${file.name}]`);
    addMapChat("user", `[uploaded image: ${file.name}]`);
    socket.emit("typed_message", { text: `[uploaded image: ${file.name}]` });
  }
}
