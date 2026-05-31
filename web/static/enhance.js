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
    }

    /* ── Reveal obfuscated PayPal email (home overlay + donate page) ── */

    function setupEmailReveal() {
        var revealBtn = document.getElementById('donateReveal');
        var emailEl = document.getElementById('donateEmail');
        if (!revealBtn || !emailEl) return;

        revealBtn.addEventListener('click', function () {
            var a = atob(revealBtn.getAttribute('data-a'));
            var b = atob(revealBtn.getAttribute('data-b'));
            var c = atob(revealBtn.getAttribute('data-c'));
            emailEl.textContent = a + b + c;
            emailEl.classList.add('visible');
            revealBtn.style.display = 'none';
        });
    }

    /* ── Donate page: fuel gauge + PayPal button + live refresh ── */

    function setFuel(pct, dollars) {
        var fill = document.getElementById('fuelFill');
        if (fill) {
            fill.style.width = Math.max(0, Math.min(100, pct)) + '%';
            fill.classList.toggle('full', pct >= 100);
        }
        var pctEl = document.getElementById('fuelPct');
        if (pctEl && dollars === undefined) pctEl.textContent = pct + '%';
        var raisedEl = document.getElementById('fuelRaised');
        if (raisedEl && dollars !== undefined) raisedEl.textContent = '$' + dollars;
    }

    function countUp(el, target, fmt) {
        var duration = 1200, startTime = null;
        function step(ts) {
            if (!startTime) startTime = ts;
            var p = Math.min((ts - startTime) / duration, 1);
            var eased = 1 - Math.pow(1 - p, 3);
            el.textContent = fmt(Math.round(eased * target));
            if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    function loadScript(src, cb) {
        var s = document.createElement('script');
        s.src = src;
        s.onload = cb;
        s.onerror = function () {};
        document.head.appendChild(s);
    }

    function showDonateToast() {
        var t = document.getElementById('donateToast');
        if (!t) return;
        t.classList.add('show');
        setTimeout(function () { t.classList.remove('show'); }, 6000);
    }

    function refreshFuel() {
        if (!document.getElementById('fuelFill')) return;
        fetch('/api/donations/status', { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data) return;
                var pct = data.percent || 0;
                setFuel(pct);
                setFuel(pct, Math.floor((data.raised_cents || 0) / 100));
            })
            .catch(function () {});
    }

    function setupDonatePage() {
        var fill = document.getElementById('fuelFill');
        if (!fill) return; // not the donate page

        // Animate the gauge from empty on load (CSS transition + counters).
        var pct = parseInt(fill.getAttribute('data-percent'), 10) || 0;
        requestAnimationFrame(function () {
            fill.style.width = pct + '%';
            fill.classList.toggle('full', pct >= 100);
        });
        var pctEl = document.getElementById('fuelPct');
        if (pctEl) countUp(pctEl, parseInt(pctEl.getAttribute('data-pct-target'), 10) || 0,
            function (v) { return v + '%'; });
        var raisedEl = document.getElementById('fuelRaised');
        if (raisedEl) countUp(raisedEl, Math.floor((parseInt(raisedEl.getAttribute('data-cents'), 10) || 0) / 100),
            function (v) { return '$' + v; });

        // Render the hosted PayPal Donate button if one is configured. Without
        // it the page still works via the reveal-email fallback.
        var mount = document.getElementById('paypalDonate');
        var buttonId = mount && mount.getAttribute('data-button-id');
        if (!buttonId) return;
        loadScript('https://www.paypalobjects.com/donate/sdk/donate-sdk.js', function () {
            if (!window.PayPal || !window.PayPal.Donation) return;
            window.PayPal.Donation.Button({
                env: 'production',
                hosted_button_id: buttonId,
                onComplete: function () {
                    // Webhook updates the total server-side; re-read it shortly
                    // after so the gauge reflects the fresh donation.
                    showDonateToast();
                    setTimeout(refreshFuel, 4000);
                    setTimeout(refreshFuel, 12000);
                }
            }).render('#paypalDonate');
        });
    }

    /* ── Init ───────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        animateCounters();
        createDust();
        setupNav();
        setupFlash();
        setupDonate();
        setupEmailReveal();
        setupDonatePage();
    });
})();
