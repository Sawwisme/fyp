(() => {
    const get = id => document.getElementById(id);
    const panel = get('patient-history-panel');
    const root = get('patient-history-records');
    const message = get('patient-history-message');
    const retry = get('patient-history-retry');
    const more = get('patient-history-more');

    const consultationId = Number(
        new URLSearchParams(location.search).get('id')
    );

    const pageSize = 10;
    let offset = 0;
    let loading = false;
    let started = false;
    let authorized = false;
    let hasMore = false;

    function paragraph(parent, label, value) {
        const text = document.createElement('p');
        const heading = document.createElement('strong');

        heading.textContent = `${label}: `;
        text.append(
            heading,
            document.createTextNode(value || 'Not recorded')
        );

        parent.appendChild(text);
    }

    function formatDate(value) {
        const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
            ? value
            : `${value}Z`;

        const date = new Date(normalized);

        return Number.isNaN(date.getTime())
            ? 'Date not recorded'
            : date.toLocaleString('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur',
                dateStyle: 'medium',
                timeStyle: 'short',
            });
    }

    function renderVisit(visit) {
        const details = document.createElement('details');
        details.className = 'patient-history-visit';

        const summary = document.createElement('summary');
        summary.textContent =
            `${formatDate(visit.consultation_date)} · ` +
            visit.veterinarian_name;

        details.appendChild(summary);

        paragraph(
            details,
            'Consultation',
            `#${visit.consultation_id}`
        );
        paragraph(
            details,
            'Complaint and history',
            visit.consultation_information
        );
        paragraph(
            details,
            'Examination findings',
            visit.examination_findings
        );
        paragraph(details, 'Diagnosis', visit.diagnosis);
        paragraph(details, 'Notes', visit.notes);

        const treatmentHeading = document.createElement('h3');
        treatmentHeading.textContent = 'Treatments';
        details.appendChild(treatmentHeading);

        if (!visit.treatments.length) {
            paragraph(details, 'Treatments', 'None recorded');
        }

        for (const treatment of visit.treatments) {
            const card = document.createElement('div');
            card.className = 'patient-history-item';

            paragraph(card, 'Treatment', treatment.treatment_name);
            paragraph(card, 'Date', treatment.treatment_date);
            paragraph(card, 'Status', treatment.status);
            paragraph(card, 'Description', treatment.description);

            details.appendChild(card);
        }

        const prescriptionHeading = document.createElement('h3');
        prescriptionHeading.textContent = 'Prescriptions';
        details.appendChild(prescriptionHeading);

        if (!visit.prescriptions.length) {
            paragraph(details, 'Prescriptions', 'None recorded');
        }

        for (const prescription of visit.prescriptions) {
            const card = document.createElement('div');
            card.className = 'patient-history-item';

            paragraph(card, 'Medication', prescription.medication_name);
            paragraph(card, 'Dosage', prescription.dosage);
            paragraph(
                card,
                'Route',
                prescription.administration_route
            );
            paragraph(card, 'Frequency', prescription.frequency);
            paragraph(card, 'Duration', prescription.duration);
            paragraph(card, 'Instructions', prescription.instructions);

            details.appendChild(card);
        }

        return details;
    }

    async function loadHistory() {
        if (!authorized || loading) return;

        loading = true;
        started = true;
        more.disabled = true;
        retry.hidden = true;
        message.textContent = 'Loading previous consultations…';

        try {
            // Fetch one extra record to determine whether more exist.
            const results = await vetRequest(
                `/consultations/${consultationId}/patient-history` +
                `?offset=${offset}&limit=${pageSize + 1}`
            );

            const visible = results.slice(0, pageSize);
            const fragment = document.createDocumentFragment();

            for (const visit of visible) {
                fragment.appendChild(renderVisit(visit));
            }

            root.appendChild(fragment);
            offset += visible.length;
            hasMore = results.length > pageSize;

            message.textContent = offset
                ? `${offset} previous consultation(s) shown.`
                : 'No previous completed consultations at this clinic.';
        } catch (error) {
            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            loading = false;
            more.disabled = false;
            more.hidden = !hasMore || !retry.hidden;
        }
    }

    panel.addEventListener('toggle', () => {
        if (panel.open && !started) {
            loadHistory();
        }
    });

    more.addEventListener('click', loadHistory);
    retry.addEventListener('click', loadHistory);

    vetReady.then(profile => {
        if (
            !profile ||
            !Number.isInteger(consultationId) ||
            consultationId < 1 ||
            consultationId > 2147483647
        ) return;

        authorized = true;

        if (panel.open && !started) {
            loadHistory();
        }
    });
})();