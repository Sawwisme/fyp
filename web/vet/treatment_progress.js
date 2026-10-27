(() => {
    const get = id => document.getElementById(id);
    const dialog = get('treatment-progress-dialog');
    const form = get('treatment-progress-form');
    const fields = get('treatment-progress-fields');
    const submit = get('treatment-progress-submit');
    const message = get('treatment-progress-message');
    const consultation = get('treatment-completion-consultation');
    const reason = get('treatment-cancellation-reason');
    const startConsultation = get('treatment-start-consultation');
    const startNotes = get('treatment-start-notes');

    let selected = null;
    let targetStatus = '';
    let refresh = null;
    let busy = false;
    let loading = false;
    let uncertain = false;
    let requestVersion = 0;

    const labels = {
        in_progress: 'Start Treatment',
        completed: 'Complete Treatment',
        cancelled: 'Cancel Plan',
    };

    function dateLabel(value) {
        const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
            ? value
            : `${value}Z`;

        return new Date(normalized).toLocaleString('en-MY', {
            timeZone: 'Asia/Kuala_Lumpur',
            dateStyle: 'medium',
            timeStyle: 'short',
        });
    }

    async function loadConsultations(item, request) {
        const starting = targetStatus === 'in_progress';
        const select = starting ? startConsultation : consultation;
        const endpoint = starting
            ? 'start-consultations'
            : 'completion-consultations';

        loading = true;
        submit.disabled = true;
        select.disabled = true;
        select.replaceChildren(new Option('Loading consultations…', ''));
        message.textContent = 'Loading eligible consultations…';

        try {
            const options = [];
            let offset = 0;

            while (true) {
                const batch = await vetRequest(
                    `/treatment-plans/${item.treatment_id}` +
                    `/${endpoint}?offset=${offset}&limit=100`
                );

                if (request !== requestVersion || !dialog.open) return;

                options.push(...batch);

                if (batch.length < 100) break;
                offset += batch.length;
            }

            select.replaceChildren(
                new Option('Select a consultation', '')
            );

            for (const option of options) {
                select.add(new Option(
                    `#${option.consultation_id} · ` +
                    dateLabel(option.consultation_date) +
                    (
                        option.diagnosis
                            ? ` · ${option.diagnosis.slice(0, 80)}`
                            : ''
                    ),
                    String(option.consultation_id)
                ));
            }

            select.disabled = options.length === 0;
            submit.disabled = options.length === 0;

            message.textContent = options.length
                ? ''
                : starting
                    ? 'No eligible consultations. Start the patient’s ' +
                    'return-visit consultation from Appointments first.'
                    : 'No eligible consultations. Complete the later visit’s ' +
                    'consultation before recording treatment completion.';
        } catch (error) {
            if (request !== requestVersion) return;

            message.textContent =
                `${error.message} Close and reopen this dialog to retry.`;
        } finally {
            if (request === requestVersion) loading = false;
        }
    }

    function openAction(item, status, onRefresh) {
        if (busy || dialog.open) return;

        const request = ++requestVersion;

        selected = item;
        targetStatus = status;
        dialog.dataset.action = status;
        refresh = onRefresh;
        uncertain = false;
        loading = false;

        form.reset();
        fields.disabled = false;
        submit.disabled = false;
        message.textContent = '';

        get('treatment-progress-title').textContent = labels[status];
        submit.textContent = labels[status];

        get('treatment-progress-patient').textContent =
            `${item.pet_name} · ${item.treatment_name}`;

        const starting = status === 'in_progress';
        const completing = status === 'completed';
        const cancelling = status === 'cancelled';

        get('treatment-start-fields').hidden = !starting;
        startConsultation.required = starting;
        startNotes.required = starting;

        get('treatment-completion-fields').hidden = !completing;
        get('treatment-cancellation-fields').hidden = !cancelling;

        consultation.required = completing;
        reason.required = cancelling;
        reason.minLength = cancelling ? 5 : 0;

        get('treatment-progress-explanation').textContent =
            completing
                ? 'Select the later completed consultation where this ' +
                'treatment’s completion was documented.'
                : cancelling
                    ? 'Record why this treatment plan will not proceed.'
                    : 'Mark this treatment as In Progress. ' +
                    'Use this when treatment has started.';

        dialog.showModal();

        if (starting || completing) {
            loadConsultations(item, request);
        }
    }

    function closeDialog() {
        if (!busy) dialog.close();
    }

    get('treatment-progress-close')
        .addEventListener('click', closeDialog);

    get('treatment-progress-dismiss')
        .addEventListener('click', closeDialog);

    dialog.addEventListener('cancel', event => {
        if (busy) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        requestVersion += 1;
        selected = null;

        if (uncertain) {
            uncertain = false;
            refresh?.();
        }
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (busy || loading || uncertain || !selected) return;

        const cancellationReason = reason.value.trim();

        if (
            targetStatus === 'in_progress' &&
            (!startConsultation.value || !startNotes.value.trim())
        ) {
            message.textContent =
                'Select the starting consultation and enter initial notes.';
            return;
        }

        if (
            targetStatus === 'cancelled' &&
            cancellationReason.length < 5
        ) {
            message.textContent =
                'Enter a reason of at least 5 characters.';
            reason.focus();
            return;
        }

        const body = {
            version: selected.progress_version,
            status: targetStatus,
            start_consultation_id:
                targetStatus === 'in_progress'
                    ? Number(startConsultation.value)
                    : null,
            start_notes:
                targetStatus === 'in_progress'
                    ? startNotes.value.trim()
                    : null,
            completion_consultation_id:
                targetStatus === 'completed'
                    ? Number(consultation.value)
                    : null,
            cancellation_reason:
                targetStatus === 'cancelled'
                    ? cancellationReason
                    : null,
        };

        if (
            targetStatus === 'completed' &&
            !body.completion_consultation_id
        ) {
            message.textContent = 'Select a completion consultation.';
            return;
        }

        busy = true;
        fields.disabled = true;
        submit.disabled = true;
        get('treatment-progress-close').disabled = true;
        get('treatment-progress-dismiss').disabled = true;
        message.textContent = 'Saving…';

        let succeeded = false;

        try {
            await vetRequest(
                `/treatment-plans/${selected.treatment_id}/progress`,
                { method: 'PATCH', body }
            );

            succeeded = true;
        } catch (error) {
            uncertain = true;
            message.textContent =
                `${error.message} Close this dialog to refresh the ` +
                'saved status before trying again.';
        } finally {
            busy = false;
            get('treatment-progress-close').disabled = false;
            get('treatment-progress-dismiss').disabled = false;
        }

        if (succeeded) {
            dialog.close();
            refresh?.();
        }
    });

    window.createTreatmentProgressActions = (item, onRefresh) => {
        const root = document.createElement('div');
        root.className = 'treatment-progress-actions';

        if (
            item.consultation_status !== 'completed' ||
            item.progress_version == null ||
            !['planned', 'in_progress'].includes(item.status)
        ) return root;

        root.appendChild(
            createReturnVisitBookingControl(
                'treatment',
                item.treatment_id,
                item.linked_visit,
                onRefresh
            )
        );

        const actions = item.status === 'planned'
            ? ['in_progress', 'completed', 'cancelled']
            : ['completed', 'cancelled'];

        for (const status of actions) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'secondary compact-button';
            button.textContent = labels[status];

            button.addEventListener(
                'click',
                () => openAction(item, status, onRefresh)
            );

            root.appendChild(button);
        }

        return root;
    };
})();