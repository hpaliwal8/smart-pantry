(async function () {
  const grid = document.getElementById("meal-grid");
  const previewEl = document.getElementById("preview-out");
  const picker = document.getElementById("recipe-picker");
  const pickerList = document.getElementById("picker-list");
  const pickerSearch = document.getElementById("picker-search");

  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const MEALS = [["b", "Breakfast"], ["l", "Lunch"], ["d", "Dinner"]];

  let plan = {}; // slot_id -> { recipe }
  let recipes = [];
  let pickingSlot = null;

  function slotId(day, meal) { return `d${day}_m${meal}`; }

  function renderGrid() {
    let html = '<div class="head"></div>' + DAYS.map((d) => `<div class="head">${d}</div>`).join("");
    for (const [m, label] of MEALS) {
      html += `<div class="row-label">${label}</div>`;
      for (let d = 0; d < 7; d++) {
        const id = slotId(d, m);
        const filled = plan[id];
        const title = filled && filled.recipe ? filled.recipe.title : "+ add";
        html += `
          <div class="meal-cell ${filled ? "filled" : ""}" data-slot="${id}" data-day="${d}" data-meal="${m}">
            <span>${ui.escape(title)}</span>
            ${filled ? `<button class="clear" data-clear="${id}">clear</button>` : ""}
          </div>`;
      }
    }
    grid.innerHTML = html;
    grid.querySelectorAll(".meal-cell").forEach((c) => {
      c.addEventListener("click", (e) => {
        if (e.target.matches("[data-clear]")) return;
        openPicker(c.dataset.day, c.dataset.meal);
      });
    });
    grid.querySelectorAll("[data-clear]").forEach((b) => {
      b.addEventListener("click", async (e) => {
        e.stopPropagation();
        await api.del("/api/meals/" + b.dataset.clear);
        await load();
      });
    });
  }

  function openPicker(day, meal) {
    pickingSlot = { day: Number(day), meal };
    picker.classList.remove("hidden");
    pickerSearch.value = "";
    renderPicker("");
    pickerSearch.focus();
  }
  function closePicker() { picker.classList.add("hidden"); pickingSlot = null; }
  document.getElementById("picker-close").addEventListener("click", closePicker);
  picker.addEventListener("click", (e) => { if (e.target === picker) closePicker(); });

  function renderPicker(q) {
    const filtered = recipes.filter((r) => r.title.toLowerCase().includes(q.toLowerCase()));
    if (!filtered.length) { pickerList.innerHTML = '<p class="muted">No matches.</p>'; return; }
    pickerList.innerHTML = filtered.map((r) => `
      <div class="card" data-pick="${r.sk}">
        <div class="row">
          <div><strong>${ui.escape(r.title)}</strong>
            <div class="meta">${(r.ingredients || []).length} ingredients</div></div>
        </div>
      </div>`).join("");
    pickerList.querySelectorAll("[data-pick]").forEach((c) => {
      c.addEventListener("click", async () => {
        if (!pickingSlot) return;
        await api.post("/api/meals/", { ...pickingSlot, recipe_id: c.dataset.pick });
        closePicker(); await load();
      });
    });
  }
  pickerSearch.addEventListener("input", (e) => renderPicker(e.target.value));

  async function loadPreview() {
    previewEl.innerHTML = ui.skeleton(2);
    const p = await api.get("/api/meals/grocery_preview");
    const have = p.have.map((i) => `<li>✓ ${ui.escape(i.name)} <span class="muted">(${i.recipes.length} recipe${i.recipes.length>1?"s":""})</span></li>`).join("");
    const buy = p.buy.map((i) => `<li>• ${ui.escape(i.name)} <span class="muted">(${i.recipes.length})</span></li>`).join("");
    previewEl.innerHTML = `
      <div class="card">
        <h3>To buy (${p.buy.length})</h3>
        <ul>${buy || '<li class="muted">Nothing — you have it all!</li>'}</ul>
        <h3>Already in pantry (${p.have.length})</h3>
        <ul>${have || '<li class="muted">—</li>'}</ul>
      </div>`;
    document.getElementById("preview-add-all").onclick = async () => {
      if (!p.buy.length) { ui.toast("Nothing to add"); return; }
      await api.post("/api/grocery/bulk", { items: p.buy.map((b) => ({ name: b.name })) });
      ui.toast(`Added ${p.buy.length} item(s) to grocery`);
    };
  }

  async function load() {
    [recipes, planArr] = await Promise.all([api.get("/api/recipes/"), api.get("/api/meals/")]);
    plan = {};
    for (const s of planArr) { plan[s.slot_id] = s; }
    renderGrid();
    await loadPreview();
  }

  let planArr = [];
  await load();
})();
