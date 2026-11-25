const clinicSettingsForm = document.getElementById('clinic-settings-form');
const clinicSettingsFields = document.getElementById('clinic-settings-fields');
const clinicSettingsMessage = document.getElementById('clinic-settings-message');
const saveClinicSettings = document.getElementById('save-clinic-settings');
const reloadClinicSettings = document.getElementById('reload-clinic-settings');

const clinicHoursForm = document.getElementById('clinic-hours-form');
const clinicHoursFields = document.getElementById('clinic-hours-fields');
const clinicHoursRows = document.getElementById('clinic-hours-rows');
const clinicHoursMessage = document.getElementById('clinic-hours-message');
const copyClinicWeekdays =
    document.getElementById('copy-clinic-weekdays');
const saveClinicHours = document.getElementById('save-clinic-hours');

const clinicFieldDefinitions = [
    ['address', 'Clinic address', 'text', 255],
    ['phone_number', 'Clinic phone number', 'tel', 20],
    ['email', 'Clinic email address', 'email', 255],
    ['latitude', 'Latitude', 'number', null],
    ['longitude', 'Longitude', 'number', null]
    ['state', 'State / federal territory', 'select', null],
];

const clinicInputs = {};
const weekdayNames = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
    'Friday', 'Saturday', 'Sunday'
];

let clinicSettingsBusy = false;
let clinicSettingsLoaded = false;

const clinicStateOptions = [
    'Johor', 'Kedah', 'Kelantan', 'Melaka',
    'Negeri Sembilan', 'Pahang', 'Pulau Pinang',
    'Perak', 'Perlis', 'Sabah', 'Sarawak',
    'Selangor', 'Terengganu',
    'W.P. Kuala Lumpur', 'W.P. Labuan', 'W.P. Putrajaya'
];

