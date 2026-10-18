const tokenKey = 'vetdental_staff_token';

const loading = document.getElementById('loading');
const loadingMessage = document.getElementById('loading-message');
const retryButton = document.getElementById('retry-button');
const dashboard = document.getElementById('dashboard');
const pageMessage = document.getElementById('page-message');

const editDialog = document.getElementById('edit-profile-dialog');
const editForm = document.getElementById('edit-profile-form');
const editFields = document.getElementById('edit-profile-fields');
const editMessage = document.getElementById('edit-profile-message');
const saveButton = document.getElementById('save-profile-button');
const closeButton = document.getElementById('close-edit-profile');
const cancelButton = document.getElementById('cancel-edit-profile');

const fullNameInput = document.getElementById('edit-full-name');
const emailInput = document.getElementById('edit-email');
const phoneInput = document.getElementById('edit-phone');
const clinicInput = document.getElementById('edit-clinic');

let currentProfile = null;
let loadingAccount = false;
let savingProfile = false;

function setText(id, value) {
    document.getElementById(id).textContent = value;
}

function showView(focusHeading = false) {
    const view = window.location.hash === '#profile'
        ? 'profile'
        : 'dashboard';

    document.getElementById('dashboard-view').hidden =
        view !== 'dashboard';

    document.getElementById('profile-view').hidden =
        view !== 'profile';

    document.querySelectorAll('[data-view]').forEach(link => {
        const active = link.dataset.view === view;

        link.classList.toggle('active', active);

        if (active) {
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    });

    document.title = view === 'profile'
        ? 'VetDental — Profile'
        : 'VetDental — Dashboard';

    if (focusHeading && !dashboard.hidden) {
        document.getElementById(`${view}-title`).focus();
    }
}

function renderProfile(profile) {
    const user = profile.user;

    const initials = user.full_name
        .trim()
        .split(/\s+/)
        .slice(0, 2)
        .map(part => Array.from(part)[0])
        .join('')
        .toUpperCase();

    setText('admin-name', user.full_name);
    setText('topbar-name', user.full_name);
    setText('topbar-avatar', initials);
    setText('profile-avatar', initials);
    setText('profile-name', user.full_name);
    setText('profile-status', user.status);
    setText('account-name', user.full_name);
    setText('account-email', user.email);
    setText('account-phone', user.phone_number || 'Not provided');
    setText('account-id', String(user.user_id));
    setText('account-clinic', profile.clinic_name);

    setText(
        'account-created',
        typeof user.created_at === 'string'
            ? user.created_at.split('T')[0]
            : 'Not available'
    );
}

function returnToLogin() {
    sessionStorage.removeItem(tokenKey);
    window.location.replace('/web/');
}

async function apiRequest(path, { method = 'GET', body, networkError } = {}) {
    const token = sessionStorage.getItem(tokenKey);

    if (!token) {
        returnToLogin();
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
            method,
            headers,
            credentials: 'omit',
            cache: 'no-store',
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: controller.signal
        });

        if (response.status === 401) {
            returnToLogin();
            throw new Error('Your session has expired. Please log in again.');
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
            throw new Error(
                networkError || (
                    method === 'GET'
                        ? 'Cannot reach the server. Check that the backend is running.'
                        : 'Could not confirm the save. Reload your profile to check before trying again.'
                )
            );
        }

        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

async function loadDashboard() {
    if (loadingAccount) return;

    loadingAccount = true;
    retryButton.hidden = true;
    loadingMessage.textContent = 'Loading your workspace…';

    try {
        const profile = await apiRequest('/admins/me');

        if (profile.user.role !== 'clinic_administrator') {
            throw new Error('This page requires an administrator account.');
        }

        currentProfile = profile;
        renderProfile(profile);
        showView();

        loading.hidden = true;
        dashboard.hidden = false;
    } catch (error) {
        loadingMessage.textContent = error.message;
        retryButton.hidden = false;
    } finally {
        loadingAccount = false;
    }
}

function setSaving(busy) {
    savingProfile = busy;
    editFields.disabled = busy;
    saveButton.disabled = busy;
    closeButton.disabled = busy;
    cancelButton.disabled = busy;
    saveButton.textContent = busy ? 'Saving…' : 'Save changes';
}

document.getElementById('edit-profile-button')
    .addEventListener('click', () => {
        if (!currentProfile) return;

        const user = currentProfile.user;

        fullNameInput.value = user.full_name;
        emailInput.value = user.email;
        phoneInput.value = user.phone_number || '';
        clinicInput.value = currentProfile.clinic_name;

        fullNameInput.setCustomValidity('');
        clinicInput.setCustomValidity('');
        editMessage.textContent = '';
        pageMessage.textContent = '';

        editDialog.showModal();
        fullNameInput.focus();
    });

for (const input of [fullNameInput, clinicInput]) {
    input.addEventListener('input', () => input.setCustomValidity(''));
}

function closeEditor() {
    if (!savingProfile) {
        editDialog.close();
    }
}

closeButton.addEventListener('click', closeEditor);
cancelButton.addEventListener('click', closeEditor);

editDialog.addEventListener('cancel', event => {
    if (savingProfile) {
        event.preventDefault();
    }
});

editForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (savingProfile) return;

    for (const input of [fullNameInput, clinicInput]) {
        input.setCustomValidity(
            input.value.trim() ? '' : 'This field cannot be blank.'
        );
    }

    if (!editForm.reportValidity()) return;

    const body = {
        full_name: fullNameInput.value.trim(),
        phone_number: phoneInput.value.trim() || null,
        clinic_name: clinicInput.value.trim()
    };

    editMessage.textContent = '';
    setSaving(true);

    try {
        const profile = await apiRequest('/admins/me', {
            method: 'PATCH',
            body
        });

        currentProfile = profile;
        renderProfile(profile);
        editDialog.close();

        pageMessage.classList.add('success');
        pageMessage.textContent = 'Profile updated successfully.';
    } catch (error) {
        editMessage.textContent = error.message;
    } finally {
        setSaving(false);
    }
});

