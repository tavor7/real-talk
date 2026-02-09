// Force immediate execution test
(function() {
  console.log("[DEBUG] app.js script loading...");
  console.log("[DEBUG] Timestamp:", new Date().toISOString());
  window._appJsLoaded = true;
  window._appJsVersion = "2.0";
})();

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

// Define endConversation function early so it's available for inline onclick
// First declare it globally to ensure it exists immediately
window.endConversation = async function endConversation() {
  console.log("[DEBUG] endConversation function called!", {
    conversationEnded,
    requestInProgress,
    historyLength: conversationHistory?.length || 0,
    stack: new Error().stack
  });
  
  // Try to get button - check both ways
  let endBtn = document.getElementById("endConversationBtn");
  if (!endBtn && window.endConversationBtnRef) {
    endBtn = window.endConversationBtnRef;
    console.log("[DEBUG] Using stored button reference");
  }
  
  if (!endBtn) {
    console.error("endConversationBtn not found");
    alert("Error: End conversation button not found. Please refresh the page.");
    return;
  }
  
  console.log("[DEBUG] Button state:", {
    disabled: endBtn.disabled,
    textContent: endBtn.textContent,
    visible: endBtn.offsetParent !== null,
    display: window.getComputedStyle(endBtn).display,
    pointerEvents: window.getComputedStyle(endBtn).pointerEvents
  });

  if (conversationEnded) {
    console.log("Conversation already ended, showing summary");
    showSection("summarySection");
    showSection("responseSection");
    return;
  }

  if (requestInProgress) {
    console.log("Request already in progress, ignoring endConversation");
    return;
  }

  if (!conversationHistory || conversationHistory.length === 0) {
    alert("No messages yet — send at least one message before ending the conversation.");
    return;
  }
  
  // Ensure button is enabled before proceeding
  if (endBtn.disabled) {
    console.warn("[DEBUG] Button was disabled, enabling it now");
    endBtn.disabled = false;
  }

  const profileId = (document.getElementById("profileSelect") && document.getElementById("profileSelect").value) || "";
  const scenario = getScenarioText();

  console.log("End conversation clicked", { 
    profileId, 
    scenario, 
    historyLength: conversationHistory.length,
    API_BASE: API_BASE || "(empty - will use relative)",
    conversationEnded,
    requestInProgress
  });
  
  if (!API_BASE && window.location.protocol !== "file:") {
    console.warn("API_BASE is empty and not using file:// protocol. API calls may fail.");
  }
  
  setRequestInProgress(true);
  endBtn.textContent = "Ending...";
  endBtn.disabled = true;
  showSection("responseSection");

  try {
    const url = `${API_BASE}/api/execute`;
    console.log("Sending end conversation request to:", url);
    const requestBody = {
      prompt: "",
      user_profile_id: profileId,
      scenario,
      conversation_history: conversationHistory,
      end_conversation: true,
    };
    console.log("Request body:", requestBody);
    
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    
    console.log("Response status:", res.status, res.statusText);

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
      // Render request/response fields even on error
      renderRequestResponseFields(requestBody, data);
      showSection("requestResponseSection");
      setRequestInProgress(false);
      endBtn.textContent = "End conversation";
      return;
    }

    // Render request/response fields
    renderRequestResponseFields(requestBody, data);
    showSection("requestResponseSection");

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
    setRequestInProgress(false); // Reset request state after successful end
    endBtn.textContent = "End conversation"; // Reset button text
  } catch (e) {
    console.error("End conversation error:", e);
    document.getElementById("finalResponse").textContent = "Request failed: " + e.message;
    setConversationEndedUI(false);
    setRequestInProgress(false);
    endBtn.textContent = "End conversation";
  }
};

console.log("[DEBUG] endConversation function assigned to window.endConversation");

