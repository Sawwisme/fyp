(() => {
    const get = id => document.getElementById(id);
    const dialog = get('product-dialog');
    const form = get('product-form');
    const rows = get('product-rows');
    const message = get('product-list-message');

    let page = 0;
    let hasMore = false;
    let version = 0;
    let saving = false;
    let uncertain = false;
    let starting = false;
    let editing = null;
    let timer;
    const pageSize = 10;

    function logout() {
        sessionStorage.removeItem('vetdental_staff_token');
        window.location.replace('/web/');
    }

    async function request(
        path,
        body,
        method = body === undefined ? 'GET' : 'POST'
    ) {
        const token = sessionStorage.getItem('vetdental_staff_token');
        if (!token) {
            logout();
            throw new Error('Please log in again.');
        }

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);
        const headers = {
            Accept: 'application/json',
            Authorization: `Bearer ${token}`
        };

        const multipart = body instanceof FormData;

        if (body !== undefined && !multipart) {
            headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch(path, {
                method,
                headers,
                credentials: 'omit',
                cache: 'no-store',
                body: body === undefined
                    ? undefined
                    : multipart
                        ? body
                        : JSON.stringify(body),
                signal: controller.signal
            });

            if (response.status === 401) {
                logout();
                throw new Error('Your session has expired.');
            }

            let data;
            try {
                data = await response.json();
            } catch (_) {
                const error = new Error('Unexpected server response.');
                error.uncertain = body !== undefined;
                throw error;
            }

            if (!response.ok) {
                const detail = Array.isArray(data.detail)
                    ? data.detail.map(item => item.msg).join(' ')
                    : data.detail;

                const error = new Error(
                    typeof detail === 'string'
                        ? detail
                        : 'The request could not be completed.'
                );
                error.uncertain =
                    body !== undefined && response.status >= 500;
                throw error;
            }

            return data;
        } catch (error) {
            if (error.name === 'AbortError' || error instanceof TypeError) {
                const failure = new Error('Cannot confirm the server response.');
                failure.uncertain = body !== undefined;
                throw failure;
            }
            throw error;
        } finally {
            clearTimeout(timeout);
        }
    }

    async function loadSummary() {
        try {
            const data = await request('/clinic-products/summary');

            for (const [id, key] of [
                ['product-total', 'total'],
                ['product-active', 'active'],
                ['product-low', 'low_stock'],
                ['product-out', 'out_of_stock']
            ]) {
                get(id).textContent = data[key];
            }

            get('product-summary-message').textContent =
                'Clinic totals. Low stock means 1–5 units of an active product.';
        } catch (error) {
            for (const id of [
                'product-total', 'product-active', 'product-low', 'product-out'
            ]) {
                get(id).textContent = '—';
            }
            get('product-summary-message').textContent = error.message;
            get('product-list-retry').hidden = false;
        }
    }

    function cell(row, value, className = '') {
        const td = document.createElement('td');
        td.textContent = value;
        td.className = className;
        row.appendChild(td);
        return td;
    }

    async function loadProducts(targetPage = 0) {
        const currentVersion = ++version;
        message.textContent = 'Loading products…';
        get('product-list-retry').hidden = true;
        get('product-previous').disabled = true;
        get('product-next').disabled = true;

        const query = new URLSearchParams({
            q: get('product-search').value.trim(),
            offset: String(targetPage * pageSize),
            limit: String(pageSize + 1)
        });

        if (get('product-category-filter').value) {
            query.set('category_id', get('product-category-filter').value);
        }
        if (get('product-status-filter').value) {
            query.set('product_status', get('product-status-filter').value);
        }

        try {
            const items = await request(`/clinic-products?${query}`);
            if (currentVersion !== version) return;

            if (!Array.isArray(items)) {
                throw new Error('Unexpected product response.');
            }

            page = targetPage;
            hasMore = items.length > pageSize;
            rows.replaceChildren();

            for (const item of items.slice(0, pageSize)) {
                const row = document.createElement('tr');
                const productCell = cell(row, '');
                const productInfo = document.createElement('div');
                productInfo.className = 'product-name-cell';

                const photo = document.createElement('img');
                photo.className = 'product-thumbnail';
                photo.alt = item.product_name;
                photo.loading = 'lazy';

                const placeholder = document.createElement('span');
                placeholder.className = 'product-photo-placeholder';
                placeholder.textContent = 'No photo';

                if (
                    /^\/clinic-products\/images\/[a-f0-9]{32}\.jpg$/
                        .test(item.image_url || '')
                ) {
                    photo.src = item.image_url;
                    photo.addEventListener(
                        'error',
                        () => photo.replaceWith(placeholder),
                        { once: true }
                    );
                    productInfo.appendChild(photo);
                } else {
                    productInfo.appendChild(placeholder);
                }

                const name = document.createElement('span');
                name.textContent = item.product_name;
                productInfo.appendChild(name);
                productCell.appendChild(productInfo);
                cell(row, item.category.category_name);
                cell(row, `RM ${Number(item.price).toFixed(2)}`);
                cell(
                    row,
                    String(item.stock_quantity),
                    item.stock_quantity <= 5 ? 'product-stock-warning' : ''
                );
                const status = cell(row, '');
                const badge = document.createElement('span');
                badge.className = item.status === 'active'
                    ? 'product-status active'
                    : 'product-status';
                badge.textContent = item.status;
                status.appendChild(badge);

                const actions = cell(row, '');
                const edit = document.createElement('button');
                edit.type = 'button';
                edit.className = 'secondary compact-button';
                edit.textContent = 'Edit';
                edit.addEventListener('click', () => openProduct(item));
                const buttons = document.createElement('div');
                buttons.className = 'product-row-actions';
                buttons.appendChild(edit);

                const adjust = document.createElement('button');
                adjust.type = 'button';
                adjust.className = 'secondary compact-button';
                adjust.textContent = 'Adjust Stock';
                adjust.addEventListener(
                    'click',
                    () => openStock(item, false)
                );

                const history = document.createElement('button');
                history.type = 'button';
                history.className = 'secondary compact-button';
                history.textContent = 'Stock History';
                history.addEventListener(
                    'click',
                    () => openStock(item, true)
                );

                const upload = document.createElement('button');
                upload.type = 'button';
                upload.className = 'secondary compact-button';
                upload.textContent = item.image_url
                    ? 'Replace Photo'
                    : 'Upload Photo';

                upload.addEventListener(
                    'click',
                    () => openProductPhoto(item)
                );

                buttons.append(adjust, history, upload);
                actions.appendChild(buttons);

                rows.appendChild(row);
            }

            message.textContent = items.length
                ? ''
                : 'No products match these filters.';
            get('product-page').textContent = `Page ${page + 1}`;
        } catch (error) {
            if (currentVersion !== version) return;
            rows.replaceChildren();
            hasMore = false;
            message.textContent = error.message;
            get('product-list-retry').hidden = false;
        } finally {
            if (currentVersion === version) {
                get('product-previous').disabled = page === 0;
                get('product-next').disabled = !hasMore;
            }
        }
    }

    function formControls() {
        get('product-fields').disabled = saving;
        get('product-stock').disabled = saving || Boolean(editing);
        get('product-close').disabled = saving;
        get('product-cancel').disabled = saving;
        get('product-save').disabled = saving || uncertain;
        get('product-add').disabled = saving || uncertain;
    }

    function openProduct(item = null) {
        if (saving || dialog.open) return;

        if (uncertain) {
            message.textContent =
                'Check the updated catalogue, then reload this page ' +
                'before making another change.';
            return;
        }

        editing = item;
        form.reset();
        get('product-form-message').textContent = '';
        get('product-stock-field').hidden = Boolean(item);
        get('product-stock').required = !item;

        get('product-dialog-title').textContent = item
            ? 'Edit Product'
            : 'Add Product';

        get('product-save').textContent = item
            ? 'Save changes'
            : 'Create product';

        if (item) {
            get('product-name').value = item.product_name;
            get('product-category').value = String(item.category_id);
            get('product-description').value = item.description || '';
            get('product-price').value = item.price;
            get('product-status').value = item.status;
        }

        formControls();
        dialog.showModal();
    }

    get('product-add').addEventListener(
        'click',
        () => openProduct()
    );

    function closeForm() {
        if (!saving) dialog.close();
    }

    get('product-close').addEventListener('click', closeForm);
    get('product-cancel').addEventListener('click', closeForm);
    dialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();

        if (saving || uncertain || !form.reportValidity()) return;

        const productName = get('product-name').value.trim();

        if (productName.length < 2) {
            get('product-form-message').textContent =
                'Enter a product name with at least two characters.';
            return;
        }

        const body = {
            category_id: Number(get('product-category').value),
            product_name: productName,
            description: get('product-description').value.trim() || null,
            price: get('product-price').value,
            status: get('product-status').value
        };

        const isEditing = Boolean(editing);

        if (isEditing) {
            body.expected_version = editing.version;
        } else {
            body.stock_quantity = Number(get('product-stock').value);
        }

        const path = isEditing
            ? `/clinic-products/${editing.product_id}`
            : '/clinic-products';

        saving = true;
        formControls();

        get('product-form-message').textContent = isEditing
            ? 'Saving changes…'
            : 'Creating product…';

        try {
            await request(
                path,
                body,
                isEditing ? 'PUT' : 'POST'
            );

            dialog.close();
            editing = null;

            await Promise.all([
                loadProducts(0),
                loadSummary()
            ]);
        } catch (error) {
            uncertain = Boolean(error.uncertain);

            get('product-form-message').textContent = uncertain
                ? error.message +
                ' Close this dialog and check the catalogue. ' +
                'Reload the page before making another change.'
                : error.message;

            await Promise.all([
                loadProducts(page),
                loadSummary()
            ]);
        } finally {
            saving = false;
            formControls();
        }
    });

    get('product-search').addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => loadProducts(0), 300);
    });
    get('product-category-filter').addEventListener(
        'change', () => loadProducts(0)
    );
    get('product-status-filter').addEventListener(
        'change', () => loadProducts(0)
    );
    get('product-previous').addEventListener(
        'click', () => loadProducts(page - 1)
    );
    get('product-next').addEventListener(
        'click', () => loadProducts(page + 1)
    );
    get('product-list-retry').addEventListener('click', () => {
        loadProducts(page);
        loadSummary();
    });
    get('logout-button').addEventListener('click', logout);

    let savingCategory = false;
    const categoryDialog = get('category-dialog');

    async function loadCategories(selectedCategoryId = null) {
        const categories = await request('/clinic-products/categories');

        if (!Array.isArray(categories)) {
            throw new Error('Unexpected category response.');
        }

        const filter = get('product-category-filter');
        const productSelect = get('product-category');

        const previousFilter = filter.value;
        const previousSelection = selectedCategoryId === null
            ? productSelect.value
            : String(selectedCategoryId);

        filter.replaceChildren(new Option('All categories', ''));
        productSelect.replaceChildren(
            new Option('Select a category', '')
        );

        for (const category of categories) {
            const title = category.clinic_id === null
                ? `${category.category_name} (Shared)`
                : category.category_name;

            filter.add(new Option(title, category.category_id));
            productSelect.add(new Option(title, category.category_id));
        }

        filter.value = previousFilter;
        if (filter.selectedIndex < 0) filter.value = '';

        productSelect.value = previousSelection;
        if (productSelect.selectedIndex < 0) {
            productSelect.value = '';
        }

        return categories;
    }

    function categoryControls() {
        get('category-fields').disabled = savingCategory;
        get('category-save').disabled = savingCategory;
        get('category-close').disabled = savingCategory;
        get('category-cancel').disabled = savingCategory;
        get('category-save').textContent = savingCategory
            ? 'Saving…'
            : 'Save category';
    }

    get('category-add').addEventListener('click', () => {
        if (savingCategory || saving) return;

        get('category-form').reset();
        get('category-form-message').textContent = '';
        get('category-page-message').textContent = '';

        categoryDialog.showModal();
        get('category-name').focus();
    });

    for (const id of ['category-close', 'category-cancel']) {
        get(id).addEventListener('click', () => {
            if (!savingCategory) categoryDialog.close();
        });
    }

    categoryDialog.addEventListener('cancel', event => {
        if (savingCategory) event.preventDefault();
    });

    get('category-form').addEventListener('submit', async event => {
        event.preventDefault();

        const form = get('category-form');
        const feedback = get('category-form-message');

        if (savingCategory || !form.reportValidity()) return;

        const name = get('category-name').value
            .trim()
            .replace(/\s+/g, ' ');

        if (name.length < 2) {
            feedback.textContent =
                'Enter a category name of at least 2 characters.';
            return;
        }

        const payload = {
            category_name: name,
            description:
                get('category-description').value.trim() || null
        };

        savingCategory = true;
        categoryControls();
        feedback.textContent = 'Saving category…';

        let saved = false;

        try {
            const category = await request(
                '/clinic-products/categories',
                payload
            );

            if (!Number.isInteger(category.category_id)) {
                throw new Error('Unexpected saved category response.');
            }

            saved = true;

            await loadCategories(category.category_id);

            categoryDialog.close();

            get('category-page-message').textContent =
                `“${category.category_name}” is ready to use. ` +
                'Existing categories are reused instead of duplicated.';

        } catch (error) {
            feedback.textContent = saved
                ? 'The category was saved, but the dropdowns could ' +
                'not refresh. Reload the page to see it.'
                : `${error.message} The result needs checking. ` +
                'Retrying the same name reuses an existing category.';

        } finally {
            savingCategory = false;
            categoryControls();
        }
    });

    async function initialize() {
        if (starting) return;
        starting = true;
        get('products-start-retry').hidden = true;

        try {
            const profile = await request('/admins/me');
            get('topbar-name').textContent = profile.user.full_name;
            get('topbar-avatar').textContent =
                Array.from(profile.user.full_name.trim())[0]?.toUpperCase() || 'A';

            await loadCategories();

            get('products-loading').hidden = true;
            get('products-workspace').hidden = false;

            await Promise.all([loadProducts(0), loadSummary()]);
        } catch (error) {
            get('products-loading-message').textContent = error.message;
            get('products-start-retry').hidden = false;
        } finally {
            starting = false;
        }
    }

    get('products-start-retry').addEventListener(
        'click', () => window.location.reload()
    );

    const stockDialog = document.createElement('dialog');
    stockDialog.id = 'product-stock-dialog';
    stockDialog.setAttribute('aria-labelledby', 'stock-dialog-title');

    stockDialog.innerHTML = `
        <form id="stock-form">
            <header class="products-heading">
                <h2 id="stock-dialog-title">Adjust Stock</h2>
                <button id="stock-close" type="button"
                        class="dialog-close"
                        aria-label="Close dialog">×</button>
            </header>

            <p id="stock-summary"></p>

            <fieldset id="stock-fields" class="product-form-grid">
                <div>
                    <label for="stock-direction">Adjustment</label>
                    <select id="stock-direction">
                        <option value="add">Add stock</option>
                        <option value="remove">Remove stock</option>
                    </select>
                </div>

                <div>
                    <label for="stock-quantity">Quantity</label>
                    <input id="stock-quantity" type="number"
                           min="1" max="1000000" step="1" required>
                </div>

                <div class="product-wide">
                    <label for="stock-reason">Reason</label>
                    <textarea id="stock-reason" rows="3"
                              minlength="5" maxlength="1000"
                              placeholder="For example: new delivery or damaged items"
                              required></textarea>
                </div>

                <p id="stock-preview" class="product-wide"></p>
            </fieldset>

            <p id="stock-message" role="status"></p>

            <footer class="product-form-actions">
                <button id="stock-cancel" type="button"
                        class="secondary compact-button">Close</button>
                <button id="stock-save" type="submit"
                        class="product-primary">Save adjustment</button>
            </footer>
        </form>

        <section class="stock-history-section">
            <h3>Stock history</h3>
            <p id="stock-history-message" role="status"></p>
            <button id="stock-history-retry" type="button"
                    class="secondary compact-button" hidden>
                Try again
            </button>

            <div class="product-table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Change</th>
                            <th>Before → After</th>
                            <th>Reason</th>
                            <th>Recorded by</th>
                        </tr>
                    </thead>
                    <tbody id="stock-history-rows"></tbody>
                </table>
            </div>

            <div class="product-pagination">
                <button id="stock-history-previous" type="button"
                        class="secondary compact-button">Previous</button>
                <span id="stock-history-page"></span>
                <button id="stock-history-next" type="button"
                        class="secondary compact-button">Next</button>
            </div>
        </section>
    `;

    document.body.appendChild(stockDialog);

    let stockItem = null;
    let stockHistoryPage = 0;
    let stockHistoryVersion = 0;
    let stockHistoryHasMore = false;
    const historyPageSize = 10;

    function stockControls() {
        get('stock-fields').disabled = saving;
        get('stock-close').disabled = saving;
        get('stock-cancel').disabled = saving;
        get('stock-save').disabled = saving || uncertain;
    }

    function updateStockPreview() {
        if (!stockItem) return;

        const quantity = Number(get('stock-quantity').value);
        const change = get('stock-direction').value === 'remove'
            ? -quantity
            : quantity;

        get('stock-preview').textContent =
            Number.isInteger(quantity) && quantity > 0
                ? `Stock after adjustment: ${stockItem.stock_quantity + change}`
                : '';
    }

    async function loadStockHistory(targetPage = 0) {
        if (!stockItem) return;

        const currentVersion = ++stockHistoryVersion;
        const productId = stockItem.product_id;

        get('stock-history-message').textContent = 'Loading history…';
        get('stock-history-retry').hidden = true;
        get('stock-history-previous').disabled = true;
        get('stock-history-next').disabled = true;
        get('stock-history-rows').replaceChildren();

        try {
            const query = new URLSearchParams({
                offset: String(targetPage * historyPageSize),
                limit: String(historyPageSize + 1)
            });

            const items = await request(
                `/clinic-products/${productId}/stock-history?${query}`
            );

            if (currentVersion !== stockHistoryVersion) return;
            if (!Array.isArray(items)) {
                throw new Error('Unexpected stock history response.');
            }

            stockHistoryPage = targetPage;
            stockHistoryHasMore = items.length > historyPageSize;

            for (const item of items.slice(0, historyPageSize)) {
                const row = document.createElement('tr');

                const timestamp = /Z$|[+-]\d{2}:\d{2}$/.test(item.created_at)
                    ? item.created_at
                    : item.created_at + 'Z';

                cell(
                    row,
                    new Date(timestamp).toLocaleString('en-MY', {
                        timeZone: 'Asia/Kuala_Lumpur',
                        dateStyle: 'medium',
                        timeStyle: 'short'
                    }) + ' MYT'
                );
                cell(
                    row,
                    item.quantity_change > 0
                        ? `+${item.quantity_change}`
                        : String(item.quantity_change)
                );
                cell(
                    row,
                    `${item.quantity_before} → ${item.quantity_after}`
                );
                cell(row, item.reason);
                cell(
                    row,
                    item.created_by_user_id == null
                        ? 'System'
                        : `User #${item.created_by_user_id}`
                );

                get('stock-history-rows').appendChild(row);
            }

            get('stock-history-message').textContent = items.length
                ? ''
                : 'No stock adjustments recorded.';
            get('stock-history-page').textContent =
                `Page ${stockHistoryPage + 1}`;
        } catch (error) {
            if (currentVersion !== stockHistoryVersion) return;
            stockHistoryHasMore = false;
            get('stock-history-message').textContent = error.message;
            get('stock-history-retry').hidden = false;
        } finally {
            if (currentVersion === stockHistoryVersion) {
                get('stock-history-previous').disabled =
                    stockHistoryPage === 0;
                get('stock-history-next').disabled =
                    !stockHistoryHasMore;
            }
        }
    }

    function openStock(item, historyOnly) {
        if (saving || dialog.open || stockDialog.open) return;

        if (uncertain && !historyOnly) {
            message.textContent =
                'Check the catalogue and reload this page before ' +
                'making another change.';
            return;
        }

        stockItem = item;
        stockHistoryPage = 0;
        stockHistoryHasMore = false;
        get('stock-form').reset();
        get('stock-message').textContent = '';
        get('stock-preview').textContent = '';
        get('stock-fields').hidden = historyOnly;
        get('stock-save').hidden = historyOnly;

        get('stock-dialog-title').textContent = historyOnly
            ? 'Stock History'
            : 'Adjust Stock';

        get('stock-summary').textContent =
            `${item.product_name} · Current stock: ${item.stock_quantity}`;

        stockControls();
        stockDialog.showModal();
        loadStockHistory(0);
    }

    function closeStock() {
        if (!saving) stockDialog.close();
    }

    get('stock-close').addEventListener('click', closeStock);
    get('stock-cancel').addEventListener('click', closeStock);

    stockDialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    stockDialog.addEventListener('close', () => {
        stockHistoryVersion++;
    });

    get('stock-direction').addEventListener('change', updateStockPreview);
    get('stock-quantity').addEventListener('input', updateStockPreview);

    get('stock-history-previous').addEventListener(
        'click', () => loadStockHistory(stockHistoryPage - 1)
    );
    get('stock-history-next').addEventListener(
        'click', () => loadStockHistory(stockHistoryPage + 1)
    );
    get('stock-history-retry').addEventListener(
        'click', () => loadStockHistory(stockHistoryPage)
    );

    get('stock-form').addEventListener('submit', async event => {
        event.preventDefault();

        if (
            saving ||
            uncertain ||
            !stockItem ||
            get('stock-save').hidden ||
            !get('stock-form').reportValidity()
        ) return;

        const quantity = Number(get('stock-quantity').value);
        const change = get('stock-direction').value === 'remove'
            ? -quantity
            : quantity;
        const reason = get('stock-reason').value.trim();

        if (
            !Number.isInteger(quantity) ||
            quantity < 1 ||
            quantity > 1000000 ||
            reason.length < 5
        ) {
            get('stock-message').textContent =
                'Enter a whole quantity and a reason of at least five characters.';
            return;
        }

        const after = stockItem.stock_quantity + change;

        if (after < 0 || after > 1000000) {
            get('stock-message').textContent =
                'The resulting stock must be between 0 and 1,000,000.';
            return;
        }

        saving = true;
        formControls();
        stockControls();
        get('stock-message').textContent = 'Saving adjustment…';

        try {
            await request(
                `/clinic-products/${stockItem.product_id}/stock-adjustments`,
                {
                    expected_version: stockItem.version,
                    quantity_change: change,
                    reason
                }
            );

            stockDialog.close();
        } catch (error) {
            uncertain = Boolean(error.uncertain);
            get('stock-message').textContent = uncertain
                ? error.message +
                ' Check stock history and reload this page before retrying.'
                : error.message;
        } finally {
            saving = false;
            formControls();
            stockControls();

            await Promise.all([
                loadProducts(page),
                loadSummary()
            ]);

            if (stockDialog.open) {
                await loadStockHistory(0);
            }
        }
    });

    const photoDialog = document.createElement('dialog');
    photoDialog.id = 'product-photo-dialog';
    photoDialog.setAttribute('aria-labelledby', 'product-photo-title');

    photoDialog.innerHTML = `
        <form id="product-photo-form">
            <header class="products-heading">
                <h2 id="product-photo-title">Product Photo</h2>
                <button id="product-photo-close" type="button"
                        class="dialog-close"
                        aria-label="Close dialog">×</button>
            </header>

            <p id="product-photo-name"></p>
            <img id="product-photo-preview"
                 alt="Selected product photo" hidden>

            <label for="product-photo-file">Choose photo</label>
            <input id="product-photo-file" type="file"
                   accept="image/jpeg,image/png,image/webp" required>

            <p class="muted">JPEG, PNG or WebP. Maximum 8 MB.</p>
            <p id="product-photo-message" role="status"></p>

            <footer class="product-form-actions">
                <button id="product-photo-cancel" type="button"
                        class="secondary compact-button">Cancel</button>
                <button id="product-photo-save" type="submit"
                        class="product-primary">Upload photo</button>
            </footer>
        </form>
    `;

    document.body.appendChild(photoDialog);

    let photoProduct = null;
    let previewUrl = null;

    function clearPhotoPreview() {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = null;

        get('product-photo-preview').removeAttribute('src');
        get('product-photo-preview').hidden = true;
    }

    function photoControls() {
        get('product-photo-file').disabled = saving;
        get('product-photo-close').disabled = saving;
        get('product-photo-cancel').disabled = saving;
        get('product-photo-save').disabled = saving || uncertain;
    }

    function openProductPhoto(item) {
        if (
            saving ||
            dialog.open ||
            stockDialog.open ||
            photoDialog.open
        ) return;

        if (uncertain) {
            message.textContent =
                'Check the catalogue and reload this page before ' +
                'making another change.';
            return;
        }

        photoProduct = item;
        get('product-photo-form').reset();
        get('product-photo-message').textContent = '';
        get('product-photo-name').textContent = item.product_name;
        clearPhotoPreview();

        if (
            /^\/clinic-products\/images\/[a-f0-9]{32}\.jpg$/
                .test(item.image_url || '')
        ) {
            get('product-photo-preview').src = item.image_url;
            get('product-photo-preview').hidden = false;
        }

        photoControls();
        photoDialog.showModal();
    }

    get('product-photo-file').addEventListener('change', () => {
        clearPhotoPreview();
        get('product-photo-message').textContent = '';

        const file = get('product-photo-file').files[0];
        if (!file) return;

        if (
            !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) ||
            file.size > 8 * 1024 * 1024
        ) {
            get('product-photo-file').value = '';
            get('product-photo-message').textContent =
                'Choose a JPEG, PNG or WebP photo no larger than 8 MB.';
            return;
        }

        previewUrl = URL.createObjectURL(file);
        get('product-photo-preview').src = previewUrl;
        get('product-photo-preview').hidden = false;
    });

    function closePhoto() {
        if (!saving) photoDialog.close();
    }

    get('product-photo-close').addEventListener('click', closePhoto);
    get('product-photo-cancel').addEventListener('click', closePhoto);

    photoDialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    photoDialog.addEventListener('close', clearPhotoPreview);

    get('product-photo-form').addEventListener('submit', async event => {
        event.preventDefault();

        if (
            saving ||
            uncertain ||
            !photoProduct ||
            !get('product-photo-form').reportValidity()
        ) return;

        const file = get('product-photo-file').files[0];
        if (!file) return;

        const body = new FormData();
        body.append('file', file);
        body.append('expected_version', String(photoProduct.version));

        saving = true;
        formControls();
        photoControls();
        get('product-photo-message').textContent = 'Uploading photo…';

        try {
            await request(
                `/clinic-products/${photoProduct.product_id}/image`,
                body
            );

            photoDialog.close();
        } catch (error) {
            uncertain = Boolean(error.uncertain);

            get('product-photo-message').textContent = uncertain
                ? error.message +
                ' Check the catalogue and reload this page before retrying.'
                : error.message;
        } finally {
            saving = false;
            formControls();
            photoControls();

            await Promise.all([
                loadProducts(page),
                loadSummary()
            ]);
        }
    });

    const shopSettingsDialog = document.createElement('dialog');
    shopSettingsDialog.id = 'shop-settings-dialog';
    shopSettingsDialog.setAttribute(
        'aria-labelledby',
        'shop-settings-title'
    );

    shopSettingsDialog.innerHTML = `
        <form id="shop-settings-form">
            <header class="products-heading">
                <h2 id="shop-settings-title">Shop Settings</h2>
                <button id="shop-settings-close"
                        class="dialog-close"
                        type="button"
                        aria-label="Close settings">×</button>
            </header>

            <p class="muted">
                Choose how owners receive products from your clinic.
            </p>

            <fieldset id="shop-settings-fields">
                <label class="shop-setting-toggle">
                    <input id="shop-pickup" type="checkbox">
                    <span>
                        <strong>Clinic pickup</strong>
                        <small>Owners collect their order at your clinic.</small>
                    </span>
                </label>

                <p id="shop-pickup-address" class="shop-pickup-address"></p>

                <label class="shop-setting-toggle">
                    <input id="shop-delivery" type="checkbox">
                    <span>
                        <strong>Delivery</strong>
                        <small>Your clinic arranges delivery to the owner.</small>
                    </span>
                </label>

                <div class="shop-delivery-fee">
                    <label for="shop-delivery-fee">Delivery fee (RM)</label>
                    <input id="shop-delivery-fee"
                           type="number"
                           min="0"
                           max="99999999.99"
                           step="0.01">
                    <small>
                        A flat fee per delivery order. Enter 0 for free delivery.
                    </small>
                </div>
            </fieldset>

            <p id="shop-settings-message" role="status"></p>

            <button id="shop-settings-retry"
                    type="button"
                    class="secondary compact-button"
                    hidden>
                Reload settings
            </button>

            <footer class="product-form-actions">
                <button id="shop-settings-cancel"
                        class="secondary compact-button"
                        type="button">
                    Cancel
                </button>
                <button id="shop-settings-save"
                        class="product-primary"
                        type="submit">
                    Save settings
                </button>
            </footer>
        </form>
    `;

    document.body.appendChild(shopSettingsDialog);

    let shopSettingsData = null;
    let shopSettingsLoading = false;
    let shopSettingsUncertain = false;
    let shopSettingsVersion = 0;

    function shopSettingsControls() {
        get('shop-settings-fields').disabled =
            saving || shopSettingsLoading || !shopSettingsData ||
            shopSettingsUncertain;

        get('shop-settings-save').disabled =
            saving || shopSettingsLoading || !shopSettingsData ||
            shopSettingsUncertain;

        get('shop-settings-close').disabled = saving;
        get('shop-settings-cancel').disabled = saving;
        get('shop-settings-retry').disabled =
            saving || shopSettingsLoading;

        get('shop-delivery-fee').disabled =
            !get('shop-delivery').checked;

        get('shop-delivery-fee').required =
            get('shop-delivery').checked;
    }

    async function loadShopSettings() {
        const currentVersion = ++shopSettingsVersion;
        shopSettingsLoading = true;
        shopSettingsData = null;

        get('shop-settings-message').textContent = 'Loading settings…';
        get('shop-settings-retry').hidden = true;
        shopSettingsControls();

        try {
            const data = await request('/clinic-shop/settings');

            if (currentVersion !== shopSettingsVersion) return;

            shopSettingsData = data;
            shopSettingsUncertain = false;

            get('shop-pickup').checked = data.pickup_enabled;
            get('shop-delivery').checked = data.delivery_enabled;
            get('shop-delivery-fee').value = data.delivery_fee;

            get('shop-pickup-address').textContent = data.pickup_address
                ? `Pickup address: ${data.pickup_address}`
                : 'Add your clinic address under Profile → Clinic information.';

            get('shop-settings-message').textContent = '';
        } catch (error) {
            if (currentVersion !== shopSettingsVersion) return;

            get('shop-settings-message').textContent = error.message;
            get('shop-settings-retry').hidden = false;
        } finally {
            if (currentVersion === shopSettingsVersion) {
                shopSettingsLoading = false;
                shopSettingsControls();
            }
        }
    }

    get('shop-settings-open').addEventListener('click', () => {
        if (saving || document.querySelector('dialog[open]')) return;

        get('shop-settings-form').reset();
        get('shop-pickup-address').textContent = '';
        shopSettingsDialog.showModal();
        loadShopSettings();
    });

    function closeShopSettings() {
        if (!saving) shopSettingsDialog.close();
    }

    get('shop-settings-close').addEventListener(
        'click', closeShopSettings
    );
    get('shop-settings-cancel').addEventListener(
        'click', closeShopSettings
    );
    get('shop-settings-retry').addEventListener(
        'click', loadShopSettings
    );
    get('shop-delivery').addEventListener(
        'change', shopSettingsControls
    );

    shopSettingsDialog.addEventListener('cancel', event => {
        if (saving) event.preventDefault();
    });

    shopSettingsDialog.addEventListener('close', () => {
        shopSettingsVersion++;
        shopSettingsData = null;
        shopSettingsLoading = false;
    });

    get('shop-settings-form').addEventListener('submit', async event => {
        event.preventDefault();

        if (
            saving ||
            shopSettingsLoading ||
            shopSettingsUncertain ||
            !shopSettingsData ||
            !get('shop-settings-form').reportValidity()
        ) return;

        const pickup = get('shop-pickup').checked;
        const delivery = get('shop-delivery').checked;

        if (!pickup && !delivery) {
            get('shop-settings-message').textContent =
                'Enable pickup, delivery, or both.';
            return;
        }

        const body = {
            expected_version: shopSettingsData.version,
            pickup_enabled: pickup,
            delivery_enabled: delivery,
            delivery_fee: delivery
                ? get('shop-delivery-fee').value
                : shopSettingsData.delivery_fee
        };

        saving = true;
        formControls();
        shopSettingsControls();
        get('shop-settings-message').textContent = 'Saving settings…';

        try {
            await request('/clinic-shop/settings', body, 'PUT');

            shopSettingsDialog.close();
            message.textContent = 'Shop settings saved.';
        } catch (error) {
            shopSettingsUncertain = Boolean(error.uncertain);

            get('shop-settings-message').textContent =
                error.message +
                ' Reload settings before making another change.';

            get('shop-settings-retry').hidden = false;
        } finally {
            saving = false;
            formControls();
            shopSettingsControls();
        }
    });

    initialize();
})();