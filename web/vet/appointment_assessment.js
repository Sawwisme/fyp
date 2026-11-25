(() => {
    'use strict';

    const rawId = new URLSearchParams(location.search)
        .get('appointment_id');

    const appointmentId = Number(rawId);
    const message = document.getElementById('scan-message');
    const retry = document.getElementById('scan-retry');
    const resultPanel = document.getElementById('scan-result');
    const images = document.getElementById('scan-images');
    const predictions = document.getElementById('scan-predictions');

    const objectUrls = [];
    let loading = false;

    function text(id, value) {
        document.getElementById(id).textContent =
            value == null || value === '' ? 'Not available' : String(value);
    }

    function clearImages() {
        images.replaceChildren();
        for (const url of objectUrls) URL.revokeObjectURL(url);
        objectUrls.length = 0;
    }

    async function loadImage(kind, title) {
        const section = document.createElement('section');
        const heading = document.createElement('h3');
        const status = document.createElement('p');

        heading.textContent = title;
        status.textContent = 'Loading image…';
        section.append(heading, status);
        images.appendChild(section);

        try {
            const token = sessionStorage.getItem('vetdental_staff_token');
            if (!token) throw new Error('Please log in again.');

            const response = await fetch(
                `/veterinarians/me/appointments/${appointmentId}` +
                `/ai-assessment/media/${kind}`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    cache: 'no-store'
                }
            );

            if (!response.ok) {
                throw new Error(
                    response.status === 404
                        ? 'Image unavailable or access is no longer permitted.'
                        : 'Could not load image.'
                );
            }

            const blob = await response.blob();
            if (!blob.type.startsWith('image/')) {
                throw new Error('Invalid image response.');
            }

            const url = URL.createObjectURL(blob);
            objectUrls.push(url);

            const image = document.createElement('img');
            image.src = url;
            image.alt = title;
            image.style.width = '100%';
            image.style.maxHeight = '650px';
            image.style.objectFit = 'contain';
            image.style.borderRadius = '12px';

            image.addEventListener('error', () => {
                status.textContent = 'The image could not be displayed.';
            });

            status.textContent = '';
            section.appendChild(image);
        } catch (error) {
            status.textContent = error.message;
        }
    }

    async function load() {
        if (loading) return;

        if (!/^[1-9]\d*$/.test(rawId || '') ||
            !Number.isSafeInteger(appointmentId) ||
            appointmentId > 2147483647) {
            message.textContent = 'Invalid appointment reference.';
            return;
        }

        loading = true;
        retry.hidden = true;
        resultPanel.hidden = true;
        message.textContent = 'Loading the linked assessment…';
        predictions.replaceChildren();
        clearImages();

        try {
            const record = await vetRequest(
                `/veterinarians/me/appointments/${appointmentId}/ai-assessment`
            );

            if (record.appointment_id !== appointmentId ||
                !record.result ||
                typeof record.result !== 'object') {
                throw new Error('Invalid assessment response.');
            }

            const result = record.result;
            const decision = result.decision || {};
            const severity = result.severity || {};

            text('scan-pet', `${record.pet_name} · ${record.species}`);
            text(
                'scan-reference',
                `Appointment #${appointmentId} · Assessment #${record.analysis_id}`
            );
            text('scan-decision', `Screening outcome: ${decision.status || 'Unavailable'}`);
            text('scan-reason', decision.reason);
            text('scan-severity', `Experimental severity reference: ${severity.label || 'Unavailable'}`);
            text('scan-severity-reason', severity.reason);

            for (const prediction of result.predictions || []) {
                const assessed =
                    prediction.assessed !== false &&
                    prediction.supported !== false &&
                    typeof prediction.positive === 'boolean';

                const score = prediction.confidence;
                const validScore =
                    Number.isFinite(score) && score >= 0 && score <= 1;

                const values = [
                    prediction.condition || 'Not recorded',
                    assessed
                        ? (prediction.positive
                            ? 'Above model threshold'
                            : 'Below model threshold')
                        : 'Not assessed',
                    assessed && validScore
                        ? `${(score * 100).toFixed(1)}%`
                        : 'Not available'
                ];

                const row = document.createElement('tr');
                for (const value of values) {
                    const cell = document.createElement('td');
                    cell.textContent = value;
                    row.appendChild(cell);
                }
                predictions.appendChild(row);
            }

            resultPanel.hidden = false;
            message.textContent = '';

            await Promise.all([
                loadImage('original', 'Submitted photo'),
                loadImage('summary', 'Combined AI visualization')
            ]);
        } catch (error) {
            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            loading = false;
        }
    }

    retry.addEventListener('click', load);
    window.addEventListener('pagehide', clearImages);

    vetReady.then(profile => {
        if (profile) load();
    });
})();