const myScheduleDate = document.getElementById('my-schedule-date');
const myScheduleRefresh = document.getElementById('my-schedule-refresh');
const myScheduleList = document.getElementById('my-schedule-list');
const myScheduleMessage = document.getElementById('my-schedule-message');
const myScheduleAction = document.getElementById('my-schedule-action');

let myScheduleBusy = false;

function setMyScheduleBusy(value) {
    myScheduleBusy = value;
    myScheduleDate.disabled = value;
    myScheduleRefresh.disabled = value;

    myScheduleList.querySelectorAll('button').forEach(button => {
        button.disabled = value;
    });
}

async function renderMySchedules() {
    myScheduleList.replaceChildren();

    if (!myScheduleDate.value) {
        myScheduleMessage.textContent = 'Select a date.';
        return;
    }

    myScheduleMessage.textContent = 'Loading schedules…';

    try {
        const schedules = [];

        // Load every page for the selected day.
        for (let offset = 0; ; offset += 100) {
            const query = new URLSearchParams({
                schedule_date: myScheduleDate.value,
                offset: String(offset),
                limit: '100'
            });

            const page = await vetRequest(
                `/veterinarians/me/schedules?${query}`
            );

            schedules.push(...page);

            if (page.length < 100) break;
        }

        myScheduleMessage.textContent = schedules.length
            ? `${schedules.length} schedule(s) found. Expand one to view its slots.`
            : 'No schedules assigned to you on this date.';

        for (const schedule of schedules) {
            const details = document.createElement('details');
            details.className = 'schedule-entry';

            const summary = document.createElement('summary');
            summary.textContent =
                `${schedule.start_time.slice(0, 5)}–${schedule.end_time.slice(0, 5)}`
                + ` · ${schedule.time_slots.length} slots · ${schedule.status}`;

            const slots = document.createElement('ul');
            slots.className = 'slot-list';

            for (const slot of schedule.time_slots) {
                const item = document.createElement('li');
                const label = document.createElement('span');

                label.textContent =
                    `${slot.start_time.slice(0, 5)}–${slot.end_time.slice(0, 5)}`
                    + ` · ${slot.status}`;

                item.appendChild(label);

                const start = Date.parse(
                    `${schedule.schedule_date}T${slot.start_time}+08:00`
                );

                if (
                    schedule.status === 'active' &&
                    start > Date.now() &&
                    ['available', 'blocked'].includes(slot.status)
                ) {
                    const button = document.createElement('button');
                    const blocking = slot.status === 'available';

                    button.type = 'button';
                    button.className = 'secondary compact-button';
                    button.textContent = blocking ? 'Block' : 'Reopen';

                    button.addEventListener('click', () => {
                        updateMySlot(
                            schedule.schedule_id,
                            slot.time_slot_id,
                            blocking ? 'blocked' : 'available'
                        );
                    });

                    item.appendChild(button);
                }

                slots.appendChild(item);
            }

            details.append(summary, slots);
            myScheduleList.appendChild(details);
        }
    } catch (error) {
        myScheduleMessage.textContent = error.message;
    }
}

async function refreshMySchedules() {
    if (myScheduleBusy) return;

    setMyScheduleBusy(true);

    try {
        await renderMySchedules();
    } finally {
        setMyScheduleBusy(false);
    }
}

async function updateMySlot(scheduleId, slotId, status) {
    if (myScheduleBusy) return;

    const question = status === 'blocked'
        ? 'Block this slot from new bookings?'
        : 'Make this slot available for booking again?';

    if (!window.confirm(question)) return;

    setMyScheduleBusy(true);
    myScheduleAction.classList.remove('success');
    myScheduleAction.textContent = '';

    try {
        await vetRequest(
            `/schedules/${scheduleId}/slots/${slotId}`,
            {
                method: 'PATCH',
                body: { status }
            }
        );

        myScheduleAction.classList.add('success');
        myScheduleAction.textContent = 'Slot availability updated.';

        await renderMySchedules();
    } catch (error) {
        myScheduleAction.textContent = error.message;
    } finally {
        setMyScheduleBusy(false);
    }
}

myScheduleDate.addEventListener('change', () => {
    myScheduleAction.textContent = '';
    refreshMySchedules();
});

myScheduleRefresh.addEventListener('click', refreshMySchedules);

vetReady.then(profile => {
    if (!profile) return;

    myScheduleDate.value = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Kuala_Lumpur',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    }).format(new Date());

    refreshMySchedules();
});