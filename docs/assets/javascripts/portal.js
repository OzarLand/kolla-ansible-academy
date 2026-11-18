/*
 * Kolla Ansible Day 2 portal: progressive enhancement only.
 *
 *  1. Search triggers: any [data-portal-search] button opens the theme's
 *     search dialog.
 *  2. assets/data/updates.json (written by tools/site/prebuild.py from the
 *     Git history) feeds the "Last updated" line of each page and the
 *     "Recently updated" list of the home page (at most N pages, whole days
 *     only; N is the value of data-portal-recent).
 *
 * Nothing here carries content. When JavaScript is off or updates.json is
 * missing, the page simply shows less: both elements stay hidden or keep
 * their fallback.
 */
(function () {
  "use strict";

  /* ---------------------------------------------------------- 1. Search */

  function initSearchTriggers() {
    var search = document.querySelector('[data-md-component="search"]');
    // The theme hides its search when the index cannot be used.
    if (!search || search.hidden) return;
    var opener = search.querySelector("button") || search;
    document.querySelectorAll("[data-portal-search]").forEach(function (trigger) {
      trigger.hidden = false;
      trigger.addEventListener("click", function () {
        opener.click();
      });
    });
  }

  /* ----------------------------------------------------- 2. updates.json */

  var ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

  function timeElement(date) {
    var time = document.createElement("time");
    time.dateTime = date;
    time.textContent = date;
    return time;
  }

  function fillLastUpdated(pages) {
    var line = document.querySelector("[data-portal-updated]");
    if (!line) return;
    var url = line.getAttribute("data-portal-updated");
    var page = pages.find(function (entry) {
      return entry.url === url;
    });
    if (!page || !ISO_DATE.test(page.updated)) return;
    line.textContent = "Last updated ";
    line.appendChild(timeElement(page.updated));
    line.hidden = false;
  }

  // Most recently updated pages, whole days only: pages that share a date
  // cannot be ranked, so a day is listed in full or not at all. Right after
  // a commit that touches every page there is no list, only the page's own
  // fallback sentence.
  function mostRecent(pages, limit) {
    var dated = pages
      .filter(function (entry) {
        return entry.url !== "" && entry.title && ISO_DATE.test(entry.updated);
      })
      .sort(function (a, b) {
        return a.updated < b.updated ? 1 : a.updated > b.updated ? -1 : a.title.localeCompare(b.title);
      });
    var recent = [];
    for (var start = 0; start < dated.length; ) {
      var end = start;
      while (end < dated.length && dated[end].updated === dated[start].updated) end++;
      if (end > limit) break;
      recent = dated.slice(0, end);
      start = end;
    }
    return recent;
  }

  function fillRecentlyUpdated(pages, base) {
    var target = document.querySelector("[data-portal-recent]");
    if (!target) return;
    var limit = parseInt(target.getAttribute("data-portal-recent"), 10) || 8;
    var recent = mostRecent(pages, limit);
    if (!recent.length) return;

    var list = document.createElement("ul");
    list.className = "portal-recent";
    recent.forEach(function (entry) {
      var item = document.createElement("li");
      var link = document.createElement("a");
      link.href = new URL(entry.url, base).href;
      link.textContent = entry.title;
      item.appendChild(link);
      item.appendChild(timeElement(entry.updated));
      list.appendChild(item);
    });
    // The fallback sentence of the page (link to the commit history) stays below.
    target.prepend(list);
  }

  function initUpdates() {
    var meta = document.querySelector('meta[name="portal-updates"]');
    if (!meta || !window.fetch) return;
    if (!document.querySelector("[data-portal-updated], [data-portal-recent]")) return;
    var source = new URL(meta.content, document.baseURI);
    // updates.json lives in <site>/assets/data/: the site root is two levels up.
    var base = new URL("../../", source);
    fetch(source)
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.pages)) return;
        fillLastUpdated(data.pages);
        fillRecentlyUpdated(data.pages, base);
      })
      .catch(function () {
        /* No file, no network, invalid JSON: stay silent. */
      });
  }

  function init() {
    initSearchTriggers();
    initUpdates();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
