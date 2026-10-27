(() => {
    function statusLabel(value) {
        return (value || 'Not recorded')
            .replaceAll('_', ' ')
            .replace(/\b\w/g, letter => letter.toUpperCase());
    }

    function timestamp(value) {
        if (!value) return 'Not recorded';

        const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
            ? value
            : `${value}Z`;

        const date = new Date(normalized);

        return Number.isNaN(date.getTime())
            ? 'Not recorded'
            : date.toLocaleString('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur',
                dateStyle: 'medium',
                timeStyle: 'short',
            });
    }

    window.createTreatmentDetails = item => {
        const root = document.createElement('dl');
        root.className = 'treatment-progress-details';

        const progress = item.progress_record;

        function entry(label, value, consultationId = null) {
            const wrapper = document.createElement('div');
            const term = document.createElement('dt');
            const description = document.createElement('dd');

            term.textContent = label;

            if (consultationId) {
                const link = document.createElement('a');
                link.href =
                    `/web/vet/consultation.html?id=${consultationId}`;
                link.textContent = `Consultation #${consultationId}`;
                description.appendChild(link);
            } else {
                description.textContent = value || 'Not recorded';
            }

            wrapper.append(term, description);
            root.appendChild(wrapper);
        }

        entry(
            'Originally recorded',
            statusLabel(item.recorded_status ?? item.status)
        );

        entry(
            'Current treatment status',
            statusLabel(progress?.status ?? item.status)
        );

        if (progress?.started_at) {
            entry('Started', timestamp(progress.started_at));
        }

        if (progress?.start_consultation_id) {
            entry(
                'Starting visit',
                null,
                progress.start_consultation_id
            );
        }

        if (progress?.start_notes) {
            entry('Initial treatment notes', progress.start_notes);
        }

        if (progress?.completed_at) {
            entry('Completed', timestamp(progress.completed_at));
        }

        if (progress?.completion_consultation_id) {
            entry(
                'Completion visit',
                null,
                progress.completion_consultation_id
            );
        }

        if (progress?.cancelled_at) {
            entry('Cancelled', timestamp(progress.cancelled_at));
        }

        if (progress?.cancellation_reason) {
            entry('Cancellation reason', progress.cancellation_reason);
        }

        return root;
    };
})();