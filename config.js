// Berlin CCI Atlas: settings you can edit without touching index.html.
// To credit a contributor: add a line to `contributors` (and to CONTRIBUTORS.md), save, done.
// roles: tester | feedback | place | data | translation | design | code
window.ATLAS_CONFIG = Object.assign(window.ATLAS_CONFIG || {}, {
  projectOwner: "Kai-Ti Wu Consulting",   // controller named in the privacy notice
  contactEmail: "hello@kaitiwu.de",       // contact for data protection requests and removal from the contributors list
  imprintUrl: "https://www.kaitiwu.de/impressum",  // Impressum and general privacy information (linked, not repeated)
  host: "GitHub Pages (GitHub, Inc., USA)",         // who serves the Atlas, named in the privacy notice
  feedbackUrl: "https://www.kaitiwu.de/berlin-cci-map#feedback",

  contributors: [
    // { name: "A. K.", roles: ["feedback"], since: "2026-11" },
  ],

  // Newest first is not required; the Atlas sorts by date. `thanks` lists contributor names.
  changelog: [
    { date: "2026-11", text: "Community Events integration: upcoming events from audited neighborhood hubs are now rendered directly inside venue cards.", thanks: [] },
    { date: "2026-11", text: "Your Kiez lights up on the map while you choose it, and you can save it straight from search or by tapping the map", thanks: [] },
    { date: "2026-11", text: "Contributors list and changelog: everyone who tests the Atlas and sends feedback gets credit", thanks: [] },
    { date: "2026-10", text: "Visits only count when you're at the place (your phone checks once; the position isn't saved)", thanks: [] },
    { date: "2026-10", text: "“What's around” replaces the Kiez profile: places near you, sorted by what you can do there", thanks: [] }
  ]
});

/* ═══════════════════════════════════════════════════════════════════
   Kiez Events Atlas Extension (Phase 4 Frontend Integration)
   Dynamically consumes data/public/events.json and enhances venue cards
   without modifying the locked index.html blob.
   ═══════════════════════════════════════════════════════════════════ */
