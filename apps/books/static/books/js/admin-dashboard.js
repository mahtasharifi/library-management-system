(async () => {
    const root = document.body;
    const translationResponse = await fetch(root.dataset.translationsUrl || '', { headers: { 'Accept': 'application/json' } });
    if (!translationResponse.ok) throw new Error(`translation bundle ${translationResponse.status}`);
    const translations = (await translationResponse.json()).translations || {};
    const tr = (key, params = {}) => {
        const template = translations[key];
        if (typeof template !== 'string') throw new Error(`Missing translation: js.admin.${key}`);
        return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_, name) => String(params[name] ?? ''));
    };
    const API = (document.body.dataset.adminApiBase || '').replace(/dashboard\/?$/, '');
    const IMPORT_TEMPLATE_URL = document.body.dataset.importTemplateUrl || '';
    const LIBRARY_URL = document.body.dataset.libraryUrl || '';
    const UPLOAD_PAGE_URL = document.body.dataset.uploadPageUrl || '';
    const REQUEST_TIMEOUT_MS = 60000;
    const mutationRequests = new Map();

    function getCookie(name) {
        try {
            const prefix = `${name}=`;
            const item = document.cookie
                .split("; ")
                .find(value => value.startsWith(prefix));
            return item ? decodeURIComponent(item.slice(prefix.length)) : "";
        } catch (error) {
            return "";
        }
    }

    function getCsrfToken() {
        return getCookie("csrftoken") || document.querySelector(
            '[name="csrfmiddlewaretoken"]'
        )?.value || "";
    }

    const content = document.getElementById('content');
    const title = document.getElementById('pageTitle');
    const actions = document.getElementById('headerActions');
    const modal = document.getElementById('modal');
    const modalCard = document.getElementById('modalCard');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const BOOK_FALLBACK = document.body.dataset.bookFallback || '';
    let books = [];
    let nbokCategories = [];
    let nbokPickerKeyHandler = null;
    let messages = [];
    let digitalRequests = [];
    let physicalRequests = [];

    const esc = (value = '') => String(value ?? '').replace(
        /[&<>'"]/g,
        char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char]),
    );
    const date = value => value
        ? new Intl.DateTimeFormat('fa-IR-u-ca-persian', {dateStyle: 'short', timeStyle: 'short'}).format(new Date(value))
        : '-';
    const dateOnly = value => value
        ? new Intl.DateTimeFormat('fa-IR-u-ca-persian', {dateStyle: 'short'}).format(new Date(`${value}T12:00:00`))
        : '-';
    const status = value => `<span class="status-chip status-${value}">${
        value === 'approved'
            ? tr('status.approved')
            : value === 'rejected'
                ? tr('status.rejected')
                : tr('status.pending')
    }</span>`;
    const empty = text => `<div class="empty"><i data-feather="inbox" class="mx-auto mb-3"></i><p>${esc(text)}</p></div>`;
    const spinner = () => {
        content.innerHTML = `<div class="empty"><div class="loader mx-auto mb-4"></div><p>${tr('loading')}</p></div>`;
    };

    function notify(text, ok = true) {
        const notice = document.getElementById('notice');
        notice.textContent = text;
        notice.className = `notice show ${ok ? '' : 'error'}`;
        window.setTimeout(() => { notice.className = 'notice'; }, 3800);
    }

    function openModal(html) {
        modalCard.innerHTML = html;
        modal.classList.add('open');
        feather.replace();
    }

    function closeModal() {
        modal.classList.remove('open');
        modalCard.innerHTML = '';
    }

    modal.addEventListener('click', event => {
        if (event.target === modal || event.target.closest('[data-close]')) closeModal();
    });

    async function requestApi(endpoint, options = {}) {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        const config = {
            ...options,
            credentials: "same-origin",
            signal: controller.signal,
            headers: {
                "Accept": "application/json",
                "X-CSRFToken": getCsrfToken(),
                ...(options.headers || {}),
            },
        };
        if (options.body !== undefined && !(options.body instanceof FormData)) {
            config.headers["Content-Type"] = "application/json";
        }
        try {
            const url = `${API}${endpoint.replace(/^\/+|\/+$/g, "")}/`;
            const response = await fetch(url, config);
            if (response.redirected && response.url.includes("/accounts/login/")) {
                return {success: false, message: tr("session_expired"), httpStatus: 401};
            }
            const contentType = response.headers.get("content-type") || "";
            let data = {success: false, message: tr("server_error", {status: response.status})};
            if (contentType.includes("application/json")) {
                data = await response.json();
            }
            if (!response.ok) data.success = false;
            return {...data, httpStatus: response.status};
        } catch (error) {
            return {success: false, message: tr("network_error"), httpStatus: 0};
        } finally {
            window.clearTimeout(timeout);
        }
    }

    function api(endpoint, options = {}) {
        const method = String(options.method || "GET").toUpperCase();
        if (method === "GET") return requestApi(endpoint, options);
        const key = `${method}:${endpoint}`;
        if (mutationRequests.has(key)) return mutationRequests.get(key);
        const pending = requestApi(endpoint, options).finally(() => mutationRequests.delete(key));
        mutationRequests.set(key, pending);
        return pending;
    }


    function setBadge(id,value){const el=document.getElementById(id);el.textContent=value;el.classList.toggle('hidden',!value)}
    function bindImageFallbacks(root=document){root.querySelectorAll?.('img[data-fallback-src]').forEach(img=>{img.addEventListener('error',()=>{const fallback=img.dataset.fallbackSrc;if(fallback&&img.src!==fallback){img.src=fallback}delete img.dataset.fallbackSrc},{once:true})})}
    async function loadCounts(){const d=await api('unread-counts');if(d.success){setBadge('managementTotal',d.total);setBadge('messageCount',d.messages);setBadge('digitalCount',d.digital);setBadge('physicalCount',d.physical)}}
    function normalize(value=''){return String(value??'').toLocaleLowerCase('fa').replace(/[\u064a\u0649]/g,'\u06cc').replace(/\u0643/g,'\u06a9').replace(/[\u06f0-\u06f9]/g,d=>String('\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9'.indexOf(d))).trim()}
    function flattenNbok(tree,depth=0,out=[]){(tree||[]).forEach(node=>{out.push({...node,depth});flattenNbok(node.children||[],depth+1,out)});return out}
    function findNbokNode(rowId,level){return flattenNbok(nbokCategories).find(node=>String(node.row_id)===String(rowId||'')&&String(node.level_code)===String(level||''))||null}
    function nbokParentOptions(){return `<option value="">${tr('categories.parent_root')}</option>`+flattenNbok(nbokCategories).filter(node=>node.level_code!=='L6').map(node=>`<option value="${node.row_id}|${node.level_code}">${'— '.repeat(node.depth)}${esc(node.name)}</option>`).join('')}
    function closeNbokPicker(){document.getElementById('nbokPickerV25')?.remove();document.documentElement.classList.remove('nbok-picker-open');if(nbokPickerKeyHandler){document.removeEventListener('keydown',nbokPickerKeyHandler);nbokPickerKeyHandler=null}}
    function openNbokPicker(onSelect,currentRowId='',currentLevel=''){
        closeNbokPicker();
        const overlay=document.createElement('div');
        overlay.id='nbokPickerV25';overlay.className='nbok-picker-overlay';
        overlay.innerHTML=`<div class="nbok-picker-card" role="dialog" aria-modal="true"><div class="nbok-picker-head"><div><strong>${tr('categories.picker_title')}</strong><small>${tr('categories.help')}</small></div><button type="button" class="action-btn" data-nbok-close><i data-feather="x"></i></button></div><div class="nbok-picker-search"><i data-feather="search"></i><input id="nbokPickerSearchV25" type="search" autocomplete="off" placeholder="${tr('categories.picker_search')}"></div><div id="nbokPickerListV25" class="nbok-picker-list"></div><div class="nbok-picker-footer"><button type="button" class="admin-btn secondary" data-nbok-none>${tr('categories.picker_none')}</button></div></div>`;
        document.body.appendChild(overlay);document.documentElement.classList.add('nbok-picker-open');feather.replace();
        const list=overlay.querySelector('#nbokPickerListV25'),search=overlay.querySelector('#nbokPickerSearchV25');
        const render=()=>{const term=normalize(search.value||'');const rows=flattenNbok(nbokCategories).filter(node=>!term||normalize(`${node.name} ${node.path_text}`).includes(term));list.innerHTML=rows.length?rows.map(node=>`<button type="button" class="nbok-picker-row ${String(node.row_id)===String(currentRowId)&&String(node.level_code)===String(currentLevel)?'is-selected':''}" data-nbok-pick="${node.row_id}|${node.level_code}" style="--nbok-depth:${node.depth}"><span class="nbok-picker-node"><b>${esc(node.name)}</b><small>${esc(node.path_text)}</small></span><span class="nbok-level-chip">${esc(tr('categories.level',{level:String(node.level_code||'').replace('L','')}))}</span></button>`).join(''):`<div class="nbok-picker-empty">${tr('categories.picker_empty')}</div>`};
        search.addEventListener('input',render);
        overlay.addEventListener('click',event=>{if(event.target===overlay||event.target.closest('[data-nbok-close]')){closeNbokPicker();return}if(event.target.closest('[data-nbok-none]')){onSelect(null);closeNbokPicker();return}const pick=event.target.closest('[data-nbok-pick]');if(pick){const [rowId,level]=pick.dataset.nbokPick.split('|');const node=findNbokNode(rowId,level);if(node){onSelect(node);closeNbokPicker()}}});
        nbokPickerKeyHandler=event=>{if(event.key==='Escape'&&document.getElementById('nbokPickerV25'))closeNbokPicker()};document.addEventListener('keydown',nbokPickerKeyHandler);
        render();setTimeout(()=>search.focus(),0);
    }
    function prepareResponsiveTables(root=content){
        root.querySelectorAll('table.data-table').forEach(table=>{
            table.classList.add('admin-responsive-table');
            table.parentElement?.classList.add('admin-responsive-table-wrap');
            const labels=[...table.querySelectorAll('thead th')].map(th=>th.textContent.trim());
            table.querySelectorAll('tbody tr').forEach(row=>{
                [...row.children].forEach((cell,index)=>{if(cell.tagName==='TD'&&!cell.hasAttribute('colspan'))cell.dataset.label=labels[index]||''});
            });
        });
    }
    let tableDecorationFrame=0;
    const tableObserver=new MutationObserver(()=>{cancelAnimationFrame(tableDecorationFrame);tableDecorationFrame=requestAnimationFrame(()=>prepareResponsiveTables())});
    tableObserver.observe(content,{childList:true,subtree:true});
    function setSidebarOpen(open){sidebar.classList.toggle('open',open);sidebarBackdrop.classList.toggle('open',open);document.documentElement.style.overflow=open&&window.innerWidth<=680?'hidden':''}

    async function showDashboard(){
        spinner();const d=await api('dashboard');
        if(!d.success){content.innerHTML=empty(tr('dashboard.load_failed'));return}
        const activities=(d.activities||[]).slice(0,8);
        content.innerHTML=`<div class="admin-overview"><div><h2>${tr('dashboard.overview_title')}</h2><p>${tr('dashboard.overview_help')}</p></div><button type="button" data-add-book-quick><i data-feather="plus"></i>${tr('dashboard.add_book')}</button></div>
        <div class="admin-quick">
            <button type="button" data-go-section="books"><span><i data-feather="search"></i></span>${tr('dashboard.manage_books')}</button>
            <button type="button" data-go-section="categories"><span><i data-feather="folder"></i></span>${tr('dashboard.manage_categories')}</button>
            <button type="button" data-go-section="messages"><span><i data-feather="message-circle"></i></span>${tr('dashboard.reply_messages')}</button>
            <a href="${esc(UPLOAD_PAGE_URL)}" target="_blank" rel="noopener"><span><i data-feather="upload-cloud"></i></span>${tr('dashboard.upload_files')}</a>
        </div><div class="stat-grid mb-5">
            ${[[tr('dashboard.total_books'),d.totalBooks,'book-open'],[tr('dashboard.pdf_requests'),d.totalRequests,'file-text'],[tr('dashboard.borrow_requests'),d.totalPhysicalRequests,'book'],[tr('dashboard.active_borrows'),d.totalBorrowed,'repeat']].map(x=>`<div class="stat"><div class="flex justify-between"><div><span class="text-sm text-gray-500">${x[0]}</span><strong>${x[1]}</strong></div><span class="stat-icon"><i data-feather="${x[2]}"></i></span></div></div>`).join('')}
        </div><div class="admin-dashboard-grid">
            <section class="panel admin-activity-panel"><div class="panel-head"><h2 class="font-black">${tr('dashboard.recent_activity')}</h2><small>${tr('dashboard.recent_count')}</small></div><div class="panel-body">${activities.length?activities.map(a=>`<div class="activity"><span class="stat-icon"><i data-feather="${a.type==='message'?'mail':a.type==='comment'?'message-circle':'book'}"></i></span><div><strong class="text-sm">${a.type==='message'?esc(tr('dashboard.message_from',{name:a.name||tr('dashboard.user_fallback')})):a.type==='comment'?esc(tr('dashboard.comment_for',{book:a.book_title})):esc(tr('dashboard.request_for',{book:a.book_title}))}</strong><p class="text-xs text-gray-500 mt-1">${date(a.created_at)}</p></div></div>`).join(''):empty(tr('dashboard.no_activity'))}</div></section>
            <aside class="panel admin-attention"><div class="panel-head"><h2 class="font-black">${tr('dashboard.needs_review')}</h2></div><div class="panel-body">
                <button type="button" data-go-section="digital"><span><strong>${tr('dashboard.pdf_requests')}</strong><small>${tr('dashboard.pdf_help')}</small></span><b>${d.totalRequests}</b></button>
                <button type="button" data-go-section="physical"><span><strong>${tr('dashboard.borrow_requests')}</strong><small>${tr('dashboard.borrow_help')}</small></span><b>${d.totalPhysicalRequests}</b></button>
                <button type="button" data-go-section="messages"><span><strong>${tr('dashboard.unread')}</strong><small>${tr('dashboard.unread_help')}</small></span><b>${d.unreadTotal}</b></button>
            </div></aside>
        </div>`;
        feather.replace();window.LIBRARY_PERSIAN_UI?.localize(content);
    }

    function renderBookRows(){
        const target=document.getElementById('adminBookTable');if(!target)return;
        const term=normalize(document.getElementById('adminBookSearch')?.value||'');
        const type=document.getElementById('adminBookType')?.value||'all';
        const sort=document.getElementById('adminBookSort')?.value||'newest';
        let rows=books.filter(book=>{
            const haystack=normalize([book.id,book.title,book.author,book.translator,book.publisher,book.nbok_category,book.nbok_category_path,book.category,book.library,book.tags?.join(' ')].join(' '));
            const typeMatches=type==='all'||(type==='physical'&&book.has_physical)||(type==='pdf'&&book.has_pdf)||(type==='available'&&Number(book.physical_available)>0);
            return typeMatches&&(!term||haystack.includes(term));
        });
        rows=[...rows].sort((a,b)=>sort==='title'?String(a.title).localeCompare(String(b.title),'fa'):sort==='stock'?Number(b.physical_available||0)-Number(a.physical_available||0):new Date(b.created_at)-new Date(a.created_at));
        const count=document.getElementById('adminBookResultCount');if(count)count.textContent=tr('books.result_count',{count:rows.length,total:books.length});
        target.innerHTML=rows.length?`<div class="overflow-auto"><table class="data-table"><thead><tr><th>${tr('books.cover')}</th><th>${tr('books.book')}</th><th>${tr('books.field.category')}</th><th>${tr('books.type')}</th><th>${tr('books.stock')}</th><th>${tr('books.actions')}</th></tr></thead><tbody>${rows.map(b=>`<tr><td><img class="book-thumb" src="${esc(b.cover_url||BOOK_FALLBACK)}" data-fallback-src="${esc(BOOK_FALLBACK)}" alt=""></td><td><strong>${esc(b.title)}</strong><div class="book-row-meta"><span>${esc(b.author)}</span>${b.publisher?`<span>${esc(b.publisher)}</span>`:''}<span>${tr('books.identifier',{id:b.id})}</span></div></td><td><strong class="admin-book-category">${esc(b.nbok_category||b.category||'-')}</strong>${b.nbok_category_path?`<small class="admin-book-category-path">${esc(b.nbok_category_path)}</small>`:''}</td><td>${b.has_physical?tr('books.physical'):''}${b.has_physical&&b.has_pdf?' + ':''}${b.has_pdf?'PDF':''}</td><td>${b.has_physical?tr('books.stock_value',{available:b.physical_available,total:b.physical_count}):'-'}</td><td><div class="flex gap-1"><button class="action-btn" data-edit-book="${b.id}" title="${tr('books.edit')}"><i data-feather="edit-2"></i></button><button class="action-btn danger" data-delete-book="${b.id}" title="${tr('books.delete')}"><i data-feather="trash-2"></i></button></div></td></tr>`).join('')}</tbody></table></div>`:empty(tr('books.empty'));
        bindImageFallbacks(target);feather.replace();window.LIBRARY_PERSIAN_UI?.localize(target);
    }

    async function loadBooks(){
        spinner();const [b,n]=await Promise.all([api('books'),api('nbok')]);books=b.data||[];nbokCategories=n.data||[];
        content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2 class="font-black">${tr('books.title')}</h2><p class="text-xs text-gray-500 mt-1">${tr('books.search_help')}</p></div></div><div class="admin-book-toolbar"><label class="admin-search"><i data-feather="search"></i><input id="adminBookSearch" type="search" autocomplete="off" placeholder="${tr('books.search_placeholder')}"></label><select id="adminBookType" aria-label="${tr('books.type_filter_aria')}"><option value="all">${tr('books.type_all')}</option><option value="physical">${tr('books.type_physical')}</option><option value="pdf">${tr('books.type_pdf')}</option><option value="available">${tr('books.type_available')}</option></select><select id="adminBookSort" aria-label="${tr('books.sort_aria')}"><option value="newest">${tr('books.sort_newest')}</option><option value="title">${tr('books.sort_title')}</option><option value="stock">${tr('books.sort_stock')}</option></select><strong id="adminBookResultCount" class="admin-result"></strong></div><div id="adminBookTable"></div></section>`;
        document.getElementById('adminBookSearch').addEventListener('input',renderBookRows);
        document.getElementById('adminBookType').addEventListener('change',renderBookRows);
        document.getElementById('adminBookSort').addEventListener('change',renderBookRows);
        renderBookRows();
    }

    function openBookForm(book={}){
        const editing=Boolean(book.id), type=book.has_pdf&&book.has_physical?'both':book.has_pdf?'pdf':'physical';
        openModal(`<div class="modal-head"><h2 class="font-black">${editing?tr('books.edit_title'):tr('dashboard.add_book')}</h2><button data-close class="action-btn"><i data-feather="x"></i></button></div><form id="bookForm" class="modal-body">
            <input type="hidden" name="id" value="${book.id||''}"><div class="form-grid">
            <div class="field"><label>${tr('books.field.title')}</label><input name="title" required value="${esc(book.title||'')}"></div>
            <div class="field"><label>${tr('books.field.author')}</label><input name="author" required value="${esc(book.author||'')}"></div>
            <div class="field"><label>${tr('books.field.translator')}</label><input name="translator" value="${esc(book.translator||'')}"></div>
            <div class="field"><label>${tr('books.field.publisher')}</label><input name="publisher" value="${esc(book.publisher||'')}"></div>
            <div class="field"><label>${tr('books.field.category')}</label><input type="hidden" name="nbok_category_id" id="bookNbokCategoryId" value="${esc(book.nbok_category_id||'')}"><input type="hidden" name="nbok_category_level" id="bookNbokCategoryLevel" value="${esc(book.nbok_category_level||'')}"><button type="button" id="bookNbokCategoryPicker" class="nbok-book-field"><span><strong id="bookNbokCategoryName">${esc(book.nbok_category||tr('no_category'))}</strong><small id="bookNbokCategoryPath">${esc(book.nbok_category_path||tr('categories.choose'))}</small></span><i data-feather="chevron-left"></i></button></div>
            <div class="field"><label>${tr('books.field.library')}</label><input name="library" value="${esc(book.library||'')}"></div>
            <div class="field"><label>${tr('books.field.type')}</label><select id="bookType" name="book_type"><option value="physical" ${type==='physical'?'selected':''}>${tr('books.type_only_physical')}</option><option value="pdf" ${type==='pdf'?'selected':''}>${tr('books.type_only_pdf')}</option><option value="both" ${type==='both'?'selected':''}>${tr('books.type_both')}</option></select></div>
            <div id="physicalFields" class="field"><label>${tr('books.field.count')}</label><input name="physical_count" type="number" min="0" value="${book.physical_count||1}"></div>
            <div id="locationField" class="field"><label>${tr('books.field.location')}</label><input name="physical_location" value="${esc(book.physical_location||'')}"></div>
            <div class="field"><label>${tr('books.field.cover_url')}</label><input name="cover_url" dir="ltr" value="${esc(book.cover_url||'')}"></div>
            <div class="field"><label>${tr('books.field.cover_upload')}</label><input name="cover" type="file" accept="image/*"></div>
            <div id="pdfFileField" class="field"><label>${tr('books.field.pdf_upload')}</label><input name="book_pdf" type="file" accept=".pdf"><small>${tr('books.pdf_private_help')}</small></div>
            <div class="field"><label>${tr('books.field.tags')}</label><input name="tags_text" value="${esc((book.tags||[]).join('، '))}"></div>
            <div class="field md:col-span-2"><label>${tr('books.field.summary')}</label><textarea name="summary" rows="4">${esc(book.summary||'')}</textarea></div></div>
            <div class="admin-actions justify-end mt-5"><button type="button" data-close class="admin-btn secondary">${tr('books.cancel')}</button><button class="admin-btn" type="submit">${tr('books.save')}</button></div></form>`);
        const bookTypeEl=document.getElementById('bookType'),physicalFieldsEl=document.getElementById('physicalFields'),locationFieldEl=document.getElementById('locationField'),pdfFileFieldEl=document.getElementById('pdfFileField');
        const toggle=()=>{const pdf=['pdf','both'].includes(bookTypeEl.value),physical=['physical','both'].includes(bookTypeEl.value);physicalFieldsEl.style.display=physical?'grid':'none';locationFieldEl.style.display=physical?'grid':'none';pdfFileFieldEl.style.display=pdf?'grid':'none'};bookTypeEl.addEventListener('change',toggle);toggle();
        const nbokIdEl=document.getElementById('bookNbokCategoryId'),nbokLevelEl=document.getElementById('bookNbokCategoryLevel'),nbokNameEl=document.getElementById('bookNbokCategoryName'),nbokPathEl=document.getElementById('bookNbokCategoryPath');
        const setNbokSelection=node=>{nbokIdEl.value=node?.row_id||'';nbokLevelEl.value=node?.level_code||'';nbokNameEl.textContent=node?.name||tr('no_category');nbokPathEl.textContent=node?.path_text||tr('categories.choose')};
        document.getElementById('bookNbokCategoryPicker').addEventListener('click',()=>openNbokPicker(setNbokSelection,nbokIdEl.value,nbokLevelEl.value));
        document.getElementById('bookForm').addEventListener('submit', async event => {
            event.preventDefault();
            const formData = new FormData(event.target);
            const id = String(formData.get('id') || '').trim();
            const tags = String(formData.get('tags_text') || '')
                .split(/[،,]/)
                .map(value => value.trim())
                .filter(Boolean);
            formData.delete('id');
            formData.delete('tags_text');
            formData.set('tags', JSON.stringify(tags));
            const endpoint = id ? `books/${id}/update` : 'books/add';
            const result = await api(endpoint, {method: 'POST', body: formData});
            notify(result.message, result.success);
            if (result.success) {
                closeModal();
                await loadBooks();
            }
        });
    }

    function renderNbokCategoryRows(){
        const target=document.getElementById('adminNbokCategoryListV25');if(!target)return;
        const term=normalize(document.getElementById('adminNbokSearchV25')?.value||'');
        const rows=flattenNbok(nbokCategories).filter(node=>!term||normalize(`${node.name} ${node.path_text}`).includes(term));
        const count=document.getElementById('adminNbokResultCountV25');if(count)count.textContent=tr('categories.result_count',{count:rows.length});
        target.innerHTML=rows.length?rows.map(node=>`<div class="admin-nbok-row" style="--nbok-depth:${node.depth}"><span class="admin-nbok-branch"></span><div class="admin-nbok-title"><strong>${esc(node.name)}</strong><small>${esc(node.path_text)}</small></div><span class="nbok-level-chip">${esc(tr('categories.level',{level:String(node.level_code||'').replace('L','')}))}</span>${node.book_count?`<span class="admin-nbok-count">${node.book_count} ${tr('books.book')}</span>`:''}</div>`).join(''):empty(tr('categories.empty'));
    }

    async function showCategories(){
        spinner();const d=await api('nbok');nbokCategories=d.data||[];
        content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2 class="font-black">${tr('categories.title')}</h2><p class="text-xs text-gray-500 mt-1">${tr('categories.help')}</p></div><button id="addCategory" class="admin-btn"><i data-feather="plus"></i>${tr('categories.add')}</button></div><div class="admin-nbok-toolbar"><label class="admin-search"><i data-feather="search"></i><input id="adminNbokSearchV25" type="search" autocomplete="off" placeholder="${tr('categories.search_placeholder')}"></label><strong id="adminNbokResultCountV25" class="admin-result"></strong></div><div id="adminNbokCategoryListV25" class="admin-nbok-list"></div></section>`;
        document.getElementById('adminNbokSearchV25').addEventListener('input',renderNbokCategoryRows);renderNbokCategoryRows();feather.replace();
    }

    function categoryForm(){
        openModal(`<div class="modal-head"><div><h2 class="font-black">${tr('categories.add_short')}</h2><p class="text-xs text-gray-500 mt-1">${tr('categories.add_help')}</p></div><button data-close class="action-btn"><i data-feather="x"></i></button></div><form id="categoryForm" class="modal-body"><div class="field"><label>${tr('categories.field.name')} *</label><input name="name" required maxlength="255"></div><div class="field mt-4"><label>${tr('categories.field.parent')}</label><select name="parent">${nbokParentOptions()}</select></div><div class="admin-actions justify-end mt-5"><button data-close type="button" class="admin-btn secondary">${tr('books.cancel')}</button><button class="admin-btn">${tr('categories.save')}</button></div></form>`);
        document.getElementById('categoryForm').addEventListener('submit',async event=>{event.preventDefault();const fd=new FormData(event.target);const parent=String(fd.get('parent')||'');const [parentRowId,parentLevel]=parent?parent.split('|'):['',''];const d=await api('nbok/create',{method:'POST',body:JSON.stringify({name:fd.get('name'),parent_row_id:parentRowId||null,parent_level:parentLevel||''})});notify(d.message,d.success);if(d.success){closeModal();showCategories()}});
    }

    async function showDigital(){spinner();const d=await api('book-requests');digitalRequests=d.data||[];content.innerHTML=`<section class="panel"><div class="panel-head"><h2 class="font-black">${tr('digital.title')}</h2></div><div class="overflow-auto">${digitalRequests.length?`<table class="data-table"><thead><tr><th>${tr('books.book')}</th><th>${tr('users.member_col')}</th><th>${tr('table.date')}</th><th>${tr('table.status')}</th><th>${tr('books.actions')}</th></tr></thead><tbody>${digitalRequests.map(r=>`<tr class="${r.is_read?'':'unread'}"><td><strong>${esc(r.book_title)}</strong><small class="block text-gray-500">${esc(r.book_author)}</small></td><td>${esc(r.name||r.email)}</td><td>${date(r.created_at)}</td><td>${status(r.status)}</td><td><div class="flex gap-1">${r.status==='pending'?`<button class="action-btn" data-approve-digital="${r.id}"><i data-feather="check"></i></button><button class="action-btn danger" data-reject-digital="${r.id}"><i data-feather="x"></i></button>`:''}<button class="action-btn danger" data-delete-digital="${r.id}"><i data-feather="trash-2"></i></button></div></td></tr>`).join('')}</tbody></table>`:empty(tr('requests.empty'))}</div></section>`;feather.replace();await api('book-requests/mark-read',{method:'POST'});loadCounts()}

    function borrowedRows(rows){return rows.length?rows.map(x=>`<tr class="${x.is_overdue?'bg-red-50':''}"><td><strong>${esc(x.book_title)}</strong><small class="block text-gray-500">${esc(x.book_author||'')}</small></td><td><strong>${esc(x.borrower_name)}</strong><small class="block text-gray-500" dir="ltr">${esc(x.borrower_email||'')}</small><small class="block text-gray-500" dir="ltr">${esc(x.borrower_phone||tr('borrow.no_phone'))}</small></td><td>${dateOnly(x.borrow_date)}</td><td>${dateOnly(x.return_date)}${x.is_overdue?` <small class="text-red-600">(${tr('borrow.overdue_days',{days:x.days_overdue})})</small>`:''}</td><td><div class="flex gap-1"><button class="action-btn" data-borrow-details="${x.id}" title="${tr('borrow.details')}"><i data-feather="eye"></i></button><button class="admin-btn" data-return="${x.id}">${tr('borrow.return')}</button></div></td></tr>`).join(''):''}
    function borrowDetails(item){openModal(`<div class="modal-head"><div><small class="text-gray-500">${tr('borrow.active_details')}</small><h2 class="font-black mt-1">${esc(item.book_title)}</h2></div><button data-close class="action-btn"><i data-feather="x"></i></button></div><div class="modal-body"><div class="admin-borrow-detail"><div><span>${tr('borrow.borrower')}</span><strong>${esc(item.borrower_name)}</strong></div><div><span>${tr('borrow.email')}</span><strong dir="ltr">${esc(item.borrower_email||'-')}</strong></div><div><span>${tr('borrow.phone')}</span><strong dir="ltr">${esc(item.borrower_phone||'-')}</strong></div><div><span>${tr('borrow.borrow_date')}</span><strong>${dateOnly(item.borrow_date)}</strong></div><div><span>${tr('borrow.return_date')}</span><strong>${dateOnly(item.return_date)}</strong></div><div><span>${tr('borrow.notes')}</span><strong>${esc(item.notes||tr('borrow.no_notes'))}</strong></div></div><div class="admin-actions justify-end mt-5"><button type="button" data-close class="admin-btn secondary">${tr('borrow.close')}</button><button type="button" class="admin-btn" data-return="${item.id}">${tr('borrow.return_book')}</button></div></div>`)}
    async function showPhysical(){spinner();const [r,b]=await Promise.all([api('physical-book-requests'),api('borrowed-books')]);physicalRequests=r.data||[];const borrowed=b.data||[];window.__activeBorrows=borrowed;content.innerHTML=`<div class="space-y-5"><section class="panel"><div class="panel-head"><h2 class="font-black">${tr('dashboard.borrow_requests')}</h2><small>${tr('borrow.review_title')}</small></div><div class="overflow-auto">${physicalRequests.length?`<table class="data-table"><thead><tr><th>${tr('books.book')}</th><th>${tr('borrow.requester')}</th><th>${tr('borrow.contact')}</th><th>${tr('table.status')}</th><th>${tr('books.actions')}</th></tr></thead><tbody>${physicalRequests.map(x=>`<tr class="${x.is_read?'':'unread'}"><td>${esc(x.book_title)}</td><td>${esc(x.name)}</td><td dir="ltr">${esc(x.phone)}</td><td>${status(x.status)}</td><td>${x.status==='pending'?`<button class="action-btn" data-approve-physical="${x.id}"><i data-feather="check"></i></button><button class="action-btn danger" data-reject-physical="${x.id}"><i data-feather="x"></i></button>`:'-'}</td></tr>`).join('')}</tbody></table>`:empty(tr('borrow.requests_empty'))}</div></section><section class="panel"><div class="panel-head"><div><h2 class="font-black">${tr('borrow.active_title')}</h2><small>${tr('borrow.active_help')}</small></div></div><div class="admin-borrow-toolbar"><label class="admin-search"><i data-feather="search"></i><input id="borrowedSearch" type="search" placeholder="${tr('borrow.search_placeholder')}" autocomplete="off"></label><strong id="borrowedCount" class="admin-result"></strong></div><div class="overflow-auto"><table class="data-table"><thead><tr><th>${tr('books.book')}</th><th>${tr('borrow.borrower_contact')}</th><th>${tr('borrow.borrow_date')}</th><th>${tr('borrow.return_date')}</th><th>${tr('books.actions')}</th></tr></thead><tbody id="borrowedTableBody">${borrowedRows(borrowed)}</tbody></table>${borrowed.length?'':'<div id="borrowedEmpty">'+empty(tr('borrow.active_empty'))+'</div>'}</div></section></div>`;const render=()=>{const term=normalize(document.getElementById('borrowedSearch')?.value||'');const rows=borrowed.filter(x=>normalize([x.book_title,x.book_author,x.borrower_name,x.borrower_email,x.borrower_phone].join(' ')).includes(term));const target=document.getElementById('borrowedTableBody');if(target)target.innerHTML=borrowedRows(rows);const count=document.getElementById('borrowedCount');if(count)count.textContent=`${rows.length} ${tr('borrow.active_status')}`;const emptyBox=document.getElementById('borrowedEmpty');if(emptyBox)emptyBox.style.display=rows.length?'none':'block';feather.replace()};document.getElementById('borrowedSearch')?.addEventListener('input',render);render();feather.replace();await api('physical-book-requests/mark-read',{method:'POST'});loadCounts()}

    function borrowForm(item){const today=new Date().toISOString().slice(0,10),next=new Date(Date.now()+14*86400000).toISOString().slice(0,10);openModal(`<div class="modal-head"><h2 class="font-black">${tr('borrow.submit')} «${esc(item.book_title)}»</h2><button data-close class="action-btn"><i data-feather="x"></i></button></div><form id="borrowForm" class="modal-body"><div class="form-grid"><div class="field"><label>${tr('borrow.borrow_date')}</label><input name="borrow_date" type="date" required value="${today}"></div><div class="field"><label>${tr('borrow.return_date')}</label><input name="return_date" type="date" required value="${next}"></div><div class="field md:col-span-2"><label>${tr('borrow.notes')}</label><textarea name="notes"></textarea></div></div><div class="admin-actions justify-end mt-5"><button data-close type="button" class="admin-btn secondary">${tr('books.cancel')}</button><button class="admin-btn">${tr('borrow.submit')}</button></div></form>`);document.getElementById('borrowForm').addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target);const d=await api('physical-book-requests/approve',{method:'POST',body:JSON.stringify({request_id:item.id,borrow_date:fd.get('borrow_date'),return_date:fd.get('return_date'),notes:fd.get('notes')})});notify(d.message,d.success);if(d.success){closeModal();showPhysical()}})}

    async function showMessages(){spinner();const d=await api('messages');messages=d.data||[];content.innerHTML=`<section class="panel"><div class="panel-head"><h2 class="font-black">${tr('messages.title')}</h2></div><div class="overflow-auto">${messages.length?`<table class="data-table"><thead><tr><th>${tr('messages.sender')}</th><th>${tr('messages.message')}</th><th>${tr('table.date')}</th><th>${tr('table.status')}</th><th>${tr('books.actions')}</th></tr></thead><tbody>${messages.map(m=>`<tr class="${m.is_read?'':'unread'}"><td><strong>${esc(m.name||tr('dashboard.user_fallback'))}</strong><small class="block text-gray-500">${esc(m.email||'')}</small></td><td>${esc(m.message).slice(0,80)}${m.message.length>80?'…':''}</td><td>${date(m.created_at)}</td><td>${m.admin_response?`<span class="status-chip status-approved">${tr('messages.answered')}</span>`:m.is_read?`<span class="status-chip status-pending">${tr('messages.read')}</span>`:`<span class="status-chip status-rejected">${tr('messages.new')}</span>`}</td><td><button class="action-btn" data-view-message="${m.id}"><i data-feather="eye"></i></button><button class="action-btn danger" data-delete-message="${m.id}"><i data-feather="trash-2"></i></button></td></tr>`).join('')}</tbody></table>`:empty(tr('messages.empty'))}</div></section>`;feather.replace();loadCounts()}
    async function messageModal(item){await api(`messages/${item.id}/mark-read`,{method:'POST'});openModal(`<div class="modal-head"><h2 class="font-black">${tr('messages.message')} ${esc(item.name||tr('dashboard.user_fallback'))}</h2><button data-close class="action-btn"><i data-feather="x"></i></button></div><div class="modal-body"><p class="text-sm leading-8 whitespace-pre-wrap bg-gray-50 p-4 rounded-xl">${esc(item.message)}</p>${item.admin_response?`<div class="mt-4 p-4 bg-emerald-50 rounded-xl"><strong>${tr('messages.saved_response')}</strong><p class="mt-2 text-sm">${esc(item.admin_response)}</p></div>`:''}<form id="replyForm" class="mt-5 field"><label>${tr('messages.admin_response')}</label><textarea name="response" required rows="4"></textarea><div class="admin-actions justify-end mt-3"><button class="admin-btn">${tr('messages.submit_response')}</button></div></form></div>`);document.getElementById('replyForm').addEventListener('submit',async e=>{e.preventDefault();const d=await api(`messages/${item.id}/reply`,{method:'POST',body:JSON.stringify({response:new FormData(e.target).get('response')})});notify(d.message,d.success);if(d.success){closeModal();showMessages()}});loadCounts()}

    async function showComments(){spinner();const d=await api('comments');const rows=d.data||[];content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2 class="font-black">${tr('comments.title')}</h2><p class="text-xs text-gray-500 mt-1">${tr('comments.help')}</p></div></div><div class="panel-body space-y-3">${rows.length?rows.map(c=>`<article class="comment-admin"><div class="flex justify-between gap-4"><div class="min-w-0"><strong>${esc(c.name)}</strong><small class="text-gray-500 mr-2">${esc(tr('comments.for_book',{book:c.book_title}))}</small><p class="mt-3 text-sm leading-7">${esc(c.text)}</p></div><div class="flex gap-1"><button class="action-btn" data-reply-comment="${c.id}" title="${tr('comments.admin_response')}"><i data-feather="corner-down-left"></i></button><button class="action-btn danger" data-delete-comment="${c.id}" title="${tr('books.delete')}"><i data-feather="trash-2"></i></button></div></div>${c.replies?.length?`<div class="mt-3 pr-4 border-r-2 border-emerald-200 text-sm space-y-2">${c.replies.map(r=>`<p class="bg-emerald-50 p-2 rounded-lg"><b>${esc(r.name)}:</b> ${esc(r.text)}</p>`).join('')}</div>`:''}</article>`).join(''):empty(tr('comments.empty'))}</div></section>`;feather.replace();content.dataset.comments=JSON.stringify(rows)}
    function commentReplyForm(item){openModal(`<div class="modal-head"><div><small class="text-gray-500">${tr('comments.reply_title')} ${esc(item.name)}</small><h2 class="font-black mt-1">${esc(item.book_title)}</h2></div><button data-close class="action-btn"><i data-feather="x"></i></button></div><div class="modal-body"><div class="p-4 rounded-xl bg-gray-50 text-sm leading-7">${esc(item.text)}</div><form id="commentReplyForm" class="field mt-5"><label>${tr('comments.reply_label')}</label><textarea name="response" required rows="4" placeholder="${tr('comments.reply_placeholder')}"></textarea><div class="admin-actions justify-end mt-3"><button type="button" data-close class="admin-btn secondary">${tr('books.cancel')}</button><button class="admin-btn">${tr('comments.submit')}</button></div></form></div>`);document.getElementById('commentReplyForm').addEventListener('submit',async e=>{e.preventDefault();const d=await api(`comments/${item.id}/reply`,{method:'POST',body:JSON.stringify({response:new FormData(e.target).get('response')})});notify(d.message,d.success);if(d.success){closeModal();showComments()}})}

    function userForm(item={}){openModal(`<div class="modal-head"><div><small class="text-gray-500">${tr('users.manage')}</small><h2 class="font-black mt-1">${tr('users.edit_title')}</h2></div><button data-close class="action-btn"><i data-feather="x"></i></button></div><form id="adminUserForm" class="modal-body"><div class="form-grid"><div class="field"><label>${tr('users.username')}</label><input name="username" required value="${esc(item.username||'')}"></div><div class="field"><label>${tr('users.email')}</label><input name="email" type="email" dir="ltr" required value="${esc(item.email||'')}"></div><div class="field"><label>${tr('users.first_name')}</label><input name="first_name" value="${esc(item.first_name||'')}"></div><div class="field"><label>${tr('users.last_name')}</label><input name="last_name" value="${esc(item.last_name||'')}"></div><div class="field"><label>${tr('borrow.phone')}</label><input name="phone" dir="ltr" value="${esc(item.phone||'')}"></div><div class="field"><label>${tr('users.access')}</label><select name="is_staff"><option value="0" ${!item.is_staff?'selected':''}>${tr('users.member')}</option><option value="1" ${item.is_staff?'selected':''}>${tr('users.admin')}</option></select></div><div class="field"><label>${tr('users.state')}</label><select name="is_active"><option value="1" ${item.is_active!==false?'selected':''}>${tr('users.active')}</option><option value="0" ${item.is_active===false?'selected':''}>${tr('users.inactive')}</option></select></div><div class="field"><label>${tr('users.password')}</label><input name="password" type="password" minlength="8" autocomplete="new-password" placeholder="${tr('users.password_placeholder')}"><small>${tr('users.password_help')}</small></div></div><div class="admin-actions justify-end mt-5"><button type="button" data-close class="admin-btn secondary">${tr('books.cancel')}</button><button class="admin-btn">${tr('users.save')}</button></div></form>`);document.getElementById('adminUserForm').addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target);const payload={username:fd.get('username'),email:fd.get('email'),first_name:fd.get('first_name'),last_name:fd.get('last_name'),phone:fd.get('phone'),is_staff:fd.get('is_staff')==='1',is_active:fd.get('is_active')==='1'};const id=item.id;const d=await api(`users/${id}/update`,{method:'POST',body:JSON.stringify(payload)});if(!d.success){notify(d.message,false);return}const password=String(fd.get('password')||'');if(password){const p=await api(`users/${id}/password`,{method:'POST',body:JSON.stringify({password})});if(!p.success){notify(p.message,false);return}}notify(password?tr('users.password_updated'):d.message,true);closeModal();showUsers()})}
    async function showUsers(){
        spinner();
        const d=await api('users');
        const rows=d.data||[];
        content.dataset.users=JSON.stringify(rows);
        content.innerHTML=`<section class="panel"><div class="panel-head"><div><h2 class="font-black">${tr('users.title')}</h2><p class="text-xs text-gray-500 mt-1">${tr('users.help')}</p></div></div><div class="admin-user-toolbar"><label class="admin-search"><i data-feather="search"></i><input id="adminUserSearch" type="search" placeholder="${tr('users.search_placeholder')}" autocomplete="off"></label><strong id="adminUserResultCount" class="admin-result"></strong></div><div class="overflow-auto"><table class="data-table"><thead><tr><th>${tr('users.member_col')}</th><th>${tr('users.contact_col')}</th><th>${tr('users.access')}</th><th>${tr('table.status')}</th><th>${tr('users.requests_col')}</th><th>${tr('books.actions')}</th></tr></thead><tbody id="adminUserTable"></tbody></table></div></section>`;
        const render=()=>{
            const term=normalize(document.getElementById('adminUserSearch')?.value||'');
            const filtered=rows.filter(u=>normalize([u.name,u.username,u.email,u.phone].join(' ')).includes(term));
            const target=document.getElementById('adminUserTable');
            target.innerHTML=filtered.map(u=>{
                const access=u.is_superuser
                    ? `<span class="status-chip status-approved">${tr('users.super_admin')}</span>`
                    : u.is_staff
                        ? `<span class="status-chip status-approved">${tr('users.admin')}</span>`
                        : `<span class="status-chip status-pending">${tr('users.member_col')}</span>`;
                const state=u.is_active
                    ? `<span class="status-chip status-approved">${tr('users.active')}</span>`
                    : `<span class="status-chip status-rejected">${tr('users.inactive')}</span>`;
                const deleteButton=u.can_delete
                    ? `<button class="action-btn danger" data-delete-user="${u.id}" title="${tr('books.delete')}"><i data-feather="trash-2"></i></button>`
                    : '';
                return `<tr><td><strong>${esc(u.name)}</strong><small class="block text-gray-500">${esc(u.username)}</small></td><td dir="ltr"><div>${esc(u.email||'-')}</div><small class="text-gray-500">${esc(u.phone||'-')}</small></td><td>${access}</td><td>${state}</td><td>${u.request_count}</td><td><div class="flex gap-1"><button class="action-btn" data-edit-user="${u.id}" title="${tr('books.edit')}"><i data-feather="edit-2"></i></button>${deleteButton}</div></td></tr>`;
            }).join('')||`<tr><td colspan="6">${empty(tr('users.empty'))}</td></tr>`;
            const count=document.getElementById('adminUserResultCount');
            if(count) count.textContent=tr('users.count',{count:filtered.length});
            feather.replace();
            window.LIBRARY_PERSIAN_UI?.localize(content);
        };
        document.getElementById('adminUserSearch').addEventListener('input',render);
        render();
    }

    const sections={dashboard:[tr('sections.dashboard'),showDashboard],books:[tr('sections.books'),loadBooks],categories:[tr('sections.categories'),showCategories],digital:[tr('sections.digital'),showDigital],physical:[tr('sections.physical'),showPhysical],messages:[tr('sections.messages'),showMessages],comments:[tr('comments.title'),showComments],users:[tr('users.title'),showUsers]};
    async function navigate(name){document.querySelectorAll('#adminNav button').forEach(b=>b.classList.toggle('active',b.dataset.section===name));content.dataset.section=name;title.textContent=sections[name][0];actions.innerHTML=name==='books'?`<button id="openUploader" class="admin-btn amber"><i data-feather="upload-cloud"></i>${tr('actions.upload')}</button><button id="openImport" class="admin-btn purple"><i data-feather="file-plus"></i>${tr('actions.import')}</button><button id="addBook" class="admin-btn"><i data-feather="plus"></i>${tr('actions.add_book')}</button>`:'';feather.replace();setSidebarOpen(false);await sections[name][1]();prepareResponsiveTables()}
    document.getElementById('adminNav').addEventListener('click',e=>{const b=e.target.closest('[data-section]');if(b)navigate(b.dataset.section)});
    document.getElementById('mobileMenu').addEventListener('click',()=>setSidebarOpen(!sidebar.classList.contains('open')));
    sidebarBackdrop.addEventListener('click',()=>setSidebarOpen(false));
    document.addEventListener('click',async e=>{
        const go=e.target.closest('[data-go-section]');if(go){navigate(go.dataset.goSection);return}
        if(e.target.closest('[data-add-book-quick]')){await navigate('books');openBookForm();return}
        if(e.target.closest('#addBook')) openBookForm();
        if(e.target.closest('#openUploader')) window.open(UPLOAD_PAGE_URL,'_blank','noopener');
        if(e.target.closest('#openImport')){openModal(`<div class="modal-head"><h2 class="font-black">${tr('import.title')}</h2><button data-close class="action-btn"><i data-feather="x"></i></button></div><form id="importForm" class="modal-body"><div class="p-4 bg-blue-50 rounded-xl text-sm leading-7 mb-4">${tr('import.help')}<br><a href="${esc(IMPORT_TEMPLATE_URL)}" class="font-black text-blue-700">${tr('import.download_template')}</a></div><label class="admin-file-drop"><strong>${tr('import.file')}</strong><input id="importExcelFile" name="excel" type="file" accept=".xlsx" required><span id="importExcelName">${tr('import.none_selected')}</span></label><div class="admin-actions justify-end mt-4"><button class="admin-btn purple">${tr('import.start')}</button></div></form>`);const file=document.getElementById('importExcelFile'),name=document.getElementById('importExcelName');file?.addEventListener('change',()=>{name.textContent=file.files?.[0]?.name||tr('import.none_selected')})}
        const edit=e.target.closest('[data-edit-book]');if(edit)openBookForm(books.find(x=>x.id==edit.dataset.editBook)||{});
        const del=e.target.closest('[data-delete-book]');if(del&&confirm(tr('confirm.delete_book'))){const d=await api(`books/${del.dataset.deleteBook}/delete`,{method:'POST'});notify(d.message,d.success);if(d.success)loadBooks()}
        if(e.target.closest('#addCategory')) categoryForm();
        const ad=e.target.closest('[data-approve-digital]');if(ad&&confirm(tr('confirm.approve_digital'))){const d=await api(`book-requests/${ad.dataset.approveDigital}/approve`,{method:'POST'});notify(d.message,d.success);showDigital()}
        const rd=e.target.closest('[data-reject-digital]');if(rd&&confirm(tr('confirm.reject_request'))){const d=await api(`book-requests/${rd.dataset.rejectDigital}/reject`,{method:'POST'});notify(d.message,d.success);showDigital()}
        const dd=e.target.closest('[data-delete-digital]');if(dd&&confirm(tr('confirm.delete_request'))){const d=await api(`book-requests/${dd.dataset.deleteDigital}/delete`,{method:'POST'});notify(d.message,d.success);showDigital()}
        const ap=e.target.closest('[data-approve-physical]');if(ap)borrowForm(physicalRequests.find(x=>x.id==ap.dataset.approvePhysical));
        const rp=e.target.closest('[data-reject-physical]');if(rp&&confirm(tr('confirm.reject_borrow'))){const d=await api(`physical-book-requests/${rp.dataset.rejectPhysical}/reject`,{method:'POST'});notify(d.message,d.success);showPhysical()}
        const borrowDetail=e.target.closest('[data-borrow-details]');if(borrowDetail){const item=(window.__activeBorrows||[]).find(x=>String(x.id)===String(borrowDetail.dataset.borrowDetails));if(item)borrowDetails(item)}
        const ret=e.target.closest('[data-return]');if(ret&&confirm(tr('confirm.return_book'))){const d=await api(`books/${ret.dataset.return}/return`,{method:'POST'});notify(d.message,d.success);if(d.success){closeModal();showPhysical()}}
        const vm=e.target.closest('[data-view-message]');if(vm)messageModal(messages.find(x=>x.id==vm.dataset.viewMessage));
        const dm=e.target.closest('[data-delete-message]');if(dm&&confirm(tr('confirm.delete_message'))){const d=await api(`messages/${dm.dataset.deleteMessage}/delete`,{method:'POST'});notify(d.message,d.success);showMessages()}
        const rcom=e.target.closest('[data-reply-comment]');if(rcom){const rows=JSON.parse(content.dataset.comments||'[]');const item=rows.find(x=>x.id==rcom.dataset.replyComment);if(item)commentReplyForm(item)}
        const dcom=e.target.closest('[data-delete-comment]');if(dcom&&confirm(tr('confirm.delete_comment'))){const d=await api(`comments/${dcom.dataset.deleteComment}/delete`,{method:'POST'});notify(d.message,d.success);showComments()}
        const editUser=e.target.closest('[data-edit-user]');if(editUser){const rows=JSON.parse(content.dataset.users||'[]');const item=rows.find(x=>String(x.id)===String(editUser.dataset.editUser));if(item)userForm(item)}
        const deleteUser=e.target.closest('[data-delete-user]');if(deleteUser&&confirm(tr('confirm.delete_user'))){const d=await api(`users/${deleteUser.dataset.deleteUser}/delete`,{method:'POST'});notify(d.message,d.success);if(d.success)showUsers()}
    });
    async function pollImportJob(jobId){
        for(let attempt=0;attempt<120;attempt+=1){
            const job=await api(`book-imports/${jobId}`);
            if(job.status==='completed'){
                notify(job.message,true);
                if(job.result?.errors?.length) alert(job.result.errors.join('\n'));
                loadBooks();
                return;
            }
            if(job.status==='failed'){notify(job.message||tr('import.failed'),false);return}
            await new Promise(resolve=>setTimeout(resolve,2000));
        }
        notify(tr('import.pending'),true);
    }
    document.addEventListener('submit',async e=>{if(e.target.id==='importForm'){e.preventDefault();const d=await api('books/import',{method:'POST',body:new FormData(e.target)});notify(d.message,d.success);if(!d.success)return;if(d.status==='completed'){if(d.result?.errors?.length)alert(d.result.errors.join('\n'));closeModal();loadBooks();return}closeModal();pollImportJob(d.id)}});
    feather.replace();loadCounts();navigate('dashboard');setInterval(loadCounts,60000);
})();
