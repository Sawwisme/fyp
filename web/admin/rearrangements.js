(() => {
    const list = document.getElementById('rearrangement-list');
    if (!list) return;

    const message = document.getElementById('rearrangement-message');
    const pageLabel = document.getElementById('rearrangement-page');
    const previous = document.getElementById('rearrangement-previous');
    const next = document.getElementById('rearrangement-next');
    const retry = document.getElementById('rearrangement-retry');

    const pageSize = 5;
    let page = 0;
    let loading = false;
    let initialized = false;

    const resolutionDialog = document.getElementById(
        'rearrangement-resolution-dialog'
    );
    const resolutionForm = document.getElementById(
        'rearrangement-resolution-form'
    );
    const resolutionFields = document.getElementById(
        'rearrangement-resolution-fields'
    );
    const resolutionMessage = document.getElementById(
        'rearrangement-resolution-message'
    );
    const resolutionSave = document.getElementById(
        'rearrangement-resolution-save'
    );
    const resolutionClose = document.getElementById(
        'rearrangement-resolution-close'
    );
    const resolutionCancel = document.getElementById(
        'rearrangement-resolution-cancel'
    );

    let selected = null;
    let saving = false;

    function openResolution(item) {
        const context = window.clinicScheduleContext;
        if (!context || context.isBusy() || saving) return;

        selected = item;
        resolutionForm.reset();
        resolutionMessage.textContent = '';
        resolutionFields.disabled = false;
        resolutionSave.disabled = false;

        document.getElementById(
            'rearrangement-resolution-summary'
        ).textContent =
            `${item.pet_name} · Appointment #${item.appointment_id}`;

        resolutionDialog.showModal();
    }

    function closeResolution() {
        if (!saving) resolutionDialog.close();
    }

    resolutionClose.addEventListener('click', closeResolution);
    resolutionCancel.addEventListener('click', closeResolution);

    resolutionDialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    resolutionForm.addEventListener('submit', async event => {
        event.preventDefault();

        const context = window.clinicScheduleContext;

        if (
            !selected ||
            saving ||
            !context ||
            context.isBusy() ||
            !resolutionForm.reportValidity()
        ) return;

        const note = document.getElementById(
            'rearrangement-resolution-note'
        ).value.trim();

        const agreement = document.getElementById(
            'rearrangement-owner-agreement'
        ).value.trim();

        if (note.length < 5 || agreement.length < 5) {
            resolutionMessage.textContent =
                'Enter at least five characters in both fields.';
            return;
        }

        saving = true;
        context.setBusy(true);
        resolutionFields.disabled = true;
        resolutionSave.disabled = true;
        resolutionClose.disabled = true;
        resolutionCancel.disabled = true;
        resolutionMessage.textContent = 'Saving resolution…';

        try {
            await context.request(
                `/clinic-appointments/rearrangements/` +
                `${selected.affected_id}/resolve`,
                {
                    expected_time_slot_id:
                        selected.current_time_slot_id,
                    expected_appointment_status:
                        selected.appointment_status,
                    resolution_note: note,
                    owner_agreement_note: agreement
                },
                'POST'
            );

            resolutionDialog.close();
        } catch (error) {
            resolutionMessage.textContent =
                error.message +
                ' Close this dialog and reopen the updated record ' +
                'before trying again.';
        } finally {
            saving = false;
            context.setBusy(false);
            resolutionClose.disabled = false;
            resolutionCancel.disabled = false;
            await load();
        }
    });

    function addText(parent, tag, text, className = '') {
        const element = document.createElement(tag);
        element.textContent = text;
        element.className = className;
        parent.appendChild(element);
        return element;
    }

    function displayDate(value) {
        const [year, month, day] = value.split('-');
        return `${day}/${month}/${year}`;
    }

    async function cancelAppointment(item) {
        const context = window.clinicScheduleContext;

        if (!context || context.isBusy() || saving) return;

        const agreed = window.confirm(
            `Cancel appointment #${item.appointment_id} ` +
            `for ${item.pet_name}?\n\n` +
            'Proceed only after confirming cancellation with the owner.'
        );

        if (!agreed) return;

        saving = true;
        context.setBusy(true);
        message.textContent = 'Cancelling appointment…';

        try {
            await context.request(
                `/clinic-appointments/${item.appointment_id}/cancel`,
                undefined,
                'POST'
            );
        } catch (error) {
            window.alert(
                error.message +
                '\nCheck the refreshed appointment before trying again.'
            );
        } finally {
            saving = false;
            context.setBusy(false);
            await load();
        }
    }

    function render(item) {
        const card = document.createElement('article');
        card.className = 'rearrangement-card';

        const heading = document.createElement('div');
        heading.className = 'rearrangement-heading';

        addText(
            heading,
            'strong',
            `${item.pet_name} · ${item.owner_name || 'Owner'}`
        );

        addText(
            heading,
            'span',
            `Appointment #${item.appointment_id}`,
            'muted'
        );

        card.appendChild(heading);

        addText(
            card,
            'p',
            `${displayDate(item.original_date)} · ` +
            `${item.original_start_time.slice(0, 5)}–` +
            `${item.original_end_time.slice(0, 5)} · ` +
            item.absent_vet_name
        );

        addText(
            card,
            'p',
            `Absence: ${item.absence_reason}`,
            'muted'
        );

        if (item.owner_phone) {
            addText(
                card,
                'p',
                `Owner contact: ${item.owner_phone}`,
                'muted'
            );
        }

        const closed = ['cancelled', 'rejected', 'completed']
            .includes(item.appointment_status);

        if (closed) {
            addText(
                card,
                'p',
                `Appointment is ${item.appointment_status}. ` +
                'Resolution record still needs updating.',
                'rearrangement-status'
            );
        } else if (item.booking_changed) {
            addText(
                card,
                'p',
                `Booking moved to ${displayDate(item.current_date)} · ` +
                `${item.current_start_time.slice(0, 5)}–` +
                `${item.current_end_time.slice(0, 5)}. ` +
                'Resolution record still needs updating.',
                'rearrangement-status'
            );
        } else {
            addText(
                card,
                'p',
                'Contact the owner to arrange another time or veterinarian.',
                'rearrangement-status'
            );
        }

        const actions = document.createElement('div');
        actions.className = 'rearrangement-card-actions';

        if (item.can_rearrange) {
            const reschedule = document.createElement('button');
            reschedule.type = 'button';
            reschedule.className = 'secondary compact-button';
            reschedule.textContent = 'Reschedule / change vet';

            reschedule.addEventListener('click', () => {
                const context = window.clinicScheduleContext;

                if (!context || context.isBusy() || saving) return;

                if (
                    typeof window.openRescheduleAppointment !== 'function'
                ) {
                    message.textContent =
                        'The reschedule dialog could not load. ' +
                        'Refresh this page.';
                    return;
                }

                window.openRescheduleAppointment({
                    appointment_id: item.appointment_id,
                    veterinarian_id: item.current_veterinarian_id,
                    pet_name: item.pet_name,
                    vet_name: item.current_vet_name,
                    schedule_date: item.current_date,
                    time:
                        `${item.current_start_time.slice(0, 5)}–` +
                        `${item.current_end_time.slice(0, 5)}`
                });
            });

            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className =
                'secondary compact-button rearrangement-cancel';
            cancel.textContent = 'Cancel appointment';
            cancel.addEventListener(
                'click',
                () => cancelAppointment(item)
            );

            actions.append(reschedule, cancel);
        }

        const canRecordResolution =
            item.booking_changed ||
            ['cancelled', 'rejected'].includes(
                item.appointment_status
            );

        if (canRecordResolution) {
            const resolve = document.createElement('button');
            resolve.type = 'button';
            resolve.className = 'secondary compact-button';
            resolve.textContent = 'Record resolution';
            resolve.addEventListener(
                'click',
                () => openResolution(item)
            );

            actions.appendChild(resolve);
        }

        if (actions.childElementCount) {
            card.appendChild(actions);
        }

        return card;
    }

    async function load(targetPage = page) {
        const context = window.clinicScheduleContext;
        if (!context || loading) return;

        loading = true;
        previous.disabled = true;
        next.disabled = true;
        retry.hidden = true;
        message.textContent = 'Loading affected appointments…';

        try {
            const query = new URLSearchParams({
                pending_only: 'true',
                offset: String(targetPage * pageSize),
                limit: String(pageSize + 1)
            });

            const items = await context.request(
                `/clinic-appointments/rearrangements?${query}`
            );

            if (!Array.isArray(items)) {
                throw new Error('Unexpected rearrangement response.');
            }

            // Return to the previous page if its last record was resolved.
            if (!items.length && targetPage > 0) {
                loading = false;
                return load(targetPage - 1);
            }

            page = targetPage;
            list.replaceChildren(
                ...items.slice(0, pageSize).map(render)
            );

            previous.hidden = page === 0;
            next.hidden = items.length <= pageSize;
            pageLabel.textContent = items.length
                ? `Page ${page + 1}`
                : '';

            message.textContent = items.length
                ? ''
                : 'No appointments awaiting rearrangement.';
        } catch (error) {
            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            loading = false;
            previous.disabled = false;
            next.disabled = false;
        }
    }

    function initialize() {
        if (initialized || !window.clinicScheduleContext) return;
        initialized = true;
        load(0);

        setInterval(() => {
            if (
                !document.hidden &&
                !window.clinicScheduleContext.isBusy()
            ) {
                load();
            }
        }, 60000);
    }

    previous.addEventListener('click', () => load(page - 1));
    next.addEventListener('click', () => load(page + 1));
    retry.addEventListener('click', () => load());

    window.addEventListener('clinic-schedule-ready', initialize);
    window.addEventListener('clinic-schedule-changed', () => load());

    initialize();
})();