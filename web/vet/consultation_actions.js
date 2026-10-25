(() => {
    let opening = false;

    function today() {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(new Date());

        const value = type =>
            parts.find(part => part.type === type).value;

        return `${value('year')}-${value('month')}-${value('day')}`;
    }

    window.createVetConsultationButton = (item, message) => {
        const existing =
            Number.isInteger(item.consultation_id) &&
            item.consultation_id > 0;

        if (
            !existing &&
            (
                item.status !== 'confirmed' ||
                item.appointment_date !== today()
            )
        ) {
            return null;
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary compact-button';

        const label = existing
            ? item.consultation_status === 'completed'
                ? 'View Consultation'
                : 'Continue Consultation'
            : 'Start Consultation';

        button.textContent = label;

        button.addEventListener('click', async () => {
            if (opening) return;

            opening = true;
            button.disabled = true;
            button.textContent = 'Opening…';
            message.textContent = '';

            try {
                let consultationId = item.consultation_id;

                if (!existing) {
                    const result = await vetRequest(
                        `/consultations/appointments/${item.appointment_id}/start`,
                        { method: 'POST', body: {} }
                    );

                    consultationId = result.consultation_id;
                }

                if (!Number.isInteger(consultationId)) {
                    throw new Error(
                        'Could not identify the consultation.'
                    );
                }

                window.location.assign(
                    `/web/vet/consultation.html?id=${consultationId}`
                );
            } catch (error) {
                message.textContent =
                    `${error.message} Refresh your appointments ` +
                    'to check the latest status.';
            } finally {
                opening = false;
                button.disabled = false;
                button.textContent = label;
            }
        });

        return button;
    };
})();