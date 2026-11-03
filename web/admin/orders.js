(() => {
    const get = id => document.getElementById(id);
    const rows = get('orders-rows');
    const message = get('orders-message');
    const dialog = get('order-dialog');
    const content = get('order-dialog-content');

    const pageSize = 10;

    let page = 0;
    let total = 0;
    let listVersion = 0;
    let detailVersion = 0;
    let starting = false;
    let savingStatus = false;

    // Keep pagination tied to the last submitted filters.
    let filters = {
        q: '',
        status: '',
        method: ''
    };

    function logout() {
        sessionStorage.removeItem('vetdental_staff_token');
        window.location.replace('/web/');
    }

    async function request(path, body) {
        const token = sessionStorage.getItem('vetdental_staff_token');

        if (!token) {
            logout();
            throw new Error('Please log in again.');
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);

        const headers = {
            Accept: 'application/json',
            Authorization: `Bearer ${token}`
        };

        if (body !== undefined) {
            headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch(path, {
                method: body === undefined ? 'GET' : 'POST',
                headers,
                body: body === undefined
                    ? undefined
                    : JSON.stringify(body),
                credentials: 'omit',
                cache: 'no-store',
                signal: controller.signal
            });

            if (response.status === 401) {
                logout();
                throw new Error('Your session has expired.');
            }

            let data;

            try {
                data = await response.json();
            } catch (_) {
                throw new Error('Unexpected server response.');
            }

            if (!response.ok) {
                const detail = Array.isArray(data.detail)
                    ? data.detail.map(item => item.msg).join(' ')
                    : data.detail;

                throw new Error(
                    typeof detail === 'string'
                        ? detail
                        : 'The request could not be completed.'
                );
            }

            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(
                    'The request timed out. The saved status needs checking.'
                );
            }

            if (error instanceof TypeError) {
                throw new Error('Cannot connect to the server.');
            }

            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    function label(value) {
        return String(value ?? 'Unknown')
            .split('_')
            .map(word => word
                ? word[0].toUpperCase() + word.slice(1)
                : '')
            .join(' ');
    }

    function money(value) {
        if (value === null || value === undefined) return '—';

        const amount = Number(value);

        return Number.isFinite(amount)
            ? `RM ${amount.toFixed(2)}`
            : '—';
    }

    function date(value) {
        if (!value) return '—';

        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return '—';

        return new Intl.DateTimeFormat('en-MY', {
            timeZone: 'Asia/Kuala_Lumpur',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(parsed) + ' MYT';
    }

    function element(tag, text, className = '') {
        const node = document.createElement(tag);
        node.textContent = text;
        node.className = className;
        return node;
    }

    function cell(row, text) {
        const node = element('td', text);
        row.appendChild(node);
        return node;
    }

    function badge(status) {
        let className = 'order-badge';

        if (status === 'pending_payment' || status === 'pending') {
            className += ' pending';
        }

        if (['cancelled', 'expired', 'failed'].includes(status)) {
            className += ' closed';
        }

        return element('span', label(status), className);
    }

    async function loadOrders(targetPage = 0) {
        const version = ++listVersion;

        rows.replaceChildren();
        message.textContent = 'Loading orders…';
        get('orders-retry').hidden = true;
        get('orders-previous').disabled = true;
        get('orders-next').disabled = true;

        const query = new URLSearchParams({
            q: filters.q,
            offset: String(targetPage * pageSize),
            limit: String(pageSize)
        });

        if (filters.status) {
            query.set('order_status', filters.status);
        }

        if (filters.method) {
            query.set('shipping_method', filters.method);
        }

        try {
            const data = await request(`/clinic-orders?${query}`);
            if (version !== listVersion) return;

            if (
                !Array.isArray(data.items) ||
                !Number.isInteger(data.total) ||
                data.total < 0
            ) {
                throw new Error('Unexpected order-list response.');
            }

            page = targetPage;
            total = data.total;

            for (const order of data.items) {
                const row = document.createElement('tr');

                cell(row, `#${order.order_id}`);
                cell(row, date(order.order_date));
                cell(row, order.recipient_name);
                cell(
                    row,
                    order.shipping_method === 'pickup'
                        ? 'Clinic pickup'
                        : 'Delivery'
                );
                cell(row, money(order.total_amount));
                cell(row, '').appendChild(badge(order.payment_status));
                cell(row, '').appendChild(badge(order.order_status));

                const button = element('button', 'View details', 'secondary');
                button.type = 'button';
                button.addEventListener('click', () => openOrder(order.order_id));

                cell(row, '').appendChild(button);
                rows.appendChild(row);
            }

            message.textContent = data.items.length
                ? `${total} matching order(s).`
                : 'No orders match these filters.';

            get('orders-page').textContent = `Page ${page + 1}`;
            get('orders-previous').disabled = page === 0;
            get('orders-next').disabled =
                (page + 1) * pageSize >= total;
        } catch (error) {
            if (version !== listVersion) return;

            message.textContent = error.message;
            get('orders-retry').hidden = false;
        }
    }

    function detailCard(title) {
        const card = element('section', '', 'order-detail-card');
        card.appendChild(element('h3', title));
        content.appendChild(card);
        return card;
    }

    function detailLine(card, title, value) {
        const line = document.createElement('p');

        line.append(
            element('strong', `${title}: `),
            document.createTextNode(String(value ?? '—'))
        );

        card.appendChild(line);
    }

    function amountLine(card, title, amount, final = false) {
        const line = element(
            'div',
            '',
            final ? 'order-total final' : 'order-total'
        );

        line.append(
            element('span', title),
            element('span', money(amount))
        );

        card.appendChild(line);
    }

    function fulfilmentAction(order) {
        if (order.payment_status !== 'paid') return null;

        const actions = {
            pickup: {
                paid: {
                    status: 'processing',
                    title: 'Start processing',
                    confirmation: 'I am starting preparation of this order.'
                },
                processing: {
                    status: 'ready_for_pickup',
                    title: 'Mark ready for pickup',
                    confirmation: 'The order is prepared and ready for collection.'
                },
                ready_for_pickup: {
                    status: 'completed',
                    title: 'Confirm collected',
                    confirmation: 'The recipient has collected this order.'
                }
            },
            delivery: {
                paid: {
                    status: 'processing',
                    title: 'Start processing',
                    confirmation: 'I am starting preparation of this order.'
                },
                processing: {
                    status: 'shipped',
                    title: 'Mark shipped',
                    confirmation: 'The order has been handed over for delivery.'
                },
                shipped: {
                    status: 'completed',
                    title: 'Confirm delivered',
                    confirmation: 'Delivery to the recipient has been confirmed.'
                }
            }
        };

        return actions[order.shipping_method]?.[order.order_status] ?? null;
    }

    function renderFulfilment(order) {
        const action = fulfilmentAction(order);

        if (!action) {
            if (order.order_status === 'pending_payment') {
                const card = detailCard('Fulfilment');
                card.appendChild(element(
                    'p',
                    'Waiting for confirmed payment before processing.',
                    'muted'
                ));
            }

            return;
        }

        const card = detailCard('Update fulfilment');
        const form = document.createElement('form');
        form.className = 'order-fulfilment-form';

        const notesId = `order-${order.order_id}-notes`;
        const notesLabel = element('label', 'Staff notes (optional)');
        notesLabel.htmlFor = notesId;

        const notes = document.createElement('textarea');
        notes.id = notesId;
        notes.rows = 3;
        notes.maxLength = 500;
        notes.placeholder = 'Packing, collection or delivery notes';

        const confirmationLabel = document.createElement('label');
        confirmationLabel.className = 'order-confirmation';

        const confirmation = document.createElement('input');
        confirmation.type = 'checkbox';
        confirmation.required = true;

        confirmationLabel.append(
            confirmation,
            element('span', action.confirmation)
        );

        const button = element(
            'button',
            action.title,
            'orders-primary'
        );
        button.type = 'submit';

        const feedback = element('p', '');
        feedback.setAttribute('role', 'status');

        form.append(
            notesLabel,
            notes,
            confirmationLabel,
            button,
            feedback
        );

        form.addEventListener('submit', async event => {
            event.preventDefault();

            if (
                savingStatus ||
                !dialog.open ||
                !form.reportValidity()
            ) return;

            savingStatus = true;
            button.disabled = true;
            notes.disabled = true;
            confirmation.disabled = true;
            get('order-dialog-close').disabled = true;
            feedback.textContent = 'Saving…';

            let failure = null;

            try {
                await request(
                    `/clinic-orders/${order.order_id}/status`,
                    {
                        expected_version: order.version,
                        new_status: action.status,
                        notes: notes.value.trim() || null
                    }
                );
            } catch (error) {
                failure = error.message;
            } finally {
                savingStatus = false;
                get('order-dialog-close').disabled = false;
            }

            if (!failure) {
                dialog.close();
                await loadOrders(page);
                return;
            }

            // Never repeat the status mutation automatically.
            // Reload the saved order before offering another action.
            await Promise.all([
                openOrder(order.order_id),
                loadOrders(page)
            ]);

            if (dialog.open) {
                content.prepend(element(
                    'p',
                    `${failure} Check the latest saved status before trying again.`,
                    'order-action-error'
                ));
            }
        });

        card.appendChild(form);
    }

    async function openOrder(orderId) {
        if (savingStatus) return;

        const version = ++detailVersion;

        get('order-dialog-title').textContent = `Order #${orderId}`;
        content.replaceChildren(element('p', 'Loading order details…'));

        if (!dialog.open) dialog.showModal();

        try {
            const order = await request(`/clinic-orders/${orderId}`);

            if (version !== detailVersion || !dialog.open) return;

            content.replaceChildren();

            const status = detailCard('Order information');
            detailLine(status, 'Clinic', order.clinic_name);
            detailLine(status, 'Placed', date(order.order_date));
            detailLine(status, 'Order status', label(order.order_status));
            detailLine(status, 'Payment status', label(order.payment_status));

            if (order.order_status === 'pending_payment') {
                detailLine(
                    status,
                    'Payment deadline',
                    date(order.payment_expires_at)
                );
            }

            const recipient = detailCard(
                order.shipping_method === 'pickup'
                    ? 'Clinic pickup'
                    : 'Delivery'
            );

            detailLine(recipient, 'Recipient', order.recipient_name);
            detailLine(recipient, 'Phone', order.recipient_phone);
            detailLine(recipient, 'Address', order.shipping_address);

            if (order.owner_note) {
                detailLine(recipient, 'Owner note', order.owner_note);
            }

            const products = detailCard('Products');

            for (const item of order.items) {
                const line = element('div', '', 'order-item');

                line.append(
                    element(
                        'span',
                        `${item.product_name} × ${item.quantity}`
                    ),
                    element('strong', money(item.subtotal))
                );

                products.appendChild(line);
            }

            amountLine(products, 'Subtotal', order.subtotal);
            amountLine(products, 'Pickup / delivery fee', order.shipping_fee);
            amountLine(products, 'Total', order.total_amount, true);
            renderFulfilment(order);
        } catch (error) {
            if (version !== detailVersion || !dialog.open) return;

            const retry = element('button', 'Try again', 'secondary');
            retry.type = 'button';
            retry.addEventListener('click', () => openOrder(orderId));

            content.replaceChildren(
                element('p', error.message),
                retry
            );
        }
    }

    async function initialize() {
        if (starting) return;
        starting = true;
        get('orders-start-retry').hidden = true;
        get('orders-start-message').textContent = 'Loading orders…';

        try {
            const profile = await request('/admins/me');

            get('topbar-name').textContent = profile.user.full_name;
            get('topbar-avatar').textContent =
                Array.from(profile.user.full_name.trim())[0]?.toUpperCase()
                || 'A';

            get('orders-loading').hidden = true;
            get('orders-workspace').hidden = false;

            await loadOrders(0);
        } catch (error) {
            get('orders-start-message').textContent = error.message;
            get('orders-start-retry').hidden = false;
        } finally {
            starting = false;
        }
    }

    get('orders-filters').addEventListener('submit', event => {
        event.preventDefault();

        filters = {
            q: get('orders-search').value.trim(),
            status: get('orders-status').value,
            method: get('orders-method').value
        };

        loadOrders(0);
    });

    for (const id of ['orders-status', 'orders-method']) {
        get(id).addEventListener('change', () => {
            get('orders-filters').requestSubmit();
        });
    }

    get('orders-previous').addEventListener('click', () => {
        if (page > 0) loadOrders(page - 1);
    });

    get('orders-next').addEventListener('click', () => {
        if ((page + 1) * pageSize < total) loadOrders(page + 1);
    });

    get('orders-retry').addEventListener('click', () => loadOrders(page));
    get('orders-start-retry').addEventListener('click', initialize);
    get('logout-button').addEventListener('click', logout);
    get('order-dialog-close').addEventListener('click', () => {
        if (!savingStatus) dialog.close();
    });

    dialog.addEventListener('cancel', event => {
        if (savingStatus) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        detailVersion++;
        content.replaceChildren();
    });

    initialize();
})();