(function initKiezEventsExtension() {
  let eventsIndex = null;
  let allEvents = [];
  let isFetching = false;

  const CATEGORY_LABELS = {
    arts_culture: "Arts & Culture",
    neighbourhood_gathering: "Neighbourhood Gathering",
    sport_outdoor: "Sport & Movement",
    participatory_workshop: "Workshop",
    community_meal: "Community Meal",
    language_exchange: "Language Café",
    civic_participation: "Civic & Advice",
    other_review: "Community Event"
  };

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatEventDate(isoStr) {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("de-DE", {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit"
      });
    } catch {
      return isoStr.slice(0, 16).replace("T", " ");
    }
  }

  function injectStyles() {
    if (document.getElementById("kiez-events-style")) return;
    const style = document.createElement("style");
    style.id = "kiez-events-style";
    style.textContent = `
      .kiez-events-container {
        margin-top: 14px;
        padding-top: 14px;
        border-top: 1px solid var(--line, #e2e8f0);
        display: grid;
        gap: 12px;
      }
      .kiez-events-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
      }
      .kiez-events-header h3 {
        margin: 0;
        font-size: 15px;
        font-weight: 700;
        font-family: var(--font-display, inherit);
        color: var(--ink, #0f172a);
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .kiez-events-badge {
        font-size: 11px;
        background: rgba(2, 132, 199, 0.15);
        color: var(--accent, #0284c7);
        padding: 2px 7px;
        border-radius: 12px;
        font-weight: 600;
      }
      .kiez-site-tabs {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
      }
      .kiez-site-tab {
        background: none;
        border: 1px solid var(--line-2, #cbd5e1);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 11.5px;
        color: var(--ink-2, #334155);
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .kiez-site-tab.active {
        background: var(--ink, #0f172a);
        color: var(--panel, #ffffff);
        border-color: var(--ink, #0f172a);
      }
      .kiez-events-scroll {
        display: grid;
        gap: 8px;
        max-height: 420px;
        overflow-y: auto;
        padding-right: 4px;
      }
      .kiez-event-item {
        border: 1px solid var(--line, #e2e8f0);
        border-radius: 8px;
        padding: 10px 12px;
        background: var(--bg, #f8fafc);
        display: grid;
        gap: 5px;
        transition: border-color 0.15s ease;
      }
      .kiez-event-item:hover {
        border-color: var(--accent, #0284c7);
      }
      .kiez-event-meta-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11.5px;
        gap: 8px;
      }
      .kiez-event-time {
        font-family: var(--font-mono, monospace);
        font-weight: 600;
        color: var(--accent, #0284c7);
      }
      .kiez-price-pill {
        font-size: 10.5px;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 4px;
        text-transform: capitalize;
      }
      .kiez-price-free {
        background: rgba(34, 197, 94, 0.15);
        color: #16a34a;
      }
      .kiez-price-paid {
        background: rgba(234, 88, 12, 0.15);
        color: #ea580c;
      }
      .kiez-price-unknown {
        background: var(--line, #e2e8f0);
        color: var(--ink-3, #64748b);
      }
      .kiez-event-title-text {
        font-size: 13.5px;
        font-weight: 600;
        color: var(--ink, #0f172a);
        line-height: 1.25;
      }
      .kiez-event-foot {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 11.5px;
        color: var(--ink-3, #64748b);
        margin-top: 2px;
      }
      .kiez-event-cat-tag {
        font-size: 11px;
        background: var(--line, #e2e8f0);
        padding: 1px 6px;
        border-radius: 4px;
      }
      .kiez-event-ext-link {
        color: var(--accent, #0284c7);
        text-decoration: none;
        font-weight: 500;
      }
      .kiez-event-ext-link:hover {
        text-decoration: underline;
      }
      .kiez-imeta-events {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        background: rgba(2, 132, 199, 0.12);
        color: var(--accent, #0284c7);
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
      }
      .kiez-empty-events {
        font-size: 12px;
        color: var(--ink-3, #64748b);
        border: 1px dashed var(--line-2, #cbd5e1);
        border-radius: 8px;
        padding: 12px;
        background: var(--bg, #f8fafc);
      }
    `;
    document.head.appendChild(style);
  }

  async function loadEventsData() {
    if (eventsIndex) return eventsIndex;
    if (isFetching) return [];
    isFetching = true;
    try {
      const resp = await fetch("data/public/events.json");
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      allEvents = data.events || [];
      eventsIndex = new Map();

      for (const ev of allEvents) {
        const vid = ev.venue_id;
        if (!eventsIndex.has(vid)) {
          eventsIndex.set(vid, []);
        }
        eventsIndex.get(vid).push(ev);
      }
      isFetching = false;
      return eventsIndex;
    } catch (err) {
      console.warn("[KiezAtlas] Could not load events.json:", err);
      eventsIndex = new Map();
      isFetching = false;
      return eventsIndex;
    }
  }

  function getEventsForPlace(placeId) {
    if (!eventsIndex) return { primary: [], sibling: [], all: [] };
    const primary = eventsIndex.get(placeId) || [];

    // Divan special case: Divan operates Nehringstr. 8 and Nehringstr. 26
    let sibling = [];
    if (placeId === "interkulturelles-stadtteilzentrum-divan") {
      sibling = eventsIndex.get("ven_divan_nehring_26") || [];
    }

    return {
      primary,
      sibling,
      all: [...primary, ...sibling]
    };
  }

  function renderEventsSection(place, container) {
    if (container.querySelector("#kiez-events-section")) return;

    const { primary, sibling, all } = getEventsForPlace(place.id);
    if (!all.length) return;

    const wrap = document.createElement("div");
    wrap.id = "kiez-events-section";
    wrap.className = "kiez-events-container";

    let activeSite = "primary";
    let activeList = primary;

    function renderContent() {
      const totalCount = all.length;
      let siteTabsHtml = "";

      if (sibling.length > 0) {
        siteTabsHtml = `
          <div class="kiez-site-tabs">
            <button type="button" class="kiez-site-tab ${activeSite === "primary" ? "active" : ""}" data-site="primary">
              Nehringstr. 8 (${primary.length})
            </button>
            <button type="button" class="kiez-site-tab ${activeSite === "sibling" ? "active" : ""}" data-site="sibling">
              Nehringstr. 26 (${sibling.length})
            </button>
            <button type="button" class="kiez-site-tab ${activeSite === "all" ? "active" : ""}" data-site="all">
              All sites (${totalCount})
            </button>
          </div>
        `;
      }

      const listHtml = activeList.map(ev => {
        let priceClass = "kiez-price-unknown";
        let priceText = "Price unknown";
        if (ev.price_status === "free") {
          priceClass = "kiez-price-free";
          priceText = "Free";
        } else if (ev.price_status === "donation") {
          priceClass = "kiez-price-free";
          priceText = "Donation";
        } else if (ev.price_status === "fixed" && ev.price_amount != null) {
          priceClass = "kiez-price-paid";
          priceText = "€" + ev.price_amount.toFixed(2);
        }

        const catLabel = CATEGORY_LABELS[ev.category] || ev.category;
        const linkUrl = ev.original_event_url || ev.source_url;

        return `
          <div class="kiez-event-item">
            <div class="kiez-event-meta-row">
              <span class="kiez-event-time">📅 ${formatEventDate(ev.start_datetime)}</span>
              <span class="kiez-price-pill ${priceClass}">${priceText}</span>
            </div>
            <div class="kiez-event-title-text">${escapeHtml(ev.title)}</div>
            <div class="kiez-event-foot">
              <span class="kiez-event-cat-tag">${escapeHtml(catLabel)}</span>
              ${linkUrl ? `<a class="kiez-event-ext-link" href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener">Event info ↗</a>` : ""}
            </div>
          </div>
        `;
      }).join("");

      wrap.innerHTML = `
        <div class="kiez-events-header">
          <h3>📅 Upcoming Events <span class="kiez-events-badge">${activeList.length}</span></h3>
          ${siteTabsHtml}
        </div>
        <div class="kiez-events-scroll">
          ${listHtml}
        </div>
      `;

      wrap.querySelectorAll(".kiez-site-tab").forEach(btn => {
        btn.onclick = () => {
          activeSite = btn.dataset.site;
          if (activeSite === "primary") activeList = primary;
          else if (activeSite === "sibling") activeList = sibling;
          else activeList = all;
          renderContent();
        };
      });
    }

    renderContent();

    // Insert before .caveat
    const caveat = container.querySelector(".caveat");
    if (caveat) {
      container.insertBefore(wrap, caveat);
    } else {
      container.appendChild(wrap);
    }
  }

  function enhancePlaceList(listEl) {
    if (!eventsIndex || !eventsIndex.size) return;
    const items = listEl.querySelectorAll(".item[data-i]");
    items.forEach(li => {
      if (li.querySelector(".kiez-imeta-events")) return;
      const idx = +li.dataset.i;
      if (isNaN(idx) || !window.PLACES || !window.PLACES[idx]) return;
      const p = window.PLACES[idx];
      const { all } = getEventsForPlace(p.id);
      if (all && all.length > 0) {
        const meta = li.querySelector(".imeta");
        if (meta) {
          const badge = document.createElement("span");
          badge.className = "kiez-imeta-events";
          badge.innerHTML = `📅 ${all.length} event${all.length === 1 ? "" : "s"}`;
          meta.appendChild(badge);
        }
      }
    });
  }

  function handlePanelMutation() {
    const panel = document.getElementById("panelBody");
    if (!panel) return;

    // 1. Check if viewing detail card
    const detail = panel.querySelector(".detail");
    if (detail && window.state && window.state.sel !== null && window.PLACES) {
      const p = window.PLACES[window.state.sel];
      if (p) {
        loadEventsData().then(() => {
          renderEventsSection(p, detail);
        });
      }
    }

    // 2. Check if viewing place list
    const list = panel.querySelector(".list");
    if (list) {
      loadEventsData().then(() => {
        enhancePlaceList(list);
      });
    }
  }

  function start() {
    injectStyles();
    loadEventsData().then(() => {
      const panel = document.getElementById("panelBody");
      if (panel) {
        const observer = new MutationObserver(handlePanelMutation);
        observer.observe(panel, { childList: true, subtree: true });
        handlePanelMutation();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
