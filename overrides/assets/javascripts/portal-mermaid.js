/*
 * Kolla-Ansible Academy portal: Mermaid set-up.
 *
 * Loaded (deferred) right after assets/vendor/mermaid/mermaid.min.js, and only
 * on pages that contain a diagram (see overrides/main.html). The theme bundle
 * renders the diagrams later, on DOMContentLoaded, with `window.mermaid`.
 *
 *  1. If the vendored library did not load, define a stub: the theme bundle
 *     would otherwise download Mermaid from a CDN. The diagram source then
 *     stays on the page as text.
 *  2. The theme styles flowcharts, sequence, class, state and ER diagrams for
 *     both colour schemes. Gantt and quadrant charts are not covered and keep
 *     Mermaid's light colours, unreadable on the dark scheme: the rules below
 *     give them the theme's own variables (--md-mermaid-*), so they follow
 *     the scheme toggle like the other diagrams.
 *  3. A diagram wider than the text column is not shrunk below 70 % of its
 *     natural size; its container scrolls sideways instead (portal.css).
 *     Gantt charts, which Mermaid sizes after the window, get a fixed width
 *     at which task labels fit inside their bars, and are never shrunk.
 *  4. Quadrant charts get a size and a margin at which the point labels are
 *     not cut off.
 */
(function () {
  "use strict";

  var mermaid = window.mermaid;

  if (!mermaid || typeof mermaid.initialize !== "function" || typeof mermaid.render !== "function") {
    window.mermaid = {
      initialize: function () {},
      render: function () {
        return Promise.reject(new Error("Mermaid is not available"));
      },
    };
    return;
  }

  var MIN_SCALE = 0.7;
  var GANTT = /aria-roledescription="gantt"/;
  var GANTT_WIDTH = 1200;
  // Mermaid draws a 500 x 500 chart with the plot against the edges: point
  // labels near an edge are cut off and sit on the quadrant titles. A chart
  // as wide as the text column, with a margin around the plot, shows them.
  var QUADRANT = {
    chartWidth: 860,
    chartHeight: 640,
    quadrantPadding: 40,
    titleFontSize: 16,
    quadrantLabelFontSize: 14,
    xAxisLabelFontSize: 14,
    yAxisLabelFontSize: 14,
    pointLabelFontSize: 12,
    pointRadius: 4,
  };

  var EXTRA_CSS = [
    /* Nodes coloured in the diagram source (`style X fill:#…`): the fills
       used in the corpus are light, so their text stays dark in both schemes. */
    '.node:has(> [style*="fill:"]) .nodeLabel{color:#1a2029}',

    /* Gantt */
    ".titleText,.sectionTitle,.taskText,.grid .tick text{font-family:var(--md-mermaid-font-family)}",
    ".titleText{fill:var(--md-mermaid-label-fg-color)}",
    ".sectionTitle0,.sectionTitle1,.sectionTitle2,.sectionTitle3{fill:var(--md-mermaid-label-fg-color)}",
    ".section0,.section2{fill:var(--md-mermaid-node-fg-color);opacity:.1}",
    ".section1,.section3{fill:var(--md-mermaid-node-fg-color);opacity:.03}",
    ".grid .tick line{stroke:var(--md-default-fg-color--lighter)}",
    ".grid .tick text{fill:var(--md-mermaid-label-fg-color);stroke:none}",
    ".task0,.task1,.task2,.task3{fill:var(--md-mermaid-node-bg-color);stroke:var(--md-mermaid-node-fg-color);stroke-width:1.5}",
    ".taskText0,.taskText1,.taskText2,.taskText3{fill:var(--md-mermaid-label-fg-color)}",
    ".taskTextOutsideLeft,.taskTextOutsideRight,.taskTextOutside0,.taskTextOutside1,.taskTextOutside2,.taskTextOutside3{fill:var(--md-mermaid-label-fg-color)}",
    ".today{display:none}",

    /* Quadrant chart */
    ".quadrant rect{fill:var(--md-mermaid-node-bg-color)}",
    ".quadrant:nth-child(2) rect,.quadrant:nth-child(4) rect{fill-opacity:.55}",
    ".quadrant:nth-child(3) rect{fill-opacity:.2}",
    ".quadrant text,.labels text,.title text,.data-point text{fill:var(--md-mermaid-label-fg-color);font-family:var(--md-mermaid-font-family)}",
    ".border line{stroke:var(--md-mermaid-node-fg-color)!important}",
    ".data-point circle{fill:var(--md-mermaid-node-fg-color);stroke:var(--md-mermaid-node-fg-color)}",
  ].join("");

  var initialize = mermaid.initialize.bind(mermaid);
  mermaid.initialize = function (config) {
    var merged = Object.assign({}, config);
    merged.themeCSS = (merged.themeCSS || "") + EXTRA_CSS;
    merged.gantt = Object.assign({ useWidth: GANTT_WIDTH, fontSize: 12, sectionFontSize: 12 }, merged.gantt);
    merged.quadrantChart = Object.assign({}, QUADRANT, merged.quadrantChart);
    return initialize(merged);
  };

  var render = mermaid.render.bind(mermaid);
  mermaid.render = function () {
    return render.apply(null, arguments).then(function (result) {
      // Root element: <svg … style="max-width: <natural width>px;" …>
      var root = result.svg.slice(0, result.svg.indexOf(">") + 1);
      var scale = GANTT.test(root) ? 1 : MIN_SCALE;
      var sized = root.replace(/(\bstyle="max-width:\s*)([\d.]+)px;/, function (match, head, width) {
        return head + width + "px; min-width: " + Math.round(width * scale) + "px;";
      });
      result.svg = sized + result.svg.slice(root.length);
      return result;
    });
  };
})();
