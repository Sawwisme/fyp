(() => {
    const get = id => document.getElementById(id);

    const form = get('booking-payment-form');
    const fields = get('booking-payment-fields');
    const amount = get('booking-deposit-amount');
    const summary = get('booking-payment-summary');
    const message = get('booking-payment-message');
    const reload = get('booking-payment-reload');
    const save = get('booking-payment-save');

    const endpoint = '/clinics/me/booking-payment-settings';

    let busy = false;
    let saved = null;

    function controls() {
        fields.disabled = busy || !saved;
        save.disabled = busy || !saved;
        reload.disabled = busy;

        form.setAttribute('aria-busy', String(busy));
    }

    function showMessage(text, success = false) {
        message.textContent = text;
        message.classList.toggle('success', success);
    }

    function applySettings(data) {
        const value = Number(data?.deposit_amount);

        if (
            !Number.isInteger(data?.clinic_id) ||
            !Number.isInteger(data?.version) ||
            data.version < 1 ||
            data.deposit_amount == null ||
            !Number.isFinite(value) ||
            value < 0 ||
            value > 30000 ||
            (value > 0 && value < 1)
        ) {
            throw new Error('Invalid deposit settings response.');
        }

        saved = data;
        amount.value = value.toFixed(2);

        summary.textContent = value === 0
            ? 'No appointment deposit required.'
            : `Saved deposit: RM ${value.toFixed(2)} per appointment.`;
    }

    async function loadSettings() {
        if (busy) return;

        busy = true;
        controls();
        showMessage('Loading…');

        try {
            const data = await apiRequest(endpoint);
            applySettings(data);
            showMessage('');
        } catch (error) {
            saved = null;
            summary.textContent = 'Deposit settings unavailable.';
            showMessage(error.message);
        } finally {
            busy = false;
            controls();
        }
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (busy || !saved) return;

        amount.setCustomValidity('');

        if (!form.reportValidity()) return;

        const rawAmount = amount.value.trim();

        if (!/^\d+(?:\.\d{1,2})?$/.test(rawAmount)) {
            amount.setCustomValidity(
                'Enter an amount with up to two decimal places.'
            );
            amount.reportValidity();
            return;
        }

        const value = Number(rawAmount);

        if (value > 0 && value < 1) {
            amount.setCustomValidity(
                'Enter RM 0 for no deposit, or at least RM 1.'
            );
            amount.reportValidity();
            return;
        }

        busy = true;
        controls();
        showMessage('Saving…');

        try {
            const data = await apiRequest(endpoint, {
                method: 'PUT',
                body: {
                    deposit_amount: rawAmount,
                    expected_version: saved.version,
                },
            });

            applySettings(data);
            showMessage('Deposit setting saved.', true);
        } catch (error) {
            // Reload before another save. A timed-out request
            // may already have been committed by the server.
            saved = null;

            summary.textContent =
                'Reload to confirm the saved deposit setting.';

            showMessage(
                `${error.message} Reload before saving again.`
            );
        } finally {
            busy = false;
            controls();
        }
    });

    amount.addEventListener('input', () => {
        amount.setCustomValidity('');
    });

    reload.addEventListener('click', loadSettings);

    window.addEventListener(
        'admin-profile-ready',
        loadSettings
    );

    if (currentProfile) loadSettings();
})();