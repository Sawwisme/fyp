(() => {
    'use strict';

    const root = document.querySelector('[data-dashboard-role]');
    if (!root) return;

    const admin = root.dataset.dashboardRole === 'admin';
    const refresh = root.querySelector('[data-dash-refresh]');
    const message = root.querySelector('[data-dash-error]');
    const statusContainer = root.querySelector('[data-dash-statuses]');

    let loading = false;

    function malaysiaDate() {
        const parts = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(new Date());

        const value = type =>
            parts.find(part => part.type === type).value;

        return `${value('year')}-${value('month')}-${value('day')}`;
    }

    function request(path) {
        return admin
            ? apiRequest(path)
            : vetRequest(path);
    }

    function report(start, end, extra = {}) {
        const query = new URLSearchParams({
            date_from: start,
            date_to: end,
            ...extra
        });

        return request(`/reports?${query}`);
    }

    function setValue(name, value) {
        const element = root.querySelector(
            `[data-dash-value="${name}"]`
        );

        if (element) element.textContent = String(value);
    }

    function count(value) {
        return Number.isInteger(value) && value >= 0
            ? value
            : '—';
    }

    function renderStatuses(items) {
        statusContainer.replaceChildren();

        if (!Array.isArray(items)) {
            statusContainer.textContent =
                'Appointment status data is unavailable.';
            return;
        }

        const total = items.reduce(
            (sum, item) => sum + Number(item.count || 0),
            0
        );

        if (!total) {
            const empty = document.createElement('p');
            empty.className = 'dash-note';
            empty.textContent = 'No appointments scheduled for today.';
            statusContainer.appendChild(empty);
            return;
        }

        const labels = {
            pending: 'Pending',
            pending_payment: 'Awaiting payment',
            confirmed: 'Confirmed',
            in_progress: 'In progress',
            completed: 'Completed',
            cancelled: 'Cancelled',
            rejected: 'Rejected',
            no_show: 'No show'
        };

        for (const item of items) {
            const row = document.createElement('div');
            row.className = 'dash-status-row';

            const label = document.createElement('span');
            label.textContent =
                labels[item.status] || item.status;

            const track = document.createElement('div');
            track.className = 'dash-track';
            track.setAttribute('aria-hidden', 'true');

            const bar = document.createElement('div');
            bar.className = 'dash-bar';
            bar.style.width =
                `${Math.max(0, Math.min(100, item.count / total * 100))}%`;

            track.appendChild(bar);

            const value = document.createElement('strong');
            value.textContent = String(item.count);

            row.append(label, track, value);
            statusContainer.appendChild(row);
        }
    }

    async function load() {
        if (loading) return;

        loading = true;
        refresh.disabled = true;
        message.textContent = '';

        root.querySelectorAll('[data-dash-value]').forEach(element => {
            element.textContent = '—';
        });

        statusContainer.textContent = 'Loading appointment status…';

        const today = malaysiaDate();
        const monthStart = `${today.slice(0, 7)}-01`;

        root.querySelector('[data-dash-date]').textContent =
            `Today: ${today} · Month to date: ${monthStart} to ${today} · Malaysia time`;

        try {
            const tasks = [
                report(today, today),
                report(monthStart, today)
            ];

            if (!admin) {
                tasks.push(report(today, today, {
                    report_type: 'followups',
                    status: 'pending'
                }));
            }

            const results = await Promise.allSettled(tasks);
            const errors = [];

            const daily = results[0];
            if (daily.status === 'fulfilled') {
                setValue(
                    'appointments',
                    count(daily.value.summary?.appointments)
                );
                renderStatuses(daily.value.appointment_statuses);
            } else {
                statusContainer.textContent =
                    'Could not load today’s appointment status.';
                errors.push('Today’s overview');
            }

            const monthly = results[1];
            if (monthly.status === 'fulfilled') {
                const data = monthly.value;

                setValue(
                    'consultations',
                    count(data.summary?.completed_consultations)
                );

                if (admin) {
                    setValue('orders', count(data.summary?.orders));

                    const net = Number(data.financial?.net);

                    setValue(
                        'collections',
                        data.financial?.net != null &&
                            Number.isFinite(net)
                            ? new Intl.NumberFormat('en-MY', {
                                style: 'currency',
                                currency: 'MYR'
                            }).format(net)
                            : '—'
                    );
                } else {
                    setValue('patients', count(data.summary?.patients));
                }
            } else {
                errors.push('Monthly overview');
            }

            if (!admin) {
                const followups = results[2];

                if (followups.status === 'fulfilled') {
                    setValue(
                        'followups',
                        count(followups.value.summary?.followups_due)
                    );
                } else {
                    errors.push('Follow-up overview');
                }
            }

            if (errors.length) {
                message.textContent =
                    `${errors.join(', ')} could not be loaded. Try Refresh.`;
            }
        } finally {
            loading = false;
            refresh.disabled = false;
        }
    }

    refresh.addEventListener('click', load);

    if (admin) {
        window.addEventListener('admin-profile-ready', load);

        // Also support initialization after the profile has loaded.
        const workspace = document.getElementById('dashboard');
        if (workspace && !workspace.hidden) load();
    } else {
        vetReady.then(profile => {
            if (profile) load();
        }).catch(() => {
            message.textContent = 'Could not load your account.';
        });
    }
})();