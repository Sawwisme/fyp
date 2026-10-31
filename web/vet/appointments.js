(() => {
    const visitParams = new URLSearchParams(location.search);
    const date = document.getElementById('vet-appointment-date');
    const search = document.getElementById('vet-appointment-search');
    const status = document.getElementById('vet-appointment-status');
    const rows = document.getElementById('vet-appointment-rows');
    const message = document.getElementById('vet-appointment-message');
    const retry = document.getElementById('vet-appointment-retry');

    let records = [];
    let version = 0;
    let loading = false;
    let ready = false;

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

    function renderAppointmentCounts(items = null) {
        const counts = items ? {
            total: items.length,
            confirmed: items.filter(
                item => item.status === 'confirmed'
            ).length,
            progress: items.filter(
                item => item.status === 'in_progress'
            ).length,
            completed: items.filter(
                item => item.status === 'completed'
            ).length
        } : null;

        for (const name of [
            'total', 'confirmed', 'progress', 'completed'
        ]) {
            document.getElementById(
                `appointment-count-${name}`
            ).textContent = counts ? counts[name] : '—';
        }
    }

    function render() {
        const query = search.value.trim().toLocaleLowerCase();

        const matches = records.filter(item => {
            const text = `${item.pet_name} ${item.owner_name}`
                .toLocaleLowerCase();

            return text.includes(query)
                && (!status.value || item.status === status.value);
        });

        renderAppointmentCounts(matches);

        rows.replaceChildren();

        for (const item of matches) {
            const row = document.createElement('tr');

            row.classList.toggle(
                'linked-appointment-highlight',
                String(item.appointment_id) ===
                visitParams.get('appointment_id')
            );

            const values = [
                item.appointment_date.split('-').reverse().join('/'),
                `${item.start_time.slice(0, 5)}–` +
                item.end_time.slice(0, 5),
                item.pet_name,
                item.owner_name,
                item.appointment_type.replaceAll('_', ' '),
                (item.appointment_source || 'Not recorded')
                    .replaceAll('_', ' '),
                item.needs_rearrangement
                    ? 'Needs rearrangement'
                    : item.status
            ];

            for (const value of values) {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.appendChild(cell);
            }

            const emergencyCell = document.createElement('td');

            if (item.appointment_type === 'emergency') {
                const details = document.createElement('details');
                const summary = document.createElement('summary');
                const reason = document.createElement('p');

                summary.textContent =
                    `View details · ${item.urgency_level || 'Unassessed'}`;

                reason.textContent =
                    item.emergency_reason || 'No emergency reason recorded.';
                reason.className = 'emergency-request-reason';

                details.append(summary, reason);
                emergencyCell.appendChild(details);
            } else {
                emergencyCell.textContent = '—';
            }

            row.appendChild(emergencyCell);

            const consultationCell = document.createElement('td');
            const consultationButton =
                window.createVetConsultationButton(item, message);

            if (consultationButton) {
                consultationCell.appendChild(consultationButton);
            } else {
                consultationCell.textContent = '—';
            }

            row.appendChild(consultationCell);
            rows.appendChild(row);
        }

        message.textContent = records.length
            ? `Showing ${matches.length} of ${records.length} appointments.`
            : date.value
                ? 'No appointments assigned to you for this date.'
                : 'No appointments assigned to you.';
    }

    let totalLoading = false;

    async function loadAllTimeCount() {
        if (totalLoading) return;
        totalLoading = true;

        const total = document.getElementById('appointment-all-time-total');
        const note = document.getElementById('appointment-all-time-message');
        const retryTotal = document.getElementById('appointment-all-time-retry');

        retryTotal.hidden = true;
        total.textContent = '—';
        note.textContent = 'Loading overall total…';

        try {
            const data = await vetRequest(
                '/veterinarians/me/appointments/summary'
            );

            if (!Number.isInteger(data.total) || data.total < 0) {
                throw new Error('Invalid appointment total.');
            }

            total.textContent = String(data.total);
            note.textContent = '';
        } catch (error) {
            note.textContent = error.message;
            retryTotal.hidden = false;
        } finally {
            totalLoading = false;
        }
    }

    document.getElementById('appointment-all-time-retry')
        .addEventListener('click', loadAllTimeCount);

    async function loadAppointments() {
        if (!ready) return;

        const currentVersion = ++version;
        renderAppointmentCounts();
        records = [];
        rows.replaceChildren();
        retry.hidden = true;

        if (!date.validity.valid) {
            loading = false;
            message.textContent = 'Select a valid date.';
            return;
        }

        loading = true;
        message.textContent = 'Loading appointments…';

        const selectedDate = date.value;
        const collected = [];

        try {
            let offset = 0;

            while (true) {
                const query = new URLSearchParams({
                    offset: String(offset),
                    limit: '100'
                });

                if (selectedDate) {
                    query.set('appointment_date', selectedDate);
                }

                const page = await vetRequest(
                    `/veterinarians/me/appointments?${query}`
                );

                if (currentVersion !== version) return;

                collected.push(...page);

                if (page.length < 100) break;
                offset += page.length;
            }

            records = collected;
            render();
        } catch (error) {
            if (currentVersion !== version) return;

            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (currentVersion === version) loading = false;
        }
    }

    date.addEventListener('change', loadAppointments);
    document.getElementById('appointment-today')
        .addEventListener('click', () => {
            date.value = today();
            loadAppointments();
        });

    document.getElementById('appointment-clear-date')
        .addEventListener('click', () => {
            date.value = '';
            loadAppointments();
        });
    retry.addEventListener('click', loadAppointments);

    search.addEventListener('input', () => {
        if (!loading && retry.hidden) render();
    });

    status.addEventListener('change', () => {
        if (!loading && retry.hidden) render();
    });

    vetReady.then(profile => {
        if (!profile) return;

        ready = true;
        const requestedDate = visitParams.get('date');

        date.value = /^\d{4}-\d{2}-\d{2}$/.test(requestedDate || '')
            ? requestedDate
            : '';

        if (!date.validity.valid) {
            date.value = '';
        }

        loadAppointments();
        loadAllTimeCount();

        setInterval(() => {
            if (!document.hidden && !loading) {
                loadAppointments();
                loadAllTimeCount();
            }
        }, 60000);
    });
})();