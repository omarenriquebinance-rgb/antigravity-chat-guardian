// Lógica de cliente para Antigravity Chat Hub & Viewer

let currentSelectedConvId = null;
let currentProjectFilter = "";
let currentSearchTerm = "";
let allConversations = [];
let allProjects = [];

document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadProjects();
  loadConversations();
  loadStats();
});

function initEventListeners() {
  // Buscador
  const searchInput = document.getElementById("search-input");
  const searchClear = document.getElementById("search-clear");
  
  searchInput.addEventListener("input", (e) => {
    currentSearchTerm = e.target.value.trim();
    searchClear.classList.toggle("hidden", currentSearchTerm.length === 0);
    renderConversationsList();
  });

  searchClear.addEventListener("click", () => {
    searchInput.value = "";
    currentSearchTerm = "";
    searchClear.classList.add("hidden");
    renderConversationsList();
  });

  // Botón Sync
  document.getElementById("btn-sync").addEventListener("click", async () => {
    const btn = document.getElementById("btn-sync");
    btn.classList.add("spinning");
    try {
      const res = await fetch("/api/sync", { method: "POST" });
      const data = await res.json();
      await loadProjects();
      await loadConversations();
      await loadStats();
    } catch (e) {
      console.error("Error al sincronizar:", e);
    } finally {
      btn.classList.remove("spinning");
    }
  });

  // Exportar MD
  document.getElementById("btn-export-md").addEventListener("click", () => {
    if (currentSelectedConvId) {
      window.location.href = `/api/export/${currentSelectedConvId}`;
    }
  });

  // Modal Restauración
  const restoreModal = document.getElementById("restore-modal");
  document.getElementById("btn-restore-ide").addEventListener("click", () => {
    if (!currentSelectedConvId) return;
    const currentConv = allConversations.find(c => c.conversation_id === currentSelectedConvId);
    const targetInput = document.getElementById("restore-workspace-input");
    targetInput.value = currentConv?.workspace_uri || "file:///path/to/project";
    document.getElementById("restore-result-msg").className = "restore-msg hidden";
    restoreModal.classList.remove("hidden");
  });

  document.getElementById("modal-close").addEventListener("click", () => restoreModal.classList.add("hidden"));
  document.getElementById("modal-btn-cancel").addEventListener("click", () => restoreModal.classList.add("hidden"));

  document.getElementById("modal-btn-confirm").addEventListener("click", async () => {
    const targetUri = document.getElementById("restore-workspace-input").value.trim();
    const resultBox = document.getElementById("restore-result-msg");
    const confirmBtn = document.getElementById("modal-btn-confirm");

    confirmBtn.disabled = true;
    confirmBtn.textContent = "Procesando...";

    try {
      const res = await fetch("/api/restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonBody({
          conversation_id: currentSelectedConvId,
          target_workspace_uri: targetUri
        })
      });
      const data = await res.json();
      resultBox.classList.remove("hidden");
      if (data.success) {
        resultBox.className = "restore-msg success";
        resultBox.textContent = "✅ " + data.message;
      } else {
        resultBox.className = "restore-msg error";
        resultBox.textContent = "⚠️ " + data.message;
      }
    } catch (err) {
      resultBox.className = "restore-msg error";
      resultBox.textContent = "Error de conexión: " + err.message;
      resultBox.classList.remove("hidden");
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Aplicar Restauración";
    }
  });
}

function jsonBody(obj) {
  return JSON.stringify(obj);
}

async function loadStats() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    document.getElementById("stat-total-convs").textContent = data.total_conversations || "0";
    document.getElementById("stat-total-msgs").textContent = (data.total_messages || 0).toLocaleString();
    document.getElementById("footer-status-text").textContent = `${data.total_conversations} chats protegidos`;
  } catch (e) {
    console.error("Error al cargar stats:", e);
  }
}

async function loadProjects() {
  try {
    const res = await fetch("/api/projects");
    allProjects = await res.json();
    document.getElementById("stat-total-projs").textContent = allProjects.length;

    const chipsContainer = document.getElementById("project-chips");
    chipsContainer.innerHTML = "";

    // Chip Todos
    const allChip = document.createElement("button");
    allChip.className = `chip ${currentProjectFilter === "" ? "active" : ""}`;
    allChip.innerHTML = `Todos (<span id="total-count">0</span>)`;
    allChip.onclick = () => selectProject("");
    chipsContainer.appendChild(allChip);

    allProjects.forEach(p => {
      const chip = document.createElement("button");
      chip.className = `chip ${currentProjectFilter === p.name ? "active" : ""}`;
      chip.textContent = `${p.name} (${p.count})`;
      chip.onclick = () => selectProject(p.name);
      chipsContainer.appendChild(chip);
    });
  } catch (e) {
    console.error("Error cargando proyectos:", e);
  }
}

function selectProject(projectName) {
  currentProjectFilter = projectName;
  document.querySelectorAll(".project-chips .chip").forEach(el => {
    el.classList.toggle("active", (projectName === "" && el.textContent.startsWith("Todos")) || el.textContent.startsWith(projectName + " "));
  });
  renderConversationsList();
}

async function loadConversations() {
  const listEl = document.getElementById("conversations-list");
  try {
    const res = await fetch("/api/conversations");
    allConversations = await res.json();
    document.getElementById("total-count").textContent = allConversations.length;
    renderConversationsList();
  } catch (e) {
    listEl.innerHTML = `<div class="error-state">Error cargando historial: ${e.message}</div>`;
  }
}

