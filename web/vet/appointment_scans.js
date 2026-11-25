(() => {
    'use strict';

    const date = document.getElementById('scan-date');
    const refresh = document.getElementById('scan-refresh');
    const previous = document.getElementById('scans-previous');
    const next = document.getElementById('scans-next');
    const pageLabel = document.getElementById('scans-page');
    const message = document.getElementById('scans-message');
    const rows = document.getElementById('scans-rows');

    const pageSize = 20;
    let page = 0;
    let hasNext = false;
    let loading = false;
    let appliedDate = '';

    const labels = {
        confirmed: 'Confirmed',
        in_progress: 'In consultation',
        completed: 'Completed'
    };

    function controls() {
        refresh.disabled = loading;
        date.disabled = loading;
        previous.disabled = loading || page === 0;
        next.disabled = loading || !hasNext;
    }

    function cell(value) {
        const element = document.createElement('td');
        element.textContent = value ?? 'Not recorded';
        return element;
    }

    async function load(targetPage, selectedDate = appliedDate) {
        if (loading) return;

        if (!date.validity.valid) {
            message.textContent = 'Select a valid appointment date.';
            return;
        }

        loading = true;
        controls();
        message.textContent = 'Loading appointment assessments…';

        try {
            const query = new URLSearchParams({
                offset: String(targetPage * pageSize),
                limit: String(pageSize + 1)
            });

            if (selectedDate) {
                query.set('appointment_date', selectedDate);
            }

            const records = await vetRequest(
                `/veterinarians/me/appointment-assessments?${query}`
            );

            if (!Array.isArray(records)) {
                throw new Error('Invalid assessment list response.');
            }

            // Keep the current page intact if loading fails.
            const fragment = document.createDocumentFragment();

            for (const record of records.slice(0, pageSize)) {
                if (!Number.isInteger(record.appointment_id) ||
                    !Number.isInteger(record.ai_analysis_id) ||
                    record.appointment_id < 1 ||
                    record.ai_analysis_id < 1) {
                    throw new Error('Invalid linked assessment record.');
                }

                const row = document.createElement('tr');
                const appointmentDate = String(
                    record.appointment_date || ''
                ).split('-').reverse().join('/');

                row.append(
                    cell(
                        `${appointmentDate} · ` +
                        String(record.start_time || '').slice(0, 5)
                    ),
                    cell(record.pet_name),
                    cell(record.owner_name),
                    cell(labels[record.status] || record.status),
                    cell(`#${record.ai_analysis_id}`)
                );

                const action = document.createElement('td');
                const link = document.createElement('a');
                const linkQuery = new URLSearchParams({
                    appointment_id: String(record.appointment_id)
                });

                link.href =
                    `/web/vet/appointment_assessment.html?${linkQuery}`;
                link.textContent = 'View assessment';
                link.className = 'secondary compact-button';

                action.appendChild(link);
                row.appendChild(action);
                fragment.appendChild(row);
            }

            rows.replaceChildren(fragment);
            page = targetPage;
            appliedDate = selectedDate;
            hasNext = records.length > pageSize;
            pageLabel.textContent = `Page ${page + 1}`;

            message.textContent = records.length
                ? 'Showing scans linked to your assigned appointments.'
                : 'No linked assessments found for this selection.';
        } catch (error) {
            message.textContent = error.message;
        } finally {
            loading = false;
            controls();
        }
    }

    refresh.addEventListener('click', () => load(0, date.value));
    previous.addEventListener('click', () => load(page - 1));
    next.addEventListener('click', () => load(page + 1));

    vetReady.then(profile => {
        if (profile) load(0, '');
    });
})();