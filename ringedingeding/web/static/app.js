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
