const pwDialog = document.getElementById('password-dialog');
const pwForm = document.getElementById('password-form');
const pwFields = document.getElementById('password-fields');
const pwMessage = document.getElementById('password-message');

const pwCurrent = document.getElementById('current-password');
const pwNew = document.getElementById('new-password');
const pwConfirm = document.getElementById('confirm-password');

const pwSave = document.getElementById('save-password');
const pwClose = document.getElementById('close-password');
const pwCancel = document.getElementById('cancel-password');

let pwSaving = false;

function resetVetPasswords() {
    pwForm.reset();
    pwMessage.textContent = '';

    for (const input of [pwCurrent, pwNew, pwConfirm]) {
        input.type = 'password';
        input.setCustomValidity('');
    }

    pwDialog.querySelectorAll('[data-password-target]').forEach(button => {
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
        resetVetPasswords();
        pwDialog.showModal();
        pwCurrent.focus();
    });

pwDialog.querySelectorAll('[data-password-target]').forEach(button => {
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

for (const input of [pwCurrent, pwNew, pwConfirm]) {
    input.addEventListener('input', () => {
        for (const field of [pwCurrent, pwNew, pwConfirm]) {
            field.setCustomValidity('');
        }
    });
}

function closeVetPasswords() {
    if (!pwSaving) pwDialog.close();
}

pwClose.addEventListener('click', closeVetPasswords);
pwCancel.addEventListener('click', closeVetPasswords);

pwDialog.addEventListener('cancel', event => {
    if (pwSaving) event.preventDefault();
});

pwDialog.addEventListener('close', resetVetPasswords);

function setPasswordSaving(busy) {
    pwSaving = busy;
    pwFields.disabled = busy;
    pwSave.disabled = busy;
    pwClose.disabled = busy;
    pwCancel.disabled = busy;
    pwSave.textContent = busy ? 'Changing…' : 'Change password';
}

pwForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (pwSaving) return;

    pwMessage.textContent = '';

    for (const input of [pwCurrent, pwNew, pwConfirm]) {
        input.setCustomValidity('');
    }

    const encoder = new TextEncoder();

    for (const input of [pwCurrent, pwNew]) {
        if (encoder.encode(input.value).length > 72) {
            input.setCustomValidity(
                'Password must not exceed 72 UTF-8 bytes.'
            );
        }
    }

    if (pwNew.value === pwCurrent.value) {
        pwNew.setCustomValidity('Choose a different new password.');
    }

    if (pwNew.value !== pwConfirm.value) {
        pwConfirm.setCustomValidity('The passwords do not match.');
    }

    if (!pwForm.reportValidity()) return;

    const body = {
        current_password: pwCurrent.value,
        new_password: pwNew.value
    };

    setPasswordSaving(true);

    try {
        await vetRequest('/auth/change-password', {
            method: 'POST',
            body
        });

        resetVetPasswords();
        window.alert('Password changed successfully. Please log in again.');
        vetLogout();
    } catch (error) {
        pwMessage.textContent = error.message;
    } finally {
        body.current_password = '';
        body.new_password = '';
        setPasswordSaving(false);
    }
});