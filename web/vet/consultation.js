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
    let assessmentOptions = [];
    let assessmentLoading = false;
    let assessmentsLoaded = false;
    let assessmentRequest = 0;

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

        updateAssessmentControls();

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

    function renderCompleted(data) {
        const root = get('consultation-readview');
        root.replaceChildren();

        function section(title) {
            const panel = document.createElement('section');
            panel.className = 'panel consultation-report-panel';

            const heading = document.createElement('h2');
            heading.textContent = title;
            panel.appendChild(heading);

            return panel;
        }

        function detail(parent, labelText, value) {
            const field = document.createElement('div');
            field.className = 'consultation-report-field';

            const label = document.createElement('h3');
            label.textContent = labelText;

            const content = document.createElement('p');
            content.textContent = value || 'Not recorded';

            field.append(label, content);
            parent.appendChild(field);
        }

        const clinical = section('Clinical information');
        const grid = document.createElement('div');
        grid.className = 'consultation-report-grid';

        detail(grid, 'Presenting complaint and history',
            data.consultation_information);
        detail(grid, 'Examination findings', data.examination_findings);
        detail(grid, 'Diagnosis', data.diagnosis);
        detail(grid, 'Additional notes', data.notes);

        clinical.appendChild(grid);
        root.appendChild(clinical);

        const columns = document.createElement('div');
        columns.className = 'consultation-report-columns';

        const treatments = section('Treatments');

        if (!data.treatments.length) {
            detail(treatments, 'Treatment records', 'No treatments recorded.');
        }

        for (const item of data.treatments) {
            const row = document.createElement('div');
            row.className = 'consultation-record-row';

            detail(row, item.treatment_name,
                `${item.treatment_date} · ${item.status}`);

            if (item.description) {
                detail(row, 'Description', item.description);
            }

            const progressDetails = document.createElement('details');
            const progressSummary = document.createElement('summary');

            progressSummary.textContent = 'View treatment progress';

            progressDetails.append(
                progressSummary,
                createTreatmentDetails(item)
            );

            row.appendChild(progressDetails);

            treatments.appendChild(row);
        }

        const prescriptions = section('Prescriptions');

        if (!data.prescriptions.length) {
            detail(prescriptions, 'Medication records',
                'No medications prescribed.');
        }

        for (const item of data.prescriptions) {
            const row = document.createElement('div');
            row.className = 'consultation-record-row';

            detail(row, 'Medication', item.medication_name);

            const medicationGrid = document.createElement('div');
            medicationGrid.className = 'consultation-report-grid';

            detail(medicationGrid, 'Dosage', item.dosage);
            detail(medicationGrid, 'Route', item.administration_route);
            detail(medicationGrid, 'Frequency', item.frequency);
            detail(medicationGrid, 'Duration', item.duration);

            row.appendChild(medicationGrid);

            if (item.instructions) {
                detail(row, 'Instructions', item.instructions);
            }

            prescriptions.appendChild(row);
        }

        columns.append(treatments, prescriptions);
        root.appendChild(columns);
    }

    function renderPatient(patient) {
        const root = get('consultation-patient-details');
        root.replaceChildren();

        let birthDate = 'Not recorded';

        if (patient.date_of_birth) {
            const [year, month, day] =
                patient.date_of_birth.split('-');

            birthDate = `${day}/${month}/${year}`;
        }

        const fields = [
            ['Species', patient.species],
            ['Breed', patient.breed],
            ['Sex', patient.gender],
            ['Date of birth', birthDate],
            [
                'Weight',
                patient.weight == null
                    ? null
                    : `${patient.weight} kg`,
            ],
            [
                'Existing dental condition',
                patient.existing_dental_condition,
            ],
            ['Patient notes', patient.notes],
        ];

        for (const [label, value] of fields) {
            const item = document.createElement('div');
            const term = document.createElement('dt');
            const description = document.createElement('dd');

            term.textContent = label;
            description.textContent = value || 'Not recorded';

            item.append(term, description);
            root.appendChild(item);
        }
    }

    function updateAssessmentControls() {
        get('consultation-assessment').disabled =
            busy ||
            assessmentLoading ||
            !assessmentsLoaded ||
            needsReload ||
            !record ||
            record.status !== 'draft';
    }

    function assessmentDate(value) {
        if (!value) return 'Date not recorded';

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

    function showAssessment(assessment) {
        const root = get('assessment-result');
        root.replaceChildren();

        if (!assessment) {
            const empty = document.createElement('p');
            empty.className = 'muted';
            empty.textContent = 'No AI dental assessment linked.';
            root.appendChild(empty);
            return;
        }

        const heading = document.createElement('p');
        heading.textContent =
            `Assessment #${assessment.analysis_id} · ` +
            assessmentDate(assessment.analysis_date);
        root.appendChild(heading);

        const list = document.createElement('ul');
        list.className = 'assessment-predictions';

        for (const prediction of assessment.predictions) {
            const item = document.createElement('li');
            const confidence = Number(prediction.confidence_score);

            const result = !prediction.supported
                ? 'Not supported by this model'
                : prediction.predicted_positive
                    ? 'Flagged by AI'
                    : 'Not flagged by AI';

            item.textContent =
                `${prediction.condition_name}: ${result}` +
                (
                    prediction.supported &&
                        Number.isFinite(confidence)
                        ? ` · Score ${(confidence * 100).toFixed(1)}%`
                        : ''
                );

            list.appendChild(item);
        }

        if (assessment.predictions.length) {
            root.appendChild(list);
        } else {
            const empty = document.createElement('p');
            empty.textContent = 'No prediction details recorded.';
            root.appendChild(empty);
        }

        if (assessment.veterinarian_override) {
            const review = document.createElement('p');
            review.textContent =
                `Recorded vet review: ` +
                assessment.veterinarian_override;
            root.appendChild(review);
        }

        if (assessment.override_notes) {
            const notes = document.createElement('p');
            notes.className = 'assessment-notes';
            notes.textContent = assessment.override_notes;
            root.appendChild(notes);
        }
    }

    async function loadAssessments() {
        if (!record || record.status !== 'draft') return;

        const request = ++assessmentRequest;
        const consultationRecord = record;
        const select = get('consultation-assessment');
        const status = get('assessment-message');

        assessmentsLoaded = false;
        assessmentLoading = true;
        updateAssessmentControls();
        get('assessment-retry').hidden = true;
        status.textContent = 'Loading patient assessments…';

        try {
            const results = [];
            let offset = 0;

            while (true) {
                const batch = await vetRequest(
                    `/consultations/${consultationId}/ai-assessments` +
                    `?offset=${offset}&limit=100`
                );

                if (
                    request !== assessmentRequest ||
                    record !== consultationRecord
                ) return;

                results.push(...batch);

                if (batch.length < 100) break;
                offset += batch.length;
            }

            const byId = new Map(
                results.map(item => [item.analysis_id, item])
            );

            // Keep the linked result visible even if the list changes.
            if (record.ai_assessment) {
                byId.set(
                    record.ai_assessment.analysis_id,
                    record.ai_assessment
                );
            }

            assessmentOptions = [...byId.values()];

            assessmentsLoaded = true;

            select.replaceChildren(
                new Option('No assessment linked', '')
            );

            for (const item of assessmentOptions) {
                select.add(new Option(
                    `#${item.analysis_id} · ` +
                    assessmentDate(item.analysis_date),
                    String(item.analysis_id)
                ));
            }

            select.value = record.ai_analysis_id == null
                ? ''
                : String(record.ai_analysis_id);

            status.textContent = assessmentOptions.length
                ? `${assessmentOptions.length} assessment(s) available.`
                : 'No assessments recorded for this patient yet.';
        } catch (error) {
            if (request !== assessmentRequest) return;

            status.textContent = error.message;
            get('assessment-retry').hidden = false;
        } finally {
            if (request === assessmentRequest) {
                assessmentLoading = false;
                updateAssessmentControls();
            }
        }
    }

    get('consultation-assessment').addEventListener('change', () => {
        if (
            busy ||
            needsReload ||
            !record ||
            record.status !== 'draft'
        ) return;

        const value = get('consultation-assessment').value;

        record.ai_analysis_id = value ? Number(value) : null;
        record.ai_assessment = assessmentOptions.find(
            item => item.analysis_id === record.ai_analysis_id
        ) || null;

        showAssessment(record.ai_assessment);
        dirty = true;
    });

    get('assessment-retry').addEventListener('click', () => {
        if (!busy && !assessmentLoading) {
            loadAssessments();
        }
    });

    function renderAppointment(appointment) {
        const root = get('consultation-appointment-details');
        root.replaceChildren();

        const readable = value => {
            if (!value) return 'Not recorded';

            return value
                .replaceAll('_', ' ')
                .replace(/\b\w/g, letter => letter.toUpperCase());
        };

        const [year, month, day] =
            appointment.appointment_date.split('-');

        const fields = [
            ['Appointment', `#${appointment.appointment_id}`],
            ['Date', `${day}/${month}/${year}`],
            [
                'Time',
                `${appointment.start_time.slice(0, 5)}–` +
                appointment.end_time.slice(0, 5),
            ],
            ['Type', readable(appointment.appointment_type)],
            ['Veterinarian', appointment.veterinarian_name],
            ['Status', readable(appointment.status)],
            ['Booking source', readable(appointment.appointment_source)],
        ];

        for (const [label, value] of fields) {
            const item = document.createElement('div');
            const term = document.createElement('dt');
            const description = document.createElement('dd');

            term.textContent = label;
            description.textContent = value || 'Not recorded';

            item.append(term, description);
            root.appendChild(item);
        }
    }

    function renderFollowup(data) {
        get('followup-required').checked =
            Boolean(data.followup_required);

        get('followup-fields').hidden = !data.followup_required;
        get('followup-date').value =
            data.followup_recommended_date || '';
        get('followup-reason').value = data.followup_reason || '';
        get('followup-instructions').value =
            data.followup_instructions || '';

        const completed = data.status === 'completed';
        get('followup-readview').hidden = !completed;

        const root = get('followup-readview-content');
        root.replaceChildren();

        if (!completed) return;

        const entries = data.followup_required
            ? [
                [
                    'Recommended review date',
                    data.followup_recommended_date,
                ],
                ['Reason for review', data.followup_reason],
                ['Home-care instructions', data.followup_instructions],
            ]
            : [['Follow-up', 'Not required']];

        if (data.followup_required) {
            entries.push(
                [
                    'Owner photo submission required',
                    data.followup_photos_required ? 'Yes' : 'No',
                ],
                [
                    'In-clinic review required',
                    data.followup_visit_required ? 'Yes' : 'No',
                ]
            );

            if (data.followup_photos_required) {
                entries.push([
                    'Photo requirements',
                    data.followup_photo_instructions,
                ]);
            }
        }

        for (const [label, value] of entries) {
            const paragraph = document.createElement('p');
            const heading = document.createElement('strong');

            heading.textContent = `${label}: `;
            paragraph.append(
                heading,
                document.createTextNode(value || 'Not recorded')
            );
            root.appendChild(paragraph);
        }

        if (data.followup_required) {
            const note = document.createElement('p');
            note.className = 'muted';
            note.textContent =
                'A follow-up task was created when this consultation ' +
                'was completed. Check Follow-up Care for its current status.';

            root.appendChild(note);
        }
    }

    get('followup-required').addEventListener('change', () => {
        get('followup-fields').hidden =
            !get('followup-required').checked;

        dirty = true;
    });

    function renderReturnVisit(context) {
        const panel = get('consultation-return-visit');
        const root = get('return-visit-context-details');

        panel.hidden = !context;
        root.replaceChildren();

        if (!context) return;

        get('return-visit-context-title').textContent =
            context.source_type === 'treatment'
                ? 'Planned Treatment Visit'
                : 'Follow-up Review Visit';

        const entries = [
            ['Purpose', context.title],
            ['Reason', context.reason],
            ['Original consultation', `#${context.original_consultation_id}`],
        ];

        if (context.care_instructions) {
            entries.push([
                'Previous care instructions',
                context.care_instructions,
            ]);
        }

        for (const [label, value] of entries) {
            const paragraph = document.createElement('p');
            const heading = document.createElement('strong');

            heading.textContent = `${label}: `;
            paragraph.append(
                heading,
                document.createTextNode(value || 'Not recorded')
            );

            root.appendChild(paragraph);
        }
    }

    function renderBookingAIReview(review) {
        const section = get('booking-ai-review');
        const root = get('booking-ai-review-details');

        root.replaceChildren();
        section.hidden = !review;

        if (!review) return;

        const severityLabels = {
            none: 'No concern identified from the image',
            mild: 'Mild',
            moderate: 'Moderate',
            severe: 'Severe',
            unable_to_assess: 'Unable to assess from the image',
        };

        const actionLabels = {
            routine_booking: 'Routine appointment',
            prompt_clinic_assessment: 'Prompt clinic assessment',
            home_care: 'Home-care guidance',
            unable_to_assess: 'Unable to advise from the image',
        };

        const fields = [
            ['Original assessment', `#${review.analysis_id}`],
            [
                'Reviewed by',
                review.reviewed_by_name || 'Not recorded',
            ],
            ['Review date', assessmentDate(review.reviewed_at)],
            [
                'Reviewed severity',
                severityLabels[review.reviewed_severity]
                || review.reviewed_severity,
            ],
            [
                'Recommended action',
                actionLabels[review.recommended_action]
                || review.recommended_action,
            ],
            ['Feedback for owner', review.feedback],
        ];

        for (const [label, value] of fields) {
            const paragraph = document.createElement('p');
            const heading = document.createElement('strong');

            heading.textContent = `${label}: `;
            paragraph.style.whiteSpace = 'pre-wrap';
            paragraph.style.overflowWrap = 'anywhere';

            paragraph.append(
                heading,
                document.createTextNode(value || 'Not recorded')
            );

            root.appendChild(paragraph);
        }

        const link = document.createElement('a');

        link.href =
            '/web/vet/ai_assessments.html?review=' +
            review.review_id;

        link.textContent = 'Open original assessment review';
        root.appendChild(link);
    }

    function render(data) {
        record = data;
        renderPrescriptionPrint(data);
        needsReload = false;

        ++assessmentRequest;
        assessmentsLoaded = false;
        assessmentLoading = false;

        get('assessment-picker').hidden =
            data.status === 'completed';

        get('assessment-message').textContent = '';
        get('assessment-retry').hidden = true;

        showAssessment(data.ai_assessment);
        renderBookingAIReview(data.booking_ai_review);

        if (data.status === 'draft') {
            loadAssessments();
        }

        get('consultation-patient').textContent = data.pet_name;

        renderPatient(data.patient);
        renderFollowup(data);
        renderAppointment(data.appointment);
        renderReturnVisit(data.return_visit);

        get('consultation-summary').textContent =
            `Owner: ${data.owner_name} · ` +
            `Appointment #${data.appointment_id}`;

        get('consultation-state').textContent =
            data.status === 'completed'
                ? 'Completed · Read-only record'
                : 'Draft · Save your changes before leaving.';

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

        get('followup-photos-required').checked =
            Boolean(data.followup_photos_required);

        get('followup-photo-instructions').value =
            data.followup_photo_instructions || '';

        get('followup-photo-fields').hidden =
            !data.followup_photos_required;

        get('followup-visit-required').checked =
            Boolean(data.followup_visit_required);

        const completed = data.status === 'completed';

        form.hidden = completed;
        get('consultation-readview').hidden = !completed;

        document.querySelector('.page-heading h1').textContent =
            completed ? 'Consultation Record' : 'Consultation';

        if (completed) {
            renderCompleted(data);
        } else {
            get('consultation-readview').replaceChildren();
        }

        for (const id of [
            'add-treatment',
            'add-prescription',
            'save-consultation',
            'complete-consultation'
        ]) {
            get(id).hidden = completed;
        }

        dirty = false;
        reload.hidden = true;
    }

    get('followup-photos-required').addEventListener('change', () => {
        get('followup-photo-fields').hidden =
            !get('followup-photos-required').checked;

        markDirty();
    });

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

        const followupRequired =
            get('followup-required').checked;

        if (complete && followupRequired) {
            const date = get('followup-date');
            const reason = get('followup-reason');

            if (!date.value || date.value < today()) {
                message.textContent =
                    'Choose a follow-up date of today or later.';
                date.focus();
                return;
            }

            if (!reason.value.trim()) {
                message.textContent = 'Enter the reason for follow-up.';
                reason.focus();
                return;
            }
        }

        if (
            complete &&
            followupRequired &&
            get('followup-photos-required').checked &&
            !get('followup-photo-instructions').value.trim()
        ) {
            message.textContent =
                'Describe the photos the owner needs to submit.';
            get('followup-photo-instructions').focus();
            return;
        }

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
            ai_analysis_id: record.ai_analysis_id ?? null,
            complete,
            treatments: readRows('treatment'),
            prescriptions: readRows('prescription'),
            followup_required: followupRequired,
            followup_recommended_date: followupRequired
                ? get('followup-date').value || null
                : null,
            followup_reason: followupRequired
                ? get('followup-reason').value.trim() || null
                : null,
            followup_instructions: followupRequired
                ? get('followup-instructions').value.trim() || null
                : null,

            followup_photos_required:
                followupRequired &&
                get('followup-photos-required').checked,

            followup_photo_instructions:
                followupRequired &&
                    get('followup-photos-required').checked
                    ? get('followup-photo-instructions').value.trim() || null
                    : null,

            followup_visit_required:
                followupRequired &&
                get('followup-visit-required').checked,
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