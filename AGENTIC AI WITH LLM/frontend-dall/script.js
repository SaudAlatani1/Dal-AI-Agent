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
const statVisits    = document.getElementById("statVisits");
const statImpact    = document.getElementById("statImpact");
const linkCheckerForm = document.getElementById("linkCheckerForm");
const linkInput     = document.getElementById("linkInput");
const linkCheckBtn  = document.getElementById("linkCheckBtn");
const linkResult    = document.getElementById("linkResult");

// ─── State ───────────────────────────────────────────────────
let isFirstQuery = true;
let isProcessing = false;
let chatHistory  = [];
let currentPlatforms = [];

// ─── Clean Slate — Reset after every completed query ────────
function resetForNewQuery() {
  isFirstQuery = true;
  chatHistory = [];
  currentPlatforms = [];
  inputField.value = "";
  inputField.placeholder = "وش حاب تبحث عنه بعد؟ صف حالة أخرى هنا...";
  sendBtn.disabled = true;
  sendBtn.classList.remove("active");
}

function clearPreviousResults() {
  chatFlow.innerHTML = "";
  intentBox.style.display = "none";
  intentText.textContent = "";
}

// ─── Icon Map ────────────────────────────────────────────────
const ICON_MAP = {
  "طبي": "🏥", "سكني": "🏠", "مالي": "💰", "زكاة": "💰",
  "صدقة": "💰", "جهدي": "🤝", "تطوع": "🤝", "غذائي": "🍽️",
  "إطعام": "🍽️", "مياه": "💧", "سقيا": "💧", "كفالة": "👦",
  "أيتام": "👦", "وقف": "🕌", "كسوة": "👕", "تعليمي": "📚",
  "ديني": "🕌", "تقني": "💻", "عيني": "🎁", "اجتماعي": "🤲",
  "تدريب": "🎓", "تمويل": "💳", "تمكين": "💪", "معنوي": "❤️",
  "تأهيلي": "🏋️", "سداد ديون": "🔓", "معلوماتي": "ℹ️",
  "منح دراسية": "🎓", "بحث علمي": "🔬", "ملابس": "👕", "أثاث": "🛋️",
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

// ─── URL Detection ───────────────────────────────────────────
const URL_REGEX = /https?:\/\/[^\s<>"{}|\\^`\[\]]+|(?:www\.)[^\s<>"{}|\\^`\[\]]+|[a-zA-Z0-9][\w.-]*\.(?:sa|gov\.sa|com|net|org|info|xyz|online|ly|co|gl|gd|link|in)(?:\/[^\s]*)?/i;

function extractUrl(text) {
  const match = text.match(URL_REGEX);
  if (!match) return null;
  let url = match[0];
  if (!url.startsWith("http")) url = "https://" + url;
  return url;
}

// ─── Submit ──────────────────────────────────────────────────
inputForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputField.value.trim();
  if (!text || isProcessing) return;
  handleFirstQuery(text);
});

// ─── Link Checker (standalone) ──────────────────────────────
linkInput.addEventListener("input", () => {
  linkCheckBtn.disabled = linkInput.value.trim().length === 0;
});

linkCheckerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = linkInput.value.trim();
  if (!raw) return;

  let url = raw;
  if (!url.startsWith("http")) url = "https://" + url;

  linkCheckBtn.disabled = true;
  linkCheckBtn.textContent = "جارٍ الفحص...";
  linkResult.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/api/analyze-link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    let verdictClass = "safe";
    if (data.verdict.includes("مشبوه")) verdictClass = "suspicious";
    if (data.verdict.includes("خطير")) verdictClass = "dangerous";

    linkResult.innerHTML = `
      <div class="link-result-card ${verdictClass}">
        <div class="link-result-verdict">${escapeHtml(data.verdict)}</div>
        <div class="link-result-desc">${escapeHtml(data.verdict_desc || "")}</div>
        <div class="link-result-url">${escapeHtml(data.hostname)}</div>
      </div>`;
  } catch {
    linkResult.innerHTML = `
      <div class="link-result-card dangerous">
        <div class="link-result-verdict">خطأ</div>
        <div class="link-result-desc">حدث خطأ في تحليل الرابط. حاول مرة أخرى.</div>
      </div>`;
  }

  linkCheckBtn.textContent = "تحقق";
  linkCheckBtn.disabled = false;
});


// ═══════════════════════════════════════════════════════════════
// First Query — shows Intent Box + AI response + Platform Cards
// ═══════════════════════════════════════════════════════════════
async function handleFirstQuery(text) {
  isProcessing = true;
  isFirstQuery = false;
  sendBtn.disabled = true;
  inputField.value = "";

  // Clean Slate — clear any previous results before showing new ones
  clearPreviousResults();

  // Hide welcome + quran + about, show intent
  welcomeScreen.style.display = "none";
  aboutSection.style.display = "none";
  if (quranVerse) quranVerse.style.display = "none";
  intentBox.style.display = "block";
  intentText.textContent = text;

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
      appendPlatformCards(data.platforms);
    }

    // Close Context — reset state for clean slate (no data contamination)
    resetForNewQuery();
  } catch (err) {
    typing.remove();
    appendAIMessage("عذراً، حدث خطأ في الاتصال. تأكد أن السيرفر شغال.");
    console.error(err);

    // Reset even on error
    resetForNewQuery();
  }

  isProcessing = false;
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
        انتقل إلى ${escapeHtml(p.name || "المنصة")} ←
      </a>`;

    // Impact tracking — increment counter ONLY on CTA click
    const cta = card.querySelector(".card-cta");
    cta.addEventListener("click", (e) => {
      e.preventDefault();
      recordImpact();
      window.open(cta.href, "_blank", "noopener");
    });

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

// ─── Stats — Traffic & Impact Counters ──────────────────────

function easeOutExpo(t) {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

function animateCounter(el, target, delay = 0) {
  const duration = 1800;
  const start = parseInt(el.textContent) || 0;
  if (start === target) return;
  const diff = target - start;

  setTimeout(() => {
    el.classList.add("counter-animate");
    const startTime = performance.now();
    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutExpo(progress);
      el.textContent = Math.floor(start + diff * eased).toLocaleString("ar-SA");
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.classList.remove("counter-animate");
      }
    }
    requestAnimationFrame(step);
  }, delay);
}

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (!res.ok) return;
    const data = await res.json();
    animateCounter(statVisits, data.total_visits || 0, 300);
    animateCounter(statImpact, data.actual_impact_count || 0, 700);
  } catch { /* silent */ }
}

async function recordVisit() {
  try {
    const res = await fetch(`${API_BASE}/api/stats/visit`, { method: "POST" });
    if (!res.ok) return;
    const data = await res.json();
    animateCounter(statVisits, data.total_visits || 0, 300);
  } catch { /* silent */ }
}

async function recordImpact() {
  try {
    const res = await fetch(`${API_BASE}/api/stats/impact`, { method: "POST" });
    if (!res.ok) return;
    const data = await res.json();
    animateCounter(statImpact, data.actual_impact_count || 0);
  } catch { /* silent */ }
}

// ─── Session Start — record visit once per session ──────────
if (!sessionStorage.getItem("dall_visited")) {
  sessionStorage.setItem("dall_visited", "1");
  recordVisit();
} else {
  loadStats();
}
