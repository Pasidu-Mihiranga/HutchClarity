/* Kodee-style Clarity chat module. Depends on shell: T, esc, api, lang, appState, go, setLang, I18N */
(function (global) {
  "use strict";

  const HISTORY_KEY = "clarity_chat_threads_v1";

  const TOPIC_CATEGORIES = [
    { id: "money", i18n: "catMoney", keys: ["qBalance", "qSub", "qTwice", "qRefund"] },
    { id: "packs", i18n: "catPacks", keys: ["qSlow", "qFup", "qPackIssue", "qPackMissing", "qRecommend", "qActivate", "qExpiry"] },
    { id: "reloads", i18n: "catReloads", keys: ["qMissing", "qTwice"] },
    { id: "subs", i18n: "catSubs", keys: ["qSub", "qVasList", "qPrevent"] },
    { id: "network", i18n: "catNetwork", keys: ["qNetwork", "qSlow"] },
    { id: "esim", i18n: "catEsim", keys: ["qEsim"] },
    { id: "protect", i18n: "catProtect", keys: ["qPrevent"] },
    { id: "support", i18n: "catSupport", keys: ["qCase"] },
  ];

  const PROGRESS_STEPS = [
    { id: "understand", key: "progUnderstand" },
    { id: "charges", key: "progCharges" },
    { id: "subs", key: "progSubs" },
    { id: "consent", key: "progConsent" },
  ];

  let hooks = {};
  let ui = {
    showTopics: false,
    topicCategory: null,
    showHistory: false,
    showEvidence: false,
    pendingConfirm: null,
    progressStep: -1,
    thinkingLabel: "",
  };

  function H() {
    return hooks;
  }
  function S() {
    return hooks.getState();
  }
  function t(key) {
    return hooks.T(key);
  }
  function esc(s) {
    return hooks.esc(String(s == null ? "" : s));
  }

  function defaultSuggestions() {
    const keys = ["qBalance", "qSlow", "qSub", "qRecommend", "qPackIssue", "qEsim"];
    return keys.map((key) => ({
      id: key,
      i18n_key: key,
      intent: (hooks.SUGGESTED.find((s) => s.key === key) || {}).chatIntent || "",
      reason: "default",
      personalized: false,
    }));
  }

  async function loadSuggestions() {
    const state = S();
    const app = hooks.getApp();
    try {
      const payload = await hooks.api("/v1/conversation/suggestions", "POST", {
        language: hooks.getLang(),
        limit: 6,
        snapshot: {
          pack: (app && app.pack) || {},
          subscriptions: (app && app.subscriptions) || [],
          activity: (app && app.activity) || [],
          open_case: ((app && app.cases) || []).some((c) => c.status === "open"),
        },
      });
      state.suggestions = (payload.suggestions || []).map((chip) => ({
        ...chip,
        personalized: ["fup_high", "unusual_vas", "pack_expiring", "double_charge", "reload_missing", "open_case"].includes(
          chip.reason
        ),
      }));
      state.moreTopics = payload.more_topics || [];
    } catch (_e) {
      state.suggestions = defaultSuggestions();
      state.moreTopics = [];
    }
  }

  function headerHtml() {
    const lang = hooks.getLang();
    return `<header class="cc-header">
      <button type="button" class="cc-back" data-cc="back" aria-label="Back">←</button>
      <div class="cc-brand">
        <div class="cc-avatar" aria-hidden="true">C</div>
        <div class="cc-brand-text">
          <div class="cc-title">${esc(t("clarityBrand"))}</div>
          <div class="cc-sub">${esc(t("claritySubtitle"))}</div>
        </div>
      </div>
      <div class="cc-header-actions">
        <div class="cc-lang" role="group" aria-label="Language">
          <button type="button" data-cc="lang" data-lang="en" class="${lang === "en" ? "on" : ""}">EN</button>
          <button type="button" data-cc="lang" data-lang="si" class="${lang === "si" ? "on" : ""}">සිං</button>
          <button type="button" data-cc="lang" data-lang="ta" class="${lang === "ta" ? "on" : ""}">த</button>
        </div>
        <button type="button" class="cc-icon-btn" data-cc="history" title="${esc(t("chatHistory"))}">☰</button>
        <button type="button" class="cc-icon-btn" data-cc="new" title="${esc(t("newChat"))}">＋</button>
      </div>
    </header>`;
  }

  function welcomeHtml() {
    const app = hooks.getApp();
    const name = (app && app.name) || "there";
    const hi = t("chatHi").replace("{name}", name);
    const chips = S().suggestions.length ? S().suggestions : defaultSuggestions();
    const cards = chips
      .map((chip) => {
        const label = chip.label || t(chip.i18n_key) || chip.id;
        const qKey = chip.i18n_key || chip.id;
        return `<button type="button" class="cc-suggest-card ${chip.personalized ? "personalized" : ""}" data-cc="ask" data-q="${esc(qKey)}" data-label="${esc(label)}" data-intent="${esc(chip.intent || "")}">${esc(label)}</button>`;
      })
      .join("");

    let topics = "";
    if (ui.showTopics) {
      topics = topicBrowserHtml();
    }

    return `<div class="cc-welcome">
      <div class="cc-welcome-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M12 3a7 7 0 0 0-7 7c0 2.5 1.2 4.2 2.4 5.4.6.6 1.1 1.3 1.3 2.1h6.6c.2-.8.7-1.5 1.3-2.1C17.8 14.2 19 12.5 19 10a7 7 0 0 0-7-7z"/><path d="M9 21h6"/></svg>
      </div>
      <p class="cc-hi">${esc(hi)}</p>
      <p class="cc-ask">${esc(t("howHelpToday"))}</p>
      <p class="cc-support">${esc(t("chatSubtitle"))}</p>
      <div class="cc-suggest-grid">${cards}</div>
      <button type="button" class="cc-more-btn" data-cc="toggle-topics">${esc(ui.showTopics ? t("seeFewerTopics") : t("seeMoreTopics"))}</button>
      ${topics}
    </div>`;
  }

  function topicBrowserHtml() {
    const cats = TOPIC_CATEGORIES.map((cat) => {
      const on = ui.topicCategory === cat.id ? "on" : "";
      return `<button type="button" class="cc-cat-btn ${on}" data-cc="topic-cat" data-cat="${esc(cat.id)}">${esc(t(cat.i18n))}</button>`;
    }).join("");
    let qs = "";
    if (ui.topicCategory) {
      const cat = TOPIC_CATEGORIES.find((c) => c.id === ui.topicCategory);
      if (cat) {
        qs = cat.keys
          .map((key) => {
            const sug = hooks.SUGGESTED.find((s) => s.key === key);
            return `<button type="button" class="cc-suggest-card" data-cc="ask" data-q="${esc(key)}" data-label="${esc(t(key))}" data-intent="${esc((sug && sug.chatIntent) || "")}">${esc(t(key))}</button>`;
          })
          .join("");
      }
    }
    return `<div class="cc-topics">
      <h3>${esc(t("browseTopics"))}</h3>
      <div class="cc-cat">${cats}</div>
      <div class="cc-topic-qs">${qs}</div>
    </div>`;
  }

  function progressHtml() {
    if (ui.progressStep < 0) return "";
    const items = PROGRESS_STEPS.map((step, i) => {
      let cls = "";
      let mark = "○";
      if (i < ui.progressStep) {
        cls = "done";
        mark = "✓";
      } else if (i === ui.progressStep) {
        cls = "active";
        mark = "…";
      }
      return `<li class="${cls}"><span>${mark}</span> ${esc(t(step.key))}</li>`;
    }).join("");
    return `<div class="cc-progress"><ul>${items}</ul></div>`;
  }

  function thinkingHtml() {
    const label = ui.thinkingLabel || t("checking");
    return `<div class="cc-thinking"><span class="cc-dots" aria-hidden="true"><span></span><span></span><span></span></span>${esc(label)}</div>`;
  }

  function evidenceList(decision, timeline) {
    const sources = (timeline && timeline.sources) || [];
    const items = [];
    for (const src of sources.slice(0, 6)) {
      const name = src.source || src.name || "source";
      const status = String(src.completeness || src.status || "").toLowerCase();
      if (status === "missing" || status === "partial") {
        items.push({ warn: true, text: `${name}: ${t("evidenceMissing")}` });
      } else {
        items.push({ warn: false, text: `${name}: ${t("evidenceOk")}` });
      }
    }
    const rule = decision && (decision.matched_rule || decision.rule_id || "");
    if (/VAS|CONSENT|NO_CONSENT/i.test(String(rule))) {
      items.push({ warn: true, text: t("evidenceWarn") });
    }
    if (!items.length) items.push({ warn: false, text: t("evidenceOk") });
    return `<ul class="cc-evidence">${items
      .map((it) => `<li><span class="${it.warn ? "warn" : "ok"}">${it.warn ? "⚠" : "✓"}</span> ${esc(it.text)}</li>`)
      .join("")}</ul>`;
  }

  function followHtml(followUps) {
    if (!followUps || !followUps.length) return "";
    return `<div class="cc-follow">${followUps
      .map((fu) => {
        const label = t(fu.i18n_key) || fu.id;
        return `<button type="button" data-cc="follow" data-intent="${esc(fu.intent || "")}" data-key="${esc(fu.i18n_key || "")}">${esc(label)}</button>`;
      })
      .join("")}</div>`;
  }

  function investigationCard(state) {
    const d = state.decision || {};
    const timeline = state.timeline || {};
    const outcome = d.outcome || "EXPLAIN_ONLY";
    const finding = d.explanation || t("unknown");
    const amount = d.amount_lkr ? `LKR ${d.amount_lkr}` : "";
    const product = d.product || d.merchant || state.contextProduct || "";
    const when = d.occurred_at ? hooks.fmtDate(d.occurred_at) : "";
    const conf =
      d.confidence != null
        ? t("confidenceLabel").replace(
            "{n}",
            String(Math.round(Number(d.confidence) * (Number(d.confidence) <= 1 ? 100 : 1)))
          )
        : "";
    const primary =
      outcome === "HANDOFF" || state.mode === "human"
        ? ""
        : outcome === "EXPLAIN_ONLY"
          ? `<button type="button" class="cc-btn cc-btn-primary" data-cc="receipt-explain">${esc(t("getReceipt"))}</button>`
          : outcome === "STAFF_APPROVAL"
            ? `<button type="button" class="cc-btn cc-btn-primary" data-cc="staff-approve">${esc(t("confirm"))}</button>`
            : `<button type="button" class="cc-btn cc-btn-primary" data-cc="confirm-fix">${esc(outcome === "AUTO_FIX" ? t("apply") : t("refundDisable"))}</button>`;
    const evidenceBlock = ui.showEvidence
      ? `<div class="cc-evidence-panel">${evidenceList(d, timeline)}
          <ul class="cc-steps">${((timeline.events || []).slice(0, 8).map((ev) => `<li>${esc(hooks.describe(ev))} · ${esc(hooks.fmtDate(ev.occurred_at))}</li>`).join(""))}</ul>
        </div>`
      : "";

    return `<div class="cc-card">
      <span class="cc-verdict ${outcome === "HANDOFF" ? "warn" : "ok"}">${esc(String(outcome).replace(/_/g, " "))}</span>
      <h3>${esc(t("foundReason"))}</h3>
      ${amount ? `<div class="cc-amount">${esc(amount)}</div>` : ""}
      ${product || when ? `<p class="cc-meta">${esc([product, when].filter(Boolean).join(" · "))}</p>` : ""}
      <p class="cc-explain">${esc(state.mode === "human" ? t("humanFinding") : finding)}</p>
      ${conf ? `<p class="cc-meta">${esc(conf)}</p>` : ""}
      <h3 style="font-size:14px;margin-top:8px">${esc(t("whatIChecked"))}</h3>
      ${evidenceList(d, timeline)}
      <button type="button" class="cc-btn-ghost" data-cc="toggle-evidence">${esc(t("viewEvidence"))}</button>
      ${evidenceBlock}
      <div class="cc-actions">
        ${primary}
        <button type="button" class="cc-btn" data-cc="handoff">${esc(t("talkSupport"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function knowledgeCard(state) {
    const top = (state.articles || [])[0];
    const steps = top && top.body
      ? String(top.body)
          .split(/(?<=\.)\s+/)
          .filter(Boolean)
          .slice(0, 5)
      : [];
    return `<div class="cc-card">
      <span class="cc-verdict">HOW TO</span>
      <h3>${esc(top ? top.title : t("unknown"))}</h3>
      ${steps.length ? `<ol class="cc-steps">${steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : `<p class="cc-explain">${esc(top ? top.body : t("intentHint"))}</p>`}
      <div class="cc-actions">
        <button type="button" class="cc-btn" data-cc="handoff">${esc(t("needMoreHelp"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function missCard(state) {
    const finding = t(hooks.INTENT_EMPTY[state.intent] || "intentNone");
    return `<div class="cc-card">
      <span class="cc-verdict warn">${esc(t("couldNotConfirm"))}</span>
      <h3>${esc(finding)}</h3>
      <p class="cc-explain">${esc(t("intentHint"))}</p>
      <div class="cc-actions">
        <button type="button" class="cc-btn cc-btn-primary" data-cc="ask" data-q="qBalance">${esc(t("tryAgain"))}</button>
        <button type="button" class="cc-btn" data-cc="handoff">${esc(t("talkSupport"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function usageCard(state) {
    const pack = (hooks.getApp() && hooks.getApp().pack) || {};
    const used = Number(pack.used_pct || 0);
    const left = pack.data_remaining || pack.remaining || "-";
    const total = pack.data_total || pack.quota || "";
    return `<div class="cc-card">
      <h3>${esc(t("dataRemaining"))}</h3>
      <p class="cc-amount">${esc(left)}${total ? ` / ${esc(total)}` : ""}</p>
      <div class="cc-usage-bar"><span style="width:${Math.min(100, used)}%"></span></div>
      <p class="cc-meta">${esc(t("fup"))}: ${used >= 80 ? esc(t("fupActive")) : esc(t("fupOk"))}</p>
      <div class="cc-actions">
        <button type="button" class="cc-btn" data-cc="go-usage">${esc(t("viewUsageDetails"))}</button>
        <button type="button" class="cc-btn cc-btn-primary" data-cc="ask" data-q="qRecommend" data-intent="PACK_RECOMMEND">${esc(t("fuBuy"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function packageCards(state) {
    const catalogue = ((hooks.getApp() && hooks.getApp().catalogue) || []).slice(0, 3);
    if (!catalogue.length) return knowledgeCard(state);
    const rows = catalogue
      .map((p) => {
        const name = hooks.packLabel(p.name || p.offering_id);
        return `<div class="cc-pack">
          <strong>${esc(name)}</strong>
          <span class="cc-meta">LKR ${esc(p.price_lkr || p.price || "-")} · ${esc(p.data || "-")} · ${esc(p.validity || "-")}</span>
          <div class="cc-actions">
            <button type="button" class="cc-btn" data-cc="pack-details" data-id="${esc(p.offering_id)}">${esc(t("fuDetails"))}</button>
            <button type="button" class="cc-btn cc-btn-primary" data-cc="pack-buy" data-id="${esc(p.offering_id)}">${esc(t("fuActivate"))}</button>
          </div>
        </div>`;
      })
      .join("");
    return `<div class="cc-card"><h3>${esc(t("qRecommend"))}</h3><div class="cc-pack-row">${rows}</div>${followHtml(state.followUps)}</div>`;
  }

  function networkCard(state) {
    return `<div class="cc-card">
      <h3>${esc(t("qNetwork"))}</h3>
      <ul class="cc-evidence">
        <li><span class="ok">✓</span> ${esc(t("accountOk"))}</li>
        <li><span class="ok">✓</span> ${esc(t("packOk"))}</li>
        <li><span class="warn">⚠</span> ${esc(t("checkLocalSignal"))}</li>
      </ul>
      <p class="cc-explain">${esc(t("networkLikely"))}</p>
      <div class="cc-actions">
        <button type="button" class="cc-btn" data-cc="go-network">${esc(t("checkNetwork"))}</button>
        <button type="button" class="cc-btn" data-cc="handoff">${esc(t("reportIssue"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function handoffCard(state) {
    const id = state.caseId || "-";
    return `<div class="cc-card">
      <span class="cc-verdict warn">HANDOFF</span>
      <h3>${esc(t("sentToSpecialist"))}</h3>
      <p class="cc-meta">${esc(t("caseNo").replace("{id}", id))}</p>
      <p class="cc-explain">${esc(t("humanFinding"))}</p>
      <div class="cc-actions">
        <button type="button" class="cc-btn cc-btn-primary" data-cc="go-cases">${esc(t("viewCase"))}</button>
      </div>
    </div>`;
  }

  function successCard(state) {
    const bal = hooks.getApp() && hooks.getApp().balance_lkr;
    const amount = (state.decision && state.decision.amount_lkr) || state.contextAmount || "";
    return `<div class="cc-card success">
      <h3>✓ ${esc(t("resolvedTitle"))}</h3>
      <ul class="cc-steps">
        ${amount ? `<li>${esc(t("refundedAmount").replace("{amount}", amount))}</li>` : ""}
        <li>${esc(t("subscriptionDisabled"))}</li>
        ${bal != null ? `<li>${esc(t("newBalance").replace("{amount}", bal))}</li>` : ""}
      </ul>
      <div class="cc-actions">
        ${state.receiptDoc ? `<button type="button" class="cc-btn cc-btn-primary" data-cc="open-receipt" data-id="${esc((state.receiptDoc.receipt_id || state.receiptDoc.id || ""))}">${esc(t("viewReceipt"))}</button>` : ""}
        <button type="button" class="cc-btn" data-cc="ask" data-q="qPrevent" data-intent="PREVENT_CHARGES">${esc(t("fuPrevent"))}</button>
      </div>
      ${followHtml(state.followUps)}
    </div>`;
  }

  function receiptCard(state) {
    const full = state.receiptDoc || {};
    const payload = full.payload || {};
    const id = full.receipt_id || full.id || "-";
    const verified = state.receiptCheck && (state.receiptCheck.valid || state.receiptCheck.ok);
    return `<div class="cc-card receipt">
      <span class="cc-verdict ok">${esc(verified ? t("verified") : t("notVerified"))}</span>
      <h3>${esc(t("trustReceipt"))}</h3>
      <p class="cc-meta">${esc(id)}</p>
      <p class="cc-explain">${esc((payload.what_happened && payload.what_happened.summary) || t("done"))}</p>
      <div class="cc-actions">
        <button type="button" class="cc-btn cc-btn-primary" data-cc="open-receipt" data-id="${esc(id)}">${esc(t("viewReceipt"))}</button>
      </div>
    </div>`;
  }

  function cardForMessage(msg, state) {
    if (msg.kind === "thinking") return thinkingHtml();
    if (msg.kind === "progress") return progressHtml();
    if (msg.kind === "html") return msg.html;
    if (msg.kind === "investigation") return investigationCard(state);
    if (msg.kind === "knowledge") return knowledgeCard(state);
    if (msg.kind === "miss") return missCard(state);
    if (msg.kind === "usage") return usageCard(state);
    if (msg.kind === "packages") return packageCards(state);
    if (msg.kind === "network") return networkCard(state);
    if (msg.kind === "handoff") return handoffCard(state);
    if (msg.kind === "success") return successCard(state);
    if (msg.kind === "receipt") return receiptCard(state);
    return msg.html || "";
  }

  function transcriptHtml() {
    const state = S();
    if (!state.messages.length) return "";
    return `<div class="cc-transcript">${state.messages
      .map((msg) => {
        if (msg.role === "user") {
          return `<div class="cc-bubble-user">${esc(msg.text)}</div>`;
        }
        return `<div class="cc-bubble-ai">${cardForMessage(msg, state)}</div>`;
      })
      .join("")}</div>`;
  }

  function historyPanelHtml() {
    if (!ui.showHistory) return "";
    const threads = loadHistory();
    const items = threads.length
      ? threads
          .map(
            (th) => `<button type="button" class="cc-history-item" data-cc="open-thread" data-id="${esc(th.id)}">
        <div>${esc(th.title)}</div>
        <div class="status">${esc(th.status)}</div>
      </button>`
          )
          .join("")
      : `<p class="cc-meta">${esc(t("empty"))}</p>`;
    return `<div class="cc-history" data-cc="close-history"><div class="cc-history-panel" data-cc="stop">
      <h2>${esc(t("chatHistory"))}</h2>
      ${items}
    </div></div>`;
  }

  function modalHtml() {
    const pending = ui.pendingConfirm;
    if (!pending) return "";
    return `<div class="cc-modal-backdrop" data-cc="cancel-confirm">
      <div class="cc-modal" data-cc="stop">
        <h3>${esc(pending.title)}</h3>
        <ul>${pending.bullets.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>
        <div class="cc-actions">
          <button type="button" class="cc-btn" data-cc="cancel-confirm">${esc(t("cancel"))}</button>
          <button type="button" class="cc-btn cc-btn-primary" data-cc="do-confirm">${esc(t("confirm"))}</button>
        </div>
      </div>
    </div>`;
  }

  function rootHtml() {
    const state = S();
    const empty = !state.messages.length;
    return `${headerHtml()}
      <div class="cc-root">
        <div class="cc-body">
          ${empty ? welcomeHtml() : transcriptHtml()}
        </div>
      </div>
      ${historyPanelHtml()}
      ${modalHtml()}`;
  }

  function mount() {
    document.body.classList.add("clarity-immersive");
    const screen = document.getElementById("screen");
    if (!screen) return;
    screen.innerHTML = `<div class="clarity-chat-kodee">${rootHtml()}</div>`;
    const input = document.getElementById("composerInput");
    if (input) {
      if (input.tagName === "INPUT") {
        /* shell may still be input; placeholder only */
      }
      input.placeholder = t("askClarityAnything");
    }
    if (!S().suggestions.length) {
      loadSuggestions().then(() => {
        if (!S().messages.length) remountBody();
      });
    }
  }

  function remountBody() {
    const host = document.querySelector(".clarity-chat-kodee");
    if (host) host.innerHTML = rootHtml();
    else mount();
  }

  function unmount() {
    document.body.classList.remove("clarity-immersive");
    ui.showTopics = false;
    ui.showHistory = false;
    ui.pendingConfirm = null;
    ui.progressStep = -1;
  }

  function pushUser(text) {
    S().messages.push({ role: "user", text });
  }

  function pushAi(kind, extra) {
    S().messages.push(Object.assign({ role: "clarity", kind }, extra || {}));
  }

  function replaceLastAi(kind, extra) {
    const msgs = S().messages;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === "clarity") {
        msgs[i] = Object.assign({ role: "clarity", kind }, extra || {});
        return;
      }
    }
    pushAi(kind, extra);
  }

  function setThinking(label) {
    ui.thinkingLabel = label;
    const last = S().messages[S().messages.length - 1];
    if (last && last.role === "clarity" && last.kind === "thinking") {
      remountBody();
      return;
    }
    pushAi("thinking");
    remountBody();
  }

  function setProgress(stepIndex) {
    ui.progressStep = stepIndex;
    const last = S().messages[S().messages.length - 1];
    if (last && last.role === "clarity" && (last.kind === "thinking" || last.kind === "progress")) {
      last.kind = "progress";
    } else {
      pushAi("progress");
    }
    remountBody();
  }

  function finishWithCard(kind) {
    ui.progressStep = -1;
    const msgs = S().messages;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === "clarity" && (msgs[i].kind === "thinking" || msgs[i].kind === "progress")) {
        msgs[i] = { role: "clarity", kind };
        remountBody();
        persistCurrentThread();
        return;
      }
    }
    pushAi(kind);
    remountBody();
    persistCurrentThread();
  }

  function newChat() {
    const state = S();
    persistCurrentThread();
    state.messages = [];
    state.mode = null;
    state.decision = null;
    state.timeline = null;
    state.caseId = null;
    state.planId = null;
    state.receipt = null;
    state.receiptDoc = null;
    state.followUps = [];
    state.question = "";
    state.chatIntent = null;
    state.contextProduct = null;
    state.contextAmount = null;
    ui.showTopics = false;
    ui.progressStep = -1;
    remountBody();
    loadSuggestions().then(remountBody);
  }

  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    } catch (_e) {
      return [];
    }
  }

  function saveHistory(threads) {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(threads.slice(0, 20)));
  }

  function persistCurrentThread() {
    const state = S();
    if (!state.messages.length) return;
    const title =
      state.question ||
      (state.messages.find((m) => m.role === "user") || {}).text ||
      t("clarityBrand");
    let status = "In progress";
    if (state.mode === "resolved") status = "Resolved";
    else if (state.mode === "result" || state.mode === "knowledge" || state.mode === "miss") status = "Explained";
    else if (state.mode === "human") status = "In progress";
    const threads = loadHistory().filter((th) => th.id !== state.threadId);
    const id = state.threadId || `th_${Date.now()}`;
    state.threadId = id;
    threads.unshift({
      id,
      title: String(title).slice(0, 80),
      status,
      messages: state.messages,
      snapshot: {
        mode: state.mode,
        decision: state.decision,
        timeline: state.timeline,
        caseId: state.caseId,
        followUps: state.followUps,
        articles: state.articles,
        receiptDoc: state.receiptDoc,
        receiptCheck: state.receiptCheck,
        question: state.question,
        chatIntent: state.chatIntent,
        contextProduct: state.contextProduct,
        contextAmount: state.contextAmount,
      },
      at: Date.now(),
    });
    saveHistory(threads);
  }

  function openThread(id) {
    const th = loadHistory().find((x) => x.id === id);
    if (!th) return;
    const state = S();
    Object.assign(state, th.snapshot || {});
    state.messages = th.messages || [];
    state.threadId = th.id;
    ui.showHistory = false;
    remountBody();
  }

  function openConfirmModal() {
    const d = S().decision || {};
    const product = d.product || S().contextProduct || t("thisSubscription");
    ui.pendingConfirm = {
      title: t("confirmDisableTitle").replace("{product}", product),
      bullets: [t("confirmBulletStop"), t("confirmBulletNoCharge"), t("confirmBulletRefund")],
      outcome: d.outcome,
    };
    remountBody();
  }

  function contextFacts() {
    const state = S();
    return {
      case_id: state.caseId || null,
      chat_intent: state.chatIntent || null,
      product: state.contextProduct || null,
      amount_lkr: state.contextAmount || (state.decision && state.decision.amount_lkr) || null,
    };
  }

  function pickResultKind(state) {
    const intent = state.chatIntent || "";
    const outcome = state.decision && state.decision.outcome;
    if (state.mode === "human" || outcome === "HANDOFF") return "handoff";
    if (state.mode === "knowledge") return "knowledge";
    if (state.mode === "miss") return "miss";
    if (intent === "DATA_SLOW" || intent === "FUP_QUERY") return "usage";
    if (intent === "PACK_RECOMMEND") return "packages";
    if (intent === "NETWORK_STATUS") return "network";
    return "investigation";
  }

  function onClick(event) {
    const act = event.target.closest("[data-cc]");
    if (!act) return false;
    const name = act.dataset.cc;
    if (name === "stop") {
      event.stopPropagation();
      return true;
    }
    if (name === "back") {
      unmount();
      hooks.go("home");
      return true;
    }
    if (name === "lang") {
      hooks.setLang(act.dataset.lang);
      return true;
    }
    if (name === "new") {
      newChat();
      return true;
    }
    if (name === "history") {
      ui.showHistory = true;
      remountBody();
      return true;
    }
    if (name === "close-history") {
      ui.showHistory = false;
      remountBody();
      return true;
    }
    if (name === "open-thread") {
      openThread(act.dataset.id);
      return true;
    }
    if (name === "toggle-topics") {
      ui.showTopics = !ui.showTopics;
      remountBody();
      return true;
    }
    if (name === "topic-cat") {
      ui.topicCategory = act.dataset.cat;
      remountBody();
      return true;
    }
    if (name === "ask") {
      const qKey = act.dataset.q || null;
      const label = act.dataset.label || "";
      const intent = act.dataset.intent || null;
      if (label && (!qKey || label !== hooks.T(qKey))) {
        S().question = label;
        hooks.ask(null, false, null, { chatIntent: intent });
      } else {
        hooks.ask(qKey, false, null, { chatIntent: intent });
      }
      return true;
    }
    if (name === "follow") {
      const key = act.dataset.key;
      const intent = act.dataset.intent;
      if (intent === "HANDOFF") hooks.ask(null, true, null);
      else {
        if (key) S().question = t(key);
        hooks.ask(null, false, null, { chatIntent: intent || null });
      }
      return true;
    }
    if (name === "toggle-evidence") {
      ui.showEvidence = !ui.showEvidence;
      remountBody();
      return true;
    }
    if (name === "confirm-fix") {
      openConfirmModal();
      return true;
    }
    if (name === "staff-approve") {
      hooks.proposeAndSend();
      return true;
    }
    if (name === "cancel-confirm") {
      ui.pendingConfirm = null;
      remountBody();
      return true;
    }
    if (name === "do-confirm") {
      const outcome = (ui.pendingConfirm && ui.pendingConfirm.outcome) || (S().decision && S().decision.outcome);
      ui.pendingConfirm = null;
      remountBody();
      hooks.confirmFix(outcome);
      return true;
    }
    if (name === "handoff") {
      hooks.ask(null, true, null);
      return true;
    }
    if (name === "receipt-explain") {
      hooks.explainReceipt();
      return true;
    }
    if (name === "open-receipt") {
      hooks.openReceipt(act.dataset.id);
      return true;
    }
    if (name === "go-usage") {
      unmount();
      hooks.go("usage");
      return true;
    }
    if (name === "go-network") {
      unmount();
      hooks.go("network");
      return true;
    }
    if (name === "go-cases") {
      unmount();
      hooks.go("cases");
      return true;
    }
    if (name === "pack-details" || name === "pack-buy") {
      unmount();
      hooks.go("packages");
      return true;
    }
    return false;
  }

  global.ClarityChat = {
    init(h) {
      hooks = h;
    },
    mount,
    unmount,
    remountBody,
    pushUser,
    pushAi,
    replaceLastAi,
    setThinking,
    setProgress,
    finishWithCard,
    pickResultKind,
    contextFacts,
    newChat,
    onClick,
    persistCurrentThread,
    showSuccessAndReceipt() {
      const state = S();
      state.mode = "resolved";
      pushAi("success");
      if (state.receiptDoc) pushAi("receipt");
      remountBody();
      persistCurrentThread();
    },
  };
})(window);
