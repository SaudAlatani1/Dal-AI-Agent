/* ══════════════════════════════════════════════════════════════
   دالّ — Light Mode Chat Logic
   Separates Intent Box (top) from Chat Flow (middle)
   Connects to FastAPI at /api/query and /api/chat
   ══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;

// ─── DOM ─────────────────────────────────────────────────────
const mainArea      = document.getElementById("mainArea");
const welcomeScreen = document.getElementById("welcomeScreen");
const aboutSection   = document.getElementById("aboutSection");
const intentBox     = document.getElementById("intentBox");
const intentText    = document.getElementById("intentText");
const chatFlow      = document.getElementById("chatFlow");
const quranVerse    = document.getElementById("quranVerse");
const inputForm     = document.getElementById("inputForm");
const inputField    = document.getElementById("inputField");
const sendBtn       = document.getElementById("sendBtn");

// ─── State ───────────────────────────────────────────────────
let isFirstQuery = true;
let isProcessing = false;
let chatHistory  = [];
let currentPlatforms = [];

// ─── Icon Map ────────────────────────────────────────────────
const ICON_MAP = {
  "\u0637\u0628\u064A": "\uD83C\uDFE5", "\u0633\u0643\u0646\u064A": "\uD83C\uDFE0",
  "\u0645\u0627\u0644\u064A": "\uD83D\uDCB0", "\u0632\u0643\u0627\u0629": "\uD83D\uDCB0",
  "\u0635\u062F\u0642\u0629": "\uD83D\uDCB0", "\u062C\u0647\u062F\u064A": "\uD83E\uDD1D",
  "\u062A\u0637\u0648\u0639": "\uD83E\uDD1D", "\u063A\u0630\u0627\u0626\u064A": "\uD83C\uDF7D\uFE0F",
  "\u0625\u0637\u0639\u0627\u0645": "\uD83C\uDF7D\uFE0F", "\u0645\u064A\u0627\u0647": "\uD83D\uDCA7",
  "\u0633\u0642\u064A\u0627": "\uD83D\uDCA7", "\u0643\u0641\u0627\u0644\u0629": "\uD83D\uDC66",
  "\u0623\u064A\u062A\u0627\u0645": "\uD83D\uDC66", "\u0648\u0642\u0641": "\uD83D\uDD4C",
  "\u0643\u0633\u0648\u0629": "\uD83D\uDC55", "\u062A\u0639\u0644\u064A\u0645\u064A": "\uD83D\uDCDA",
};

// SVG templates
const SPARK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`;

const USER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;

// ─── Input Toggle + Dynamic Send Button Color ───────────────
inputField.addEventListener("input", () => {
  const hasText = inputField.value.trim().length > 0;
  sendBtn.disabled = !hasText || isProcessing;
  sendBtn.classList.toggle("active", hasText);
});

// ─── Submit ──────────────────────────────────────────────────
inputForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputField.value.trim();
  if (!text || isProcessing) return;

  if (isFirstQuery) {
    handleFirstQuery(text);
  } else {
    handleFollowUp(text);
  }
});


// ═══════════════════════════════════════════════════════════════
// First Query — shows Intent Box + AI response + Platform Cards
// ═══════════════════════════════════════════════════════════════
async function handleFirstQuery(text) {
  isProcessing = true;
  isFirstQuery = false;
  sendBtn.disabled = true;
  inputField.value = "";

  // Hide welcome + quran + about, show intent
  welcomeScreen.style.display = "none";
  aboutSection.style.display = "none";
  if (quranVerse) quranVerse.style.display = "none";
  intentBox.style.display = "block";
  intentText.textContent = text;

  // Change placeholder for follow-up
  inputField.placeholder = "\u0627\u0633\u0623\u0644 \u0639\u0646 \u0627\u0644\u0645\u0646\u0635\u0629...";

  // Typing indicator in chat
  const typing = appendTyping();

  try {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    typing.remove();

    // AI text
    if (data.response) {
      appendAIMessage(data.response);
    }

    // Platform cards
    if (data.platforms && data.platforms.length > 0) {
      currentPlatforms = data.platforms;
      appendPlatformCards(data.platforms);
    }

    chatHistory.push({ role: "user", content: text });
    chatHistory.push({ role: "ai", content: data.response || "" });
  } catch (err) {
    typing.remove();
    appendAIMessage("\u0639\u0630\u0631\u0627\u064B\u060C \u062D\u062F\u062B \u062E\u0637\u0623 \u0641\u064A \u0627\u0644\u0627\u062A\u0635\u0627\u0644. \u062A\u0623\u0643\u062F \u0623\u0646 \u0627\u0644\u0633\u064A\u0631\u0641\u0631 \u0634\u063A\u0627\u0644.");
    console.error(err);
  }

  isProcessing = false;
  sendBtn.disabled = !inputField.value.trim();
  scrollToBottom();
}

// ═══════════════════════════════════════════════════════════════
// Follow-up — regular chat about the platforms
// ═══════════════════════════════════════════════════════════════
async function handleFollowUp(text) {
  isProcessing = true;
  sendBtn.disabled = true;
  inputField.value = "";

  appendUserMessage(text);
  const typing = appendTyping();

  chatHistory.push({ role: "user", content: text });

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history: chatHistory,
        platforms: currentPlatforms,
        previous_response: chatHistory.find((m) => m.role === "ai")?.content || "",
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    typing.remove();
    appendAIMessage(data.response || "");
    chatHistory.push({ role: "ai", content: data.response || "" });
  } catch (err) {
    typing.remove();
    appendAIMessage("\u0639\u0630\u0631\u0627\u064B\u060C \u062D\u062F\u062B \u062E\u0637\u0623. \u062D\u0627\u0648\u0644 \u0645\u0631\u0629 \u0623\u062E\u0631\u0649.");
    console.error(err);
  }

  isProcessing = false;
  sendBtn.disabled = !inputField.value.trim();
  scrollToBottom();
}

// ─── Append Helpers ──────────────────────────────────────────

function appendUserMessage(text) {
  const el = document.createElement("div");
  el.className = "chat-msg user";
  el.innerHTML = `
    <div class="chat-avatar">${USER_SVG}</div>
    <div class="chat-bubble">${escapeHtml(text)}</div>`;
  chatFlow.appendChild(el);
  scrollToBottom();
}

function appendAIMessage(text) {
  const el = document.createElement("div");
  el.className = "chat-msg ai";

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.innerHTML = SPARK_SVG;

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.style.opacity = "0";

  el.appendChild(avatar);
  el.appendChild(bubble);
  chatFlow.appendChild(el);

  // Typing animation
  typeText(bubble, text);
  scrollToBottom();
}

function appendTyping() {
  const el = document.createElement("div");
  el.className = "chat-msg ai";
  el.innerHTML = `
    <div class="chat-avatar">${SPARK_SVG}</div>
    <div class="chat-bubble">
      <div class="typing-dots"><span></span><span></span><span></span></div>
    </div>`;
  chatFlow.appendChild(el);
  scrollToBottom();
  return el;
}

// ─── Platform Cards ──────────────────────────────────────────

function appendPlatformCards(platforms) {
  const container = document.createElement("div");
  container.className = "platform-cards";

  platforms.forEach((p) => {
    const card = document.createElement("div");
    card.className = "platform-card";

    // Icon
    const givingTypes = p.giving_types || [];
    let icon = "\uD83C\uDF1F";
    for (const t of givingTypes) {
      for (const [kw, emoji] of Object.entries(ICON_MAP)) {
        if (t.includes(kw)) { icon = emoji; break; }
      }
      if (icon !== "\uD83C\uDF1F") break;
    }

    // Services (max 3)
    const svcs = (p.services || []).slice(0, 3);
    const svcsHTML = svcs
      .map((s) => `<div class="svc-row"><div class="svc-dot"></div><span>${escapeHtml(s)}</span></div>`)
      .join("");

    card.innerHTML = `
      <div class="card-top">
        <div class="card-icon">${icon}</div>
        <div class="card-name">${escapeHtml(p.name || "")}</div>
      </div>
      <div class="card-pills">
        <span class="pill green">${escapeHtml(p.supervisor || "")}</span>
        <span class="pill grey">${escapeHtml(p.intervention_type || "")}</span>
      </div>
      <div class="card-services">${svcsHTML}</div>
      <a class="card-cta" href="${p.direct_url || "#"}" target="_blank" rel="noopener">
        \u0627\u0646\u062A\u0642\u0644 \u0625\u0644\u0649 ${escapeHtml(p.name || "\u0627\u0644\u0645\u0646\u0635\u0629")} \u2190
      </a>`;

    container.appendChild(card);
  });

  chatFlow.appendChild(container);
  scrollToBottom();
}

// ─── Typing Animation ────────────────────────────────────────

function typeText(el, text, speed = 16) {
  el.style.opacity = "1";
  let i = 0;
  const interval = setInterval(() => {
    el.textContent = text.slice(0, i + 1);
    i++;
    if (i >= text.length) clearInterval(interval);
    scrollToBottom();
  }, speed);
}

// ─── Utilities ───────────────────────────────────────────────

function scrollToBottom() {
  requestAnimationFrame(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