function renderConversationsList() {
  const listEl = document.getElementById("conversations-list");
  
  let filtered = allConversations;
  if (currentProjectFilter) {
    filtered = filtered.filter(c => c.project_name === currentProjectFilter);
  }
  if (currentSearchTerm) {
    const q = currentSearchTerm.toLowerCase();
    filtered = filtered.filter(c => 
      c.title.toLowerCase().includes(q) || 
      c.conversation_id.toLowerCase().includes(q) ||
      (c.project_name && c.project_name.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="empty-list-msg" style="padding: 24px; text-align: center; color: var(--text-dim);">No se encontraron conversaciones.</div>`;
    return;
  }

  listEl.innerHTML = "";
  filtered.forEach(c => {
    const card = document.createElement("div");
    card.className = `conv-card ${currentSelectedConvId === c.conversation_id ? "active" : ""}`;
    card.onclick = () => selectConversation(c.conversation_id);

    const dateFormatted = formatDate(c.updated_at || c.created_at);

    card.innerHTML = `
      <div class="conv-top">
        <span class="conv-project">${escapeHtml(c.project_name || "General")}</span>
        <span class="conv-date">${dateFormatted}</span>
      </div>
      <div class="conv-title" title="${escapeHtml(c.title)}">${escapeHtml(c.title)}</div>
      <div class="conv-meta">
        <span>💬 ${c.user_message_count || 0} msgs</span>
        <span>⚡ ${c.step_count || 0} pasos</span>
      </div>
    `;
    listEl.appendChild(card);
  });
}

async function selectConversation(convId) {
  currentSelectedConvId = convId;
  renderConversationsList();

  const header = document.getElementById("chat-header");
  const messagesContainer = document.getElementById("messages-container");
  const emptyState = document.getElementById("empty-state");

  if (emptyState) emptyState.classList.add("hidden");
  header.classList.remove("hidden");

  messagesContainer.innerHTML = `<div class="loading-state" style="margin: auto; text-align: center;"><div class="spinner"></div><p>Cargando mensajes...</p></div>`;

  try {
    const res = await fetch(`/api/conversations/${convId}`);
    if (!res.ok) throw new Error("No se pudo cargar la conversación");
    const data = await res.json();

    // Actualizar encabezado
    document.getElementById("current-project-tag").textContent = data.project_name || "General";
    document.getElementById("current-chat-title").textContent = data.title;
    document.getElementById("current-chat-date").textContent = formatDate(data.updated_at || data.created_at);
    document.getElementById("current-chat-steps").textContent = `${data.step_count} pasos (${data.messages.length} mensajes)`;
    document.getElementById("current-chat-id").textContent = data.conversation_id;

    renderMessages(data.messages);
  } catch (e) {
    messagesContainer.innerHTML = `<div class="error-msg" style="color: #f87171; padding: 20px;">Error: ${e.message}</div>`;
  }
}

function renderMessages(messages) {
  const container = document.getElementById("messages-container");
  container.innerHTML = "";

  if (!messages || messages.length === 0) {
    container.innerHTML = `<div style="margin: auto; color: var(--text-dim);">Esta conversación no contiene mensajes registrados en el transcript.</div>`;
    return;
  }

  messages.forEach(m => {
    // Filtrar mensajes puramente internos de sistema si no tienen texto
    if (!m.content && (!m.tool_calls || m.tool_calls.length === 0)) return;

    const bubble = document.createElement("div");
    const isUser = m.sender === "user";
    bubble.className = `message-bubble ${isUser ? "message-user" : "message-agent"}`;

    const roleName = isUser ? "Usuario" : "Agente Antigravity";
    const roleClass = isUser ? "role-user" : "role-agent";
    const roleIcon = isUser ? "👤" : "🤖";
    const timeStr = m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : "";

    let formattedContent = formatMarkdownLike(m.content || "");

    let toolCallsHtml = "";
    if (m.tool_calls && m.tool_calls.length > 0) {
      toolCallsHtml = `<div class="tool-calls-box" style="margin-top: 8px; font-size: 0.8rem; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px;">
        <span style="color: var(--accent-cyan); font-weight: 600;">Herramientas ejecutadas:</span>
        <ul style="padding-left: 18px; margin-top: 4px;">
          ${m.tool_calls.map(tc => `<li><code>${escapeHtml(tc.tool_name || tc.name || "tool")}</code></li>`).join("")}
        </ul>
      </div>`;
    }

    bubble.innerHTML = `
      <div class="message-header">
        <span class="role-badge ${roleClass}">${roleIcon} ${roleName}</span>
        <span class="message-time">Paso #${m.step_index} ${timeStr ? "• " + timeStr : ""}</span>
      </div>
      <div class="message-body">${formattedContent}</div>
      ${toolCallsHtml}
    `;

    container.appendChild(bubble);
  });

  // Auto-scroll al final
  container.scrollTop = container.scrollHeight;
}

function formatMarkdownLike(text) {
  let clean = escapeHtml(text);
  
  // Limpiar etiquetas de Antigravity
  clean = clean.replace(/&lt;USER_REQUEST&gt;|&lt;\/USER_REQUEST&gt;/g, "");
  clean = clean.replace(/&lt;ADDITIONAL_METADATA&gt;[\s\S]*?&lt;\/ADDITIONAL_METADATA&gt;/g, "");

  // Bloques de código con triple backticks
  clean = clean.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
  });

  // Código inline
  clean = clean.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Negrita
  clean = clean.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  return clean;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString([], { day: '2-digit', month: '2-digit' });
  } catch (e) {
    return dateStr;
  }
}

function escapeHtml(text) {
  if (!text) return "";
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}
