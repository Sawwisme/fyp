(() => {
    const get = id => document.getElementById(id);
    const search = get('history-search');
    const status = get('history-status');
    const treatmentStatus = get('history-treatment-status');
    const dateFrom = get('history-date-from');
    const dateTo = get('history-date-to');
    const rows = get('history-rows');
    const message = get('history-message');
    const retry = get('history-retry');
    const previous = get('history-previous');
    const next = get('history-next');

    const tabs = [
        get('history-treatments-tab'),
        get('history-prescriptions-tab')
    ];

    const pageSize = 20;

    let type = 'treatments';
    let page = 0;
    let version = 0;
    let ready = false;
    let loading = false;
    let timer;

    function dateLabel(value) {
        const [year, month, day] = value.split('-').map(Number);

        return new Date(Date.UTC(year, month - 1, day))
            .toLocaleDateString('en-MY', {
                timeZone: 'UTC',
                dateStyle: 'medium'
            });
    }

    function cell(value) {
        const element = document.createElement('td');
        element.textContent = value || '—';
        return element;
    }

    function detailsCell(item, selectedType) {
        const result = document.createElement('td');
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        const content = document.createElement('p');

        content.className = 'clinical-history-detail';

        if (selectedType === 'treatments') {
            summary.textContent = item.status
                .replaceAll('_', ' ')
                .replace(/\b\w/g, letter => letter.toUpperCase());
            content.textContent =
                item.description || 'No description recorded.';
        } else {
            summary.textContent = 'View directions';

            content.textContent = [
                `Dosage: ${item.dosage}`,
                `Route: ${item.administration_route || 'Not recorded'}`,
                `Frequency: ${item.frequency || 'Not recorded'}`,
                `Duration: ${item.duration || 'Not recorded'}`,
                `Instructions: ${item.instructions || 'Not recorded'}`
            ].join('\n');
        }

        details.append(summary, content);

        if (selectedType === 'treatments') {
            details.appendChild(createTreatmentDetails(item));
            details.appendChild(
                createLinkedVisitDetails(item.linked_visit, 'treatment')
            );
        }

        result.appendChild(details);

        return result;
    }

    function renderCounts(counts = null) {
        const treatment = type === 'treatments';

        get('history-progress-card').hidden = !treatment;
        get('history-treatment-filter').hidden = !treatment;

        document.querySelector('.clinical-history-summary')
            .classList.toggle('show-treatment-progress', treatment);

        get('history-label-total').textContent = treatment
            ? 'Total Treatments'
            : 'Total Prescriptions';

        get('history-label-second').textContent = treatment
            ? 'Planned Treatments'
            : 'Draft Prescriptions';

        get('history-label-third').textContent = treatment
            ? 'Completed Treatments'
            : 'Finalized Prescriptions';

        get('history-label-month').textContent = treatment
            ? 'Treatments This Month'
            : 'Prescriptions This Month';

        get('history-count-note').textContent = treatment
            ? 'Counts follow the selected filters. Planned, In Progress and ' +
            'Completed refer to current treatment status.'
            : 'Counts follow the selected filters. Draft and finalized ' +
            'refer to consultation status, not medication-course completion.';

        const values = {
            'history-count-total': counts?.total,
            'history-count-draft': treatment
                ? counts?.planned
                : counts?.draft,
            'history-count-finalized': treatment
                ? counts?.completed
                : counts?.finalized,
            'history-count-month': counts?.this_month,
            'history-count-progress': counts?.in_progress,
        };

        for (const [id, value] of Object.entries(values)) {
            get(id).textContent = value == null
                ? '—'
                : Number(value).toLocaleString('en-MY');
        }
    }

    async function load(targetPage = 0) {
        if (!ready) return;

        const currentVersion = ++version;
        const selectedType = type;

        loading = true;
        previous.disabled = true;
        next.disabled = true;
        retry.hidden = true;
        rows.replaceChildren();
        renderCounts();

        if (
            dateFrom.value &&
            dateTo.value &&
            dateFrom.value > dateTo.value
        ) {
            message.textContent =
                'From date must be on or before To date.';
            loading = false;
            return;
        }

        message.textContent = 'Loading records…';

        const query = new URLSearchParams({
            offset: String(targetPage * pageSize),
            limit: String(pageSize + 1),
        });

        if (search.value.trim()) {
            query.set('search', search.value.trim());
        }

        if (status.value) {
            query.set('consultation_status', status.value);
        }

        if (dateFrom.value) {
            query.set('date_from', dateFrom.value);
        }

        if (dateTo.value) {
            query.set('date_to', dateTo.value);
        }

        if (
            selectedType === 'treatments' &&
            treatmentStatus.value
        ) {
            query.set('treatment_status', treatmentStatus.value);
        }

        const countQuery = new URLSearchParams(query);
        countQuery.delete('offset');
        countQuery.delete('limit');
        countQuery.set('record_type', selectedType);

        try {
            const [data, counts] = await Promise.all([
                vetRequest(
                    `/consultations/${selectedType}/history?${query}`
                ),
                vetRequest(
                    `/consultations/clinical-history/counts?${countQuery}`
                ),
            ]);

            if (currentVersion !== version) return;

            renderCounts(counts);
            page = targetPage;
            get('history-page-label').textContent = `Page ${page + 1}`;

            const visible = data.slice(0, pageSize);

            for (const item of visible) {
                const treatment = selectedType === 'treatments';
                const row = document.createElement('tr');

                row.append(
                    cell(dateLabel(
                        treatment
                            ? item.treatment_date
                            : item.prescription_date
                    )),
                    cell(item.pet_name),
                    cell(item.owner_name),
                    cell(
                        treatment
                            ? item.treatment_name
                            : item.medication_name
                    ),
                    detailsCell(item, selectedType),
                    cell(
                        item.consultation_status === 'draft'
                            ? 'Draft — not final'
                            : 'Completed'
                    )
                );

                const action = document.createElement('td');
                const link = document.createElement('a');

                link.href =
                    `/web/vet/consultation.html?id=${item.consultation_id}`;

                link.textContent =
                    item.consultation_status === 'draft'
                        ? 'Continue consultation'
                        : 'View consultation';

                action.appendChild(link);

                if (treatment) {
                    action.appendChild(
                        createTreatmentProgressActions(item, () => load(0))
                    );
                }

                row.appendChild(action);
                rows.appendChild(row);
            }

            message.textContent = visible.length
                ? `Page ${page + 1} · ${visible.length} record(s).`
                : 'No matching records.';

            previous.disabled = page === 0;
            next.disabled = data.length <= pageSize;
        } catch (error) {
            if (currentVersion !== version) return;

            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (currentVersion === version) {
                loading = false;
            }
        }
    }

    function selectTab(index) {
        clearTimeout(timer);
        type = index === 0 ? 'treatments' : 'prescriptions';

        tabs.forEach((tab, position) => {
            tab.setAttribute(
                'aria-selected',
                String(position === index)
            );
            tab.tabIndex = position === index ? 0 : -1;
        });

        get('clinical-history-panel').setAttribute(
            'aria-labelledby',
            tabs[index].id
        );

        get('history-name-heading').textContent =
            index === 0 ? 'Treatment' : 'Medication';

        search.placeholder = index === 0
            ? 'Pet, owner or treatment'
            : 'Pet, owner or medication';

        load(0);
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => selectTab(index));

        tab.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) {
                return;
            }

            event.preventDefault();
            const target = index === 0 ? 1 : 0;
            selectTab(target);
            tabs[target].focus();
        });
    });

    search.addEventListener('input', () => {
        clearTimeout(timer);
        version += 1;
        previous.disabled = true;
        next.disabled = true;
        timer = setTimeout(() => load(0), 300);
    });

    status.addEventListener('change', () => {
        clearTimeout(timer);
        load(0);
    });

    for (const input of [dateFrom, dateTo]) {
        input.addEventListener('change', () => {
            clearTimeout(timer);
            load(0);
        });
    }

    treatmentStatus.addEventListener('change', () => {
        clearTimeout(timer);
        load(0);
    });

    previous.addEventListener('click', () => {
        if (!loading && page > 0) load(page - 1);
    });

    next.addEventListener('click', () => {
        if (!loading) load(page + 1);
    });

    retry.addEventListener('click', () => load(0));

    vetReady.then(profile => {
        if (!profile) return;
        ready = true;
        load(0);
    });
})();