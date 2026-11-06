(() => {
    const get=id=>document.getElementById(id);
    const admin=document.body.dataset.reportRole==='admin';
    let currentReport=null, version=0, ready=false;
    const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
    const money=value=>new Intl.NumberFormat('en-MY',{style:'currency',currency:'MYR'}).format(Number(value));
    const label=value=>({shop:'Shop',consultation_balance:'Consultation balances',booking_deposit:'Booking deposits',online_banking:'FPX',card:'Card',cash:'Cash',in_progress:'In progress',pending_payment:'Awaiting payment',no_show:'No-show'}[value] || value.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()));
    function today(){const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kuala_Lumpur',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const pick=type=>parts.find(p=>p.type===type).value;return `${pick('year')}-${pick('month')}-${pick('day')}`;}
    function dates(mode){const end=today();get('report-to').value=end;get('report-from').value=mode==='today'?end:mode==='year'?`${end.slice(0,4)}-01-01`:`${end.slice(0,7)}-01`;}
    async function request(path){
        if(!admin)return vetRequest(path);
        const token=sessionStorage.getItem('vetdental_staff_token');
        if(!token){location.replace('/web/');throw new Error('Please log in again.');}
        const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),20000);
        try{
            const response=await fetch(path,{headers:{Accept:'application/json',Authorization:`Bearer ${token}`},credentials:'omit',cache:'no-store',signal:controller.signal});
            if(response.status===401){sessionStorage.removeItem('vetdental_staff_token');location.replace('/web/');throw new Error('Your session has expired.');}
            let data;try{data=await response.json();}catch(_){throw new Error(`Unexpected server response (HTTP ${response.status}).`);}
            if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Could not load this report.');
            return data;
        }catch(error){if(error.name==='AbortError'||error instanceof TypeError)throw new Error('Cannot reach the server. Please try again.');throw error;}
        finally{clearTimeout(timeout);}
    }
    function cards(container,items){
        container.replaceChildren();
        for(const [title,value] of items){const card=node('article',undefined,'report-stat');card.append(node('span',title),node('strong',value));container.appendChild(card);}
    }
    function statuses(container,rows){
        container.replaceChildren();
        if(!rows.length){container.appendChild(node('p','No records in this period.','muted'));return;}
        const total=rows.reduce((sum,r)=>sum+r.count,0);
        for(const item of rows){const row=node('div',undefined,'report-status-row');const heading=node('div');heading.append(node('span',label(item.status)),node('strong',item.count));const track=node('div',undefined,'report-track');const bar=node('span');bar.style.width=`${100*item.count/Math.max(total,1)}%`;track.appendChild(bar);row.append(heading,track);container.appendChild(row);}
    }
    function chart(days){
        const chart=get('report-chart');chart.replaceChildren();
        const monthly=days.length>62;const grouped=new Map();
        for(const day of days){const key=monthly?day.date.slice(0,7):day.date;grouped.set(key,(grouped.get(key)||0)+day.consultations);}
        const max=Math.max(1,...grouped.values());
        for(const [date,value] of grouped){const column=node('div',undefined,'report-chart-column');const bar=node('div',undefined,'report-chart-bar');bar.style.height=`${value/max*150}px`;bar.title=`${date}: ${value} completed consultation(s)`;const caption=node('small',monthly?date.slice(5):date.slice(8));column.append(node('strong',value),bar,caption);chart.appendChild(column);}
        get('report-chart-caption').textContent=monthly?'Completed consultations by month (within the selected dates).':'Completed consultations by day of month. Dates use Malaysia time.';
    }
    function render(data){
        const s=data.summary;
        cards(get('report-clinical-cards'),[['Appointments',s.appointments],['Completed consultations',s.completed_consultations],['Unique patients',s.patients],['Treatments recorded',s.treatments]]);
        get('report-clinical-extra').textContent=`${s.prescriptions} prescription(s) recorded · ${s.followups_due} follow-up task(s) due in this period`;
        for(const [id,rows] of [['appointments',data.appointment_statuses],['consultations',data.consultation_statuses],['treatments',data.treatment_statuses],['followups',data.followup_statuses]])statuses(get(`report-${id}`),rows);
        chart(data.daily);
        if(admin){
            const f=data.financial;
            cards(get('report-financial-cards'),[['Payments received',money(f.collected)],['Refunds completed',money(f.refunded)],['Net collections',money(f.net)]]);
            get('report-financial-rows').replaceChildren();
            for(const item of f.breakdown){const row=node('tr');for(const value of [label(item.source),label(item.method),money(item.collected),money(item.refunded),money(item.net)])row.appendChild(node('td',value));get('report-financial-rows').appendChild(row);}
            get('report-financial-empty').hidden=!!f.breakdown.length;
            statuses(get('report-orders'),data.order_statuses);
            get('report-order-total').textContent=`${s.orders} order(s) placed in this period`;
        }
    }
    async function load(){
        if(!ready || !get('report-filters').reportValidity())return;
        const from=get('report-from').value,to=get('report-to').value;
        const seq=++version;currentReport=null;get('report-export').disabled=true;get('report-results').hidden=true;get('report-retry').hidden=true;
        get('report-message').textContent='Preparing report…';
        if(from>to){get('report-message').textContent='From date must be before or equal to To date.';return;}
        try{
            const data=await request(`/reports?${new URLSearchParams({date_from:from,date_to:to})}`);
            if(seq!==version)return;
            currentReport=data;render(data);get('report-results').hidden=false;get('report-export').disabled=false;
            get('report-message').textContent=`Report for ${data.date_from} to ${data.date_to} · Malaysia time`;
        }catch(error){if(seq!==version)return;get('report-message').textContent=error.message;get('report-retry').hidden=false;}
    }
    function exportCSV(){
        if(!currentReport)return;
        const d=currentReport;const rows=[['VetDental report'],['From',d.date_from],['To',d.date_to],['Scope',admin?'Clinic':'Signed-in veterinarian'],[],['Metric','Count']];
        for(const [key,value]of Object.entries(d.summary))rows.push([label(key),value]);
        for(const [title,items]of [['Appointment statuses',d.appointment_statuses],['Consultation statuses',d.consultation_statuses],['Treatment statuses',d.treatment_statuses],['Follow-up statuses',d.followup_statuses],['Order statuses',d.order_statuses||[]]]){rows.push([], [title,'Count']);for(const item of items)rows.push([label(item.status),item.count]);}
        rows.push([],['Date (MYT)','Completed consultations']);for(const item of d.daily)rows.push([item.date,item.consultations]);
        if(admin){rows.push([],['Source','Method','Received MYR','Refunded MYR','Net MYR']);for(const item of d.financial.breakdown)rows.push([label(item.source),label(item.method),item.collected,item.refunded,item.net]);rows.push(['Total','',d.financial.collected,d.financial.refunded,d.financial.net]);}
        rows.push([],['Clinical notes','Appointment dates are scheduled dates. Consultations use recorded dates. Treatments and prescriptions include finalized consultations only. Follow-up counts use recommended dates. Statuses are current.']);
        if(admin)rows.push([],['Collection notes','Collections are completed ledger entries, including booking deposits. Deposit credits are not counted again. Refunds use their completion date. Delivery fees are included; gateway fees are not deducted. This is not a profit report.']);
        const escape=value=>{let text=String(value??'');if(/^[=+@\t\r]/.test(text)||(/^[-]/.test(text)&&!/^-[0-9]+(?:\.[0-9]+)?$/.test(text)))text="'"+text;return '"'+text.replaceAll('"','""')+'"';};
        const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(row=>row.map(escape).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
        const a=node('a');a.href=url;a.download=`vetdental-${admin?'clinic':'vet'}-report-${d.date_from}-${d.date_to}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    get('report-filters').addEventListener('submit',event=>{event.preventDefault();load();});
    for(const id of ['report-from','report-to'])get(id).addEventListener('input',()=>{version++;currentReport=null;get('report-export').disabled=true;get('report-results').hidden=true;get('report-message').textContent='Dates changed. Select Generate report to update.';});
    document.querySelectorAll('[data-report-period]').forEach(button=>button.addEventListener('click',()=>{dates(button.dataset.reportPeriod);load();}));
    get('report-export').addEventListener('click',exportCSV);
    get('report-retry').addEventListener('click',()=>ready?load():initialize());
    async function initialize(){
        try{
            if(admin){const profile=await request('/admins/me');if(profile.user.role!=='clinic_administrator')throw new Error('A clinic administrator account is required.');get('topbar-name').textContent=profile.user.full_name;get('topbar-avatar').textContent=Array.from(profile.user.full_name.trim())[0];}
            else{const profile=await vetReady;if(!profile)return;}
            ready=true;dates('month');load();
        }catch(error){get('report-message').textContent=error.message;get('report-retry').hidden=false;}
    }
    if(admin)get('logout-button').addEventListener('click',()=>{sessionStorage.removeItem('vetdental_staff_token');location.replace('/web/');});
    initialize();
})();
