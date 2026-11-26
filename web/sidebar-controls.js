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

        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.className = 'shell-sidebar-close';
        closeButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="1.7"
                stroke-linecap="round" stroke-linejoin="round"
                aria-hidden="true">
                <rect x="3" y="4" width="18" height="16" rx="3"></rect>
                <path d="M9 4v16"></path>
                <path d="m16 9-3 3 3 3"></path>
            </svg>
        `;
        closeButton.setAttribute('aria-label', 'Close navigation');
        closeButton.setAttribute('aria-controls', 'shared-sidebar');

        const sidebarHeader = document.createElement('div');
        sidebarHeader.className = 'shell-sidebar-header';

        const brand = sidebar.querySelector('.brand');
        sidebar.prepend(sidebarHeader);

        if (brand) sidebarHeader.appendChild(brand);
        sidebarHeader.appendChild(closeButton);

        const icons = {
            dashboard: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
            schedules: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
            appointments: '<rect x="4" y="4" width="16" height="17" rx="2"/><path d="M8 3v3m8-3v3M8 11h8M8 15h5"/>',
            'ai-assessments': '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
            patients: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
            consultations: '<path d="M9 3H5v6a7 7 0 0 0 14 0V3h-4M12 16v2a3 3 0 0 0 6 0v-2"/><circle cx="18" cy="14" r="2"/>',
            'clinical-history': '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',
            followups: '<path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7m2-4v5l3 2"/>',
            reports: '<path d="M4 3v18h17M8 16v-5m5 5V7m5 9v-8"/>',
            staff: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2m4-15v6m-3-3h6"/>',
            products: '<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 5v9l9 5 9-5V8m-9 5v9"/>',
            orders: '<path d="M6 3h12l2 18H4L6 3Zm3 4a3 3 0 0 0 6 0"/>',
            billing: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6m-6 4h6m-6 4h3"/>',
            profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
            logout: '<path d="M9 21H4V3h5m6 5 5 4-5 4m-6-4h11"/>'
        };

        const navigation = sidebar.querySelector('.main-nav');

        if (navigation) {
            const heading = document.createElement('p');
            heading.className = 'shell-navigation-label';
            heading.textContent = 'WORKSPACE';
            navigation.before(heading);
        }

        sidebar.querySelectorAll('.nav-item').forEach(item => {
            const key = item.classList.contains('logout')
                ? 'logout'
                : item.dataset.vetPage || item.dataset.page;

            if (!icons[key]) return;

            const icon = document.createElement('span');
            icon.className = 'shell-nav-icon';
            icon.setAttribute('aria-hidden', 'true');
            icon.innerHTML = `
        <svg width="19" height="19" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round">
            ${icons[key]}
        </svg>
    `;

            item.prepend(icon);
        });

        closeButton.addEventListener('click', () => {
            setClosed(true);
            button.focus();
        });

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

            const focusWasInside = sidebar.contains(document.activeElement);

            if (closed && focusWasInside) {
                requestAnimationFrame(() => button.focus());
            }

            button.textContent = '☰';
            button.hidden = !closed;
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