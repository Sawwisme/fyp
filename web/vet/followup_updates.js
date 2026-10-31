(() => {
    const get = id => document.getElementById(id);
    const dialog = get('followup-updates-dialog');
    const list = get('followup-updates-list');
    const message = get('followup-updates-message');
    const retry = get('followup-updates-retry');
    const previous = get('followup-updates-previous');
    const next = get('followup-updates-next');
    const close = get('followup-updates-close');
    const photoDialog = get('followup-photo-dialog');
    const largePhoto = get('followup-photo-large');

    get('followup-photo-close').addEventListener('click', () => {
        photoDialog.close();
    });

    largePhoto.addEventListener('click', () => {
        largePhoto.classList.toggle('full-size');
    });

    photoDialog.addEventListener('close', () => {
        largePhoto.removeAttribute('src');
        largePhoto.classList.remove('full-size');
    });


    const pageSize = 10;
    let selected = null;
    let onSaved = null;
    let page = 0;
    let hasMore = false;
    let loading = false;
    let saving = false;
    let version = 0;
    let photoController = new AbortController();
    const photoUrls = new Set();

    function clearPhotos() {
        if (photoDialog.open) photoDialog.close();
        photoController.abort();
        photoController = new AbortController();

        for (const url of photoUrls) URL.revokeObjectURL(url);
        photoUrls.clear();
    }

    function timestamp(value) {
        if (!value) return 'Not recorded';

        const text = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
            ? value
            : `${value}Z`;

        const date = new Date(text);
        if (Number.isNaN(date.getTime())) return 'Not recorded';

        return new Intl.DateTimeFormat('en-MY', {
            timeZone: 'Asia/Kuala_Lumpur',
            dateStyle: 'medium',
            timeStyle: 'short',
        }).format(date);
    }

    function paragraph(parent, label, value) {
        const element = document.createElement('p');
        const strong = document.createElement('strong');

        strong.textContent = `${label}: `;
        element.append(
            strong,
            document.createTextNode(value || 'Not recorded')
        );
        parent.appendChild(element);
    }

    function updateControls() {
        close.disabled = saving;
        previous.disabled = loading || saving || page === 0;
        next.disabled = loading || saving || !hasMore;
        retry.disabled = loading || saving;
    }

    async function showPhoto(photo, parent, request) {
        const container = document.createElement('div');
        const status = document.createElement('p');
        status.textContent = 'Loading photo…';
        container.appendChild(status);
        parent.appendChild(container);

        const signal = photoController.signal;
        const timeout = setTimeout(
            () => controller.abort(),
            20000
        );
        const controller = new AbortController();
        const abort = () => controller.abort();
        signal.addEventListener('abort', abort, { once: true });

        try {
            const token = sessionStorage.getItem(vetTokenKey);

            if (!token) {
                vetLogout();
                return;
            }

            const response = await fetch(
                `/followup-media/${photo.followup_care_image_id}`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    credentials: 'omit',
                    cache: 'no-store',
                    signal: controller.signal,
                }
            );

            if (response.status === 401) {
                vetLogout();
                return;
            }

            if (!response.ok) {
                throw new Error('Photo unavailable.');
            }

            const blob = await response.blob();

            if (request !== version || !dialog.open) return;

            const url = URL.createObjectURL(blob);
            photoUrls.add(url);

            const image = document.createElement('img');
            image.src = url;
            image.alt = 'Owner-submitted follow-up photo';

            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'followup-photo-thumbnail';
            button.setAttribute('aria-label', 'Enlarge follow-up photo');

            const caption = document.createElement('span');
            caption.textContent = 'View photo ↗';

            button.append(image, caption);

            button.addEventListener('click', () => {
                largePhoto.src = url;
                largePhoto.classList.remove('full-size');
                photoDialog.showModal();
            });

            container.replaceChildren(button);
        } catch (_) {
            if (request === version && dialog.open) {
                status.textContent =
                    'Could not load photo. Use Try again to reload.';
                retry.hidden = false;
            }
        } finally {
            clearTimeout(timeout);
            signal.removeEventListener('abort', abort);
        }
    }

    function renderSubmission(
        item,
        request,
        isLatest,
        correctionMode = false
    ) {
        const card = document.createElement('article');
        card.className = 'followup-update-card';

        const linkedVisit = selected.linked_visit;

        const hasActiveVisit = Boolean(
            linkedVisit &&
            !['cancelled', 'rejected'].includes(linkedVisit.status)
        );

        paragraph(card, 'Submitted', timestamp(item.submitted_at));
        paragraph(
            card,
            'Status',
            {
                submitted: 'Awaiting review',
                reviewed: 'Reviewed',
                more_requested: 'More photos or information requested',
            }[item.review_status] || item.review_status
        );
        paragraph(card, 'Owner comment', item.owner_comment);

        const photos = document.createElement('div');
        photos.className = 'followup-update-photos';
        card.appendChild(photos);

        for (const photo of item.images) {
            void showPhoto(photo, photos, request);
        }

        if (item.veterinarian_comment) {
            paragraph(card, 'Vet feedback', item.veterinarian_comment);
            paragraph(card, 'Reviewed', timestamp(item.reviewed_at));
        }

        if (item.decision_outcome) {
            paragraph(
                card,
                'Saved outcome',
                {
                    complete: 'No further follow-up needed — completed',
                    request_update: 'Another owner update requested',
                    in_clinic: 'In-clinic review required',
                }[item.decision_outcome] || item.decision_outcome
            );
        }

        if (
            selected.status === 'pending' &&
            item.decision_outcome &&
            isLatest &&
            !correctionMode
        ) {
            const correct = document.createElement('button');
            correct.type = 'button';
            correct.className = 'secondary compact-button';
            correct.textContent = hasActiveVisit
                ? 'Update feedback'
                : 'Correct decision';

            correct.addEventListener('click', () => {
                if (saving || loading) return;

                card.replaceWith(
                    renderSubmission(item, request, isLatest, true)
                );
            });

            card.appendChild(correct);
        }

        if (
            selected.status === 'pending' &&
            (
                (!item.decision_outcome &&
                    (item.review_status === 'submitted' || isLatest)) ||
                (correctionMode && isLatest && item.decision_outcome)
            )
        ) {
            const form = document.createElement('form');
            const fields = document.createElement('fieldset');
            fields.style.border = '0';
            fields.style.padding = '0';
            fields.style.margin = '0';

            const commentId = `submission-comment-${item.submission_id}`;
            const statusId = `submission-status-${item.submission_id}`;

            const commentLabel = document.createElement('label');
            commentLabel.htmlFor = commentId;
            commentLabel.textContent = 'Feedback for owner';

            const comment = document.createElement('textarea');
            comment.id = commentId;
            comment.rows = 4;
            comment.required = true;
            comment.maxLength = 5000;
            comment.value = item.veterinarian_comment || '';

            const statusLabel = document.createElement('label');
            statusLabel.htmlFor = statusId;
            statusLabel.textContent = 'Review outcome';

            const outcome = document.createElement('select');
            outcome.id = statusId;
            outcome.required = true;
            outcome.add(new Option('Select an outcome', ''));

            const completeOption = new Option(
                hasActiveVisit
                    ? 'Complete follow-up — resolve booked appointment first'
                    : selected.visit_required
                        ? 'Clinic visit no longer needed — complete follow-up'
                        : 'No further follow-up needed — complete',
                'complete'
            );

            completeOption.disabled = hasActiveVisit;
            outcome.add(completeOption);

            if (hasActiveVisit) {
                const explanation = document.createElement('p');
                explanation.className = 'muted';
                explanation.textContent =
                    `Review appointment #${linkedVisit.appointment_id} is linked. ` +
                    'Complete its consultation, or cancel the booking through ' +
                    'appointment management before withdrawing the visit requirement.';

                fields.appendChild(explanation);
            }

            outcome.add(
                new Option(
                    'Request another photo / progress update',
                    'request_update'
                )
            );

            outcome.add(
                new Option(
                    'In-clinic review required',
                    'in_clinic'
                )
            );

            if (hasActiveVisit) {
                outcome.value = item.decision_outcome || 'in_clinic';
                outcome.disabled = true;
                statusLabel.textContent = 'Saved outcome — locked';

                paragraph(
                    fields,
                    'Appointment booked',
                    'You may update feedback only. Manage the booked ' +
                    'appointment through the appointment workflow.'
                );
            }

            const waiverFields = document.createElement('div');
            waiverFields.hidden = true;

            const waiverId = `visit-waiver-${item.submission_id}`;

            const waiverLabel = document.createElement('label');
            waiverLabel.htmlFor = waiverId;
            waiverLabel.textContent =
                'Why is the in-clinic review no longer needed?';

            const waiverReason = document.createElement('textarea');
            waiverReason.id = waiverId;
            waiverReason.rows = 3;
            waiverReason.minLength = 10;
            waiverReason.maxLength = 1000;
            waiverReason.disabled = true;

            waiverFields.append(waiverLabel, waiverReason);
            fields.appendChild(waiverFields);

            function updateWaiverFields() {
                const withdrawingVisit =
                    outcome.value === 'complete' &&
                    selected.visit_required &&
                    !hasActiveVisit;

                waiverFields.hidden = !withdrawingVisit;
                waiverReason.disabled = !withdrawingVisit;
                waiverReason.required = Boolean(withdrawingVisit);
            }

            outcome.addEventListener('change', updateWaiverFields);
            updateWaiverFields();

            let correctionReason = null;

            if (correctionMode) {
                const reasonId = `correction-reason-${item.submission_id}`;

                const reasonLabel = document.createElement('label');
                reasonLabel.htmlFor = reasonId;
                reasonLabel.textContent = hasActiveVisit
                    ? 'Reason for updating feedback'
                    : 'Reason for correcting the decision';

                correctionReason = document.createElement('textarea');
                correctionReason.id = reasonId;
                correctionReason.rows = 2;
                correctionReason.required = true;
                correctionReason.minLength = 5;
                correctionReason.maxLength = 1000;

                fields.append(reasonLabel, correctionReason);
            }

            const submit = document.createElement('button');
            submit.type = 'submit';
            submit.textContent = hasActiveVisit
                ? 'Save feedback'
                : correctionMode
                    ? 'Save corrected decision'
                    : 'Send feedback';

            fields.append(
                commentLabel, comment,
                statusLabel, outcome
            );

            const actions = document.createElement('div');
            actions.className = 'followup-feedback-actions';
            actions.appendChild(submit);

            fields.appendChild(actions);
            form.appendChild(fields);

            if (correctionMode) {
                const cancelCorrection = document.createElement('button');
                cancelCorrection.type = 'button';
                cancelCorrection.className = 'secondary compact-button';
                cancelCorrection.textContent = hasActiveVisit
                    ? 'Cancel editing'
                    : 'Cancel correction';

                cancelCorrection.addEventListener('click', () => {
                    if (saving || loading) return;

                    card.replaceWith(
                        renderSubmission(item, request, isLatest)
                    );
                });

                actions.appendChild(cancelCorrection);
            }

            form.addEventListener('submit', async event => {
                event.preventDefault();

                if (saving || loading || !comment.value.trim()) return;

                const correctionText = correctionReason?.value.trim() || null;

                if (correctionMode && (!correctionText || correctionText.length < 5)) {
                    message.textContent =
                        'Enter a correction reason of at least 5 characters.';
                    correctionReason.focus();
                    return;
                }

                const withdrawingVisit =
                    outcome.value === 'complete' &&
                    selected.visit_required &&
                    !hasActiveVisit;

                const waiverText = withdrawingVisit
                    ? waiverReason.value.trim()
                    : null;

                if (withdrawingVisit && (!waiverText || waiverText.length < 10)) {
                    message.textContent =
                        'Explain why the clinic review is no longer needed ' +
                        '(at least 10 characters).';
                    waiverReason.focus();
                    return;
                }

                saving = true;
                list.querySelectorAll('fieldset').forEach(element => {
                    element.disabled = true;
                });
                updateControls();
                message.textContent = 'Saving feedback…';

                let succeeded = false;

                try {
                    await vetRequest(
                        `/followups/${selected.followup_care_id}` +
                        `/submissions/${item.submission_id}/review`,
                        {
                            method: 'POST',
                            body: {
                                outcome: outcome.value,
                                veterinarian_comment: comment.value.trim(),
                                expected_reviewed_at: item.reviewed_at ?? null,
                                correction_reason: correctionText,
                                visit_waiver_reason: waiverText,
                            },
                        }
                    );

                    succeeded = true;
                } catch (error) {
                    message.textContent =
                        `${error.message} Use Try again to reload ` +
                        'the saved status before submitting again.';
                    retry.hidden = false;
                } finally {
                    saving = false;
                    updateControls();
                }

                if (succeeded) {
                    const refreshList = onSaved;
                    dialog.close();

                    if (refreshList) await refreshList();
                }
            });

            card.appendChild(form);
        }

        return card;
    }

    async function load(targetPage = 0) {
        if (!selected || saving) return;

        const request = ++version;
        clearPhotos();
        loading = true;
        retry.hidden = true;
        list.replaceChildren();
        message.textContent = 'Loading owner updates…';
        updateControls();

        try {
            const query = new URLSearchParams({
                offset: String(targetPage * pageSize),
                limit: String(pageSize + 1),
            });

            const data = await vetRequest(
                `/followups/${selected.followup_care_id}` +
                `/submissions?${query}`
            );

            if (request !== version || !dialog.open) return;
            if (!Array.isArray(data)) {
                throw new Error('Invalid submission list response.');
            }

            page = targetPage;
            hasMore = data.length > pageSize;

            data.slice(0, pageSize).forEach((item, index) => {
                list.appendChild(
                    renderSubmission(
                        item,
                        request,
                        targetPage === 0 && index === 0
                    )
                );
            });

            message.textContent = data.length
                ? 'Feedback is visible to the owner after refreshing.'
                : 'No owner updates submitted yet.';

            get('followup-updates-page').textContent = `Page ${page + 1}`;
        } catch (error) {
            if (request !== version) return;

            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (request === version) {
                loading = false;
                updateControls();
            }
        }
    }

    window.openFollowupUpdates = (item, afterSave = null) => {
        if (dialog.open || saving) return;

        selected = item;
        onSaved = afterSave;
        page = 0;
        hasMore = false;
        get('followup-updates-patient').textContent =
            `${item.pet_name} · Owner: ${item.owner_name}`;
        get('followup-updates-page').textContent = '';
        dialog.showModal();
        void load(0);
    };

    close.addEventListener('click', () => {
        if (!saving) dialog.close();
    });

    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    dialog.addEventListener('close', () => {
        version += 1;
        clearPhotos();
        selected = null;
        list.replaceChildren();
    });

    retry.addEventListener('click', () => load(page));
    previous.addEventListener('click', () => {
        if (!loading && !saving && page > 0) load(page - 1);
    });
    next.addEventListener('click', () => {
        if (!loading && !saving && hasMore) load(page + 1);
    });
})();