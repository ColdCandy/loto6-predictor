/**
 * 360Hz級スムーズ — requestAnimationFrame 補間
 */
(function () {
  const SPRING = (t) => 1 - Math.pow(1 - t, 3);

  function animateValue(el, to, duration = 380, suffix = "") {
    if (!el) return;
    const from = parseFloat(String(el.dataset.value || el.textContent)) || 0;
    if (Math.abs(from - to) < 0.01) {
      el.textContent = `${to}${suffix}`;
      return;
    }
    const start = performance.now();
    el.classList.add("smooth-count");

    function frame(now) {
      const p = Math.min(1, (now - start) / duration);
      const v = from + (to - from) * SPRING(p);
      el.textContent = `${Math.round(v)}${suffix}`;
      if (p < 1) requestAnimationFrame(frame);
      else el.dataset.value = String(to);
    }
    requestAnimationFrame(frame);
  }

  function animateBars(container) {
    if (!container) return;
    container.querySelectorAll(".apple-bar-fill, .bar-fill").forEach((bar, i) => {
      const target = bar.style.width;
      bar.style.width = "0%";
      const delay = i * 2.78;
      setTimeout(() => {
        const start = performance.now();
        const targetNum = parseFloat(target) || 0;
        function frame(now) {
          const p = Math.min(1, (now - start) / 420);
          bar.style.width = `${targetNum * SPRING(p)}%`;
          if (p < 1) requestAnimationFrame(frame);
          else bar.style.width = target;
        }
        requestAnimationFrame(frame);
      }, delay);
    });
  }

  function enhanceBalls(root) {
    (root || document).querySelectorAll(".ball-row").forEach((row) => {
      row.querySelectorAll(".ball").forEach((ball, i) => {
        ball.style.animationDelay = `${i * 2.78}ms`;
      });
    });
  }

  function smoothTabSwitch(panel) {
    if (!panel) return;
    panel.style.opacity = "0";
    panel.style.transform = "translate3d(0, 6px, 0)";
    requestAnimationFrame(() => {
      panel.style.transition = "opacity 0.22s cubic-bezier(0.16,1,0.3,1), transform 0.22s cubic-bezier(0.16,1,0.3,1)";
      panel.style.opacity = "1";
      panel.style.transform = "translate3d(0, 0, 0)";
    });
  }

  window.UltraSmooth = {
    animateValue,
    animateBars,
    enhanceBalls,
    smoothTabSwitch,
  };

  document.addEventListener("DOMContentLoaded", () => {
    enhanceBalls(document);
  });
})();