for (const [name, title, type, maxLength] of clinicFieldDefinitions) {
    const wrapper = document.createElement('div');
    wrapper.dataset.clinicField = name;
    const label = document.createElement('label');
    const input = document.createElement(
        type === 'select' ? 'select' : 'input'
    );

    input.id = `clinic-setting-${name}`;

    if (type === 'select') {
        const empty = document.createElement('option');
        empty.value = '';
        empty.textContent = 'Not specified';
        input.appendChild(empty);

        for (const state of clinicStateOptions) {
            const option = document.createElement('option');
            option.value = state;
            option.textContent = state;
            input.appendChild(option);
        }
    } else {
        input.type = type;
    }
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
        ['State', clinic.state || 'Not provided'],
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

function createDayEditor(weekday, periods) {
    const card = document.createElement('div');
    card.className = 'weekly-day-card';
    card.dataset.weekday = weekday;

    const heading = document.createElement('label');
    heading.className = 'weekly-day-heading';

    const open = document.createElement('input');
    open.type = 'checkbox';
    open.className = 'day-open';
    open.checked = periods.length > 0;
    open.setAttribute(
        'aria-label',
        `${weekdayNames[weekday]} open`
    );

    const title = document.createElement('strong');
    title.textContent = weekdayNames[weekday];

    const state = document.createElement('span');

    heading.append(open, title, state);

    const editor = document.createElement('fieldset');
    editor.className = 'weekly-day-periods';

    const rows = document.createElement('div');
    rows.className = 'day-period-rows';

    function updateDay() {
        state.textContent = open.checked ? 'Open' : 'Closed';
        editor.hidden = !open.checked;
        editor.disabled = !open.checked;
    }

    function addPeriod(period = {}) {
        const row = document.createElement('div');
        row.className = 'clinic-period-row';

        function timeField(labelText, className, value) {
            const wrapper = document.createElement('label');
            wrapper.className = 'weekly-time-field';

            const label = document.createElement('span');
            label.textContent = labelText;

            const input = document.createElement('input');
            input.type = 'time';
            input.step = '60';
            input.required = true;
            input.className = className;
            input.value = value ? value.slice(0, 5) : '';

            wrapper.append(label, input);
            return wrapper;
        }

        const start = timeField(
            'Opens',
            'period-start',
            period.start_time
        );

        const end = timeField(
            'Closes',
            'period-end',
            period.end_time
        );

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'secondary compact-button';
        remove.textContent = 'Remove';
        remove.setAttribute(
            'aria-label',
            `Remove ${weekdayNames[weekday]} opening period`
        );

        remove.addEventListener('click', () => {
            row.remove();

            if (!rows.children.length) {
                open.checked = false;
                updateDay();
            }
        });

        row.append(start, end, remove);
        rows.appendChild(row);
    }

    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'secondary compact-button';
    add.textContent = 'Add another opening period';

    add.addEventListener('click', () => {
        if (rows.children.length >= 12) {
            settingsMessage(
                clinicHoursMessage,
                'A maximum of 12 periods per day is allowed.'
            );
            return;
        }

        addPeriod();
    });

    for (const period of periods) addPeriod(period);

    open.addEventListener('change', () => {
        if (open.checked && !rows.children.length) {
            addPeriod({
                start_time: '09:00',
                end_time: '17:00'
            });
        }

        updateDay();
    });

    editor.append(rows, add);
    card.append(heading, editor);
    updateDay();

    return card;
}

function readDayPeriods(card) {
    if (!card.querySelector('.day-open').checked) return [];

    return [...card.querySelectorAll('.clinic-period-row')].map(
        row => ({
            weekday: Number(card.dataset.weekday),
            start_time: row.querySelector('.period-start').value,
            end_time: row.querySelector('.period-end').value
        })
    );
}

function fillClinicHours(periods) {
    clinicHoursRows.replaceChildren();

    weekdayNames.forEach((name, weekday) => {
        const dayPeriods = periods
            .filter(period => period.weekday === weekday)
            .sort((a, b) =>
                a.start_time.localeCompare(b.start_time)
            );

        clinicHoursRows.appendChild(
            createDayEditor(weekday, dayPeriods)
        );
    });

    const summary = document.getElementById('clinic-week-summary');
    summary.replaceChildren();

    weekdayNames.forEach((name, weekday) => {
        const row = document.createElement('div');
        row.className = 'clinic-day-summary';

        const dayLabel = document.createElement('span');
        dayLabel.textContent = name;

        const hoursLabel = document.createElement('span');

        const dayPeriods = periods
            .filter(period => period.weekday === weekday)
            .sort((a, b) =>
                a.start_time.localeCompare(b.start_time)
            );

        hoursLabel.textContent = dayPeriods.length
            ? dayPeriods.map(period =>
                `${period.start_time.slice(0, 5)}–${period.end_time.slice(0, 5)}`
            ).join(' / ')
            : 'Closed';

        hoursLabel.classList.toggle(
            'closed-day',
            !dayPeriods.length
        );

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

copyClinicWeekdays.addEventListener('click', () => {
    if (clinicSettingsBusy || !clinicSettingsLoaded) return;

    const monday = clinicHoursRows.querySelector(
        '[data-weekday="0"]'
    );

    const periods = readDayPeriods(monday).sort(
        (a, b) => a.start_time.localeCompare(b.start_time)
    );

    if (
        !periods.length ||
        periods.some(period =>
            !period.start_time ||
            !period.end_time ||
            period.end_time <= period.start_time
        ) ||
        periods.some((period, index) =>
            index > 0 &&
            periods[index - 1].end_time > period.start_time
        )
    ) {
        settingsMessage(
            clinicHoursMessage,
            'Set valid, non-overlapping Monday hours first.'
        );
        return;
    }

    for (let weekday = 1; weekday <= 4; weekday++) {
        const existing = clinicHoursRows.querySelector(
            `[data-weekday="${weekday}"]`
        );

        existing.replaceWith(
            createDayEditor(
                weekday,
                periods.map(period => ({
                    ...period,
                    weekday
                }))
            )
        );
    }

    settingsMessage(
        clinicHoursMessage,
        'Monday hours copied to Tuesday–Friday. Click Save weekly hours to apply.',
        true
    );
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

    if (!clinicHoursForm.reportValidity()) return;

    const periods = [
        ...clinicHoursRows.querySelectorAll('.weekly-day-card')
    ].flatMap(readDayPeriods);

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