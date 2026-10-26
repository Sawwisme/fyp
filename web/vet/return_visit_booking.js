(() => {
    const dialog = document.createElement('dialog');
    dialog.id = 'return-visit-dialog';
    dialog.setAttribute('aria-labelledby', 'return-visit-title');

    // Static markup only. Patient data is assigned with textContent.
    dialog.innerHTML = `
        <form id="return-visit-form">
            <div class="return-visit-heading">
                <h2 id="return-visit-title">Book Return Visit</h2>
                <button id="return-visit-close" type="button"
                        aria-label="Close dialog">×</button>
            </div>

            <p id="return-visit-patient"></p>
            <p id="return-visit-vet" class="muted"></p>

            <fieldset id="return-visit-fields" disabled>
                <label for="return-visit-date">Appointment date</label>
                <input id="return-visit-date" type="date" required>

                <label for="return-visit-slot">Available time</label>
                <select id="return-visit-slot" required disabled>
                    <option value="">Select a date first</option>
                </select>
            </fieldset>

            <p id="return-visit-message"
               role="status" aria-live="polite"></p>

            <a id="return-visit-existing"
               href="/web/vet/appointments.html" hidden>
                View appointments
            </a>

            <div class="return-visit-footer">
                <button id="return-visit-dismiss" type="button">
                    Cancel
                </button>
                <button id="return-visit-submit" type="submit" disabled>
                    Book Appointment
                </button>
            </div>
        </form>
    `;

    document.body.appendChild(dialog);

    const get = id => document.getElementById(id);
    const form = get('return-visit-form');
    const fields = get('return-visit-fields');
    const date = get('return-visit-date');
    const slot = get('return-visit-slot');
    const message = get('return-visit-message');
    const submit = get('return-visit-submit');

    let context = null;
    let sourceType = '';
    let sourceId = null;
    let refresh = null;
    let busy = false;
    let uncertain = false;
    let generation = 0;
    let slotRequest = 0;

    function today() {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).formatToParts(new Date());

        const value = type =>
            parts.find(part => part.type === type).value;

        return `${value('year')}-${value('month')}-${value('day')}`;
    }

    async function loadSlots() {
        const request = ++slotRequest;
        const opened = generation;

        slot.replaceChildren(new Option('Loading times…', ''));
        slot.disabled = true;
        submit.disabled = true;

        if (
            !context ||
            !date.value ||
            date.value < today() ||
            context.existing_appointment_id
        ) {
            slot.replaceChildren(new Option('Choose a valid date', ''));
            return;
        }

        message.textContent = 'Loading available times…';

        try {
            const available = [];
            let offset = 0;

            while (true) {
                const query = new URLSearchParams({
                    appointment_date: date.value,
                    offset: String(offset),
                    limit: '100',
                });

                const batch = await vetRequest(
                    `/return-visits/slots?${query}`
                );

                if (
                    request !== slotRequest ||
                    opened !== generation ||
                    !dialog.open
                ) return;

                available.push(...batch);

                if (batch.length < 100) break;
                offset += batch.length;
            }

            slot.replaceChildren(new Option('Select a time', ''));

            for (const item of available) {
                slot.add(new Option(
                    `${item.start_time.slice(0, 5)}–` +
                    item.end_time.slice(0, 5),
                    String(item.time_slot_id)
                ));
            }

            slot.disabled = available.length === 0;
            message.textContent = available.length
                ? 'All times use Malaysia time.'
                : 'No available times for this date. Choose another date.';
        } catch (error) {
            if (
                request !== slotRequest ||
                opened !== generation
            ) return;

            slot.replaceChildren(new Option('Times unavailable', ''));
            message.textContent =
                `${error.message} Choose a date again to retry.`;
        }
    }

    window.openReturnVisitBooking = async (
        type, id, onRefresh
    ) => {
        if (busy || dialog.open) return;

        const opened = ++generation;
        sourceType = type;
        sourceId = id;
        refresh = onRefresh;
        context = null;
        uncertain = false;

        form.reset();
        fields.disabled = true;
        slot.disabled = true;
        submit.disabled = true;
        slot.replaceChildren(new Option('Select a date first', ''));

        get('return-visit-patient').textContent = '';
        get('return-visit-vet').textContent = '';
        get('return-visit-existing').hidden = true;
        message.textContent = 'Loading return-visit details…';

        dialog.showModal();

        try {
            const query = new URLSearchParams({
                source_type: type,
                source_id: String(id),
            });

            const data = await vetRequest(
                `/return-visits/context?${query}`
            );

            if (opened !== generation || !dialog.open) return;

            context = data;

            get('return-visit-patient').textContent =
                `${data.pet_name} · Owner: ${data.owner_name}`;
            get('return-visit-vet').textContent =
                `Veterinarian: ${data.veterinarian_name}`;

            if (data.existing_appointment_id) {
                message.textContent =
                    `Appointment #${data.existing_appointment_id} ` +
                    'is already linked. Manage that appointment ' +
                    'before booking another.';

                get('return-visit-existing').hidden = false;
                return;
            }

            date.min = today();
            date.value =
                data.recommended_date &&
                    data.recommended_date >= today()
                    ? data.recommended_date
                    : today();

            fields.disabled = false;
            await loadSlots();
        } catch (error) {
            if (opened !== generation) return;

            message.textContent =
                `${error.message} Close and reopen to retry.`;
        }
    };

    date.addEventListener('change', loadSlots);

    slot.addEventListener('change', () => {
        submit.disabled = !slot.value || busy || uncertain;
    });

    function closeDialog() {
        if (!busy) dialog.close();
    }

    get('return-visit-close')
        .addEventListener('click', closeDialog);
    get('return-visit-dismiss')
        .addEventListener('click', closeDialog);

    dialog.addEventListener('cancel', event => {
        if (busy) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        generation += 1;
        slotRequest += 1;
        context = null;

        if (uncertain) {
            uncertain = false;
            refresh?.();
        }
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (
            busy ||
            uncertain ||
            !context ||
            !slot.value ||
            context.existing_appointment_id
        ) return;

        const body = {
            pet_owner_id: context.pet_owner_id,
            pet_id: context.pet_id,
            time_slot_id: Number(slot.value),
            appointment_source: 'reception',
            appointment_type:
                sourceType === 'followup' ? 'follow_up' : 'consultation',
            planned_treatment_id:
                sourceType === 'treatment' ? sourceId : null,
            followup_care_id:
                sourceType === 'followup' ? sourceId : null,
        };

        busy = true;
        fields.disabled = true;
        submit.disabled = true;
        get('return-visit-close').disabled = true;
        get('return-visit-dismiss').disabled = true;
        message.textContent = 'Booking appointment…';

        let succeeded = false;

        try {
            await vetRequest('/return-visits', {
                method: 'POST',
                body,
            });

            succeeded = true;
        } catch (error) {
            uncertain = true;
            message.textContent =
                `${error.message} Close and reopen this dialog ` +
                'to check for an existing booking before trying again.';
        } finally {
            busy = false;
            get('return-visit-close').disabled = false;
            get('return-visit-dismiss').disabled = false;
        }

        if (succeeded) {
            dialog.close();
            refresh?.();
        }
    });
})();