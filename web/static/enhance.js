/* DirtForever — Progressive Enhancement */

(function () {
    'use strict';

    /* ── Animated counters ──────────────────────────── */

    function animateCounters() {
        var els = document.querySelectorAll('[data-count]');
        if (!els.length) return;

        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                var target = parseInt(el.getAttribute('data-count'), 10);
                if (isNaN(target)) return;
                observer.unobserve(el);

                var start = 0;
                var duration = 1200;
                var startTime = null;

                function step(ts) {
                    if (!startTime) startTime = ts;
                    var progress = Math.min((ts - startTime) / duration, 1);
                    var eased = 1 - Math.pow(1 - progress, 3);
                    el.textContent = Math.round(eased * target);
                    if (progress < 1) requestAnimationFrame(step);
                }

                requestAnimationFrame(step);
            });
        }, { threshold: 0.3 });

        els.forEach(function (el) { observer.observe(el); });
    }

    /* ── Dust particles (hero only) ─────────────────── */

    function createDust() {
        var container = document.getElementById('dust');
        if (!container) return;

        for (var i = 0; i < 30; i++) {
            var p = document.createElement('div');
            p.className = 'dust';
            p.style.left = Math.random() * 100 + '%';
            p.style.top = (60 + Math.random() * 40) + '%';
            p.style.width = (1 + Math.random() * 2) + 'px';
            p.style.height = p.style.width;
            p.style.animationDuration = (6 + Math.random() * 10) + 's';
            p.style.animationDelay = (Math.random() * 8) + 's';
            container.appendChild(p);
        }
    }

    /* ── Mobile nav toggle ──────────────────────────── */

    function setupNav() {
        var toggle = document.getElementById('navToggle');
        if (!toggle) return;
        var links = document.querySelector('.nav-links');
        if (!links) return;

        toggle.addEventListener('click', function () {
            links.classList.toggle('open');
        });

        document.addEventListener('click', function (e) {
            if (!toggle.contains(e.target) && !links.contains(e.target)) {
                links.classList.remove('open');
            }
        });
    }

    /* ── Auto-dismiss flash messages ────────────────── */

    function setupFlash() {
        var flashes = document.querySelectorAll('.flash');
        flashes.forEach(function (el) {
            setTimeout(function () {
                el.style.transition = 'opacity .4s, transform .4s';
                el.style.opacity = '0';
                el.style.transform = 'translateX(20px)';
                setTimeout(function () { el.remove(); }, 400);
            }, 5000);
        });
    }

    /* ── Donate panel ──────────────────────────────── */

    function setupDonate() {
        var overlay = document.getElementById('donateOverlay');
        if (!overlay) return;
        var openBtn = document.getElementById('donateOpen');
        var closeBtn = document.getElementById('donateClose');
        var revealBtn = document.getElementById('donateReveal');
        var emailEl = document.getElementById('donateEmail');

        function open() { overlay.classList.add('open'); }
        function close() { overlay.classList.remove('open'); }

        if (openBtn) openBtn.addEventListener('click', open);
        if (closeBtn) closeBtn.addEventListener('click', close);

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) close();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') close();
        });

        if (revealBtn && emailEl) {
            revealBtn.addEventListener('click', function () {
                var a = atob(revealBtn.getAttribute('data-a'));
                var b = atob(revealBtn.getAttribute('data-b'));
                var c = atob(revealBtn.getAttribute('data-c'));
                emailEl.textContent = a + b + c;
                emailEl.classList.add('visible');
                revealBtn.style.display = 'none';
            });
        }
    }

    /* ── Init ───────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        animateCounters();
        createDust();
        setupNav();
        setupFlash();
        setupDonate();
    });
})();
