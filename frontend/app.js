const API_BASE = window.location.port === "5500" || window.location.port === "3000"
  ? "http://localhost:8000"
  : "";

let conversationHistory = [];
let lastSteps = [];
let lastSummary = "";

async function loadProfiles() {
  const res = await fetch(`${API_BASE}/api/user_profiles`);
  const profiles = await res.json();
  const sel = document.getElementById("profileSelect");
  sel.innerHTML = '<option value="">-- Select profile --</option>';
  profiles.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = `${p.name} (${p.level}) – ${p.goals}`;
    sel.appendChild(opt);
  });
}

async function loadScenarios() {
  const predefined = [
    { id: "coffee", name: "Casual chat at a coffee shop" },
    { id: "gaming", name: "Arguing about a game with a friend" },
    { id: "party", name: "Meeting someone at a party" },
    { id: "streaming", name: "Talking like a streamer to viewers" },
    { id: "diner", name: "Ordering food at a casual diner" },
  ];
  const sel = document.getElementById("scenarioSelect");
  sel.innerHTML = '<option value="">-- Pre-defined scenario --</option>';
  predefined.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.name;
    opt.textContent = s.name;
    sel.appendChild(opt);
  });
}

function updateProfileInfo() {
  const sel = document.getElementById("profileSelect");
  const id = sel.value;
  if (!id) {
    document.getElementById("profileInfo").textContent = "";
    return;
  }
  fetch(`${API_BASE}/api/user_profiles`)
    .then((r) => r.json())
    .then((profiles) => {
      const p = profiles.find((x) => String(x.id) === String(id));
      if (p) {
        document.getElementById("profileInfo").textContent =
          `Level: ${p.level} | Goals: ${p.goals} | Age: ${p.age_group}`;
      }
    });
}

function getScenarioText() {
  const custom = document.getElementById("scenarioCustom").value.trim();
  if (custom) return custom;
  return document.getElementById("scenarioSelect").value || "";
}

function showSection(id) {
  document.getElementById(id).classList.remove("hidden");
}

function renderConversation() {
  const box = document.getElementById("conversation");
  box.innerHTML = conversationHistory
    .map(
      (m) =>
        `<div class="msg ${m.role}">${escapeHtml(m.content)}</div>`
    )
    .join("");
  box.scrollTop = box.scrollHeight;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function renderSteps(steps) {
  const box = document.getElementById("stepsTrace");
  if (!steps || steps.length === 0) {
    box.textContent = "No steps logged.";
    return;
  }
  box.innerHTML = steps
    .map(
      (s) => `
    <div class="step">
      <div class="module">${escapeHtml(s.module)}</div>
      <div class="prompt">Prompt: ${escapeHtml(JSON.stringify(s.prompt || {}).slice(0, 500))}...</div>
      <div class="response">Response: ${escapeHtml(String(s.response || "").slice(0, 500))}...</div>
    </div>`
    )
    .join("");
}

async function runAgent() {
  const profileId = document.getElementById("profileSelect").value;
  const scenario = getScenarioText();
  if (!profileId) {
    alert("Please select a user profile.");
    return;
  }
  if (!scenario) {
    alert("Please choose or describe a scenario.");
    return;
  }

  conversationHistory = [];
  const prompt = scenario;
  const runBtn = document.getElementById("runAgent");
  runBtn.disabled = true;
  runBtn.textContent = "Running...";

  try {
    const res = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        user_profile_id: profileId,
        scenario,
        conversation_history: [],
      }),
    });
    const data = await res.json();

    if (data.status === "error") {
      document.getElementById("finalResponse").textContent = "Error: " + (data.error || "Unknown");
      lastSteps = data.steps || [];
    } else {
      document.getElementById("finalResponse").textContent = data.response || "";
      lastSteps = data.steps || [];
      conversationHistory = [
        { role: "user", content: prompt },
        { role: "assistant", content: data.response || "" },
      ];
      showSection("chatSection");
      renderConversation();
    }

    showSection("responseSection");
    showSection("stepsSection");
    renderSteps(lastSteps);
    document.getElementById("summaryContent").textContent =
      lastSummary || "Complete a conversation and end it to see summary & evaluation.";
    showSection("summarySection");
  } catch (e) {
    document.getElementById("finalResponse").textContent = "Request failed: " + e.message;
    showSection("responseSection");
  }

  runBtn.disabled = false;
  runBtn.textContent = "Run Agent";
}

async function sendMessage() {
  const input = document.getElementById("userInput");
  const text = input.value.trim();
  if (!text) return;

  const profileId = document.getElementById("profileSelect").value;
  const scenario = getScenarioText();
  conversationHistory.push({ role: "user", content: text });
  renderConversation();
  input.value = "";

  try {
    const res = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: text,
        user_profile_id: profileId,
        scenario,
        conversation_history: conversationHistory.slice(0, -1),
      }),
    });
    const data = await res.json();

    if (data.status === "ok" && data.response) {
      conversationHistory.push({ role: "assistant", content: data.response });
      if (data.response.includes("[Summary]")) {
        const idx = data.response.indexOf("[Summary]");
        lastSummary = data.response.slice(idx);
      }
    }
    if (data.steps && data.steps.length) {
      lastSteps = data.steps;
      renderSteps(lastSteps);
    }
    renderConversation();
    document.getElementById("finalResponse").textContent = data.response || "";
    if (lastSummary) {
      document.getElementById("summaryContent").textContent = lastSummary;
    }
  } catch (e) {
    conversationHistory.push({ role: "assistant", content: "Error: " + e.message });
    renderConversation();
  }
}

document.getElementById("profileSelect").addEventListener("change", updateProfileInfo);
document.getElementById("runAgent").addEventListener("click", runAgent);
document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("userInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

loadProfiles();
loadScenarios();
