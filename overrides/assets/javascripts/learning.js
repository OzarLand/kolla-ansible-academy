/*
 * Learning journey: the reader's progress (pages marked as read), kept in
 * this browser only (localStorage, one key per release). Nothing is sent.
 *
 * - [data-oz-read-toggle]: the "Mark this page as read" box at the end of a
 *   page of the journey (overrides/main.html).
 * - [data-oz-progress]: the progress block of the journey page
 *   (overrides/journey.html), with [data-oz-page] items, [data-oz-stage]
 *   stages, [data-oz-seal] seals (lit when a stage is complete) and
 *   [data-oz-complete], Lumo's message at the end of the journey.
 *
 * - [data-oz-quiz]: the "Check yourself" block of a page; the best score of
 *   each page is kept under its own key (QUIZ_PREFIX).
 * - [data-oz-resume]: "Continue where you left off" (partials/resume.html).
 *
 * Without JavaScript or without storage, the boxes and the progress stay
 * hidden and the pages read as before.
 */
(function () {
  "use strict";

  var PREFIX = "kolla-ansible-academy:read:";
  var QUIZ_PREFIX = "kolla-ansible-academy:quiz:";
  var CHALLENGE_PREFIX = "kolla-ansible-academy:challenge:";

  /* Best quiz score of each page: {"<page url>": {"score": n, "total": m}}. */
  function loadScores(release, prefix) {
    try {
      var data = JSON.parse(window.localStorage.getItem((prefix || QUIZ_PREFIX) + release) || "{}");
      return data && typeof data === "object" && !Array.isArray(data) ? data : {};
    } catch (error) {
      return null;
    }
  }

  function saveScores(release, scores, prefix) {
    try {
      window.localStorage.setItem((prefix || QUIZ_PREFIX) + release, JSON.stringify(scores));
      return true;
    } catch (error) {
      return false;
    }
  }

  function load(release) {
    try {
      var data = JSON.parse(window.localStorage.getItem(PREFIX + release) || "[]");
      return Array.isArray(data) ? data : [];
    } catch (error) {
      return null;
    }
  }

  function save(release, pages) {
    try {
      window.localStorage.setItem(PREFIX + release, JSON.stringify(pages));
      return true;
    } catch (error) {
      return false;
    }
  }

  function setupToggle(box) {
    var release = box.getAttribute("data-oz-release");
    var page = box.getAttribute("data-oz-page");
    var pages = load(release);
    if (pages === null) return;
    box.checked = pages.indexOf(page) !== -1;
    box.closest("[data-oz-read]").hidden = false;
    var cheer = document.querySelector("[data-oz-cheer]");
    var line = document.querySelector("[data-oz-lumo-line]");
    box.addEventListener("change", function () {
      if (cheer) cheer.hidden = !box.checked;
      if (line) line.hidden = box.checked;
      var current = load(release) || [];
      var at = current.indexOf(page);
      if (box.checked && at === -1) current.push(page);
      if (!box.checked && at !== -1) current.splice(at, 1);
      save(release, current);
    });
  }

  function message(read, total) {
    if (read === 0) return "Start with stage 1 below.";
    if (read >= total) return "Journey complete: well done! Keep the reference pages close when you work.";
    if (read / total >= 0.5) return "More than halfway there: keep going.";
    return "Good start: one page at a time.";
  }

  function setSeal(id, complete, started) {
    var seal = document.querySelector('[data-oz-seal="' + id + '"]');
    if (!seal) return;
    seal.classList.toggle("is-complete", complete);
    seal.classList.toggle("is-progress", !complete && !!started);
    var state = seal.querySelector("[data-oz-seal-state]");
    if (state) state.textContent = complete ? "completed" : started ? "in progress" : "not started";
  }

  function setupProgress(block) {
    var release = block.getAttribute("data-oz-release");
    var total = parseInt(block.getAttribute("data-oz-total"), 10) || 0;
    if (load(release) === null) return;

    function render() {
      var pages = load(release) || [];
      var read = 0;
      document.querySelectorAll("[data-oz-page]").forEach(function (item) {
        var done = pages.indexOf(item.getAttribute("data-oz-page")) !== -1;
        if (done) read += 1;
        item.classList.toggle("is-read", done);
        var mark = item.querySelector("[data-oz-read-mark]");
        if (mark) mark.hidden = !done;
      });
      var challenges = loadScores(release, CHALLENGE_PREFIX) || {};
      var stagesDone = 0;
      var stagesAll = 0;
      var pagesWaiting = 0;
      document.querySelectorAll("[data-oz-stage]").forEach(function (stage) {
        var id = stage.id.replace(/^stage-/, "");
        var items = stage.querySelectorAll("[data-oz-page]");
        var doneItems = stage.querySelectorAll("[data-oz-page].is-read");
        var pagesRead = items.length > 0 && items.length === doneItems.length;
        /* A stage with a final challenge needs it passed too. */
        var quiz = stage.querySelector('[data-oz-quiz-kind="challenge"]');
        var best = challenges[id];
        var passed = !quiz || !!(best && best.score >= parseInt(quiz.getAttribute("data-oz-pass"), 10));
        var complete = pagesRead && passed;
        stagesAll += 1;
        if (complete) stagesDone += 1;
        if (pagesRead && !passed) pagesWaiting += 1;
        stage.classList.toggle("is-complete", complete);
        var label = stage.querySelector("[data-oz-stage-done]");
        if (label) label.hidden = !complete;
        var state = stage.querySelector("[data-oz-challenge-state]");
        if (state && quiz) {
          var need = quiz.getAttribute("data-oz-pass");
          state.hidden = false;
          state.classList.toggle("is-passed", passed);
          state.textContent = passed
            ? "Final challenge passed (" + best.score + " of " + best.total + ")" +
              (pagesRead ? ": seal earned." : ". Mark the pages of the stage as read to earn the seal.")
            : best
              ? "Final challenge: best score " + best.score + " of " + best.total + ", " + need + " needed for the seal."
              : "Final challenge: not taken yet (" + need + " right answers needed for the seal).";
        }
        setSeal(id, complete, doneItems.length > 0 || !!best);
      });
      var scores = loadScores(release) || {};
      var taken = 0;
      var perfect = 0;
      document.querySelectorAll("[data-oz-page]").forEach(function (item) {
        var mark = item.querySelector("[data-oz-quiz-mark]");
        var best = scores[item.getAttribute("data-oz-page")];
        if (!mark) return;
        mark.hidden = !best;
        mark.classList.remove("is-perfect");
        if (!best) return;
        taken += 1;
        if (best.score >= best.total) perfect += 1;
        mark.classList.toggle("is-perfect", best.score >= best.total);
        mark.textContent = " quiz " + best.score + "/" + best.total;
      });
      var summary = block.querySelector("[data-oz-quiz-summary]");
      if (summary) {
        summary.hidden = taken === 0;
        summary.textContent = taken === 0 ? "" : "Quizzes: " + taken + " taken, " + perfect +
          " with every answer right on the first try.";
      }
      var finished = total > 0 && read >= total && stagesDone === stagesAll;
      setSeal("journey", finished, read > 0);
      var done = block.querySelector("[data-oz-complete]");
      if (done) done.hidden = !finished;
      var bar = block.querySelector("[role=progressbar]");
      bar.setAttribute("aria-valuenow", String(read));
      block.querySelector("[data-oz-progress-fill]").style.width = (total ? (100 * read) / total : 0) + "%";
      block.querySelector("[data-oz-progress-count]").textContent = String(read);
      block.querySelector("[data-oz-progress-message]").textContent = !finished && pagesWaiting
        ? (read >= total ? "Every page is read: pass" : "Pass") + " the final challenge of " +
          (pagesWaiting === 1 ? "a stage whose pages are all read" : pagesWaiting + " stages whose pages are all read") +
          " to earn its seal."
        : message(read, total);
      block.classList.toggle("is-complete", finished);
    }

    block.querySelector("[data-oz-reset]").addEventListener("click", function () {
      if (window.confirm("Forget the pages you marked as read and your quiz scores in this release?")) {
        save(release, []);
        saveScores(release, {});
        saveScores(release, {}, CHALLENGE_PREFIX);
        render();
        document.querySelectorAll("[data-oz-resume]").forEach(setupResume);
      }
    });
    document.addEventListener("oz:progress", render);
    block.hidden = false;
    render();
  }

  /* ---------------------------------------------------- definitions on hover
   * <meta name="portal-glossary"> names assets/data/glossary.json of the
   * release (tools/site/glossary.py). The first occurrence of each term in the
   * page becomes a button; hovering, focusing or clicking it shows the meaning
   * from the glossary, with a link to the section that defines it. */

  var SKIP = "a, h1, h2, h3, h4, h5, h6, pre, button, label, legend, summary, script, style, " +
    ".admonition-title, .portal-impact, .oz-pagebar, .oz-step-end, .oz-lumo, .oz-quiz, .oz-scenarios, .oz-remember, .md-source-file, " +
    ".md-content__button, .oz-term, .oz-term-pop, .ev, .md-tags, .portal-updated";

  function escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function setupGlossary(meta) {
    var url = meta.getAttribute("content");
    var base = url.replace(/assets\/data\/glossary\.json$/, "");
    var root = document.querySelector(".md-content .md-typeset");
    if (!root || !window.fetch) return;
    window.fetch(url).then(function (response) {
      return response.ok ? response.json() : null;
    }).then(function (data) {
      if (data && Array.isArray(data.terms)) decorate(root, data, base);
    }).catch(function () { /* no definitions: the page reads as before */ });
  }

  function decorate(root, data, base) {
    var byCode = {};
    var words = [];
    data.terms.forEach(function (term, index) {
      term.keys.forEach(function (key) { byCode[key] = index; });
      (term.words || []).forEach(function (word) { words.push({ word: word, index: index }); });
    });
    words.sort(function (a, b) { return b.word.length - a.word.length; });
    var pattern = words.length ? new RegExp("(^|[^\\w-])(" + words.map(function (w) {
      return escapeRegExp(w.word);
    }).join("|") + ")(s?)(?![\\w-])", "i") : null;
    var used = {};
    var targets = [];

    var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        if (node.nodeType === 1) {
          if (node.matches(SKIP)) return NodeFilter.FILTER_REJECT;
          if (node.tagName === "CODE") return NodeFilter.FILTER_ACCEPT;
          return NodeFilter.FILTER_SKIP;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var node;
    while ((node = walker.nextNode())) {
      if (node.nodeType === 1) {
        var index = byCode[node.textContent.trim()];
        if (index !== undefined && !used[index]) {
          used[index] = true;
          targets.push({ node: node, index: index });
        }
        continue;
      }
      if (!pattern || (node.parentNode && node.parentNode.closest("code"))) continue;
      var match = pattern.exec(node.nodeValue);
      if (!match) continue;
      var word = match[2].toLowerCase();
      var entry = words.filter(function (w) { return w.word.toLowerCase() === word; })[0];
      if (!entry || used[entry.index]) continue;
      used[entry.index] = true;
      var start = match.index + match[1].length;
      var rest = node.splitText(start);
      rest.splitText(match[2].length + match[3].length);
      targets.push({ node: rest, index: entry.index });
      walker.currentNode = rest;
    }
    if (!targets.length) return;

    var pop = document.createElement("div");
    pop.className = "oz-term-pop";
    pop.id = "oz-term-pop";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", "Definition");
    pop.hidden = true;
    document.body.appendChild(pop);
    var current = null;
    var pinned = false;
    var timer = null;

    function show(button, pin) {
      var term = data.terms[button.getAttribute("data-oz-term")];
      if (current && current !== button) current.setAttribute("aria-expanded", "false");
      current = button;
      pinned = pin || pinned;
      var more = term.more ? '<a href="' + base + term.more + '">' + escapeHtml(term.more_text || "Read more") + "</a> · " : "";
      pop.innerHTML = '<p class="oz-term-pop__term">' + escapeHtml(term.term) + "</p>" +
        '<p class="oz-term-pop__text">' + term.html + "</p>" +
        '<p class="oz-term-pop__more">Defined in: ' + more + '<a href="' + base + data.glossary + '">Glossary</a></p>';
      pop.hidden = false;
      button.setAttribute("aria-expanded", "true");
      var box = button.getBoundingClientRect();
      var width = Math.min(352, document.documentElement.clientWidth - 24);
      var left = Math.max(12, Math.min(box.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - width - 12));
      pop.style.width = width + "px";
      pop.style.left = left + "px";
      pop.style.top = (box.bottom + window.scrollY + 6) + "px";
    }

    function hide() {
      pop.hidden = true;
      pinned = false;
      if (current) current.setAttribute("aria-expanded", "false");
      current = null;
    }

    targets.forEach(function (target) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "oz-term";
      button.setAttribute("data-oz-term", String(target.index));
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-controls", "oz-term-pop");
      button.title = "Show the definition";
      target.node.parentNode.insertBefore(button, target.node);
      button.appendChild(target.node);
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        if (current === button && pinned) hide();
        else show(button, true);
      });
      button.addEventListener("mouseenter", function () {
        clearTimeout(timer);
        if (!pinned) show(button, false);
      });
      button.addEventListener("mouseleave", function () {
        if (!pinned) timer = setTimeout(hide, 250);
      });
      button.addEventListener("focus", function () { if (!pinned) show(button, false); });
      button.addEventListener("blur", function () { if (!pinned) timer = setTimeout(hide, 250); });
    });
    pop.addEventListener("mouseenter", function () { clearTimeout(timer); });
    pop.addEventListener("mouseleave", function () { if (!pinned) timer = setTimeout(hide, 250); });
    pop.addEventListener("focusin", function () { clearTimeout(timer); });
    document.addEventListener("click", function (event) {
      if (!pop.hidden && !pop.contains(event.target)) hide();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !pop.hidden) {
        var button = current;
        hide();
        if (button) button.focus();
      }
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* ------------------------------------------------------------------ quizzes
   * The "Check yourself" block of a page (front matter `quiz`, rendered by
   * overrides/main.html). Choosing an answer says whether it is right and
   * opens the explanation; without JavaScript the explanation stays one click
   * away (<details>). */

  function setupQuiz(section) {
    var release = section.getAttribute("data-oz-release");
    var page = section.getAttribute("data-oz-quiz-key") || section.getAttribute("data-oz-page");
    var challenge = section.getAttribute("data-oz-quiz-kind") === "challenge";
    var prefix = challenge ? CHALLENGE_PREFIX : QUIZ_PREFIX;
    var pass = parseInt(section.getAttribute("data-oz-pass"), 10);
    var questions = Array.prototype.slice.call(section.querySelectorAll("[data-oz-quiz-answer]"));
    var first = {};
    var scoreBox = section.querySelector("[data-oz-quiz-score]");
    var result = section.querySelector("[data-oz-quiz-result]");
    var bestLine = section.querySelector("[data-oz-quiz-best]");

    function stageRead() {
      var stage = section.closest("[data-oz-stage]");
      if (!stage) return false;
      return stage.querySelectorAll("[data-oz-page]").length === stage.querySelectorAll("[data-oz-page].is-read").length;
    }

    function showBest() {
      var scores = loadScores(release, prefix);
      var best = scores && scores[page];
      if (!bestLine) return;
      bestLine.hidden = !best;
      if (best) bestLine.textContent = " Your best score so far: " + best.score + " of " + best.total + ".";
    }

    function finish() {
      var right = 0;
      questions.forEach(function (question, index) {
        if (first[index]) right += 1;
      });
      var total = questions.length;
      var all = right === total;
      if (challenge) {
        var ok = right >= pass;
        result.innerHTML = "<strong>Lumo:</strong> " + right + " of " + total + " right on the first try. " + (ok
          ? (all ? "A perfect run! " : "Challenge passed! ") + (stageRead()
            ? "The seal of this stage is yours."
            : "Mark every page of the stage as read and its seal is yours.")
          : pass + " are needed to pass. Have another look at the pages linked in the answers, then try again.");
        all = ok;
      } else result.innerHTML = "<strong>Lumo:</strong> " + (all
        ? "all " + total + " right on the first try. You have the main ideas of this page" +
          (document.querySelector("[data-oz-read-toggle]") ? ": you can mark it as read below." : ".")
        : right + " of " + total + " right on the first try. Read the sections linked in the answers, then try again: " +
          "that is how it sticks.");
      section.querySelectorAll("[data-oz-quiz-pose]").forEach(function (img) {
        img.hidden = img.getAttribute("data-oz-quiz-pose") !== (all ? "right" : "again");
      });
      scoreBox.classList.toggle("is-perfect", all);
      scoreBox.hidden = false;
      var scores = loadScores(release, prefix);
      if (scores === null) return;
      var best = scores[page];
      if (!best || right > best.score || best.total !== total) {
        scores[page] = { score: right, total: total };
        saveScores(release, scores, prefix);
      }
      showBest();
      document.dispatchEvent(new CustomEvent("oz:progress"));
    }

    questions.forEach(function (question, index) {
      var answer = question.getAttribute("data-oz-quiz-answer");
      var feedback = question.querySelector("[data-oz-feedback]");
      var details = question.querySelector("details");
      question.querySelectorAll("input[type=radio]").forEach(function (input) {
        input.addEventListener("change", function () {
          var right = input.value === answer;
          question.classList.toggle("is-right", right);
          question.classList.toggle("is-wrong", !right);
          feedback.textContent = right ? "Right! " : "Not quite. Have another look: ";
          feedback.hidden = false;
          if (details) details.open = true;
          if (!(index in first)) {
            first[index] = right;
            if (Object.keys(first).length === questions.length) finish();
          }
        });
      });
    });

    var retry = section.querySelector("[data-oz-quiz-retry]");
    if (retry) {
      retry.addEventListener("click", function () {
        first = {};
        questions.forEach(function (question) {
          question.classList.remove("is-right", "is-wrong");
          question.querySelectorAll("input[type=radio]").forEach(function (input) { input.checked = false; });
          var feedback = question.querySelector("[data-oz-feedback]");
          feedback.hidden = true;
          feedback.textContent = "";
          var details = question.querySelector("details");
          if (details) details.open = false;
        });
        scoreBox.hidden = true;
        var input = questions.length && questions[0].querySelector("input[type=radio]");
        if (input) input.focus();
      });
    }
    showBest();
  }

  /* ------------------------------------------------------------ to remember
   * "Copy these notes": the takeaways of the page as plain text, with the
   * title and address of the page, for the reader's own notes. */

  function setupRemember(section) {
    var button = section.querySelector("[data-oz-remember-copy]");
    var status = section.querySelector("[data-oz-remember-status]");
    if (!button || !navigator.clipboard || !window.isSecureContext) return;
    button.parentNode.hidden = false;
    button.addEventListener("click", function () {
      var title = document.querySelector(".md-content h1");
      var name = title ? title.textContent.replace(/\u00b6/g, "").trim() : document.title;
      var lines = [name + " (" + location.href.split("#")[0] + ")"];
      section.querySelectorAll(".oz-remember__list li").forEach(function (item) {
        /* The evidence chips keep their label in brackets, as in the sources. */
        var copy = item.cloneNode(true);
        copy.querySelectorAll(".ev").forEach(function (chip) { chip.textContent = "[" + chip.textContent.trim() + "]"; });
        lines.push("- " + copy.textContent.replace(/\s+/g, " ").trim());
      });
      navigator.clipboard.writeText(lines.join("\n") + "\n").then(function () {
        status.textContent = "Copied.";
      }, function () {
        status.textContent = "Copy failed: select the list instead.";
      });
    });
  }

  /* ----------------------------------------------------- empty search help
   * The search dialog of the theme lives in an open shadow root, without
   * classes to rely on: its status (role=status) says "No results" and its
   * result list (role=listbox) is empty. Lumo's help, from
   * <template id="oz-empty-search">, goes right after that list. If the
   * theme changes its markup, nothing is shown and search works as before. */

  function setupEmptySearch(template) {
    function attach(root) {
      if (root.ozEmptySearch) return;
      root.ozEmptySearch = true;
      var help = null;
      function update() {
        var input = root.querySelector("input[role=combobox]");
        var status = root.querySelector("[role=status]");
        var list = root.querySelector("[role=listbox]");
        if (!input || !status || !list) return;
        var query = input.value.trim();
        var empty = query !== "" && list.children.length === 0 && /no results/i.test(status.textContent);
        if (empty && !help) {
          help = template.content.firstElementChild.cloneNode(true);
          list.parentNode.insertBefore(help, list.nextSibling);
        }
        if (!help) return;
        /* Change the DOM only when needed: the observer sees every change. */
        if (help.hidden === empty) help.hidden = !empty;
        var slot = help.querySelector("[data-oz-query]");
        if (empty && slot.textContent !== query) slot.textContent = query;
      }
      new MutationObserver(update).observe(root, { childList: true, subtree: true, characterData: true });
      root.addEventListener("input", update);
      update();
    }
    function scan() {
      Array.prototype.forEach.call(document.body.children, function (element) {
        if (element.shadowRoot) attach(element.shadowRoot);
      });
    }
    new MutationObserver(scan).observe(document.body, { childList: true });
    scan();
  }

  /* ---------------------------------------------------- what would you do?
   * A scenario of a page (front matter `scenarios`, overrides/main.html):
   * choosing an action shows its verdict and why, under that action. */

  function setupScenario(fieldset) {
    var feedbacks = fieldset.querySelectorAll("[data-oz-scenario-feedback]");
    fieldset.querySelectorAll("input[type=radio]").forEach(function (input) {
      input.addEventListener("change", function () {
        feedbacks.forEach(function (box) {
          box.hidden = box.getAttribute("data-oz-scenario-feedback") !== input.value;
        });
        var chosen = fieldset.querySelector('[data-oz-scenario-feedback="' + input.value + '"]');
        fieldset.classList.remove("is-best", "is-risky", "is-avoid");
        ["best", "risky", "avoid"].forEach(function (verdict) {
          if (chosen.classList.contains("oz-scenario__feedback--" + verdict)) fieldset.classList.add("is-" + verdict);
        });
      });
    });
  }

  /* ------------------------------------------------- continue where you left
   * Once at least one page is marked as read, the first page of the journey
   * not yet read; nothing when the journey is finished. */

  function setupResume(block) {
    var pages = load(block.getAttribute("data-oz-release"));
    var links = block.querySelectorAll("[data-oz-resume-page]");
    var next = null;
    links.forEach(function (link) {
      link.hidden = true;
      if (!next && pages && pages.indexOf(link.getAttribute("data-oz-resume-page")) === -1) next = link;
    });
    var show = !!(pages && pages.length && next);
    if (next) next.hidden = !show;
    block.hidden = !show;
    var start = block.parentNode.querySelector("[data-oz-resume-start]");
    if (start) start.classList.toggle("portal-cta--primary", !show);
  }

  function init() {
    document.querySelectorAll("[data-oz-read-toggle]").forEach(setupToggle);
    document.querySelectorAll("[data-oz-progress]").forEach(setupProgress);
    document.querySelectorAll('meta[name="portal-glossary"]').forEach(setupGlossary);
    document.querySelectorAll("[data-oz-quiz]").forEach(setupQuiz);
    document.querySelectorAll("[data-oz-resume]").forEach(setupResume);
    document.querySelectorAll("[data-oz-scenario]").forEach(setupScenario);
    document.querySelectorAll("[data-oz-remember]").forEach(setupRemember);
    var emptySearch = document.getElementById("oz-empty-search");
    if (emptySearch && "content" in emptySearch) setupEmptySearch(emptySearch);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
