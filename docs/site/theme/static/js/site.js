/* AssistantAMU documentation site — the four behaviours the prose cannot carry
   on its own: retracting the two summaries, following the reading position,
   and copying a command.

   No dependency and no build step. Everything degrades to a usable page when
   the script does not run: the site summary is open, the page summary is
   absent rather than empty, previous/next is rendered at build time, and the
   heading anchors come from the Markdown toc extension. */

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

  /* --- Groups of the site summary --------------------------------------- */

  /* Each group of the tree folds as a whole. The build decides how it opens —
     the API reference folded, the short groups open — and the reader's last
     choice overrides that, in either direction, on the groups they are not
     currently reading. The group holding the current page stays open whatever
     was stored: its pages are the ones the reader is in. */
  function setUpGroups() {
    var groups = document.querySelectorAll(".sidebar .nav-group");
    Array.prototype.forEach.call(groups, function (group) {
      var toggle = group.querySelector(".group-toggle");
      if (!toggle) return;
      var key = "amu.group." + group.id;
      var inside = group.querySelector("a.current");
      var stored = recall(key);

      if (!inside && stored) {
        group.classList.toggle("closed", stored !== "open");
        toggle.setAttribute("aria-expanded", stored === "open" ? "true" : "false");
      }

      toggle.addEventListener("click", function () {
        var open = group.classList.contains("closed");
        group.classList.toggle("closed", !open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        remember(key, open ? "open" : "closed");
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

  setUpSidebar();
  setUpRubrics();
  setUpGroups();
  setUpPageSummary();
  setUpCopyButtons();
})();
