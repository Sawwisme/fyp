(() => {
    'use strict';
    const sidebar = document.getElementById('shared-sidebar');
    const topbar = document.getElementById('shared-topbar');
    if (!sidebar || !topbar) return;

    const key = 'vetdental.sidebar.closed';
    const mobile = window.matchMedia('(max-width: 760px)');
    let closed = mobile.matches;
    try {
        const saved = localStorage.getItem(key);
        if (saved === '1' || saved === '0') closed = saved === '1';
    } catch (_) { /* Navigation still works when storage is unavailable. */ }

    const backdrop = document.createElement('button');
    backdrop.type = 'button';
    backdrop.className = 'shell-sidebar-backdrop';
    backdrop.setAttribute('aria-label', 'Close navigation');
    backdrop.hidden = true;
    // Keep the backdrop inside the authenticated workspace so a hidden/loading
    // workspace cannot cover its retry or login controls on mobile.
    (sidebar.closest('.workspace') || document.body).appendChild(backdrop);

    function paint() {
        document.body.classList.toggle('shell-sidebar-closed', closed);
        sidebar.inert = closed;
        sidebar.setAttribute('aria-hidden', String(closed));
        const toggle = document.getElementById('shell-sidebar-toggle');
        if (toggle) {
            toggle.textContent = closed ? '☰' : '‹';
            toggle.setAttribute('aria-expanded', String(!closed));
            toggle.setAttribute('aria-label', closed ? 'Show navigation' : 'Hide navigation');
        }
        backdrop.hidden = closed || !mobile.matches;
    }

    function setClosed(next, moveFocus = false) {
        closed = next;
        paint();
        try { localStorage.setItem(key, closed ? '1' : '0'); } catch (_) { /* Optional preference. */ }
        if (moveFocus) {
            const target = document.getElementById(
                closed ? 'shell-sidebar-toggle' : 'shell-sidebar-close'
            );
            target?.focus();
        }
    }

    function installControls() {
        // Layout scripts rebuild these containers after profile loading.
        if (topbar.children.length && !topbar.querySelector('#shell-sidebar-toggle')) {
            const title = Array.from(topbar.children).find(node => node.tagName === 'SPAN');
            const group = document.createElement('div');
            group.className = 'shell-title-group';
            const toggle = document.createElement('button');
            toggle.id = 'shell-sidebar-toggle';
            toggle.type = 'button';
            toggle.setAttribute('aria-controls', 'shared-sidebar');
            toggle.addEventListener('click', () => setClosed(!closed, mobile.matches));
            group.appendChild(toggle);
            if (title) group.appendChild(title);
            topbar.prepend(group);
        }
        if (sidebar.children.length && !sidebar.querySelector('#shell-sidebar-close')) {
            const close = document.createElement('button');
            close.id = 'shell-sidebar-close';
            close.type = 'button';
            close.textContent = '×';
            close.setAttribute('aria-label', 'Close navigation');
            close.addEventListener('click', () => setClosed(true, true));
            sidebar.prepend(close);
        }
        paint();
    }

    backdrop.addEventListener('click', () => setClosed(true, true));
    sidebar.addEventListener('click', event => {
        if (mobile.matches && event.target.closest('a[href]')) setClosed(true, true);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !closed && !document.querySelector('dialog[open]')) {
            setClosed(true, true);
        }
    });
    mobile.addEventListener('change', paint);
    const observer = new MutationObserver(installControls);
    observer.observe(topbar, { childList: true });
    observer.observe(sidebar, { childList: true });
    window.addEventListener('pagehide', () => observer.disconnect(), { once: true });
    installControls();
})();
