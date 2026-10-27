(() => {
    const button = document.getElementById('print-prescription');
    const sheet = document.createElement('section');

    sheet.id = 'prescription-print-sheet';
    document.body.appendChild(sheet);

    const preview = document.createElement('dialog');
    preview.id = 'prescription-preview';
    preview.setAttribute('aria-labelledby', 'prescription-preview-title');

    // Static markup only; prescription data is copied as DOM nodes.
    preview.innerHTML = `
    <div class="rx-preview-header">
        <div>
            <h2 id="prescription-preview-title">
                Prescription Preview
            </h2>
            <p>Review the prescription before printing.</p>
        </div>

        <button id="rx-preview-close" type="button"
                aria-label="Close preview">×</button>
    </div>

    <div class="rx-preview-body">
        <div id="prescription-preview-content"></div>
    </div>

    <div class="rx-preview-actions">
        <button id="rx-preview-cancel" type="button">
            Cancel
        </button>
        <button id="rx-preview-print" type="button">
            Print / Save PDF
        </button>
    </div>
`;

    document.body.appendChild(preview);

    const previewContent = document.getElementById(
        'prescription-preview-content'
    );

    document.getElementById('rx-preview-close')
        .addEventListener('click', () => preview.close());

    document.getElementById('rx-preview-cancel')
        .addEventListener('click', () => preview.close());

    document.getElementById('rx-preview-print')
        .addEventListener('click', () => {
            preview.close();

            // Remove the modal from the top layer before printing.
            requestAnimationFrame(() => {
                document.body.classList.add('printing-prescription');
                window.print();
            });
        });

    let record = null;

    function text(parent, tag, value, className = '') {
        const element = document.createElement(tag);
        element.textContent = value;
        element.className = className;
        parent.appendChild(element);
        return element;
    }

    function field(parent, label, value) {
        const paragraph = document.createElement('p');
        const heading = document.createElement('strong');

        heading.textContent = `${label}: `;
        paragraph.append(
            heading,
            document.createTextNode(value || 'Not recorded')
        );

        parent.appendChild(paragraph);
    }

    function dateLabel(value) {
        if (!value) return 'Not recorded';

        const [year, month, day] = value.split('-');
        return `${day}/${month}/${year}`;
    }

    function buildPrescription(data) {
        sheet.replaceChildren();

        const header = data.prescription_header;

        text(sheet, 'h1', header.clinic_name);

        for (const value of [
            header.clinic_address,
            header.clinic_phone,
            header.clinic_email,
        ]) {
            if (value) text(sheet, 'p', value, 'rx-contact');
        }

        text(sheet, 'h2', 'Prescription');

        const patient = document.createElement('div');
        patient.className = 'rx-patient';

        field(patient, 'Pet', data.pet_name);
        field(patient, 'Species', data.patient.species);
        field(patient, 'Owner', data.owner_name);
        field(patient, 'Consultation', `#${data.consultation_id}`);
        field(
            patient,
            'Visit date',
            dateLabel(data.appointment.appointment_date)
        );

        sheet.appendChild(patient);

        for (const [index, medication] of data.prescriptions.entries()) {
            const card = document.createElement('article');
            card.className = 'rx-medication';

            text(
                card,
                'h3',
                `${index + 1}. ${medication.medication_name}`
            );

            field(card, 'Prescription ID', `#${medication.prescription_id}`);
            field(card, 'Date', dateLabel(medication.prescription_date));
            field(card, 'Dosage', medication.dosage);
            field(card, 'Route', medication.administration_route);
            field(card, 'Frequency', medication.frequency);
            field(card, 'Duration', medication.duration);
            field(card, 'Instructions', medication.instructions);

            sheet.appendChild(card);
        }

        const footer = document.createElement('footer');
        footer.className = 'rx-footer';

        field(
            footer,
            'Prescribing veterinarian',
            header.veterinarian_name
        );
        field(
            footer,
            'Registration number',
            header.registration_number
        );

        sheet.appendChild(footer);
    }

    window.renderPrescriptionPrint = data => {
        record = data;

        button.hidden =
            data.status !== 'completed' ||
            data.prescriptions.length === 0;
    };

    button.addEventListener('click', () => {
        if (
            !record ||
            record.status !== 'completed' ||
            !record.prescriptions.length
        ) return;

        buildPrescription(record);

        previewContent.replaceChildren(
            ...Array.from(sheet.childNodes, node => node.cloneNode(true))
        );

        preview.showModal();
    });

    window.addEventListener('afterprint', () => {
        document.body.classList.remove('printing-prescription');
    });
})();