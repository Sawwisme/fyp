(() => {
    const oldContent = document.getElementById('overview-content');
    const dateInput = document.getElementById('overview-date');
    const vetFilter = document.getElementById('overview-vet');

    oldContent.hidden = true;

    const workspace = document.createElement('div');

    workspace.innerHTML = `
        <div class="schedule-tabs" role="tablist"
             aria-label="Schedule views">
            <button id="calendar-tab" type="button"
                    role="tab" aria-selected="true"
                    aria-controls="calendar-view">
                Schedule Calendar
            </button>
            <button id="appointments-tab" type="button"
                    role="tab" aria-selected="false"
                    aria-controls="appointments-view" tabindex="-1">
                Appointments
            </button>
            <button id="emergency-tab" type="button"
                    role="tab" aria-selected="false"
                    aria-controls="emergency-view" tabindex="-1">
                Emergency Requests
            </button>
        </div>

        <div id="calendar-view" role="tabpanel"
             aria-labelledby="calendar-tab">
            <div class="calendar-navigation">
                <strong id="calendar-month"></strong>
                <div>
                    <button id="calendar-previous" type="button"
                            class="secondary compact-button"
                            aria-label="Previous month">‹</button>
                    <button id="calendar-today" type="button"
                            class="secondary compact-button">Today</button>
                    <button id="calendar-next" type="button"
                            class="secondary compact-button"
                            aria-label="Next month">›</button>
                </div>
            </div>

            <p class="muted">
                Select a date to update the counts.
                Select a veterinarian to manage their schedule.
            </p>

            <div class="calendar-scroll">
                <div id="clinic-calendar" class="clinic-calendar"></div>
            </div>

            <p id="calendar-message" role="status"></p>
        </div>

        <div id="appointments-view" role="tabpanel"
             aria-labelledby="appointments-tab" hidden>
            <div class="staff-list-toolbar">
                <div>
                    <label class="field-label" for="appointment-search">
                        Search appointments
                    </label>
                    <input id="appointment-search" type="search"
                           placeholder="Pet, owner or veterinarian">
                </div>
                <div>
                    <label class="field-label" for="appointment-status">
                        Status
                    </label>
                    <select id="appointment-status">
                        <option value="">All statuses</option>
                        <option value="confirmed">Confirmed</option>
                        <option value="in_progress">In progress</option>
                        <option value="pending">Pending</option>
                        <option value="completed">Completed</option>
                        <option value="cancelled">Cancelled</option>
                        <option value="rejected">Rejected</option>
                    </select>
                </div>
            </div>

            <p id="appointment-list-note" role="status"></p>

            <div class="table-scroll">
                <table class="staff-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Pet</th>
                            <th>Owner</th>
                            <th>Veterinarian</th>
                            <th>Type</th>
                            <th>Source</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="appointment-overview-rows"></tbody>
                </table>
            </div>
        </div>
        <div id="emergency-view" role="tabpanel"
     aria-labelledby="emergency-tab" hidden></div>
    `;

    oldContent.after(workspace);

    const get = id => workspace.querySelector(`#${id}`);
    const grid = get('clinic-calendar');
    const calendarMessage = get('calendar-message');
    const appointmentRows = get('appointment-overview-rows');
    const tabs = [get('calendar-tab'), get('appointments-tab'), get('emergency-tab')];

    let context = null;
    let calendarVersion = 0;
    let appointments = [];

    function isoDate(value) {
        return value.toISOString().slice(0, 10);
    }

    function switchTab(index) {
        tabs.forEach((tab, position) => {
            tab.setAttribute(
                'aria-selected',
                String(position === index)
            );
            tab.tabIndex = position === index ? 0 : -1;
        });

        get('calendar-view').hidden = index !== 0;
        get('appointments-view').hidden = index !== 1;
        get('emergency-view').hidden = index !== 2;

        if (index === 2) {
            window.dispatchEvent(new Event('clinic-emergency-open'));
        }
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => switchTab(index));

        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) {
                return;
            }

            event.preventDefault();
            const direction = event.key === 'ArrowRight' ? 1 : -1;
            const next = (index + direction + tabs.length) % tabs.length;
            switchTab(next);
            tabs[next].focus();
        });
    });

    function selectDate(value) {
        dateInput.value = value;
        dateInput.dispatchEvent(new Event('change'));
    }

    function changeMonth(step) {
        if (!dateInput.value) return;

        const selected = new Date(`${dateInput.value}T00:00:00Z`);

        selectDate(isoDate(new Date(Date.UTC(
            selected.getUTCFullYear(),
            selected.getUTCMonth() + step,
            1
        ))));
    }

    get('calendar-previous').addEventListener(
        'click',
        () => changeMonth(-1)
    );

    get('calendar-next').addEventListener(
        'click',
        () => changeMonth(1)
    );

    get('calendar-today').addEventListener('click', () => {
        selectDate(new Intl.DateTimeFormat('en-CA', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).format(new Date()));
    });

    async function loadCalendar() {
        context = window.clinicScheduleContext;

        if (!context || !dateInput.value) return;

        const version = ++calendarVersion;
        const selectedDate = dateInput.value;
        const selected = new Date(`${selectedDate}T00:00:00Z`);
        const month = selected.getUTCMonth();

        const first = new Date(Date.UTC(
            selected.getUTCFullYear(),
            month,
            1
        ));

        // Monday is the first calendar column.
        const start = new Date(first);
        start.setUTCDate(
            first.getUTCDate() - (first.getUTCDay() + 6) % 7
        );

        const end = new Date(start);
        end.setUTCDate(start.getUTCDate() + 41);

        get('calendar-month').textContent =
            first.toLocaleDateString('en-MY', {
                month: 'long',
                year: 'numeric',
                timeZone: 'UTC'
            });

        grid.replaceChildren();
        calendarMessage.textContent = 'Loading calendar…';

        try {
            const query = new URLSearchParams({
                start_date: isoDate(start),
                end_date: isoDate(end)
            });

            if (vetFilter.value) {
                query.set('veterinarian_id', vetFilter.value);
            }

            const data = await context.request(
                `/schedules/calendar?${query}`
            );

            if (version !== calendarVersion) return;

            const byDay = new Map();

            for (const entry of data.entries) {
                if (!byDay.has(entry.schedule_date)) {
                    byDay.set(entry.schedule_date, []);
                }
                byDay.get(entry.schedule_date).push(entry);
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
                const day = new Date(start);
                day.setUTCDate(start.getUTCDate() + index);
                const date = isoDate(day);

                const cell = document.createElement('div');
                cell.className = 'calendar-day';
                cell.classList.toggle(
                    'outside-month',
                    day.getUTCMonth() !== month
                );
                cell.classList.toggle(
                    'selected-day',
                    date === selectedDate
                );

                const dateButton = document.createElement('button');
                dateButton.type = 'button';
                dateButton.className = 'calendar-date';
                dateButton.textContent = day.getUTCDate();
                dateButton.setAttribute('aria-label', date);
                dateButton.addEventListener(
                    'click',
                    () => selectDate(date)
                );
                cell.appendChild(dateButton);

                for (const entry of byDay.get(date) || []) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'calendar-vet';

                    const name = document.createElement('strong');
                    name.textContent = entry.full_name;

                    const times = document.createElement('span');
                    times.textContent = entry.periods.map(period =>
                        `${period.start_time.slice(0, 5)}–` +
                        period.end_time.slice(0, 5)
                    ).join(' / ');

                    const count = document.createElement('span');
                    count.textContent =
                        `${entry.appointment_count} appointment(s)`;

                    button.append(name, times, count);

                    button.addEventListener('click', () => {
                        if (context.isBusy()) return;

                        const vetSelect =
                            document.getElementById('schedule-vet');

                        // Retain access to historical schedules even
                        // if a vet is no longer in the active selector.
                        if (
                            ![...vetSelect.options].some(
                                option =>
                                    option.value ===
                                    String(entry.veterinarian_id)
                            )
                        ) {
                            const option =
                                document.createElement('option');
                            option.value = entry.veterinarian_id;
                            option.textContent = entry.full_name;
                            vetSelect.appendChild(option);
                        }

                        window.openClinicScheduleEditor(
                            'individual',
                            date,
                            String(entry.veterinarian_id)
                        );
                    });

                    cell.appendChild(button);
                }

                grid.appendChild(cell);
            }

            calendarMessage.textContent = data.entries.length
                ? 'Calendar shows active working schedules.'
                : 'No active schedules in this calendar range.';
        } catch (error) {
            if (version === calendarVersion) {
                calendarMessage.textContent = error.message;
            }
        }
    }

    let cancellingAppointment = false;

    const actionMessage = document.createElement('p');
    actionMessage.className = 'message';
    actionMessage.setAttribute('role', 'status');
    get('appointment-list-note').after(actionMessage);

    async function cancelAppointment(item) {
        const scheduleContext = window.clinicScheduleContext;

        if (
            !scheduleContext ||
            scheduleContext.isBusy() ||
            cancellingAppointment
        ) {
            return;
        }

        const confirmed = window.confirm(
            `Cancel ${item.pet_name}'s appointment at ${item.time}?`
        );

        if (!confirmed) return;

        cancellingAppointment = true;
        scheduleContext.setBusy(true);
        actionMessage.textContent = 'Cancelling appointment…';
        actionMessage.classList.remove('error', 'success');
        renderAppointments();

        try {
            const result = await scheduleContext.request(
                `/clinic-appointments/${item.appointment_id}/cancel`,
                undefined,
                'POST'
            );

            item.status = 'cancelled';
            actionMessage.textContent = result.message;
            actionMessage.classList.add('success');
        } catch (error) {
            actionMessage.textContent = error.message;
            actionMessage.classList.add('error');
        } finally {
            cancellingAppointment = false;
            scheduleContext.setBusy(false);
            renderAppointments();
        }
    }

    function renderAppointments() {
        const query = get('appointment-search').value
            .trim().toLocaleLowerCase();
        const status = get('appointment-status').value;

        const matches = appointments.filter(item => {
            const text = [
                item.pet_name,
                item.owner_name,
                item.vet_name
            ].join(' ').toLocaleLowerCase();

            return (!status || item.status === status)
                && text.includes(query);
        });

        appointmentRows.replaceChildren();

        for (const item of matches) {
            const row = document.createElement('tr');

            for (const value of [
                item.time,
                item.pet_name,
                item.owner_name,
                item.vet_name,
                item.appointment_type.replaceAll('_', ' '),
                (item.appointment_source || 'Not recorded')
                    .replaceAll('_', ' '),
                item.status
            ]) {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.appendChild(cell);
            }

            const actions = document.createElement('td');

            const canCancel =
                ['pending', 'confirmed'].includes(item.status) &&
                Date.parse(item.starts_at) > Date.now();

            if (canCancel) {
                actions.classList.add('appointment-row-actions');

                const rescheduleButton = document.createElement('button');
                rescheduleButton.type = 'button';
                rescheduleButton.className = 'secondary compact-button';
                rescheduleButton.textContent = 'Reschedule';
                rescheduleButton.disabled = cancellingAppointment;

                rescheduleButton.addEventListener('click', () => {
                    window.openRescheduleAppointment(item);
                });

                actions.appendChild(rescheduleButton);

                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'secondary compact-button';
                button.textContent = 'Cancel';
                button.disabled = cancellingAppointment;
                button.setAttribute(
                    'aria-label',
                    `Cancel appointment for ${item.pet_name} at ${item.time}`
                );

                button.addEventListener('click', () => {
                    cancelAppointment(item);
                });

                actions.appendChild(button);
            } else {
                actions.textContent = '—';
            }

            row.appendChild(actions);
            appointmentRows.appendChild(row);
        }

        get('appointment-list-note').textContent =
            `Showing ${matches.length} of ${appointments.length} ` +
            `appointments for ${dateInput.value}.`;
    }

    function receiveOverview(data) {
        const unique = new Map();

        for (const vet of data.veterinarians) {
            for (const schedule of vet.schedules) {
                for (const slot of schedule.time_slots) {
                    for (const appointment of slot.appointments) {
                        unique.set(appointment.appointment_id, {
                            ...appointment,
                            vet_name: vet.full_name,
                            veterinarian_id: vet.veterinarian_id,
                            schedule_date: schedule.schedule_date,
                            time: slot.start_time.slice(0, 5),
                            starts_at:
                                `${schedule.schedule_date}T${slot.start_time}+08:00`
                        });
                    }
                }
            }
        }

        appointments = [...unique.values()].sort(
            (a, b) => a.time.localeCompare(b.time)
        );

        renderAppointments();
        loadCalendar();
    }

    get('appointment-search').addEventListener(
        'input',
        renderAppointments
    );

    get('appointment-status').addEventListener(
        'change',
        renderAppointments
    );

    for (const input of [dateInput, vetFilter]) {
        input.addEventListener('change', () => {
            calendarVersion += 1;
            grid.replaceChildren();
            appointments = [];
            appointmentRows.replaceChildren();
            calendarMessage.textContent = 'Loading…';
            get('appointment-list-note').textContent = 'Loading…';
        });
    }

    window.addEventListener('clinic-overview-loaded', event => {
        receiveOverview(event.detail);
    });

    if (window.clinicLastOverview) {
        receiveOverview(window.clinicLastOverview);
    }
})();