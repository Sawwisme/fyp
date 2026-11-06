(() => {
    const isStaffPage =
        window.location.pathname.endsWith('/user_management.html');

    const isSchedulePage =
        window.location.pathname.endsWith('/schedules.html');
    const isProductPage =
        window.location.pathname.endsWith('/products.html');
    const sidebar = document.getElementById('shared-sidebar');
    const topbar = document.getElementById('shared-topbar');
    const isOrderPage =
        window.location.pathname.endsWith('/orders.html');
    const isBillingPage =
        window.location.pathname.endsWith('/billing.html');

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

            <a class="nav-item" href="/web/admin/schedules.html"
            data-page="schedules">
                Appointment Schedule
            </a>

            <a class="nav-item" href="/web/admin/products.html"
            data-page="products">
                Products
            </a>

            <a class="nav-item"
               href="/web/admin/orders.html"
               data-page="orders">
                Orders
            </a>

            <a class="nav-item"
            href="/web/admin/billing.html"
            data-page="billing">
                Consultation Billing
            </a>

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
        const activePage = isBillingPage
            ? 'billing'
            : isOrderPage
                ? 'orders'
                : isProductPage
                    ? 'products'
                    : isSchedulePage
                        ? 'schedules'
                        : isStaffPage
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

(() => {
    const script = document.createElement('script');
    script.src = '/web/notifications.js';
    document.head.appendChild(script);
})();