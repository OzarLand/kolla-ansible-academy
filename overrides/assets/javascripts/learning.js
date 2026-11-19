/*
 * Learning journey: the reader's progress (pages marked as read), kept in
 * this browser only (localStorage, one key per release). Nothing is sent.
 *
 * - [data-oz-read-toggle]: the "Mark this page as read" box at the end of a
 *   page of the journey (overrides/main.html).
 * - [data-oz-progress]: the progress block of the journey page
 *   (overrides/journey.html), with [data-oz-page] items and [data-oz-stage]
 *   stages.
 *
 * Without JavaScript or without storage, the boxes and the progress stay
 * hidden and the pages read as before.
 */
(function () {
  "use strict";

  var PREFIX = "ozarland-day2:read:";

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
    box.addEventListener("change", function () {
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
      document.querySelectorAll("[data-oz-stage]").forEach(function (stage) {
        var items = stage.querySelectorAll("[data-oz-page]");
        var doneItems = stage.querySelectorAll("[data-oz-page].is-read");
        var complete = items.length > 0 && items.length === doneItems.length;
        stage.classList.toggle("is-complete", complete);
        var label = stage.querySelector("[data-oz-stage-done]");
        if (label) label.hidden = !complete;
      });
      var bar = block.querySelector("[role=progressbar]");
      bar.setAttribute("aria-valuenow", String(read));
      block.querySelector("[data-oz-progress-fill]").style.width = (total ? (100 * read) / total : 0) + "%";
      block.querySelector("[data-oz-progress-count]").textContent = String(read);
      block.querySelector("[data-oz-progress-message]").textContent = message(read, total);
      block.classList.toggle("is-complete", total > 0 && read >= total);
    }

    block.querySelector("[data-oz-reset]").addEventListener("click", function () {
      if (window.confirm("Forget the pages you marked as read in this release?")) {
        save(release, []);
        render();
      }
    });
    block.hidden = false;
    render();
  }

  function init() {
    document.querySelectorAll("[data-oz-read-toggle]").forEach(setupToggle);
    document.querySelectorAll("[data-oz-progress]").forEach(setupProgress);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
