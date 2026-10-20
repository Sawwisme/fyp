(() => {
    window.clinicMapSelection = null;
    window.clinicMapSearching = false;
    window.clinicManualMode = false;

    const stateSelect = document.getElementById('clinic-state');
    const entryMode = document.getElementById('clinic-entry-mode');
    const searchFields = document.getElementById('clinic-search-fields');
    const queryInput = document.getElementById('clinic-name-query');
    const clinicSelect = document.getElementById('clinic-map-results');
    const message = document.getElementById('clinic-map-message');
    const selected = document.getElementById('selected-map-clinic');
    const existingClinic = document.getElementById('registration-clinic');
    const manualFields = document.getElementById('manual-clinic-fields');
    const manualName = document.getElementById('manual-clinic-name');
    const manualAddress = document.getElementById('manual-clinic-address');
    const preview = document.getElementById('clinic-map-preview');

    let clinics = [];
    let loadedState = '';
    let requestVersion = 0;
    let map = null;
    let marker = null;

    function identity(clinic) {
        return `${clinic.osm_type}/${clinic.osm_id}`;
    }

    function normalize(value) {
        return String(value)
            .toLocaleLowerCase()
            .replace(/[^\p{L}\p{N}]+/gu, ' ')
            .trim();
    }

    function closeClinicList() {
        clinicSelect.hidden = true;
        queryInput.setAttribute('aria-expanded', 'false');
        queryInput.removeAttribute('aria-activedescendant');
    }

    function setPlaceholder(text) {
        clinicSelect.replaceChildren();
        closeClinicList();

        queryInput.disabled = true;
        queryInput.placeholder = text;
    }

    function clearSelection() {
        window.clinicMapSelection = null;
        existingClinic.value = '';
        closeClinicList();
        selected.textContent = 'No clinic selected.';
        preview.hidden = true;
        preview.open = false;
    }

    function cancelPendingLoad() {
        requestVersion += 1;
        window.clinicMapSearching = false;
    }

    function setManualMode(enabled) {
        window.clinicManualMode = enabled;
        entryMode.value = enabled ? 'manual' : 'search';

        manualFields.hidden = !enabled;
        manualFields.disabled = !enabled;
        searchFields.hidden = enabled;

        manualName.setCustomValidity('');
        manualAddress.setCustomValidity('');
    }

    function showPreview(clinic) {
        if (typeof L === 'undefined') {
            message.textContent =
                'Clinic selected. Map preview is unavailable.';
            return;
        }

        preview.hidden = false;
        preview.open = true;

        if (!map) {
            map = L.map('registration-map', {
                scrollWheelZoom: false
            });

            L.tileLayer(
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                {
                    maxZoom: 19,
                    attribution:
                        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }
            ).addTo(map);
        }

        if (marker) marker.remove();

        marker = L.marker([
            clinic.latitude,
            clinic.longitude
        ]).addTo(map);

        const popup = document.createElement('span');
        popup.textContent = clinic.clinic_name;
        marker.bindPopup(popup);

        map.setView([clinic.latitude, clinic.longitude], 16);
        requestAnimationFrame(() => map.invalidateSize());
    }

    function chooseClinic(clinic) {
        if (
            registrationBusy ||
            window.clinicMapSearching ||
            window.clinicManualMode
        ) return;

        clearSelection();

        window.clinicMapSelection = clinic;
        queryInput.value = clinic.clinic_name;

        selected.textContent =
            `Selected: ${clinic.clinic_name}` +
            (clinic.address ? ` — ${clinic.address}` : '');

        closeClinicList();
        showPreview(clinic);
    }

    function renderClinics() {
        if (
            loadedState !== stateSelect.value ||
            window.clinicManualMode ||
            registrationBusy
        ) return;

        queryInput.disabled = false;
        queryInput.placeholder = 'Select or type your clinic';

        const keywords = normalize(queryInput.value)
            .split(/\s+/)
            .filter(Boolean);

        const matches = clinics.filter(clinic => {
            const text = normalize(
                `${clinic.clinic_name} ${clinic.address || ''}`
            );

            return keywords.every(keyword => text.includes(keyword));
        });

        clinicSelect.replaceChildren();

        for (const [index, clinic] of matches.entries()) {
            const option = document.createElement('button');
            option.type = 'button';
            option.className = 'clinic-option';
            option.id = `clinic-option-${index}`;
            option.tabIndex = -1;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', 'false');

            const name = document.createElement('strong');
            name.textContent = clinic.clinic_name;
            option.appendChild(name);

            if (clinic.address) {
                const address = document.createElement('span');
                address.textContent = clinic.address;
                option.appendChild(address);
            }

            // Keep keyboard focus in the searchable input.
            option.addEventListener('mousedown', event => {
                event.preventDefault();
            });

            option.addEventListener('click', () => {
                chooseClinic(clinic);
            });

            clinicSelect.appendChild(option);
        }

        if (!matches.length) {
            const empty = document.createElement('p');
            empty.className = 'clinic-empty';
            empty.textContent =
                'No matches. Choose Enter clinic details manually.';
            clinicSelect.appendChild(empty);
        }

        message.classList.add('success');
        message.textContent = `${matches.length} matching clinic(s).`;

        const open = document.activeElement === queryInput;
        clinicSelect.hidden = !open;
        queryInput.setAttribute('aria-expanded', String(open));
        queryInput.removeAttribute('aria-activedescendant');
    }

    async function loadClinics() {
        const version = ++requestVersion;
        const state = stateSelect.value;
        queryInput.value = '';
        message.classList.remove('success');

        clinics = [];
        loadedState = '';
        clearSelection();

        if (!state || window.clinicManualMode) {
            window.clinicMapSearching = false;
            setPlaceholder('Select your state first');
            message.textContent = '';
            return;
        }

        window.clinicMapSearching = true;
        setPlaceholder('Loading clinics…');
        message.textContent = 'Loading saved clinic directory…';

        try {
            const data = await registrationRequest(
                `/clinic-discovery/by-state?state=${encodeURIComponent(state)}`
            );

            if (
                version !== requestVersion ||
                state !== stateSelect.value ||
                window.clinicManualMode ||
                registrationBusy
            ) return;

            if (!Array.isArray(data)) {
                throw new Error('Invalid clinic directory response.');
            }

            clinics = data;
            loadedState = state;
            renderClinics();
        } catch (error) {
            if (
                version === requestVersion &&
                !window.clinicManualMode &&
                !registrationBusy
            ) {
                setPlaceholder('Clinic directory unavailable');
                message.textContent = error.message;
            }
        } finally {
            if (version === requestVersion) {
                window.clinicMapSearching = false;
            }
        }
    }

    entryMode.addEventListener('change', () => {
        if (registrationBusy) return;

        const enabled = entryMode.value === 'manual';

        cancelPendingLoad();
        clearSelection();
        setManualMode(enabled);

        if (enabled) {
            if (!manualName.value.trim()) {
                manualName.value = queryInput.value.trim();
            }

            selected.textContent = 'Manual clinic entry selected.';
            manualName.focus();
        } else {
            loadClinics();
        }
    });

    stateSelect.addEventListener('change', () => {
        if (registrationBusy) return;

        queryInput.value = '';
        loadClinics();

        if (window.clinicManualMode) {
            selected.textContent = 'Manual clinic entry selected.';
        }
    });

    queryInput.addEventListener('input', () => {
        if (registrationBusy || window.clinicManualMode) return;

        clearSelection();
        renderClinics();
    });

    queryInput.addEventListener('focus', () => {
        if (
            loadedState === stateSelect.value &&
            !window.clinicManualMode
        ) {
            renderClinics();
        }
    });

    queryInput.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeClinicList();
            return;
        }

        if (event.key === 'Enter') {
            event.preventDefault();

            if (clinicSelect.hidden) return;

            const activeId =
                queryInput.getAttribute('aria-activedescendant');

            const active = activeId
                ? document.getElementById(activeId)
                : null;

            if (active) active.click();
            return;
        }

        if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;

        event.preventDefault();

        if (clinicSelect.hidden) renderClinics();
        if (clinicSelect.hidden) return;

        const options = [
            ...clinicSelect.querySelectorAll('[role="option"]')
        ];

        if (!options.length) return;

        const activeId =
            queryInput.getAttribute('aria-activedescendant');

        let index = options.findIndex(option => option.id === activeId);

        if (index === -1) {
            index = event.key === 'ArrowDown'
                ? 0
                : options.length - 1;
        } else {
            index = (
                index +
                (event.key === 'ArrowDown' ? 1 : -1) +
                options.length
            ) % options.length;
        }

        options.forEach((option, position) => {
            option.setAttribute(
                'aria-selected',
                String(position === index)
            );
        });

        queryInput.setAttribute(
            'aria-activedescendant',
            options[index].id
        );

        options[index].scrollIntoView({ block: 'nearest' });
    });

    queryInput.addEventListener('blur', closeClinicList);

    existingClinic.addEventListener('change', () => {
        if (registrationBusy) return;

        const value = existingClinic.value;
        if (!value) return;

        const name = existingClinic.selectedOptions[0].textContent;

        cancelPendingLoad();
        clearSelection();
        setManualMode(false);

        existingClinic.value = value;
        selected.textContent = `Selected registered clinic: ${name}`;
    });

    preview.addEventListener('toggle', () => {
        if (preview.open && map) {
            requestAnimationFrame(() => map.invalidateSize());
        }
    });

    setManualMode(entryMode.value === 'manual');

    if (stateSelect.value && !window.clinicManualMode) {
        loadClinics();
    }
})();