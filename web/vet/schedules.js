(() => {
    const get = id => document.getElementById(id);
    const calendarView = get('vet-calendar-view');
    const dayView = get('vet-day-view');
    const grid = get('vet-calendar');
    const date = get('my-schedule-date');
    const list = get('my-schedule-list');
    const message = get('my-schedule-message');
    const action = get('my-schedule-action');
    const retry = get('my-schedule-refresh');

    let month;
    let currentView = 'calendar';
    let version = 0;
    let busy = false;
    let loading = false;

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

    function parseDate(value) {
        return new Date(`${value}T00:00:00Z`);
    }

    function iso(value) {
        return value.toISOString().slice(0, 10);
    }

    function shiftDate(value, days) {
        const result = parseDate(value);
        result.setUTCDate(result.getUTCDate() + days);
        return iso(result);
    }

    function displayDate(value) {
        return parseDate(value).toLocaleDateString('en-MY', {
            timeZone: 'UTC',
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
    }

    function label(text, className) {
        const element = document.createElement('span');
        element.textContent = text;
        if (className) element.className = className;
        return element;
    }

    function setBusy(value) {
        busy = value;

        document.querySelectorAll(
            '#vet-day-view button, #vet-day-view input'
        ).forEach(element => {
            element.disabled = value;
        });
    }

    const dialog = document.createElement('dialog');
    dialog.className = 'reception-dialog vet-appointment-dialog';
    dialog.setAttribute('aria-labelledby', 'vet-detail-title');

    dialog.innerHTML = `
        <header class="schedule-dialog-header">
            <h2 id="vet-detail-title">Appointment details</h2>
            <button type="button" class="dialog-close"
                    aria-label="Close appointment details">×</button>
        </header>
        <dl class="vet-appointment-details"></dl>
    `;

    document.body.appendChild(dialog);
    dialog.querySelector('button').addEventListener(
        'click', () => dialog.close()
    );

    function showAppointment(item) {
        const details = dialog.querySelector('dl');
        details.replaceChildren();

        const values = [
            ['Pet', item.pet_name],
            ['Owner', item.owner_name],
            ['Date', displayDate(item.appointment_date)],
            ['Time',
                `${item.start_time.slice(0, 5)}–` +
                item.end_time.slice(0, 5)],
            ['Type', item.appointment_type.replaceAll('_', ' ')],
            ['Source',
                (item.appointment_source || 'Not recorded')
                    .replaceAll('_', ' ')],
            ['Status', item.status]
        ];

        for (const [name, value] of values) {
            const term = document.createElement('dt');
            const description = document.createElement('dd');
            term.textContent = name;
            description.textContent = value;
            details.append(term, description);
        }

        dialog.showModal();
    }

    async function loadPages(path, query, currentVersion) {
        const result = [];

        for (let offset = 0; ; offset += 100) {
            const params = new URLSearchParams({
                ...query,
                offset: String(offset),
                limit: '100'
            });

            const page = await vetRequest(`${path}?${params}`);

            if (currentVersion !== version) return null;

            result.push(...page);
            if (page.length < 100) return result;
        }
    }

    async function loadCalendar() {
        const currentVersion = ++version;
        loading = true;
        retry.hidden = true;
        grid.replaceChildren();
        message.textContent = 'Loading calendar…';

        const first = new Date(Date.UTC(
            month.getUTCFullYear(), month.getUTCMonth(), 1
        ));

        const start = new Date(first);
        start.setUTCDate(
            start.getUTCDate() - (start.getUTCDay() + 6) % 7
        );

        const end = shiftDate(iso(start), 41);

        get('vet-calendar-month').textContent =
            first.toLocaleDateString('en-MY', {
                timeZone: 'UTC',
                month: 'long',
                year: 'numeric'
            });

        try {
            const query = new URLSearchParams({
                start_date: iso(start),
                end_date: end
            });

            const entries = await vetRequest(
                `/veterinarians/me/calendar?${query}`
            );

            if (currentVersion !== version) return;

            const grouped = new Map();

            for (const entry of entries) {
                if (!grouped.has(entry.schedule_date)) {
                    grouped.set(entry.schedule_date, []);
                }
                grouped.get(entry.schedule_date).push(entry);
            }

            for (const name of [
                'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'
            ]) {
                const heading = document.createElement('div');
                heading.className = 'calendar-weekday';
                heading.textContent = name;
                grid.appendChild(heading);
            }

            for (let index = 0; index < 42; index++) {
                const day = shiftDate(iso(start), index);
                const periods = grouped.get(day) || [];

                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'calendar-day vet-calendar-cell';

                button.classList.toggle(
                    'outside-month',
                    parseDate(day).getUTCMonth() !== month.getUTCMonth()
                );
                button.classList.toggle('selected-day', day === today());
                button.setAttribute('aria-label', displayDate(day));

                button.appendChild(label(
                    String(parseDate(day).getUTCDate()),
                    'vet-calendar-number'
                ));

                if (day === today()) {
                    button.setAttribute('aria-current', 'date');
                }

                if (periods.length) {
                    for (const period of periods) {
                        button.appendChild(label(
                            `${period.start_time.slice(0, 5)}–` +
                            period.end_time.slice(0, 5),
                            'vet-calendar-hours'
                        ));
                    }

                    const count = periods.reduce(
                        (total, period) =>
                            total + period.appointment_count,
                        0
                    );

                    button.appendChild(label(
                        `${count} appointment(s)`,
                        'vet-calendar-count'
                    ));
                } else {
                    button.appendChild(label(
                        'No assigned hours',
                        'vet-calendar-empty'
                    ));
                }

                button.addEventListener('click', () => openDay(day));
                grid.appendChild(button);
            }

            message.textContent =
                'Select a date to view its daily timeline.';
        } catch (error) {
            if (currentVersion !== version) return;
            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (currentVersion === version) loading = false;
        }
    }

    async function loadDay() {
        const currentVersion = ++version;
        loading = true;
        retry.hidden = true;
        list.replaceChildren();

        if (!date.value || !date.validity.valid) {
            loading = false;
            message.textContent = 'Select a valid date.';
            return;
        }

        const selectedDate = date.value;
        get('vet-day-title').textContent = displayDate(selectedDate);
        message.textContent = 'Loading timeline…';

        try {
            const [schedules, appointments] = await Promise.all([
                loadPages('/veterinarians/me/schedules', {
                    schedule_date: selectedDate
                }, currentVersion),
                loadPages('/veterinarians/me/appointments', {
                    appointment_date: selectedDate
                }, currentVersion)
            ]);

            if (currentVersion !== version) return;

            const bySlot = new Map();

            for (const appointment of appointments) {
                if (['cancelled', 'rejected'].includes(appointment.status)) {
                    continue;
                }

                if (!bySlot.has(appointment.time_slot_id)) {
                    bySlot.set(appointment.time_slot_id, []);
                }

                bySlot.get(appointment.time_slot_id).push(appointment);
            }

            const slots = schedules
                .filter(schedule => schedule.status === 'active')
                .flatMap(schedule => schedule.time_slots.map(slot => ({
                    ...slot,
                    schedule_id: schedule.schedule_id
                })))
                .sort((a, b) => a.start_time.localeCompare(b.start_time));

            for (const slot of slots) {
                const row = document.createElement('div');
                row.className = 'vet-timeline-row';

                const time = label(
                    `${slot.start_time.slice(0, 5)}–` +
                    slot.end_time.slice(0, 5),
                    'vet-timeline-time'
                );

                const card = document.createElement('div');
                card.className = 'vet-timeline-card';

                const bookings = bySlot.get(slot.time_slot_id) || [];
                const start = Date.parse(
                    `${selectedDate}T${slot.start_time}+08:00`
                );
                const end = Date.parse(
                    `${selectedDate}T${slot.end_time}+08:00`
                );

                if (bookings.length) {
                    card.classList.add('is-booked');

                    for (const appointment of bookings) {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = 'vet-booking-link';
                        button.textContent =
                            `${appointment.pet_name} · ${appointment.status}`;
                        button.addEventListener(
                            'click', () => showAppointment(appointment)
                        );

                        card.append(
                            button,
                            label(appointment.owner_name, 'muted')
                        );
                    }
                } else {
                    card.classList.toggle(
                        'is-blocked', slot.status === 'blocked'
                    );

                    card.appendChild(label(
                        slot.status === 'available' && end <= Date.now()
                            ? 'Expired'
                            : slot.status.replaceAll('_', ' '),
                        'vet-slot-status'
                    ));

                    if (
                        start > Date.now() &&
                        ['available', 'blocked'].includes(slot.status)
                    ) {
                        const button = document.createElement('button');
                        const blocking = slot.status === 'available';

                        button.type = 'button';
                        button.className = 'secondary compact-button';
                        button.textContent = blocking ? 'Block' : 'Reopen';
                        button.addEventListener('click', () => {
                            updateSlot(
                                slot.schedule_id,
                                slot.time_slot_id,
                                blocking ? 'blocked' : 'available'
                            );
                        });

                        card.appendChild(button);
                    }
                }

                row.append(time, card);
                list.appendChild(row);
            }

            message.textContent = slots.length
                ? `${slots.length} total slots for this date.`
                : 'No active working hours assigned for this date.';
        } catch (error) {
            if (currentVersion !== version) return;
            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (currentVersion === version) loading = false;
        }
    }

    async function updateSlot(scheduleId, slotId, status) {
        if (busy) return;

        const confirmed = window.confirm(
            status === 'blocked'
                ? 'Block this slot from new bookings?'
                : 'Make this slot available for booking?'
        );

        if (!confirmed) return;

        setBusy(true);
        action.textContent = '';
        action.classList.remove('success');

        try {
            await vetRequest(
                `/schedules/${scheduleId}/slots/${slotId}`,
                { method: 'PATCH', body: { status } }
            );

            action.textContent = 'Slot availability updated.';
            action.classList.add('success');
            await loadDay();
        } catch (error) {
            action.textContent = error.message;
        } finally {
            setBusy(false);
        }
    }

    function openDay(value) {
        if (busy) return;

        currentView = 'day';
        date.value = value;
        calendarView.hidden = true;
        dayView.hidden = false;
        action.textContent = '';
        loadDay();
    }

    function openCalendar() {
        if (busy) return;

        currentView = 'calendar';
        month = parseDate(date.value || today());
        month.setUTCDate(1);
        dayView.hidden = true;
        calendarView.hidden = false;
        action.textContent = '';
        loadCalendar();
    }

    function changeMonth(amount) {
        month = new Date(Date.UTC(
            month.getUTCFullYear(),
            month.getUTCMonth() + amount,
            1
        ));
        loadCalendar();
    }

    get('vet-month-previous').addEventListener(
        'click', () => changeMonth(-1)
    );
    get('vet-month-next').addEventListener(
        'click', () => changeMonth(1)
    );
    get('vet-calendar-today').addEventListener('click', () => {
        month = parseDate(today());
        month.setUTCDate(1);
        loadCalendar();
    });

    get('vet-back-calendar').addEventListener('click', openCalendar);
    get('vet-day-previous').addEventListener(
        'click', () => openDay(shiftDate(date.value, -1))
    );
    get('vet-day-next').addEventListener(
        'click', () => openDay(shiftDate(date.value, 1))
    );
    get('vet-day-today').addEventListener(
        'click', () => openDay(today())
    );

    date.addEventListener('change', () => {
        action.textContent = '';
        loadDay();
    });

    retry.addEventListener('click', () => {
        if (!busy) {
            currentView === 'calendar' ? loadCalendar() : loadDay();
        }
    });

    vetReady.then(profile => {
        if (!profile) return;

        date.value = today();
        month = parseDate(today());
        month.setUTCDate(1);
        loadCalendar();

        setInterval(() => {
            if (!document.hidden && !busy && !loading && !dialog.open) {
                currentView === 'calendar' ? loadCalendar() : loadDay();
            }
        }, 60000);
    });
})();