(() => {
    const get = id => document.getElementById(id);
    const dialog = get('billing-dialog');
    const itemContainer = get('billing-items');
    const formMessage = get('billing-form-message');

    const pageSize = 10;

    let ready = false;
    let starting = false;
    let page = 0;
    let total = 0;
    let listVersion = 0;
    let detailVersion = 0;
    let rowSequence = 0;

    let selected = null;
    let bill = null;
    let payments = [];
    let clinicName = '';
    let detailReady = false;
    let saving = false;
    let dirty = false;

    let filters = { q: '', status: '' };

    function logout() {
        sessionStorage.removeItem('vetdental_staff_token');
        window.location.replace('/web/');
    }

    function node(tag, text = '', className = '') {
        const element = document.createElement(tag);
        element.textContent = text;
        element.className = className;
        return element;
    }

    async function request(
        path,
        body,
        method = body === undefined ? 'GET' : 'POST'
    ) {
        const token = sessionStorage.getItem('vetdental_staff_token');

        if (!token) {
            logout();
            throw new Error('Please log in again.');
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);

        try {
            const response = await fetch(path, {
                method,
                headers: {
                    Accept: 'application/json',
                    Authorization: `Bearer ${token}`,
                    ...(body === undefined
                        ? {}
                        : { 'Content-Type': 'application/json' })
                },
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

            const data = await response.json();

            if (!response.ok) {
                const detail = Array.isArray(data.detail)
                    ? data.detail.map(item => item.msg).join(' ')
                    : data.detail;

                const error = new Error(
                    typeof detail === 'string'
                        ? detail
                        : 'The request could not be completed.'
                );

                error.status = response.status;
                throw error;
            }

            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error(
                    'The request timed out. Check the saved bill before retrying.'
                );
            }

            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    function money(value) {
        if (value === null || value === undefined) return '—';

        const amount = Number(value);
        return Number.isFinite(amount)
            ? `RM ${amount.toFixed(2)}`
            : '—';
    }

    function label(value) {
        return {
            unbilled: 'Unbilled',
            draft: 'Draft',
            issued: 'Awaiting payment',
            paid: 'Paid',
            void: 'Void'
        }[value] ?? String(value);
    }

    function date(value) {
        const parsed = new Date(value);

        if (Number.isNaN(parsed.getTime())) return '—';

        return new Intl.DateTimeFormat('en-MY', {
            timeZone: 'Asia/Kuala_Lumpur',
            day: '2-digit',
            month: 'short',
            year: 'numeric'
        }).format(parsed);
    }

    async function loadList(targetPage = 0) {
        if (!ready) return;

        const version = ++listVersion;
        get('billing-rows').replaceChildren();
        get('billing-message').textContent = 'Loading consultations…';
        get('billing-retry').hidden = true;
        get('billing-previous').disabled = true;
        get('billing-next').disabled = true;

        const query = new URLSearchParams({
            q: filters.q,
            offset: String(targetPage * pageSize),
            limit: String(pageSize)
        });

        if (filters.status) {
            query.set('bill_status', filters.status);
        }

        try {
            const data = await request(
                `/clinic-billing/consultations?${query}`
            );

            if (version !== listVersion) return;

            if (
                !Array.isArray(data.items) ||
                !Number.isInteger(data.total) ||
                data.total < 0
            ) {
                throw new Error('Unexpected consultation-list response.');
            }

            page = targetPage;
            total = data.total;

            for (const entry of data.items) {
                const row = document.createElement('tr');

                for (const value of [
                    date(entry.consultation_date),
                    entry.pet_name,
                    entry.owner_name,
                    `#${entry.consultation_id}`,
                    label(entry.bill_status),
                    money(entry.total_amount)
                ]) {
                    row.appendChild(node('td', value));
                }

                const button = node(
                    'button',
                    entry.bill_status === 'unbilled'
                        ? 'Prepare bill'
                        : 'View bill',
                    'secondary'
                );

                button.type = 'button';
                button.addEventListener('click', () => openEditor(entry));

                const action = document.createElement('td');
                action.appendChild(button);
                row.appendChild(action);

                get('billing-rows').appendChild(row);
            }

            get('billing-message').textContent = data.items.length
                ? `${total} matching consultation(s).`
                : 'No completed consultations match these filters.';

            get('billing-page').textContent = `Page ${page + 1}`;
            get('billing-previous').disabled = page === 0;
            get('billing-next').disabled =
                (page + 1) * pageSize >= total;

        } catch (error) {
            if (version !== listVersion) return;

            get('billing-message').textContent = error.message;
            get('billing-retry').hidden = false;
        }
    }

    function editable() {
        return detailReady && (!bill || bill.status === 'draft');
    }

    function controls() {
        const canEdit = editable();

        get('billing-fields').disabled = saving || !canEdit;
        get('billing-add-item').hidden = !canEdit;

        get('billing-save').hidden = !canEdit;
        get('billing-save').disabled = saving || !detailReady;
        get('billing-save').textContent = saving
            ? 'Saving…'
            : 'Save draft';

        const canIssue = detailReady && bill?.status === 'draft';

        get('billing-issue').hidden = !canIssue;
        get('billing-issue-confirmation').hidden = !canIssue;
        get('billing-issue-confirm').disabled = saving || dirty;

        get('billing-issue').disabled =
            saving ||
            dirty ||
            !get('billing-issue-confirm').checked;

        const issued = detailReady && bill?.status === 'issued';

        const competingPayment = payments.some(payment =>
            !['failed', 'cancelled', 'expired'].includes(
                payment.payment_status
            )
        );

        get('billing-cash-panel').hidden = !issued;

        get('billing-cash-fields').disabled =
            saving || !issued || competingPayment;

        get('billing-collect-cash').disabled =
            saving ||
            !issued ||
            competingPayment ||
            !get('billing-cash-confirm').checked;

        get('billing-cash-amount').textContent = competingPayment
            ? 'Another payment is pending or recorded. ' +
            'Resolve it before accepting cash.'
            : `Amount to collect: ${money(bill?.balance_amount)}`;

        get('billing-close').disabled = saving;
        get('billing-cancel').disabled = saving;
    }

    function readItems() {
        const rows = [...itemContainer.children];

        if (!rows.length || rows.length > 50) {
            throw new Error('Enter between 1 and 50 charges.');
        }

        let totalCents = 0;

        const items = rows.map(row => {
            const description = row.querySelector(
                '[data-field="description"]'
            ).value.trim();

            const quantity = Number(
                row.querySelector('[data-field="quantity"]').value
            );

            const price = row.querySelector(
                '[data-field="unit_price"]'
            ).value;

            if (
                description.length < 2 ||
                description.length > 255 ||
                !Number.isInteger(quantity) ||
                quantity < 1 ||
                quantity > 999 ||
                !/^\d{1,8}(?:\.\d{1,2})?$/.test(price)
            ) {
                throw new Error(
                    'Check each description, whole quantity and price.'
                );
            }

            const [whole, fraction = ''] = price.split('.');
            const cents =
                Number(whole) * 100 +
                Number(fraction.padEnd(2, '0'));

            totalCents += cents * quantity;

            if (totalCents > 9999999999) {
                throw new Error('The bill total is too large.');
            }

            return {
                item_type: row.querySelector(
                    '[data-field="item_type"]'
                ).value,
                description,
                quantity,
                unit_price: price
            };
        });

        return { items, totalCents };
    }

    function renderDepositRefund(section) {
        if (Number(bill.deposit_excess_refund_amount) <= 0) {
            return;
        }

        const refund = bill.deposit_refund;

        const labels = {
            approved: 'Queued',
            processing: 'Processing',
            requires_action: 'Needs attention',
            succeeded: 'Refunded',
            failed: 'Failed — needs review',
        };

        const box = node('div', '', 'billing-refund-status');

        box.appendChild(node('h4', 'Excess deposit refund'));

        box.appendChild(node(
            'p',
            refund
                ? labels[refund.status] ?? 'Unknown status'
                : 'Refund status unavailable. Refresh the bill.'
        ));

        if (refund) {
            box.appendChild(node(
                'p',
                `Refund #${refund.refund_id} · ` +
                money(refund.refund_amount)
            ));

            if (refund.processed_at) {
                box.appendChild(node(
                    'p',
                    `Processed: ${date(refund.processed_at)}`
                ));
            }

            if (refund.status === 'failed') {
                box.appendChild(node(
                    'p',
                    'Check the failed refund in Stripe before ' +
                    'arranging another refund.'
                ));
            }
        }

        const refresh = node(
            'button',
            'Refresh refund status',
            'secondary compact-button'
        );

        refresh.type = 'button';

        refresh.addEventListener('click', () => {
            if (saving || !selected || !detailReady) return;

            openEditor(selected);
        });

        box.appendChild(refresh);
        section.appendChild(box);
    }

    function renderBalanceSummary() {
        const section = get('billing-balance-summary');

        section.replaceChildren();

        section.hidden =
            !detailReady ||
            !bill ||
            bill.status === 'draft';

        if (section.hidden) return;

        section.appendChild(node('h3', 'Deposit & balance'));

        const breakdown = node(
            'dl',
            '',
            'billing-balance-breakdown'
        );

        const entries = [
            ['Total charges', bill.total_amount],
            ['Booking deposit received', bill.deposit_paid_amount],
            ['Deposit applied', bill.deposit_applied_amount],
            ['Balance after deposit', bill.balance_amount],
            ['Amount still due', bill.amount_due],
        ];

        if (Number(bill.deposit_excess_refund_amount) > 0) {
            entries.push([
                'Excess deposit refund',
                bill.deposit_excess_refund_amount,
            ]);
        }

        for (const [title, amount] of entries) {
            const row = node('div');

            row.append(
                node('dt', title),
                node('dd', money(amount))
            );

            breakdown.appendChild(row);
        }

        section.appendChild(breakdown);
        renderDepositRefund(section);
    }

    function updatePreview() {
        try {
            const { totalCents } = readItems();
            get('billing-total').textContent =
                money(totalCents / 100);
        } catch (_) {
            get('billing-total').textContent = '—';
        }

        renderBalanceSummary();
    }

    function changed() {
        dirty = true;
        get('billing-issue-confirm').checked = false;
        updatePreview();
        controls();
    }

    function addRow(item = {}) {
        const row = node('div', '', 'billing-charge');
        const rowId = ++rowSequence;

        function field(title, name, input) {
            input.dataset.field = name;
            input.id = `bill-item-${rowId}-${name}`;

            const wrapper = document.createElement('div');
            const caption = node('label', title);
            caption.htmlFor = input.id;

            wrapper.append(caption, input);
            row.appendChild(wrapper);
            return input;
        }

        const type = document.createElement('select');

        for (const [value, title] of [
            ['consultation', 'Consultation'],
            ['procedure', 'Procedure'],
            ['medication', 'Medication'],
            ['other', 'Other']
        ]) {
            type.add(new Option(title, value));
        }

        type.value = item.item_type ?? 'consultation';
        field('Type', 'item_type', type);

        const description = document.createElement('input');
        description.required = true;
        description.minLength = 2;
        description.maxLength = 255;
        description.value = item.description ?? '';
        field('Description', 'description', description);

        const quantity = document.createElement('input');
        quantity.type = 'number';
        quantity.required = true;
        quantity.min = '1';
        quantity.max = '999';
        quantity.step = '1';
        quantity.value = String(item.quantity ?? 1);
        field('Quantity', 'quantity', quantity);

        const price = document.createElement('input');
        price.type = 'number';
        price.required = true;
        price.min = '0';
        price.max = '99999999.99';
        price.step = '0.01';
        price.value = String(item.unit_price ?? '0.00');
        field('Unit price (RM)', 'unit_price', price);

        const remove = node('button', 'Remove', 'secondary');
        remove.type = 'button';

        remove.addEventListener('click', () => {
            if (saving || !editable()) return;

            if (itemContainer.children.length <= 1) {
                formMessage.textContent =
                    'The bill needs at least one charge.';
                return;
            }

            row.remove();
            changed();
        });

        row.appendChild(remove);
        itemContainer.appendChild(row);
    }

    function printReceipt(payment) {
        if (
            saving ||
            !detailReady ||
            !bill ||
            !selected ||
            payment.payment_status !== 'paid' ||
            !payment.receipt_number ||
            !payment.payment_date
        ) {
            return;
        }

        const receiptWindow = window.open(
            '',
            '_blank',
            'width=900,height=750'
        );

        if (!receiptWindow) {
            formMessage.textContent =
                'Allow pop-ups for this website to print receipts.';
            return;
        }

        receiptWindow.opener = null;

        const doc = receiptWindow.document;
        doc.title = `Receipt ${payment.receipt_number}`;
        doc.documentElement.lang = 'en';

        const style = doc.createElement('style');
        style.textContent = `
        * { box-sizing: border-box; }
        body {
            max-width: 780px;
            margin: 40px auto;
            padding: 0 24px;
            color: #23352a;
            font: 15px/1.6 Arial, sans-serif;
        }
        h1 { margin-bottom: 4px; font-size: 25px; }
        h2 { margin-top: 0; color: #176b32; }
        p { margin: 6px 0; }
        table {
            width: 100%;
            margin-top: 24px;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 8px;
            border-bottom: 1px solid #ddd;
            text-align: left;
            vertical-align: top;
            overflow-wrap: anywhere;
        }
        th { background: #f3f7f4; }
        th:last-child, td:last-child {
            text-align: right;
            white-space: nowrap;
        }
        .total {
            margin-top: 24px;
            font-size: 20px;
            font-weight: bold;
            text-align: right;
        }
        .actions { margin-top: 28px; }
        button {
            padding: 10px 18px;
            border: 0;
            border-radius: 7px;
            background: #176b32;
            color: white;
            cursor: pointer;
        }
        @page { size: A4; margin: 18mm; }
        @media print {
            body { margin: 0; padding: 0; max-width: none; }
            .actions { display: none; }
            tr { break-inside: avoid; }
            thead { display: table-header-group; }
        }
    `;
        doc.head.appendChild(style);

        function add(tag, text, parent = doc.body) {
            const element = doc.createElement(tag);
            element.textContent = text;
            parent.appendChild(element);
            return element;
        }

        add('h1', clinicName || 'Veterinary clinic');
        add('h2', 'Payment receipt');
        add('p', `Receipt: ${payment.receipt_number}`);
        add('p', `Bill #${bill.consultation_bill_id}`);
        add('p', `Consultation #${bill.consultation_id}`);
        add('p', `Pet: ${selected.pet_name}`);
        add('p', `Owner: ${selected.owner_name}`);

        add(
            'p',
            `Paid: ${new Date(payment.payment_date).toLocaleString(
                'en-MY',
                { timeZone: 'Asia/Kuala_Lumpur' }
            )} MYT`
        );

        add(
            'p',
            `Payment method: ${payment.payment_method === 'cash'
                ? 'Cash at clinic'
                : 'Online payment'
            }`
        );

        const table = doc.createElement('table');
        doc.body.appendChild(table);

        const head = table.createTHead().insertRow();

        for (const title of [
            'Description', 'Quantity', 'Unit price', 'Subtotal'
        ]) {
            add('th', title, head);
        }

        const body = table.createTBody();

        for (const item of bill.items) {
            const row = body.insertRow();

            for (const value of [
                item.description,
                item.quantity,
                money(item.unit_price),
                money(item.subtotal),
            ]) {
                add('td', String(value), row);
            }
        }

        add('p', `Total charges: ${money(bill.total_amount)}`);
        add(
            'p',
            `Booking deposit applied: ${money(bill.deposit_applied_amount)}`
        );
        add(
            'p',
            `Balance after deposit: ${money(bill.balance_amount)}`
        );

        if (Number(bill.deposit_excess_refund_amount) > 0) {
            add(
                'p',
                'Excess deposit refund amount: ' +
                money(bill.deposit_excess_refund_amount)
            );
        }

        const total = add(
            'p',
            `Amount paid: ${money(payment.amount)}`
        );
        total.className = 'total';

        const actions = add('div', '');
        actions.className = 'actions';

        const print = add('button', 'Print / Save PDF', actions);
        print.type = 'button';
        print.addEventListener('click', () => {
            receiptWindow.focus();
            receiptWindow.print();
        });

        receiptWindow.focus();
    }

    function renderPayments() {
        const section = get('billing-payment-summary');
        section.replaceChildren();
        section.hidden = !detailReady || !bill;

        if (section.hidden) return;

        section.appendChild(node('h3', 'Payment records'));

        if (!payments.length) {
            section.appendChild(node(
                'p',
                bill.status === 'paid' &&
                    Number(bill.deposit_applied_amount) > 0
                    ? 'This bill was settled using its booking deposit.'
                    : bill.status === 'paid' &&
                        Number(bill.total_amount) === 0
                        ? 'No payment was required for this bill.'
                        : 'No balance payment has been recorded.'
            ));
            return;
        }

        for (const payment of payments) {
            const entry = node('div', '', 'billing-payment-entry');

            entry.append(
                node(
                    'strong',
                    `${money(payment.amount)} · ` +
                    `${payment.payment_method === 'cash'
                        ? 'Cash'
                        : 'Online payment'}`
                ),
                node('p', `Status: ${label(payment.payment_status)}`)
            );

            if (payment.receipt_number) {
                entry.appendChild(node(
                    'p',
                    `Receipt: ${payment.receipt_number}`
                ));
            }

            if (payment.payment_date) {
                entry.appendChild(node(
                    'p',
                    `Paid: ${new Date(payment.payment_date).toLocaleString(
                        'en-MY',
                        { timeZone: 'Asia/Kuala_Lumpur' }
                    )} MYT`
                ));
            }

            if (
                payment.payment_status === 'paid' &&
                payment.receipt_number &&
                payment.payment_date
            ) {
                const print = node(
                    'button',
                    'Print receipt',
                    'secondary compact-button'
                );

                print.type = 'button';
                print.disabled = saving;
                print.addEventListener('click', () => {
                    printReceipt(payment);
                });

                entry.appendChild(print);
            }

            section.appendChild(entry);
        }
    }

    async function openEditor(entry) {
        if (saving) return;

        const version = ++detailVersion;

        selected = entry;
        bill = null;
        payments = [];
        get('billing-cash-confirm').checked = false;
        get('billing-cash-notes').value = '';
        get('billing-payment-summary').hidden = true;
        get('billing-balance-summary').hidden = true;
        detailReady = false;
        dirty = false;

        itemContainer.replaceChildren();
        formMessage.textContent = 'Loading saved bill…';
        get('billing-state').textContent = '';
        get('billing-total').textContent = '—';
        get('billing-issue-confirm').checked = false;

        get('billing-dialog-title').textContent =
            `Consultation #${entry.consultation_id}`;

        get('billing-context').textContent =
            `${entry.pet_name} · Owner: ${entry.owner_name}`;

        controls();

        if (!dialog.open) dialog.showModal();

        try {
            let saved = null;

            try {
                saved = await request(
                    `/clinic-billing/consultations/` +
                    `${entry.consultation_id}/bill`
                );
            } catch (error) {
                if (error.status !== 404) throw error;
            }

            const savedPayments = saved
                ? await request(
                    `/clinic-billing/consultations/` +
                    `${entry.consultation_id}/payments`
                )
                : [];

            if (version !== detailVersion || !dialog.open) return;

            if (!Array.isArray(savedPayments)) {
                throw new Error('Unexpected payment response.');
            }

            payments = savedPayments;

            if (saved && !Array.isArray(saved.items)) {
                throw new Error('Unexpected bill response.');
            }

            bill = saved;
            detailReady = true;

            const items = saved?.items ?? [{
                item_type: 'consultation',
                description: 'Consultation fee',
                quantity: 1,
                unit_price: '0.00'
            }];

            items.forEach(addRow);

            get('billing-state').textContent = saved
                ? `Bill #${saved.consultation_bill_id} · ` +
                `${label(saved.status)} · Version ${saved.version}`
                : 'No saved bill yet. Enter the actual charges.';

            formMessage.textContent = saved?.status === 'draft'
                ? 'Save any changes before issuing this bill.'
                : saved
                    ? 'This bill is read-only.'
                    : 'Saving creates a draft. It does not collect payment.';

            dirty = false;
            updatePreview();
            controls();
            renderPayments();

        } catch (error) {
            if (version !== detailVersion || !dialog.open) return;

            detailReady = false;
            controls();

            const retry = node('button', 'Reload bill', 'secondary');
            retry.type = 'button';
            retry.addEventListener('click', () => openEditor(entry));

            formMessage.replaceChildren(
                document.createTextNode(`${error.message} `),
                retry
            );
        }
    }

    async function mutate(path, payload, method = 'POST') {
        if (saving || !selected || !detailReady) return;

        const entry = selected;

        saving = true;
        controls();
        formMessage.textContent = 'Saving and checking bill…';

        let failure = null;

        try {
            await request(path, payload, method);
        } catch (error) {
            failure = error.message;
        } finally {
            saving = false;
            controls();
        }

        // Reload saved state; never automatically repeat a mutation.
        await Promise.all([
            openEditor(entry),
            loadList(page)
        ]);

        if (
            dialog.open &&
            selected?.consultation_id === entry.consultation_id
        ) {
            formMessage.textContent = failure
                ? `${failure}\nCheck the saved bill before trying again.`
                : 'Saved. The latest bill is displayed.';
        }
    }

    get('billing-items').addEventListener('input', changed);

    get('billing-add-item').addEventListener('click', () => {
        if (saving || !editable()) return;

        if (itemContainer.children.length >= 50) {
            formMessage.textContent =
                'A bill can contain at most 50 charges.';
            return;
        }

        addRow();
        changed();
    });

    get('billing-form').addEventListener('submit', event => {
        event.preventDefault();

        if (
            saving ||
            !editable() ||
            !get('billing-form').reportValidity()
        ) return;

        try {
            const { items } = readItems();

            const payload = bill
                ? { items, expected_version: bill.version }
                : { items };

            mutate(
                `/clinic-billing/consultations/` +
                `${selected.consultation_id}/draft`,
                payload,
                bill ? 'PUT' : 'POST'
            );
        } catch (error) {
            formMessage.textContent = error.message;
        }
    });

    get('billing-issue-confirm').addEventListener('change', controls);

    get('billing-issue').addEventListener('click', () => {
        if (
            saving ||
            !detailReady ||
            bill?.status !== 'draft' ||
            dirty ||
            !get('billing-issue-confirm').checked
        ) return;

        mutate(
            `/clinic-billing/consultations/` +
            `${selected.consultation_id}/issue`,
            { expected_version: bill.version }
        );
    });

    for (const id of ['billing-close', 'billing-cancel']) {
        get(id).addEventListener('click', () => {
            if (!saving) dialog.close();
        });
    }

    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        detailVersion++;
        selected = null;
        bill = null;
        detailReady = false;
        dirty = false;
        itemContainer.replaceChildren();
    });

    get('billing-filters').addEventListener('submit', event => {
        event.preventDefault();

        filters = {
            q: get('billing-search').value.trim(),
            status: get('billing-status').value
        };

        loadList(0);
    });

    get('billing-status').addEventListener('change', () => {
        get('billing-filters').requestSubmit();
    });

    get('billing-previous').addEventListener('click', () => {
        if (page > 0) loadList(page - 1);
    });

    get('billing-next').addEventListener('click', () => {
        if ((page + 1) * pageSize < total) loadList(page + 1);
    });

    get('billing-retry').addEventListener('click', () => {
        if (ready) loadList(page);
        else initialize();
    });

    get('logout-button').addEventListener('click', logout);

    async function initialize() {
        if (starting) return;
        starting = true;

        get('billing-message').textContent = 'Loading billing…';
        get('billing-retry').hidden = true;

        try {
            const profile = await request('/admins/me');

            clinicName = profile.clinic_name || '';

            get('topbar-name').textContent = profile.user.full_name;
            get('topbar-avatar').textContent =
                Array.from(profile.user.full_name.trim())[0]
                    ?.toUpperCase() || 'A';

            ready = true;
            await loadList(0);

        } catch (error) {
            get('billing-message').textContent = error.message;
            get('billing-retry').hidden = false;

        } finally {
            starting = false;
        }
    }

    get('billing-cash-confirm').addEventListener(
        'change',
        controls
    );

    get('billing-collect-cash').addEventListener('click', () => {
        if (
            saving ||
            !detailReady ||
            bill?.status !== 'issued' ||
            !get('billing-cash-confirm').checked
        ) return;

        mutate(
            `/clinic-billing/consultations/` +
            `${selected.consultation_id}/collect-cash`,
            {
                expected_version: bill.version,
                expected_amount: String(bill.balance_amount),
                cash_received: true,
                notes: get('billing-cash-notes').value.trim() || null
            }
        );
    });

    initialize();
})();