/* The XMB wave: bands of offset sine curves drifting past each other. Hand
   written, because the console it is imitating is the whole point and a
   dependency would outlive its own CDN. */
(function () {
  var c = document.getElementById("wave"), x = c.getContext("2d");
  var still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var w, h, t = 0;

  function size() { w = c.width = innerWidth; h = c.height = innerHeight; }

  function band(mid, amp, freq, phase, lines, alpha) {
    for (var i = 0; i < lines; i++) {
      var lift = (i - lines / 2) * (amp * 0.13);
      x.beginPath();
      for (var px = 0; px <= w; px += 8) {
        var u = px / w;
        var y = mid + lift
              + Math.sin(u * freq + phase + i * 0.10) * amp
              + Math.sin(u * freq * 2.7 + phase * 1.6) * amp * 0.28;
        px ? x.lineTo(px, y) : x.moveTo(px, y);
      }
      x.strokeStyle = "rgba(158,214,255," +
        (alpha * (1 - Math.abs(i - lines / 2) / lines)) + ")";
      x.lineWidth = 1;
      x.stroke();
    }
  }

  function frame() {
    x.clearRect(0, 0, w, h);
    band(h * 0.42, h * 0.075, 4.2, t, 16, 0.30);
    band(h * 0.56, h * 0.055, 5.6, t * 0.7 + 2, 12, 0.20);
    band(h * 0.70, h * 0.045, 3.4, -t * 0.5, 10, 0.13);
    if (!still) { t += 0.004; requestAnimationFrame(frame); }
  }

  addEventListener("resize", function () { size(); if (still) frame(); });
  size();
  frame();
})();
