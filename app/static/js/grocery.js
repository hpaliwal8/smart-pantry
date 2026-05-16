(async function () {
  const listEl = document.getElementById("grocery-list");
  const form = document.getElementById("grocery-add");

  async function render() {
    listEl.innerHTML = ui.skeleton(3);
    const items = await api.get("/api/grocery/");
    if (!items.length) { listEl.innerHTML = '<p class="muted">Your grocery list is empty.</p>'; return; }
    listEl.innerHTML = items.map(row).join("");
    listEl.querySelectorAll("input[type=checkbox]").forEach((cb) => {
      cb.addEventListener("change", async () => {
        await api.put("/api/grocery/" + cb.dataset.id, { purchased: cb.checked });
        render();
      });
    });
    listEl.querySelectorAll("[data-del]").forEach((b) => {
      b.addEventListener("click", async () => {
        await api.del("/api/grocery/" + b.dataset.del);
        render();
      });
    });
  }

  function row(it) {
    const meta = [it.quantity, it.unit].filter(Boolean).join(" ");
    return `
      <div class="card">
        <div class="row">
          <div class="left">
            <input type="checkbox" data-id="${it.sk}" ${it.purchased ? "checked" : ""} />
            <div>
              <h3 class="${it.purchased ? "purchased" : ""}">${ui.escape(it.name)}</h3>
              <div class="meta">${ui.escape(meta)}</div>
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
    await api.post("/api/grocery/", payload);
    form.reset();
    form.querySelector("[name=quantity]").value = 1;
    render();
  });

  document.getElementById("move-to-pantry").addEventListener("click", async () => {
    const res = await api.post("/api/grocery/move_to_pantry", {});
    ui.toast(`Moved ${res.moved.length} item(s) to pantry`);
    render();
  });

  render();
})();
