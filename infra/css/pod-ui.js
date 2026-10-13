/*
 * pod-ui.js — the few behaviours every identity page shares. Loaded as a
 * BLOCKING script in <head> (main.html.ejs and welcome/index.html), served at
 * /.well-known/css/scripts/pod-ui.js by a bind mount (docker-compose.yml).
 *
 * 1. Theme stamp, before first paint. A deferred or module script runs too
 *    late: a Dark choice would flash light on every page load. Same storage
 *    key and choices as solid-kit src/ui/theme.ts (ADR 008), so one stored
 *    choice means the same thing everywhere on this origin. Light is the
 *    default and is not stamped unless chosen, so prefers-contrast: more
 *    (skin.css) still applies while nothing is stored.
 * 2. The footer switch: three buttons, aria-pressed, wired by delegation.
 * 3. A page whose controls never arrive. CSS's page scripts start with
 *    `await fetchControls(...)` and nothing catches it: on a network error or
 *    a server error the submit stays disabled and the page says nothing. Put
 *    a sentence in #error instead.
 */
(function () {
  "use strict";

  var KEY = "solid-kit:theme";
  var THEMES = ["light", "dark", "contrast"];
  var root = document.documentElement;

  try {
    var stored = localStorage.getItem(KEY);
    if (THEMES.indexOf(stored) !== -1) root.setAttribute("data-theme", stored);
  } catch (e) { /* storage blocked: the default theme applies */ }

  function currentTheme() {
    var stamped = root.getAttribute("data-theme");
    if (THEMES.indexOf(stamped) !== -1) return stamped;
    return window.matchMedia && matchMedia("(prefers-contrast: more)").matches ? "contrast" : "light";
  }

  function showPressed(container) {
    var theme = currentTheme();
    var buttons = container.querySelectorAll("[data-theme-set]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", String(buttons[i].getAttribute("data-theme-set") === theme));
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var switches = document.querySelectorAll(".theme-switch");
    for (var i = 0; i < switches.length; i++) showPressed(switches[i]);
  });

  document.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("[data-theme-set]");
    if (!button) return;
    var theme = button.getAttribute("data-theme-set");
    if (THEMES.indexOf(theme) === -1) return;
    // An explicit Light is stamped too, so it beats the OS contrast setting.
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch (e) { /* applies to this view only */ }
    showPressed(button.closest(".theme-switch") || document);
  });

  window.addEventListener("unhandledrejection", function () {
    var error = document.getElementById("error");
    if (!error || error.textContent.trim()) return; // a server message is already shown: keep it
    error.textContent = "This page could not reach the server. Reload it; nothing you typed was sent.";
    error.classList.remove("hidden");
  });
})();
