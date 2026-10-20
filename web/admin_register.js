const registrationForm = document.getElementById('admin-registration-form');
const registrationFields = document.getElementById('registration-fields');
const registrationMessage = document.getElementById('registration-message');
const registrationSubmit = document.getElementById('registration-submit');
const registrationRetry = document.getElementById('registration-retry');

const registrationName = document.getElementById('registration-name');
const registrationEmail = document.getElementById('registration-email');
const registrationPhone = document.getElementById('registration-phone');
const registrationClinic = document.getElementById('registration-clinic');
const registrationPassword = document.getElementById('registration-password');
const registrationConfirm = document.getElementById('registration-confirm');

let registrationBusy = false;
let registrationClinicsReady = false;

async function registrationRequest(path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);

    try {
        const response = await fetch(path, {
            method: body === undefined ? 'GET' : 'POST',
            headers: body === undefined
                ? { Accept: 'application/json' }
                : {
                    Accept: 'application/json',
                    'Content-Type': 'application/json'
                },
            credentials: 'omit',
            cache: 'no-store',
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: controller.signal
        });

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
                    : 'Check your registration details and try again.'
            );
        }

        return data;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) {
            throw new Error(
                body === undefined
                    ? 'Cannot load clinics. Check that the backend is running.'
                    : 'Could not confirm registration. Try logging in later or contact the system operator before submitting again.'
            );
        }

        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

async function loadRegistrationClinics() {
    if (registrationBusy) return;

    registrationBusy = true;
    registrationClinicsReady = false;
    registrationFields.disabled = true;
    registrationRetry.hidden = true;
    registrationMessage.textContent = 'Loading available clinics…';
    registrationClinic.replaceChildren();

    try {
        const clinics = [];

        for (let offset = 0; ; offset += 100) {
            const page = await registrationRequest(
                `/admin-registration/clinics?offset=${offset}&limit=100`
            );

            if (!Array.isArray(page)) {
                throw new Error('Invalid clinic directory response.');
            }

            clinics.push(...page);

            if (page.length < 100) break;
        }

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select your clinic';
        registrationClinic.appendChild(placeholder);

        for (const clinic of clinics) {
            const option = document.createElement('option');
            option.value = clinic.clinic_id;
            option.textContent = clinic.address
                ? `${clinic.clinic_name} — ${clinic.address}`
                : clinic.clinic_name;
            registrationClinic.appendChild(option);
        }

        registrationClinicsReady = true;
        registrationMessage.textContent = '';
    } catch (error) {
        registrationMessage.textContent = error.message;
        registrationRetry.hidden = false;
    } finally {
        registrationBusy = false;
        registrationFields.disabled = !registrationClinicsReady;
    }
}

document.querySelectorAll('[data-registration-password]').forEach(button => {
    button.addEventListener('click', () => {
        const input = document.getElementById(
            button.dataset.registrationPassword
        );
        const show = input.type === 'password';
        const confirmation = input === registrationConfirm;

        input.type = show ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(show));
        button.setAttribute(
            'aria-label',
            `${show ? 'Hide' : 'Show'} ${confirmation ? 'confirmation password' : 'password'
            }`
        );
    });
});

for (const input of [
    registrationName,
    registrationPassword,
    registrationConfirm
]) {
    input.addEventListener('input', () => {
        registrationName.setCustomValidity('');
        registrationPassword.setCustomValidity('');
        registrationConfirm.setCustomValidity('');
    });
}

registrationForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (registrationBusy || !registrationClinicsReady || window.clinicMapSearching)
        return;

    registrationName.setCustomValidity(
        registrationName.value.trim() ? '' : 'Full name cannot be blank.'
    );

    registrationPassword.setCustomValidity(
        new TextEncoder().encode(registrationPassword.value).length > 72
            ? 'Password must not exceed 72 UTF-8 bytes.'
            : ''
    );

    registrationConfirm.setCustomValidity(
        registrationConfirm.value === registrationPassword.value
            ? ''
            : 'The passwords do not match.'
    );

    if (!registrationForm.reportValidity()) return;

    const mapSelection = window.clinicMapSelection;

    let clinicChoice;

    if (window.clinicManualMode) {
        const manualName = document.getElementById('manual-clinic-name');
        const manualAddress = document.getElementById('manual-clinic-address');

        manualName.setCustomValidity(
            manualName.value.trim() ? '' : 'Clinic name cannot be blank.'
        );

        manualAddress.setCustomValidity(
            manualAddress.value.trim() ? '' : 'Clinic address cannot be blank.'
        );

        if (!registrationForm.reportValidity()) return;

        clinicChoice = {
            manual_clinic: {
                clinic_name: manualName.value.trim(),
                address: manualAddress.value.trim()
            }
        };
    } else if (mapSelection) {
        clinicChoice = {
            selection_token: mapSelection.selection_token
        };
    } else if (registrationClinic.value) {
        clinicChoice = {
            clinic_id: Number(registrationClinic.value)
        };
    } else {
        registrationMessage.textContent =
            'Select a clinic result or enter your clinic manually.';
        return;
    }

    const body = {
        full_name: registrationName.value.trim(),
        email: registrationEmail.value.trim(),
        phone_number: registrationPhone.value.trim() || null,
        password: registrationPassword.value,
        ...clinicChoice
    };

    registrationBusy = true;
    registrationFields.disabled = true;
    registrationSubmit.textContent = 'Submitting…';
    registrationMessage.textContent = '';

    try {
        const data = await registrationRequest('/admin-registration', body);

        if (typeof data.message !== 'string') {
            throw new Error('Unexpected registration response.');
        }

        registrationForm.reset();
        window.clinicMapSelection = null;
        document.getElementById('registration-section').hidden = true;
        document.getElementById('registration-success').hidden = false;
        document.getElementById('registration-success-message').textContent =
            data.message;
    } catch (error) {
        registrationMessage.textContent = error.message;
    } finally {
        body.password = '';
        registrationBusy = false;
        registrationFields.disabled = !registrationClinicsReady;
        registrationSubmit.textContent = 'Submit registration';
    }
});

registrationRetry.addEventListener('click', loadRegistrationClinics);
loadRegistrationClinics();

for (const id of ['manual-clinic-name', 'manual-clinic-address']) {
    document.getElementById(id).addEventListener('input', event => {
        event.target.setCustomValidity('');
    });
}