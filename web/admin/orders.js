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
                const paymentCell = cell(row, '');

                paymentCell.append(
                    badge(order.payment_status),
                    element(
                        'div',
                        order.payment_method === 'cash'
                            ? 'Cash at pickup'
                            : order.payment_method === 'card' ? 'Card' : order.payment_status === 'pending' ? 'Online payment (Card or FPX)' : 'FPX online banking',
                        'muted'
                    )
                );
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
        const cash = order.payment_method === 'cash';

        if (
            cash &&
            order.shipping_method === 'pickup' &&
            order.payment_status === 'pending'
        ) {
            const actions = {
                confirmed: {
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
                    title: 'Collect cash & complete',
                    cashReceived: true,
                    confirmation:
                        `I received ${money(order.total_amount)} in cash ` +
                        'and handed the order to the recipient.'
                }
            };

            return actions[order.order_status] ?? null;
        }

        if (order.payment_status !== 'paid') return null;

        const actions = {
            pickup: {
                paid: {
                    status: 'processing',
                    title: 'Start processing',
                    confirmation: 'I am starting preparation of this order.'
                },
                confirmed: {
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

    function createActionForm(order, action) {
        const cancelling = action.status === 'cancelled';

        const form = document.createElement('form');
        form.className = 'order-fulfilment-form';

        const notesId = `order-${order.order_id}-${action.status}-notes`;

        const notesLabel = element(
            'label',
            cancelling ? 'Cancellation reason' : 'Staff notes (optional)'
        );
        notesLabel.htmlFor = notesId;

        const notes = document.createElement('textarea');
        notes.id = notesId;
        notes.rows = 3;
        notes.maxLength = 500;
        notes.required = cancelling;

        if (cancelling) {
            notes.minLength = 5;
            notes.placeholder = 'Explain why this cash order is being cancelled';
        } else {
            notes.placeholder = 'Packing or collection notes';
        }

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
            cancelling
                ? 'orders-primary order-cancel'
                : 'orders-primary'
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

            if (cancelling && notes.value.trim().length < 5) {
                feedback.textContent =
                    'Enter a cancellation reason of at least 5 characters.';
                return;
            }

            savingStatus = true;

            content.querySelectorAll(
                'button, input, textarea, select'
            ).forEach(control => {
                control.disabled = true;
            });

            get('order-dialog-close').disabled = true;
            feedback.textContent = 'Saving…';

            let failure = null;

            try {
                await request(
                    `/clinic-orders/${order.order_id}/status`,
                    {
                        expected_version: order.version,
                        new_status: action.status,
                        cash_received: action.cashReceived === true,
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

        return form;
    }

    function renderFulfilment(order) {
        const action = fulfilmentAction(order);

        if (action) {
            const card = detailCard('Update fulfilment');
            card.appendChild(createActionForm(order, action));
        } else if (order.order_status === 'pending_payment') {
            const card = detailCard('Fulfilment');

            card.appendChild(element(
                'p',
                'Waiting for confirmed online payment before processing.',
                'muted'
            ));
        }

        const cancellableCashOrder =
            order.payment_method === 'cash' &&
            order.payment_status === 'pending' &&
            order.shipping_method === 'pickup' &&
            [
                'confirmed',
                'processing',
                'ready_for_pickup'
            ].includes(order.order_status);

        if (cancellableCashOrder) {
            const details = element('details', '', 'order-cash-cancel');

            details.appendChild(element(
                'summary',
                'Cancel unpaid cash order'
            ));

            details.appendChild(createActionForm(order, {
                status: 'cancelled',
                title: 'Cancel cash order',
                confirmation:
                    'I confirm this order is unpaid and should be cancelled. ' +
                    'Its reserved stock will be returned.'
            }));

            content.appendChild(details);
        }
    }

    function refundStatus(status) {
        return {
            pending: 'Awaiting review',
            approved: 'Approved — refund not completed',
            processing: 'Refund processing',
            requires_action: 'Action required',
            succeeded: 'Refund successful',
            rejected: 'Request rejected',
            failed: 'Refund needs attention'
        }[status] ?? label(status);
    }

    function refundActionForm(order, refund, kind) {
        const reviewing = kind === 'review';
        const cash = kind === 'cash';
        const startingOnline =
            kind === 'online' && refund.status === 'approved';

        const form = element('form', '', 'order-fulfilment-form');
        const baseId = `refund-${refund.refund_id}-${kind}`;

        let decision = null;
        let notes = null;
        let confirmation = null;

        if (reviewing) {
            const decisionLabel = element('label', 'Decision');
            decisionLabel.htmlFor = `${baseId}-decision`;

            decision = document.createElement('select');
            decision.id = `${baseId}-decision`;
            decision.required = true;

            decision.add(new Option('Select a decision', ''));
            decision.add(new Option('Approve refund', 'approved'));
            decision.add(new Option('Reject request', 'rejected'));

            form.append(decisionLabel, decision);
        }

        if (reviewing || cash) {
            const notesLabel = element(
                'label',
                reviewing
                    ? 'Explanation for the owner'
                    : 'Cash return notes'
            );

            notesLabel.htmlFor = `${baseId}-notes`;

            notes = document.createElement('textarea');
            notes.id = `${baseId}-notes`;
            notes.rows = 3;
            notes.required = true;
            notes.minLength = 5;
            notes.maxLength = reviewing ? 1000 : 500;

            form.append(notesLabel, notes);
        }

        if (cash || startingOnline) {
            const confirmationLabel = element(
                'label',
                '',
                'order-confirmation'
            );

            confirmation = document.createElement('input');
            confirmation.type = 'checkbox';
            confirmation.required = true;

            confirmationLabel.append(
                confirmation,
                element(
                    'span',
                    cash
                        ? `I have returned ${money(refund.refund_amount)} ` +
                        'in cash to the owner.'
                        : `I confirm that this approved refund of ` +
                        `${money(refund.refund_amount)} should be ` +
                        'submitted to Stripe.'
                )
            );

            form.appendChild(confirmationLabel);
        }

        const title = reviewing
            ? 'Save decision'
            : cash
                ? 'Confirm cash returned'
                : startingOnline
                    ? 'Process online refund'
                    : 'Check Stripe refund status';

        const button = element('button', title, 'orders-primary');
        button.type = 'submit';

        const feedback = element('p', '');
        feedback.setAttribute('role', 'status');

        form.append(button, feedback);

        form.addEventListener('submit', async event => {
            event.preventDefault();

            if (
                savingStatus ||
                !dialog.open ||
                !form.reportValidity()
            ) return;

            if (notes && notes.value.trim().length < 5) {
                feedback.textContent =
                    'Enter an explanation of at least 5 characters.';
                return;
            }

            const payload = {
                expected_version: refund.version
            };

            let endpoint;

            if (reviewing) {
                endpoint = 'review';
                payload.decision = decision.value;
                payload.review_notes = notes.value.trim();
            } else if (cash) {
                endpoint = 'confirm-cash';
                payload.cash_returned = confirmation.checked;
                payload.notes = notes.value.trim();
            } else {
                endpoint = 'process-online';
            }

            savingStatus = true;

            content.querySelectorAll(
                'button, input, textarea, select'
            ).forEach(control => {
                control.disabled = true;
            });

            get('order-dialog-close').disabled = true;
            feedback.textContent = 'Saving and checking refund…';

            let failure = null;

            try {
                await request(
                    `/clinic-orders/${order.order_id}` +
                    `/refunds/${refund.refund_id}/${endpoint}`,
                    payload
                );
            } catch (error) {
                failure = error.message;
            } finally {
                savingStatus = false;
                get('order-dialog-close').disabled = false;
            }

            // Read saved state after both success and uncertain responses.
            // Never automatically repeat a refund mutation.
            await Promise.all([
                openOrder(order.order_id),
                loadOrders(page)
            ]);

            if (dialog.open) {
                content.prepend(element(
                    'p',
                    failure
                        ? `${failure} Check the saved refund status ` +
                        'below before trying again.'
                        : 'The action was saved. The latest refund ' +
                        'status appears below.',
                    failure
                        ? 'order-action-error'
                        : 'order-refund-notice'
                ));
            }
        });

        return form;
    }

    function refundStockForm(order, refund) {
        const form = element(
            'form',
            '',
            'order-fulfilment-form order-refund-stock'
        );

        form.append(
            element('h4', 'Review stock'),
            element(
                'p',
                'Enter only quantities physically held by the clinic ' +
                'and suitable for resale. Leave everything at 0 if ' +
                'nothing should return to stock. This decision is final.',
                'muted'
            )
        );

        const products = new Map();

        for (const item of order.items) {
            const existing = products.get(item.product_id);

            if (existing) {
                existing.quantity += item.quantity;
            } else {
                products.set(item.product_id, {
                    name: item.product_name,
                    quantity: item.quantity
                });
            }
        }

        const inputs = [];

        for (const [productId, product] of products) {
            const row = element('div', '', 'refund-stock-row');
            const inputId =
                `refund-${refund.refund_id}-product-${productId}`;

            const description = element('div', '');
            description.append(
                element('strong', product.name),
                element(
                    'div',
                    `Ordered: ${product.quantity}`,
                    'muted'
                )
            );

            const field = element('div', '');
            const inputLabel = element('label', 'Restock quantity');
            inputLabel.htmlFor = inputId;

            const input = document.createElement('input');
            input.id = inputId;
            input.type = 'number';
            input.min = '0';
            input.max = String(product.quantity);
            input.step = '1';
            input.value = '0';
            input.required = true;

            field.append(inputLabel, input);
            row.append(description, field);
            form.appendChild(row);

            inputs.push({
                productId,
                maximum: product.quantity,
                input
            });
        }

        const notesId = `refund-${refund.refund_id}-stock-notes`;
        const notesLabel = element('label', 'Stock decision notes');
        notesLabel.htmlFor = notesId;

        const notes = document.createElement('textarea');
        notes.id = notesId;
        notes.rows = 3;
        notes.required = true;
        notes.minLength = 5;
        notes.maxLength = 1000;
        notes.placeholder =
            'Explain the condition of the goods, or why nothing is restocked';

        const confirmationLabel = element(
            'label',
            '',
            'order-confirmation'
        );

        const confirmation = document.createElement('input');
        confirmation.type = 'checkbox';
        confirmation.required = true;

        confirmationLabel.append(
            confirmation,
            element(
                'span',
                'I checked these quantities and confirm this final ' +
                'stock decision. Damaged, used or missing goods ' +
                'are excluded.'
            )
        );

        const button = element(
            'button',
            'Save stock decision',
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

            if (notes.value.trim().length < 5) {
                feedback.textContent =
                    'Enter stock decision notes of at least 5 characters.';
                return;
            }

            const items = [];

            for (const field of inputs) {
                const quantity = Number(field.input.value);

                if (
                    !Number.isInteger(quantity) ||
                    quantity < 0 ||
                    quantity > field.maximum
                ) {
                    feedback.textContent =
                        'Enter whole quantities within the ordered amounts.';
                    return;
                }

                if (quantity > 0) {
                    items.push({
                        product_id: field.productId,
                        quantity
                    });
                }
            }

            const payload = {
                expected_version: refund.version,
                confirmed: confirmation.checked,
                notes: notes.value.trim(),
                items
            };

            savingStatus = true;

            content.querySelectorAll(
                'button, input, textarea, select'
            ).forEach(control => {
                control.disabled = true;
            });

            get('order-dialog-close').disabled = true;
            feedback.textContent = 'Saving stock decision…';

            let failure = null;

            try {
                await request(
                    `/clinic-orders/${order.order_id}` +
                    `/refunds/${refund.refund_id}/review-stock`,
                    payload
                );
            } catch (error) {
                failure = error.message;
            } finally {
                savingStatus = false;
                get('order-dialog-close').disabled = false;
            }

            await Promise.all([
                openOrder(order.order_id),
                loadOrders(page)
            ]);

            if (dialog.open) {
                content.prepend(element(
                    'p',
                    failure
                        ? `${failure} Check the saved stock decision ` +
                        'before trying again.'
                        : 'The stock decision was saved.',
                    failure
                        ? 'order-action-error'
                        : 'order-refund-notice'
                ));
            }
        });

        return form;
    }

    function renderRefunds(order, refunds) {
        const section = detailCard('Refund requests');

        if (!refunds.length) {
            section.appendChild(element(
                'p',
                'No refund requests for this order.',
                'muted'
            ));
            return;
        }

        for (const refund of refunds) {
            const card = element(
                'article',
                '',
                'order-refund-card'
            );

            const heading = element(
                'div',
                '',
                'order-refund-heading'
            );

            heading.append(
                element('h4', `Refund #${refund.refund_id}`),
                element('strong', money(refund.refund_amount))
            );

            card.append(
                heading,
                element(
                    'span',
                    refundStatus(refund.status),
                    'order-badge'
                )
            );

            detailLine(
                card,
                'Requested',
                date(refund.requested_at)
            );

            detailLine(card, 'Owner reason', refund.reason);

            if (refund.review_notes) {
                detailLine(
                    card,
                    'Clinic response',
                    refund.review_notes
                );
            }

            if (refund.processed_at) {
                detailLine(
                    card,
                    'Processed',
                    date(refund.processed_at)
                );
            }

            if (refund.status === 'pending') {
                card.appendChild(element(
                    'p',
                    'Approval pauses fulfilment. It does not ' +
                    'mark the payment as refunded.',
                    'muted'
                ));

                card.appendChild(
                    refundActionForm(order, refund, 'review')
                );
            }

            if (
                refund.status === 'approved' &&
                order.payment_method === 'cash'
            ) {
                card.appendChild(element(
                    'p',
                    'Return the cash to the owner before confirming.',
                    'muted'
                ));

                card.appendChild(
                    refundActionForm(order, refund, 'cash')
                );
            }

            if (
                order.payment_method === 'online_banking' &&
                [
                    'approved',
                    'processing',
                    'requires_action',
                    'failed'
                ].includes(refund.status)
            ) {
                card.appendChild(
                    refundActionForm(order, refund, 'online')
                );
            }

            if (refund.status === 'requires_action') {
                card.appendChild(element(
                    'p',
                    'Additional action is required. Review this ' +
                    'refund in the Stripe sandbox Dashboard.',
                    'muted'
                ));
            }

            if (refund.status === 'failed') {
                card.appendChild(element(
                    'p',
                    'Review the refund in Stripe before taking ' +
                    'further action. Checking status does not ' +
                    'create a replacement refund.',
                    'muted'
                ));
            }

            if (refund.status === 'succeeded') {
                if (refund.stock_reviewed_at) {
                    detailLine(
                        card,
                        'Stock reviewed',
                        date(refund.stock_reviewed_at)
                    );

                    const returnedItems =
                        refund.stock_return_items ?? [];

                    if (!returnedItems.length) {
                        card.appendChild(element(
                            'p',
                            'Stock review completed. No quantities ' +
                            'were added to stock.',
                            'muted'
                        ));
                    } else {
                        const list = document.createElement('ul');
                        list.className = 'refund-stock-result';

                        for (const returned of returnedItems) {
                            const product = order.items.find(
                                item =>
                                    item.product_id === returned.product_id
                            );

                            list.appendChild(element(
                                'li',
                                `${product?.product_name ??
                                `Product #${returned.product_id}`} ` +
                                `— ${returned.quantity} returned to stock`
                            ));
                        }

                        card.appendChild(list);
                    }
                } else {
                    card.appendChild(
                        refundStockForm(order, refund)
                    );
                }
            }

            section.appendChild(card);
        }
    }

    async function openOrder(orderId) {
        if (savingStatus) return;

        const version = ++detailVersion;

        get('order-dialog-title').textContent = `Order #${orderId}`;
        content.replaceChildren(element('p', 'Loading order details…'));

        if (!dialog.open) dialog.showModal();

        try {
            const [order, refunds] = await Promise.all([
                request(`/clinic-orders/${orderId}`),
                request(`/clinic-orders/${orderId}/refunds`)
            ]);

            if (!Array.isArray(refunds)) {
                throw new Error('Unexpected refund response.');
            }

            if (version !== detailVersion || !dialog.open) return;

            content.replaceChildren();

            const status = detailCard('Order information');
            detailLine(status, 'Clinic', order.clinic_name);
            detailLine(status, 'Placed', date(order.order_date));
            detailLine(status, 'Order status', label(order.order_status));
            detailLine(
                status,
                'Payment method',
                order.payment_method === 'cash'
                    ? 'Cash at clinic pickup'
                    : order.payment_method === 'card' ? 'Card' : order.payment_status === 'pending' ? 'Online payment (Card or FPX)' : 'FPX online banking'
            );
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
            const refundBlocksFulfilment = refunds.some(refund =>
                [
                    'approved',
                    'processing',
                    'requires_action',
                    'succeeded',
                    'failed'
                ].includes(refund.status)
            );

            if (!refundBlocksFulfilment) {
                renderFulfilment(order);
            }

            renderRefunds(order, refunds);
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

            const linkedOrder = new URLSearchParams(
                window.location.search
            ).get('order_id');

            if (
                linkedOrder &&
                /^[1-9][0-9]{0,9}$/.test(linkedOrder)
            ) {
                const orderId = Number(linkedOrder);

                if (
                    Number.isSafeInteger(orderId) &&
                    orderId <= 2147483647
                ) {
                    await openOrder(orderId);
                }
            }
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