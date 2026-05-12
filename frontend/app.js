const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const listenBtn = document.getElementById("listenBtn");
const wakeBtn = document.getElementById("wakeBtn");
const sleepBtn = document.getElementById("sleepBtn");
const interruptBtn = document.getElementById("interruptBtn");
const testAudioBtn = document.getElementById("testAudioBtn");
const statusBadge = document.getElementById("statusBadge");
const orb = document.getElementById("orb");
const heard = document.getElementById("heard");
const stateBox = document.getElementById("stateBox");
const useVoice = document.getElementById("useVoice");
const useEdgeTts = document.getElementById("useEdgeTts");
const autoListen = document.getElementById("autoListen");

let awake = false;
let listening = false;
let recognition = null;
let speakingAudio = null;
let browserUtterance = null;
let lastCommand = "";
let restartTimer = null;
let suppressRecognitionRestart = false;
let edgeTtsFailedOnce = false;
let audioUnlocked = false;

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function setState(state, detail = "") {
  statusBadge.className = `badge ${state}`;
  orb.className = `orb ${state}`;
  statusBadge.textContent = state[0].toUpperCase() + state.slice(1);
  stateBox.textContent = [
    `state: ${state}`,
    `awake: ${awake}`,
    `listening: ${listening}`,
    `voice replies: ${useVoice?.checked}`,
    `edge tts: ${useEdgeTts?.checked}`,
    `last: ${lastCommand}`,
    detail
  ].filter(Boolean).join("\n");
}

function addMessage(role, text, meta = "") {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const m = document.createElement("div");
  m.className = "meta";
  m.textContent = meta || (role === "user" ? "You" : "JARVIS");
  const body = document.createElement("div");
  body.textContent = text;
  div.appendChild(m);
  div.appendChild(body);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function clientNormalize(text) {
  let t = (text || "").toLowerCase().trim();
  const map = {
    "face text": "paste text",
    "phase text": "paste text",
    "pays text": "paste text",
    "paced text": "paste text",
    "based text": "paste text",
    "peace text": "paste text",
    "pasta text": "paste text",
    "clothes chrome": "close chrome",
    "close crumb": "close chrome",
    "open crow": "open chrome",
    "take screen short": "take screenshot",
    "reed screen": "read screen",
    "red screen": "read screen",
    "high light": "highlight",
    "copy tax": "copy text",
    "pressed blue button": "press blue button",
    "press blew button": "press blue button",
    "righting mode": "writing mode",
    "undo debt": "undo that",
    "screen target": "screen targets"
  };
  Object.entries(map).forEach(([wrong, right]) => {
    t = t.replaceAll(wrong, right);
  });
  return t;
}

function extractCommand(transcript) {
  let t = clientNormalize(transcript);
  heard.textContent = `Heard: ${transcript}`;
  const speechStopOnly = ["stop", "cancel", "interrupt", "stop talking", "cancel speech"];
  if (speechStopOnly.includes(t)) {
    interruptSpeech();
    return "stop";
  }
  if (t.includes("go to sleep")) {
    awake = false;
    setState("sleeping", "Sleep command received.");
    return "go to sleep";
  }
  const wakeWords = ["hey jarvis", "jarvis", "hey service", "hey travis", "hey jervis"];
  const wake = wakeWords.find(w => t.includes(w));
  if (wake) {
    awake = true;
    const after = t.split(wake).slice(1).join(wake).replace(/^,?\s*/, "").trim();
    setState("listening", "Wake word detected.");
    return after || "";
  }
  if (awake) return t;
  return null;
}

async function sendCommand(text, source = "text") {
  const command = (text || "").trim();
  if (!command) {
    if (awake) speak("Yes?");
    return;
  }
  lastCommand = command;
  addMessage("user", command);
  setState("thinking");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: command, source })
    });
    const data = await res.json();
    const reply = data.reply || data.error || "No response.";
    const meta = data.normalized && data.normalized !== command ? `JARVIS · normalized: ${data.normalized}` : "JARVIS";
    addMessage("jarvis", reply, meta);
    const silent = data.extra && data.extra.silent;
    if (data.action === "interrupt") interruptSpeech();
    else if (!silent) await speak(reply);
  } catch (err) {
    const msg = `Connection failed: ${err}. Make sure server.py is running.`;
    addMessage("jarvis", msg);
    await speak(msg);
  } finally {
    setState(awake ? "listening" : "sleeping");
  }
}

function stopRecognitionForSpeech() {
  if (!recognition || !listening) return;
  suppressRecognitionRestart = true;
  try { recognition.stop(); } catch (_) {}
}

function resumeRecognitionAfterSpeech() {
  suppressRecognitionRestart = false;
  if (!recognition || !autoListen.checked) return;
  clearTimeout(restartTimer);
  restartTimer = setTimeout(() => {
    try { recognition.start(); } catch (_) {}
  }, 350);
}

