
(() => {
    const get = id => document.getElementById(id);
    const admin = document.body.dataset.reportRole === 'admin';

    const names = {
        overview: 'Clinic activity report',
        appointments: 'Appointment report',
        consultations: 'Consultation report',
        treatments: 'Treatment report',
        prescriptions: 'Prescription report',
        followups: 'Follow-up care report',
        collections: 'Payment collections report',
        orders: 'Shop order report'
    };

    if (!admin) {
        names.overview = 'My clinical activity report';
    }

    const statuses = {
        appointments: [
            'pending', 'pending_payment', 'confirmed', 'in_progress',
            'completed', 'cancelled', 'rejected', 'no_show'
        ],
        consultations: ['draft', 'completed'],
        treatments: ['planned', 'in_progress', 'completed', 'cancelled'],
        followups: ['pending', 'completed', 'cancelled'],
        orders: [
            'pending_payment', 'pending', 'paid', 'processing',
            'ready_for_pickup', 'shipped', 'completed', 'cancelled',
            'refunded', 'expired'
        ]
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

    let ready = false;
    let version = 0;
    let data = null;
    let exportRows = [];

    const node = (tag, text, cls) => {
        const e = document.createElement(tag);

        if (text !== undefined) {
            e.textContent = text;
        }

        if (cls) {
            e.className = cls;
        }

        return e;
    };

    const money = value => new Intl.NumberFormat('en-MY', {
        style: 'currency',
        currency: 'MYR'
    }).format(Number(value));

    const label = value => ({
        online_banking: 'FPX',
        card: 'Card',
        cash: 'Cash',
        shop: 'Shop',
        consultation_balance: 'Consultation balances',
        booking_deposit: 'Booking deposits',
        no_show: 'No-show',
        pending_payment: 'Awaiting payment'
    }[value] || String(value).replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()));

    function today() {
        const parts = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'Asia/Kuala_Lumpur',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(new Date());

        const pick = name => parts.find(part => part.type === name).value;

        return `${pick('year')}-${pick('month')}-${pick('day')}`;
    }

    const displayDate = value => value.split('-').reverse().join('/');

    function dates(mode) {
        const end = today();

        get('report-to').value = end;

        get('report-from').value = mode === 'today'
            ? end
            : mode === 'year'
                ? `${end.slice(0, 4)}-01-01`
                : `${end.slice(0, 7)}-01`;
    }

    async function request(path) {
        if (!admin) {
            return vetRequest(path);
        }

        const token = sessionStorage.getItem('vetdental_staff_token');

        if (!token) {
            location.replace('/web/');
            throw new Error('Please log in again.');
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);

        try {
            const response = await fetch(path, {
                headers: {
                    Accept: 'application/json',
                    Authorization: `Bearer ${token}`
                },
                credentials: 'omit',
                cache: 'no-store',
                signal: controller.signal
            });

            if (response.status === 401) {
                sessionStorage.removeItem('vetdental_staff_token');
                location.replace('/web/');
                throw new Error('Your session has expired.');
            }

            let json;

            try {
                json = await response.json();
            } catch (_) {
                throw new Error(`Unexpected server response (HTTP ${response.status}).`);
            }

            if (!response.ok) {
                throw new Error(
                    typeof json.detail === 'string'
                        ? json.detail
                        : 'Could not load the report.'
                );
            }

            return json;

        } catch (error) {
            if (error.name === 'AbortError' || error instanceof TypeError) {
                throw new Error('Cannot reach the server. Please try again.');
            }

            throw error;

        } finally {
            clearTimeout(timeout);
        }
    }

    function invalidate() {
        version++;
        data = null;
        exportRows = [];

        get('report-export').disabled = get('report-print').disabled = true;
        get('report-results').hidden = true;
        get('report-retry').hidden = true;

        get('report-message').textContent =
            'Filters changed. Generate the report to update the results.';
    }

    function configure() {
        const type = get('report-type').value;
        const status = get('report-status');

        status.replaceChildren(new Option('All statuses', ''));

        for (const value of statuses[type] || []) {
            status.add(new Option(label(value), value));
        }

        get('report-status-field').hidden = !statuses[type];
        get('report-vet-field').hidden = !admin || ['collections', 'orders'].includes(type);
        get('report-method-field').hidden = get('report-source-field').hidden = type !== 'collections';
        get('report-shipping-field').hidden = type !== 'orders';
        get('report-medication-field').hidden = type !== 'prescriptions';
        get('report-title').placeholder = names[type];

        invalidate();
    }

    function title() {
        return get('report-title').value.trim()
            || names[data?.report_type || get('report-type').value];
    }

    function updateTitle() {
        if (data) {
            get('report-document-title').textContent = title();
            if (get('report-cover-title')) {
                get('report-cover-title').textContent = title();
            }
        }
    }

    function renderCover(report) {
        get('report-cover')?.remove();
        const cover = node('section', undefined, 'report-cover');
        cover.id = 'report-cover';
        cover.setAttribute('aria-labelledby', 'report-cover-title');

        const brand = node('div', undefined, 'report-cover-brand');
        brand.append(node('strong', 'VetDental'), node('span', 'VETERINARY DENTAL CARE'));

        const heading = node('div', undefined, 'report-cover-heading');
        const reportTitle = node('h2', title());
        reportTitle.id = 'report-cover-title';
        heading.append(node('p', names[report.report_type], 'report-cover-eyebrow'),
            reportTitle, node('p', report.clinic_name, 'report-cover-clinic'));

        const details = node('dl', undefined, 'report-cover-details');
        for (const [term, value] of [
            ['Reporting period', `${displayDate(report.date_from)} - ${displayDate(report.date_to)}`],
            ['Applied filters', filterDescription(report)],
            ['Prepared by', report.prepared_by],
            ['Generated', new Date(report.generated_at).toLocaleString('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur', dateStyle: 'medium', timeStyle: 'short'
            }) + ' MYT']
        ]) {
            const item = node('div');
            item.append(node('dt', term), node('dd', value));
            details.appendChild(item);
        }

        const footer = node('div', undefined, 'report-cover-footer');
        footer.append(node('span', 'Charts, detailed figures and explanations'),
            node('span', 'Confidential | For authorised use'));
        cover.append(brand, heading, details, footer);
        get('report-results').prepend(cover);
    }

    function addCards(items) {
        const container = get('report-cards');
        container.replaceChildren();

        exportRows.push([], ['Metric', 'Value']);

        for (const [text, value] of items) {
            const card = node('article', undefined, 'report-stat');

            card.append(
                node('span', text),
                node('strong', value)
            );

            container.appendChild(card);
            exportRows.push([text, value]);
        }
    }

    function detailTable(headers, rows, caption) {
        const scroll = node('div', undefined, 'table-scroll report-detail-scroll');
        const table = node('table', undefined, 'staff-table report-detail-table');

        table.appendChild(node('caption', caption));

        const head = node('thead');
        const heading = node('tr');

        for (const text of headers) {
            const cell = node('th', text);
            cell.scope = 'col';
            heading.appendChild(cell);
        }

        head.appendChild(heading);
        table.appendChild(head);

        const body = node('tbody');

        for (const values of rows) {
            const row = node('tr');

            for (const value of values) {
                row.appendChild(node('td', value));
            }

            body.appendChild(row);
        }

        if (!rows.length) {
            const row = node('tr');
            const cell = node('td', 'No matching records.');

            cell.colSpan = headers.length;
            row.appendChild(cell);
            body.appendChild(row);
        }

        table.appendChild(body);
        scroll.appendChild(table);

        return scroll;
    }

    function explanation(section, text) {
        section.appendChild(node('p', text, 'report-explanation'));
    }

    const reportPalette = [
        '#2549c7', '#168879', '#8960c5',
        '#c07729', '#5c7ea5', '#b64960'
    ];

    function categoryColor(status, index) {
        return ({
            completed: '#168879',
            confirmed: '#2549c7',
            paid: '#168879',
            in_progress: '#8960c5',
            pending: '#c07729',
            pending_payment: '#c07729',
            planned: '#5c7ea5',
            draft: '#5c7ea5',
            cancelled: '#b64960',
            rejected: '#b64960',
            refunded: '#c07729',
            expired: '#7a8597'
        })[status] || reportPalette[index % reportPalette.length];
    }

    function reportSVG(tag, attrs = {}, text) {
        const e = document.createElementNS('http://www.w3.org/2000/svg', tag);

        for (const [key, value] of Object.entries(attrs)) {
            e.setAttribute(key, String(value));
        }

        if (text !== undefined) {
            e.textContent = text;
        }

        return e;
    }

    function distributionRing(rows, total) {
        const wrapper = node('div', undefined, 'report-distribution');

        const svg = reportSVG('svg', {
            viewBox: '0 0 180 180',
            role: 'img',
            'aria-label': `Distribution of ${total} filtered records. Exact counts and percentages follow.`
        });

        svg.appendChild(reportSVG('circle', {
            cx: 90,
            cy: 90,
            r: 67,
            fill: 'none',
            stroke: '#e9edf6',
            'stroke-width': 17
        }));

        const circumference = 2 * Math.PI * 67;
        let offset = 0;

        rows.forEach((item, index) => {
            const length = total ? item.count / total * circumference : 0;

            if (length > 0) {
                const arc = reportSVG('circle', {
                    cx: 90,
                    cy: 90,
                    r: 67,
                    fill: 'none',
                    stroke: categoryColor(item.status, index),
                    'stroke-width': 17,
                    'stroke-dasharray': `${length} ${circumference - length}`,
                    'stroke-dashoffset': -offset,
                    transform: 'rotate(-90 90 90)'
                });

                arc.appendChild(reportSVG(
                    'title',
                    {},
                    `${label(item.status)}: ${item.count}`
                ));

                svg.appendChild(arc);
            }

            offset += length;
        });

        svg.appendChild(reportSVG('text', {
            x: 90,
            y: 91,
            'text-anchor': 'middle',
            fill: '#172333',
            'font-size': 34,
            'font-weight': 700
        }, String(total)));

        svg.appendChild(reportSVG('text', {
            x: 90,
            y: 112,
            'text-anchor': 'middle',
            fill: '#65748c',
            'font-size': 11
        }, 'FILTERED RECORDS'));

        wrapper.append(
            svg,
            node('span', 'Status distribution', 'report-chart-eyebrow')
        );

        return wrapper;
    }

    function statusPanel(title, rows, options = {}) {
        const section = node('section', undefined, 'report-section report-wide');
        section.appendChild(node('h3', title));

        const total = options.total
            ?? rows.reduce((sum, item) => sum + item.count, 0);

        const category = options.medication ? 'Medication' : 'Status';
        const name = item => options.medication ? item.status : label(item.status);

        exportRows.push([], [title, 'Count', 'Share of filtered records']);

        const chart = node('div', undefined, 'report-status-chart');
        chart.setAttribute('role', 'group');
        chart.setAttribute('aria-label', title);

        for (const [index, item] of rows.entries()) {
            const share = total ? 100 * item.count / total : 0;

            const line = node('div', undefined, 'report-status-row');
            const heading = node('div');

            heading.append(
                node('span', name(item)),
                node('strong', `${item.count} (${share.toFixed(1)}%)`)
            );

            const track = node('div', undefined, 'report-track');
            const bar = node('span');

            bar.style.width = `${share}%`;
            bar.style.backgroundColor = categoryColor(
                options.medication ? 'medication' : item.status,
                index
            );

            track.appendChild(bar);

            line.style.setProperty(
                '--report-category',
                categoryColor(
                    options.medication ? 'medication' : item.status,
                    index
                )
            );

            line.append(heading, track);
            chart.appendChild(line);

            exportRows.push([
                name(item),
                item.count,
                `${share.toFixed(1)}%`
            ]);
        }

        const visual = node('div', undefined, 'report-status-visual');

        if (rows.length) {
            if (!options.medication) {
                visual.appendChild(distributionRing(rows, total));
            }

            visual.appendChild(chart);
        }

        const layout = node('div', undefined, 'report-figure-layout');

        layout.appendChild(visual);

        layout.appendChild(detailTable(
            [category, 'Count', 'Share'],
            rows.map(item => [
                name(item),
                item.count,
                total ? `${(100 * item.count / total).toFixed(1)}%` : '0.0%'
            ]),
            `${title} — detailed figures`
        ));

        section.appendChild(layout);

        let text = 'No matching records were found for these dates and filters.';

        if (rows.length && total) {
            const highest = Math.max(...rows.map(item => item.count));
            const leaders = rows.filter(item => item.count === highest).map(name);

            text = `${total} record(s) match the current filters. `;

            text += leaders.length === 1
                ? `${leaders[0]} is the largest category: ${highest} record(s), ${(100 * highest / total).toFixed(1)}%. `
                : `${leaders.length} categories share the highest count of ${highest} each. `;

            text += options.medication
                ? 'The chart and table show up to 20 medication names; percentages use all matching prescriptions.'
                : 'Percentages use the filtered total. Statuses show their current state, not their historical state on the visit date.';
        }

        explanation(section, text);
        get('report-sections').appendChild(section);

        exportRows.push([], ['Explanation', text]);
    }

    function trend(days) {
        const section = node('section', undefined, 'report-section report-wide');
        section.appendChild(node('h3', 'Completed consultation trend'));

        // Use one bucket list for the chart, table, explanation and CSV.
        const buckets = [];

        const monthly = days.length > 93;
        const weekly = days.length > 31 && !monthly;

        for (let i = 0; i < days.length; i++) {
            const day = days[i];

            const key = monthly
                ? day.date.slice(0, 7)
                : weekly
                    ? String(Math.floor(i / 7))
                    : day.date;

            let bucket = buckets[buckets.length - 1];

            if (!bucket || bucket.key !== key) {
                bucket = {
                    key,
                    start: day.date,
                    end: day.date,
                    count: 0
                };

                buckets.push(bucket);
            }

            bucket.end = day.date;
            bucket.count += day.consultations;
        }

        const period = bucket => monthly
            ? bucket.key
            : weekly
                ? `${bucket.start} – ${bucket.end}`
                : bucket.start;

        const ns = 'http://www.w3.org/2000/svg';

        const svgNode = (tag, attrs = {}, text) => {
            const e = document.createElementNS(ns, tag);

            for (const [key, value] of Object.entries(attrs)) {
                e.setAttribute(key, String(value));
            }

            if (text !== undefined) {
                e.textContent = text;
            }

            return e;
        };

        const svg = svgNode('svg', {
            viewBox: '0 0 960 280',
            role: 'img',
            'aria-label': 'Completed consultations by ' + (
                monthly ? 'month' : weekly ? 'seven-day period' : 'day'
            )
        });

        svg.appendChild(svgNode(
            'title',
            {},
            'Completed consultations in the selected period. Exact counts appear in the table below.'
        ));

        const defs = svgNode('defs');

        const gradient = svgNode('linearGradient', {
            id: 'report-trend-gradient',
            x1: 0,
            y1: 0,
            x2: 0,
            y2: 1
        });

        gradient.append(
            svgNode('stop', {
                offset: '0%',
                'stop-color': '#2549c7'
            }),
            svgNode('stop', {
                offset: '100%',
                'stop-color': '#8ca7f3'
            })
        );

        defs.appendChild(gradient);
        svg.appendChild(defs);

        svg.appendChild(svgNode('rect', {
            x: 54,
            y: 28,
            width: 878,
            height: 182,
            rx: 12,
            fill: '#f5f7fd'
        }));

        const maximum = Math.max(1, ...buckets.map(bucket => bucket.count));
        const axisStep = Math.max(1, Math.ceil(maximum / 4));
        const axisMax = axisStep * 4;
        const step = 860 / Math.max(1, buckets.length);

        for (let tick = 0; tick <= 4; tick++) {
            const y = 210 - tick * 42;

            svg.appendChild(svgNode('line', {
                x1: 55,
                y1: y,
                x2: 930,
                y2: y,
                stroke: '#dce3f0',
                'stroke-width': 1,
                'stroke-dasharray': '3 5'
            }));

            svg.appendChild(svgNode(
                'text',
                {
                    x: 45,
                    y: y + 4,
                    'text-anchor': 'end',
                    fill: '#536580',
                    'font-size': 11
                },
                String(axisStep * tick)
            ));
        }

        buckets.forEach((bucket, index) => {
            const x = 60 + index * step;
            const height = bucket.count / axisMax * 168;

            const width = Math.min(step * .64, 46);
            const peak = bucket.count > 0 && bucket.count === maximum;

            const bar = svgNode('rect', {
                x: x + (step - width) / 2,
                y: 210 - height,
                width,
                height,
                fill: peak ? '#2549c7' : 'url(#report-trend-gradient)',
                rx: 5,
                class: 'report-trend-bar'
            });

            bar.appendChild(svgNode(
                'title',
                {},
                `${period(bucket)}: ${bucket.count} completed consultations`
            ));

            svg.appendChild(bar);

            svg.appendChild(svgNode(
                'text',
                {
                    x: x + step / 2,
                    y: Math.max(25, 203 - height),
                    'text-anchor': 'middle',
                    fill: '#172333',
                    'font-size': 11
                },
                String(bucket.count)
            ));

            if (
                index % Math.ceil(buckets.length / 10) === 0
                || index === buckets.length - 1
            ) {
                const dateLabel = monthly
                    ? bucket.key
                    : bucket.start.slice(5);

                svg.appendChild(svgNode(
                    'text',
                    {
                        x: x + step / 2,
                        y: 235,
                        'text-anchor': 'middle',
                        fill: '#536580',
                        'font-size': 11
                    },
                    dateLabel
                ));
            }
        });

        svg.appendChild(svgNode(
            'text',
            {
                x: 480,
                y: 268,
                'text-anchor': 'middle',
                fill: '#536580',
                'font-size': 12
            },
            monthly
                ? 'Month (MYT)'
                : weekly
                    ? 'Seven-day period start (MYT)'
                    : 'Date (MM-DD, MYT)'
        ));

        const highlights = node('div', undefined, 'report-chart-highlights');

        const totalCount = buckets.reduce(
            (sum, bucket) => sum + bucket.count,
            0
        );

        for (const [caption, value] of [
            ['Completed', totalCount],
            ['Highest period', Math.max(0, ...buckets.map(bucket => bucket.count))],
            ['Days with activity', days.filter(day => day.consultations > 0).length]
        ]) {
            const chip = node('div');

            chip.append(
                node('span', caption),
                node('strong', value)
            );

            highlights.appendChild(chip);
        }

        section.appendChild(highlights);

        const chart = node('div', undefined, 'report-vector-chart');
        chart.appendChild(svg);
        section.appendChild(chart);

        const rows = buckets.map(bucket => [
            period(bucket),
            bucket.count
        ]);

        section.appendChild(detailTable(
            ['Period (MYT)', 'Completed consultations'],
            rows,
            'Consultation trend — exact counts'
        ));

        const total = buckets.reduce(
            (sum, bucket) => sum + bucket.count,
            0
        );

        let text = `${total} completed consultation(s) were recorded across ${days.length} selected day(s). `;

        if (total) {
            const peak = Math.max(...buckets.map(bucket => bucket.count));
            const peaks = buckets.filter(bucket => bucket.count === peak);

            text += peaks.length === 1
                ? `The highest count was ${peak} in ${period(peaks[0])}. `
                : `${peaks.length} periods share the highest count of ${peak}. `;
        }

        text += monthly
            ? 'Both the chart and table use monthly buckets, clipped to the selected dates.'
            : weekly
                ? 'Both the chart and table use consecutive seven-day buckets starting on the selected From date; the last may be shorter.'
                : 'Both the chart and table show daily counts, including days with no completed consultations.';

        explanation(section, text);
        get('report-sections').appendChild(section);

        exportRows.push(
            [],
            ['Period (MYT)', 'Completed consultations'],
            ...rows,
            [],
            ['Trend explanation', text]
        );
    }

    function collections(finance) {
        const section = node('section', undefined, 'report-section report-wide');
        section.appendChild(node('h3', 'Collections by source and method'));

        const sources = new Map();

        for (const row of finance.breakdown) {
            const source = sources.get(row.source) || {
                received: 0,
                refunded: 0
            };

            source.received += Math.round(Number(row.collected) * 100);
            source.refunded += Math.round(Number(row.refunded) * 100);

            sources.set(row.source, source);
        }

        const max = Math.max(
            1,
            ...[...sources.values()].flatMap(value => [
                value.received,
                value.refunded
            ])
        );

        const chart = node('div', undefined, 'report-collection-chart');

        chart.setAttribute('role', 'group');
        chart.setAttribute('aria-label', 'Payments received and refunds by source');

        for (const [source, amount] of sources) {
            const group = node('div', undefined, 'report-collection-group');
            group.appendChild(node('h4', label(source)));

            for (const [key, text] of [
                ['received', 'Received'],
                ['refunded', 'Refunded']
            ]) {
                const line = node('div', undefined, 'report-status-row');
                const heading = node('div');

                heading.append(
                    node('span', text),
                    node('strong', money(amount[key] / 100))
                );

                const track = node('div', undefined, 'report-track');
                const bar = node('span');

                bar.className = key === 'refunded' ? 'report-refund-bar' : '';
                bar.style.width = `${100 * amount[key] / max}%`;

                track.appendChild(bar);
                line.append(heading, track);
                group.appendChild(line);
            }

            chart.appendChild(group);
        }

        if (sources.size) {
            const legend = node('div', undefined, 'report-chart-legend');

            legend.append(
                node('span', 'Payments received', 'report-legend-received'),
                node('span', 'Completed refunds', 'report-legend-refunded')
            );

            section.append(legend, chart);
        }

        const rows = finance.breakdown.map(row => [
            label(row.source),
            label(row.method),
            money(row.collected),
            money(row.refunded),
            money(row.net)
        ]);

        rows.push([
            'Total',
            'All selected methods',
            money(finance.collected),
            money(finance.refunded),
            money(finance.net)
        ]);

        section.appendChild(detailTable(
            ['Source', 'Method', 'Received', 'Refunded', 'Net'],
            rows,
            'Collection details — MYR'
        ));

        const text = `Payments received total ${money(finance.collected)} and completed refunds total ${money(finance.refunded)}, leaving net collections of ${money(finance.net)}. The chart compares received and refunded amounts by source on one shared scale; the table splits each source by payment method. Refunds can relate to earlier payments, so a period’s net collections may be negative. Deposits are included once when received. These figures are not profit; gateway fees are not deducted.`;

        explanation(section, text);
        get('report-sections').appendChild(section);

        exportRows.push(
            [],
            ['Source', 'Method', 'Received MYR', 'Refunded MYR', 'Net MYR']
        );

        for (const row of finance.breakdown) {
            exportRows.push([
                label(row.source),
                label(row.method),
                row.collected,
                row.refunded,
                row.net
            ]);
        }

        exportRows.push(
            ['Total', '', finance.collected, finance.refunded, finance.net],
            [],
            ['Collections explanation', text]
        );
    }

    function filterDescription(report) {
        const values = [];

        if (!['collections', 'orders'].includes(report.report_type)) {
            values.push(report.filters.veterinarian);
        }

        for (const [key, prefix] of [
            ['status', 'Status'],
            ['payment_method', 'Method'],
            ['payment_source', 'Source'],
            ['shipping_method', 'Fulfilment'],
            ['medication', 'Medication']
        ]) {
            if (report.filters[key]) {
                values.push(`${prefix}: ${label(report.filters[key])}`);
            }
        }

        return values.filter(Boolean).join(' · ')
            || 'All records in the selected period';
    }

    function render(report) {
        const type = report.report_type;
        const s = report.summary;
        const statusesFor = key => report[`${key}_statuses`] || [];

        const count = (key, status) =>
            statusesFor(key).find(row => row.status === status)?.count || 0;

        exportRows = [];

        get('report-sections').replaceChildren();
        get('report-clinic-name').textContent = report.clinic_name;

        updateTitle();

        get('report-document-period').textContent =
            `${displayDate(report.date_from)} – ${displayDate(report.date_to)} · Malaysia time`;

        get('report-document-filters').textContent = filterDescription(report);

        get('report-document-prepared').textContent =
            `Prepared by ${report.prepared_by} · ${new Date(report.generated_at).toLocaleString('en-MY', {
                timeZone: 'Asia/Kuala_Lumpur',
                dateStyle: 'medium',
                timeStyle: 'short'
            })} MYT`;

        if (type === 'overview') {
            addCards([
                ['Appointments', s.appointments],
                ['Completed consultations', s.completed_consultations],
                ['Unique patients', s.patients],
                ['Treatments recorded', s.treatments]
            ]);

        } else if (type === 'appointments') {
            addCards([
                ['Appointments', s.appointments],
                ['Confirmed', count('appointment', 'confirmed')],
                ['In progress', count('appointment', 'in_progress')],
                ['Completed', count('appointment', 'completed')]
            ]);

        } else if (type === 'consultations') {
            addCards([
                ['Consultations', statusesFor('consultation').reduce((sum, x) => sum + x.count, 0)],
                ['Draft', count('consultation', 'draft')],
                ['Completed', s.completed_consultations]
            ]);

        } else if (type === 'treatments') {
            addCards([
                ['Treatments', s.treatments],
                ['Planned', count('treatment', 'planned')],
                ['In progress', count('treatment', 'in_progress')],
                ['Completed', count('treatment', 'completed')]
            ]);

        } else if (type === 'prescriptions') {
            addCards([
                ['Prescriptions', s.prescriptions]
            ]);

        } else if (type === 'followups') {
            addCards([
                ['Follow-up tasks due', s.followups_due],
                ['Pending', count('followup', 'pending')],
                ['Completed', count('followup', 'completed')],
                ['Cancelled', count('followup', 'cancelled')]
            ]);

        } else if (type === 'orders') {
            addCards([
                ['Orders placed', s.orders],
                ['Processing', count('order', 'processing')],
                ['Completed', count('order', 'completed')],
                ['Cancelled', count('order', 'cancelled')]
            ]);

        } else {
            addCards([
                ['Payments received', money(report.financial.collected)],
                ['Refunds completed', money(report.financial.refunded)],
                ['Net collections', money(report.financial.net)]
            ]);
        }

        for (const [kind, key, heading] of [
            ['appointments', 'appointment', 'Appointment statuses'],
            ['consultations', 'consultation', 'Consultation statuses'],
            ['treatments', 'treatment', 'Treatment statuses'],
            ['followups', 'followup', 'Follow-up task statuses']
        ]) {
            if (type === 'overview' || type === kind) {
                statusPanel(heading, statusesFor(key));
            }
        }

        if (['overview', 'consultations'].includes(type)) {
            trend(report.daily);
        }

        if (type === 'prescriptions') {
            const rows = (report.medications || []).map(item => ({
                status: item.name,
                count: item.count
            }));

            statusPanel('Medication names · top 20', rows, {
                medication: true,
                total: s.prescriptions
            });
        }

        if (
            admin
            && ['overview', 'collections'].includes(type)
            && report.financial
        ) {
            collections(report.financial);
        }

        if (
            admin
            && ['overview', 'orders'].includes(type)
            && report.order_statuses
        ) {
            statusPanel('Shop order statuses', report.order_statuses);
        }

        get('report-definition').textContent = notes[type];

        if (type === 'overview' && !report.financial) {
            get('report-definition').textContent =
                notes.overview.split(' Collections use')[0];
        }
        renderCover(report);
    }

    async function load() {
        if (!ready || !get('report-filters').reportValidity()) {
            return;
        }

        const seq = ++version;

        data = null;
        exportRows = [];

        get('report-export').disabled = get('report-print').disabled = true;
        get('report-results').hidden = true;
        get('report-retry').hidden = true;
        get('report-message').textContent = 'Preparing report…';

        const type = get('report-type').value;
        const from = get('report-from').value;
        const to = get('report-to').value;

        if (from > to) {
            get('report-message').textContent =
                'From date must be before or equal to To date.';
            return;
        }

        const query = new URLSearchParams({
            report_type: type,
            date_from: from,
            date_to: to
        });

        for (const [id, key] of [
            ['report-status', 'status'],
            ['report-vet', 'veterinarian_id'],
            ['report-method', 'payment_method'],
            ['report-source', 'payment_source'],
            ['report-shipping', 'shipping_method'],
            ['report-medication', 'medication']
        ]) {
            if (!get(`${id}-field`).hidden && get(id).value.trim()) {
                query.set(key, get(id).value.trim());
            }
        }

        try {
            const report = await request(`/reports?${query}`);

            if (seq !== version) {
                return;
            }

            data = report;
            render(report);

            get('report-results').hidden = false;
            get('report-export').disabled = get('report-print').disabled = false;
            get('report-message').textContent =
                'Report ready. Print or export the filtered results below.';

        } catch (error) {
            if (seq !== version) {
                return;
            }

            get('report-message').textContent = error.message;
            get('report-retry').hidden = false;
        }
    }

    function csv() {
        if (!data) {
            return;
        }

        const rows = [
            [title()],
            ['Clinic', data.clinic_name],
            ['From', data.date_from],
            ['To', data.date_to],
            ['Filters', filterDescription(data)],
            ['Prepared by', data.prepared_by],
            ['Generated at (UTC)', data.generated_at],
            ...exportRows,
            [],
            ['Notes', get('report-definition').textContent]
        ];

        const escape = value => {
            let text = String(value ?? '');

            if (
                /^\s*[=+@\t\r]/.test(text)
                || (/^\s*-/.test(text) && !/^-[0-9]+(?:\.[0-9]+)?$/.test(text))
            ) {
                text = "'" + text;
            }

            return '"' + text.replaceAll('"', '""') + '"';
        };

        const url = URL.createObjectURL(new Blob([
            '\uFEFF' + rows.map(row => row.map(escape).join(',')).join('\r\n')
        ], {
            type: 'text/csv;charset=utf-8'
        }));

        const a = node('a');

        a.href = url;
        a.download = `vetdental-${data.report_type}-${data.date_from}-${data.date_to}.csv`;

        document.body.appendChild(a);
        a.click();
        a.remove();

        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    get('report-filters').addEventListener('submit', event => {
        event.preventDefault();
        load();
    });

    get('report-type').addEventListener('change', configure);

    for (const id of [
        'report-from',
        'report-to',
        'report-status',
        'report-vet',
        'report-method',
        'report-source',
        'report-shipping',
        'report-medication'
    ]) {
        get(id).addEventListener('input', invalidate);
        get(id).addEventListener('change', invalidate);
    }

    get('report-title').addEventListener('input', updateTitle);
    get('report-export').addEventListener('click', csv);

    get('report-print').addEventListener('click', () => {
        if (data) {
            updateTitle();
            window.print();
        }
    });

    // Also update the title when the browser's own Print command is used.
    window.addEventListener('beforeprint', () => {
        if (data) {
            updateTitle();
        }
    });

    document.querySelectorAll('[data-report-period]').forEach(button =>
        button.addEventListener('click', () => {
            dates(button.dataset.reportPeriod);
            invalidate();
        })
    );

    get('report-retry').addEventListener(
        'click',
        () => ready ? load() : initialize()
    );

    async function initialize() {
        try {
            if (admin) {
                const profile = await request('/admins/me');

                if (profile.user.role !== 'clinic_administrator') {
                    throw new Error('A clinic administrator account is required.');
                }

                get('topbar-name').textContent = profile.user.full_name;
                get('topbar-avatar').textContent =
                    Array.from(profile.user.full_name.trim())[0];

            } else if (!await vetReady) {
                return;
            }

            if (admin) {
                const options = await request('/reports/filters');

                for (const vet of options.veterinarians) {
                    get('report-vet').add(new Option(vet.name, vet.id));
                }
            }

            ready = true;
            dates('month');
            configure();
            get('report-message').textContent =
                'Choose your report settings, then click Generate report.';

        } catch (error) {
            get('report-message').textContent = error.message;
            get('report-retry').hidden = false;
        }
    }

    if (admin) {
        get('logout-button').addEventListener('click', () => {
            sessionStorage.removeItem('vetdental_staff_token');
            location.replace('/web/');
        });
    }

    initialize();
})();
