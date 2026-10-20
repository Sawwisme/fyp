const staffTokenKey = 'vetdental_staff_token';

const staffLoading = document.getElementById('staff-loading');
const staffLoadingMessage = document.getElementById('staff-loading-message');
const staffRetry = document.getElementById('staff-retry');
const staffWorkspace = document.getElementById('staff-workspace');

const vetFormPanel = document.getElementById('vet-form-panel');
const vetForm = document.getElementById('vet-form');
const vetFields = document.getElementById('vet-fields');
const vetFormMessage = document.getElementById('vet-form-message');
const vetListMessage = document.getElementById('vet-list-message');
const vetTableBody = document.getElementById('vet-table-body');

const vetName = document.getElementById('vet-name');
const vetEmail = document.getElementById('vet-email');
const vetPassword = document.getElementById('vet-password');
const vetRegistration = document.getElementById('vet-registration');
const vetPhone = document.getElementById('vet-phone');
const vetQualification = document.getElementById('vet-qualification');

const openVetForm = document.getElementById('open-vet-form');
const cancelVet = document.getElementById('cancel-vet');
const createVet = document.getElementById('create-vet');
const refreshVets = document.getElementById('refresh-vets');
const vetPasswordToggle = document.getElementById('vet-password-toggle');

const staffRole = document.getElementById('staff-role');
const vetRegistrationField =
    document.getElementById('vet-registration-field');
const vetQualificationField =
    document.getElementById('vet-qualification-field');

let staffStarting = false;
let vetListBusy = false;
let vetCreating = false;

function staffLogin() {
    sessionStorage.removeItem(staffTokenKey);
    window.location.replace('/web/');
}