function interruptSpeech() {
  if (speakingAudio) {
    try { speakingAudio.pause(); } catch (_) {}
    speakingAudio.currentTime = 0;
    speakingAudio = null;
  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  resumeRecognitionAfterSpeech();
  setState(awake ? "listening" : "sleeping", "Speech interrupted.");
}

function cleanSpeechText(text) {
  return String(text || "")
    .replace(/https?:\/\/\S+/g, "link")
    .replace(/\b[A-Z]:\\[^\s]+/gi, "a file path")
    .slice(0, 2800);
}

async function unlockAudioOnce() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  try {
    const a = new Audio();
    a.muted = true;
    await a.play().catch(() => {});
  } catch (_) {}
}

function speakWithBrowser(clean) {
  return new Promise(resolve => {
    if (!window.speechSynthesis) {
      resolve(false);
      return;
    }
    try {
      window.speechSynthesis.cancel();
      browserUtterance = new SpeechSynthesisUtterance(clean);
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(v => /guy|david|mark|aria|jenny/i.test(v.name)) || voices.find(v => /english|en-us/i.test(v.lang));
      if (preferred) browserUtterance.voice = preferred;
      browserUtterance.rate = 1.02;
      browserUtterance.pitch = 0.88;
      browserUtterance.volume = 1;
      browserUtterance.onend = () => resolve(true);
      browserUtterance.onerror = () => resolve(false);
      window.speechSynthesis.speak(browserUtterance);
      setTimeout(() => resolve(true), Math.min(9000, clean.length * 80 + 1200));
    } catch (_) {
      resolve(false);
    }
  });
}

async function speakWithEdge(clean) {
  const r = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: clean })
  });
  const data = await r.json();
  if (!data.ok || !data.url) throw new Error(data.error || "Edge TTS failed.");
  return new Promise((resolve, reject) => {
    speakingAudio = new Audio(data.url + `?t=${Date.now()}`);
    speakingAudio.volume = 1;
    speakingAudio.onended = () => resolve(true);
    speakingAudio.onerror = () => reject(new Error("Audio file could not be played."));
    speakingAudio.play().then(() => {}).catch(reject);
  });
}

async function speak(text) {
  if (!useVoice.checked || !text) return;
  const clean = cleanSpeechText(text);
  setState("speaking");
  stopRecognitionForSpeech();

  let spoken = false;
  if (useEdgeTts.checked && !edgeTtsFailedOnce) {
    try {
      spoken = await speakWithEdge(clean);
    } catch (err) {
      edgeTtsFailedOnce = true;
      heard.textContent = `Edge TTS failed, using browser voice: ${err.message || err}`;
    }
  }

  if (!spoken) {
    spoken = await speakWithBrowser(clean);
  }

  resumeRecognitionAfterSpeech();
  setState(awake ? "listening" : "sleeping", spoken ? "Audio finished." : "Audio failed. Check browser/site sound permissions.");
}

function initRecognition() {
  if (!SpeechRecognition) {
    addMessage("jarvis", "Speech recognition is not supported here. Use Chrome or Edge.");
    return null;
  }
  const rec = new SpeechRecognition();
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = "en-US";
  rec.onstart = () => {
    listening = true;
    setState(awake ? "listening" : "sleeping", "Microphone active.");
  };
  rec.onerror = event => {
    heard.textContent = `Recognition error: ${event.error}`;
  };
  rec.onend = () => {
    listening = false;
    if (suppressRecognitionRestart) return;
    if (autoListen.checked) {
      clearTimeout(restartTimer);
      restartTimer = setTimeout(() => {
        try { rec.start(); } catch (_) {}
      }, 450);
    } else {
      setState(awake ? "awake" : "sleeping");
    }
  };
  rec.onresult = event => {
    let finalText = "";
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const txt = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += txt;
      else interim += txt;
    }
    if (interim) heard.textContent = `Listening: ${interim}`;
    if (finalText.trim()) {
      const cmd = extractCommand(finalText);
      if (cmd !== null) sendCommand(cmd, "voice");
    }
  };
  return rec;
}

listenBtn.addEventListener("click", async () => {
  await unlockAudioOnce();
  if (!recognition) recognition = initRecognition();
  if (!recognition) return;
  autoListen.checked = true;
  try { recognition.start(); } catch (_) {}
});

wakeBtn.addEventListener("click", async () => {
  await unlockAudioOnce();
  awake = true;
  setState("listening", "Manually awakened.");
  await speak("Ready.");
});

sleepBtn.addEventListener("click", () => {
  awake = false;
  interruptSpeech();
  setState("sleeping", "Manual sleep.");
});

interruptBtn.addEventListener("click", interruptSpeech);

if (testAudioBtn) {
  testAudioBtn.addEventListener("click", async () => {
    await unlockAudioOnce();
    edgeTtsFailedOnce = false;
    await speak("Audio test. If you can hear this, JARVIS voice is working.");
  });
}

form.addEventListener("submit", e => {
  e.preventDefault();
  const text = input.value.trim();
  input.value = "";
  sendCommand(text, "text");
});

document.querySelectorAll("[data-cmd]").forEach(btn => {
  btn.addEventListener("click", () => sendCommand(btn.dataset.cmd, "button"));
});

if (window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}

addMessage("jarvis", "JARVIS V10 ready. Click Start always-listening mode, then say “Hey Jarvis”. Use Test Audio if voice is silent.");
setState("sleeping");
