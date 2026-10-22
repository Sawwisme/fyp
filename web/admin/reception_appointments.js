(() => {
    let initialized = false;

    function initialize() {
        if (initialized || !window.clinicScheduleContext) return;
        initialized = true;

        const context = window.clinicScheduleContext;
        const actions = document.querySelector(
            '.schedule-workspace-actions'
        );

        const openButton = document.createElement('button');
        openButton.type = 'button';
        openButton.className = 'primary compact-button';
        openButton.textContent = 'Create Appointment';
        actions.appendChild(openButton);

        const notice = document.createElement('p');
        notice.className = 'message success';
        notice.setAttribute('role', 'status');
        actions.after(notice);

        const dialog = document.createElement('dialog');
        dialog.className = 'reception-dialog';
        dialog.setAttribute('aria-labelledby', 'reception-title');

        dialog.innerHTML = `
            <div class="schedule-dialog-header">
                <h2 id="reception-title">Create Appointment</h2>
                <button id="reception-close"
                        class="dialog-close"
                        type="button"
                        aria-label="Close appointment dialog">×</button>
            </div>

            <form id="reception-form">
                <fieldset id="reception-fields">
                    <label class="field-label" for="customer-mode">
                        Customer
                    </label>
                    <select id="customer-mode">
                        <option value="existing">Existing customer</option>
                        <option value="new">Register new customer</option>
                    </select>

                    <div id="existing-customer-fields">
                        <label class="field-label" for="customer-query">
                            Search your clinic's customers
                        </label>
                        <input id="customer-query" type="search"
                               placeholder="Name, phone or email">

                        <label class="field-label" for="customer-results">
                            Matching customers
                        </label>
                        <select id="customer-results" disabled>
                            <option value="">Type at least 2 characters</option>
                        </select>

                        <p id="customer-search-message"
                           class="muted" role="status"></p>
                    </div>

                    <fieldset id="new-customer-fields" hidden disabled>
                        <div class="staff-form-grid">
                            <div>
                                <label class="field-label" for="walkin-name">
                                    Owner name
                                </label>
                                <input id="walkin-name" maxlength="150" required>
                            </div>
                            <div>
                                <label class="field-label" for="walkin-phone">
                                    Phone number
                                </label>
                                <input id="walkin-phone" type="tel"
                                       maxlength="20" required>
                            </div>
                            <div>
                                <label class="field-label" for="walkin-email">
                                    Email (optional)
                                </label>
                                <input id="walkin-email" type="email"
                                       maxlength="255">
                            </div>
                            <div>
                                <label class="field-label" for="walkin-address">
                                    Address (optional)
                                </label>
                                <input id="walkin-address" maxlength="255">
                            </div>
                            <div>
                                <label class="field-label" for="walkin-pet">
                                    Pet name
                                </label>
                                <input id="walkin-pet" maxlength="100" required>
                            </div>
                            <div>
                                <label class="field-label" for="walkin-species">
                                    Species
                                </label>
                                <select id="walkin-species" required>
                                    <option value="dog">Dog</option>
                                    <option value="cat">Cat</option>
                                </select>
                            </div>
                            <div>
                                <label class="field-label" for="walkin-breed">
                                    Breed (optional)
                                </label>
                                <input id="walkin-breed" maxlength="100">
                            </div>
                        </div>

                        <p class="muted">
                            Saves a customer and pet record without
                            creating a login account.
                        </p>

                        <button id="save-walkin-customer"
                                class="secondary compact-button"
                                type="button">
                            Save customer and pet
                        </button>
                    </fieldset>

                    <p id="selected-customer" class="selected-clinic">
                        No customer selected.
                    </p>

                    <label class="field-label" for="appointment-pet">
                        Pet
                    </label>
                    <select id="appointment-pet" required disabled>
                        <option value="">Select a customer first</option>
                    </select>

                    <div class="staff-form-grid">
                        <div>
                            <label class="field-label" for="appointment-source">
                                Booking source
                            </label>
                            <select id="appointment-source">
                                <option value="walk_in">Walk-in today</option>
                                <option value="reception">Reception booking</option>
                            </select>
                        </div>

                        <div>
                            <label class="field-label" for="appointment-date">
                                Appointment date
                            </label>
                            <input id="appointment-date" type="date" required>
                        </div>

                        <div>
                            <label class="field-label" for="appointment-vet">
                                Veterinarian
                            </label>
                            <select id="appointment-vet" required></select>
                        </div>

                        <div>
                            <label class="field-label" for="appointment-slot">
                                Available slot
                            </label>
                            <select id="appointment-slot" required disabled>
                                <option value="">Loading slots…</option>
                            </select>
                        </div>

                        <div>
                            <label class="field-label" for="appointment-type">
                                Appointment type
                            </label>
                            <select id="appointment-type">
                                <option value="dental_checkup">Dental checkup</option>
                                <option value="consultation">Consultation</option>
                                <option value="follow_up">Follow-up</option>
                            </select>
                        </div>
                    </div>

                    <p id="appointment-slot-message"
                       class="muted" role="status"></p>

                    <p id="reception-message"
                       class="message"
                       role="status"
                       aria-live="polite"></p>

                    <div class="staff-actions">
                        <button id="save-reception-appointment"
                                class="primary compact-button"
                                type="submit">
                            Create appointment
                        </button>

                        <button id="cancel-reception-appointment" class="secondary compact-button" type="button">
                            Cancel
                        </button>
                    </div>
                </fieldset>
            </form>
        `;

        document.body.appendChild(dialog);

        const field = id => dialog.querySelector(`#${id}`);
        const form = field('reception-form');
        const fields = field('reception-fields');
        const mode = field('customer-mode');
        const newFields = field('new-customer-fields');
        const queryInput = field('customer-query');
        const customerResults = field('customer-results');
        const petSelect = field('appointment-pet');
        const source = field('appointment-source');
        const appointmentDate = field('appointment-date');
        const vetSelect = field('appointment-vet');
        const slotSelect = field('appointment-slot');
        const message = field('reception-message');

        let customer = null;
        let customers = [];
        let saving = false;
        let slotsLoading = false;
        let searchTimer;
        let searchVersion = 0;
        let slotVersion = 0;

        function today() {
            return new Intl.DateTimeFormat('en-CA', {
                timeZone: 'Asia/Kuala_Lumpur',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            }).format(new Date());
        }

        function placeholder(select, text) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = text;
            select.replaceChildren(option);
            select.disabled = true;
        }

        function setSaving(value) {
            saving = value;
            fields.disabled = value;
            field('reception-close').disabled = value;
            context.setBusy(value);
        }

        function selectCustomer(record) {
            customer = record;

            placeholder(petSelect, 'Select a pet');

            for (const pet of record.pets) {
                const option = document.createElement('option');
                option.value = pet.pet_id;
                option.textContent =
                    `${pet.pet_name} (${pet.species})`;
                petSelect.appendChild(option);
            }

            petSelect.disabled = record.pets.length === 0;

            if (record.pets.length === 1) {
                petSelect.value = record.pets[0].pet_id;
            }

            field('selected-customer').textContent =
                `${record.full_name}` +
                (record.phone_number ? ` · ${record.phone_number}` : '');
        }

        function changeCustomerMode() {
            searchVersion += 1;
            clearTimeout(searchTimer);
            customer = null;

            const manual = mode.value === 'new';

            field('existing-customer-fields').hidden = manual;
            newFields.hidden = !manual;
            newFields.disabled = !manual;

            placeholder(petSelect, 'Select a customer first');
            field('selected-customer').textContent =
                'No customer selected.';
            field('customer-search-message').textContent = '';
        }

        async function loadSlots() {
            const version = ++slotVersion;
            slotsLoading = true;

            placeholder(slotSelect, 'Loading slots…');
            field('appointment-slot-message').textContent = '';

            if (!vetSelect.value || !appointmentDate.value) {
                slotsLoading = false;
                placeholder(slotSelect, 'Select a vet and date');
                return;
            }

            const bookingSource = source.value;

            try {
                const query = new URLSearchParams({
                    schedule_date: appointmentDate.value,
                    veterinarian_id: vetSelect.value
                });

                const overview = await context.request(
                    `/schedules/overview?${query}`
                );

                if (version !== slotVersion || !dialog.open) return;

                const slots = overview.veterinarians.flatMap(
                    vet => vet.schedules.flatMap(
                        schedule => schedule.time_slots
                    )
                ).filter(slot =>
                    bookingSource === 'walk_in'
                        ? slot.can_book_walk_in
                        : slot.can_book_reception
                );

                placeholder(
                    slotSelect,
                    slots.length
                        ? 'Select an available slot'
                        : 'No available slots'
                );

                for (const slot of slots) {
                    const option = document.createElement('option');
                    option.value = slot.time_slot_id;
                    option.textContent =
                        `${slot.start_time.slice(0, 5)}–` +
                        slot.end_time.slice(0, 5);
                    slotSelect.appendChild(option);
                }

                slotSelect.disabled = slots.length === 0;

                field('appointment-slot-message').textContent =
                    slots.length
                        ? 'Availability is checked again when booking.'
                        : 'No suitable slots. Check the vet’s schedule or select another vet/date.';
            } catch (error) {
                if (version !== slotVersion || !dialog.open) return;

                placeholder(slotSelect, 'Could not load slots');
                field('appointment-slot-message').textContent =
                    error.message;
            } finally {
                if (version === slotVersion) slotsLoading = false;
            }
        }

        function updateSource() {
            const walkIn = source.value === 'walk_in';
            const currentDay = today();

            appointmentDate.min = currentDay;
            appointmentDate.readOnly = walkIn;

            if (walkIn) {
                appointmentDate.value = currentDay;
                appointmentDate.max = currentDay;
            } else {
                appointmentDate.removeAttribute('max');

                if (appointmentDate.value < currentDay) {
                    appointmentDate.value = currentDay;
                }
            }

            loadSlots();
        }

        openButton.addEventListener('click', () => {
            if (context.isBusy()) return;

            const closeEditor =
                document.getElementById('close-schedule-editor');

            if (!closeEditor.hidden) closeEditor.click();

            form.reset();
            customer = null;
            customers = [];
            message.textContent = '';
            notice.textContent = '';

            placeholder(
                customerResults,
                'Type at least 2 characters'
            );

            vetSelect.replaceChildren(
                ...[
                    ...document.getElementById('schedule-vet').options
                ].map(option => option.cloneNode(true))
            );

            appointmentDate.value = today();
            changeCustomerMode();

            dialog.showModal();
            updateSource();
        });

        field('reception-close').addEventListener('click', () => {
            if (!saving) dialog.close();
        });

        dialog.addEventListener('cancel', event => {
            if (saving) event.preventDefault();
        });

        dialog.addEventListener('close', () => {
            searchVersion += 1;
            slotVersion += 1;
            clearTimeout(searchTimer);
        });

        field('cancel-reception-appointment').addEventListener(
            'click',
            () => {
                if (!saving) dialog.close();
            }
        );

        mode.addEventListener('change', changeCustomerMode);
        source.addEventListener('change', updateSource);
        appointmentDate.addEventListener('change', loadSlots);
        vetSelect.addEventListener('change', loadSlots);

        queryInput.addEventListener('input', () => {
            const version = ++searchVersion;
            clearTimeout(searchTimer);

            customer = null;
            placeholder(petSelect, 'Select a customer first');
            placeholder(customerResults, 'Searching…');
            field('selected-customer').textContent =
                'No customer selected.';

            const query = queryInput.value.trim();

            if (query.length < 2) {
                placeholder(
                    customerResults,
                    'Type at least 2 characters'
                );
                field('customer-search-message').textContent = '';
                return;
            }

            searchTimer = setTimeout(async () => {
                try {
                    const data = await context.request(
                        `/clinic-customers?q=${encodeURIComponent(query)}&limit=20`
                    );

                    if (
                        version !== searchVersion ||
                        mode.value !== 'existing' ||
                        !dialog.open
                    ) return;

                    customers = data;

                    placeholder(
                        customerResults,
                        data.length
                            ? 'Select a customer'
                            : 'No matching customers'
                    );

                    for (const record of data) {
                        const option = document.createElement('option');
                        option.value = record.pet_owner_id;
                        option.textContent =
                            `${record.full_name}` +
                            (record.phone_number
                                ? ` · ${record.phone_number}`
                                : '');

                        customerResults.appendChild(option);
                    }

                    customerResults.disabled = data.length === 0;

                    field('customer-search-message').textContent =
                        data.length
                            ? 'Showing up to 20 matching customers.'
                            : 'No match in this clinic. Check the details or register a new customer.';
                } catch (error) {
                    if (version !== searchVersion) return;

                    placeholder(customerResults, 'Search unavailable');
                    field('customer-search-message').textContent =
                        error.message;
                }
            }, 350);
        });

        customerResults.addEventListener('change', () => {
            const record = customers.find(
                item =>
                    String(item.pet_owner_id) === customerResults.value
            );

            customer = null;
            placeholder(petSelect, 'Select a customer first');

            if (record) selectCustomer(record);
        });

        field('save-walkin-customer').addEventListener(
            'click',
            async () => {
                if (saving || context.isBusy()) return;

                const inputs = [
                    ...newFields.querySelectorAll('input, select')
                ];

                for (const input of inputs) {
                    if (!input.reportValidity()) return;
                }

                message.textContent = '';
                setSaving(true);

                try {
                    const record = await context.request(
                        '/clinic-customers',
                        {
                            full_name: field('walkin-name').value.trim(),
                            phone_number: field('walkin-phone').value.trim(),
                            email:
                                field('walkin-email').value.trim() || null,
                            address:
                                field('walkin-address').value.trim() || null,
                            pet: {
                                pet_name: field('walkin-pet').value.trim(),
                                species: field('walkin-species').value,
                                breed:
                                    field('walkin-breed').value.trim() || null
                            }
                        }
                    );

                    mode.value = 'existing';
                    changeCustomerMode();

                    customers = [record];
                    queryInput.value = record.full_name;

                    placeholder(customerResults, 'Select a customer');

                    const option = document.createElement('option');
                    option.value = record.pet_owner_id;
                    option.textContent = record.full_name;
                    customerResults.appendChild(option);
                    customerResults.disabled = false;
                    customerResults.value = record.pet_owner_id;

                    selectCustomer(record);

                    message.textContent =
                        'Customer and pet saved. Complete the appointment details below.';
                } catch (error) {
                    message.textContent = error.message;
                } finally {
                    setSaving(false);
                }
            }
        );

        form.addEventListener('submit', async event => {
            event.preventDefault();

            if (saving || context.isBusy()) return;

            message.textContent = '';

            if (!customer) {
                message.textContent =
                    'Select an existing customer or save the new customer first.';
                return;
            }

            if (slotsLoading || !slotSelect.value) {
                message.textContent =
                    'Select an available appointment slot.';
                return;
            }

            if (!form.reportValidity() || !petSelect.value) return;

            const bookingDate = appointmentDate.value;

            setSaving(true);

            try {
                const result = await context.request(
                    '/clinic-appointments',
                    {
                        pet_owner_id: customer.pet_owner_id,
                        pet_id: Number(petSelect.value),
                        time_slot_id: Number(slotSelect.value),
                        appointment_type: field('appointment-type').value,
                        appointment_source: source.value
                    }
                );

                document.getElementById('overview-date').value =
                    bookingDate;

                notice.textContent =
                    `Appointment #${result.appointment_id} created successfully.`;

                dialog.close();

                window.dispatchEvent(
                    new Event('clinic-schedule-changed')
                );

                openButton.focus();
            } catch (error) {
                message.textContent = error.message;
            } finally {
                setSaving(false);
            }
        });
    }

    window.addEventListener(
        'clinic-schedule-ready',
        initialize
    );

    initialize();
})();