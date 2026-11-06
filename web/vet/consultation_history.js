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
        const treatments = Array.isArray(visit.treatments) ? visit.treatments : [];
        const prescriptions = Array.isArray(visit.prescriptions) ? visit.prescriptions : [];
        function element(tag, className, value) {
            const node = document.createElement(tag);
            if (className) node.className = className;
            if (value != null) node.textContent = String(value);
            return node;
        }
        const details = element('details', 'patient-history-visit history-visit-card');
        const summary = element('summary', 'history-visit-summary');
        const dateText = formatDate(visit.consultation_date);
        const date = element('div', 'history-visit-date', dateText);
        const overview = element('div', 'history-visit-overview');
        overview.appendChild(element('span', 'history-visit-diagnosis', visit.diagnosis || 'Diagnosis not recorded'));
        overview.appendChild(element('span', 'history-visit-vet', visit.veterinarian_name || 'Veterinarian not recorded'));
        const chips = element('div', 'history-visit-chips');
        chips.append(
            element('span', 'history-visit-chip', `${treatments.length} treatment${treatments.length === 1 ? '' : 's'}`),
            element('span', 'history-visit-chip', `${prescriptions.length} prescription${prescriptions.length === 1 ? '' : 's'}`)
        );
        overview.appendChild(chips);
        const reference = element('div', 'history-visit-reference');
        reference.append(
            element('span', 'history-visit-id', `#${visit.consultation_id}`),
            element('span', 'history-visit-completed', 'Completed')
        );
        summary.append(date, overview, reference);
        details.appendChild(summary);

        const body = element('div', 'history-visit-body');
        const fields = element('div', 'history-visit-fields');
        paragraph(fields, 'Complaint and history', visit.consultation_information);
        paragraph(fields, 'Examination findings', visit.examination_findings);
        paragraph(fields, 'Diagnosis', visit.diagnosis);
        paragraph(fields, 'Notes', visit.notes);
        body.appendChild(fields);

        const collections = element('div', 'history-visit-collections');
        const treatmentSection = element('section', 'history-visit-collection');
        treatmentSection.appendChild(element('h3', '', 'Treatments'));
        if (!treatments.length) treatmentSection.appendChild(element('p', 'history-visit-empty', 'No treatments recorded.'));
        for (const treatment of treatments) {
            const card = element('div', 'patient-history-item history-visit-item');
            card.appendChild(element('h4', '', treatment.treatment_name || 'Treatment name not recorded'));
            paragraph(card, 'Date', treatment.treatment_date);
            paragraph(card, 'Status', treatment.status ? treatment.status.replaceAll('_', ' ') : null);
            paragraph(card, 'Description', treatment.description);
            treatmentSection.appendChild(card);
        }
        const medicationSection = element('section', 'history-visit-collection');
        medicationSection.appendChild(element('h3', '', 'Prescriptions'));
        if (!prescriptions.length) medicationSection.appendChild(element('p', 'history-visit-empty', 'No medications prescribed.'));
        for (const prescription of prescriptions) {
            const card = element('div', 'patient-history-item history-visit-item');
            card.appendChild(element('h4', '', prescription.medication_name || 'Medication name not recorded'));
            paragraph(card, 'Dosage', prescription.dosage);
            paragraph(card, 'Route', prescription.administration_route);
            paragraph(card, 'Frequency', prescription.frequency);
            paragraph(card, 'Duration', prescription.duration);
            paragraph(card, 'Instructions', prescription.instructions);
            medicationSection.appendChild(card);
        }
        collections.append(treatmentSection, medicationSection);
        body.appendChild(collections);
        details.appendChild(body);
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