// Verify function is set immediately
console.log("[DEBUG] endConversation function defined:", typeof window.endConversation);
if (typeof window.endConversation !== 'function') {
  console.error("[DEBUG] ERROR: window.endConversation is not a function! Type:", typeof window.endConversation);
} else {
  console.log("[DEBUG] ✓ window.endConversation is ready and accessible");
}

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
  // Removed scrollIntoView to prevent autoscroll
  
  // If chatSection is shown, ensure end conversation button has event listener
  if (id === "chatSection") {
    setTimeout(() => {
      const endBtn = document.getElementById("endConversationBtn");
      if (endBtn && !endBtn.hasAttribute("data-listener-attached")) {
        console.log("[DEBUG] Re-attaching end conversation listener after chatSection shown");
        endBtn.setAttribute("data-listener-attached", "true");
        endBtn.addEventListener("click", function() {
          console.log("[DEBUG] End conversation clicked (re-attached listener)");
          if (typeof window.endConversation === 'function') {
            window.endConversation();
          } else {
            console.error("[DEBUG] window.endConversation not available!");
          }
        });
      }
    }, 100);
  }
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
  if (endBtn) {
    endBtn.disabled = inProgress || conversationEnded;
    console.log(`[DEBUG] setRequestInProgress(${inProgress}) - endBtn.disabled = ${endBtn.disabled} (conversationEnded: ${conversationEnded})`);
  }
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
  document.getElementById("requestFields").innerHTML = "";
  document.getElementById("responseFields").innerHTML = "";
  setConversationEndedUI(false);
  setRequestInProgress(false);
  hideSection("responseSection");
  hideSection("summarySection");
  hideSection("stepsSection");
  hideSection("requestResponseSection");
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
  // Removed scrollTop to prevent autoscroll
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
  
  // Agent descriptions
  const agentDescriptions = {
    "SupervisorAgent": "Orchestrates flow, decides sub-agent, aggregates response",
    "ProgramPlanner": "Plan & Execute: learning objective, conversation structure",
    "SystemCritic": "Reflection: reviews dialogue, slang/safety/level, decides when to finish",
    "ScenarioArchitect": "Builds scenarios from RAG + user profile; predefined scenarios for fast start",
    "UserEvaluation": "ReAct: interacts during conversation, adapts difficulty, updates proficiency, produces summary"
  };
  
  box.innerHTML = steps
    .map((s) => {
      const promptStr = typeof s.prompt === "object" ? JSON.stringify(s.prompt, null, 2) : String(s.prompt || "");
      const rawResp = s.response;
      const responseStr = rawResp === null || rawResp === undefined ? "" : String(rawResp);
      const responseDisplay = responseStr.trim() === "" ? "(empty or null — no response from this step)" : responseStr;
      const promptLen = promptStr.length;
      const responseLen = responseDisplay.length;
      const agentDesc = agentDescriptions[s.module] || "";
      return `
    <div class="step">
      <div class="module">
        <span class="module-name">${escapeHtml(s.module)}</span>
        ${agentDesc ? `<span class="module-description">${escapeHtml(agentDesc)}</span>` : ""}
      </div>
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

function renderRequestResponseFields(requestData, responseData) {
  const requestBox = document.getElementById("requestFields");
  const responseBox = document.getElementById("responseFields");
  
  if (!requestBox || !responseBox) return;
  
  // Render request fields
  const requestFields = [
    { label: "prompt", value: requestData.prompt || "(empty)", fullValue: requestData.prompt || "(empty)" },
    { label: "user_profile_id", value: requestData.user_profile_id || "(not set)", fullValue: requestData.user_profile_id || "(not set)" },
    { label: "scenario", value: requestData.scenario || "(not set)", fullValue: requestData.scenario || "(not set)" },
    { label: "conversation_history", value: requestData.conversation_history ? `${requestData.conversation_history.length} message(s)` : "[] (empty)", fullValue: JSON.stringify(requestData.conversation_history || [], null, 2) },
    { label: "end_conversation", value: requestData.end_conversation ? "true" : "false", fullValue: String(requestData.end_conversation || false) },
  ];
  
  requestBox.innerHTML = requestFields
    .map(f => {
      const displayValue = f.value.length > 100 ? f.value.substring(0, 100) + "..." : f.value;
      return `
      <div class="field-item">
        <strong>${escapeHtml(f.label)}:</strong>
        <div class="field-value">${escapeHtml(displayValue)}</div>
        ${f.fullValue.length > 100 ? `<details><summary>Show full value</summary><pre class="field-full-value">${escapeHtml(f.fullValue)}</pre></details>` : ""}
      </div>
    `;
    })
    .join("");
  
  // Render response fields
  const responseFields = [
    { label: "status", value: responseData.status || "(not set)", fullValue: responseData.status || "(not set)" },
    { label: "error", value: responseData.error || "null", fullValue: responseData.error || "null" },
    { label: "response", value: responseData.response ? `${responseData.response.length} chars` : "null", fullValue: responseData.response || "null" },
    { label: "reply", value: responseData.reply ? `${responseData.reply.length} chars` : "null", fullValue: responseData.reply || "null" },
    { label: "steps", value: responseData.steps ? `${responseData.steps.length} step(s)` : "[] (empty)", fullValue: JSON.stringify(responseData.steps || [], null, 2) },
  ];
  
  responseBox.innerHTML = responseFields
    .map(f => {
      const displayValue = f.value.length > 100 ? f.value.substring(0, 100) + "..." : f.value;
      return `
      <div class="field-item">
        <strong>${escapeHtml(f.label)}:</strong>
        <div class="field-value">${escapeHtml(displayValue)}</div>
        ${f.fullValue.length > 100 ? `<details><summary>Show full value</summary><pre class="field-full-value">${escapeHtml(f.fullValue)}</pre></details>` : ""}
      </div>
    `;
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

  const requestBody = {
    prompt,
    user_profile_id: profileId,
    scenario,
    conversation_history: [],
    end_conversation: false,
  };

  try {
    const res = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await res.json();

    // Render request/response fields
    renderRequestResponseFields(requestBody, data);
    showSection("requestResponseSection");

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
      // Ensure end conversation button is enabled when conversation starts
      const endBtn = document.getElementById("endConversationBtn");
      if (endBtn && !requestInProgress && !conversationEnded) {
        endBtn.disabled = false;
        console.log("[DEBUG] Enabled end conversation button when conversation started");
      }
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
    // Removed scrollTop to prevent autoscroll
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

// endConversation function already defined above (line 15)

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

  const requestBody = {
    prompt: text,
    user_profile_id: profileId,
    scenario,
    conversation_history: conversationHistory.slice(0, -1),
    end_conversation: false,
  };

  try {
    const res = await fetch(`${API_BASE}/api/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await res.json();
    showChatLoading(false);

    // Render request/response fields
    renderRequestResponseFields(requestBody, data);
    showSection("requestResponseSection");

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
    // Ensure end conversation button is enabled after sending a message
    const endBtn = document.getElementById("endConversationBtn");
    if (endBtn && !conversationEnded && !requestInProgress) {
      endBtn.disabled = false;
      console.log("[DEBUG] Enabled end conversation button after sending message");
    }
  } catch (e) {
    showChatLoading(false);
    conversationHistory.push({ role: "assistant", content: "Error: " + e.message });
    renderConversation();
  }
  showChatLoading(false);
  setRequestInProgress(false);
}

