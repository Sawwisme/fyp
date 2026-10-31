(() => {
    const dateInput = document.getElementById('overview-date');
    const vetFilter = document.getElementById('overview-vet');
    const message = document.getElementById('overview-message');
    const content = document.getElementById('overview-content');
    const appointmentCount =
        document.getElementById('overview-appointments');
    const availableCount =
        document.getElementById('overview-available');
    const blockedCount =
        document.getElementById('overview-blocked');

    const editorButtons = [
        ...document.querySelectorAll('[data-schedule-editor]')
    ];

    const closeButton =
        document.getElementById('close-schedule-editor');

    closeButton.hidden = true;

    let context = null;
    let requestVersion = 0;
    let initialized = false;
    let vetsLoaded = false;

    const panels = {
        automatic: [
            document.getElementById('auto-schedule-form')
                .closest('section')
        ],
        multiple: [
            document.getElementById('bulk-schedule-form')
                .closest('section')
        ],
        individual: [
            document.getElementById('schedule-form')
                .closest('section'),
            document.getElementById('schedule-list')
                .closest('section')
        ]
    };

    const titles = {
        automatic: 'Automatic Scheduling',
        multiple: 'Assign Multiple Vets',
        individual: 'Manage Vet Schedule'
    };

    const editorDialogs = {};

    for (const [name, sections] of Object.entries(panels)) {
        const dialog = document.createElement('dialog');
        dialog.className = 'schedule-editor-dialog';
        dialog.setAttribute('aria-labelledby', `editor-title-${name}`);

        const header = document.createElement('div');
        header.className = 'schedule-dialog-header';

        const title = document.createElement('h2');
        title.id = `editor-title-${name}`;
        title.textContent = titles[name];

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'dialog-close';
        close.setAttribute('aria-label', 'Close dialog');
        close.textContent = '×';

        function dismiss() {
            if (!context || context.isBusy()) return;
            dialog.close();
        }

        close.addEventListener('click', dismiss);
        header.append(title, close);
        dialog.appendChild(header);

        sections.forEach((section, index) => {
            section.hidden = false;

            if (index === 0) {
                const oldHeading = section.querySelector('h2');
                if (oldHeading) oldHeading.hidden = true;
            }

            dialog.appendChild(section);
        });

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.className = 'secondary compact-button';
        cancel.textContent = 'Cancel';
        cancel.addEventListener('click', dismiss);

        if (name === 'individual') {
            const footer = document.createElement('div');
            footer.className = 'staff-actions';
            footer.appendChild(cancel);
            dialog.appendChild(footer);
        } else {
            const actions = sections[0].querySelector('.staff-actions');
            actions.prepend(cancel);
        }

        dialog.addEventListener('cancel', event => {
            if (context?.isBusy()) event.preventDefault();
        });

        dialog.addEventListener('close', () => {
            const button = editorButtons.find(
                item => item.dataset.scheduleEditor === name
            );

            button?.setAttribute('aria-expanded', 'false');
        });

        document.body.appendChild(dialog);
        editorDialogs[name] = dialog;
    }

    function closeEditors() {
        if (context?.isBusy()) return;

        Object.values(editorDialogs).forEach(dialog => {
            if (dialog.open) dialog.close();
        });
    }

    async function openEditor(
        name,
        selectedDate = dateInput.value,
        selectedVet = vetFilter.value
    ) {
        if (!context || context.isBusy()) return;

        const dialog = editorDialogs[name];
        if (!dialog) return;

        closeEditors();

        if (name === 'individual') {
            document.getElementById('schedule-date').value =
                selectedDate;

            document.getElementById('schedule-form').hidden = true;

            document.getElementById('toggle-add-schedule')
                .setAttribute('aria-expanded', 'false');

            const individualVet =
                document.getElementById('schedule-vet');

            if (
                selectedVet &&
                [...individualVet.options].some(
                    option => option.value === String(selectedVet)
                )
            ) {
                individualVet.value = String(selectedVet);
            }
        }

        if (name === 'multiple') {
            for (const id of ['bulk-start-date', 'bulk-end-date']) {
                const input = document.getElementById(id);
                if (!input.value) input.value = input.min;
            }
        }

        dialog.showModal();

        const button = editorButtons.find(
            item => item.dataset.scheduleEditor === name
        );

        button?.setAttribute('aria-expanded', 'true');

        if (name === 'individual') {
            await context.refreshSchedules();
        }
    }

    editorButtons.forEach(button => {
        button.addEventListener('click', () => {
            openEditor(button.dataset.scheduleEditor);
        });
    });

    closeButton.addEventListener('click', closeEditors);

    // Also used when opening an individual vet from the calendar.
    window.openClinicScheduleEditor = openEditor;

    function renderOverview(data) {
        appointmentCount.textContent = data.summary.appointments;
        availableCount.textContent = data.summary.available_slots;
        blockedCount.textContent = data.summary.blocked_slots;
        content.replaceChildren();

        window.clinicLastOverview = data;

        window.dispatchEvent(
            new CustomEvent('clinic-overview-loaded', {
                detail: data
            })
        );

        if (!vetsLoaded) {
            for (const vet of data.veterinarians) {
                const option = document.createElement('option');
                option.value = vet.veterinarian_id;
                option.textContent = vet.full_name;
                vetFilter.appendChild(option);
            }

            vetsLoaded = true;
        }

        message.textContent =
            `Counts for ${data.schedule_date}. ` +
            'Cancelled and rejected appointments are excluded from the cards.';

        for (const vet of data.veterinarians) {
            const details = document.createElement('details');
            details.className = 'overview-vet-entry';

            const summary = document.createElement('summary');

            const name = document.createElement('strong');
            name.textContent = vet.full_name;

            const description = document.createElement('span');
            description.className = 'overview-vet-description';

            const hasActiveSchedule = vet.schedules.some(
                schedule => schedule.status === 'active'
            );

            description.textContent = hasActiveSchedule
                ? `${vet.appointment_count} appointments · ${vet.available_slots} available`
                : 'No active schedule';

            summary.append(name, description);

            details.appendChild(summary);

            if (!vet.schedules.length) {
                const empty = document.createElement('p');
                empty.className = 'muted';
                empty.textContent = 'No schedule on this date.';
                details.appendChild(empty);
            }

            for (const schedule of vet.schedules) {
                const heading = document.createElement('h4');
                heading.textContent =
                    `${schedule.start_time.slice(0, 5)}–` +
                    `${schedule.end_time.slice(0, 5)} · ` +
                    schedule.status;

                details.appendChild(heading);

                const slots = document.createElement('ul');
                slots.className = 'overview-slot-list';

                for (const slot of schedule.time_slots) {
                    const item = document.createElement('li');

                    const time = document.createElement('strong');
                    time.textContent =
                        `${slot.start_time.slice(0, 5)}–` +
                        slot.end_time.slice(0, 5);

                    const status = document.createElement('span');
                    status.textContent = slot.status;

                    item.append(time, status);

                    for (const appointment of slot.appointments) {
                        const description = document.createElement('span');
                        description.className = 'overview-appointment';

                        description.textContent =
                            `${appointment.pet_name} · ` +
                            `${appointment.owner_name} · ` +
                            `${appointment.appointment_type.replaceAll('_', ' ')} · ` +
                            (appointment.needs_rearrangement
                                ? 'Needs rearrangement'
                                : appointment.status);

                        if (appointment.needs_rearrangement) {
                            description.style.color = '#b42318';
                            description.style.fontWeight = '600';
                        }

                        item.appendChild(description);
                    }

                    slots.appendChild(item);
                }

                details.appendChild(slots);
            }

            content.appendChild(details);
        }
    }

    async function loadOverview() {
        if (!context || !dateInput.value) return;

        const version = ++requestVersion;
        message.textContent = 'Loading clinic overview…';

        try {
            const query = new URLSearchParams({
                schedule_date: dateInput.value
            });

            if (vetFilter.value) {
                query.set('veterinarian_id', vetFilter.value);
            }

            const data = await context.request(
                `/schedules/overview?${query}`
            );

            if (version !== requestVersion) return;

            renderOverview(data);
        } catch (error) {
            if (version !== requestVersion) return;

            appointmentCount.textContent = '—';
            availableCount.textContent = '—';
            blockedCount.textContent = '—';
            content.replaceChildren();
            message.textContent = error.message;
        }
    }

    function initialize() {
        if (initialized || !window.clinicScheduleContext) return;

        initialized = true;
        context = window.clinicScheduleContext;
        dateInput.value =
            document.getElementById('schedule-date').value;

        loadOverview();

        setInterval(() => {
            if (!document.hidden && !context.isBusy()) {
                loadOverview();
            }
        }, 60000);
    }

    dateInput.addEventListener('change', loadOverview);
    vetFilter.addEventListener('change', loadOverview);

    window.addEventListener(
        'clinic-schedule-changed',
        loadOverview
    );

    window.addEventListener(
        'clinic-schedule-ready',
        initialize
    );

    initialize();
})();