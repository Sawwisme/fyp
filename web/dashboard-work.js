(() => {
    'use strict';

    const root = document.querySelector('[data-dashboard-role]');
    if (!root) return;

    const admin = root.dataset.dashboardRole === 'admin';

    let loading = false;

    function node(tag, text, className) {
        const element = document.createElement(tag);

        if (text !== undefined) {
            element.textContent = String(text);
        }

        if (className) element.className = className;

        return element;
    }

    function today() {
        const parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(new Date());

        const part = type =>
            parts.find(item => item.type === type).value;

        return `${part('year')}-${part('month')}-${part('day')}`;
    }

    function request(path) {
        return admin ? apiRequest(path) : vetRequest(path);
    }

    async function listAll(path) {
        const collected = [];

        for (let offset = 0; ; offset += 100) {
            const url = new URL(path, location.origin);
            url.searchParams.set('offset', String(offset));
            url.searchParams.set('limit', '100');

            const data = await request(
                `${url.pathname}${url.search}`
            );

            // Some endpoints return lists; clinic orders return {items,total}.
            const items = Array.isArray(data) ? data : data.items;

            if (!Array.isArray(items)) {
                throw new Error('Unexpected dashboard response.');
            }

            collected.push(...items);

            if (items.length < 100) return collected;
        }
    }

    const grid = node('div', undefined, 'dash-work-grid');

    const appointmentPanel = node(
        'section',
        undefined,
        'dash-panel'
    );

    const appointmentHeading = node(
        'div',
        undefined,
        'dash-toolbar'
    );

    appointmentHeading.appendChild(
        node('h2', 'Today’s appointments', 'dash-section-heading')
    );

    const appointmentLink = node('a', 'View all →');
    appointmentLink.href = admin
        ? '/web/admin/schedules.html'
        : '/web/vet/appointments.html';

    appointmentHeading.appendChild(appointmentLink);

    const appointmentContent = node('div');

    appointmentPanel.append(
        appointmentHeading,
        node(
            'p',
            'Active bookings in Malaysia time. Showing up to six.',
            'dash-note'
        ),
        appointmentContent
    );

    const taskPanel = node('section', undefined, 'dash-panel');
    taskPanel.appendChild(
        node('h2', 'Needs attention', 'dash-section-heading')
    );

    const taskContent = node('div');
    taskPanel.appendChild(taskContent);

    grid.append(appointmentPanel, taskPanel);

    // Keep the overview above the daily work panels.
    const overview = root.querySelector('.dash-overview');

    if (overview) {
        overview.after(grid);
    } else {
        root.appendChild(grid);
    }

    function task(title, detail, count, href, urgent = false) {
        const link = node(
            'a',
            undefined,
            `dash-task${urgent && count > 0 ? ' urgent' : ''}`
        );

        link.href = href;

        const description = node('div');
        description.append(
            node('strong', title),
            node('small', detail)
        );

        link.append(
            description,
            node('span', count, 'dash-task-count')
        );

        return link;
    }

    function taskError(title) {
        const text = node(
            'p',
            `${title} could not be loaded. Use Refresh to retry.`,
            'dash-note'
        );

        taskContent.appendChild(text);
    }

    async function appointments() {
        let records;

        if (admin) {
            const data = await request(
                `/schedules/overview?schedule_date=${today()}`
            );

            if (!Array.isArray(data.veterinarians)) {
                throw new Error('Invalid clinic overview.');
            }

            records = [];

            for (const vet of data.veterinarians) {
                for (const schedule of vet.schedules || []) {
                    for (const slot of schedule.time_slots || []) {
                        for (const appointment of slot.appointments || []) {
                            records.push({
                                ...appointment,
                                start_time: slot.start_time,
                                end_time: slot.end_time,
                                veterinarian_name: vet.full_name
                            });
                        }
                    }
                }
            }
        } else {
            records = await listAll(
                `/veterinarians/me/appointments?appointment_date=${today()}`
            );
        }

        const activeStatuses = new Set([
            'pending',
            'confirmed',
            'in_progress'
        ]);

        return records
            .filter(item => activeStatuses.has(item.status))
            .sort((a, b) => {
                // Patients already being seen appear first.
                const aProgress = a.status === 'in_progress' ? 0 : 1;
                const bProgress = b.status === 'in_progress' ? 0 : 1;

                return aProgress - bProgress ||
                    String(a.start_time).localeCompare(String(b.start_time));
            });
    }

    function renderAppointments(records) {
        appointmentContent.replaceChildren();

        if (!records.length) {
            appointmentContent.appendChild(
                node(
                    'p',
                    'No pending, confirmed or in-progress appointments today.',
                    'dash-note'
                )
            );
            return;
        }

        const wrapper = node('div', undefined, 'dash-table-wrap');
        const table = node('table', undefined, 'dash-table');
        const head = node('thead');
        const headingRow = node('tr');

        for (const title of ['Time', 'Patient', 'Vet', 'Status']) {
            const heading = node('th', title);
            heading.scope = 'col';
            headingRow.appendChild(heading);
        }

        head.appendChild(headingRow);

        const body = node('tbody');

        for (const appointment of records.slice(0, 6)) {
            const row = node('tr');

            const time = node(
                'td',
                `${String(appointment.start_time).slice(0, 5)}–` +
                `${String(appointment.end_time).slice(0, 5)}`
            );

            const patient = node('td');
            patient.append(
                node('strong', appointment.pet_name),
                node('small', appointment.owner_name || '')
            );

            const status = node('td');
            status.appendChild(
                node(
                    'span',
                    appointment.needs_rearrangement
                        ? 'Needs rearrangement'
                        : String(appointment.status).replaceAll('_', ' '),
                    'dash-pill'
                )
            );

            row.append(
                time,
                patient,
                node('td', appointment.veterinarian_name || '—'),
                status
            );

            body.appendChild(row);
        }

        table.append(head, body);
        wrapper.appendChild(table);
        appointmentContent.appendChild(wrapper);
    }

    async function vetTasks() {
        const results = await Promise.allSettled([
            listAll('/ai-assessment-reviews?status=pending'),
            listAll('/consultations?consultation_status=draft'),
            listAll('/followups?status=pending')
        ]);

        taskContent.replaceChildren();

        if (results[0].status === 'fulfilled') {
            taskContent.appendChild(task(
                'AI assessments',
                'Shared with your clinic and awaiting review',
                results[0].value.length,
                '/web/vet/ai_assessments.html'
            ));
        } else {
            taskError('AI assessments');
        }

        if (results[1].status === 'fulfilled') {
            taskContent.appendChild(task(
                'Draft consultations',
                'Records that have not been finalized',
                results[1].value.length,
                '/web/vet/consultations.html'
            ));
        } else {
            taskError('Draft consultations');
        }

        if (results[2].status === 'fulfilled') {
            const items = results[2].value;
            const overdue = items.filter(item => item.overdue).length;

            taskContent.appendChild(task(
                'Open follow-ups',
                `${overdue} overdue. Includes tasks awaiting owner or vet action.`,
                items.length,
                '/web/vet/followups.html',
                overdue > 0
            ));
        } else {
            taskError('Follow-ups');
        }
    }

    async function adminTasks(records) {
        const results = await Promise.allSettled([
            listAll('/emergency-requests/clinic?request_status=pending'),
            listAll('/clinic-orders?order_status=processing')
        ]);

        taskContent.replaceChildren();

        if (results[0].status === 'fulfilled') {
            taskContent.appendChild(task(
                'Emergency requests',
                'Requests awaiting clinic review',
                results[0].value.length,
                '/web/admin/schedules.html',
                true
            ));
        } else {
            taskError('Emergency requests');
        }

        if (results[1].status === 'fulfilled') {
            taskContent.appendChild(task(
                'Orders in processing',
                'Prepare these orders for pickup or delivery',
                results[1].value.length,
                '/web/admin/orders.html'
            ));
        } else {
            taskError('Shop orders');
        }

        if (records !== null) {
            taskContent.appendChild(task(
                'Bookings needing rearrangement',
                'Today’s affected appointments',
                records.filter(item => item.needs_rearrangement).length,
                '/web/admin/schedules.html',
                true
            ));
        } else {
            taskError('Bookings needing rearrangement');
        }
    }

    async function load() {
        if (loading) return;
        loading = true;

        appointmentContent.textContent = 'Loading appointments…';
        taskContent.textContent = 'Loading tasks…';

        try {
            // Start vet task requests alongside appointment loading.
            const taskPromise = admin ? null : vetTasks();

            let records = null;

            try {
                records = await appointments();
                renderAppointments(records);
            } catch (_) {
                appointmentContent.textContent =
                    'Appointments could not be loaded. Use Refresh to retry.';
            }

            if (admin) {
                await adminTasks(records);
            } else {
                await taskPromise;
            }
        } finally {
            loading = false;
        }
    }

    root.querySelector('[data-dash-refresh]')
        ?.addEventListener('click', load);

    if (admin) {
        window.addEventListener('admin-profile-ready', load);

        const workspace = document.getElementById('dashboard');
        if (workspace && !workspace.hidden) load();
    } else {
        vetReady.then(profile => {
            if (profile) load();
        }).catch(() => {
            appointmentContent.textContent = 'Account unavailable.';
            taskContent.textContent = 'Please reload the page.';
        });
    }
})();