/* Project-owned presentation layer. No requests, auth hooks, Bot actions or model changes. */
(() => {
  "use strict";
  const root = document.documentElement;
  if (root.dataset.workflourWorkbench === "1") return;
  root.dataset.workflourWorkbench = "1";
  const storageKey = "workflour.settings.view.v1";
  const queryView = new URL(window.location.href).searchParams.get("workflourView");
  let view = "simple";
  try {
    if (window.localStorage.getItem(storageKey) === "full") view = "full";
  } catch { /* Browsers denying storage still get a working per-page switch. */ }
  if (queryView === "full" || queryView === "simple") view = queryView;

  const chinese = () => /^zh\b/i.test(root.lang) || /高级|设置/.test(
    document.querySelector("#app-settings-title")?.textContent || ""
  );

  function attachModelGuide(sheet) {
    const engines = sheet.querySelector('[data-settings-block="engines"]');
    let guide = sheet.querySelector("[data-workflour-model-guide]");
    // Native page changes retain the scroll container but only remove React-owned children.
    if (!engines || sheet.dataset.settingsLook !== "simple") {
      guide?.remove();
      return;
    }
    if (!guide) {
      guide = document.createElement("section");
      guide.dataset.workflourModelGuide = "";
      guide.className = "wf-model-guide";
      guide.translate = false;
      guide.append(document.createElement("h3"), document.createElement("p"), document.createElement("p"));
      engines.before(guide);
    }
    const copy = chinese() ? [
      "模型与思考程度",
      "给大管家发“打开模型设置”，选择要调整的 Bot、模型和思考程度。调整大管家自己时，交给通用助手。",
      "先确认修改当前任务还是以后默认值。运行中的任务请等本轮结束，或先停止。接入与引擎维护在高级设置中。"
    ] : [
      "Models and reasoning",
      "Ask the manager to open model settings, then choose the Bot, model and reasoning level. Use the general assistant to adjust the manager itself.",
      "Choose whether to change the current task or future defaults. Wait for a running turn to finish, or stop it first. Connection and engine maintenance are in Advanced settings."
    ];
    Array.from(guide.children).forEach((element, index) => {
      if (element.textContent !== copy[index]) element.textContent = copy[index];
    });
  }

  function updateButtons() {
    root.dataset.workflourView = view;
    for (const button of document.querySelectorAll("[data-workflour-settings-toggle]")) {
      const active = view === "full";
      const label = chinese() ? "高级设置" : "Advanced settings";
      const hint = chinese()
        ? (active ? "显示完整设置；点击返回日常设置" : "显示接入、密钥、云服务等完整设置")
        : (active ? "Full settings shown; return to everyday settings" : "Show all connection, key and cloud settings");
      if (button.getAttribute("aria-pressed") !== String(active)) button.setAttribute("aria-pressed", String(active));
      if (button.getAttribute("aria-label") !== label) button.setAttribute("aria-label", label);
      if (button.title !== hint) button.title = hint;
      const text = button.querySelector("[data-workflour-settings-label]");
      if (text.textContent !== label) text.textContent = label;
    }
  }

  function attach() {
    for (const sheet of document.querySelectorAll("[data-settings-sheet]")) {
      attachModelGuide(sheet);
      const dialog = sheet.querySelector('[role="dialog"][aria-labelledby="app-settings-title"]');
      if (!dialog || dialog.querySelector("[data-workflour-settings-toggle]")) continue;
      // Version-pinned native simple header. Advanced mode is already the full product page.
      const header = dialog.querySelector("header");
      if (!header) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "wf-settings-view-control";
      button.translate = false;
      button.dataset.workflourSettingsToggle = "";
      const text = document.createElement("span");
      text.dataset.workflourSettingsLabel = "";
      const indicator = document.createElement("span");
      indicator.className = "wf-settings-view-indicator";
      indicator.setAttribute("aria-hidden", "true");
      button.append(text, indicator);
      button.addEventListener("click", () => {
        view = view === "simple" ? "full" : "simple";
        try { window.localStorage.setItem(storageKey, view); } catch { /* No storage needed for this toggle. */ }
        updateButtons();
      });
      header.append(button);
    }
    updateButtons();
  }

  let scheduled = false;
  const observer = new MutationObserver((changes) => {
    // Ignore changes made inside our own controls to avoid observer feedback.
    if (!changes.some((change) => !(change.target instanceof Element) || !change.target.closest("[data-workflour-settings-toggle], [data-workflour-model-guide]"))) return;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; attach(); });
  });
  updateButtons();
  observer.observe(document.body, { childList: true, subtree: true });
  attach();
  window.addEventListener("storage", (event) => {
    if (event.key !== storageKey) return;
    view = event.newValue === "full" ? "full" : "simple";
    updateButtons();
  });
})();
