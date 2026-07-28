/* AssistantAMU documentation site — the behaviours the prose cannot carry on
   its own: switching the theme, retracting the two summaries, following the
   reading position, copying a command, and measuring the bar the rest is
   positioned from.

   No dependency and no build step. Everything degrades to a usable page when
   the script does not run: the theme stays light, the site summary is open,
   the page summary is absent rather than empty, previous/next is rendered at
   build time, and the heading anchors come from the Markdown toc extension. */

(function () {
  "use strict";

  var NARROW = window.matchMedia("(max-width: 56rem)");

  /* localStorage throws in a few privacy configurations; a lost preference is
     not worth breaking the page for. */
  function remember(key, value) {
    try { window.localStorage.setItem(key, value); } catch (error) { /* ignore */ }
  }
  function recall(key) {
    try { return window.localStorage.getItem(key); } catch (error) { return null; }
  }

  /* --- Height of the masthead ------------------------------------------- */

  /* Everything that sticks below the bar is positioned from --topbar, whose
     declared value is that of a bar on one line. Below 56rem the subtitle takes
     a line of its own and the bar grows, so the measured height replaces the
     declared one — otherwise the drawer opens over the subtitle. Without the
     script the declared value holds and only that overlap comes back. */
  function setUpMastheadHeight() {
    var masthead = document.querySelector(".masthead");
    if (!masthead) return;

    function measure() {
      var height = Math.round(masthead.getBoundingClientRect().height);
      document.documentElement.style.setProperty("--topbar", height + "px");
    }
    measure();
    window.addEventListener("resize", measure);
  }

  /* --- Light and dark theme --------------------------------------------- */

  /* An inline script in the head applies the stored choice before the
     stylesheet loads — no flash of the wrong theme; this button only has to
     switch it afterwards. Light is the default, and the attribute is removed
     rather than set to "light", so the default never needs a value. */
  function setUpThemeToggle() {
    var toggle = document.getElementById("themeToggle");
    if (!toggle) return;

    function apply(dark) {
      if (dark) document.documentElement.setAttribute("data-theme", "dark");
      else document.documentElement.removeAttribute("data-theme");
      toggle.setAttribute("aria-pressed", dark ? "true" : "false");
    }

    apply(document.documentElement.getAttribute("data-theme") === "dark");

    toggle.addEventListener("click", function () {
      var dark = document.documentElement.getAttribute("data-theme") !== "dark";
      apply(dark);
      remember("amu.theme", dark ? "dark" : "light");
    });
  }

  /* --- Site summary, retractable ---------------------------------------- */

  function setUpSidebar() {
    var toggle = document.getElementById("navToggle");
    var sidebar = document.getElementById("sommaire");
    var scrim = document.getElementById("scrim");
    if (!toggle || !sidebar) return;

    function apply(open) {
      document.body.classList.toggle("nav-closed", !open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      // On a narrow screen the sidebar is a drawer over the text, so it needs
      // the scrim; on a wide one it merely takes its column back.
      if (scrim) scrim.hidden = !(open && NARROW.matches);
    }

    // A narrow screen starts closed whatever the stored preference: the drawer
    // would cover the text the reader came for.
    var open = NARROW.matches ? false : recall("amu.nav") !== "closed";
    apply(open);

    toggle.addEventListener("click", function () {
      open = !open;
      apply(open);
      if (!NARROW.matches) remember("amu.nav", open ? "open" : "closed");
    });

    if (scrim) {
      scrim.addEventListener("click", function () { open = false; apply(false); });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && open && NARROW.matches) { open = false; apply(false); }
    });
    NARROW.addEventListener("change", function () {
      open = NARROW.matches ? false : recall("amu.nav") !== "closed";
      apply(open);
    });
  }

  /* --- Rubrics of the site summary -------------------------------------- */

  /* Each page of the tree carries its sections. The current one is open, the
     others follow what the reader last decided about them. */
  function setUpRubrics() {
    var items = document.querySelectorAll(".sidebar .nav-item.has-sub");
    if (!items.length) return;

    var opened;
    try { opened = JSON.parse(recall("amu.rubrics") || "[]"); } catch (error) { opened = []; }
    if (!Array.isArray(opened)) opened = [];

    Array.prototype.forEach.call(items, function (item) {
      var toggle = item.querySelector(".sub-toggle");
      var link = item.querySelector(".nav-row > a");
      if (!toggle || !link) return;
      var key = link.getAttribute("href");

      // The current page is open whatever was stored: its sections are the
      // ones the reader is in.
      if (!item.classList.contains("open") && opened.indexOf(key) !== -1) {
        item.classList.add("open");
        toggle.setAttribute("aria-expanded", "true");
      }

      toggle.addEventListener("click", function () {
        var open = !item.classList.contains("open");
        item.classList.toggle("open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        var at = opened.indexOf(key);
        if (open && at === -1) opened.push(key);
        if (!open && at !== -1) opened.splice(at, 1);
        remember("amu.rubrics", JSON.stringify(opened));
      });
    });
  }

  /* --- Page summary, retractable, following the reading position -------- */

  function setUpPageSummary() {
    var aside = document.getElementById("toc");
    var list = document.getElementById("tocList");
    var toggle = document.getElementById("tocToggle");
    var content = document.getElementById("contenu");
    if (!aside || !list || !toggle || !content) return;

    // The embedded pages carry the id on the <section>, not on its heading.
    var headings = [].slice.call(
      content.querySelectorAll(".embed section[id]").length
        ? content.querySelectorAll(".embed section[id]")
        : content.querySelectorAll("h2[id], h3[id]")
    );
    // One or two headings are read faster than a summary of them.
    if (headings.length < 3) return;

    // On an API page every public function is a heading. Listing them all would
    // reproduce the page rather than summarise it, so a heading that is a bare
    // function signature is left out: modules and classes carry the structure,
    // the functions are read inside them. No prose heading looks like this.
    headings = headings.filter(function (heading) {
      var text = (heading.textContent || "").trim();
      return !/^[\w.]+\s*\(/.test(text);
    });
    if (headings.length < 3) return;

    var links = headings.map(function (heading) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      item.className = heading.tagName === "H3" ? "toc-sub" : "toc-top";
      link.href = "#" + heading.id;
      var titled = heading.tagName === "SECTION" ? heading.querySelector("h2") : heading;
      // The anchor mark belongs to the prose, not to the summary line.
      var label = ((titled || heading).textContent || "").replace(/[¶#]\s*$/, "").trim();
      // A class heading still carries its constructor arguments in some pages.
      var signature = label.match(/^((?:class\s+)?[\w.]+)\s*\(/);
      link.textContent = signature ? signature[1] : label;
      item.appendChild(link);
      list.appendChild(item);
      return link;
    });

    aside.hidden = false;

    var open = recall("amu.toc") !== "closed";
    function applyOpen(value) {
      aside.classList.toggle("toc-closed", !value);
      toggle.setAttribute("aria-expanded", value ? "true" : "false");
    }
    applyOpen(open);
    toggle.addEventListener("click", function () {
      open = !open;
      applyOpen(open);
      remember("amu.toc", open ? "open" : "closed");
    });

    // Reading position: the last heading whose top has passed the masthead.
    var current = null;
    function follow() {
      var limit = 96;
      var active = headings[0];
      for (var i = 0; i < headings.length; i++) {
        if (headings[i].getBoundingClientRect().top <= limit) active = headings[i];
        else break;
      }
      if (active === current) return;
      current = active;
      for (var j = 0; j < links.length; j++) {
        links[j].classList.toggle("current", headings[j] === active);
      }
    }

    var waiting = false;
    function schedule() {
      if (waiting) return;
      waiting = true;
      window.requestAnimationFrame(function () { waiting = false; follow(); });
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    follow();
  }

  /* --- Copying a code block --------------------------------------------- */

  function setUpCopyButtons() {
    var blocks = document.querySelectorAll(".content pre");
    Array.prototype.forEach.call(blocks, function (block) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy-btn";
      button.textContent = "Copier";
      button.setAttribute("aria-label", "Copier le contenu du bloc");

      button.addEventListener("click", function () {
        var text = block.innerText;
        function done(ok) {
          button.textContent = ok ? "Copié" : "Échec";
          button.classList.add(ok ? "copied" : "failed");
          window.setTimeout(function () {
            button.textContent = "Copier";
            button.classList.remove("copied", "failed");
          }, 1600);
        }
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(text).then(function () { done(true); },
                                                    function () { done(false); });
        } else {
          // Opened straight from the filesystem, the clipboard API is absent.
          var field = document.createElement("textarea");
          field.value = text;
          field.setAttribute("readonly", "");
          field.style.position = "fixed";
          field.style.top = "-1000px";
          document.body.appendChild(field);
          field.select();
          var ok = false;
          try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
          document.body.removeChild(field);
          done(ok);
        }
      });

      var shell = document.createElement("div");
      shell.className = "pre-shell";
      block.parentNode.insertBefore(shell, block);
      shell.appendChild(block);
      shell.appendChild(button);
    });
  }

  /* --- Assistant panel --------------------------------------------------- */

  /* The panel is markup of the page, rendered by base.html; this opens it,
     writes the thread and calls the API. Both the button and the panel are
     rendered hidden and revealed here — a page whose script never runs shows no
     control it cannot honour.

     Questions go to the origin the page is served from, unless data-api names
     another: the application mounts the built site under /site precisely so the
     two share an origin, which spares the API a CORS configuration and the
     browser its private network rules. */
  function setUpAssistant() {
    var panel = document.getElementById("assistant");
    var openBtn = document.getElementById("assistantOpen");
    var thread = document.getElementById("assistantThread");
    var blank = document.getElementById("assistantBlank");
    var form = document.getElementById("assistantForm");
    var input = document.getElementById("assistantInput");
    var send = document.getElementById("assistantSend");
    var foot = document.getElementById("assistantFoot");
    if (!panel || !openBtn || !thread || !blank || !form || !input || !send || !foot) return;

    var closeBtn = document.getElementById("assistantClose");
    var resetBtn = document.getElementById("assistantReset");
    var seeds = [].slice.call(panel.querySelectorAll(".assistant-seed"));

    var api = (panel.getAttribute("data-api") || "").replace(/\/+$/, "");
    var history = [];   // {role, content} — the multi-turn context /ask expects
    var open = false;
    var live = false;   // an instance answered /health
    var probing = false;

    panel.hidden = false;
    openBtn.hidden = false;

    function esc(text) {
      return String(text).replace(/[&<>]/g, function (character) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[character];
      });
    }

    /* Emphasis, citation marks and paragraphs. The marks are what this panel
       exists to show — an assertion attached to a passage — so they are drawn
       rather than left as brackets in the running text. */
    function render(answer) {
      var safe = esc(answer)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[(S\d+)\]/g, '<span class="assistant-cite">$1</span>');
      return safe.split(/\n{2,}/).map(function (block) {
        return "<p>" + block.replace(/\n/g, "<br>") + "</p>";
      }).join("");
    }

    function sourcesHtml(sources) {
      if (!sources || !sources.length) return "";
      var items = sources.map(function (source, index) {
        var page = source.page != null ? ", p. " + source.page : "";
        return '<div class="assistant-src"><div class="assistant-src-head">[S' + (index + 1)
             + "] " + esc(source.title) + page
             + ' <span class="assistant-src-score">' + source.score.toFixed(2)
             + "</span></div><div class=\"assistant-src-excerpt\">"
             + esc(source.excerpt) + "…</div></div>";
      }).join("");
      return '<details class="assistant-sources"><summary>Sources citées ('
           + sources.length + ")</summary>" + items + "</details>";
    }

    function append(className, html) {
      var node = document.createElement("div");
      node.className = className;
      node.innerHTML = html;
      thread.appendChild(node);
      thread.scrollTop = thread.scrollHeight;
      return node;
    }

    /* The reformulation belongs to the question, not to the answer: the
       condensation of a follow-up, and the query actually searched when the
       rewrite changed it. A condensation that gives the question back unchanged
       is not shown — the line exists to signal a difference, and printing it
       when there is none teaches the reader to stop reading it. */
    function reformHtml(question, condensed, rewritten) {
      var lines = "";
      if (condensed && condensed.trim() !== question.trim()) {
        lines += "↳ compris comme : « " + esc(condensed) + " »";
      }
      if (rewritten && rewritten.trim() !== question.trim()) {
        lines += (lines ? "<br>" : "") + "🔎 recherché comme : « " + esc(rewritten) + " »";
      }
      return lines;
    }

    function post(path, body) {
      return window.fetch(api + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
    }

    function busy(state) {
      send.disabled = state;
      input.disabled = state;
      seeds.forEach(function (seed) { seed.disabled = state; });
    }

    function ask(question) {
      blank.hidden = true;
      append("assistant-q", esc(question));
      var answer = append("assistant-a",
        '<span class="assistant-typing"><span></span><span></span><span></span></span>');
      busy(true);

      var context = history.length ? history.slice() : null;

      /* /prepare resolves the retrieval query without generating, so the panel
         can show it before the answer arrives. Best effort: when it fails, the
         same fields come back with the answer, only later. */
      post("/prepare", { question: question, history: context })
        .then(function (response) { return response.ok ? response.json() : null; })
        .catch(function () { return null; })
        .then(function (prepared) {
          if (prepared) {
            var lines = reformHtml(question, prepared.condensed_question, prepared.rewritten_query);
            if (lines) {
              var node = document.createElement("div");
              node.className = "assistant-reform";
              node.innerHTML = lines;
              thread.insertBefore(node, answer);
            }
          }
          var body = { question: question, history: context };
          // Reuse the resolved query so the reformulation shown cannot drift
          // from the one actually searched.
          if (prepared) {
            body.retrieval_query = prepared.retrieval_query;
            body.condensed_question = prepared.condensed_question;
            body.rewritten_query = prepared.rewritten_query;
          }
          return post("/ask", body).then(function (response) {
            return response.json().then(function (data) {
              if (!response.ok) throw new Error(data.detail || "HTTP " + response.status);
              return data;
            });
          });
        })
        .then(function (data) {
          answer.innerHTML = render(data.answer) + sourcesHtml(data.sources);
          history.push({ role: "user", content: question });
          history.push({ role: "assistant", content: data.answer });
        })
        .catch(function (error) {
          answer.className = "assistant-a assistant-error";
          answer.innerHTML = "<p>La question n'a pas abouti : " + esc(error.message)
            + ".</p><p>Vérifier que l'instance répond, puis reposer la question.</p>";
        })
        .then(function () {
          busy(false);
          thread.scrollTop = thread.scrollHeight;
          if (open) input.focus();
        });
    }

    /* Which instance answers, and whether one answers at all. Probed on
       opening, and again on the next opening as long as none has: a page whose
       panel is never opened never calls the API. */
    function probe() {
      if (live || probing) return;
      probing = true;
      busy(true);
      foot.textContent = "Recherche d'une instance…";
      var address = (api || window.location.origin).replace(/^https?:\/\//, "");
      var local = /^(127\.0\.0\.1|localhost|\[::1\])(:|$)/.test(address);

      window.fetch(api + "/health")
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          live = true;
          probing = false;
          busy(false);
          foot.textContent = (local ? "Instance locale" : "Instance publique")
            + " · " + data.documents + " documents, " + data.chunks + " fragments indexés"
            + (data.llm_backend === "ok" ? "" : " · modèle de génération injoignable");
        })
        .catch(function () {
          probing = false;
          busy(true);
          foot.textContent = "Aucune instance ne répond : le panneau est inactif. "
            + "Lancer l'API, puis rouvrir le panneau.";
        });
    }

    function apply(state) {
      open = state;
      panel.classList.toggle("open", state);
      openBtn.setAttribute("aria-expanded", state ? "true" : "false");
      if (state) {
        probe();
        input.focus();
      } else {
        openBtn.focus();
      }
    }

    openBtn.addEventListener("click", function () { apply(!open); });
    if (closeBtn) closeBtn.addEventListener("click", function () { apply(false); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && open) apply(false);
    });

    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        history.length = 0;
        while (thread.lastChild && thread.lastChild !== blank) {
          thread.removeChild(thread.lastChild);
        }
        blank.hidden = false;
        input.value = "";
        input.style.height = "auto";
        input.focus();
      });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var question = input.value.trim();
      if (!question || !live) return;
      input.value = "";
      input.style.height = "auto";
      ask(question);
    });

    /* Enter sends, Shift+Enter opens a line — the convention of every field of
       this kind, and the reason the field is a textarea rather than an input. */
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else form.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });

    input.addEventListener("input", function () {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 128) + "px";
    });

    /* A suggestion sends its question. Filling the field instead would ask the
       reader to confirm a choice they have already made. */
    seeds.forEach(function (seed) {
      seed.addEventListener("click", function () {
        if (live) ask(seed.textContent.trim());
      });
    });
  }

  setUpMastheadHeight();
  setUpThemeToggle();
  setUpSidebar();
  setUpRubrics();
  setUpPageSummary();
  setUpCopyButtons();
  setUpAssistant();
})();
