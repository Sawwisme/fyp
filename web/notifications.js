(() => {
    const topbar = document.getElementById('shared-topbar');
    if (!topbar || document.getElementById('staff-notification-bell')) return;

    const stylesheet = document.createElement('link');
    stylesheet.rel = 'stylesheet';
    stylesheet.href = '/web/notifications.css';
    document.head.appendChild(stylesheet);

    const bell = document.createElement('button');
    bell.id = 'staff-notification-bell';
    bell.type = 'button';
    bell.className = 'notification-bell';
    bell.setAttribute('aria-label', 'Notifications');
    bell.setAttribute('aria-haspopup', 'dialog');
    bell.innerHTML = `
        <svg width="21" height="21" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="1.7"
             aria-hidden="true">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/>
            <path d="M10 21h4"/>
        </svg>
        <span class="notification-badge" hidden></span>
    `;

    const badge = bell.querySelector('.notification-badge');
    const account = topbar.querySelector('.account-link');
    const actions = document.createElement('div');
    actions.className = 'notification-topbar-actions';
    actions.appendChild(bell);
    if (account) actions.appendChild(account);
    topbar.appendChild(actions);

    const dialog = document.createElement('dialog');
    dialog.id = 'staff-notification-dialog';
    dialog.setAttribute('aria-labelledby', 'staff-notification-title');
    dialog.innerHTML = `
        <header class="notification-dialog-header">
            <div>
                <h2 id="staff-notification-title">Notifications</h2>
                <p>Updates about your clinic and appointments.</p>
            </div>
            <button type="button" class="notification-close"
                    aria-label="Close notifications">×</button>
        </header>
        <p class="notification-message" role="status"></p>
        <div class="notification-list"></div>
        <footer class="notification-pagination">
            <button type="button" data-direction="previous">Previous</button>
            <span></span>
            <button type="button" data-direction="next">Next</button>
        </footer>
    `;
    document.body.appendChild(dialog);

    const list = dialog.querySelector('.notification-list');
    const message = dialog.querySelector('.notification-message');
    const previous = dialog.querySelector('[data-direction="previous"]');
    const next = dialog.querySelector('[data-direction="next"]');
    const pageLabel = dialog.querySelector('.notification-pagination span');

    let page = 0;
    let loading = false;
    let countLoading = false;
    const pageSize = 10;

    async function request(path, method = 'GET') {
        const token = sessionStorage.getItem('vetdental_staff_token');
        if (!token) throw new Error('Please log in again.');

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);

        try {
            const response = await fetch(path, {
                method,
                headers: {
                    Accept: 'application/json',
                    Authorization: `Bearer ${token}`
                },
                credentials: 'omit',
                cache: 'no-store',
                signal: controller.signal
            });

            if (response.status === 401) {
                throw new Error('Your session expired. Please log in again.');
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Could not load notifications.'
                );
            }

            return data;
        } catch (error) {
            if (error.name === 'AbortError' || error instanceof TypeError) {
                throw new Error(
                    'Cannot reach the server. Close and reopen notifications to retry.'
                );
            }
            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    async function refreshCount() {
        if (countLoading) return;
        countLoading = true;

        try {
            const data = await request('/notifications/unread-count');
            const count = Number(data.unread_count);

            if (!Number.isInteger(count) || count < 0) {
                throw new Error('Invalid notification count.');
            }

            badge.hidden = count === 0;
            badge.textContent = count > 99 ? '99+' : String(count);
            bell.setAttribute(
                'aria-label',
                `Notifications, ${count} unread`
            );
            bell.title = `${count} unread notifications`;
        } catch (_) {
            badge.hidden = true;
            bell.title = 'Open notifications to check for updates';
        } finally {
            countLoading = false;
        }
    }

    function text(parent, tag, value, className = '') {
        const element = document.createElement(tag);
        element.textContent = value;
        element.className = className;
        parent.appendChild(element);
        return element;
    }

    function render(item) {
        const card = document.createElement('article');
        card.className = 'notification-card';
        card.classList.toggle('is-unread', !item.read_at);

        text(card, 'h3', item.title);
        text(card, 'p', item.message);
        text(
            card,
            'small',
            new Date(item.created_at).toLocaleString('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur',
                dateStyle: 'medium',
                timeStyle: 'short'
            }) + ' MYT'
        );

        const controls = document.createElement('div');
        controls.className = 'notification-card-actions';

        if (
            item.resource_type === 'clinic_rearrangements' &&
            window.location.pathname.startsWith('/web/admin/')
        ) {
            const link = document.createElement('a');
            link.href = '/web/admin/schedules.html#rearrangement-title';
            link.textContent = 'View affected appointments';
            controls.appendChild(link);
        }

        if (!item.read_at) {
            const read = document.createElement('button');
            read.type = 'button';
            read.textContent = 'Mark as read';

            read.addEventListener('click', async () => {
                if (loading) return;

                loading = true;
                read.disabled = true;
                previous.disabled = true;
                next.disabled = true;

                try {
                    await request(
                        `/notifications/${item.notification_id}/read`,
                        'POST'
                    );

                    card.classList.remove('is-unread');
                    read.remove();
                    message.textContent = '';
                    await refreshCount();
                } catch (error) {
                    message.textContent = error.message;
                } finally {
                    loading = false;
                    read.disabled = false;
                    previous.disabled = page === 0;
                    next.disabled = !next.dataset.hasMore;
                }
            });

            controls.appendChild(read);
        }

        card.appendChild(controls);
        return card;
    }

    async function load(targetPage = 0) {
        if (loading) return;
        loading = true;
        previous.disabled = true;
        next.disabled = true;
        list.replaceChildren();
        message.textContent = 'Loading notifications…';

        try {
            const query = new URLSearchParams({
                offset: String(targetPage * pageSize),
                limit: String(pageSize + 1)
            });
            const items = await request(`/notifications?${query}`);

            if (!Array.isArray(items)) {
                throw new Error('Unexpected notification response.');
            }

            page = targetPage;
            next.dataset.hasMore = items.length > pageSize ? 'yes' : '';
            list.replaceChildren(...items.slice(0, pageSize).map(render));
            message.textContent = items.length
                ? ''
                : 'You have no notifications.';
            pageLabel.textContent = `Page ${page + 1}`;
        } catch (error) {
            next.dataset.hasMore = '';
            message.textContent = error.message;
        } finally {
            loading = false;
            previous.disabled = page === 0;
            next.disabled = !next.dataset.hasMore;
        }
    }

    bell.addEventListener('click', () => {
        if (!dialog.open) dialog.showModal();
        load(0);
        refreshCount();
    });

    dialog.querySelector('.notification-close')
        .addEventListener('click', () => dialog.close());

    previous.addEventListener('click', () => load(page - 1));
    next.addEventListener('click', () => load(page + 1));

    refreshCount();

    setInterval(() => {
        if (!document.hidden) refreshCount();
    }, 60000);
})();