// Wait for DOM to be ready before attaching event listeners
function initEventListeners() {
  const profileSelect = document.getElementById("profileSelect");
  const runAgentBtn = document.getElementById("runAgent");
  const sendBtn = document.getElementById("sendBtn");
  const endConversationBtn = document.getElementById("endConversationBtn");
  const chatAgainBtn = document.getElementById("chatAgainBtn");
  const userInput = document.getElementById("userInput");
  
  if (profileSelect) profileSelect.addEventListener("change", updateProfileInfo);
  if (runAgentBtn) runAgentBtn.addEventListener("click", runAgent);
  if (sendBtn) sendBtn.addEventListener("click", sendMessage);
  if (endConversationBtn) {
    // Remove any existing listeners by cloning and replacing
    const newBtn = endConversationBtn.cloneNode(true);
    endConversationBtn.parentNode.replaceChild(newBtn, endConversationBtn);
    
    // Attach listener to the new button
    newBtn.addEventListener("click", function(e) {
      e.preventDefault();
      e.stopPropagation();
      console.log("[DEBUG] End conversation button clicked!", {
        disabled: newBtn.disabled,
        conversationEnded,
        requestInProgress,
        historyLength: conversationHistory?.length || 0
      });
      
      // Force enable if disabled (for debugging)
      if (newBtn.disabled) {
        console.warn("[DEBUG] Button was disabled, but click registered. Forcing enable for debugging.");
        newBtn.disabled = false;
      }
      
      // Call the function
      if (typeof window.endConversation === 'function') {
        window.endConversation();
      } else {
        console.error("[DEBUG] window.endConversation is not a function!", typeof window.endConversation);
        alert("Error: endConversation function not available. Please refresh the page.");
      }
    });
    
    // Also try mousedown as backup
    newBtn.addEventListener("mousedown", function(e) {
      console.log("[DEBUG] End conversation button mousedown event!");
    });
    
    console.log("End conversation button event listener attached to:", newBtn);
    
    // Ensure button is enabled initially if there's a conversation
    if (conversationHistory && conversationHistory.length > 0 && !conversationEnded) {
      newBtn.disabled = false;
    }
    
    // Store reference
    window.endConversationBtnRef = newBtn;
  } else {
    console.error("endConversationBtn not found when attaching event listener");
  }
  if (chatAgainBtn) chatAgainBtn.addEventListener("click", resetConversation);
  if (userInput) {
    userInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }
}

// Test button immediately
function testEndButton() {
  const endBtn = document.getElementById("endConversationBtn");
  if (endBtn) {
    console.log("[DEBUG] End conversation button found on page load:", {
      id: endBtn.id,
      disabled: endBtn.disabled,
      textContent: endBtn.textContent,
      className: endBtn.className,
      parentElement: endBtn.parentElement?.id || "none"
    });
    
    // Add a simple test click
    endBtn.addEventListener("click", function testClick(e) {
      console.log("[TEST] Button click test fired!", e);
      alert("Button click test works! Now calling endConversation...");
    }, { once: true });
  } else {
    console.error("[DEBUG] End conversation button NOT found on page load");
  }
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    testEndButton();
    initEventListeners();
  });
} else {
  testEndButton();
  initEventListeners();
}

// Ensure end conversation button is enabled on page load (if conversation exists)
window.addEventListener("load", () => {
  const endBtn = document.getElementById("endConversationBtn");
  if (endBtn && conversationHistory && conversationHistory.length > 0 && !conversationEnded) {
    endBtn.disabled = false;
    console.log("[DEBUG] Enabled end conversation button on page load");
  }
});

loadProfiles();
loadScenarios();

// Verify endConversation is accessible globally
setTimeout(() => {
  if (typeof window.endConversation === 'function') {
    console.log("[DEBUG] ✓ endConversation is globally accessible");
  } else {
    console.error("[DEBUG] ✗ endConversation is NOT globally accessible");
  }
}, 1000);
