const clinicSettingsForm = document.getElementById('clinic-settings-form');
const clinicSettingsFields = document.getElementById('clinic-settings-fields');
const clinicSettingsMessage = document.getElementById('clinic-settings-message');
const saveClinicSettings = document.getElementById('save-clinic-settings');
const reloadClinicSettings = document.getElementById('reload-clinic-settings');

const clinicHoursForm = document.getElementById('clinic-hours-form');
const clinicHoursFields = document.getElementById('clinic-hours-fields');
const clinicHoursRows = document.getElementById('clinic-hours-rows');
const clinicHoursMessage = document.getElementById('clinic-hours-message');
const addClinicPeriod = document.getElementById('add-clinic-period');
const saveClinicHours = document.getElementById('save-clinic-hours');

const clinicFieldDefinitions = [
    ['address', 'Clinic address', 'text', 255],
    ['phone_number', 'Clinic phone number', 'tel', 20],
    ['email', 'Clinic email address', 'email', 255],
    ['latitude', 'Latitude', 'number', null],
    ['longitude', 'Longitude', 'number', null]
];

const clinicInputs = {};
const weekdayNames = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
    'Friday', 'Saturday', 'Sunday'
];

let clinicSettingsBusy = false;
let clinicSettingsLoaded = false;

for (const [name, title, type, maxLength] of clinicFieldDefinitions) {
    const wrapper = document.createElement('div');
    wrapper.dataset.clinicField = name;
    const label = document.createElement('label');
    const input = document.createElement('input');

    input.id = `clinic-setting-${name}`;
    input.type = type;
    label.htmlFor = input.id;
    label.className = 'field-label';
    label.textContent = title;

    if (maxLength) input.maxLength = maxLength;

    if (type === 'number') {
        input.step = '0.000001';
        input.min = name === 'latitude' ? '-90' : '-180';
        input.max = name === 'latitude' ? '90' : '180';
    }

    wrapper.append(label, input);
    clinicSettingsFields.appendChild(wrapper);
    clinicInputs[name] = input;
}

const clinicMapDetails = document.createElement('details');
clinicMapDetails.className = 'clinic-map-editor';

const clinicMapHeading = document.createElement('summary');
clinicMapHeading.textContent = 'Map coordinates (optional)';

const clinicMapFields = document.createElement('div');
clinicMapFields.className = 'clinic-map-fields';

clinicMapFields.append(
    clinicInputs.latitude.parentElement,
    clinicInputs.longitude.parentElement
);

clinicMapDetails.append(clinicMapHeading, clinicMapFields);
clinicSettingsFields.appendChild(clinicMapDetails);

function settingsMessage(element, text, success = false) {
    element.classList.toggle('success', success);
    element.textContent = text;
}

function setClinicSettingsBusy(value) {
    clinicSettingsBusy = value;

    const disabled = value || !clinicSettingsLoaded;

    clinicSettingsFields.disabled = disabled;
    clinicHoursFields.disabled = disabled;
    saveClinicSettings.disabled = disabled;
    saveClinicHours.disabled = disabled;
    reloadClinicSettings.disabled = value;
}

function fillClinicInformation(clinic) {
    for (const [name] of clinicFieldDefinitions) {
        clinicInputs[name].value = clinic[name] ?? '';
    }

    const summary = document.getElementById('clinic-contact-summary');
    summary.replaceChildren();

    const entries = [
        ['Address', clinic.address || 'Not provided'],
        ['Clinic phone', clinic.phone_number || 'Not provided'],
        ['Clinic email', clinic.email || 'Not provided'],
        [
            'Map location',
            clinic.latitude != null && clinic.longitude != null
                ? 'Coordinates saved'
                : 'Not provided'
        ]
    ];

    for (const [label, value] of entries) {
        const wrapper = document.createElement('div');
        const term = document.createElement('dt');
        const description = document.createElement('dd');

        term.textContent = label;
        description.textContent = value;

        wrapper.append(term, description);
        summary.appendChild(wrapper);
    }
}

function addOpeningPeriod(period) {
    const row = document.createElement('div');
    row.className = 'clinic-period-row';

    const day = document.createElement('select');
    day.className = 'period-day';
    day.setAttribute('aria-label', 'Weekday');

    weekdayNames.forEach((name, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = name;
        day.appendChild(option);
    });

    day.value = period.weekday;

    const start = document.createElement('input');
    start.type = 'time';
    start.step = '60';
    start.required = true;
    start.className = 'period-start';
    start.value = period.start_time.slice(0, 5);
    start.setAttribute('aria-label', 'Opening time');

    const end = document.createElement('input');
    end.type = 'time';
    end.step = '60';
    end.required = true;
    end.className = 'period-end';
    end.value = period.end_time.slice(0, 5);
    end.setAttribute('aria-label', 'Closing time');

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary compact-button';
    remove.textContent = 'Remove';
    remove.addEventListener('click', () => row.remove());

    row.append(day, start, end, remove);
    clinicHoursRows.appendChild(row);
}

