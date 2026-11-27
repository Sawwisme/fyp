(() => {
    const get = id => document.getElementById(id);
    const search = get('followups-search');
    const status = get('followups-status');
    const rows = get('followups-rows');
    const message = get('followups-message');
    const retry = get('followups-retry');
    const previous = get('followups-previous');
    const next = get('followups-next');

    const pageSize = 20;
    let page = 0;
    let version = 0;
    let ready = false;
    let loading = false;
    let timer;

    function cell(value) {
        const element = document.createElement('td');
        element.textContent = value || '—';
        return element;
    }

    function dateLabel(value) {
        if (!value) return 'Not recorded';

        const [year, month, day] = value.split('-');
        return `${day}/${month}/${year}`;
    }

    function detail(parent, label, value) {
        const paragraph = document.createElement('p');
        const heading = document.createElement('strong');

        heading.textContent = `${label}: `;
        paragraph.append(
            heading,
            document.createTextNode(value || 'Not recorded')
        );
        parent.appendChild(paragraph);
    }

    function statusCell(item) {
        const td = document.createElement('td');
        const badge = document.createElement('span');

        const state = item.overdue ? 'overdue' : item.status;
        badge.className = `followup-status followup-status-${state}`;

        badge.textContent = {
            overdue: 'Overdue',
            pending: 'Pending',
            completed: 'Completed',
            cancelled: 'Cancelled',
        }[state] || state;

        td.appendChild(badge);
        return td;
    }

    function detailsCell(item) {
        const element = document.createElement('td');
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        const content = document.createElement('div');

        summary.textContent = 'View details';
        content.className = 'clinical-history-detail';

        detail(content, 'Reason', item.reason);
        detail(content, 'Home-care instructions', item.care_instructions);
        detail(
            content,
            'Owner photos required',
            item.photos_required ? 'Yes' : 'No'
        );

        if (item.photos_required) {
            detail(content, 'Photo requirements', item.photo_instructions);
        }

        detail(
            content,
            'In-clinic review required',
            item.visit_required ? 'Yes' : 'No'
        );
        detail(content, 'Review findings', item.assessment_information);
        detail(content, 'Notes', item.notes);

        content.appendChild(
            createLinkedVisitDetails(item.linked_visit, 'followup')
        );

        details.append(summary, content);
        element.appendChild(details);
        return element;
    }

    const dialog = get('followup-action-dialog');
    const actionForm = get('followup-action-form');
    const actionFields = get('followup-action-fields');
    const submitAction = get('followup-action-submit');
    const actionMessage = get('followup-action-message');

    let selectedFollowup = null;
    let actionBusy = false;
    let actionUncertain = false;

    function openAction(item, mode) {
        if (
            mode !== 'cancel' ||
            actionBusy ||
            loading ||
            dialog.open
        ) return;

        selectedFollowup = item;
        actionUncertain = false;

        actionForm.reset();
        actionFields.disabled = false;
        submitAction.disabled = false;
        actionMessage.textContent = '';

        get('followup-action-title').textContent = 'Cancel follow-up';
        submitAction.textContent = 'Confirm cancellation';

        get('followup-action-patient').textContent =
            `${item.pet_name} · Owner: ${item.owner_name}`;

        const reason = get('followup-cancel-reason');
        reason.required = true;
        reason.minLength = 5;

        dialog.showModal();
    }

    function closeAction() {
        if (!actionBusy) dialog.close();
    }

    get('followup-action-close').addEventListener('click', closeAction);
    get('followup-action-dismiss').addEventListener('click', closeAction);

    dialog.addEventListener('cancel', event => {
        if (actionBusy) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        selectedFollowup = null;

        // A failed response might still have committed on the server.
        if (actionUncertain) {
            actionUncertain = false;
            load(0);
        }
    });

    actionForm.addEventListener('submit', async event => {
        event.preventDefault();

        if (
            actionBusy ||
            actionUncertain ||
            !selectedFollowup
        ) return;

        const reason = get('followup-cancel-reason').value.trim();

        if (reason.length < 5) {
            actionMessage.textContent =
                'Enter a cancellation reason of at least 5 characters.';
            get('followup-cancel-reason').focus();
            return;
        }

        const body = { reason };

        actionBusy = true;
        actionFields.disabled = true;
        submitAction.disabled = true;
        get('followup-action-close').disabled = true;
        get('followup-action-dismiss').disabled = true;
        actionMessage.textContent = 'Saving…';

        let succeeded = false;

        try {
            await vetRequest(
                `/followups/${selectedFollowup.followup_care_id}/cancel`,
                { method: 'POST', body }
            );

            succeeded = true;
        } catch (error) {
            actionUncertain = true;
            actionMessage.textContent =
                `${error.message} Close this dialog to refresh the list ` +
                'and check the saved status before trying again.';
        } finally {
            actionBusy = false;
            get('followup-action-close').disabled = false;
            get('followup-action-dismiss').disabled = false;
        }

        if (succeeded) {
            dialog.close();
            await load(0);
        }
    });

    async function load(targetPage = 0) {
        if (!ready) return;

        const request = ++version;
        loading = true;
        previous.disabled = true;
        next.disabled = true;
        retry.hidden = true;
        rows.replaceChildren();
        message.textContent = 'Loading follow-ups…';

        const query = new URLSearchParams({
            status: status.value,
            offset: String(targetPage * pageSize),
            limit: String(pageSize + 1),
        });

        if (search.value.trim()) {
            query.set('search', search.value.trim());
        }

        try {
            const data = await vetRequest(`/followups?${query}`);

            if (request !== version) return;

            page = targetPage;
            get('followups-page-label').textContent = `Page ${page + 1}`;
            const visible = data.slice(0, pageSize);

            for (const item of visible) {
                const row = document.createElement('tr');

                row.append(
                    cell(dateLabel(item.recommended_date)),
                    cell(item.pet_name),
                    cell(item.owner_name),
                    statusCell(item),
                    detailsCell(item)
                );

                const action = document.createElement('td');
                const toolbar = document.createElement('div');
                toolbar.className = 'followup-action-toolbar';

                const updates = document.createElement('button');
                updates.type = 'button';
                updates.className = 'secondary compact-button';
                updates.textContent = 'View updates';
                updates.addEventListener('click', () => {
                    openFollowupUpdates(item, () => load(page));
                });

                const menu = document.createElement('div');
                menu.className = 'followup-more';

                const summary = document.createElement('button');
                summary.type = 'button';
                summary.className = 'followup-more-trigger';
                summary.textContent = 'More actions ⋯';
                summary.setAttribute('aria-expanded', 'false');

                const options = document.createElement('div');
                options.className = 'followup-more-options';
                options.setAttribute('popover', 'auto');

                summary.addEventListener('click', () => {
                    if (options.matches(':popover-open')) {
                        options.hidePopover();
                        return;
                    }

                    options.showPopover();

                    const rect = summary.getBoundingClientRect();
                    const width = options.offsetWidth;
                    const height = options.offsetHeight;

                    const left = Math.max(
                        12,
                        Math.min(rect.right - width, window.innerWidth - width - 12)
                    );

                    let top = rect.bottom + 6;

                    if (top + height > window.innerHeight - 12) {
                        top = Math.max(12, rect.top - height - 6);
                    }

                    options.style.left = `${left}px`;
                    options.style.top = `${top}px`;
                });

                options.addEventListener('toggle', () => {
                    summary.setAttribute(
                        'aria-expanded',
                        String(options.matches(':popover-open'))
                    );
                });

                options.addEventListener('click', event => {
                    if (event.target.closest('button, a')) {
                        options.hidePopover();
                    }
                });

                const link = document.createElement('a');
                link.href =
                    `/web/vet/consultation.html?id=${item.consultation_id}`;
                link.textContent = 'View original consultation';
                options.appendChild(link);

                if (item.status === 'pending') {

                    for (const [mode, label] of [
                        ['cancel', 'Cancel follow-up'],
                    ]) {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.textContent = label;
                        button.className = mode === 'cancel'
                            ? 'followup-menu-danger'
                            : '';

                        button.addEventListener('click', () => {
                            options.hidePopover();
                            openAction(item, mode);
                        });

                        options.appendChild(button);
                    }
                }

                menu.append(summary, options);
                toolbar.append(updates, menu);
                action.appendChild(toolbar);
                row.appendChild(action);
                rows.appendChild(row);
            }

            message.textContent = visible.length
                ? `Page ${page + 1} · ${visible.length} follow-up(s).`
                : 'No matching follow-ups.';

            previous.disabled = page === 0;
            next.disabled = data.length <= pageSize;
            const showPagination = page > 0 || data.length > pageSize;
            previous.hidden = !showPagination;
            next.hidden = !showPagination;
        } catch (error) {
            if (request !== version) return;

            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (request === version) loading = false;
        }
    }

    search.addEventListener('input', () => {
        clearTimeout(timer);
        version += 1;
        previous.disabled = true;
        next.disabled = true;
        timer = setTimeout(() => load(0), 300);
    });

    status.addEventListener('change', () => {
        clearTimeout(timer);
        load(0);
    });

    previous.addEventListener('click', () => {
        if (!loading && page > 0) load(page - 1);
    });

    next.addEventListener('click', () => {
        if (!loading) load(page + 1);
    });

    retry.addEventListener('click', () => load(0));

    vetReady.then(profile => {
        if (!profile) return;

        ready = true;
        load(0);
    });
})();