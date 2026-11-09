const vetTokenKey = 'vetdental_staff_token';

function vetLogout() {
    sessionStorage.removeItem(vetTokenKey);
    window.location.replace('/web/');
}

async function vetRequest(path, { method = 'GET', body } = {}) {
    const token = sessionStorage.getItem(vetTokenKey);

    if (!token) {
        vetLogout();
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
            vetLogout();
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
                    : 'Request failed. Check your details and try again.'
            );
        }

        return data;
    } catch (error) {
        if (error.name === 'AbortError' || error instanceof TypeError) {
            throw new Error(
                path === '/auth/change-password'
                    ? 'Could not confirm the password change. Try logging in with your new password. If it does not work, try your previous password.'
                    : method === 'GET'
                        ? 'Cannot reach the server. Check that the backend is running.'
                        : 'Could not confirm the update. Refresh your profile before trying again.'
            );
        }

        throw error;
    } finally {
        clearTimeout(timeout);
    }
}

function renderVetHeader(user) {
    document.getElementById('vet-header-name').textContent = user.full_name;

    document.getElementById('vet-header-avatar').textContent =
        user.full_name
            .trim()
            .split(/\s+/)
            .slice(0, 2)
            .map(part => Array.from(part)[0])
            .join('')
            .toUpperCase();
}

function buildVetLayout() {
    document.getElementById('shared-sidebar').innerHTML = `
        <a class="brand" href="/web/vet/">
            <span class="brand-icon" aria-hidden="true">✚</span>
            <span>
                VetDental
                <small>Clinical Management</small>
            </span>
        </a>

        <nav class="main-nav" aria-label="Veterinarian navigation">
            <a class="nav-item" href="/web/vet/" data-vet-page="dashboard">
                Dashboard
            </a>

            <a class="nav-item" href="/web/vet/schedules.html" data-vet-page="schedules">
                My Schedule
            </a>

            <a class="nav-item" href="/web/vet/appointments.html"
            data-vet-page="appointments">
                Appointments
            </a>

            <a class="nav-item" href="/web/vet/ai_assessments.html"
            data-vet-page="ai-assessments">
                AI Assessments
            </a>

            <a class="nav-item" href="/web/vet/patients.html" data-vet-page="patients">Patients</a>

            <a class="nav-item" href="/web/vet/consultations.html"
                data-vet-page="consultations">
                    Consultations
                </a>

            <a class="nav-item" href="/web/vet/clinical_history.html"
            data-vet-page="clinical-history">
                Treatment & Prescriptions
            </a>

            <a class="nav-item" href="/web/vet/followups.html"
            data-vet-page="followups">
                Follow-up Care
            </a>
            <a class="nav-item" href="/web/vet/reports.html" data-vet-page="reports">Reports</a>
        </nav>

        <nav class="bottom-nav" aria-label="Account">
            <a class="nav-item" href="/web/vet/profile.html" data-vet-page="profile">
                Profile
            </a>

            <button id="vet-logout" class="nav-item logout" type="button">
                Log out
            </button>
        </nav>
    `;

    const pathname = window.location.pathname;

    const currentVetPage =
        pathname.endsWith('/ai_assessments.html') ? 'ai-assessments' :
            pathname.endsWith('/reports.html') ? 'reports' :
                pathname.endsWith('/patients.html') ? 'patients' : pathname.endsWith('/profile.html')
                    ? 'profile'
                    : pathname.endsWith('/schedules.html')
                        ? 'schedules'
                        : pathname.endsWith('/appointments.html')
                            ? 'appointments'
                            : pathname.endsWith('/followups.html')
                                ? 'followups'
                                : pathname.endsWith('/clinical_history.html')
                                    ? 'clinical-history'
                                    : (
                                        pathname.endsWith('/consultations.html') ||
                                        pathname.endsWith('/consultation.html')
                                    )
                                        ? 'consultations'
                                        : 'dashboard';

    document.querySelectorAll('[data-vet-page]').forEach(link => {
        const active = link.dataset.vetPage === currentVetPage;

        link.classList.toggle('active', active);

        if (active) {
            link.setAttribute('aria-current', 'page');
        } else {
            link.removeAttribute('aria-current');
        }
    });

    document.getElementById('shared-topbar').innerHTML = `
        <span>Veterinarian Portal</span>
        <div class="account-link">
            <span id="vet-header-name"></span>
            <span id="vet-header-avatar" class="avatar small"
                  aria-hidden="true"></span>
        </div>
    `;

    document.getElementById('vet-logout').addEventListener('click', () => {
        try {
            vetLogout();
        } catch (_) {
            window.alert('Unable to log out. Please try again.');
        }
    });
}

async function initializeVetPage() {
    try {
        buildVetLayout();

        const profile = await vetRequest('/veterinarians/me');

        if (profile.user.role !== 'veterinarian') {
            throw new Error('This page requires a veterinarian account.');
        }

        renderVetHeader(profile.user);

        document.getElementById('vet-loading').hidden = true;
        document.getElementById('vet-workspace').hidden = false;

        return profile;
    } catch (error) {
        document.getElementById('vet-loading-message').textContent =
            error.message;

        document.getElementById('vet-retry').hidden = false;
        return null;
    }
}

document.getElementById('vet-retry').addEventListener('click', () => {
    window.location.reload();
});

const vetReady = initializeVetPage();

(() => {
    const script = document.createElement('script');
    script.src = '/web/notifications.js';
    document.head.appendChild(script);
})();