(() => {
    const get = id => document.getElementById(id);
    const admin = document.body.dataset.reportRole === 'admin';
    const names = {
        overview: 'Clinic activity report', appointments: 'Appointment report',
        consultations: 'Consultation report', treatments: 'Treatment report',
        prescriptions: 'Prescription report', followups: 'Follow-up care report',
        collections: 'Payment collections report', orders: 'Shop order report'
    };
    if (!admin) names.overview = 'My clinical activity report';
    const statuses = {
        appointments: ['pending', 'pending_payment', 'confirmed', 'in_progress', 'completed', 'cancelled', 'rejected', 'no_show'],
        consultations: ['draft', 'completed'], treatments: ['planned', 'in_progress', 'completed', 'cancelled'],
        followups: ['pending', 'completed', 'cancelled'],
        orders: ['pending_payment', 'pending', 'paid', 'processing', 'ready_for_pickup', 'shipped', 'completed', 'cancelled', 'refunded', 'expired']
    };
    const notes = {
        appointments: 'Appointments are selected by their scheduled date. Statuses show the current state, including cancellations.',
        consultations: 'Consultations are selected by their recorded consultation date in Malaysia time. Statuses show the current state.',
        treatments: 'Treatments from finalized consultations only, selected by their recorded treatment date. Status uses the latest treatment progress record.',
        prescriptions: 'Prescriptions from finalized consultations only, selected by prescription date. Medication counts show the top 20 names; use the medication filter to narrow the report.',
        followups: 'Follow-up tasks from finalized consultations, selected by recommended review date. Tasks without a recommended date are excluded. Statuses show the current state.',
        collections: 'Completed payment and refund ledger entries, selected by the date money was recorded. Deposits are counted when received; applying a deposit to a bill does not count it again. Refunds may relate to earlier periods. Delivery fees are included; gateway fees are not deducted. This is a collections report, not a profit report.',
        orders: 'Orders are selected by the date they were placed in Malaysia time. Statuses show the current state; order counts do not indicate payments received.',
        overview: 'Each metric uses its own activity date: scheduled date for appointments, recorded date for consultations, treatment and prescription dates for finalized clinical records, and recommended date for follow-ups. Statuses show the current state. Collections use completed ledger entries, including deposits and completed refunds; deposit credits are not counted twice.'
    };
    let ready = false, version = 0, data = null, exportRows = [];
    const node = (tag, text, cls) => {
        const e = document.createElement(tag);
        if (text !== undefined) e.textContent = text;
        if (cls) e.className = cls;
        return e;
    };
    const money = value => new Intl.NumberFormat('en-MY', {style:'currency',currency:'MYR'}).format(Number(value));
    const label = value => ({online_banking:'FPX',card:'Card',cash:'Cash',shop:'Shop',
        consultation_balance:'Consultation balances',booking_deposit:'Booking deposits',
        no_show:'No-show',pending_payment:'Awaiting payment'}[value] || String(value).replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()));
    function today() {
        const parts = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kuala_Lumpur',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
        const pick = name => parts.find(part=>part.type===name).value;
        return `${pick('year')}-${pick('month')}-${pick('day')}`;
    }
    const displayDate = value => value.split('-').reverse().join('/');
    function dates(mode) {
        const end=today();get('report-to').value=end;
        get('report-from').value=mode==='today'?end:mode==='year'?`${end.slice(0,4)}-01-01`:`${end.slice(0,7)}-01`;
    }
    async function request(path) {
        if (!admin) return vetRequest(path);
        const token=sessionStorage.getItem('vetdental_staff_token');
        if (!token) { location.replace('/web/'); throw new Error('Please log in again.'); }
        const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),20000);
        try {
            const response=await fetch(path,{headers:{Accept:'application/json',Authorization:`Bearer ${token}`},credentials:'omit',cache:'no-store',signal:controller.signal});
            if(response.status===401){sessionStorage.removeItem('vetdental_staff_token');location.replace('/web/');throw new Error('Your session has expired.');}
            let json;try{json=await response.json();}catch(_){throw new Error(`Unexpected server response (HTTP ${response.status}).`);}
            if(!response.ok)throw new Error(typeof json.detail==='string'?json.detail:'Could not load the report.');
            return json;
        }catch(error){if(error.name==='AbortError'||error instanceof TypeError)throw new Error('Cannot reach the server. Please try again.');throw error;}
        finally{clearTimeout(timeout);}
    }
    function invalidate() {
        version++;data=null;exportRows=[];
        get('report-export').disabled=get('report-print').disabled=true;
        get('report-results').hidden=true;get('report-retry').hidden=true;
        get('report-message').textContent='Filters changed. Generate the report to update the results.';
    }
    function configure() {
        const type=get('report-type').value;
        const status=get('report-status');status.replaceChildren(new Option('All statuses',''));
        for(const value of statuses[type]||[]) status.add(new Option(label(value),value));
        get('report-status-field').hidden=!statuses[type];
        get('report-vet-field').hidden=!admin||['collections','orders'].includes(type);
        get('report-method-field').hidden=get('report-source-field').hidden=type!=='collections';
        get('report-shipping-field').hidden=type!=='orders';
        get('report-medication-field').hidden=type!=='prescriptions';
        get('report-title').placeholder=names[type];
        invalidate();
    }
    function title() { return get('report-title').value.trim() || names[data?.report_type||get('report-type').value]; }
    function updateTitle() { if(data)get('report-document-title').textContent=title(); }
    function addCards(items) {
        const container=get('report-cards');container.replaceChildren();
        exportRows.push([],['Metric','Value']);
        for(const [text,value] of items){const card=node('article',undefined,'report-stat');card.append(node('span',text),node('strong',value));container.appendChild(card);exportRows.push([text,value]);}
    }
    function statusPanel(title,rows) {
        const section=node('section',undefined,'report-section');section.appendChild(node('h3',title));
        exportRows.push([],[title,'Count']);
        if(!rows.length)section.appendChild(node('p','No matching records.','muted'));
        const total=rows.reduce((sum,item)=>sum+item.count,0);
        for(const item of rows){const line=node('div',undefined,'report-status-row'), heading=node('div');heading.append(node('span',label(item.status)),node('strong',item.count));const track=node('div',undefined,'report-track'),bar=node('span');bar.style.width=`${100*item.count/Math.max(total,1)}%`;track.appendChild(bar);line.append(heading,track);section.appendChild(line);exportRows.push([label(item.status),item.count]);}
        get('report-sections').appendChild(section);
    }
    function trend(days) {
        const section=node('section',undefined,'report-section report-wide');section.appendChild(node('h3','Completed consultation trend'));
        const grouped=new Map(), monthly=days.length>62;
        for(const day of days){const key=monthly?day.date.slice(0,7):day.date;grouped.set(key,(grouped.get(key)||0)+day.consultations);}
        const max=Math.max(1,...grouped.values()), chart=node('div',undefined,'report-chart');
        chart.setAttribute('role','group');chart.setAttribute('aria-label','Completed consultations over the selected period');
        for(const [date,count] of grouped){const column=node('div',undefined,'report-chart-column'),bar=node('div',undefined,'report-chart-bar');bar.style.height=`${count/max*130}px`;column.setAttribute('aria-label',`${date}: ${count} consultations`);column.append(node('strong',count),bar,node('small',monthly?date:date.slice(5)));chart.appendChild(column);}
        section.append(chart,node('p',monthly?'Monthly totals within the selected dates.':'Daily totals in Malaysia time.','muted'));get('report-sections').appendChild(section);
        // This table also provides a printable alternative to a wide chart.
        const table=node('table',undefined,'report-print-trend');const head=node('thead'),hr=node('tr');hr.append(node('th','Date (MYT)'),node('th','Completed consultations'));head.appendChild(hr);const body=node('tbody');
        for(const [date,count] of grouped){const row=node('tr');row.append(node('td',date),node('td',count));body.appendChild(row);}table.append(head,body);section.appendChild(table);
        exportRows.push([],['Date (MYT)','Completed consultations']);for(const day of days)exportRows.push([day.date,day.consultations]);
    }
    function collections(finance) {
        const section=node('section',undefined,'report-section report-wide');section.appendChild(node('h3','Collections by source and method'));
        const scroll=node('div',undefined,'table-scroll'),table=node('table',undefined,'staff-table');const head=node('thead'),header=node('tr');
        for(const name of ['Source','Method','Received','Refunded','Net']){const cell=node('th',name);cell.scope='col';header.appendChild(cell);}head.appendChild(header);table.appendChild(head);const body=node('tbody');
        exportRows.push([],['Source','Method','Received MYR','Refunded MYR','Net MYR']);
        for(const row of finance.breakdown){const tr=node('tr');for(const value of [label(row.source),label(row.method),money(row.collected),money(row.refunded),money(row.net)])tr.appendChild(node('td',value));body.appendChild(tr);exportRows.push([label(row.source),label(row.method),row.collected,row.refunded,row.net]);}
        table.appendChild(body);scroll.appendChild(table);section.appendChild(scroll);
        if(!finance.breakdown.length)section.appendChild(node('p','No completed collections or refunds match these filters.','muted'));
        const total=node('p',`Received ${money(finance.collected)} · Refunded ${money(finance.refunded)} · Net ${money(finance.net)}`,'report-financial-total');section.appendChild(total);get('report-sections').appendChild(section);
        exportRows.push(['Total','',finance.collected,finance.refunded,finance.net]);
    }
    function filterDescription(report) {
        const values=[];
        if(!['collections','orders'].includes(report.report_type))values.push(report.filters.veterinarian);
        for(const [key,prefix] of [['status','Status'],['payment_method','Method'],['payment_source','Source'],['shipping_method','Fulfilment'],['medication','Medication']])if(report.filters[key])values.push(`${prefix}: ${label(report.filters[key])}`);
        return values.filter(Boolean).join(' · ') || 'All records in the selected period';
    }
    function render(report) {
        const type=report.report_type,s=report.summary, statusesFor=key=>report[`${key}_statuses`]||[];
        const count=(key,status)=>statusesFor(key).find(row=>row.status===status)?.count||0;
        exportRows=[];get('report-sections').replaceChildren();
        get('report-clinic-name').textContent=report.clinic_name;
        updateTitle();
        get('report-document-period').textContent=`${displayDate(report.date_from)} – ${displayDate(report.date_to)} · Malaysia time`;
        get('report-document-filters').textContent=filterDescription(report);
        get('report-document-prepared').textContent=`Prepared by ${report.prepared_by} · ${new Date(report.generated_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'})} MYT`;
        if(type==='overview')addCards([['Appointments',s.appointments],['Completed consultations',s.completed_consultations],['Unique patients',s.patients],['Treatments recorded',s.treatments]]);
        else if(type==='appointments')addCards([['Appointments',s.appointments],['Confirmed',count('appointment','confirmed')],['In progress',count('appointment','in_progress')],['Completed',count('appointment','completed')]]);
        else if(type==='consultations')addCards([['Consultations',statusesFor('consultation').reduce((sum,x)=>sum+x.count,0)],['Draft',count('consultation','draft')],['Completed',s.completed_consultations]]);
        else if(type==='treatments')addCards([['Treatments',s.treatments],['Planned',count('treatment','planned')],['In progress',count('treatment','in_progress')],['Completed',count('treatment','completed')]]);
        else if(type==='prescriptions')addCards([['Prescriptions',s.prescriptions]]);
        else if(type==='followups')addCards([['Follow-up tasks due',s.followups_due],['Pending',count('followup','pending')],['Completed',count('followup','completed')],['Cancelled',count('followup','cancelled')]]);
        else if(type==='orders')addCards([['Orders placed',s.orders],['Processing',count('order','processing')],['Completed',count('order','completed')],['Cancelled',count('order','cancelled')]]);
        else addCards([['Payments received',money(report.financial.collected)],['Refunds completed',money(report.financial.refunded)],['Net collections',money(report.financial.net)]]);
        for(const [kind,key,heading]of [['appointments','appointment','Appointment statuses'],['consultations','consultation','Consultation statuses'],['treatments','treatment','Treatment statuses'],['followups','followup','Follow-up task statuses']])if(type==='overview'||type===kind)statusPanel(heading,statusesFor(key));
        if(['overview','consultations'].includes(type))trend(report.daily);
        if(type==='prescriptions'){
            const rows=(report.medications||[]).map(item=>({status:item.name,count:item.count}));
            statusPanel('Medication names · top 20',rows);
        }
        if(admin && ['overview','collections'].includes(type) && report.financial)collections(report.financial);
        if(admin && ['overview','orders'].includes(type) && report.order_statuses)statusPanel('Shop order statuses',report.order_statuses);
        get('report-definition').textContent=notes[type];
        if(type==='overview'&&!report.financial)get('report-definition').textContent=notes.overview.split(' Collections use')[0];
    }
    async function load() {
        if(!ready||!get('report-filters').reportValidity())return;
        const seq=++version;data=null;exportRows=[];get('report-export').disabled=get('report-print').disabled=true;
        get('report-results').hidden=true;get('report-retry').hidden=true;get('report-message').textContent='Preparing report…';
        const type=get('report-type').value, from=get('report-from').value,to=get('report-to').value;
        if(from>to){get('report-message').textContent='From date must be before or equal to To date.';return;}
        const query=new URLSearchParams({report_type:type,date_from:from,date_to:to});
        for(const [id,key]of [['report-status','status'],['report-vet','veterinarian_id'],['report-method','payment_method'],['report-source','payment_source'],['report-shipping','shipping_method'],['report-medication','medication']]){
            if(!get(`${id}-field`).hidden && get(id).value.trim())query.set(key,get(id).value.trim());
        }
        try{
            const report=await request(`/reports?${query}`);
            if(seq!==version)return;
            data=report;render(report);get('report-results').hidden=false;get('report-export').disabled=get('report-print').disabled=false;
            get('report-message').textContent='Report ready. Print or export the filtered results below.';
        }catch(error){if(seq!==version)return;get('report-message').textContent=error.message;get('report-retry').hidden=false;}
    }
    function csv() {
        if(!data)return;
        const rows=[[title()],['Clinic',data.clinic_name],['From',data.date_from],['To',data.date_to],['Filters',filterDescription(data)],['Prepared by',data.prepared_by],['Generated at (UTC)',data.generated_at],...exportRows,[],['Notes',get('report-definition').textContent]];
        const escape=value=>{let text=String(value??'');if(/^\s*[=+@\t\r]/.test(text)||(/^\s*-/.test(text)&&!/^-[0-9]+(?:\.[0-9]+)?$/.test(text)))text="'"+text;return '"'+text.replaceAll('"','""')+'"';};
        const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row=>row.map(escape).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
        const a=node('a');a.href=url;a.download=`vetdental-${data.report_type}-${data.date_from}-${data.date_to}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    get('report-filters').addEventListener('submit',event=>{event.preventDefault();load();});
    get('report-type').addEventListener('change',configure);
    for(const id of ['report-from','report-to','report-status','report-vet','report-method','report-source','report-shipping','report-medication']){
        get(id).addEventListener('input',invalidate);get(id).addEventListener('change',invalidate);
    }
    get('report-title').addEventListener('input',updateTitle);
    get('report-export').addEventListener('click',csv);
    get('report-print').addEventListener('click',()=>{if(data){updateTitle();window.print();}});
    // Also update the title when the browser's own Print command is used.
    window.addEventListener('beforeprint',()=>{if(data)updateTitle();});
    document.querySelectorAll('[data-report-period]').forEach(button=>button.addEventListener('click',()=>{dates(button.dataset.reportPeriod);load();}));
    get('report-retry').addEventListener('click',()=>ready?load():initialize());
    async function initialize() {
        try{
            if(admin){const profile=await request('/admins/me');if(profile.user.role!=='clinic_administrator')throw new Error('A clinic administrator account is required.');get('topbar-name').textContent=profile.user.full_name;get('topbar-avatar').textContent=Array.from(profile.user.full_name.trim())[0];}
            else if(!await vetReady)return;
            if(admin){const options=await request('/reports/filters');for(const vet of options.veterinarians)get('report-vet').add(new Option(vet.name,vet.id));}
            ready=true;dates('month');configure();load();
        }catch(error){get('report-message').textContent=error.message;get('report-retry').hidden=false;}
    }
    if(admin)get('logout-button').addEventListener('click',()=>{sessionStorage.removeItem('vetdental_staff_token');location.replace('/web/');});
    initialize();
})();
