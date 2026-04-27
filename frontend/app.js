const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const micBtn = document.getElementById("micBtn");
const speakToggle = document.getElementById("speakToggle");
const autoSendVoice = document.getElementById("autoSendVoice");
const serverState = document.getElementById("serverState");
const apiState = document.getElementById("apiState");
const voiceState = document.getElementById("voiceState");

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

function speak(text) {
  if (!speakToggle.checked || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text.replace(/https?:\/\/\S+/g, "link"));
  utter.rate = 1;
  utter.pitch = 1;
  speechSynthesis.speak(utter);
}

async function checkHealth() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    serverState.textContent = data.status === "ok" ? "Online" : "Problem";
    apiState.textContent = data.api_key_loaded ? "Loaded" : "Missing key";
  } catch (e) {
    serverState.textContent = "Offline";
    apiState.textContent = "Unknown";
  }
}

async function sendMessage(text) {
  const msg = text.trim();
  if (!msg) return;
  addMessage("user", msg);
  input.value = "";

  const thinking = addMessage("assistant", "Working...");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    thinking.textContent = data.reply || data.error || "No response.";
    speak(thinking.textContent);
  } catch (e) {
    thinking.textContent = "Connection failed. Make sure server.py is running and open http://127.0.0.1:5050, not the file directly.";
  }
  chat.scrollTop = chat.scrollHeight;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(input.value);
});

document.querySelectorAll("[data-cmd]").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.cmd));
});

let recognition = null;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.continuous = false;

  recognition.onstart = () => {
    micBtn.classList.add("listening");
    voiceState.textContent = "Listening";
  };

  recognition.onend = () => {
    micBtn.classList.remove("listening");
    voiceState.textContent = "Ready";
  };

  recognition.onerror = (event) => {
    voiceState.textContent = event.error || "Error";
    addMessage("system", `Voice error: ${event.error}. Try speaking closer to the mic or type the command.`);
  };

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    input.value = text;
    if (autoSendVoice.checked) sendMessage(text);
  };
} else {
  voiceState.textContent = "Unsupported";
}

micBtn.addEventListener("click", () => {
  if (!recognition) {
    addMessage("system", "Speech recognition is not supported in this browser. Use Chrome or Edge.");
    return;
  }
  try {
    recognition.start();
  } catch (e) {
    recognition.stop();
  }
});

addMessage("assistant", "J.A.R.V.I.S full PC control is ready. Try: take screenshot, open notepad, press ctrl + l, type hello, system info, or ask a normal question.");
checkHealth();
setInterval(checkHealth, 5000);
