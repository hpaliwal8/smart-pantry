(async function () {
  const listEl = document.getElementById("pantry-list");
  const form = document.getElementById("pantry-add");

  async function render() {
    listEl.innerHTML = ui.skeleton(3);
    try {
      const items = await api.get("/api/pantry/");
      if (!items.length) {
        listEl.innerHTML = '<p class="muted">Your pantry is empty. Add something above.</p>';
        return;
      }
      listEl.innerHTML = items.map(itemRow).join("");
      listEl.querySelectorAll("[data-del]").forEach((b) => {
        b.addEventListener("click", async () => {
          await api.del("/api/pantry/" + b.dataset.del);
          ui.toast("Removed from pantry");
          render();
        });
      });
    } catch (e) {
      listEl.innerHTML = '<p class="muted">Could not load pantry.</p>';
      ui.toast(e.message, "error");
    }
  }

  function itemRow(it) {
    const meta = [it.quantity, it.unit, it.category, it.expiry_date && "exp " + it.expiry_date]
      .filter(Boolean).join(" · ");
    return `
      <div class="card">
        <div class="row">
          <div class="left">
            <div>
              <h3>${ui.escape(it.name)}</h3>
              <div class="meta">${ui.escape(meta || "—")}</div>
            </div>
          </div>
          <div class="actions">
            <button class="danger" data-del="${it.sk}">Remove</button>
          </div>
        </div>
      </div>`;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = Object.fromEntries(fd.entries());
    payload.quantity = parseFloat(payload.quantity) || 1;
    try {
      await api.post("/api/pantry/", payload);
      form.reset();
      form.querySelector('[name=quantity]').value = 1;
      ui.toast("Added to pantry");
      render();
    } catch (e) { ui.toast(e.message, "error"); }
  });

  render();
})();
