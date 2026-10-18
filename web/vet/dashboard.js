vetReady.then(profile => {
    if (!profile) return;

    document.getElementById('vet-welcome-name').textContent =
        profile.user.full_name;

    document.getElementById('vet-clinic').textContent =
        profile.clinic_name || 'Clinic not provided';
});