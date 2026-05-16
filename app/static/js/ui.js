// Tiny UI helpers: toast, escape, skeleton.
const ui = (() => {
  function escape(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }
  function toast(msg, kind) {
    const host = document.getElementById("toast-host");
    if (!host) { console.log("toast:", msg); return; }
    const el = document.createElement("div");
    el.className = "toast" + (kind === "error" ? " error" : "");
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }
  function skeleton(n = 3) {
    return Array.from({ length: n }, () => '<div class="card"><div class="skeleton" style="width:60%"></div></div>').join("");
  }
  function tabs(root) {
    const tabs = root.querySelectorAll(".tab");
    const panes = root.querySelectorAll(".tab-pane");
    tabs.forEach((t) => t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      panes.forEach((p) => p.classList.remove("active"));
      t.classList.add("active");
      const pane = root.querySelector("#tab-" + t.dataset.tab);
      if (pane) pane.classList.add("active");
    }));
  }
  return { escape, toast, skeleton, tabs };
})();
window.ui = ui;
