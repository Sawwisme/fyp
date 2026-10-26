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

    function detailsCell(item) {
        const element = document.createElement('td');
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        const content = document.createElement('div');

        summary.textContent = 'View details';
        content.className = 'clinical-history-detail';

        detail(content, 'Reason', item.reason);
        detail(content, 'Home-care instructions', item.care_instructions);
        detail(content, 'Review findings', item.assessment_information);
        detail(content, 'Notes', item.notes);

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
    let actionMode = 'review';
    let actionBusy = false;
    let actionUncertain = false;

    function openAction(item, mode) {
        if (actionBusy || loading || dialog.open) return;

        selectedFollowup = item;
        actionMode = mode;
        actionUncertain = false;

        actionForm.reset();
        actionFields.disabled = false;
        submitAction.disabled = false;
        actionMessage.textContent = '';

        const reviewing = mode === 'review';

        get('followup-action-title').textContent = reviewing
            ? 'Record Review'
            : 'Cancel Follow-up';

        submitAction.textContent = reviewing
            ? 'Save Review'
            : 'Confirm Cancellation';

        get('followup-action-patient').textContent =
            `${item.pet_name} · Owner: ${item.owner_name}`;

        get('followup-review-fields').hidden = !reviewing;
        get('followup-cancel-fields').hidden = reviewing;

        get('followup-review-findings').required = reviewing;

        const reason = get('followup-cancel-reason');
        reason.required = !reviewing;
        reason.minLength = reviewing ? 0 : 5;

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

        const findings = get('followup-review-findings').value.trim();
        const notes = get('followup-review-notes').value.trim();
        const reason = get('followup-cancel-reason').value.trim();

        if (actionMode === 'review' && !findings) {
            actionMessage.textContent = 'Enter the review findings.';
            get('followup-review-findings').focus();
            return;
        }

        if (actionMode === 'cancel' && reason.length < 5) {
            actionMessage.textContent =
                'Enter a cancellation reason of at least 5 characters.';
            get('followup-cancel-reason').focus();
            return;
        }

        const body = actionMode === 'review'
            ? {
                assessment_information: findings,
                notes: notes || null,
            }
            : { reason };

        actionBusy = true;
        actionFields.disabled = true;
        submitAction.disabled = true;
        get('followup-action-close').disabled = true;
        get('followup-action-dismiss').disabled = true;
        actionMessage.textContent = 'Saving…';

        let succeeded = false;

        try {
            await vetRequest(
                `/followups/${selectedFollowup.followup_care_id}/${actionMode}`,
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
            const visible = data.slice(0, pageSize);

            for (const item of visible) {
                const row = document.createElement('tr');

                row.append(
                    cell(dateLabel(item.recommended_date)),
                    cell(item.pet_name),
                    cell(item.owner_name),
                    cell(
                        item.overdue
                            ? 'Pending — overdue'
                            : item.status.charAt(0).toUpperCase() +
                            item.status.slice(1)
                    ),
                    detailsCell(item)
                );

                const action = document.createElement('td');
                const link = document.createElement('a');

                link.href =
                    `/web/vet/consultation.html?id=${item.consultation_id}`;
                link.textContent = 'View original consultation';

                action.appendChild(link);

                if (item.status === 'pending') {
                    const buttons = document.createElement('div');
                    buttons.className = 'followup-row-actions';

                    const booking = document.createElement('button');
                    booking.type = 'button';
                    booking.className = 'secondary compact-button';
                    booking.textContent = 'Book Appointment';

                    booking.addEventListener('click', () => {
                        openReturnVisitBooking(
                            'followup',
                            item.followup_care_id,
                            () => load(0)
                        );
                    });

                    buttons.appendChild(booking);

                    for (const [mode, label] of [
                        ['review', 'Record Review'],
                        ['cancel', 'Cancel Follow-up'],
                    ]) {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = 'secondary compact-button';
                        button.textContent = label;
                        button.addEventListener(
                            'click',
                            () => openAction(item, mode)
                        );

                        buttons.appendChild(button);
                    }

                    action.appendChild(buttons);
                }

                row.appendChild(action);
                rows.appendChild(row);
            }

            message.textContent = visible.length
                ? `Page ${page + 1} · ${visible.length} follow-up(s).`
                : 'No matching follow-ups.';

            previous.disabled = page === 0;
            next.disabled = data.length <= pageSize;
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