/* ============================================================
   Quantlerning · 共享交互 (轻量，无依赖)
   主题切换 / 移动抽屉 / Toast / 标签页 — 所有页面共用
   ============================================================ */
(function () {
  'use strict';
  var KEY = 'ql:theme';
  var root = document.documentElement;

  /* ---- 主题：用户选择 > 系统偏好 ---- */
  function applyInitial() {
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) {}
    if (stored === 'dark' || stored === 'light') {
      root.setAttribute('data-theme', stored);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      root.setAttribute('data-theme', 'dark');
    }
  }
  function syncToggle() {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (el) {
      el.setAttribute('aria-pressed', root.getAttribute('data-theme') === 'dark' ? 'true' : 'false');
    });
  }
  function toggleTheme() {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem(KEY, next); } catch (e) {}
    syncToggle();
  }
  document.addEventListener('DOMContentLoaded', function () {
    applyInitial();
    syncToggle();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (el) {
      el.addEventListener('click', toggleTheme);
    });
  });

  /* ---- 移动端侧边栏抽屉 ---- */
  function openDrawer(s) { s.classList.add('open'); var sc = document.querySelector('.scrim'); if (sc) sc.classList.add('show'); }
  function closeDrawer(s) { s.classList.remove('open'); var sc = document.querySelector('.scrim'); if (sc) sc.classList.remove('show'); }
  document.addEventListener('DOMContentLoaded', function () {
    var sb = document.querySelector('.sidebar');
    if (!sb) return;
    var menu = document.querySelector('[data-menu]');
    if (menu) menu.addEventListener('click', function () { openDrawer(sb); });
    var sc = document.querySelector('.scrim');
    if (sc) sc.addEventListener('click', function () { closeDrawer(sb); });
    sb.querySelectorAll('.nav-item').forEach(function (n) {
      n.addEventListener('click', function () { if (window.innerWidth <= 900) closeDrawer(sb); });
    });
  });

  /* ---- Toast ---- */
  window.QL = window.QL || {};
  window.QL.toast = function (msg, kind) {
    var wrap = document.querySelector('.toast-wrap');
    if (!wrap) { wrap = document.createElement('div'); wrap.className = 'toast-wrap'; document.body.appendChild(wrap); }
    var t = document.createElement('div');
    t.className = 'toast';
    var icon = kind === 'ok'
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>';
    t.innerHTML = icon + '<span>' + msg + '</span>';
    wrap.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transform = 'translateY(12px)'; setTimeout(function () { t.remove(); }, 240); }, 2600);
  };

  /* ---- 标签页（同组互斥）---- */
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-tabs]').forEach(function (group) {
      var tabs = group.querySelectorAll('.tab');
      tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
          tabs.forEach(function (t) { t.classList.remove('active'); });
          tab.classList.add('active');
          var target = tab.getAttribute('data-tab');
          group.parentElement.querySelectorAll('[data-panel]').forEach(function (p) {
            p.hidden = p.getAttribute('data-panel') !== target;
          });
        });
      });
    });
  });
})();
