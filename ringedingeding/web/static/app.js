// The selected product changes the creation form immediately. The server also
// renders the initial state, so following either cockpit link works without
// JavaScript; this only keeps a manual radio-button change in sync.
(function () {
  "use strict";

  var form = document.querySelector("[data-chain-form]");
  if (!form) return;

  var radios = form.querySelectorAll('input[name="mode"]');
  var panels = form.querySelectorAll("[data-mode-panel]");
  var scheduleOnly = form.querySelector("[data-schedule-only]");

  function showMode(mode) {
    var selected = mode === "roundtable" ? "roundtable" : "schedule";
    form.dataset.mode = selected;
    panels.forEach(function (panel) {
      panel.hidden = panel.dataset.modePanel !== selected;
    });
    if (scheduleOnly) {
      scheduleOnly.hidden = selected === "roundtable";
      scheduleOnly.disabled = selected === "roundtable";
    }
  }

  radios.forEach(function (radio) {
    radio.addEventListener("change", function () {
      if (radio.checked) showMode(radio.value);
    });
    if (radio.checked) showMode(radio.value);
  });
})();

// The live view, and nothing else.
//
// This file exists so an open page keeps up with a round that is running. It is
// deliberately not load-bearing: the server renders the same panel at
// data-panel, and the page carries a meta refresh while a round is in flight,
// so somebody with JavaScript switched off sees exactly the same thing a few
// seconds later. Nothing here drives a call — the calls run in the server.

(function () {
  "use strict";

  var panel = document.getElementById("live-panel");
  if (!panel || typeof EventSource === "undefined") return;

  var streamUrl = panel.dataset.stream;
  if (!streamUrl) return;

  var source = new EventSource(streamUrl);

  source.addEventListener("panel", function (event) {
    try {
      var payload = JSON.parse(event.data);
      if (payload && typeof payload.html === "string") {
        panel.innerHTML = payload.html;
      }
    } catch (error) {
      // A malformed frame is not worth breaking the page over — the meta
      // refresh will bring the correct state along shortly.
    }
  });

  source.addEventListener("done", function () {
    // Close it ourselves. Letting the browser reconnect to a finished round
    // would reopen the stream every few seconds for nothing.
    source.close();
    // Take the meta refresh out of the way so the finished page stays still.
    var refresh = document.querySelector('meta[http-equiv="refresh"]');
    if (refresh && refresh.parentNode) refresh.parentNode.removeChild(refresh);
  });

  source.onerror = function () {
    if (source.readyState === EventSource.CLOSED) return;
    // Leave reconnection to the browser; the panel is whole-state, so a missed
    // frame costs nothing.
  };
})();
