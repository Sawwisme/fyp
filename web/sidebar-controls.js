(() => {
    'use strict';

    let installed = false;

    function installSidebar() {
        if (installed) return;

        const sidebar = document.getElementById('shared-sidebar');
        const topbar = document.getElementById('shared-topbar');

        // Vet layout may populate these after fetching the profile.
        if (!sidebar?.children.length || !topbar?.children.length) {
            return;
        }

        installed = true;
        observer.disconnect();

        const mobile = window.matchMedia('(max-width: 760px)');
        const storageKey = 'vetdental_sidebar_closed';

        const button = document.createElement('button');
        button.id = 'shell-sidebar-toggle';
        button.type = 'button';
        button.setAttribute('aria-controls', 'shared-sidebar');

        const group = document.createElement('div');
        group.className = 'shell-title-group';

        // Preserve the existing portal title and account elements.
        const title = topbar.firstElementChild;

        topbar.prepend(group);
        group.appendChild(button);

        if (title) group.appendChild(title);

        const backdrop = document.createElement('button');
        backdrop.type = 'button';
        backdrop.className = 'shell-sidebar-backdrop';
        backdrop.setAttribute('aria-label', 'Close navigation');
        backdrop.tabIndex = -1;
        document.body.appendChild(backdrop);

        function savedClosed() {
            try {
                return localStorage.getItem(storageKey) === 'true';
            } catch (_) {
                return false;
            }
        }

        function setClosed(closed, remember = true) {
            document.body.classList.toggle(
                'shell-sidebar-closed',
                closed
            );

            sidebar.inert = closed;

            button.textContent = closed ? '☰' : '‹';
            button.setAttribute('aria-expanded', String(!closed));
            button.setAttribute(
                'aria-label',
                closed ? 'Open navigation' : 'Close navigation'
            );
            button.title =
                closed ? 'Open navigation' : 'Close navigation';

            backdrop.disabled = closed || !mobile.matches;

            if (remember && !mobile.matches) {
                try {
                    localStorage.setItem(storageKey, String(closed));
                } catch (_) {
                    // Navigation still works if storage is unavailable.
                }
            }
        }

        button.addEventListener('click', () => {
            setClosed(
                !document.body.classList.contains(
                    'shell-sidebar-closed'
                )
            );
        });

        backdrop.addEventListener('click', () => {
            setClosed(true, false);
            button.focus();
        });

        document.addEventListener('keydown', event => {
            if (
                event.key === 'Escape' &&
                !document.body.classList.contains(
                    'shell-sidebar-closed'
                ) &&
                !document.querySelector('dialog[open]')
            ) {
                setClosed(true);
                button.focus();
            }
        });

        sidebar.addEventListener('click', event => {
            if (mobile.matches && event.target.closest('a')) {
                setClosed(true, false);
            }
        });

        mobile.addEventListener('change', () => {
            setClosed(
                mobile.matches ? true : savedClosed(),
                false
            );
        });

        setClosed(mobile.matches || savedClosed(), false);

        requestAnimationFrame(() => {
            document.body.classList.add('shell-motion-ready');
        });
    }

    const observer = new MutationObserver(installSidebar);

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    installSidebar();
})();