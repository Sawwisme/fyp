const tokenKey = 'vetdental_staff_token';

const loginSection = document.getElementById('login-section');
const accountSection = document.getElementById('account-section');
const form = document.getElementById('login-form');
const email = document.getElementById('email');
const password = document.getElementById('password');
const roleSwitch = document.getElementById('role-switch');
const loginButton = document.getElementById('login-button');
const togglePassword = document.getElementById('toggle-password');
const forgotButton = document.getElementById('forgot-button');
const message = document.getElementById('message');

const resetDialog = document.getElementById('reset-dialog');
const resetForm = document.getElementById('reset-form');
const resetEmail = document.getElementById('reset-email');
const resetButton = document.getElementById('reset-button');
const resetMessage = document.getElementById('reset-message');

let sendingReset = false;

function setLoginBusy(busy) {
    loginButton.disabled = busy;
    email.disabled = busy;
    password.disabled = busy;
    roleSwitch.disabled = busy;
    togglePassword.disabled = busy;
    forgotButton.disabled = busy || sendingReset;
    loginButton.textContent = busy ? 'Signing in…' : 'Sign in';
}

function validateStaff(user) {
    if (
        !user ||
        !['clinic_administrator', 'veterinarian'].includes(user.role)
    ) {
        const error = new Error(
            'This portal is for clinic staff. Pet owners use the mobile app.'
        );
        error.status = 403;
        throw error;
    }
}

function hidePassword() {
    password.type = 'password';
    togglePassword.setAttribute('aria-label', 'Show password');
    togglePassword.setAttribute('aria-pressed', 'false');
    togglePassword.style.color = '';
}

function showAccount(user) {
    validateStaff(user);

    if (user.role === 'clinic_administrator') {
        window.location.replace('/web/admin/');
        return;
    }
    if (user.role === 'veterinarian') {
        window.location.replace('/web/vet/');
        return;
    }

    document.getElementById('account-name').textContent = user.full_name;
    document.getElementById('account-email').textContent = user.email;
    document.getElementById('account-role').textContent =
        user.role === 'clinic_administrator'
            ? 'Clinic Administrator'
            : 'Veterinarian';

    loginSection.hidden = true;
    accountSection.hidden = false;

    password.value = '';
    hidePassword();
}

function showLogin() {
    loginSection.hidden = false;
    accountSection.hidden = true;

    password.value = '';
    hidePassword();
}

async function apiRequest(path, { body, token } = {}) {
    const headers = { Accept: 'application/json' };

    if (body) {
        headers['Content-Type'] = 'application/json';
    }

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);

    try {
        const response = await fetch(path, {
            method: body ? 'POST' : 'GET',
            headers,
            credentials: 'omit',
            body: body ? JSON.stringify(body) : undefined,
            signal: controller.signal
        });

        let data;

        try {
            data = await response.json();
        } catch (_) {
            throw new Error(
                `Unexpected response: HTTP ${response.status} from ${response.url}`
            );
        }

        if (!response.ok) {
            const error = new Error(
                typeof data.detail === 'string'
                    ? data.detail
                    : 'Request failed. Check your details and try again.'
            );

            error.status = response.status;
            throw error;
        }

        return data;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) {
            throw new Error('Cannot reach the server. Please try again.');
        }

        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

togglePassword.addEventListener('click', () => {
    const show = password.type === 'password';

    password.type = show ? 'text' : 'password';

    togglePassword.setAttribute(
        'aria-label',
        show ? 'Hide password' : 'Show password'
    );
    togglePassword.setAttribute('aria-pressed', String(show));
    togglePassword.style.color = show ? '#176b32' : '';
});

form.addEventListener('submit', async event => {
    event.preventDefault();

    if (loginButton.disabled) return;

    const selectedRole =
        document.querySelector('input[name="staff-role"]:checked').value;

    const credentials = {
        email: email.value.trim(),
        password: password.value,
        role: selectedRole
    };

    message.textContent = '';
    setLoginBusy(true);

    try {
        const data = await apiRequest('/auth/staff-login', {
            body: credentials
        });

        validateStaff(data.user);

        if (data.user.role !== selectedRole) {
            throw new Error(
                'Select the role assigned to your clinic account.'
            );
        }

        if (typeof data.access_token !== 'string' || !data.access_token) {
            throw new Error('Invalid login response.');
        }

        sessionStorage.setItem(tokenKey, data.access_token);
        showAccount(data.user);
    } catch (error) {
        message.textContent = error.message;
    } finally {
        setLoginBusy(false);
    }
});

document.getElementById('logout-button').addEventListener('click', () => {
    try {
        sessionStorage.removeItem(tokenKey);
        message.textContent = '';
        showLogin();
    } catch (_) {
        message.textContent = 'Unable to log out. Please try again.';
    }
});

forgotButton.addEventListener('click', () => {
    resetEmail.value = email.value.trim();
    resetMessage.textContent = '';
    resetMessage.classList.remove('success');
    resetForm.hidden = false;
    resetDialog.showModal();
});

document.getElementById('close-reset').addEventListener('click', () => {
    resetDialog.close();
});

resetForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (sendingReset) return;

    sendingReset = true;
    forgotButton.disabled = true;
    resetButton.disabled = true;
    resetEmail.disabled = true;
    resetButton.textContent = 'Sending…';
    resetMessage.textContent = '';
    resetMessage.classList.remove('success');

    try {
        const data = await apiRequest('/auth/forgot-password', {
            body: { email: resetEmail.value.trim() }
        });

        if (typeof data.message !== 'string') {
            throw new Error(
                `Unexpected response: HTTP ${response.status} from ${response.url}`
            );
        }

        resetMessage.classList.add('success');
        resetMessage.textContent = data.message;
        resetForm.hidden = true;
    } catch (error) {
        resetMessage.textContent = error.message;
    } finally {
        sendingReset = false;
        forgotButton.disabled = loginButton.disabled;
        resetButton.disabled = false;
        resetEmail.disabled = false;
        resetButton.textContent = 'Send reset link';
    }
});

async function restoreSession() {
    setLoginBusy(true);

    try {
        const token = sessionStorage.getItem(tokenKey);

        if (token) {
            const user = await apiRequest('/auth/me', { token });
            showAccount(user);
        }
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            try {
                sessionStorage.removeItem(tokenKey);
            } catch (_) {
                // The login screen remains available if storage is unavailable.
            }
        }

        showLogin();
        message.textContent = error.message;
    } finally {
        setLoginBusy(false);
    }
}

restoreSession();

function updateRegistrationVisibility() {
    const selectedRole =
        document.querySelector('input[name="staff-role"]:checked')?.value;

    document.getElementById('admin-registration-link').hidden =
        selectedRole !== 'clinic_administrator';
}

roleSwitch.addEventListener('change', updateRegistrationVisibility);
window.addEventListener('pageshow', updateRegistrationVisibility);

updateRegistrationVisibility();