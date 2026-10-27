(() => {
    function appointmentUrl(visit) {
        const query = new URLSearchParams({
            date: visit.appointment_date,
            appointment_id: String(visit.appointment_id),
        });

        return `/web/vet/appointments.html?${query}`;
    }

    function link(label, href) {
        const element = document.createElement('a');
        element.textContent = label;
        element.href = href;
        element.className = 'linked-visit-action';
        return element;
    }

    window.createLinkedVisitDetails = (visit, sourceType) => {
        const root = document.createElement('div');
        root.className = 'linked-visit-details';

        const heading = document.createElement('strong');
        heading.textContent = 'Linked Return Visit';
        root.appendChild(heading);

        const description = document.createElement('p');

        if (!visit) {
            description.textContent = 'No return appointment booked.';
            root.appendChild(description);
            return root;
        }

        const [year, month, day] =
            visit.appointment_date.split('-');

        const status = visit.status
            .replaceAll('_', ' ')
            .replace(/\b\w/g, letter => letter.toUpperCase());

        description.textContent =
            `#${visit.appointment_id} · ${day}/${month}/${year} · ` +
            `${visit.start_time.slice(0, 5)}–` +
            `${visit.end_time.slice(0, 5)} · ${status}`;

        root.appendChild(description);
        root.appendChild(link(
            'View Appointment',
            appointmentUrl(visit)
        ));

        if (visit.consultation_id) {
            const completed =
                visit.consultation_status === 'completed';

            root.appendChild(link(
                sourceType === 'followup' && completed
                    ? 'View Review Consultation'
                    : completed
                        ? 'View Visit Consultation'
                        : 'Continue Visit Consultation',
                `/web/vet/consultation.html?id=${visit.consultation_id}`
            ));
        }

        return root;
    };

    window.createReturnVisitBookingControl = (
        sourceType,
        sourceId,
        visit,
        onRefresh
    ) => {
        if (
            visit &&
            !['cancelled', 'rejected'].includes(visit.status)
        ) {
            return link('View Appointment', appointmentUrl(visit));
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary compact-button';
        button.textContent = visit
            ? 'Rebook Appointment'
            : 'Book Appointment';

        button.addEventListener('click', () => {
            openReturnVisitBooking(
                sourceType,
                sourceId,
                onRefresh
            );
        });

        return button;
    };
})();