window.addEventListener('hashchange', () => {
    pageMessage.textContent = '';
    showView(true);
});

retryButton.addEventListener('click', loadDashboard);

document.getElementById('logout-button').addEventListener('click', () => {
    try {
        returnToLogin();
    } catch (_) {
        pageMessage.classList.remove('success');
        pageMessage.textContent = 'Unable to log out. Please try again.';
    }
});

loadDashboard();

const passwordDialog = document.getElementById('password-dialog');
const passwordForm = document.getElementById('password-form');
const passwordFields = document.getElementById('password-fields');
const passwordMessage = document.getElementById('password-message');
const savePasswordButton = document.getElementById('save-password');
const closePasswordButton = document.getElementById('close-password');
const cancelPasswordButton = document.getElementById('cancel-password');

const currentPasswordInput = document.getElementById('current-password');
const newPasswordInput = document.getElementById('new-password');
const confirmPasswordInput = document.getElementById('confirm-password');

let changingPassword = false;

function resetPasswordForm() {
    passwordForm.reset();
    passwordMessage.textContent = '';

    for (const input of [
        currentPasswordInput,
        newPasswordInput,
        confirmPasswordInput
    ]) {
        input.type = 'password';
        input.setCustomValidity('');
    }

    document.querySelectorAll('[data-password-target]').forEach(button => {
        const input = document.getElementById(button.dataset.passwordTarget);
        const label = document.querySelector(`label[for="${input.id}"]`);

        button.setAttribute('aria-pressed', 'false');
        button.setAttribute(
            'aria-label',
            `Show ${label.textContent.trim().toLowerCase()}`
        );
    });
}

document.getElementById('change-password-button')
    .addEventListener('click', () => {
        resetPasswordForm();
        passwordDialog.showModal();
        currentPasswordInput.focus();
    });

document.querySelectorAll('[data-password-target]').forEach(button => {
    button.addEventListener('click', () => {
        const input = document.getElementById(button.dataset.passwordTarget);
        const label = document.querySelector(`label[for="${input.id}"]`);
        const show = input.type === 'password';

        input.type = show ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(show));
        button.setAttribute(
            'aria-label',
            `${show ? 'Hide' : 'Show'} ${label.textContent.trim().toLowerCase()}`
        );
    });
});

for (const input of [
    currentPasswordInput,
    newPasswordInput,
    confirmPasswordInput
]) {
    input.addEventListener('input', () => {
        currentPasswordInput.setCustomValidity('');
        newPasswordInput.setCustomValidity('');
        confirmPasswordInput.setCustomValidity('');
    });
}

function closePasswordDialog() {
    if (!changingPassword) {
        passwordDialog.close();
    }
}

closePasswordButton.addEventListener('click', closePasswordDialog);
cancelPasswordButton.addEventListener('click', closePasswordDialog);

passwordDialog.addEventListener('cancel', event => {
    if (changingPassword) {
        event.preventDefault();
    }
});

passwordDialog.addEventListener('close', resetPasswordForm);

passwordForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (changingPassword) return;

    passwordMessage.textContent = '';

    for (const input of [
        currentPasswordInput,
        newPasswordInput,
        confirmPasswordInput
    ]) {
        input.setCustomValidity('');
    }

    const encoder = new TextEncoder();

    for (const input of [currentPasswordInput, newPasswordInput]) {
        if (encoder.encode(input.value).length > 72) {
            input.setCustomValidity(
                'Password must not exceed 72 UTF-8 bytes.'
            );
        }
    }

    if (newPasswordInput.value === currentPasswordInput.value) {
        newPasswordInput.setCustomValidity(
            'Choose a different new password.'
        );
    }

    if (confirmPasswordInput.value !== newPasswordInput.value) {
        confirmPasswordInput.setCustomValidity(
            'The passwords do not match.'
        );
    }

    if (!passwordForm.reportValidity()) return;

    changingPassword = true;
    passwordFields.disabled = true;
    savePasswordButton.disabled = true;
    closePasswordButton.disabled = true;
    cancelPasswordButton.disabled = true;
    savePasswordButton.textContent = 'Changing…';

    try {
        await apiRequest('/auth/change-password', {
            method: 'POST',
            body: {
                current_password: currentPasswordInput.value,
                new_password: newPasswordInput.value
            },
            networkError:
                'Could not confirm the password change. Try logging in with your new password. If it does not work, try your previous password.'
        });

        resetPasswordForm();
        window.alert('Password changed successfully. Please log in again.');
        returnToLogin();
    } catch (error) {
        passwordMessage.textContent = error.message;
    } finally {
        changingPassword = false;
        passwordFields.disabled = false;
        savePasswordButton.disabled = false;
        closePasswordButton.disabled = false;
        cancelPasswordButton.disabled = false;
        savePasswordButton.textContent = 'Change password';
    }
});