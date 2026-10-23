(() => {
    const dialog = document.createElement('dialog');
    dialog.className = 'reception-dialog reschedule-dialog';
    dialog.setAttribute('aria-labelledby', 'reschedule-title');

    dialog.innerHTML = `
        <header class="schedule-dialog-header">
            <h2 id="reschedule-title">Reschedule Appointment</h2>
            <button id="reschedule-close" type="button"
                    class="dialog-close" aria-label="Close dialog">×</button>
        </header>

        <p id="reschedule-summary"></p>

        <form id="reschedule-form">
            <fieldset id="reschedule-fields">
                <label class="field-label" for="reschedule-vet">
                    Veterinarian
                </label>
                <select id="reschedule-vet" required></select>

                <label class="field-label" for="reschedule-date">
                    New date
                </label>
                <input id="reschedule-date" type="date" required>

                <label class="field-label" for="reschedule-slot">
                    Available slot
                </label>
                <select id="reschedule-slot" required disabled></select>
            </fieldset>

            <p id="reschedule-message" class="message"
               role="status"></p>

            <div class="staff-actions">
                <button id="reschedule-cancel" type="button"
                        class="secondary compact-button">Cancel</button>
                <button id="reschedule-save" type="submit"
                        class="compact-button" disabled>
                    Save changes
                </button>
            </div>
        </form>
    `;

    document.body.appendChild(dialog);

    const field = id => dialog.querySelector(`#${id}`);
    const form = field('reschedule-form');
    const vet = field('reschedule-vet');
    const date = field('reschedule-date');
    const slot = field('reschedule-slot');
    const message = field('reschedule-message');
    const save = field('reschedule-save');

    let appointment = null;
    let saving = false;
    let loading = false;
    let version = 0;

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

    function resetSlots(text) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = text;
        slot.replaceChildren(option);
        slot.disabled = true;
        save.disabled = true;
    }

    async function loadSlots() {
        const currentVersion = ++version;
        loading = true;
        message.textContent = '';
        resetSlots('Loading available slots…');

        if (!vet.value || !date.value || date.value < today()) {
            loading = false;
            resetSlots('Select a veterinarian and valid date');
            return;
        }

        try {
            const query = new URLSearchParams({
                veterinarian_id: vet.value,
                schedule_date: date.value
            });

            const data = await window.clinicScheduleContext.request(
                `/schedules/overview?${query}`
            );

            if (currentVersion !== version || !dialog.open) return;

            const available = data.veterinarians.flatMap(
                item => item.schedules.flatMap(
                    schedule => schedule.time_slots
                )
            ).filter(item => item.can_book_reception);

            resetSlots(
                available.length
                    ? 'Select a new slot'
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

            message.textContent = available.length
                ? 'Your current booking stays reserved until changes are saved.'
                : 'Choose another date or veterinarian.';
        } catch (error) {
            if (currentVersion !== version || !dialog.open) return;

            resetSlots('Could not load slots');
            message.textContent = error.message;
        } finally {
            if (currentVersion === version) loading = false;
        }
    }

    window.openRescheduleAppointment = item => {
        const context = window.clinicScheduleContext;

        if (!context || context.isBusy() || saving || dialog.open) return;

        appointment = item;
        form.reset();
        message.textContent = '';
        date.min = today();
        date.value = item.schedule_date;

        const source = document.getElementById('schedule-vet');
        vet.replaceChildren(
            ...Array.from(source.options, option =>
                option.cloneNode(true)
            )
        );

        vet.value = String(item.veterinarian_id);

        if (!vet.value) {
            vet.value = Array.from(vet.options)
                .find(option => option.value)?.value || '';
        }

        field('reschedule-summary').textContent =
            `${item.pet_name} · ${item.vet_name} · ` +
            `${item.schedule_date} at ${item.time}`;

        dialog.showModal();
        loadSlots();
    };

    vet.addEventListener('change', loadSlots);
    date.addEventListener('change', loadSlots);

    slot.addEventListener('change', () => {
        save.disabled = saving || loading || !slot.value;
    });

    function closeDialog() {
        if (!saving) dialog.close();
    }

    field('reschedule-close').addEventListener('click', closeDialog);
    field('reschedule-cancel').addEventListener('click', closeDialog);

    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        version += 1;
        appointment = null;
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();

        const context = window.clinicScheduleContext;

        if (
            !appointment || saving || loading ||
            context.isBusy() || !slot.value ||
            !form.reportValidity()
        ) {
            return;
        }

        saving = true;
        context.setBusy(true);
        field('reschedule-fields').disabled = true;
        field('reschedule-close').disabled = true;
        field('reschedule-cancel').disabled = true;
        save.disabled = true;
        message.textContent = 'Saving changes…';

        try {
            await context.request(
                `/clinic-appointments/${appointment.appointment_id}/reschedule`,
                { time_slot_id: Number(slot.value) },
                'POST'
            );

            document.getElementById('overview-date').value = date.value;
            document.getElementById('overview-vet').value = '';

            dialog.close();

            window.dispatchEvent(
                new Event('clinic-schedule-changed')
            );
        } catch (error) {
            message.textContent = error.message;
        } finally {
            saving = false;
            context.setBusy(false);
            field('reschedule-fields').disabled = false;
            field('reschedule-close').disabled = false;
            field('reschedule-cancel').disabled = false;
            save.disabled = loading || !slot.value;
        }
    });
})();