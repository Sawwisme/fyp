(() => {
    const panel = document.getElementById('emergency-view');

    panel.innerHTML = `
        <div class="staff-list-toolbar">
            <div>
                <label class="field-label" for="emergency-status">
                    Request status
                </label>
                <select id="emergency-status">
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                    <option value="cancelled">Cancelled</option>
                </select>
            </div>
        </div>

        <p class="muted">
            Requests are for your clinic. The calendar date and vet
            filters above do not apply to this list.
        </p>

        <p id="emergency-action" class="message" role="status"></p>
        <p id="emergency-list-message" role="status"></p>

        <button id="emergency-retry" type="button"
                class="secondary compact-button" hidden>Try again</button>

        <div id="emergency-list"></div>
    `;

    const get = id => document.getElementById(id);
    const list = get('emergency-list');
    const listMessage = get('emergency-list-message');
    const action = get('emergency-action');
    const status = get('emergency-status');
    const retry = get('emergency-retry');

    let context;
    let listVersion = 0;
    let slotVersion = 0;
    let saving = false;
    let slotsLoading = false;
    let currentRequest = null;
    let mode = 'approve';

    const dialog = document.createElement('dialog');
    dialog.className = 'reception-dialog emergency-dialog';
    dialog.setAttribute('aria-labelledby', 'emergency-dialog-title');

    dialog.innerHTML = `
        <header class="schedule-dialog-header">
            <h2 id="emergency-dialog-title"></h2>
            <button id="emergency-close" type="button"
                    class="dialog-close" aria-label="Close dialog">×</button>
        </header>

        <p id="emergency-dialog-summary"></p>

        <form id="emergency-decision-form">
            <fieldset id="emergency-decision-fields">
                <fieldset id="emergency-assign-fields">
                    <label class="field-label" for="emergency-vet">
                        Veterinarian
                    </label>
                    <select id="emergency-vet" required></select>

                    <label class="field-label" for="emergency-date">
                        Date
                    </label>
                    <input id="emergency-date" type="date" required>

                    <label class="field-label" for="emergency-slot">
                        Available slot
                    </label>
                    <select id="emergency-slot" required disabled></select>

                    <label class="field-label" for="emergency-urgency">
                        Urgency recorded by clinic staff
                    </label>
                    <select id="emergency-urgency">
                        <option value="urgent">Urgent</option>
                        <option value="critical">Critical</option>
                    </select>
                </fieldset>

                <fieldset id="emergency-reject-fields" hidden disabled>
                    <label class="field-label" for="emergency-reason">
                        Reason for declining
                    </label>
                    <textarea id="emergency-reason" rows="4"
                              minlength="5" maxlength="1000"
                              required></textarea>
                </fieldset>
            </fieldset>

            <p id="emergency-dialog-message"
               class="message" role="status"></p>

            <div class="staff-actions">
                <button id="emergency-cancel" type="button"
                        class="secondary compact-button">Cancel</button>
                <button id="emergency-save" type="submit"
                        class="compact-button">Save</button>
            </div>
        </form>
    `;

    document.body.appendChild(dialog);

    const form = get('emergency-decision-form');
    const vet = get('emergency-vet');
    const date = get('emergency-date');
    const slot = get('emergency-slot');
    const save = get('emergency-save');
    const dialogMessage = get('emergency-dialog-message');

    function today() {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(new Date());

        const value = type =>
            parts.find(part => part.type === type).value;

        return `${value('year')}-${value('month')}-${value('day')}`;
    }

    function text(tag, value, className) {
        const element = document.createElement(tag);
        element.textContent = value;
        if (className) element.className = className;
        return element;
    }

    async function loadRequests() {
        context = window.clinicScheduleContext;
        if (!context) return;

        const version = ++listVersion;
        const selectedStatus = status.value;

        list.replaceChildren();
        retry.hidden = true;
        listMessage.textContent = 'Loading emergency requests…';

        try {
            const records = [];

            for (let offset = 0; ; offset += 100) {
                const query = new URLSearchParams({
                    request_status: selectedStatus,
                    offset: String(offset),
                    limit: '100'
                });

                const page = await context.request(
                    `/emergency-requests/clinic?${query}`
                );

                if (version !== listVersion) return;

                records.push(...page);
                if (page.length < 100) break;
            }

            for (const item of records) {
                const card = document.createElement('article');
                card.className = 'emergency-request-card';

                card.append(
                    text('h3', item.pet_name),
                    text('p',
                        `${item.owner_name} · ` +
                        (item.owner_phone || 'Phone not provided')),
                    text('p', item.emergency_reason, 'emergency-request-reason'),
                    text('p',
                        `Status: ${item.approval_status} · ` +
                        `Urgency: ${item.urgency_level}`)
                );

                if (item.rejection_reason) {
                    card.appendChild(text(
                        'p', `Reason: ${item.rejection_reason}`
                    ));
                }

                if (item.appointment_id) {
                    card.appendChild(text(
                        'p', `Appointment #${item.appointment_id}`
                    ));
                }

                if (item.approval_status === 'pending') {
                    const actions = document.createElement('div');
                    actions.className = 'staff-actions';

                    for (const [decision, label] of [
                        ['approve', 'Assign slot'],
                        ['reject', 'Reject']
                    ]) {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = 'secondary compact-button';
                        button.textContent = label;
                        button.disabled = saving;
                        button.addEventListener(
                            'click', () => openDecision(item, decision)
                        );
                        actions.appendChild(button);
                    }

                    card.appendChild(actions);
                }

                list.appendChild(card);
            }

            listMessage.textContent = records.length
                ? `${records.length} ${selectedStatus} request(s).`
                : `No ${selectedStatus} emergency requests.`;
        } catch (error) {
            if (version !== listVersion) return;
            listMessage.textContent = error.message;
            retry.hidden = false;
        }
    }

    function resetSlots(label) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = label;
        slot.replaceChildren(option);
        slot.disabled = true;
        save.disabled = true;
    }

    async function loadSlots() {
        const version = ++slotVersion;
        slotsLoading = true;
        resetSlots('Loading slots…');
        dialogMessage.textContent = '';

        if (!vet.value || !date.value || date.value < today()) {
            slotsLoading = false;
            resetSlots('Select a veterinarian and valid date');
            return;
        }

        try {
            const query = new URLSearchParams({
                veterinarian_id: vet.value,
                schedule_date: date.value
            });

            const data = await context.request(
                `/schedules/overview?${query}`
            );

            if (version !== slotVersion || !dialog.open) return;

            const available = data.veterinarians.flatMap(
                item => item.schedules.flatMap(
                    schedule => schedule.time_slots
                )
            ).filter(item =>
                item.can_book_walk_in || item.can_book_reception
            );

            resetSlots(
                available.length
                    ? 'Select an available slot'
                    : 'No available slots'
            );

            for (const item of available) {
                const option = document.createElement('option');
                option.value = item.time_slot_id;
                option.textContent =
                    `${item.start_time.slice(0, 5)}–` +
                    item.end_time.slice(0, 5);
                slot.appendChild(option);
            }

            slot.disabled = available.length === 0;

            if (!available.length) {
                dialogMessage.textContent =
                    'Choose another date or veterinarian. ' +
                    'Existing bookings will not be displaced.';
            }
        } catch (error) {
            if (version !== slotVersion || !dialog.open) return;
            resetSlots('Could not load slots');
            dialogMessage.textContent = error.message;
        } finally {
            if (version === slotVersion) slotsLoading = false;
        }
    }

    function openDecision(item, decision) {
        context = window.clinicScheduleContext;

        if (!context || context.isBusy() || saving || dialog.open) return;

        currentRequest = item;
        mode = decision;
        form.reset();
        dialogMessage.textContent = '';

        const approving = mode === 'approve';

        get('emergency-dialog-title').textContent = approving
            ? 'Assign Emergency Appointment'
            : 'Reject Emergency Request';

        get('emergency-dialog-summary').textContent =
            `${item.pet_name} · ${item.owner_name}\n` +
            item.emergency_reason;

        get('emergency-assign-fields').hidden = !approving;
        get('emergency-assign-fields').disabled = !approving;
        get('emergency-reject-fields').hidden = approving;
        get('emergency-reject-fields').disabled = approving;

        save.textContent = approving
            ? 'Approve and book slot'
            : 'Reject request';
        save.disabled = approving;

        dialog.showModal();

        if (approving) {
            const source = get('schedule-vet');
            vet.replaceChildren(
                ...Array.from(source.options, option =>
                    option.cloneNode(true)
                )
            );

            vet.value = Array.from(vet.options)
                .find(option => option.value)?.value || '';

            date.min = today();
            date.value = today();
            loadSlots();
        }
    }

    vet.addEventListener('change', loadSlots);
    date.addEventListener('change', loadSlots);

    slot.addEventListener('change', () => {
        save.disabled = saving || slotsLoading || !slot.value;
    });

    function closeDialog() {
        if (!saving) dialog.close();
    }

    get('emergency-close').addEventListener('click', closeDialog);
    get('emergency-cancel').addEventListener('click', closeDialog);

    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        slotVersion += 1;
        slotsLoading = false;
        currentRequest = null;
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (!currentRequest || saving || context.isBusy()) return;

        if (
            mode === 'approve' &&
            (slotsLoading || !slot.value)
        ) return;

        if (!form.reportValidity()) return;

        const reason = get('emergency-reason').value.trim();

        if (mode === 'reject' && reason.length < 5) {
            dialogMessage.textContent =
                'Enter a rejection reason of at least 5 characters.';
            return;
        }

        const id = currentRequest.emergency_appointment_id;
        const approving = mode === 'approve';
        const selectedDate = date.value;

        const body = approving
            ? {
                time_slot_id: Number(slot.value),
                urgency_level: get('emergency-urgency').value
            }
            : { rejection_reason: reason };

        saving = true;
        context.setBusy(true);
        get('emergency-decision-fields').disabled = true;
        get('emergency-close').disabled = true;
        get('emergency-cancel').disabled = true;
        status.disabled = true;
        save.disabled = true;
        dialogMessage.textContent = 'Saving decision…';

        try {
            await context.request(
                `/emergency-requests/${id}/${mode}`,
                body,
                'POST'
            );

            if (approving) {
                get('overview-date').value = selectedDate;
                get('overview-vet').value = '';
            }

            dialog.close();
            action.textContent = approving
                ? 'Emergency appointment booked successfully.'
                : 'Emergency request rejected.';
            action.classList.add('success');

            window.dispatchEvent(new Event('clinic-schedule-changed'));
        } catch (error) {
            dialogMessage.textContent = error.message;
        } finally {
            saving = false;
            context.setBusy(false);
            get('emergency-decision-fields').disabled = false;
            get('emergency-close').disabled = false;
            get('emergency-cancel').disabled = false;
            status.disabled = false;
            save.disabled = mode === 'approve'
                && (slotsLoading || !slot.value);

            await loadRequests();
        }
    });

    status.addEventListener('change', loadRequests);
    retry.addEventListener('click', loadRequests);
    window.addEventListener('clinic-emergency-open', loadRequests);

    setInterval(() => {
        if (
            !document.hidden &&
            !panel.hidden &&
            !saving &&
            !dialog.open
        ) {
            loadRequests();
        }
    }, 30000);
})();