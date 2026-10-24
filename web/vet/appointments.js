(() => {
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

    function render() {
        const query = search.value.trim().toLocaleLowerCase();

        const matches = records.filter(item => {
            const text = `${item.pet_name} ${item.owner_name}`
                .toLocaleLowerCase();

            return text.includes(query)
                && (!status.value || item.status === status.value);
        });

        rows.replaceChildren();

        for (const item of matches) {
            const row = document.createElement('tr');

            const values = [
                `${item.start_time.slice(0, 5)}–` +
                item.end_time.slice(0, 5),
                item.pet_name,
                item.owner_name,
                item.appointment_type.replaceAll('_', ' '),
                (item.appointment_source || 'Not recorded')
                    .replaceAll('_', ' '),
                item.status
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
            rows.appendChild(row);
        }

        message.textContent = records.length
            ? `Showing ${matches.length} of ${records.length} appointments.`
            : 'No appointments assigned to you for this date.';
    }

    async function loadAppointments() {
        if (!ready) return;

        const currentVersion = ++version;
        records = [];
        rows.replaceChildren();
        retry.hidden = true;

        if (!date.value || !date.validity.valid) {
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
                    appointment_date: selectedDate,
                    offset: String(offset),
                    limit: '100'
                });

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
        date.value = today();
        loadAppointments();

        setInterval(() => {
            if (!document.hidden && !loading) {
                loadAppointments();
            }
        }, 60000);
    });
})();