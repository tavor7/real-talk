const API_BASE =
  window.location.port === "5500" || window.location.port === "3000"
    ? "http://localhost:8000"
    : window.location.protocol === "file:"
      ? "http://localhost:8000"
      : "";

let conversationHistory = [];
let lastSteps = [];
let lastSummary = "";
let conversationEnded = false;
let requestInProgress = false;

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
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove("hidden");
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function hideSection(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}

function setRequestInProgress(inProgress) {
  requestInProgress = inProgress;
  const runBtn = document.getElementById("runAgent");
  const sendBtn = document.getElementById("sendBtn");
  const endBtn = document.getElementById("endConversationBtn");
  if (runBtn) runBtn.disabled = inProgress;
  if (sendBtn) sendBtn.disabled = inProgress;
  if (endBtn) endBtn.disabled = inProgress || conversationEnded;
}

function resetConversation() {
  conversationHistory = [];
  lastSteps = [];
  lastSummary = "";
  conversationEnded = false;
  requestInProgress = false;
  const box = document.getElementById("conversation");
  if (box) box.innerHTML = "";
  document.getElementById("finalResponse").textContent = "";
  document.getElementById("summaryContent").textContent = "Complete a conversation and end it to see summary & evaluation.";
  setConversationEndedUI(false);
  setRequestInProgress(false);
  hideSection("responseSection");
  hideSection("summarySection");
  hideSection("stepsSection");
  showSection("chatSection");
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
    .map((s) => {
      const promptStr = typeof s.prompt === "object" ? JSON.stringify(s.prompt, null, 2) : String(s.prompt || "");
      const rawResp = s.response;
      const responseStr = rawResp === null || rawResp === undefined ? "" : String(rawResp);
      const responseDisplay = responseStr.trim() === "" ? "(empty or null — no response from this step)" : responseStr;
      const promptLen = promptStr.length;
      const responseLen = responseDisplay.length;
      return `
    <div class="step">
      <div class="module">${escapeHtml(s.module)}</div>
      <details class="step-details" open>
        <summary style="white-space: normal; word-break: break-word; display: block;">Prompt (${promptLen} chars) — click to collapse</summary>
        <pre class="step-full">${escapeHtml(promptStr)}</pre>
      </details>
      <details class="step-details" open>
        <summary style="white-space: normal; word-break: break-word; display: block;">Response (${responseLen} chars) — click to collapse</summary>
        <pre class="step-full">${escapeHtml(responseDisplay)}</pre>
      </details>
    </div>`;
    })
    .join("");
}

async function runAgent() {
  if (requestInProgress) return;
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
  setRequestInProgress(true);
  const runBtn = document.getElementById("runAgent");
  runBtn.textContent = "Running...";
  showSection("chatSection");
  showChatLoading(true);
  await new Promise(requestAnimationFrame);

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
      // First assistant message = plain opening line (from LLM or fallback) so conversation history has clean flow
      const firstAssistantMessage = data.reply != null ? data.reply : data.response || "";
      conversationHistory = [
        { role: "user", content: prompt },
        { role: "assistant", content: firstAssistantMessage },
      ];
      conversationEnded = false;
      setConversationEndedUI(false);
      renderConversation();
    }
    showChatLoading(false);

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
  showChatLoading(false);
  runBtn.textContent = "Run Agent";
  setRequestInProgress(false);
}

const LOADING_MESSAGES = [
  "thinking",
  "thinking.",
  "thinking..",
  "thinking...",
  "thinking....",
  "thinking.....",
];

let loadingIntervalId = null;

function showChatLoading(show) {
  const bar = document.getElementById("loadingBar");
  const textEl = document.getElementById("loadingBarText");
  if (!bar || !textEl) return;
  if (show) {
    if (loadingIntervalId) clearInterval(loadingIntervalId);
    bar.classList.remove("hidden");
    let msgIdx = 0;
    textEl.textContent = LOADING_MESSAGES[0];
    loadingIntervalId = setInterval(() => {
      msgIdx += 1;
      textEl.textContent = LOADING_MESSAGES[msgIdx % LOADING_MESSAGES.length];
    }, 200);
    const box = document.getElementById("conversation");
    if (box) box.scrollTop = box.scrollHeight;
  } else {
    if (loadingIntervalId) {
      clearInterval(loadingIntervalId);
      loadingIntervalId = null;
    }
    bar.classList.add("hidden");
    textEl.textContent = "";
  }
}

