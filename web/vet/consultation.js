(() => {
    const get = id => document.getElementById(id);
    const form = get('consultation-form');
    const fields = get('consultation-fields');
    const message = get('consultation-message');
    const reload = get('consultation-reload');

    const consultationId = Number(
        new URLSearchParams(window.location.search).get('id')
    );

    let record = null;
    let busy = false;
    let dirty = false;
    let needsReload = false;
    let rowCounter = 0;

    // Validation is performed explicitly before each save.
    form.noValidate = true;

    const clinicalFields = {
        consultation_information: 'consultation-information',
        examination_findings: 'examination-findings',
        diagnosis: 'consultation-diagnosis',
        notes: 'consultation-notes'
    };

    const rowDefinitions = {
        treatment: [
            ['treatment_name', 'Treatment name', 'text', 150, true],
            ['treatment_date', 'Treatment date', 'date', null, true],
            ['status', 'Status', 'select', null, true],
            ['description', 'Description', 'textarea', 5000, false]
        ],
        prescription: [
            ['medication_name', 'Medication name', 'text', 150, true],
            ['dosage', 'Dosage', 'text', 100, true],
            ['administration_route', 'Administration route',
                'text', 50, true],
            ['frequency', 'Frequency', 'text', 100, true],
            ['duration', 'Duration', 'text', 100, true],
            ['instructions', 'Instructions', 'textarea', 5000, false]
        ]
    };

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

    function setBusy(value) {
        busy = value;

        fields.disabled =
            value ||
            !record ||
            needsReload ||
            record.status !== 'draft';

        reload.disabled = value;
    }

    function markDirty() {
        if (record?.status === 'draft' && !busy && !needsReload) {
            dirty = true;
        }
    }

    function rootFor(kind) {
        return get(
            kind === 'treatment'
                ? 'consultation-treatments'
                : 'consultation-prescriptions'
        );
    }

    function createRow(kind, item = {}, changed = true) {
        const root = rootFor(kind);

        if (root.children.length >= 50) {
            message.textContent = 'Maximum 50 rows per section.';
            return;
        }

        const row = document.createElement('div');
        row.className = 'clinical-row';

        const idField = `${kind}_id`;
        if (item[idField] != null) {
            row.dataset.id = String(item[idField]);
        }

        const grid = document.createElement('div');
        grid.className = 'clinical-row-grid';

        const rowKey = ++rowCounter;

        for (const [
            name, labelText, type, maxLength, required
        ] of rowDefinitions[kind]) {
            const wrapper = document.createElement('div');
            const label = document.createElement('label');

            let input;

            if (type === 'textarea') {
                input = document.createElement('textarea');
                input.rows = 3;
            } else if (type === 'select') {
                input = document.createElement('select');

                for (const status of [
                    'planned', 'completed', 'cancelled'
                ]) {
                    const option = document.createElement('option');
                    option.value = status;
                    option.textContent =
                        status[0].toUpperCase() + status.slice(1);
                    input.appendChild(option);
                }
            } else {
                input = document.createElement('input');
                input.type = type;
            }

            input.id = `clinical-${rowKey}-${name}`;
            input.dataset.field = name;
            input.required = required;

            if (maxLength) input.maxLength = maxLength;

            const defaultValue =
                name === 'treatment_date'
                    ? today()
                    : name === 'status'
                        ? 'planned'
                        : '';

            input.value = item[name] ?? defaultValue;

            label.htmlFor = input.id;
            label.textContent = labelText;

            wrapper.append(label, input);
            grid.appendChild(wrapper);
        }

        const actions = document.createElement('div');
        actions.className = 'staff-actions';

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'secondary compact-button';
        remove.textContent =
            kind === 'treatment'
                ? 'Remove treatment'
                : 'Remove medication';

        remove.addEventListener('click', () => {
            if (busy || needsReload || record?.status !== 'draft') {
                return;
            }

            row.remove();
            markDirty();
        });

        actions.appendChild(remove);
        row.append(grid, actions);
        root.appendChild(row);

        if (changed) markDirty();
    }

    function readRows(kind) {
        return Array.from(rootFor(kind).children, row => {
            const item = {
                [`${kind}_id`]: row.dataset.id
                    ? Number(row.dataset.id)
                    : null
            };

            for (const input of row.querySelectorAll('[data-field]')) {
                const value = input.value.trim();

                item[input.dataset.field] =
                    !input.required && !value ? null : value;
            }

            return item;
        });
    }

    function render(data) {
        record = data;
        needsReload = false;

        get('consultation-patient').textContent = data.pet_name;

        get('consultation-summary').textContent =
            `Owner: ${data.owner_name} · ` +
            `Appointment #${data.appointment_id}`;

        get('consultation-state').textContent =
            `Status: ${data.status} · Version ${data.version}` +
            (data.status === 'completed'
                ? ' · Completed records are read-only.'
                : '');

        const emergency = get('consultation-emergency');
        emergency.hidden = !data.emergency_reason;

        emergency.textContent = data.emergency_reason
            ? `Emergency · ${data.urgency_level || 'Unassessed'}\n` +
            data.emergency_reason
            : '';

        for (const [name, id] of Object.entries(clinicalFields)) {
            get(id).value = data[name] ?? '';
        }

        rootFor('treatment').replaceChildren();
        rootFor('prescription').replaceChildren();

        for (const item of data.treatments) {
            createRow('treatment', item, false);
        }

        for (const item of data.prescriptions) {
            createRow('prescription', item, false);
        }

        const completed = data.status === 'completed';

        for (const id of [
            'add-treatment',
            'add-prescription',
            'save-consultation',
            'complete-consultation'
        ]) {
            get(id).hidden = completed;
        }

        dirty = false;
        reload.hidden = false;
    }

    async function loadConsultation() {
        if (busy) return;

        setBusy(true);
        message.classList.remove('success');
        message.textContent = 'Loading consultation…';

        try {
            const data = await vetRequest(
                `/consultations/${consultationId}`
            );

            render(data);
            message.textContent = '';
        } catch (error) {
            needsReload = true;
            message.textContent = error.message;
            reload.hidden = false;
        } finally {
            setBusy(false);
        }
    }

    function validate(complete) {
        // Clear previous custom errors before checking again.
        for (const input of form.querySelectorAll(
            'input, select, textarea'
        )) {
            input.setCustomValidity('');

            if (input.required && !input.value.trim()) {
                input.setCustomValidity('This field cannot be blank.');
            }
        }

        for (const row of rootFor('treatment').children) {
            const status = row.querySelector('[data-field="status"]');
            const date = row.querySelector(
                '[data-field="treatment_date"]'
            );

            if (status.value === 'completed' && date.value > today()) {
                date.setCustomValidity(
                    'A completed treatment cannot have a future date.'
                );
            }
        }

        if (!form.reportValidity()) return false;

        if (complete) {
            const required = [
                ['consultation-information', 'Presenting complaint'],
                ['examination-findings', 'Examination findings'],
                ['consultation-diagnosis', 'Diagnosis']
            ];

            for (const [id, label] of required) {
                if (!get(id).value.trim()) {
                    message.textContent =
                        `${label} is required to complete the consultation.`;
                    get(id).focus();
                    return false;
                }
            }
        }

        return true;
    }

    async function saveConsultation(complete) {
        if (
            busy || needsReload ||
            !record || record.status !== 'draft'
        ) return;

        if (!validate(complete)) return;

        if (
            complete &&
            !window.confirm(
                'Complete this consultation? Review the clinical notes, ' +
                'treatments and prescriptions first. ' +
                'The completed record will be read-only.'
            )
        ) return;

        const body = {
            version: record.version,
            complete,
            treatments: readRows('treatment'),
            prescriptions: readRows('prescription')
        };

        for (const [name, id] of Object.entries(clinicalFields)) {
            body[name] = get(id).value.trim() || null;
        }

        setBusy(true);
        message.classList.remove('success');
        message.textContent = complete
            ? 'Completing consultation…'
            : 'Saving draft…';

        try {
            const saved = await vetRequest(
                `/consultations/${consultationId}`,
                { method: 'PUT', body }
            );

            render(saved);
            message.classList.add('success');
            message.textContent = complete
                ? 'Consultation completed. The appointment is completed.'
                : 'Draft saved successfully.';
        } catch (error) {
            // An uncertain response may have saved on the server.
            // Reload before retrying to avoid duplicate child records.
            needsReload = true;

            message.textContent =
                `${error.message} Your displayed entries have been kept. ` +
                'Reload the saved record before trying again.';

            reload.hidden = false;
        } finally {
            setBusy(false);
        }
    }

    form.addEventListener('input', markDirty);
    form.addEventListener('change', markDirty);

    form.addEventListener('submit', event => {
        event.preventDefault();
        saveConsultation(false);
    });

    get('complete-consultation').addEventListener(
        'click', () => saveConsultation(true)
    );

    get('add-treatment').addEventListener(
        'click', () => createRow('treatment')
    );

    get('add-prescription').addEventListener(
        'click', () => createRow('prescription')
    );

    reload.addEventListener('click', () => {
        if (
            dirty &&
            !window.confirm(
                'Reloading replaces the displayed entries with the ' +
                'last saved record. Continue?'
            )
        ) return;

        loadConsultation();
    });

    window.addEventListener('beforeunload', event => {
        if (!dirty) return;
        event.preventDefault();
        event.returnValue = '';
    });

    vetReady.then(profile => {
        if (!profile) return;

        if (
            !Number.isInteger(consultationId) ||
            consultationId < 1 ||
            consultationId > 2147483647
        ) {
            message.textContent =
                'Open a consultation from your assigned appointment.';
            return;
        }

        loadConsultation();
    });
})();