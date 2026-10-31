(() => {
    const get = id => document.getElementById(id);
    const dialog = get('absence-dialog');
    const form = get('absence-form');
    const fields = get('absence-fields');
    const history = get('absence-history');
    const list = get('absence-list');
    const listMessage = get('absence-list-message');
    const formMessage = get('absence-form-message');

    let ready = false;
    let saving = false;
    let loading = false;
    let uncertain = false;
    let page = 0;
    let hasMore = false;
    const pageSize = 10;

    function today() {
        const parts = new Intl.DateTimeFormat('en-US', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        }).formatToParts(new Date());

        const value = type =>
            parts.find(part => part.type === type).value;

        return `${value('year')}-${value('month')}-${value('day')}`;
    }

    function controls() {
        get('absence-open').disabled = !ready || saving;
        get('absence-close').disabled = saving;
        get('absence-cancel').disabled = saving;
        get('absence-submit').disabled = saving || uncertain;
        fields.disabled = saving || uncertain;
        get('absence-previous').disabled = loading || saving || page === 0;
        get('absence-next').disabled = loading || saving || !hasMore;
    }

    async function loadReports(targetPage = 0) {
        if (!ready || loading) return;

        loading = true;
        list.replaceChildren();
        listMessage.textContent = 'Loading reports…';
        get('absence-list-retry').hidden = true;
        controls();

        try {
            const query = new URLSearchParams({
                offset: String(targetPage * pageSize),
                limit: String(pageSize + 1),
            });

            const data = await vetRequest(
                `/veterinarians/me/absences?${query}`
            );

            if (!Array.isArray(data)) {
                throw new Error('Invalid absence report response.');
            }

            page = targetPage;
            hasMore = data.length > pageSize;

            for (const item of data.slice(0, pageSize)) {
                const card = document.createElement('article');
                card.className = 'absence-report';

                const heading = document.createElement('strong');
                heading.textContent =
                    `${item.absence_date.split('-').reverse().join('/')} · ` +
                    `${item.start_time.slice(0, 5)}–${item.end_time.slice(0, 5)}`;

                const reason = document.createElement('p');
                reason.textContent = item.reason;

                const status = document.createElement('small');
                status.textContent = `Report status: ${item.status}`;

                card.append(heading, reason, status);
                list.appendChild(card);
            }

            listMessage.textContent = data.length
                ? `Page ${page + 1}`
                : 'No absence reports.';

            const showPages = page > 0 || hasMore;
            get('absence-previous').hidden = !showPages;
            get('absence-next').hidden = !showPages;
        } catch (error) {
            hasMore = false;
            listMessage.textContent = error.message;
            get('absence-list-retry').hidden = false;
        } finally {
            loading = false;
            controls();
        }
    }

    get('absence-open').addEventListener('click', () => {
        if (!ready || saving) return;

        form.reset();
        get('absence-date').value = today();
        get('absence-date').min = today();
        formMessage.textContent = uncertain
            ? 'A previous save could not be confirmed. Check My absence ' +
            'reports before refreshing this page and reporting again.'
            : '';

        controls();
        dialog.showModal();
    });

    function closeForm() {
        if (!saving) dialog.close();
    }

    get('absence-close').addEventListener('click', closeForm);
    get('absence-cancel').addEventListener('click', closeForm);

    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (saving || uncertain) return;

        const start = get('absence-start').value;
        const end = get('absence-end').value;
        const reason = get('absence-reason').value.trim();

        if (end <= start || reason.length < 5) {
            formMessage.textContent =
                'End time must be after start time. Enter a reason ' +
                'of at least five characters.';
            return;
        }

        saving = true;
        controls();
        formMessage.textContent = 'Reporting absence…';

        let result = null;

        try {
            result = await vetRequest('/veterinarians/me/absences', {
                method: 'POST',
                body: {
                    absence_date: get('absence-date').value,
                    start_time: start,
                    end_time: end,
                    reason,
                },
            });

            if (!Number.isInteger(result.absence_id)) {
                throw new Error('Could not confirm the saved report.');
            }
        } catch (error) {
            uncertain = true;
            formMessage.textContent =
                `${error.message} Close this form and check My absence ` +
                'reports before trying again.';
        } finally {
            saving = false;
            controls();
        }

        if (result && Number.isInteger(result.absence_id)) {
            dialog.close();
            history.open = true;
            await loadReports(0);
            listMessage.textContent =
                `Absence reported. ${result.affected_appointments} ` +
                'appointment(s) need rearrangement.';
            window.dispatchEvent(new Event('vet-absence-reported'));
        }
    });

    history.addEventListener('toggle', () => {
        if (history.open) void loadReports(0);
    });

    get('absence-list-retry').addEventListener(
        'click', () => loadReports(page)
    );
    get('absence-previous').addEventListener('click', () => {
        if (!loading && page > 0) void loadReports(page - 1);
    });
    get('absence-next').addEventListener('click', () => {
        if (!loading && hasMore) void loadReports(page + 1);
    });

    vetReady.then(profile => {
        ready = Boolean(profile);
        controls();
    });
})();