const chatEl = document.getElementById("chat");
const chipsEl = document.getElementById("chips");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("input");
const sendEl = document.getElementById("send");
const statusEl = document.getElementById("status");
const suggestionsEl = document.getElementById("suggestions");
const toggleSuggestEl = document.getElementById("toggleSuggest");
const clearBtnEl = document.getElementById("clearBtn");
const scrollBtnEl = document.getElementById("scrollBtn");
const msgTemplate = document.getElementById("msgTemplate");

let busy = false;

const SEND_ICON =
  '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
  '<path d="M3.4 20.4l17.45-7.48a1 1 0 0 0 0-1.84L3.4 3.6a1 1 0 0 0-1.39 1.1l1.3 6.05 10.03 1.25-10.03 1.25-1.3 6.05a1 1 0 0 0 1.39 1.1z" fill="currentColor"/></svg>';

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status " + (cls || "");
}

/** Minimal, safe markdown -> HTML: paragraphs, bold, bullet/numbered lists. */
function formatAnswer(text) {
  const lines = escapeHtml(text).split("\n");
  let html = "";
  let listType = null;

  const closeList = () => {
    if (listType) { html += `</${listType}>`; listType = null; }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { closeList(); continue; }

    const bullet = line.match(/^[-*]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);

    if (bullet || numbered) {
      const wanted = bullet ? "ul" : "ol";
      if (listType !== wanted) { closeList(); html += `<${wanted}>`; listType = wanted; }
      html += `<li>${inline(bullet ? bullet[1] : numbered[1])}</li>`;
    } else {
      closeList();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return html || "<p></p>";
}

function inline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

function atBottom() {
  return chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight < 80;
}

function scrollToBottom(force) {
  if (force || atBottom()) {
    chatEl.scrollTop = chatEl.scrollHeight;
  }
}

function addMessage(role, html) {
  const node = msgTemplate.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  const avatar = node.querySelector(".avatar");
  const bubble = node.querySelector(".bubble");

  if (role === "bot") {
    avatar.classList.add("bot-avatar");
    avatar.textContent = "KMV";
  } else {
    avatar.classList.add("user-avatar");
    avatar.textContent = "You";
  }

  if (html !== undefined) bubble.innerHTML = html;
  chatEl.appendChild(node);
  scrollToBottom(true);
  return bubble;
}

function typingHtml() {
  return '<span class="typing" aria-label="Thinking"><i></i><i></i><i></i></span>';
}

function renderSources(bubble, sources) {
  const tools = document.createElement("div");
  tools.className = "msg-tools";

  if (sources && sources.length) {
    const box = document.createElement("div");
    box.className = "sources";
    const seen = new Set();
    const tags = [];
    for (const s of sources) {
      const label = s.heading || s.source;
      if (seen.has(label)) continue;
      seen.add(label);
      tags.push(`<span class="tag" title="${escapeHtml(s.source)}">${escapeHtml(label)}</span>`);
    }
    box.innerHTML = "Sources: " + tags.join("");
    tools.appendChild(box);
  }

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "tool";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => copyText(copy, bubble.dataset.plain || bubble.textContent));
  tools.appendChild(copy);

  bubble.appendChild(tools);
}

async function copyText(button, text) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied!";
  } catch {
    button.textContent = "Copy failed";
  }
  setTimeout(() => { button.textContent = "Copy"; }, 1500);
}

async function loadFaqs() {
  try {
    const res = await fetch("/api/faqs");
    const data = await res.json();
    chipsEl.innerHTML = "";
    (data.questions || []).forEach((q) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = q;
      chip.addEventListener("click", () => ask(q));
      chipsEl.appendChild(chip);
    });
  } catch (err) {
    console.error("Failed to load FAQs", err);
  }
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    setStatus(`Online · ${data.chat_model}`, "ok");
  } catch {
    setStatus("Offline", "bad");
  }
}

function setBusy(state) {
  busy = state;
  sendEl.disabled = state;
  sendEl.innerHTML = state ? '<span class="spinner"></span>' : SEND_ICON;
  inputEl.disabled = state;
}

function autoGrow() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
}

async function ask(question) {
  question = (question || "").trim();
  if (busy || !question) return;

  setBusy(true);
  inputEl.value = "";
  autoGrow();

  addMessage("user", `<p>${escapeHtml(question)}</p>`);

  const botBubble = addMessage("bot", typingHtml());
  let answerText = "";
  let sources = [];

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!res.ok || !res.body) throw new Error(`Server returned ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split("\n\n");
      buffer = parts.pop();

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        let event;
        try { event = JSON.parse(line.slice(5).trim()); }
        catch { continue; }

        if (event.type === "sources") {
          sources = event.sources || [];
        } else if (event.type === "token") {
          answerText += event.token;
          const stick = atBottom();
          botBubble.dataset.plain = answerText;
          botBubble.innerHTML = formatAnswer(answerText) + typingHtml();
          if (stick) scrollToBottom(true);
        } else if (event.type === "error") {
          throw new Error(event.error);
        }
      }
    }

    botBubble.dataset.plain = answerText || "";
    botBubble.innerHTML = formatAnswer(answerText || "(No answer was generated.)");
    renderSources(botBubble, sources);
  } catch (err) {
    const message = `Sorry, something went wrong: ${err.message || err}.`;
    botBubble.dataset.plain = message;
    botBubble.innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
    renderSources(botBubble, []);
  } finally {
    setBusy(false);
    inputEl.focus();
    scrollToBottom(true);
  }
}

/* ---------- Events ---------- */
formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  ask(inputEl.value);
});

inputEl.addEventListener("input", autoGrow);

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    ask(inputEl.value);
  }
});

toggleSuggestEl.addEventListener("click", () => {
  const collapsed = suggestionsEl.classList.toggle("collapsed");
  toggleSuggestEl.textContent = collapsed ? "Show" : "Hide";
  toggleSuggestEl.setAttribute("aria-expanded", String(!collapsed));
});

clearBtnEl.addEventListener("click", () => {
  chatEl.innerHTML = "";
  addMessage("bot", `<p>Chat cleared. How can I help you with Keshav Mahavidyalaya?</p>`);
});

chatEl.addEventListener("scroll", () => {
  scrollBtnEl.hidden = atBottom();
});

scrollBtnEl.addEventListener("click", () => scrollToBottom(true));

loadFaqs();
checkHealth();
inputEl.focus();
