/**
 * FinSimplify AI — frontend logic.
 * Uses only the Fetch API and safe DOM methods (textContent, not innerHTML)
 * for anything derived from external news/AI content.
 */
(function () {
  "use strict";

  const API_BASE = "/api";

  // --- State -----------------------------------------------------------
  let currentQuery = "";
  let currentTopic = "";
  /** In-memory cache of summaries for this browser session, keyed by article id. */
  const summaryCache = new Map();
  /** Cache of fetched articles by id, so the modal can reuse title/desc/url. */
  const articleById = new Map();

  // --- DOM references ----------------------------------------------------
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

  // --- Helpers -------------------------------------------------------------
  function showStatus(message, type) {
    statusBanner.textContent = message;
    statusBanner.className = `status-banner ${type}`;
    statusBanner.hidden = false;
  }

  function clearStatus() {
    statusBanner.hidden = true;
    statusBanner.textContent = "";
  }

  function isSafeHttpUrl(value) {
    try {
      const parsed = new URL(value, window.location.href);
      return parsed.protocol === "https:" || parsed.protocol === "http:";
    } catch (err) {
      return false;
    }
  }

  function formatDate(isoString) {
    if (!isoString) return "Date unknown";
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return "Date unknown";
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // --- Rendering: skeletons / empty / grid --------------------------------
  function renderSkeletons(count) {
    newsGrid.innerHTML = "";
    emptyState.hidden = true;
    for (let i = 0; i < count; i++) {
      const clone = skeletonTemplate.content.cloneNode(true);
      newsGrid.appendChild(clone);
    }
  }

  function renderArticles(articles) {
    newsGrid.innerHTML = "";
    articleById.clear();

    if (!articles || articles.length === 0) {
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;

    articles.forEach((article) => {
      articleById.set(article.id, article);
      newsGrid.appendChild(buildCard(article));
    });
  }

  function buildCard(article) {
    const card = el("article", "card");
    card.dataset.articleId = article.id;

    if (article.image_url && isSafeHttpUrl(article.image_url)) {
      const img = document.createElement("img");
      img.className = "card-img";
      img.src = article.image_url;
      img.alt = "";
      img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      img.onerror = () => {
        img.replaceWith(buildImagePlaceholder());
      };
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

    if (article.description) {
      body.appendChild(el("p", "card-desc", article.description));
    }

    const actions = el("div", "card-actions");

    const aiBtn = el("button", "btn btn-ai", "✨ Simplify with AI");
    aiBtn.type = "button";
    aiBtn.addEventListener("click", () => openSummaryModal(article));
    actions.appendChild(aiBtn);

    if (article.url && isSafeHttpUrl(article.url)) {
      const link = document.createElement("a");
      link.className = "card-link";
      link.href = article.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer nofollow";
      link.textContent = "Read Original Article →";
      actions.appendChild(link);
    }

    body.appendChild(actions);
    card.appendChild(body);
    return card;
  }

  function buildImagePlaceholder() {
    const div = el("div", "card-img-placeholder", "📰");
    return div;
  }

  // --- News fetching ---------------------------------------------------
  async function loadNews() {
    renderSkeletons(6);
    clearStatus();

    const params = new URLSearchParams();
    if (currentQuery) params.set("q", currentQuery);
    if (currentTopic) params.set("topic", currentTopic);

    try {
      const response = await fetch(`${API_BASE}/news?${params.toString()}`);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const message = data && data.detail ? data.detail : "Could not load news right now.";
        throw new Error(message);
      }

      renderArticles(data.articles || []);

      if (!data.articles || data.articles.length === 0) {
        showStatus("No articles matched your search. Try different keywords.", "info");
      }
    } catch (err) {
      newsGrid.innerHTML = "";
      emptyState.hidden = true;
      showRetryableError(err.message || "Something went wrong while loading news.");
    }
  }

  function showRetryableError(message) {
    showStatus(message, "error");
    const wrapper = el("div", "empty-state");
    wrapper.appendChild(el("p", null, message));
    const retryBtn = el("button", "btn btn-retry", "Retry");
    retryBtn.type = "button";
    retryBtn.addEventListener("click", loadNews);
    wrapper.appendChild(retryBtn);
    newsGrid.appendChild(wrapper);
  }

  // --- Summarization modal -----------------------------------------------
  function openModal() {
    modalOverlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modalOverlay.hidden = true;
    document.body.style.overflow = "";
    modalContent.innerHTML = "";
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
      const response = await fetch(`${API_BASE}/summarize`, {
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
        const message = data && data.detail ? data.detail : "Could not generate a summary.";
        throw new Error(typeof message === "string" ? message : "Could not generate a summary.");
      }

      summaryCache.set(article.id, data);
      renderModalSummary(article, data);
    } catch (err) {
      renderModalError(article, err.message || "Something went wrong while summarizing.");
    }
  }

  function renderModalLoading(article) {
    modalContent.innerHTML = "";
    modalContent.appendChild(el("h2", "modal-title", article.title));
    const loading = el("div", "modal-loading", "Analyzing article with AI…");
    modalContent.appendChild(loading);
  }

  function renderModalError(article, message) {
    modalContent.innerHTML = "";
    modalContent.appendChild(el("h2", "modal-title", article.title));
    const errBox = el("div", "modal-error");
    errBox.appendChild(el("p", null, message));
    const retryBtn = el("button", "btn btn-retry", "Try Again");
    retryBtn.type = "button";
    retryBtn.addEventListener("click", () => openSummaryModal(article));
    errBox.appendChild(retryBtn);
    modalContent.appendChild(errBox);
  }

  function renderModalSummary(article, summary) {
    modalContent.innerHTML = "";
    modalContent.appendChild(el("h2", "modal-title", article.title));

    const badge = el(
      "span",
      `sentiment-badge sentiment-${summary.sentiment || "neutral"}`,
      summary.sentiment || "neutral"
    );
    const topicLine = el("p", null);
    topicLine.appendChild(document.createTextNode((summary.topic || "General") + "  ·  "));
    topicLine.appendChild(badge);
    modalContent.appendChild(topicLine);

    modalContent.appendChild(buildModalSection("Simple Summary", [summary.simple_summary]));

    const takeawaysSection = el("div", "modal-section");
    takeawaysSection.appendChild(el("h3", null, "Key Takeaways"));
    const ul = document.createElement("ul");
    (summary.key_takeaways || []).forEach((point) => {
      const li = el("li", null, point);
      ul.appendChild(li);
    });
    takeawaysSection.appendChild(ul);
    modalContent.appendChild(takeawaysSection);

    modalContent.appendChild(buildModalSection("Why It Matters", [summary.why_it_matters]));

    const glossarySection = el("div", "modal-section");
    glossarySection.appendChild(el("h3", null, "Glossary"));
    (summary.important_terms || []).forEach((item) => {
      const p = document.createElement("p");
      const strong = el("span", "glossary-term", (item.term || "") + ": ");
      p.appendChild(strong);
      p.appendChild(document.createTextNode(item.explanation || ""));
      glossarySection.appendChild(p);
    });
    modalContent.appendChild(glossarySection);

    if (article.url && isSafeHttpUrl(article.url)) {
      const link = document.createElement("a");
      link.className = "card-link";
      link.href = article.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer nofollow";
      link.textContent = "Read Original Article →";
      modalContent.appendChild(link);
    }

    const disclaimer = el(
      "p",
      "footer-meta",
      summary.disclaimer || "AI-generated summary for educational purposes only."
    );
    disclaimer.style.marginTop = "14px";
    disclaimer.style.color = "#6b7686";
    modalContent.appendChild(disclaimer);
  }

  function buildModalSection(heading, paragraphs) {
    const section = el("div", "modal-section");
    section.appendChild(el("h3", null, heading));
    paragraphs.filter(Boolean).forEach((text) => {
      section.appendChild(el("p", null, text));
    });
    return section;
  }

  // --- Event wiring --------------------------------------------------------
  searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    currentQuery = searchInput.value.trim();
    loadNews();
  });

  topicFilters.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    [...topicFilters.querySelectorAll(".chip")].forEach((chip) => {
      chip.classList.remove("active");
      chip.setAttribute("aria-selected", "false");
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

  // --- Init ------------------------------------------------------------
  loadNews();
})();
