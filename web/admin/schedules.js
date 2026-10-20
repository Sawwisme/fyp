(() => {
    const tokenKey = 'vetdental_staff_token';
    const form = document.getElementById('schedule-form');
    const fields = document.getElementById('schedule-fields');
    const vetSelect = document.getElementById('schedule-vet');
    const dateInput = document.getElementById('schedule-date');
    const startInput = document.getElementById('schedule-start');
    const endInput = document.getElementById('schedule-end');
    const durationInput = document.getElementById('schedule-duration');
    const createButton = document.getElementById('create-schedule');
    const refreshButton = document.getElementById('refresh-schedules');
    const message = document.getElementById('schedule-message');
    const listMessage = document.getElementById('schedule-list-message');
    const list = document.getElementById('schedule-list');

    const bulkForm = document.getElementById('bulk-schedule-form');
    const bulkFields = document.getElementById('bulk-schedule-fields');
    const bulkVetOptions = document.getElementById('bulk-vet-options');
    const bulkStart = document.getElementById('bulk-start-date');
    const bulkEnd = document.getElementById('bulk-end-date');
    const bulkDuration = document.getElementById('bulk-slot-duration');
    const bulkMessage = document.getElementById('bulk-schedule-message');
    const generateButton = document.getElementById('generate-schedules');

    let busy = false;

    function logout() {
        sessionStorage.removeItem(tokenKey);
        window.location.replace('/web/');
    }

    async function request(path, body, method = body === undefined ? 'GET' : 'POST') {
        const token = sessionStorage.getItem(tokenKey);

        if (!token) {
            logout();
            throw new Error('Please log in again.');
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);

        try {
            const headers = {
                Accept: 'application/json',
                Authorization: `Bearer ${token}`
            };

            if (body !== undefined) {
                headers['Content-Type'] = 'application/json';
            }

            const response = await fetch(path, {
                method,
                headers,
                credentials: 'omit',
                cache: 'no-store',
                body: body === undefined ? undefined : JSON.stringify(body),
                signal: controller.signal
            });

            if (response.status === 401) {
                logout();
                throw new Error('Your session has expired.');
            }

            let data;

            try {
                data = await response.json();
            } catch (_) {
                throw new Error(
                    `Unexpected server response (HTTP ${response.status}).`
                );
            }

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Check your schedule details and try again.'
                );
            }

            return data;
        } catch (error) {
            if (error.name === 'AbortError' || error instanceof TypeError) {
                throw new Error(
                    body === undefined
                        ? 'Cannot reach the server. Please try again.'
                        : 'Could not confirm the change. Refresh the schedule list before trying again.'
                );
            }

            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    function setBusy(value) {
        busy = value;
        fields.disabled = value;
        createButton.disabled = value || !vetSelect.value;
        refreshButton.disabled = value || !vetSelect.value;
        bulkFields.disabled = value;
        generateButton.disabled = value || !vetSelect.options.length;

        list.querySelectorAll('button').forEach(button => {
            button.disabled = value;
        });
    }

    async function changeAvailability(path, body, method, question) {
        if (busy || !window.confirm(question)) return;

        setBusy(true);
        message.classList.remove('success');
        message.textContent = '';

        try {
            await request(path, body, method);

            message.classList.add('success');
            message.textContent = 'Schedule availability updated successfully.';

            await renderSchedules();
        } catch (error) {
            message.textContent = error.message;
        } finally {
            setBusy(false);
        }
    }

    async function renderSchedules() {
        list.replaceChildren();

        if (!vetSelect.value || !dateInput.value) {
            listMessage.textContent = 'Select a veterinarian and date.';
            return;
        }

        listMessage.textContent = 'Loading schedules…';

        try {
            const query = new URLSearchParams({
                veterinarian_id: vetSelect.value,
                schedule_date: dateInput.value,
                limit: '100'
            });

            const schedules = await request(`/schedules?${query}`);

            listMessage.textContent = schedules.length
                ? `${schedules.length} schedule(s) found. Expand one to view its slots.`
                : 'No schedules for this veterinarian on the selected date.';

            for (const schedule of schedules) {
                const details = document.createElement('details');
                details.className = 'schedule-entry';

                const summary = document.createElement('summary');
                summary.textContent =
                    `${schedule.start_time.slice(0, 5)}–${schedule.end_time.slice(0, 5)}`
                    + ` · ${schedule.time_slots.length} slots · ${schedule.status}`;

                details.appendChild(summary);

                const scheduleStart = Date.parse(
                    `${schedule.schedule_date}T${schedule.start_time}+08:00`
                );

                if (
                    schedule.status === 'active' &&
                    scheduleStart > Date.now()
                ) {
                    const cancelButton = document.createElement('button');
                    cancelButton.type = 'button';
                    cancelButton.className =
                        'secondary compact-button cancel-schedule';
                    cancelButton.textContent = 'Cancel schedule';

                    cancelButton.addEventListener('click', () => {
                        changeAvailability(
                            `/schedules/${schedule.schedule_id}/cancel`,
                            {},
                            'POST',
                            'Cancel this entire schedule? Its slots will stop accepting bookings. Existing appointments must be handled first.'
                        );
                    });

                    details.appendChild(cancelButton);
                }

                const slots = document.createElement('ul');
                slots.className = 'slot-list';

                for (const slot of schedule.time_slots) {
                    const item = document.createElement('li');
                    const label = document.createElement('span');

                    label.textContent =
                        `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`
                        + ` · ${slot.status}`;

                    item.appendChild(label);

                    const slotStart = Date.parse(
                        `${schedule.schedule_date}T${slot.start_time}+08:00`
                    );

                    if (
                        schedule.status === 'active' &&
                        slotStart > Date.now() &&
                        ['available', 'blocked'].includes(slot.status)
                    ) {
                        const button = document.createElement('button');
                        const blocking = slot.status === 'available';

                        button.type = 'button';
                        button.className = 'secondary compact-button';
                        button.textContent = blocking ? 'Block' : 'Reopen';

                        button.addEventListener('click', () => {
                            changeAvailability(
                                `/schedules/${schedule.schedule_id}/slots/${slot.time_slot_id}`,
                                {
                                    status: blocking ? 'blocked' : 'available'
                                },
                                'PATCH',
                                blocking
                                    ? 'Block this slot from new bookings?'
                                    : 'Make this slot available for booking again?'
                            );
                        });

                        item.appendChild(button);
                    }

                    slots.appendChild(item);
                }

                details.appendChild(slots);
                list.appendChild(details);
            }
        } catch (error) {
            listMessage.textContent = error.message;
        }
    }

    async function refreshSchedules() {
        if (busy) return;

        setBusy(true);

        try {
            await renderSchedules();
        } finally {
            setBusy(false);
        }
    }

    vetSelect.addEventListener('change', refreshSchedules);
    dateInput.addEventListener('change', refreshSchedules);
    refreshButton.addEventListener('click', refreshSchedules);

    for (const input of [startInput, endInput, durationInput]) {
        input.addEventListener('input', () => endInput.setCustomValidity(''));
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (busy) return;

        const minutes = value => {
            const [hour, minute] = value.split(':').map(Number);
            return hour * 60 + minute;
        };

        const duration = minutes(endInput.value) - minutes(startInput.value);
        const slotMinutes = Number(durationInput.value);

        endInput.setCustomValidity(
            duration <= 0
                ? 'End time must be later than start time.'
                : duration % slotMinutes !== 0
                    ? 'Working hours must divide evenly into the slot length.'
                    : ''
        );

        if (!form.reportValidity()) return;

        const body = {
            veterinarian_id: Number(vetSelect.value),
            schedule_date: dateInput.value,
            start_time: startInput.value,
            end_time: endInput.value,
            slot_minutes: slotMinutes
        };

        setBusy(true);
        message.classList.remove('success');
        message.textContent = '';
        createButton.textContent = 'Creating…';

        try {
            const schedule = await request('/schedules', body);

            message.classList.add('success');
            message.textContent =
                `Schedule created with ${schedule.time_slots.length} time slots.`;

            await renderSchedules();
        } catch (error) {
            message.textContent = error.message;
        } finally {
            createButton.textContent = 'Create schedule';
            setBusy(false);
        }
    });

    document.getElementById('logout-button').addEventListener('click', () => {
        try {
            logout();
        } catch (_) {
            message.classList.remove('success');
            message.textContent = 'Unable to log out. Please try again.';
        }
    });

    document.getElementById('schedule-retry').addEventListener('click', () => {
        window.location.reload();
    });

    bulkForm.addEventListener('submit', async event => {
        event.preventDefault();

        if (busy || !bulkForm.reportValidity()) return;

        bulkMessage.classList.remove('success');
        bulkMessage.textContent = '';

        const veterinarianIds = [
            ...bulkVetOptions.querySelectorAll('input:checked')
        ].map(input => Number(input.value));

        if (
            veterinarianIds.length === 0 ||
            veterinarianIds.length > 20
        ) {
            bulkMessage.textContent =
                'Select between 1 and 20 veterinarians.';
            return;
        }

        const start = Date.parse(`${bulkStart.value}T00:00:00Z`);
        const end = Date.parse(`${bulkEnd.value}T00:00:00Z`);
        const days = (end - start) / 86400000;

        if (!Number.isFinite(days) || days < 0 || days > 30) {
            bulkMessage.textContent =
                'Select a valid date range of at most 31 days.';
            return;
        }

        const body = {
            veterinarian_ids: veterinarianIds,
            start_date: bulkStart.value,
            end_date: bulkEnd.value,
            slot_minutes: Number(bulkDuration.value)
        };

        setBusy(true);
        generateButton.textContent = 'Generating…';

        try {
            const result = await request('/schedules/generate', body);

            bulkMessage.classList.add('success');
            bulkMessage.textContent =
                `Created ${result.created_schedules} schedules with ` +
                `${result.created_slots} slots. ` +
                `${result.closed_days} closed day(s) skipped.`;

            vetSelect.value = String(veterinarianIds[0]);
            dateInput.value = body.start_date;

            await renderSchedules();
        } catch (error) {
            bulkMessage.textContent = error.message;
        } finally {
            generateButton.textContent = 'Generate schedules';
            setBusy(false);
        }
    });

    async function start() {
        setBusy(true);

        try {
            const profile = await request('/admins/me');

            if (profile.user.role !== 'clinic_administrator') {
                throw new Error('This page requires an administrator account.');
            }

            document.getElementById('topbar-name').textContent =
                profile.user.full_name;

            document.getElementById('topbar-avatar').textContent =
                profile.user.full_name.trim().split(/\s+/)
                    .slice(0, 2)
                    .map(part => Array.from(part)[0])
                    .join('').toUpperCase();

            // Fetch every page so the veterinarian selector is complete.
            for (let offset = 0; ; offset += 100) {
                const vets = await request(
                    `/staff/veterinarians?offset=${offset}&limit=100`
                );

                for (const vet of vets) {
                    if (
                        vet.user.status !== 'active' ||
                        vet.approval_status !== 'approved'
                    ) continue;

                    const option = document.createElement('option');
                    option.value = vet.veterinarian_id;
                    option.textContent =
                        `${vet.user.full_name} (${vet.registration_number})`;
                    vetSelect.appendChild(option);
                    const label = document.createElement('label');
                    label.className = 'bulk-vet-option';

                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.name = 'bulk-vet';
                    checkbox.value = vet.veterinarian_id;

                    const text = document.createElement('span');
                    text.textContent = option.textContent;

                    label.append(checkbox, text);
                    bulkVetOptions.appendChild(label);
                }

                if (vets.length < 100) break;
            }

            dateInput.value = new Intl.DateTimeFormat('en-CA', {
                timeZone: 'Asia/Kuala_Lumpur',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            }).format(new Date());

            const tomorrow = new Date(`${dateInput.value}T00:00:00Z`);
            tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
            const tomorrowText = tomorrow.toISOString().slice(0, 10);

            bulkStart.min = tomorrowText;
            bulkEnd.min = tomorrowText;
            bulkStart.value = tomorrowText;
            bulkEnd.value = tomorrowText;

            document.getElementById('schedule-loading').hidden = true;
            document.getElementById('schedule-workspace').hidden = false;

            if (!vetSelect.value) {
                message.textContent =
                    'Create an active, approved veterinarian account first.';
            }

            await renderSchedules();
        } catch (error) {
            document.getElementById('schedule-loading-message').textContent =
                error.message;
            document.getElementById('schedule-retry').hidden = false;
        } finally {
            setBusy(false);
        }
    }

    start();
})();