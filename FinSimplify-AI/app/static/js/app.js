/**
 * FinSimplify AI frontend. Uses Fetch API and safe DOM methods (textContent) only
 * for anything derived from external news / AI content.
 */
(function () {
  "use strict";

  const API_BASE = "/api";
  let currentQuery = "";
  let currentTopic = "";
  const summaryCache = new Map();

  const newsGrid = document.getElementById("news-grid");
  const emptyState = document.getElementById("empty-state");
  const statusBanner = document.getElementById("status-banner");
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("search-input");
  const topicFilters = document.getElementById("topic-filters");
  const refreshBtn = document.getElementById("refresh-btn");
  const modalOverlay = document.getElementById("modal-overlay");
  const modalContent = document.getElementById("modal-content");
  const modalClose = document.getElementById("modal-close");
  const skeletonTemplate = document.getElementById("skeleton-card-template");

  function showStatus(message, type) {
    statusBanner.textContent = message;
    statusBanner.className = "status-banner " + type;
    statusBanner.hidden = false;
  }
  function clearStatus() {
    statusBanner.hidden = true;
    statusBanner.textContent = "";
  }
  function isSafeHttpUrl(value) {
    try {
      const p = new URL(value, window.location.href);
      return p.protocol === "https:" || p.protocol === "http:";
    } catch (e) {
      return false;
    }
  }
  function formatDate(iso) {
    if (!iso) return "Date unknown";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "Date unknown";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }
  function el(tag, className, text) {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function renderSkeletons(count) {
    clear(newsGrid);
    emptyState.hidden = true;
    for (let i = 0; i < count; i++) newsGrid.appendChild(skeletonTemplate.content.cloneNode(true));
  }

  function renderArticles(articles) {
    clear(newsGrid);
    if (!articles || articles.length === 0) {
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;
    articles.forEach((a) => newsGrid.appendChild(buildCard(a)));
  }

  function buildImagePlaceholder() {
    return el("div", "card-img-placeholder", "📰");
  }


  function buildCard(article) {
    const card = el("article", "card");

    if (article.image_url && isSafeHttpUrl(article.image_url)) {
      const img = document.createElement("img");
      img.className = "card-img";
      img.src = article.image_url;
      img.alt = "";
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.onerror = () => img.replaceWith(buildImagePlaceholder());
      card.appendChild(img);
    } else {
      card.appendChild(buildImagePlaceholder());
    }

    const body = el("div", "card-body");
    const meta = el("div", "card-meta");
    meta.appendChild(el("span", null, article.source || "Unknown source"));
    meta.appendChild(el("span", null, formatDate(article.published_at)));
    body.appendChild(meta);
    body.appendChild(el("h2", "card-title", article.title));
    if (article.description) body.appendChild(el("p", "card-desc", article.description));

    const actions = el("div", "card-actions");
    const aiBtn = el("button", "btn btn-ai", "✨ Simplify with AI");
    aiBtn.type = "button";
    aiBtn.addEventListener("click", () => openSummaryModal(article));
    actions.appendChild(aiBtn);
    const link = makeOriginalLink(article);
    if (link) actions.appendChild(link);
    body.appendChild(actions);
    card.appendChild(body);
    return card;
  }

  function makeOriginalLink(article) {
    if (!article.url || !isSafeHttpUrl(article.url)) return null;
    const link = document.createElement("a");
    link.className = "card-link";
    link.href = article.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer nofollow";
    link.textContent = "Read Original Article →";
    return link;
  }

  async function loadNews() {
    renderSkeletons(6);
    clearStatus();
    const params = new URLSearchParams();
    if (currentQuery) params.set("q", currentQuery);
    if (currentTopic) params.set("topic", currentTopic);
    try {
      const response = await fetch(API_BASE + "/news?" + params.toString());
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const msg = data && typeof data.detail === "string" ? data.detail : "Could not load news right now.";
        throw new Error(msg);
      }
      renderArticles(data.articles || []);
    } catch (err) {
      clear(newsGrid);
      emptyState.hidden = true;
      showRetryableError(err.message || "Something went wrong while loading news.");
    }
  }

  function showRetryableError(message) {
    clearStatus();
    const wrapper = el("div", "empty-state");
    wrapper.appendChild(el("p", null, message));
    const retry = el("button", "btn btn-retry", "Retry");
    retry.type = "button";
    retry.addEventListener("click", loadNews);
    wrapper.appendChild(retry);
    newsGrid.appendChild(wrapper);
  }

  function openModal() {
    modalOverlay.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeModal() {
    modalOverlay.hidden = true;
    document.body.style.overflow = "";
    clear(modalContent);
  }

  async function openSummaryModal(article) {
    openModal();
    renderModalLoading(article);
    const cached = summaryCache.get(article.id);
    if (cached) {
      renderModalSummary(article, cached);
      return;
    }
    try {
      const response = await fetch(API_BASE + "/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: article.title,
          description: article.description || "",
          content: article.content || "",
          url: article.url || "",
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const msg = data && typeof data.detail === "string" ? data.detail : "Could not generate a summary.";
        throw new Error(msg);
      }
      summaryCache.set(article.id, data);
      renderModalSummary(article, data);
    } catch (err) {
      renderModalError(article, err.message || "Something went wrong while summarizing.");
    }
  }

  function renderModalLoading(article) {
    clear(modalContent);
    modalContent.appendChild(el("h2", "modal-title", article.title));
    modalContent.appendChild(el("div", "modal-loading", "Analyzing article with AI…"));
  }

  function renderModalError(article, message) {
    clear(modalContent);
    modalContent.appendChild(el("h2", "modal-title", article.title));
    const box = el("div", "modal-error");
    box.appendChild(el("p", null, message));
    const retry = el("button", "btn btn-retry", "Try Again");
    retry.type = "button";
    retry.addEventListener("click", () => openSummaryModal(article));
    box.appendChild(retry);
    modalContent.appendChild(box);
  }

  function buildModalSection(heading, text) {
    const s = el("div", "modal-section");
    s.appendChild(el("h3", null, heading));
    if (text) s.appendChild(el("p", null, text));
    return s;
  }

  function renderModalSummary(article, summary) {
    clear(modalContent);
    modalContent.appendChild(el("h2", "modal-title", article.title));

    const sentiment = ["positive", "negative", "neutral"].includes(summary.sentiment) ? summary.sentiment : "neutral";
    const topicLine = el("p", null);
    topicLine.appendChild(document.createTextNode((summary.topic || "General") + "  ·  "));
    topicLine.appendChild(el("span", "sentiment-badge sentiment-" + sentiment, sentiment));
    modalContent.appendChild(topicLine);

    modalContent.appendChild(buildModalSection("Simple Summary", summary.simple_summary));

    const tk = el("div", "modal-section");
    tk.appendChild(el("h3", null, "Key Takeaways"));
    const ul = document.createElement("ul");
    (summary.key_takeaways || []).forEach((pt) => ul.appendChild(el("li", null, pt)));
    tk.appendChild(ul);
    modalContent.appendChild(tk);

    modalContent.appendChild(buildModalSection("Why It Matters", summary.why_it_matters));

    const gl = el("div", "modal-section");
    gl.appendChild(el("h3", null, "Glossary"));
    (summary.important_terms || []).forEach((item) => {
      const p = document.createElement("p");
      p.appendChild(el("span", "glossary-term", (item.term || "") + ": "));
      p.appendChild(document.createTextNode(item.explanation || ""));
      gl.appendChild(p);
    });
    modalContent.appendChild(gl);

    const link = makeOriginalLink(article);
    if (link) modalContent.appendChild(link);

    const disclaimer = el("p", "footer-meta", summary.disclaimer || "AI-generated summary for educational purposes only.");
    disclaimer.style.marginTop = "14px";
    disclaimer.style.color = "#6b7686";
    modalContent.appendChild(disclaimer);
  }

  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    currentQuery = searchInput.value.trim();
    loadNews();
  });

  topicFilters.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    topicFilters.querySelectorAll(".chip").forEach((c) => {
      c.classList.remove("active");
      c.setAttribute("aria-selected", "false");
    });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    currentTopic = btn.dataset.topic || "";
    loadNews();
  });

  refreshBtn.addEventListener("click", () => {
    summaryCache.clear();
    loadNews();
  });

  modalClose.addEventListener("click", closeModal);
  modalOverlay.addEventListener("click", (e) => {
    if (e.target === modalOverlay) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modalOverlay.hidden) closeModal();
  });

  loadNews();
})();
