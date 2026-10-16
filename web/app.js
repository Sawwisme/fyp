const tokenKey = 'vetdental_staff_token';

const loginSection = document.getElementById('login-section');
const accountSection = document.getElementById('account-section');
const form = document.getElementById('login-form');
const email = document.getElementById('email');
const password = document.getElementById('password');
const loginButton = document.getElementById('login-button');
const togglePassword = document.getElementById('toggle-password');
const message = document.getElementById('message');

function validateStaff(user) {
    if (
        !user ||
        !['clinic_administrator', 'veterinarian'].includes(user.role)
    ) {
        throw new Error(
            'This portal is for clinic staff. Pet owners use the mobile app.'
        );
    }
}

function showAccount(user) {
    validateStaff(user);

    document.getElementById('account-name').textContent = user.full_name;
    document.getElementById('account-email').textContent = user.email;
    document.getElementById('account-role').textContent =
        user.role === 'clinic_administrator'
            ? 'Clinic Administrator'
            : 'Veterinarian';

    loginSection.hidden = true;
    accountSection.hidden = false;
    password.value = '';
}

function showLogin() {
    loginSection.hidden = false;
    accountSection.hidden = true;
}

async function apiRequest(path, { body, token } = {}) {
    const headers = { Accept: 'application/json' };

    if (body) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;

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

        const data = await response.json();

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
    togglePassword.textContent = show ? 'Hide' : 'Show';
    togglePassword.setAttribute(
        'aria-label',
        show ? 'Hide password' : 'Show password'
    );
});

form.addEventListener('submit', async event => {
    event.preventDefault();
    if (loginButton.disabled) return;

    message.textContent = '';
    loginButton.disabled = true;
    togglePassword.disabled = true;
    loginButton.textContent = 'Logging in…';

    try {
        const data = await apiRequest('/auth/login', {
            body: {
                email: email.value.trim(),
                password: password.value
            }
        });

        validateStaff(data.user);

        if (typeof data.access_token !== 'string' || !data.access_token) {
            throw new Error('Invalid login response.');
        }

        sessionStorage.setItem(tokenKey, data.access_token);
        showAccount(data.user);
    } catch (error) {
        message.textContent = error.message;
    } finally {
        loginButton.disabled = false;
        togglePassword.disabled = false;
        loginButton.textContent = 'Log in';
    }
});

document.getElementById('logout-button').addEventListener('click', () => {
    sessionStorage.removeItem(tokenKey);
    message.textContent = '';
    showLogin();
});

async function restoreSession() {
    loginButton.disabled = true;

    try {
        const token = sessionStorage.getItem(tokenKey);

        if (token) {
            const user = await apiRequest('/auth/me', { token });
            showAccount(user);
        }
    } catch (error) {
        if (error.status === 401 || error.status === 403) {
            sessionStorage.removeItem(tokenKey);
        }

        showLogin();
        message.textContent = error.message;
    } finally {
        loginButton.disabled = false;
    }
}

restoreSession();