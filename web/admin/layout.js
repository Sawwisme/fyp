(() => {
    const isStaffPage =
        window.location.pathname.endsWith('/user_management.html');

    const sidebar = document.getElementById('shared-sidebar');
    const topbar = document.getElementById('shared-topbar');

    sidebar.innerHTML = `
        <a class="brand" href="/web/admin/">
            <span class="brand-icon" aria-hidden="true">✚</span>
            <span>
                VetDental
                <small>Clinical Management</small>
            </span>
        </a>

        <nav class="main-nav" aria-label="Clinic management">
            <a class="nav-item"
               href="/web/admin/#dashboard"
               data-page="dashboard"
               data-view="dashboard">
                Dashboard
            </a>

            <a class="nav-item"
               href="/web/admin/user_management.html"
               data-page="staff">
                User Management
            </a>

            <button class="nav-item" type="button" disabled>
                Appointment Schedule <small>Coming soon</small>
            </button>

            <button class="nav-item" type="button" disabled>
                Products <small>Coming soon</small>
            </button>

            <button class="nav-item" type="button" disabled>
                Orders <small>Coming soon</small>
            </button>

            <button class="nav-item" type="button" disabled>
                Financial <small>Coming soon</small>
            </button>

            <button class="nav-item" type="button" disabled>
                Reports <small>Coming soon</small>
            </button>
        </nav>

        <nav class="bottom-nav" aria-label="Account">
            <a class="nav-item"
               href="/web/admin/#profile"
               data-page="profile"
               data-view="profile">
                Profile
            </a>

            <button id="${isStaffPage ? 'staff-logout' : 'logout-button'}"
                    class="nav-item logout" type="button">
                Log out
            </button>
        </nav>
    `;

    topbar.innerHTML = `
        <span>Clinic Administrator Portal</span>

        <a class="account-link" href="/web/admin/#profile"
           aria-label="View your profile">
            <span id="${isStaffPage ? 'staff-admin-name' : 'topbar-name'}">
            </span>
            <span id="topbar-avatar" class="avatar small"
                  aria-hidden="true">✚</span>
        </a>
    `;

    function highlightNavigation() {
        const activePage = isStaffPage
            ? 'staff'
            : window.location.hash === '#profile'
                ? 'profile'
                : 'dashboard';

        sidebar.querySelectorAll('[data-page]').forEach(link => {
            const active = link.dataset.page === activePage;

            link.classList.toggle('active', active);

            if (active) {
                link.setAttribute('aria-current', 'page');
            } else {
                link.removeAttribute('aria-current');
            }
        });
    }

    highlightNavigation();
    window.addEventListener('hashchange', highlightNavigation);
})();