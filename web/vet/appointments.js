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

    async function openSharedHistory(appointmentId) {
        const dialog = document.createElement('dialog');
        dialog.className = 'ar-dialog';
        dialog.style.width = 'min(850px, calc(100vw - 32px))';
        dialog.style.maxHeight = '85vh';
        dialog.style.overflow = 'auto';
        dialog.style.padding = '24px';

        function node(tag, value) {
            const element = document.createElement(tag);
            if (value !== undefined) {
                element.textContent = String(value);
            }
            return element;
        }

        const title = node('h2', 'Shared medical history');
        const note = node(
            'p',
            'Read-only records from previous completed consultations. ' +
            'Record new findings in the current consultation.'
        );
        const close = node('button', 'Close');
        close.type = 'button';
        close.className = 'secondary compact-button';

        const status = node('p');
        status.setAttribute('role', 'status');

        const content = node('div');
        const previous = node('button', 'Previous');
        const next = node('button', 'Next');
        const pageLabel = node('span', 'Page 1');

        for (const button of [previous, next]) {
            button.type = 'button';
            button.className = 'secondary compact-button';
        }

        const navigation = node('div');
        navigation.style.display = 'flex';
        navigation.style.gap = '12px';
        navigation.style.alignItems = 'center';
        navigation.append(previous, pageLabel, next);

        dialog.append(title, note, close, status, content, navigation);
        document.body.appendChild(dialog);

        close.addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => dialog.remove(), {
            once: true
        });
        dialog.showModal();

        let page = 0;
        let loading = false;
        let hasMore = false;

        function controls() {
            previous.disabled = loading || page === 0;
            next.disabled = loading || !hasMore;
        }

        async function load(targetPage) {
            if (loading || !dialog.open) return;

            loading = true;
            controls();
            status.textContent = 'Loading shared history…';
            content.replaceChildren();

            try {
                const query = new URLSearchParams({
                    offset: String(targetPage * 20),
                    limit: '20'
                });

                const response = await vetRequest(
                    `/veterinarians/me/appointments/${appointmentId}` +
                    `/shared-history?${query}`
                );

                if (!dialog.open) return;
                if (!Array.isArray(response.items)) {
                    throw new Error('Invalid medical history response.');
                }

                for (const record of response.items) {
                    const section = node('section');
                    section.className = 'panel section-panel';

                    section.append(
                        node('h3', record.clinic_name || 'Clinic not recorded'),
                        node(
                            'p',
                            `${record.veterinarian_name || 'Vet not recorded'} · ` +
                            `${record.consultation_date || 'Date not recorded'}`
                        )
                    );

                    function detail(label, value) {
                        const paragraph = node(
                            'p',
                            `${label}: ${value || 'Not recorded'}`
                        );
                        paragraph.style.whiteSpace = 'pre-wrap';
                        section.appendChild(paragraph);
                    }

                    detail('Diagnosis', record.diagnosis);
                    detail('Examination findings', record.examination_findings);
                    detail('Follow-up instructions', record.followup_instructions);

                    for (const treatment of record.treatments || []) {
                        detail(
                            'Treatment',
                            [
                                treatment.treatment_name,
                                treatment.description,
                                treatment.treatment_date,
                                treatment.status
                            ].filter(Boolean).join(' · ')
                        );
                    }

                    for (const prescription of record.prescriptions || []) {
                        detail(
                            'Recorded prescription',
                            [
                                prescription.medication_name,
                                prescription.dosage,
                                prescription.administration_route,
                                prescription.frequency,
                                prescription.duration,
                                prescription.instructions
                            ].filter(Boolean).join(' · ')
                        );
                    }

                    content.appendChild(section);
                }

                page = targetPage;
                hasMore = response.has_more === true;
                pageLabel.textContent = `Page ${page + 1}`;
                status.textContent = response.items.length
                    ? 'Original clinical wording is preserved.'
                    : 'No previous completed records are available.';
            } catch (error) {
                if (dialog.open) status.textContent = error.message;
            } finally {
                loading = false;
                controls();
            }
        }

        previous.addEventListener('click', () => load(page - 1));
        next.addEventListener('click', () => load(page + 1));
        await load(0);
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

            const assessmentCell = document.createElement('td');

            const canViewAssessment =
                Number.isInteger(item.ai_analysis_id) &&
                item.ai_analysis_id > 0 &&
                ['confirmed', 'in_progress', 'completed']
                    .includes(item.status);

            if (canViewAssessment) {
                const link = document.createElement('a');
                link.className = 'secondary compact-button';
                link.textContent = 'View AI assessment';

                const query = new URLSearchParams({
                    appointment_id: String(item.appointment_id)
                });

                link.href =
                    `/web/vet/appointment_assessment.html?${query}`;

                assessmentCell.appendChild(link);
            } else {
                assessmentCell.textContent = '—';
            }

            row.appendChild(assessmentCell);

            const historyCell = document.createElement('td');
            const canViewHistory =
                item.medical_history_shared === true &&
                ['confirmed', 'in_progress', 'completed']
                    .includes(item.status);

            if (canViewHistory) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'secondary compact-button';
                button.textContent = 'View shared history';
                button.addEventListener('click', () =>
                    openSharedHistory(item.appointment_id)
                );
                historyCell.appendChild(button);
            } else {
                historyCell.textContent = '—';
            }

            row.appendChild(historyCell);
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