function fillClinicHours(periods) {
    clinicHoursRows.replaceChildren();

    for (const period of periods) {
        addOpeningPeriod(period);
    }

    const summary = document.getElementById('clinic-week-summary');
    summary.replaceChildren();

    weekdayNames.forEach((name, weekday) => {
        const row = document.createElement('div');
        const dayLabel = document.createElement('span');
        const hoursLabel = document.createElement('span');

        row.className = 'clinic-day-summary';
        dayLabel.textContent = name;

        const dayPeriods = periods
            .filter(period => period.weekday === weekday)
            .sort((a, b) => a.start_time.localeCompare(b.start_time));

        hoursLabel.textContent = dayPeriods.length
            ? dayPeriods.map(period =>
                `${period.start_time.slice(0, 5)}–${period.end_time.slice(0, 5)}`
            ).join('  /  ')
            : 'Closed';

        hoursLabel.classList.toggle('closed-day', !dayPeriods.length);

        row.append(dayLabel, hoursLabel);
        summary.appendChild(row);
    });
}

async function loadClinicSettings() {
    if (clinicSettingsBusy || !currentProfile) return;

    setClinicSettingsBusy(true);
    settingsMessage(clinicSettingsMessage, 'Loading clinic settings…');
    settingsMessage(clinicHoursMessage, '');

    try {
        const [clinic, periods] = await Promise.all([
            apiRequest('/clinics/me'),
            apiRequest('/clinics/me/working-hours')
        ]);

        fillClinicInformation(clinic);
        fillClinicHours(periods);
        clinicSettingsLoaded = true;

        settingsMessage(clinicSettingsMessage, '');
    } catch (error) {
        settingsMessage(clinicSettingsMessage, error.message);
    } finally {
        setClinicSettingsBusy(false);
    }
}

reloadClinicSettings.addEventListener('click', () => {
    if (
        clinicSettingsLoaded &&
        !window.confirm('Reload saved settings and discard unsaved changes?')
    ) return;

    loadClinicSettings();
});

addClinicPeriod.addEventListener('click', () => {
    if (clinicHoursRows.children.length >= 84) {
        settingsMessage(
            clinicHoursMessage,
            'A maximum of 84 opening periods is allowed.'
        );
        return;
    }

    // A draft only: it is not saved until Save weekly hours is clicked.
    addOpeningPeriod({
        weekday: 0,
        start_time: '09:00',
        end_time: '17:00'
    });
});

clinicSettingsForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (clinicSettingsBusy || !clinicSettingsLoaded) return;

    const body = {};

    for (const [name] of clinicFieldDefinitions) {
        body[name] = clinicInputs[name].value.trim() || null;
    }

    if ((body.latitude === null) !== (body.longitude === null)) {
        settingsMessage(
            clinicSettingsMessage,
            'Enter both latitude and longitude, or clear both.'
        );
        return;
    }

    if (!clinicSettingsForm.reportValidity()) return;

    setClinicSettingsBusy(true);
    settingsMessage(clinicSettingsMessage, 'Saving…');

    try {
        const clinic = await apiRequest('/clinics/me', {
            method: 'PATCH',
            body
        });

        fillClinicInformation(clinic);

        settingsMessage(
            clinicSettingsMessage,
            'Clinic information saved.',
            true
        );
    } catch (error) {
        settingsMessage(clinicSettingsMessage, error.message);
    } finally {
        setClinicSettingsBusy(false);
    }
});

clinicHoursForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (clinicSettingsBusy || !clinicSettingsLoaded) return;

    const periods = Array.from(clinicHoursRows.children).map(row => ({
        weekday: Number(row.querySelector('.period-day').value),
        start_time: row.querySelector('.period-start').value,
        end_time: row.querySelector('.period-end').value
    }));

    const ordered = [...periods].sort(
        (a, b) =>
            a.weekday - b.weekday ||
            a.start_time.localeCompare(b.start_time)
    );

    if (ordered.some(period => period.end_time <= period.start_time)) {
        settingsMessage(
            clinicHoursMessage,
            'Each closing time must be later than its opening time.'
        );
        return;
    }

    for (let index = 1; index < ordered.length; index++) {
        const previous = ordered[index - 1];
        const current = ordered[index];

        if (
            previous.weekday === current.weekday &&
            previous.end_time > current.start_time
        ) {
            settingsMessage(
                clinicHoursMessage,
                'Opening periods on the same day cannot overlap.'
            );
            return;
        }
    }

    if (
        periods.length === 0 &&
        !window.confirm('Save no opening periods? This marks every day as closed.')
    ) return;

    if (!clinicHoursForm.reportValidity()) return;

    setClinicSettingsBusy(true);
    settingsMessage(clinicHoursMessage, 'Saving…');

    try {
        const saved = await apiRequest('/clinics/me/working-hours', {
            method: 'PUT',
            body: { periods }
        });

        fillClinicHours(saved);

        settingsMessage(
            clinicHoursMessage,
            'Weekly working hours saved.',
            true
        );
    } catch (error) {
        settingsMessage(clinicHoursMessage, error.message);
    } finally {
        setClinicSettingsBusy(false);
    }
});

window.addEventListener('admin-profile-ready', loadClinicSettings);

// Also handles a session that loaded before this script finished loading.
if (currentProfile) loadClinicSettings();