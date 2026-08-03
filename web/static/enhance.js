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

    /* ── Create-event form: cap stages to what the game can deliver ── */

    function setupEventForm() {
        var loc = document.getElementById('ev_location');
        var stages = document.getElementById('ev_num_stages');
        if (!loc || !stages) return;

        var caps;
        try { caps = JSON.parse(loc.getAttribute('data-stage-caps') || '{}'); }
        catch (e) { caps = {}; }

        var hint = document.getElementById('ev_stage_hint');

        function applyCap() {
            var cap = caps[loc.value];
            if (!cap) { stages.removeAttribute('max'); if (hint) hint.textContent = 'Select a location to set the stage limit.'; return; }
            stages.max = cap;
            stages.min = 1;
            var val = parseInt(stages.value, 10);
            if (isNaN(val) || val < 1) stages.value = 1;
            else if (val > cap) stages.value = cap;
            if (hint) hint.textContent = cap === 1
                ? 'This location has 1 stage.'
                : 'This location supports up to ' + cap + ' stages.';
        }

        loc.addEventListener('change', applyCap);
        applyCap();
    }

    /* ── Championship builder: routes, stage add/remove, live end ── */

    function setupChampionshipEditor() {
        var form = document.getElementById('championshipForm');
        if (!form) return;

        var routesByLocation = {};
        var stageCaps = {};
        try { routesByLocation = JSON.parse((document.getElementById('routesByLocation') || {}).textContent || '{}'); }
        catch (e) { routesByLocation = {}; }
        try { stageCaps = JSON.parse((document.getElementById('stageCaps') || {}).textContent || '{}'); }
        catch (e) { stageCaps = {}; }

        function section(el) { return el.closest('.champ-event'); }
        function evIndex(sec) { return sec.getAttribute('data-event-index'); }

        function populateRoutes(sec) {
            var loc = sec.querySelector('.champ-location').value;
            var routes = routesByLocation[loc] || [];
            sec.querySelectorAll('.champ-route').forEach(function (sel) {
                var current = sel.value;
                var html = '<option value="">' + (routes.length ? 'Select route...' : 'Select a location first') + '</option>';
                routes.forEach(function (r) {
                    var sel2 = String(r[0]) === String(current) ? ' selected' : '';
                    html += '<option value="' + r[0] + '"' + sel2 + '>' + r[1] + ' - ' + r[2].toFixed(2) + ' km</option>';
                });
                sel.innerHTML = html;
            });
            updateStageHint(sec);
        }

        function updateStageHint(sec) {
            var loc = sec.querySelector('.champ-location').value;
            var cap = stageCaps[loc];
            var rows = sec.querySelectorAll('.champ-stage-row').length;
            var hint = sec.querySelector('.champ-stage-hint');
            var addBtn = sec.querySelector('[data-cc="add-stage"]');
            if (!cap) {
                if (hint) hint.textContent = loc ? 'No verified routes for this location yet.' : '';
                if (addBtn) addBtn.disabled = false;
                return;
            }
            if (hint) hint.textContent = 'Supports up to ' + cap + ' stage' + (cap === 1 ? '' : 's') + '.';
            if (addBtn) addBtn.disabled = rows >= cap;
        }

        function renumberStages(sec) {
            var ei = evIndex(sec);
            sec.querySelectorAll('.champ-stage-row').forEach(function (row, j) {
                var num = row.querySelector('.champ-col-stage');
                if (num) num.textContent = (j < 9 ? '0' : '') + (j + 1);
                row.querySelectorAll('[name]').forEach(function (input) {
                    input.name = input.name.replace(/\[stages\]\[\d+\]/, '[stages][' + j + ']');
                });
                var del = row.querySelector('[data-cc="del-stage"]');
                if (del) del.value = 'delete_stage:' + ei + ':' + j;
            });
        }

        function addStage(sec) {
            var cap = stageCaps[sec.querySelector('.champ-location').value];
            var tbody = sec.querySelector('.champ-stage-table tbody');
            var rows = tbody.querySelectorAll('.champ-stage-row');
            if (cap && rows.length >= cap) { updateStageHint(sec); return; }
            var newIndex = rows.length;  // position of the row being added
            var clone = rows[rows.length - 1].cloneNode(true);
            clone.querySelectorAll('select').forEach(function (sel) { sel.selectedIndex = 0; });
            // Default service area: Medium every 2 stages (0, 2, 4, ...).
            var svc = clone.querySelector('select[name*="[service_area]"]');
            if (svc) svc.value = (newIndex % 2 === 0) ? 'Medium' : 'None';
            tbody.appendChild(clone);
            renumberStages(sec);
            populateRoutes(sec);
        }

        function removeStage(row) {
            var sec = section(row);
            if (sec.querySelectorAll('.champ-stage-row').length <= 1) return;
            row.remove();
            renumberStages(sec);
            updateStageHint(sec);
        }

        form.addEventListener('change', function (e) {
            if (e.target.classList && e.target.classList.contains('champ-location')) {
                populateRoutes(section(e.target));
            }
        });

        form.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-cc]');
            if (!btn) return;
            var cc = btn.getAttribute('data-cc');
            if (cc === 'add-stage') { e.preventDefault(); addStage(section(btn)); }
            else if (cc === 'del-stage') { e.preventDefault(); removeStage(e.target.closest('.champ-stage-row')); }
            // add-event / del-event fall through to a server round-trip.
        });

        form.querySelectorAll('.champ-event').forEach(updateStageHint);
    }

    // "YYYY-MM-DDTHH:MM" in the viewer's zone, which is how <input
    // type="datetime-local"> reads and writes its value.
    function toLocalInputValue(date) {
        function pad(n) { return (n < 10 ? '0' : '') + n; }
        return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' +
            pad(date.getDate()) + 'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
    }

    function setupChampionshipPreview() {
        var input = document.getElementById('start_at');
        if (!input) return;
        var endsOn = document.getElementById('endsOn');
        var epochField = document.getElementById('start_at_epoch');
        var zoneNote = document.getElementById('startAtZone');
        var totalSeconds = parseInt(input.getAttribute('data-total-seconds'), 10);

        // The server renders min/value in its own zone; rewrite both in the
        // viewer's zone so "now" reads as the clock on their wall.
        var nowEpoch = parseInt(input.getAttribute('data-now-epoch'), 10);
        var startEpoch = parseInt(input.getAttribute('data-start-epoch'), 10);
        if (!isNaN(nowEpoch)) input.min = toLocalInputValue(new Date(nowEpoch * 1000));
        if (!isNaN(startEpoch)) input.value = toLocalInputValue(new Date(startEpoch * 1000));

        if (zoneNote) {
            var zone = '';
            try {
                zone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
            } catch (err) { /* older browsers: fall back to the offset only */ }
            var offsetLabel = new Date().toLocaleTimeString(undefined, { timeZoneName: 'short' })
                .split(' ').pop();
            zoneNote.textContent = 'Times shown in your local timezone' +
                (zone ? ' (' + zone + ', ' + offsetLabel + ')' : ' (' + offsetLabel + ')') + '.';
        }

        function update() {
            var start = input.value ? new Date(input.value) : null;
            if (!start || isNaN(start.getTime())) return;
            // Post the chosen instant, not the wall-clock string, so the
            // server stores the moment the user actually meant.
            if (epochField) epochField.value = String(Math.floor(start.getTime() / 1000));
            if (!endsOn || isNaN(totalSeconds) || totalSeconds <= 0) return;
            var end = new Date(start.getTime() + totalSeconds * 1000);
            endsOn.textContent = end.toLocaleString(undefined, {
                weekday: 'short', day: '2-digit', month: 'short',
                year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
            });
        }
        input.addEventListener('change', update);
        input.addEventListener('input', update);
        update();
    }

    /* ── Init ───────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        animateCounters();
        createDust();
        setupNav();
        setupFlash();
        setupDonate();
        setupEventForm();
        setupChampionshipEditor();
        setupChampionshipPreview();
    });
})();
