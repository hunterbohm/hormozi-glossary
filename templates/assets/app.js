/* The Hormozi Glossary — client search + category filter + deep links. Vanilla JS. */
(function () {
  "use strict";

  var dataEl = document.getElementById("glossary-data");
  if (!dataEl) return;

  var DATA;
  try {
    DATA = JSON.parse(dataEl.textContent);
  } catch (err) {
    return; // never break the static page
  }

  // Precompute a lowercase search blob per id (term + aliases + short_def + full_def).
  var index = Object.create(null);
  for (var i = 0; i < DATA.length; i++) {
    var e = DATA[i];
    var blob = [
      e.term || "",
      (e.aliases || []).join(" "),
      e.short_def || "",
      e.full_def || ""
    ].join(" ").toLowerCase();
    index[e.id] = { cat: e.category, blob: blob };
  }

  var search = document.getElementById("search");
  var countEl = document.getElementById("match-count");
  var noResults = document.getElementById("no-results");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var cards = Array.prototype.slice.call(document.querySelectorAll(".term"));
  var sections = Array.prototype.slice.call(document.querySelectorAll(".category"));

  var total = DATA.length;
  var activeCat = "all";
  var query = "";

  function apply() {
    var q = query.trim().toLowerCase();
    var visible = 0;

    for (var i = 0; i < cards.length; i++) {
      var card = cards[i];
      var meta = index[card.id];
      if (!meta) { card.hidden = true; continue; }
      var okCat = activeCat === "all" || meta.cat === activeCat;
      var okQ = !q || meta.blob.indexOf(q) !== -1;
      var show = okCat && okQ;
      card.hidden = !show;
      if (show) visible++;
    }

    // Collapse category sections that have no visible cards.
    for (var s = 0; s < sections.length; s++) {
      var sec = sections[s];
      sec.hidden = sec.querySelectorAll(".term:not([hidden])").length === 0;
    }

    if (countEl) {
      countEl.textContent = visible === total
        ? total + " terms"
        : visible + " of " + total + " terms";
    }
    if (noResults) noResults.hidden = visible !== 0;
  }

  function setCat(cat) {
    activeCat = cat;
    for (var i = 0; i < chips.length; i++) {
      var on = chips[i].getAttribute("data-cat") === cat;
      chips[i].classList.toggle("is-active", on);
      chips[i].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  if (search) {
    search.addEventListener("input", function () { query = this.value; apply(); });
    search.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { this.value = ""; query = ""; apply(); }
    });
  }

  for (var c = 0; c < chips.length; c++) {
    chips[c].addEventListener("click", function () {
      setCat(this.getAttribute("data-cat"));
      apply();
    });
  }

  // "/" focuses the search box (unless already typing somewhere).
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "/" || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    var t = ev.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (search) { ev.preventDefault(); search.focus(); }
  });

  // Deep links: reset filters so the target is visible, scroll, and flash it.
  function gotoHash() {
    var id = decodeURIComponent((location.hash || "").slice(1));
    if (!id) return;
    var el = document.getElementById(id);
    if (!el || !el.classList.contains("term")) return;
    if (search) search.value = "";
    query = "";
    setCat("all");
    apply();
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.classList.remove("is-target");
    void el.offsetWidth; // restart the animation
    el.classList.add("is-target");
    window.setTimeout(function () { el.classList.remove("is-target"); }, 2000);
  }

  window.addEventListener("hashchange", gotoHash);

  apply();
  if (location.hash) gotoHash();
})();
