(async function () {
  ui.tabs(document);
  const matchEl = document.getElementById("match-list");
  const allEl = document.getElementById("all-list");
  const suggestEl = document.getElementById("suggest-out");
  const previewEl = document.getElementById("recipe-preview");

  function scoreClass(s) { return s >= 0.999 ? "" : s >= 0.5 ? "partial" : "low"; }

  function recipeCard(r, opts = {}) {
    const m = r.match || {};
    const pct = m.score != null ? Math.round(m.score * 100) + "%" : "";
    const ings = (r.ingredients || []).map((i) => `<li>${ui.escape(i)}</li>`).join("");
    const missing = (m.missing || []).map((i) => `<li>${ui.escape(i)}</li>`).join("");
    const id = r.sk || r.recipe_id || "";
    return `
      <div class="card">
        <div class="row">
          <div class="left">
            <div>
              <h3>${ui.escape(r.title || "(untitled)")}</h3>
              <div class="meta">${(r.ingredients || []).length} ingredients</div>
            </div>
          </div>
          ${pct ? `<span class="score-pill ${scoreClass(m.score)}">${pct}</span>` : ""}
        </div>
        <details style="margin-top:0.5rem;">
          <summary class="muted">Ingredients</summary>
          <ul>${ings}</ul>
          ${missing ? `<p class="muted">Missing:</p><ul>${missing}</ul>
            <button class="ghost" data-add-missing="${id}">Add missing to grocery</button>` : ""}
        </details>
        <div class="actions">
          <button class="danger" data-del="${id}">Delete</button>
        </div>
      </div>`;
  }

  let allRecipes = [];

  async function loadMatched() {
    matchEl.innerHTML = ui.skeleton(3);
    const matched = await api.get("/api/recipes/match");
    if (!matched.length) {
      matchEl.innerHTML = '<p class="muted">No recipes yet. Add one in the Import / generate tab.</p>';
      return;
    }
    matchEl.innerHTML = matched.map((r) => recipeCard(r)).join("");
    bindCardActions(matchEl, matched);
  }

  async function loadAll() {
    allEl.innerHTML = ui.skeleton(3);
    allRecipes = await api.get("/api/recipes/");
    if (!allRecipes.length) { allEl.innerHTML = '<p class="muted">No recipes yet.</p>'; return; }
    allEl.innerHTML = allRecipes.map((r) => recipeCard(r)).join("");
    bindCardActions(allEl, allRecipes);
  }

  async function loadSuggest() {
    suggestEl.innerHTML = ui.skeleton(2);
    const res = await api.get("/api/recipes/suggest?top=5");
    const s = res[0] || {};
    const buyList = (s.buy || []).map((i) => `<li>${ui.escape(i)}</li>`).join("");
    const unlockList = (s.unlocks || []).map((r) => `<li>${ui.escape(r.title)}</li>`).join("");
    suggestEl.innerHTML = `
      <div class="card">
        <h3>Buy these ${(s.buy || []).length} items</h3>
        <ul>${buyList || "<li class='muted'>Your pantry already covers your library.</li>"}</ul>
        <h3>Unlocks</h3>
        <ul>${unlockList || "<li class='muted'>—</li>"}</ul>
        ${(s.buy || []).length ? '<button class="primary" id="suggest-add">Add all to grocery</button>' : ""}
      </div>`;
    const btn = document.getElementById("suggest-add");
    if (btn) btn.addEventListener("click", async () => {
      await api.post("/api/grocery/bulk", { items: s.buy.map((n) => ({ name: n })) });
      ui.toast("Added to grocery");
    });
  }

  function bindCardActions(root, items) {
    root.querySelectorAll("[data-del]").forEach((b) => {
      b.addEventListener("click", async () => {
        await api.del("/api/recipes/" + b.dataset.del);
        ui.toast("Deleted");
        loadMatched(); loadAll();
      });
    });
    root.querySelectorAll("[data-add-missing]").forEach((b) => {
      b.addEventListener("click", async () => {
        const id = b.dataset.addMissing;
        const r = items.find((x) => (x.sk || x.recipe_id) === id);
        if (!r) return;
        const missing = (r.match && r.match.missing) || [];
        await api.post("/api/grocery/bulk", {
          items: missing.map((m) => ({ name: m, source_recipe_id: id })),
        });
        ui.toast(`Added ${missing.length} item(s)`);
      });
    });
  }

  // Manual recipe form
  document.getElementById("recipe-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      title: fd.get("title"),
      ingredients: String(fd.get("ingredients") || "").split("\n").map((x) => x.trim()).filter(Boolean),
      instructions: String(fd.get("instructions") || "").split("\n").map((x) => x.trim()).filter(Boolean),
      image_url: fd.get("image_url") || "",
      library: !!fd.get("library"),
    };
    await api.post("/api/recipes/", payload);
    ui.toast("Recipe saved");
    e.target.reset();
    loadAll(); loadMatched();
  });

  // Import from URL
  document.getElementById("import-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = new FormData(e.target).get("url");
    previewEl.innerHTML = ui.skeleton(1);
    try {
      const data = await api.post("/api/recipes/import", { url });
      fillRecipeForm(data);
      previewEl.innerHTML = '<p class="muted">Imported — review and save below.</p>';
    } catch (err) { previewEl.innerHTML = `<p class="muted">${ui.escape(err.message)}</p>`; }
  });

  // Generate by title
  document.getElementById("generate-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const prompt = new FormData(e.target).get("prompt");
    previewEl.innerHTML = ui.skeleton(1);
    try {
      const data = await api.post("/api/recipes/generate", { prompt });
      fillRecipeForm(data);
      previewEl.innerHTML = '<p class="muted">Generated — review and save below.</p>';
    } catch (err) { previewEl.innerHTML = `<p class="muted">${ui.escape(err.message)}</p>`; }
  });

  function fillRecipeForm(data) {
    const f = document.getElementById("recipe-form");
    f.title.value = data.title || "";
    f.ingredients.value = (data.ingredients || []).join("\n");
    f.instructions.value = (data.instructions || []).join("\n");
    f.image_url.value = data.image_url || "";
  }

  await Promise.all([loadMatched(), loadAll(), loadSuggest()]);
})();
