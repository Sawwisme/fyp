(() => {
    const get = id => document.getElementById(id);
    const search = get('consult-search');
    const status = get('consult-status');
    const rows = get('consult-list-rows');
    const message = get('consult-list-message');
    const previous = get('consult-previous');
    const next = get('consult-next');
    const retry = get('consult-list-retry');

    const pageSize = 20;

    let page = 0;
    let version = 0;
    let loading = false;
    let ready = false;
    let timer;

    function renderCounts(counts = null) {
        for (const name of ['total', 'draft', 'completed']) {
            get(`consult-count-${name}`).textContent =
                counts ? counts[name] : '—';
        }
    }

    function formatDate(value) {
        const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
            ? value
            : `${value}Z`;

        return new Date(timestamp).toLocaleString('en-MY', {
            timeZone: 'Asia/Kuala_Lumpur',
            dateStyle: 'medium',
            timeStyle: 'short'
        });
    }

    async function load(targetPage = 0) {
        if (!ready) return;

        const currentVersion = ++version;
        loading = true;
        renderCounts();

        previous.disabled = true;
        next.disabled = true;
        retry.hidden = true;
        rows.replaceChildren();
        message.textContent = 'Loading consultations…';

        const query = new URLSearchParams({
            offset: String(targetPage * pageSize),
            limit: String(pageSize + 1)
        });

        if (search.value.trim()) {
            query.set('search', search.value.trim());
        }

        if (status.value) {
            query.set('consultation_status', status.value);
        }

        try {
            const countsQuery = new URLSearchParams(query);
            countsQuery.delete('offset');
            countsQuery.delete('limit');

            const [data, counts] = await Promise.all([
                vetRequest(`/consultations?${query}`),
                vetRequest(`/consultations/summary/counts?${countsQuery}`)
            ]);

            if (currentVersion !== version) return;

            page = targetPage;

            renderCounts(counts);

            const visible = data.slice(0, pageSize);

            for (const item of visible) {
                const row = document.createElement('tr');

                for (const value of [
                    formatDate(item.consultation_date),
                    item.pet_name,
                    item.owner_name,
                    item.diagnosis
                        ? item.diagnosis.slice(0, 120)
                        : '—',
                    item.status
                ]) {
                    const cell = document.createElement('td');
                    cell.textContent = value;
                    row.appendChild(cell);
                }

                const action = document.createElement('td');
                const link = document.createElement('a');

                link.href =
                    `/web/vet/consultation.html?id=${item.consultation_id}`;
                link.textContent =
                    item.status === 'draft' ? 'Continue' : 'View';

                action.appendChild(link);
                row.appendChild(action);
                rows.appendChild(row);
            }

            message.textContent = visible.length
                ? `Page ${page + 1} · ${visible.length} record(s). ` +
                'Times use Malaysia time.'
                : 'No matching consultations.';

            previous.disabled = page === 0;
            next.disabled = data.length <= pageSize;
        } catch (error) {
            if (currentVersion !== version) return;

            message.textContent = error.message;
            retry.hidden = false;
        } finally {
            if (currentVersion === version) loading = false;
        }
    }

    search.addEventListener('input', () => {
        clearTimeout(timer);
        version += 1;
        previous.disabled = true;
        next.disabled = true;
        timer = setTimeout(() => load(0), 300);
    });

    status.addEventListener('change', () => {
        clearTimeout(timer);
        load(0);
    });

    previous.addEventListener('click', () => {
        if (!loading && page > 0) load(page - 1);
    });

    next.addEventListener('click', () => {
        if (!loading) load(page + 1);
    });

    retry.addEventListener('click', () => load(0));

    vetReady.then(profile => {
        if (!profile) return;
        ready = true;
        load(0);
    });
})();