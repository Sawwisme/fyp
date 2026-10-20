(() => {
    window.clinicMapSelection = null;
    window.clinicMapSearching = false;
    window.clinicManualMode = false;

    const queryInput = document.getElementById('clinic-name-query');
    const searchButton = document.getElementById('search-clinic-name');
    const message = document.getElementById('clinic-map-message');
    const results = document.getElementById('clinic-map-results');
    const selected = document.getElementById('selected-map-clinic');
    const existingClinic = document.getElementById('registration-clinic');

    const manualToggle = document.getElementById('clinic-manual-toggle');
    const manualFields = document.getElementById('manual-clinic-fields');
    const manualName = document.getElementById('manual-clinic-name');
    const manualAddress = document.getElementById('manual-clinic-address');

    const preview = document.getElementById('clinic-map-preview');

    let map = null;
    let marker = null;
    let lastSearch = 0;

    function hidePreview() {
        preview.hidden = true;
        preview.open = false;
    }

    function resetSelection() {
        window.clinicMapSelection = null;
        existingClinic.value = '';
        selected.textContent = 'No clinic selected.';

        results.querySelectorAll('button').forEach(button => {
            button.classList.remove('selected');
            button.setAttribute('aria-pressed', 'false');
        });

        hidePreview();
    }

    function setManualMode(enabled) {
        window.clinicManualMode = enabled;
        manualFields.hidden = !enabled;
        manualFields.disabled = !enabled;
        manualToggle.textContent = enabled
            ? 'Cancel manual entry'
            : 'My clinic isn’t listed';

        manualName.setCustomValidity('');
        manualAddress.setCustomValidity('');
    }

    function showClinicPreview(clinic) {
        if (typeof L === 'undefined') {
            message.textContent =
                'Clinic selected. The map preview is unavailable, but you can still submit.';
            return;
        }

        preview.hidden = false;
        preview.open = true;

        if (!map) {
            map = L.map('registration-map', {
                scrollWheelZoom: false
            });

            L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution:
                    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);
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

    preview.addEventListener('toggle', () => {
        if (preview.open && map) {
            requestAnimationFrame(() => map.invalidateSize());
        }
    });

    function chooseClinic(clinic) {
        if (registrationBusy || window.clinicMapSearching) return;

        setManualMode(false);
        resetSelection();

        window.clinicMapSelection = clinic;
        selected.textContent =
            `Selected: ${clinic.clinic_name}`
            + (clinic.address ? ` — ${clinic.address}` : '');

        results.querySelectorAll('button').forEach(button => {
            const active =
                button.dataset.identity === `${clinic.osm_type}/${clinic.osm_id}`;

            button.classList.toggle('selected', active);
            button.setAttribute('aria-pressed', String(active));
        });

        showClinicPreview(clinic);
    }

    manualToggle.addEventListener('click', () => {
        if (registrationBusy || window.clinicMapSearching) return;

        const enabled = !window.clinicManualMode;

        resetSelection();
        setManualMode(enabled);

        if (enabled) {
            manualName.value = queryInput.value.trim();
            selected.textContent = 'Manual clinic entry selected.';
            manualName.focus();
        }
    });

    existingClinic.addEventListener('change', () => {
        const value = existingClinic.value;

        if (!value) {
            if (!window.clinicManualMode && !window.clinicMapSelection) {
                selected.textContent = 'No clinic selected.';
            }
            return;
        }

        const name = existingClinic.selectedOptions[0].textContent;

        setManualMode(false);
        resetSelection();
        existingClinic.value = value;
        selected.textContent = `Selected registered clinic: ${name}`;
    });

    queryInput.addEventListener('input', () => {
        if (window.clinicMapSelection) resetSelection();
    });

    queryInput.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchButton.click();
        }
    });

    searchButton.addEventListener('click', async () => {
        if (window.clinicMapSearching || registrationBusy) return;

        const query = queryInput.value.trim();

        if (query.length < 3) {
            message.textContent = 'Enter at least 3 characters.';
            return;
        }

        if (Date.now() - lastSearch < 8000) {
            message.textContent = 'Please wait a few seconds before searching again.';
            return;
        }

        lastSearch = Date.now();
        window.clinicMapSearching = true;
        searchButton.disabled = true;
        manualToggle.disabled = true;
        searchButton.textContent = 'Searching…';

        setManualMode(false);
        resetSelection();
        results.replaceChildren();
        message.textContent = 'Searching veterinary clinics…';

        try {
            const clinics = await registrationRequest(
                `/clinic-discovery/by-name?q=${encodeURIComponent(query)}`
            );

            if (!Array.isArray(clinics)) {
                throw new Error('Unexpected clinic search response.');
            }

            message.textContent = clinics.length
                ? 'Select your clinic below.'
                : 'No matching clinics found. Add the town to your search, or choose My clinic isn’t listed.';

            for (const clinic of clinics) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'clinic-search-result';
                button.dataset.identity = `${clinic.osm_type}/${clinic.osm_id}`;
                button.setAttribute('aria-pressed', 'false');

                const name = document.createElement('strong');
                name.textContent = clinic.clinic_name;

                const address = document.createElement('span');
                address.textContent = clinic.address || 'Address not provided';

                button.append(name, address);
                button.addEventListener('click', () => chooseClinic(clinic));
                results.appendChild(button);
            }
        } catch (error) {
            message.textContent =
                `${error.message} You can also enter your clinic manually.`;
        } finally {
            window.clinicMapSearching = false;
            searchButton.disabled = false;
            manualToggle.disabled = false;
            searchButton.textContent = 'Search';
        }
    });
})();