async function staffRequest(path, body) {
    const token = sessionStorage.getItem(staffTokenKey);

    if (!token) {
        staffLogin();
        throw new Error('Please log in again.');
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);

    try {
        const headers = {
            Accept: 'application/json',
            Authorization: `Bearer ${token}`
        };

        if (body !== undefined) {
            headers['Content-Type'] = 'application/json';
        }

        const response = await fetch(path, {
            method: body === undefined ? 'GET' : 'POST',
            headers,
            credentials: 'omit',
            cache: 'no-store',
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: controller.signal
        });

        if (response.status === 401) {
            staffLogin();
            throw new Error('Your session has expired.');
        }

        let data;

        try {
            data = await response.json();
        } catch (_) {
            throw new Error(
                `Unexpected server response (HTTP ${response.status}).`
            );
        }

        if (!response.ok) {
            throw new Error(
                typeof data.detail === 'string'
                    ? data.detail
                    : 'Check the entered details and try again.'
            );
        }

        return data;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) {
            throw new Error(
                body === undefined
                    ? 'Cannot reach the server. Check that the backend is running.'
                    : 'Could not confirm account creation. Refresh the staff list before trying again.'
            );
        }

        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

function updateStaffButtons() {
    openVetForm.disabled = vetListBusy || vetCreating;
    refreshVets.disabled = vetListBusy || vetCreating;
    createVet.disabled = vetListBusy || vetCreating;
    cancelVet.disabled = vetCreating;
    vetFields.disabled = vetCreating;
    createVet.textContent = vetCreating ? 'Creating…' : 'Create account';
}

async function loadVeterinarians() {
    if (vetListBusy) return;

    vetListBusy = true;
    updateStaffButtons();
    vetListMessage.textContent = 'Loading clinic staff…';
    vetTableBody.replaceChildren();

    async function loadAll(path) {
        const records = [];

        for (let offset = 0; ; offset += 100) {
            const page = await staffRequest(
                `${path}?offset=${offset}&limit=100`
            );

            if (!Array.isArray(page)) {
                throw new Error('Invalid staff list response.');
            }

            records.push(...page);

            if (page.length < 100) break;
        }

        return records;
    }

    try {
        const [vets, administrators] = await Promise.all([
            loadAll('/staff/veterinarians'),
            loadAll('/staff/administrators')
        ]);

        const staff = [
            ...administrators.map(record => ({
                user: record.user,
                role: 'Clinic Administrator',
                registration: '—'
            })),
            ...vets.map(record => ({
                user: record.user,
                role: 'Veterinarian',
                registration: record.registration_number
            }))
        ];

        staff.sort((first, second) =>
            first.user.full_name.localeCompare(second.user.full_name)
        );

        for (const person of staff) {
            const row = document.createElement('tr');

            for (const value of [
                person.user.full_name,
                person.user.email,
                person.role,
                person.registration,
                person.user.status
            ]) {
                const cell = document.createElement('td');
                cell.textContent = value;
                row.appendChild(cell);
            }

            vetTableBody.appendChild(row);
        }

        vetListMessage.textContent =
            `${staff.length} staff account(s) in your clinic.`;
    } catch (error) {
        vetListMessage.textContent = error.message;
    } finally {
        vetListBusy = false;
        updateStaffButtons();
    }
}

function updateStaffRoleFields() {
    const isVet = staffRole.value === 'veterinarian';

    vetRegistrationField.hidden = !isVet;
    vetQualificationField.hidden = !isVet;

    vetRegistration.disabled = !isVet;
    vetRegistration.required = isVet;
    vetQualification.disabled = !isVet;

    vetRegistration.setCustomValidity('');
}

staffRole.addEventListener('change', updateStaffRoleFields);

function resetVetForm() {
    vetForm.reset();
    updateStaffRoleFields();
    vetPassword.type = 'password';
    vetPasswordToggle.setAttribute('aria-pressed', 'false');
    vetPasswordToggle.setAttribute('aria-label', 'Show initial password');

    for (const input of [vetName, vetRegistration, vetPassword]) {
        input.setCustomValidity('');
    }

    vetFormMessage.textContent = '';
}

openVetForm.addEventListener('click', () => {
    resetVetForm();
    vetFormPanel.hidden = false;
    vetName.focus();
});

cancelVet.addEventListener('click', () => {
    if (vetCreating) return;

    resetVetForm();
    vetFormPanel.hidden = true;
    openVetForm.focus();
});

vetPasswordToggle.addEventListener('click', () => {
    const show = vetPassword.type === 'password';

    vetPassword.type = show ? 'text' : 'password';
    vetPasswordToggle.setAttribute('aria-pressed', String(show));
    vetPasswordToggle.setAttribute(
        'aria-label',
        show ? 'Hide initial password' : 'Show initial password'
    );
});

for (const input of [vetName, vetRegistration, vetPassword]) {
    input.addEventListener('input', () => input.setCustomValidity(''));
}

refreshVets.addEventListener('click', () => {
    if (!vetCreating) loadVeterinarians();
});

vetForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (vetCreating || vetListBusy) return;

    const isVet = staffRole.value === 'veterinarian';

    const requiredInputs = isVet
        ? [vetName, vetRegistration]
        : [vetName];

    for (const input of requiredInputs) {
        input.setCustomValidity(
            input.value.trim() ? '' : 'This field cannot be blank.'
        );
    }

    vetPassword.setCustomValidity(
        new TextEncoder().encode(vetPassword.value).length > 72
            ? 'Password must not exceed 72 UTF-8 bytes.'
            : ''
    );

    if (!vetForm.reportValidity()) return;

    const body = {
        full_name: vetName.value.trim(),
        email: vetEmail.value.trim(),
        password: vetPassword.value,
        phone_number: vetPhone.value.trim() || null
    };

    if (isVet) {
        body.registration_number = vetRegistration.value.trim();
        body.qualification = vetQualification.value.trim() || null;
    }

    const endpoint = isVet
        ? '/staff/veterinarians'
        : '/staff/administrators';

    vetCreating = true;
    updateStaffButtons();
    vetFormMessage.textContent = '';

    try {
        await staffRequest(endpoint, body);
        resetVetForm();
        vetFormPanel.hidden = true;

        await loadVeterinarians();
        window.alert('Staff account created successfully.');
    } catch (error) {
        vetFormMessage.textContent = error.message;
    } finally {
        body.password = '';
        vetCreating = false;
        updateStaffButtons();
    }
});

async function startStaffPage() {
    if (staffStarting) return;

    staffStarting = true;
    staffRetry.hidden = true;
    staffLoadingMessage.textContent = 'Loading your workspace…';

    try {
        const profile = await staffRequest('/admins/me');

        if (profile.user.role !== 'clinic_administrator') {
            throw new Error('This page requires an administrator account.');
        }

        document.getElementById('staff-admin-name').textContent =
            profile.user.full_name;

        document.getElementById('topbar-avatar').textContent =
            profile.user.full_name
                .trim()
                .split(/\s+/)
                .slice(0, 2)
                .map(part => Array.from(part)[0])
                .join('')
                .toUpperCase();

        staffLoading.hidden = true;
        staffWorkspace.hidden = false;

        await loadVeterinarians();
    } catch (error) {
        staffLoadingMessage.textContent = error.message;
        staffRetry.hidden = false;
    } finally {
        staffStarting = false;
    }
}

staffRetry.addEventListener('click', startStaffPage);

document.getElementById('staff-logout').addEventListener('click', () => {
    try {
        staffLogin();
    } catch (_) {
        vetListMessage.textContent = 'Unable to log out. Please try again.';
    }
});

startStaffPage();