function setConversationEndedUI(ended) {
  conversationEnded = ended;
  const inputRow = document.getElementById("inputRow");
  const endedEl = document.getElementById("conversationEnded");
  const endedText = document.getElementById("conversationEndedText");
  const endBtn = document.getElementById("endConversationBtn");
  if (ended) {
    inputRow.classList.add("hidden");
    endedEl.classList.remove("hidden");
    if (endedText) endedText.textContent = "Conversation ended. See summary below.";
    endBtn.disabled = true;
    showSection("summarySection");
  } else {
    inputRow.classList.remove("hidden");
    endedEl.classList.add("hidden");
    if (endedText) endedText.textContent = "";
    endBtn.disabled = requestInProgress;
  }
}

async function endConversation() {
  const endBtn = document.getElementById("endConversationBtn");
  if (!endBtn) {
    console.error("endConversationBtn not found");
    return;
  }

  if (conversationEnded) {
    showSection("summarySection");
    showSection("responseSection");
    return;
  }

  if (requestInProgress) {
    console.log("Request already in progress, ignoring endConversation");
    return;
  }

  if (!conversationHistory.length) {
    alert("No messages yet — send at least one message before ending the conversation.");
    return;
  }

  const profileId = (document.getElementById("profileSelect") && document.getElementById("profileSelect").value) || "";
  const scenario = getScenarioText();

  console.log("End conversation clicked", { profileId, scenario, historyLength: conversationHistory.length });
  setRequestInProgress(true);
  endBtn.textContent = "Ending...";
  showSection("responseSection");

  try {
    const res = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: "",
        user_profile_id: profileId,
        scenario,
        conversation_history: conversationHistory,
        end_conversation: true,
      }),
    });

    let data;
    try {
      data = await res.json();
    } catch (_) {
      document.getElementById("finalResponse").textContent = "Server error: " + res.status + " " + res.statusText;
      setRequestInProgress(false);
      endBtn.textContent = "End conversation";
      return;
    }

    if (!res.ok) {
      document.getElementById("finalResponse").textContent = "Error " + res.status + ": " + (data.error || data.detail || res.statusText);
      setRequestInProgress(false);
      endBtn.textContent = "End conversation";
      return;
    }

    if (data.status === "error") {
      document.getElementById("finalResponse").textContent = "Error: " + (data.error || "Unknown");
      setRequestInProgress(false);
      endBtn.textContent = "End conversation";
      return;
    }

    const reply = data.reply != null ? data.reply : (data.response || "").split("\n\n[Summary]")[0];
    conversationHistory.push({ role: "assistant", content: reply });
    renderConversation();

    if (data.response && data.response.includes("[Summary]")) {
      const idx = data.response.indexOf("[Summary]");
      lastSummary = data.response.slice(idx);
      document.getElementById("summaryContent").textContent = lastSummary;
      showSection("summarySection");
    }
    document.getElementById("finalResponse").textContent = data.response || "";
    setConversationEndedUI(true);
  } catch (e) {
    console.error("End conversation error:", e);
    document.getElementById("finalResponse").textContent = "Request failed: " + e.message;
    setConversationEndedUI(false);
    setRequestInProgress(false);
    endBtn.textContent = "End conversation";
  }
}

async function sendMessage() {
  if (conversationEnded || requestInProgress) return;
  const input = document.getElementById("userInput");
  const text = input.value.trim();
  if (!text) return;

  const profileId = document.getElementById("profileSelect").value;
  const scenario = getScenarioText();
  conversationHistory.push({ role: "user", content: text });
  renderConversation();
  input.value = "";
  setRequestInProgress(true);
  showChatLoading(true);
  await new Promise(requestAnimationFrame);

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
    showChatLoading(false);

    if (data.status === "ok" && data.response) {
      // Store plain agent reply in history so the next turn has clean dialogue (opening line or follow-up)
      conversationHistory.push({ role: "assistant", content: data.reply != null ? data.reply : data.response });
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
    showChatLoading(false);
    conversationHistory.push({ role: "assistant", content: "Error: " + e.message });
    renderConversation();
  }
  showChatLoading(false);
  setRequestInProgress(false);
}

document.getElementById("profileSelect").addEventListener("change", updateProfileInfo);
document.getElementById("runAgent").addEventListener("click", runAgent);
document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("endConversationBtn").addEventListener("click", endConversation);
const chatAgainBtn = document.getElementById("chatAgainBtn");
if (chatAgainBtn) chatAgainBtn.addEventListener("click", resetConversation);
document.getElementById("userInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

loadProfiles();
loadScenarios();
