(() => {
    const get = id => document.getElementById(id);
    const node = (tag, text, cls) => {
        const element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        if (cls) element.className = cls;
        return element;
    };
    const size = 20;
    let ready = false, page = 0, version = 0, timer;
    let selected, kind = 'consultations', recordPage = 0, recordVersion = 0;
    const dialog = get('patient-dialog');
    function date(value) {
        if (!value) return 'Not recorded';
        if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.split('-').reverse().join('/');
        return new Date(value + (/(Z|[+-]\d{2}:\d{2})$/.test(value) ? '' : 'Z'))
            .toLocaleDateString('en-MY', {timeZone: 'Asia/Kuala_Lumpur'});
    }
    function age(value) {
        if (!value) return 'Age not recorded';
        const today = new Date().toLocaleDateString('en-CA', {timeZone:'Asia/Kuala_Lumpur'});
        const [y,m,d] = value.split('-').map(Number);
        const [ty,tm,td] = today.split('-').map(Number);
        const years = ty-y-Number(tm<m || (tm===m && td<d));
        return years < 0 ? 'Age not recorded' : years === 0 ? 'Under 1 year' : `${years} year${years===1?'':'s'}`;
    }
    async function load(target = 0) {
        if (!ready) return;
        const current = ++version;
        get('patient-message').textContent = 'Loading patients…';
        get('patient-rows').replaceChildren();
        get('patient-total').textContent = '—';
        get('patient-previous').disabled = get('patient-next').disabled = true;
        get('patient-retry').hidden = true;
        try {
            const query = new URLSearchParams({search:get('patient-search').value.trim(), offset:target*size, limit:size});
            const data = await vetRequest(`/vet-patients?${query}`);
            if (current !== version) return;
            page = target;
            get('patient-total').textContent = data.total;
            for (const patient of data.items) {
                const row = node('tr');
                for (const text of [patient.pet_name, [patient.species,patient.breed].filter(Boolean).join(' · '), age(patient.date_of_birth), patient.owner_name || 'Not recorded']) row.appendChild(node('td',text));
                const action = node('td');
                const button = node('button','View patient','secondary compact-button');
                button.type = 'button';
                button.addEventListener('click',()=>openPatient(patient));
                action.appendChild(button); row.appendChild(action); get('patient-rows').appendChild(row);
            }
            get('patient-message').textContent = data.total ? `${data.total} matching patient(s) · Page ${page+1}` : 'No matching patients assigned to you.';
            get('patient-previous').disabled = page === 0;
            get('patient-next').disabled = (page+1)*size >= data.total;
        } catch(error) {
            if(current!==version)return;
            get('patient-message').textContent=error.message;
            get('patient-retry').hidden=false;
        }
    }
    function openPatient(patient) {
        selected = patient; kind = 'consultations';
        get('patient-dialog-title').textContent = patient.pet_name;
        get('patient-profile').replaceChildren();
        for(const [label,value] of [['Species',patient.species],['Breed',patient.breed],['Age',age(patient.date_of_birth)],['Gender',patient.gender],['Weight',patient.weight == null ? null : `${patient.weight} kg`],['Owner',patient.owner_name],['Phone',patient.owner_phone],['Email',patient.owner_email]]) {
            const box=node('div');box.append(node('small',label),node('strong',value||'Not recorded'));get('patient-profile').appendChild(box);
        }
        dialog.showModal(); loadRecords();
    }
    async function loadRecords(target = 0) {
        const current = ++recordVersion;
        get('patient-records').replaceChildren();
        get('record-message').textContent='Loading records…';
        get('record-previous').disabled=get('record-next').disabled=true;
        get('record-retry').hidden=true;
        document.querySelectorAll('[data-record-kind]').forEach(button=>{
            const active=button.dataset.recordKind===kind;
            button.setAttribute('aria-pressed',String(active));
        });
        try {
            const query = new URLSearchParams({kind,offset:target*size,limit:size});
            const data = await vetRequest(`/vet-patients/${selected.pet_id}/records?${query}`);
            if(current!==recordVersion || !dialog.open)return;
            recordPage=target;
            for(const record of data.items) {
                const card=node('article',undefined,'patient-record');
                card.append(node('small',date(record.date)),node('h3',record.title));
                if(record.status)card.appendChild(node('span',record.status.replaceAll('_',' '),'patient-status'));
                if(record.details)card.appendChild(node('p',record.details));
                if(record.consultation_id){const link=node('a','Open consultation');link.href=`/web/vet/consultation.html?id=${record.consultation_id}`;card.appendChild(link);}
                get('patient-records').appendChild(card);
            }
            get('record-message').textContent=data.total?`${data.total} record(s) · Page ${recordPage+1}`:'No records in this section.';
            get('record-previous').disabled=recordPage===0;
            get('record-next').disabled=(recordPage+1)*size>=data.total;
        }catch(error){if(current!==recordVersion || !dialog.open)return;get('record-message').textContent=error.message;get('record-retry').hidden=false;}
    }
    get('patient-search').addEventListener('input',()=>{clearTimeout(timer);version++;get('patient-previous').disabled=get('patient-next').disabled=true;timer=setTimeout(()=>load(),300);});
    get('patient-previous').addEventListener('click',()=>load(page-1));
    get('patient-next').addEventListener('click',()=>load(page+1));
    get('patient-retry').addEventListener('click',()=>load(page));
    get('record-retry').addEventListener('click',()=>loadRecords(recordPage));
    get('record-previous').addEventListener('click',()=>loadRecords(recordPage-1));
    get('record-next').addEventListener('click',()=>loadRecords(recordPage+1));
    get('patient-close').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>{recordVersion++;});
    document.querySelectorAll('[data-record-kind]').forEach(button=>button.addEventListener('click',()=>{kind=button.dataset.recordKind;loadRecords();}));
    vetReady.then(profile=>{if(profile){ready=true;load();}});
})();
