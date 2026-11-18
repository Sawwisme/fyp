(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const dialog = $('ar-dialog');
    const size = 20;
    let ready = false, page = 0, listVersion = 0, detailVersion = 0;
    let selected = null, saving = false, uncertain = false;
    let photoController = null, photoUrl = null;
    const labels = {
        none: 'No concern identified from this image', mild: 'Mild', moderate: 'Moderate', severe: 'Severe',
        unable_to_assess: 'Unable to assess from this image', routine_booking: 'Routine appointment',
        prompt_clinic_assessment: 'Prompt clinic assessment', home_care: 'Home-care guidance'
    };
    function node(tag, text, cls) {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        if (cls) element.className = cls;
        return element;
    }
    function date(value) {
        if (!value) return 'Not recorded';
        return new Date(value).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur', dateStyle: 'medium', timeStyle: 'short' });
    }
    function updateForm() {
        const disabled = saving || uncertain || !selected || selected.status !== 'pending';
        for (const element of $('ar-form').elements) element.disabled = disabled;
        $('ar-close').disabled = saving;
        $('ar-reload').disabled = saving;
        $('ar-save').textContent = saving ? 'Saving review…' : 'Save review & notify owner';
    }
    function releasePhoto() {
        if (photoController) photoController.abort();
        photoController = null;
        if (photoUrl) URL.revokeObjectURL(photoUrl);
        photoUrl = null;
        $('ar-image').removeAttribute('src');
        $('ar-image').hidden = true;
        $('ar-open-image').disabled = true;
    }
    async function load(target = 0) {
        if (!ready) return;
        const version = ++listVersion;
        $('ar-rows').replaceChildren();
        $('ar-message').textContent = 'Loading shared assessments…';
        $('ar-previous').disabled = $('ar-next').disabled = true;
        try {
            const query = new URLSearchParams({ offset: String(target * size), limit: String(size + 1) });
            if ($('ar-status').value) query.set('status', $('ar-status').value);
            const items = await vetRequest(`/ai-assessment-reviews?${query}`);
            if (version !== listVersion) return;
            if (!Array.isArray(items)) throw new Error('Invalid assessment list response.');
            page = target;
            for (const item of items.slice(0, size)) {
                const row = node('tr');
                const patient = node('td');
                patient.append(node('strong', item.pet_name), node('div', item.species, 'muted'));
                const status = node('td');
                status.appendChild(node('span', item.status === 'pending' ? 'Awaiting review' : 'Reviewed', `ar-status ${item.status === 'pending' ? 'pending' : 'reviewed'}`));
                const action = node('td');
                const button = node('button', item.status === 'pending' ? 'Review assessment' : 'View review', 'secondary compact-button');
                button.type = 'button'; button.addEventListener('click', () => openReview(item.review_id));
                action.appendChild(button);
                row.append(patient, node('td', item.owner_name), node('td', date(item.requested_at)), status, action);
                $('ar-rows').appendChild(row);
            }
            $('ar-message').textContent = items.length ? 'Only assessments shared with your clinic are shown.' : 'No shared assessments match this status.';
            $('ar-page').textContent = `Page ${page + 1}`;
            $('ar-previous').disabled = page === 0;
            $('ar-next').disabled = items.length <= size;
        } catch (error) {
            if (version === listVersion) $('ar-message').textContent = error.message;
        }
    }
    async function showPhoto(kind) {
        releasePhoto();
        if (!selected || !dialog.open) return;
        const id = selected.review_id;
        const controller = new AbortController(); photoController = controller;
        const timeout = setTimeout(() => controller.abort(), 20000);
        $('ar-image-message').textContent = 'Loading image…';
        document.querySelectorAll('[data-ar-kind]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.arKind === kind)));
        try {
            const token = sessionStorage.getItem(vetTokenKey);
            if (!token) { vetLogout(); return; }
            const response = await fetch(`/ai-assessment-reviews/${id}/media/${kind}`, {
                headers: { Authorization: `Bearer ${token}` }, credentials: 'omit', cache: 'no-store', signal: controller.signal
            });
            if (response.status === 401) { vetLogout(); return; }
            if (!response.ok) throw new Error('Image unavailable. Try another image or reload the review.');
            if (!response.headers.get('content-type')?.startsWith('image/')) throw new Error('Invalid image response.');
            const blob = await response.blob();
            if (photoController !== controller || !dialog.open || selected?.review_id !== id) return;
            photoUrl = URL.createObjectURL(blob);
            $('ar-image').src = photoUrl;
            $('ar-image').alt = `${kind} image for ${selected.pet_name}`;
            $('ar-image').hidden = false;
            $('ar-open-image').disabled = false;
            $('ar-image-message').textContent = '';
        } catch (error) {
            if (photoController === controller && dialog.open) $('ar-image-message').textContent = error.name === 'AbortError' ? 'Image request timed out. Select the image again to retry.' : error.message;
        } finally { clearTimeout(timeout); }
    }
    function renderDetail(record) {
        $('ar-patient').textContent = `${record.pet_name} · Owner: ${record.owner_name}`;
        const severity = record.ai_severity;
        $('ar-ai-severity').textContent = severity?.label ? `AI reference severity: ${severity.label}` : 'AI reference severity not recorded';
        $('ar-ai-reason').textContent = severity?.reason || '';
        $('ar-owner-message').textContent = record.owner_message || 'No message provided.';
        $('ar-predictions').replaceChildren();
        for (const prediction of record.predictions || []) {
            const assessed =
                prediction.supported !== false &&
                prediction.assessed !== false &&
                typeof prediction.positive === 'boolean';

            let text;

            if (!assessed) {
                text = `${prediction.condition}: Not assessed for this species`;
            } else {
                const score = prediction.confidence;
                const scoreText = Number.isFinite(score)
                    ? `${(score * 100).toFixed(1)}%`
                    : 'Not recorded';

                const state = prediction.positive
                    ? 'Above model threshold'
                    : 'Below model threshold';

                text = `${prediction.condition}: ${scoreText} · ${state}`;
            }

            $('ar-predictions').appendChild(
                node('div', text, 'ar-prediction')
            );
        }
        $('ar-form').reset();
        $('ar-form').hidden = record.status !== 'pending';
        $('ar-saved').replaceChildren();
        $('ar-saved').hidden = record.status !== 'reviewed';
        if (record.status === 'reviewed') {
            $('ar-saved').append(
                node('strong', 'Reviewed by veterinarian'),
                node('p', `${record.reviewed_by_name || 'Veterinarian'} · ${date(record.reviewed_at)}`),
                node('p', `Interpretation: ${labels[record.reviewed_severity] || record.reviewed_severity}`),
                node('p', `Next action: ${labels[record.recommended_action] || record.recommended_action}`),
                node('p', record.feedback, 'ar-preserve')
            );
        }
        $('ar-detail').hidden = false;
        updateForm(); showPhoto('original');
    }
    async function openReview(id) {
        if (saving) return;
        const version = ++detailVersion;
        releasePhoto(); selected = null; uncertain = false;
        $('ar-detail').hidden = true;
        $('ar-patient').textContent = '';
        $('ar-detail-message').textContent = 'Loading assessment…';
        $('ar-reload').dataset.id = String(id);
        if (!dialog.open) dialog.showModal();
        updateForm();
        try {
            const record = await vetRequest(`/ai-assessment-reviews/${id}`);
            if (version !== detailVersion || !dialog.open) return;
            selected = record;
            renderDetail(record);
            $('ar-detail-message').textContent = '';
        } catch (error) {
            if (version === detailVersion && dialog.open) $('ar-detail-message').textContent = error.message;
        }
    }
    $('ar-form').addEventListener('submit', async event => {
        event.preventDefault();
        if (saving || uncertain || selected?.status !== 'pending') return;
        const feedback = $('ar-feedback').value.trim();
        if (!feedback) { $('ar-feedback').focus(); return; }
        const id = selected.review_id;
        const body = { reviewed_severity: $('ar-severity').value, recommended_action: $('ar-action').value, feedback };
        saving = true; updateForm();
        $('ar-detail-message').textContent = 'Saving review…';
        let success = false;
        try {
            const record = await vetRequest(`/ai-assessment-reviews/${id}/decision`, { method: 'POST', body });
            selected = record; success = true;
        } catch (error) {
            uncertain = true;
            $('ar-detail-message').textContent = `${error.message} Reload this review to check whether it was saved before trying again.`;
        } finally { saving = false; updateForm(); }
        if (success) {
            dialog.close();
            await load(0);
            $('ar-message').textContent = 'Review saved. The owner has been notified.';
        }
    });
    $('ar-status').addEventListener('change', () => load(0));
    $('ar-refresh').addEventListener('click', () => load(page));
    $('ar-previous').addEventListener('click', () => load(page - 1));
    $('ar-next').addEventListener('click', () => load(page + 1));
    $('ar-close').addEventListener('click', () => { if (!saving) dialog.close(); });
    $('ar-reload').addEventListener('click', () => openReview(Number($('ar-reload').dataset.id)));
    dialog.addEventListener('cancel', event => { if (saving) event.preventDefault(); });
    dialog.addEventListener('close', () => { detailVersion++; releasePhoto(); selected = null; });
    $('ar-open-image').addEventListener('click', () => { if (photoUrl) window.open(photoUrl, '_blank', 'noopener,noreferrer'); });
    document.querySelectorAll('[data-ar-kind]').forEach(button => button.addEventListener('click', () => showPhoto(button.dataset.arKind)));
    window.addEventListener('pagehide', releasePhoto);
    vetReady.then(profile => {
        if (!profile) return;
        ready = true; load(0);
        const id = Number(new URLSearchParams(location.search).get('review'));
        if (Number.isInteger(id) && id >= 1 && id <= 2147483647) openReview(id);
    });
})();
