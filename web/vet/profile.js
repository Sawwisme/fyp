const vetEditDialog = document.getElementById('vet-edit-dialog');
const vetEditForm = document.getElementById('vet-edit-form');
const vetEditFields = document.getElementById('vet-edit-fields');
const vetEditName = document.getElementById('vet-edit-name');
const vetEditPhone = document.getElementById('vet-edit-phone');
const vetEditMessage = document.getElementById('vet-edit-message');
const vetEditSave = document.getElementById('vet-edit-save');
const vetEditClose = document.getElementById('vet-edit-close');
const vetEditCancel = document.getElementById('vet-edit-cancel');

let vetProfile = null;
let vetProfileSaving = false;

function profileText(id, value) {
    document.getElementById(id).textContent = value;
}

function renderVetProfile(profile) {
    const user = profile.user;

    renderVetHeader(user);

    profileText(
        'profile-avatar',
        document.getElementById('vet-header-avatar').textContent
    );

    profileText('profile-name', user.full_name);
    profileText('profile-full-name', user.full_name);
    profileText('profile-status', user.status);
    profileText('profile-vet-id', `Vet ID: ${profile.veterinarian_id}`);
    profileText('profile-registration', profile.registration_number);
    profileText('profile-clinic', profile.clinic_name || 'Not provided');
    profileText('profile-qualification', profile.qualification || 'Not provided');
    profileText('profile-specialization', profile.specialization || 'Not provided');
    profileText(
        'profile-experience',
        profile.years_experience == null
            ? 'Not provided'
            : `${profile.years_experience} year(s)`
    );

    profileText('profile-email', user.email);
    profileText('profile-phone', user.phone_number || 'Not provided');
    profileText(
        'profile-created',
        typeof user.created_at === 'string'
            ? user.created_at.split('T')[0]
            : 'Not available'
    );
}

vetReady.then(profile => {
    if (!profile) return;

    vetProfile = profile;
    renderVetProfile(profile);
});

document.getElementById('edit-vet-profile').addEventListener('click', () => {
    if (!vetProfile) return;

    vetEditName.value = vetProfile.user.full_name;
    vetEditPhone.value = vetProfile.user.phone_number || '';
    vetEditName.setCustomValidity('');
    vetEditMessage.textContent = '';
    profileText('profile-message', '');

    vetEditDialog.showModal();
    vetEditName.focus();
});

vetEditName.addEventListener('input', () => {
    vetEditName.setCustomValidity('');
});

function closeVetEditor() {
    if (!vetProfileSaving) vetEditDialog.close();
}

vetEditClose.addEventListener('click', closeVetEditor);
vetEditCancel.addEventListener('click', closeVetEditor);

vetEditDialog.addEventListener('cancel', event => {
    if (vetProfileSaving) event.preventDefault();
});

vetEditForm.addEventListener('submit', async event => {
    event.preventDefault();

    if (vetProfileSaving) return;

    vetEditName.setCustomValidity(
        vetEditName.value.trim() ? '' : 'Full name cannot be blank.'
    );

    if (!vetEditForm.reportValidity()) return;

    const body = {
        full_name: vetEditName.value.trim(),
        phone_number: vetEditPhone.value.trim() || null
    };

    vetProfileSaving = true;
    vetEditFields.disabled = true;
    vetEditSave.disabled = true;
    vetEditClose.disabled = true;
    vetEditCancel.disabled = true;
    vetEditSave.textContent = 'Saving…';
    vetEditMessage.textContent = '';

    try {
        const profile = await vetRequest('/veterinarians/me', {
            method: 'PATCH',
            body
        });

        vetProfile = profile;
        renderVetProfile(profile);
        vetEditDialog.close();
        profileText('profile-message', 'Profile updated successfully.');
    } catch (error) {
        vetEditMessage.textContent = error.message;
    } finally {
        vetProfileSaving = false;
        vetEditFields.disabled = false;
        vetEditSave.disabled = false;
        vetEditClose.disabled = false;
        vetEditCancel.disabled = false;
        vetEditSave.textContent = 'Save changes';
    }
});