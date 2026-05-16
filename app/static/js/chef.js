// Chef Charlie chat widget. Renders structured blocks returned by /api/chat.
(function () {
  const panel = document.getElementById("chef-panel");
  const log = document.getElementById("chef-log");
  const form = document.getElementById("chef-form");
  const input = document.getElementById("chef-input");
  const toggle = document.getElementById("chef-toggle");
  const closeBtn = document.getElementById("chef-close");
  if (!panel) return;

  let history = [];

  toggle.addEventListener("click", () => panel.classList.toggle("hidden"));
  closeBtn.addEventListener("click", () => panel.classList.add("hidden"));

  function addBubble(html, klass = "assistant") {
    const el = document.createElement("div");
    el.className = "bubble " + klass;
    el.innerHTML = html;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function renderBlocks(blocks) {
    for (const b of blocks) {
      if (b.type === "text") {
        addBubble(ui.escape(b.content || "").replace(/\n/g, "<br>"));
      } else if (b.type === "recipe_card") {
        const ings = (b.ingredients || []).map((i) => `<li>${ui.escape(i)}</li>`).join("");
        const steps = (b.instructions || []).map((i) => `<li>${ui.escape(i)}</li>`).join("");
        const el = addBubble(`
          <h4>${ui.escape(b.title || "Recipe")}</h4>
          <ul class="ing-list">${ings}</ul>
          <ol class="step-list">${steps}</ol>
          <button class="ghost" data-save>Save recipe</button>
        `, "recipe-card actionable");
        el.querySelector("[data-save]").addEventListener("click", async () => {
          await api.post("/api/recipes/", {
            title: b.title, ingredients: b.ingredients || [], instructions: b.instructions || [],
          });
          ui.toast("Recipe saved");
        });
      } else if (b.type === "grocery_suggestion") {
        const items = (b.items || []).map((i, idx) => `<li><label><input type="checkbox" data-idx="${idx}" checked /> ${ui.escape(i.name)}${i.quantity ? " · " + ui.escape(i.quantity) : ""}</label></li>`).join("");
        const el = addBubble(`
          <p>Add to grocery?</p>
          <ul>${items}</ul>
          <button class="ghost" data-confirm>Add selected</button>
        `, "actionable");
        el.querySelector("[data-confirm]").addEventListener("click", async () => {
          const checked = [...el.querySelectorAll("input:checked")].map((c) => b.items[Number(c.dataset.idx)]);
          await api.post("/api/grocery/bulk", { items: checked });
          ui.toast(`Added ${checked.length} item(s)`);
        });
      } else if (b.type === "meal_plan") {
        const slots = (b.slots || []).map((s) => `<li>${ui.escape(["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][s.day] || "?")} ${ui.escape(s.meal)}: ${ui.escape(s.title)}</li>`).join("");
        const el = addBubble(`
          <p>Proposed plan:</p>
          <ul>${slots}</ul>
          <button class="ghost" data-apply>Apply to meal plan</button>
        `, "actionable");
        el.querySelector("[data-apply]").addEventListener("click", async () => {
          // For each slot, find or create a matching recipe, then set the slot.
          let ok = 0, fail = 0;
          for (const s of b.slots || []) {
            try {
              let rid = null;
              const recipes = await api.get("/api/recipes/");
              const found = recipes.find((r) => r.title.toLowerCase() === String(s.title).toLowerCase());
              if (found) rid = found.sk;
              else {
                const gen = await api.post("/api/recipes/generate", { prompt: s.title });
                if (gen && gen.title) {
                  const saved = await api.post("/api/recipes/", gen);
                  rid = saved.sk;
                }
              }
              if (!rid) { fail++; continue; }
              const mealKey = String(s.meal || "").toLowerCase()[0]; // breakfast->b
              await api.post("/api/meals/", { day: s.day, meal: mealKey, recipe_id: rid });
              ok++;
            } catch (e) { fail++; }
          }
          ui.toast(`Applied ${ok}/${ok+fail} slots`);
        });
      } else if (b.type === "action") {
        const el = addBubble(`<button class="ghost" data-go>${ui.escape(b.label || "Run")}</button>`, "actionable");
        el.querySelector("[data-go]").addEventListener("click", async () => {
          if (b.action === "add_to_grocery") {
            await api.post("/api/grocery/bulk", { items: b.payload?.items || [] });
            ui.toast("Added");
          } else { ui.toast("Action: " + b.action); }
        });
      } else {
        addBubble(ui.escape(JSON.stringify(b)));
      }
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;
    addBubble(ui.escape(msg), "user");
    history.push({ role: "user", content: msg });
    input.value = "";
    const loading = addBubble('<span class="skeleton" style="display:inline-block;width:6rem;"></span>');
    try {
      const res = await api.post("/api/chat/", { message: msg, history: history.slice(-8) });
      loading.remove();
      renderBlocks(res.blocks || []);
      // Track minimal assistant turn for context
      history.push({ role: "assistant", content: (res.blocks || []).map((b) => b.content || b.title || "").filter(Boolean).join(" ") });
    } catch (err) {
      loading.remove();
      addBubble(ui.escape("Error: " + err.message));
    }
  });

  // Seed greeting
  addBubble("Hi — I'm Chef Charlie. I can see your pantry, grocery list, meal plan, and recipes. Ask me to plan a week, suggest dinner, or build a shopping list.");
})();
