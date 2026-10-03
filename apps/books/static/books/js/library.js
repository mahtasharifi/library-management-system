'use strict';

    const root = document.body;
    async function loadTranslations() {
        const response = await fetch(root.dataset.translationsUrl || '', { headers: { 'Accept': 'application/json' } });
        if (!response.ok) throw new Error(`translation bundle ${response.status}`);
        const payload = await response.json();
        return payload.translations || {};
    }
    const translations = await loadTranslations();
    const tr = (key, params = {}) => {
        const template = translations[key];
        if (typeof template !== 'string') throw new Error(`Missing translation: js.library.${key}`);
        return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_, name) => String(params[name] ?? ''));
    };
    const config = {
        catalogUrl: root.dataset.catalogUrl || '',
        apiBase: (root.dataset.libraryApiBase || '').replace(/books\/?$/, ''),
        homeUrl: root.dataset.homeUrl || '',
        bookDetailUrlTemplate: root.dataset.bookDetailUrlTemplate || '',
        fallbackCover: root.dataset.fallbackCover || '',
        user: {
            name: root.dataset.userName || '',
            email: root.dataset.userEmail || '',
            phone: root.dataset.userPhone || '',
        },
    };
    const page = document.body.dataset.libraryPage;
    const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
    const csrf = csrfInput ? csrfInput.value : '';
    const state = {
        categories: [],
        categoryMap: new Map(),
        visibleBooks: [],
        activeBook: null,
        detailBook: null,
        catalogPage: 1,
        totalPages: 1,
    };
    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
    const esc = (value = '') => String(value ?? '').replace(/[&<>'"]/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    })[char]);
    const toFa = (value) => new Intl.NumberFormat('fa-IR').format(Number(value || 0));
    const toFaDecimal = (value) => new Intl.NumberFormat('fa-IR', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
    }).format(Number(value || 0));

    const detailBookData = document.getElementById('detailBookData');
    if (detailBookData) {
        try {
            state.detailBook = JSON.parse(detailBookData.textContent);
            state.visibleBooks = [state.detailBook];
            state.activeBook = state.detailBook;
        } catch (error) {
            state.detailBook = null;
        }
    }

    function refreshIcons() {
        if (window.feather) window.feather.replace();
    }

    async function api(endpoint, options = {}) {
        const raw = endpoint.replace(/^\/+|\/+$/g, '');
        const questionIndex = raw.indexOf('?');
        const path = questionIndex === -1 ? raw : raw.slice(0, questionIndex);
        const query = questionIndex === -1 ? '' : raw.slice(questionIndex + 1);
        const url = `${config.apiBase}${path}/${query ? `?${query}` : ''}`;
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'X-CSRFToken': csrf,
                    'Content-Type': 'application/json',
                    ...(options.headers || {}),
                },
            });
            let data;
            try {
                data = await response.json();
            } catch (error) {
                if (response.status === 403) {
                    return { success: false, message: tr('session_expired') };
                }
                return { success: false, message: tr('invalid_response') };
            }
            if (!response.ok) {
                const fallback = response.status === 401
                    ? tr('authentication_required')
                    : tr('server_error', { status: response.status });
                return { success: false, message: data.message || fallback };
            }
            return data;
        } catch (error) {
            return { success: false, message: tr('server_unreachable') };
        }
    }

    function notify(message, success = true) {
        const toast = $('#toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = `library-toast show ${success ? '' : 'error'}`;
        clearTimeout(notify.timer);
        notify.timer = setTimeout(() => { toast.className = 'library-toast'; }, 3800);
    }

    function openModal(html, wide = false) {
        const backdrop = $('#modalBackdrop');
        const content = $('#modalContent');
        if (!backdrop || !content) return;
        content.className = `library-modal ${wide ? 'wide' : ''}`;
        content.innerHTML = html;
        backdrop.classList.remove('hidden');
        backdrop.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        refreshIcons();
    }

    function closeModal() {
        const backdrop = $('#modalBackdrop');
        const content = $('#modalContent');
        if (!backdrop || !content) return;
        backdrop.classList.add('hidden');
        backdrop.setAttribute('aria-hidden', 'true');
        content.innerHTML = '';
        document.body.style.overflow = '';
        state.activeBook = null;
    }

    function flattenCategories(nodes, parent = null, level = 0, result = []) {
        nodes.forEach((node) => {
            node.parentNode = parent;
            node.level = level;
            state.categoryMap.set(String(node.id), node);
            result.push(node);
            flattenCategories(node.children || [], node, level + 1, result);
        });
        return result;
    }

    function categoryPath(category) {
        const path = [];
        let current = category;
        while (current) {
            path.unshift(current);
            current = current.parentNode;
        }
        return path;
    }

    function categoryUrl(id) {
        return `${config.catalogUrl}?category=${encodeURIComponent(id)}`;
    }

    function bookAvailability(book) {
        if (!book.has_physical) return book.has_pdf ? tr('availability.digital') : tr('availability.unknown');
        const total = Number(book.physical_count || 0);
        const available = Number(book.physical_available || 0);
        const borrowed = Math.max(0, total - available);
        if (borrowed > 0 && available > 0) return tr('availability.mixed', { available: toFa(available), borrowed: toFa(borrowed) });
        if (borrowed > 0) return tr('availability.borrowed');
        return tr('availability.available');
    }

    function bookshelfBook(book, index) {
        const seed = Math.abs(Number(book.id) || index + 1);
        const rotation = [-2, -1, 0, 1, 2][seed % 5];
        // Store a concrete height so the flex shelf remains stable even when
        // its parent only has a min-height (percentage heights would collapse).
        const height = 208 + (seed % 6) * 12;
        const widthScale = (0.84 + (seed % 5) * 0.06).toFixed(2);
        const hue = 115 + (seed % 8) * 27;
        const borrowed = book.has_physical && Number(book.physical_available || 0) < Number(book.physical_count || 0);
        const available = book.has_physical && Number(book.physical_available || 0) > 0;
        const status = bookAvailability(book);
        const statusClass = borrowed ? 'borrowed' : available ? 'available' : 'digital';
        return `<article class="shelf-preview-book" data-book-id="${book.id}" tabindex="0" style="--book-rotation:${rotation}deg;--book-height:${height}px;--book-scale:${widthScale};--book-hue:${hue}" title="${esc(book.title)}">
            <div class="shelf-preview-spine is-placeholder">
                <span class="shelf-preview-title">${esc(book.title)}</span>
                <span class="shelf-preview-mark"></span>
            </div>
            <div class="shelf-book-popover">
                <div class="shelf-book-popover-cover is-placeholder"><span>${esc(book.title.slice(0, 1) || 'K')}</span></div>
                <div class="shelf-book-popover-copy"><small>${esc(book.category || tr('book.no_category'))}</small><strong>${esc(book.title)}</strong><span>${esc(book.author || tr('book.unknown_author'))}</span><b class="shelf-status ${statusClass}">${esc(status)}</b><button type="button" data-book-detail="${book.id}">${tr('book.view_details')} <i data-feather="arrow-left"></i></button></div>
            </div>
        </article>`;
    }

    function bookshelfRows(books) {
        if (!books.length) return '';
        const rowSize = window.innerWidth <= 580 ? 6 : window.innerWidth <= 820 ? 8 : 12;
        const rows = [];
        for (let index = 0; index < books.length; index += rowSize) {
            const chunk = books.slice(index, index + rowSize);
            rows.push(`<section class="bookshelf-row" aria-label="${esc(tr('shelf.aria', { number: toFa(rows.length + 1) }))}"><div class="bookshelf-books">${chunk.map((book, offset) => bookshelfBook(book, index + offset)).join('')}</div><div class="bookshelf-plank"></div></section>`);
        }
        return rows.join('');
    }

    function commentsHtml(comments = []) {
        if (!comments.length) return `<div class="library-comments-empty">${esc(tr('comments.empty'))}</div>`;
        const faDate = (value) => window.LIBRARY_PERSIAN_UI ? window.LIBRARY_PERSIAN_UI.formatDate(value, false) : esc(value);
        return comments.map((comment) => `<article class="library-comment"><div><span>${esc(comment.name).slice(0, 1)}</span><strong>${esc(comment.name)}</strong><time>${faDate(comment.date)}</time></div><p>${esc(comment.text)}</p>${comment.replies?.length ? `<section>${comment.replies.map((reply) => `<div class="library-admin-reply"><i data-feather="corner-down-left"></i><div><strong>${esc(reply.name)}</strong><p>${esc(reply.text)}</p></div></div>`).join('')}</section>` : ''}</article>`).join('');
    }

    function openBook(bookId) {
        if (!config.bookDetailUrlTemplate) return;
        window.location.assign(config.bookDetailUrlTemplate.replace('/0/', `/${bookId}/`));
    }

    let bookPulloutActive = false;
    let bookPulloutTimer = null;

    function cleanupBookPullout() {
        window.clearTimeout(bookPulloutTimer);
        bookPulloutTimer = null;
        bookPulloutActive = false;
        hideShelfPreview();
        $$('.book-pullout-scene, .book-pullout-clone, .book-pullout-model').forEach((element) => element.remove());
        $$('.catalog-shelf-book.is-departing').forEach((book) => book.classList.remove('is-departing'));
        $$('.shelf-slot.is-empty').forEach((slot) => slot.classList.remove('is-empty'));
        const status = $('#bookTransitionStatus');
        if (status) status.textContent = '';
    }

    function shelfPreviewPosition(preview, link) {
        const rect = link.getBoundingClientRect();
        const margin = 14;
        const gap = 16;
        const width = Math.min(300, window.innerWidth - (margin * 2));
        preview.style.width = `${width}px`;
        preview.style.left = `${margin}px`;
        preview.style.top = `${margin}px`;
        preview.classList.add('is-measuring');
        const height = Math.min(preview.offsetHeight || 190, window.innerHeight - (margin * 2));
        preview.classList.remove('is-measuring');
        let left = rect.left - width - gap;
        if (left < margin) left = rect.right + gap;
        if (left + width > window.innerWidth - margin) left = Math.max(margin, window.innerWidth - width - margin);
        let top = rect.top + (rect.height - height) / 2;
        top = Math.max(margin, Math.min(window.innerHeight - height - margin, top));
        preview.style.left = `${Math.round(left)}px`;
        preview.style.top = `${Math.round(top)}px`;
    }

    function ensureShelfPreviewPortal() {
        let preview = document.getElementById('shelfBookPreviewPortalV17');
        if (!preview) {
            preview = document.createElement('aside');
            preview.id = 'shelfBookPreviewPortalV17';
            preview.className = 'shelf-book-preview-portal';
            preview.setAttribute('aria-hidden', 'true');
            document.body.append(preview);
        }
        return preview;
    }

    function showShelfPreview(link) {
        if (!window.matchMedia('(hover: hover) and (pointer: fine) and (min-width: 721px)').matches) return;
        const preview = ensureShelfPreviewPortal();
        const title = link.dataset.bookTitle || '';
        const author = link.dataset.bookAuthor || tr('book.unknown_author');
        const category = link.dataset.bookCategory || tr('book.no_category');
        const status = link.dataset.bookStatus || '';
        const statusClass = link.dataset.bookStatusClass || 'unknown';
        preview.innerHTML = `<strong>${esc(title)}</strong><span>${esc(tr('preview.author', { author }))}</span><span>${esc(tr('preview.category', { category }))}</span><b class="shelf-status ${esc(statusClass)}">${esc(status)}</b>`;
        preview.setAttribute('aria-hidden', 'false');
        shelfPreviewPosition(preview, link);
        preview.classList.add('is-visible');
    }

    function hideShelfPreview() {
        const preview = document.getElementById('shelfBookPreviewPortalV17');
        preview?.classList.remove('is-visible');
        preview?.setAttribute('aria-hidden', 'true');
    }

    function buildBookPulloutScene(link) {
        const rect = link.getBoundingClientRect();
        const computed = window.getComputedStyle(link);
        const coverWidth = Math.max(82, Math.min(142, rect.height * .66));
        const roomRight = window.innerWidth - rect.right;
        const roomLeft = rect.left;
        const direction = roomRight >= coverWidth + 30 ? 1 : (roomLeft >= coverWidth + 30 ? -1 : (roomRight >= roomLeft ? 1 : -1));

        const scene = document.createElement('div');
        scene.className = 'book-pullout-scene';
        scene.setAttribute('aria-hidden', 'true');
        scene.style.left = `${rect.left}px`;
        scene.style.top = `${rect.top}px`;
        scene.style.width = `${rect.width}px`;
        scene.style.height = `${rect.height}px`;

        const model = document.createElement('div');
        model.className = `book-pullout-model ${direction > 0 ? 'opens-right' : 'opens-left'}`;
        model.style.setProperty('--pull-direction', String(direction));
        model.style.setProperty('--pull-cover-width', `${coverWidth}px`);
        model.style.setProperty('--pull-spine-width', `${rect.width}px`);
        model.style.setProperty('--pull-book-color', computed.getPropertyValue('--book-color').trim() || '#355f52');
        model.style.setProperty('--pull-book-dark', computed.getPropertyValue('--book-dark').trim() || '#213f37');

        const spine = link.cloneNode(true);
        spine.removeAttribute('href');
        spine.removeAttribute('aria-describedby');
        spine.removeAttribute('aria-label');
        spine.removeAttribute('data-book-pullout');
        spine.querySelectorAll('[id]').forEach((element) => element.removeAttribute('id'));
        spine.querySelector('.shelf-book-tooltip')?.remove();
        spine.classList.add('book-pullout-clone', 'book-pullout-spine');
        spine.style.width = `${rect.width}px`;
        spine.style.height = `${rect.height}px`;

        const volume = document.createElement('div');
        volume.className = 'book-pullout-volume';
        volume.style.transform = `rotateY(${direction * 90}deg)`;

        const backCover = document.createElement('span');
        backCover.className = 'book-pullout-back-cover';

        const pages = document.createElement('span');
        pages.className = 'book-pullout-pages';
        const pageEdge = document.createElement('span');
        pageEdge.className = 'book-pullout-page-edge';
        pages.append(pageEdge);

        const frontCover = document.createElement('span');
        frontCover.className = 'book-pullout-front-cover';
        const coverTitle = document.createElement('strong');
        coverTitle.className = 'book-pullout-cover-title';
        coverTitle.textContent = link.dataset.bookTitle || '';
        const coverMark = document.createElement('small');
        coverMark.className = 'book-pullout-cover-mark';
        coverMark.textContent = tr('app_name');
        frontCover.append(coverTitle, coverMark);

        volume.append(backCover, pages, frontCover);
        model.append(spine, volume);
        scene.append(model);
        document.body.append(scene);
        return { rect, direction, scene, model, frontCover, pages };
    }

    function pullBookToDetail(link) {
        if (bookPulloutActive || !link.href) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || typeof link.animate !== 'function') {
            window.location.assign(link.href);
            return;
        }

        bookPulloutActive = true;
        hideShelfPreview();
        const slot = link.closest('[data-shelf-book-id]');
        const { direction, model, frontCover, pages } = buildBookPulloutScene(link);
        const isMobile = window.innerWidth <= 720;
        const duration = isMobile ? 980 : 1120;
        const pullDepth = isMobile ? 92 : 132;
        const turnAngle = -direction * (isMobile ? 73 : 78);
        const driftX = direction * (isMobile ? 2 : 5);
        const lift = isMobile ? -3 : -6;
        const openAngle = -direction * (isMobile ? 52 : 60);

        const status = $('#bookTransitionStatus');
        if (status) status.textContent = tr('shelf.opening_status', { title: link.dataset.bookTitle || '' });

        window.setTimeout(() => {
            link.classList.add('is-departing');
            slot?.classList.add('is-empty');
        }, Math.round(duration * .10));

        const modelAnimation = model.animate([
            { transform: 'translate3d(0, 0, 0) rotateY(0deg) rotateX(0deg)', offset: 0 },
            { transform: 'translate3d(0, -1px, 24px) rotateY(0deg) rotateX(-.2deg)', offset: .14 },
            { transform: `translate3d(${driftX * .35}px, ${lift * .45}px, ${pullDepth * .62}px) rotateY(${turnAngle * .42}deg) rotateX(-.55deg)`, offset: .43 },
            { transform: `translate3d(${driftX}px, ${lift}px, ${pullDepth}px) rotateY(${turnAngle}deg) rotateX(-1deg)`, offset: .66 },
            { transform: `translate3d(${driftX}px, ${lift}px, ${pullDepth + (isMobile ? 5 : 8)}px) rotateY(${turnAngle}deg) rotateX(-1deg)`, offset: 1 },
        ], {
            duration,
            easing: 'cubic-bezier(.18,.76,.16,1)',
            fill: 'forwards',
        });

        frontCover.animate([
            { transform: 'translateZ(4px) rotateY(0deg)', offset: 0 },
            { transform: 'translateZ(4px) rotateY(0deg)', offset: .60 },
            { transform: `translateZ(4px) rotateY(${openAngle * .42}deg)`, offset: .76 },
            { transform: `translateZ(4px) rotateY(${openAngle}deg)`, offset: .94 },
            { transform: `translateZ(4px) rotateY(${openAngle}deg)`, offset: 1 },
        ], {
            duration,
            easing: 'cubic-bezier(.22,.72,.18,1)',
            fill: 'forwards',
        });

        pages.animate([
            { transform: 'translateZ(1px)', filter: 'brightness(.96)', offset: 0 },
            { transform: 'translateZ(1px)', filter: 'brightness(.96)', offset: .62 },
            { transform: 'translateZ(2px)', filter: 'brightness(1)', offset: .82 },
            { transform: 'translateZ(2px)', filter: 'brightness(1)', offset: 1 },
        ], { duration, easing: 'ease-out', fill: 'forwards' });

        let navigated = false;
        const navigate = () => {
            if (navigated) return;
            navigated = true;
            window.location.assign(link.href);
        };
        modelAnimation.finished.then(() => window.setTimeout(navigate, 70)).catch(navigate);
        bookPulloutTimer = window.setTimeout(navigate, duration + 240);
    }

    function returnBookToShelf() {
        return;
    }

    function openPhysicalRequest(bookId) {
        const book = state.visibleBooks.find((item) => Number(item.id) === Number(bookId));
        if (!book) return;
        const unavailable = Number(book.physical_available) <= 0;
        openModal(`<button class="library-modal-close" data-close-modal aria-label="${tr('modal.close')}"><i data-feather="x"></i></button><div class="library-form-head"><span><i data-feather="book"></i></span><div><small>${unavailable ? tr('physical.unavailable_kicker') : tr('physical.kicker')}</small><h2>${esc(book.title)}</h2></div></div><form id="physicalRequestForm" class="library-form"><input type="hidden" name="book_id" value="${book.id}"><label>${tr('physical.full_name')}<input name="name" required value="${esc(config.user?.name || '')}"></label><label>${tr('physical.response_email')}<input name="email" type="email" dir="ltr" required value="${esc(config.user?.email || '')}"><small>${tr('physical.account_email_help')}</small></label><label>${tr('physical.phone')}<input name="phone" dir="ltr" required value="${esc(config.user?.phone || '')}"></label><label>${tr('physical.notes')}<textarea name="message" rows="3" placeholder="${tr('physical.notes_placeholder')}"></textarea></label><button type="submit">${unavailable ? tr('physical.notify_submit') : tr('physical.borrow_submit')}</button></form>`);
    }

    function openNewBookRequest() {
        openModal(`<button class="library-modal-close" data-close-modal aria-label="${tr('modal.close')}"><i data-feather="x"></i></button><div class="library-form-head"><span><i data-feather="plus"></i></span><div><small>${tr('new_book.kicker')}</small><h2>${tr('new_book.title')}</h2></div></div><form id="newBookRequestForm" class="library-form"><label>${tr('new_book.subject')}<textarea name="message" required rows="4" placeholder="${tr('new_book.subject_placeholder')}"></textarea></label><label>${tr('new_book.reason')}<textarea name="reason" rows="3" placeholder="${tr('new_book.reason_placeholder')}"></textarea></label><label>${tr('physical.response_email')}<input name="email" type="email" dir="ltr" required value="${esc(config.user?.email || '')}"><small>${tr('new_book.email_help')}</small></label><button type="submit">${tr('new_book.submit')}</button></form>`);
    }

    function openContactForm() {
        openModal(`<button class="library-modal-close" data-close-modal aria-label="${tr('modal.close')}"><i data-feather="x"></i></button><div class="library-form-head"><span><i data-feather="message-circle"></i></span><div><small>${tr('contact.kicker')}</small><h2>${tr('contact.title')}</h2></div></div><form id="contactSupportForm" class="library-form"><label>${tr('contact.topic')}<select name="topic" required><option value="general">${tr('contact.topic.general')}</option><option value="borrow_help">${tr('contact.topic.borrow')}</option><option value="technical">${tr('contact.topic.technical')}</option><option value="feedback">${tr('contact.topic.feedback')}</option></select></label><label>${tr('contact.subject')}<input name="subject" required maxlength="140" placeholder="${tr('contact.subject_placeholder')}"></label><label>${tr('contact.message')}<textarea name="message" required rows="5" placeholder="${tr('contact.message_placeholder')}"></textarea></label><label>${tr('physical.response_email')}<input name="email" type="email" dir="ltr" required value="${esc(config.user?.email || '')}"><small>${tr('contact.email_help')}</small></label><button type="submit">${tr('contact.submit')}</button></form>`);
    }

    function openPdfRequest(bookId) {
        const book = state.visibleBooks.find((item) => Number(item.id) === Number(bookId));
        if (!book) return;
        openModal(`<button class="library-modal-close" data-close-modal aria-label="${tr('modal.close')}"><i data-feather="x"></i></button><div class="library-form-head"><span><i data-feather="file-text"></i></span><div><small>${tr('pdf.kicker')}</small><h2>${esc(tr('pdf.title', { title: book.title }))}</h2></div></div><form id="pdfRequestForm" class="library-form"><input type="hidden" name="book_id" value="${book.id}"><label>${tr('pdf.email')}<input name="email" type="email" dir="ltr" required value="${esc(config.user?.email || '')}"><small>${tr('contact.email_help')}</small></label><button type="submit">${tr('pdf.submit')}</button></form>`);
    }

    function homeCategoryCard(category, index) {
        return `<a href="${categoryUrl(category.id)}" class="home-category-card">
            <span>${String(index + 1).padStart(2, '0')}</span>
            <div><strong>${esc(category.name)}</strong><small>${category.children?.length ? tr('category.children', { count: toFa(category.children.length) }) : tr('category.view_books')}</small></div>
            <b>${toFa(category.book_count)}<small>${tr('category.book_count')}</small></b>
            <i data-feather="arrow-left"></i>
        </a>`;
    }

    function homeCoverCard(book, index) {
        const cover = book.cover_url || book.cover || config.fallbackCover;
        return `<a href="${config.bookDetailUrlTemplate.replace('/0/', `/${book.id}/`)}" class="home-cover-card home-cover-real cover-${index + 1}" aria-label="${esc(tr('home.book_aria', { title: book.title }))}">
            <img src="${esc(cover)}" alt="${esc(tr('home.cover_alt', { title: book.title }))}" loading="eager" data-home-cover data-fallback="${esc(config.fallbackCover)}">
            <span>${esc(book.title)}</span>
        </a>`;
    }

    function bindHomeCoverFallbacks(root) {
        root?.querySelectorAll('[data-home-cover]').forEach((image) => {
            image.addEventListener('error', () => {
                if (image.dataset.fallbackApplied === 'true') return;
                image.dataset.fallbackApplied = 'true';
                image.src = image.dataset.fallback || config.fallbackCover;
            }, { once: true });
        });
    }

    async function initHome() {
        const categoryGrid = $('#homeCategoryGrid');
        const coverPreview = $('#homeCoverPreview');
        const [categories, books] = await Promise.all([api('categories'), api('books?paginate=1&page_size=6')]);
        if (!categories.success) {
            const error = `<div class="library-empty"><h3>${tr('load.failed_title')}</h3><p>${tr('load.retry')}</p></div>`;
            if (categoryGrid) categoryGrid.innerHTML = error;
            return;
        }
        state.categories = categories.data || [];
        state.categoryMap.clear();
        flattenCategories(state.categories);
        if (categoryGrid) categoryGrid.innerHTML = state.categories.length ? state.categories.slice(0, 6).map(homeCategoryCard).join('') : `<div class="library-empty"><h3>${tr('categories.empty')}</h3></div>`;
        state.visibleBooks = books.success ? (books.data || []) : [];
        if (coverPreview) {
            const previewBooks = state.visibleBooks.slice(0, 3);
            coverPreview.innerHTML = previewBooks.map(homeCoverCard).join('');
            bindHomeCoverFallbacks(coverPreview);
            coverPreview.classList.toggle('hidden', !previewBooks.length);
            const heroGrid = $('.home-minimal-grid');
            if (heroGrid) heroGrid.classList.toggle('without-covers', !previewBooks.length);
        }
        refreshIcons();
    }

    function renderCategoryTree(nodes, level = 0) {
        return nodes.map((node) => `<div class="catalog-category-branch">
            <button type="button" data-catalog-category="${node.id}" style="--category-level:${level}"><span>${esc(node.name)}</span><b>${toFa(node.book_count)}</b></button>
            ${node.children?.length ? renderCategoryTree(node.children, level + 1) : ''}
        </div>`).join('');
    }

    function setCatalogUrl(params, replace = false) {
        const query = params.toString();
        const url = `${config.catalogUrl}${query ? `?${query}` : ''}`;
        window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
    }

    function updateCatalogHead(params) {
        const categoryId = params.get('category') || '';
        const category = state.categoryMap.get(String(categoryId));
        const search = params.get('q') || '';
        const availability = params.get('availability') || '';
        const breadcrumb = $('#catalogBreadcrumbV3');
        const activeFilter = $('#catalogActiveFilter');
        $$('.catalog-category-tree button, .catalog-all-category').forEach((button) => {
            button.classList.toggle('active', String(button.dataset.catalogCategory || '') === String(categoryId || ''));
        });
        if (category) {
            const path = categoryPath(category);
            breadcrumb.innerHTML = `<a href="${config.catalogUrl}">${tr('catalog.all_books')}</a>${path.map((item) => `<i data-feather="chevron-left"></i><span>${esc(item.name)}</span>`).join('')}`;
        } else {
            breadcrumb.innerHTML = `<a href="${config.catalogUrl}">${tr('catalog.all_books')}</a>`;
        }
        const labels = [];
        if (category) labels.push(`<span>${esc(tr('filter.category', { category: category.name }))}<button type="button" data-clear-param="category" aria-label="${tr('filter.clear_category')}"><i data-feather="x"></i></button></span>`);
        if (search) labels.push(`<span>${esc(tr('filter.search', { query: search }))}<button type="button" data-clear-param="q" aria-label="${tr('filter.clear_search')}"><i data-feather="x"></i></button></span>`);
        if (availability) labels.push(`<span>${esc(tr('filter.status', { status: availability === 'available' ? tr('availability.available') : tr('availability.borrowed') }))}<button type="button" data-clear-param="availability" aria-label="${tr('filter.clear_status')}"><i data-feather="x"></i></button></span>`);
        activeFilter.innerHTML = labels.join('');
        activeFilter.classList.toggle('hidden', !labels.length);
        $('#catalogSearchInput').value = search;
        const availabilitySelect = $('#catalogAvailabilityFilter');
        if (availabilitySelect) availabilitySelect.value = availability;
        $('#catalogClearSearch')?.classList.toggle('hidden', !search);
        $$('[data-clear-search]').forEach((button) => button.classList.toggle('hidden', !search));
        refreshIcons();
    }

    function renderPagination(current, total) {
        const target = $('#catalogPagination');
        if (!target) return;
        if (total <= 1) {
            target.innerHTML = '';
            target.hidden = true;
            return;
        }
        target.hidden = false;
        const pages = new Set([1, total, current - 1, current, current + 1]);
        const valid = [...pages].filter((item) => item >= 1 && item <= total).sort((a, b) => a - b);
        let previous = 0;
        const items = [];
        valid.forEach((number) => {
            if (previous && number - previous > 1) items.push('<span>…</span>');
            items.push(`<button type="button" data-catalog-page="${number}" class="${number === current ? 'active' : ''}">${toFa(number)}</button>`);
            previous = number;
        });
        target.innerHTML = `<button type="button" data-catalog-page="${current - 1}" ${current <= 1 ? 'disabled' : ''} aria-label="${tr('pagination.previous')}"><i data-feather="chevron-right"></i></button>${items.join('')}<button type="button" data-catalog-page="${current + 1}" ${current >= total ? 'disabled' : ''} aria-label="${tr('pagination.next')}"><i data-feather="chevron-left"></i></button>`;
        refreshIcons();
    }

    function packShelfPages(widths, availableWidth, rowCount, gap) {
        if (!widths.length) return [];
        const pages = [];
        let page = [];
        let row = 0;
        let used = 0;
        widths.forEach((width, index) => {
            const required = used > 0 ? gap + width : width;
            if (used > 0 && used + required > availableWidth + 0.5) {
                row += 1;
                used = 0;
            }
            if (row >= rowCount) {
                pages.push(page);
                page = [];
                row = 0;
            }
            page.push(index);
            used += (used > 0 ? gap : 0) + width;
        });
        if (page.length) pages.push(page);
        return pages;
    }

    window.LIBRARY_BOOKSHELF_PACKER = packShelfPages;

    function setCatalogPhysicalPage(pageNumber, scroll = false) {
        const grid = $('#catalogBookGrid');
        if (!grid || !state.catalogPhysicalPages) return;
        const total = state.catalogPhysicalPages.length || 1;
        const current = Math.min(Math.max(1, Number(pageNumber) || 1), total);
        const visible = new Set(state.catalogPhysicalPages[current - 1] || []);
        $$('.shelf-slot', grid).forEach((slot, index) => { slot.hidden = !visible.has(index); });
        state.catalogPage = current;
        state.totalPages = total;
        renderPagination(current, total);
        const params = new URLSearchParams(window.location.search);
        if (current > 1) params.set('page', String(current)); else params.delete('page');
        setCatalogUrl(params, true);
        if (scroll) $('.catalog-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function layoutCatalogShelf() {
        const grid = $('#catalogBookGrid');
        if (!grid) return;
        const slots = $$('.shelf-slot', grid);
        grid.classList.add('is-measuring-capacity');
        try {
            slots.forEach((slot) => { slot.hidden = false; });
            const style = window.getComputedStyle(grid);
            const availableWidth = grid.clientWidth
                - parseFloat(style.paddingLeft || 0)
                - parseFloat(style.paddingRight || 0);
            const parsedGap = parseFloat(style.columnGap || 0);
            const gap = Number.isFinite(parsedGap) ? parsedGap : 0;
            if (!Number.isFinite(availableWidth) || availableWidth <= 0) return;
            const widths = slots.map((slot) => {
                const slotStyle = window.getComputedStyle(slot);
                const marginLeft = parseFloat(slotStyle.marginLeft || 0);
                const marginRight = parseFloat(slotStyle.marginRight || 0);
                return slot.getBoundingClientRect().width
                    + (Number.isFinite(marginLeft) ? marginLeft : 0)
                    + (Number.isFinite(marginRight) ? marginRight : 0);
            });
            if (widths.some((width) => !Number.isFinite(width) || width <= 0)) return;
            let requiredRows = 1;
            let usedWidth = 0;
            widths.forEach((width) => {
                const required = usedWidth > 0 ? gap + width : width;
                if (usedWidth > 0 && usedWidth + required > availableWidth + 0.5) {
                    requiredRows += 1;
                    usedWidth = 0;
                }
                usedWidth += (usedWidth > 0 ? gap : 0) + width;
            });
            const rowCount = Math.min(2, Math.max(1, requiredRows));
            grid.style.setProperty('--shelf-visible-rows', String(rowCount));
            grid.dataset.shelfRows = String(rowCount);
            state.catalogPhysicalPages = packShelfPages(widths, availableWidth, rowCount, gap);
            const requestedPage = Number(new URLSearchParams(window.location.search).get('page') || state.catalogPage || 1);
            setCatalogPhysicalPage(requestedPage, false);
            console.debug('[bookshelf capacity]', {
                totalBooks: slots.length,
                innerWidth: availableWidth,
                rows: rowCount,
                gap,
                bookWidths: widths,
                pages: state.catalogPhysicalPages.map((indexes) => indexes.map((index) => slots[index].dataset.shelfBookId)),
            });
        } finally {
            grid.classList.remove('is-measuring-capacity');
        }
    }

    function loadCatalogBooks() {
        window.location.assign(`${window.location.pathname}${window.location.search}`);
    }

    async function initCatalog() {
        const categories = await api('categories');
        if (categories.success) {
            state.categories = categories.data || [];
            state.categoryMap.clear();
            flattenCategories(state.categories);
            $('#catalogCategoryTree').innerHTML = state.categories.length ? renderCategoryTree(state.categories) : `<p class="catalog-no-category">${tr('categories.empty')}</p>`;
        } else {
            $('#catalogCategoryTree').innerHTML = `<p class="catalog-no-category">${tr('categories.load_failed')}</p>`;
        }
        await loadCatalogBooks(false);
        refreshIcons();

        const params = new URLSearchParams(window.location.search);
        if (params.get('show_categories') === '1') {
            params.delete('show_categories');
            setCatalogUrl(params, true);
            if (window.matchMedia('(max-width: 820px)').matches) {
                document.body.classList.add('catalog-sidebar-open');
            } else {
                $('#categories')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }

    function closeCatalogSidebar() {
        document.body.classList.remove('catalog-sidebar-open');
    }

    function updateDetailRating(result) {
        const selectedRating = Number(result.user_rating);
        $$('.book-rating-stars [data-rate]').forEach((button) => {
            const value = Number(button.dataset.rate);
            button.classList.toggle('is-filled', value <= selectedRating);
            button.setAttribute('aria-pressed', value === selectedRating ? 'true' : 'false');
        });
        const average = $('#ratingAverage');
        const count = $('#ratingCount');
        const overall = $('#ratingOverallCompact');
        const userRating = $('#userRatingText');
        if (average) average.textContent = tr('rating.from_five', { value: toFaDecimal(result.average_rating) });
        if (count) count.textContent = tr('rating.count', { count: toFa(result.rating_count) });
        if (overall) overall.classList.remove('hidden');
        if (userRating) userRating.textContent = tr('rating.yours', { value: toFa(selectedRating) });
    }

    async function submitDetailRating(button) {
        const form = button.closest('#bookRatingForm');
        if (!form) return;
        const buttons = $$('[data-rate]', form);
        buttons.forEach((item) => { item.disabled = true; });
        form.setAttribute('aria-busy', 'true');
        const result = await api('rate-book', {
            method: 'POST',
            body: JSON.stringify({
                book_id: Number(form.dataset.ratingBookId),
                rating: Number(button.dataset.rate),
            }),
        });
        buttons.forEach((item) => { item.disabled = false; });
        form.removeAttribute('aria-busy');
        notify(result.message, result.success);
        if (result.success) updateDetailRating(result);
    }

    document.addEventListener('mouseover', (event) => {
        const link = event.target.closest?.('[data-book-pullout]');
        if (link && page === 'catalog' && !link.contains(event.relatedTarget)) showShelfPreview(link);
    });
    document.addEventListener('mouseout', (event) => {
        const link = event.target.closest?.('[data-book-pullout]');
        if (link && page === 'catalog' && !link.contains(event.relatedTarget)) hideShelfPreview();
    });
    document.addEventListener('focusin', (event) => {
        const link = event.target.closest?.('[data-book-pullout]');
        if (link && page === 'catalog') showShelfPreview(link);
    });
    document.addEventListener('focusout', (event) => {
        if (event.target.closest?.('[data-book-pullout]') && page === 'catalog') hideShelfPreview();
    });
    window.addEventListener('resize', hideShelfPreview);
    window.addEventListener('scroll', hideShelfPreview, { passive: true });

    document.addEventListener('click', async (event) => {
        const pulloutLink = event.target.closest('[data-book-pullout]');
        if (pulloutLink && page === 'catalog') {
            const modifiedClick = event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
            if (!modifiedClick) {
                event.preventDefault();
                pullBookToDetail(pulloutLink);
            }
            return;
        }
        if (event.target.closest('[data-open-request]')) {
            openNewBookRequest();
            return;
        }
        if (event.target.closest('[data-open-contact]')) {
            openContactForm();
            return;
        }
        if (event.target.closest('[data-close-modal]') || event.target === $('#modalBackdrop')) {
            closeModal();
            return;
        }
        const physical = event.target.closest('[data-request-physical]');
        if (physical) {
            openPhysicalRequest(physical.dataset.requestPhysical);
            return;
        }
        const pdf = event.target.closest('[data-request-pdf]');
        if (pdf) {
            openPdfRequest(pdf.dataset.requestPdf);
            return;
        }
        const rate = event.target.closest('[data-rate]');
        if (rate && page === 'book-detail') {
            await submitDetailRating(rate);
            return;
        }
        if (rate && state.activeBook) {
            const result = await api('rate-book', { method: 'POST', body: JSON.stringify({ book_id: state.activeBook.id, rating: Number(rate.dataset.rate) }) });
            notify(result.message, result.success);
            return;
        }
        const category = event.target.closest('[data-catalog-category]');
        if (category && page === 'catalog') {
            const params = new URLSearchParams(window.location.search);
            if (category.dataset.catalogCategory) params.set('category', category.dataset.catalogCategory);
            else params.delete('category');
            params.delete('page');
            setCatalogUrl(params);
            closeCatalogSidebar();
            loadCatalogBooks(true);
            return;
        }
        const clearSearch = event.target.closest('[data-clear-search]');
        if (clearSearch && page === 'catalog') {
            const params = new URLSearchParams(window.location.search);
            params.delete('q');
            params.delete('page');
            setCatalogUrl(params);
            loadCatalogBooks(true);
            return;
        }
        const clearParam = event.target.closest('[data-clear-param]');
        if (clearParam && page === 'catalog') {
            const params = new URLSearchParams(window.location.search);
            params.delete(clearParam.dataset.clearParam);
            params.delete('page');
            setCatalogUrl(params);
            loadCatalogBooks(true);
            return;
        }
        const pagination = event.target.closest('[data-catalog-page]');
        if (pagination && !pagination.disabled && page === 'catalog') {
            setCatalogPhysicalPage(pagination.dataset.catalogPage, true);
            return;
        }
        const card = event.target.closest('[data-book-id]');
        if (card) openBook(card.dataset.bookId);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            cleanupBookPullout();
            closeModal();
            closeCatalogSidebar();
        }
        if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-book-id]')) {
            event.preventDefault();
            openBook(event.target.dataset.bookId);
        }
    });

    document.addEventListener('submit', async (event) => {
        if (event.target.id === 'catalogSearchForm') {
            event.preventDefault();
            const params = new URLSearchParams(window.location.search);
            const term = $('#catalogSearchInput').value.trim();
            if (term) params.set('q', term); else params.delete('q');
            params.delete('page');
            setCatalogUrl(params);
            loadCatalogBooks(true);
            return;
        }
        if (event.target.id === 'physicalRequestForm') {
            event.preventDefault();
            const form = new FormData(event.target);
            const result = await api('request-physical-book', { method: 'POST', body: JSON.stringify(Object.fromEntries(form.entries())) });
            notify(result.message, result.success);
            if (result.success) closeModal();
            return;
        }
        if (event.target.id === 'pdfRequestForm') {
            event.preventDefault();
            const form = new FormData(event.target);
            const result = await api('request-book', { method: 'POST', body: JSON.stringify(Object.fromEntries(form.entries())) });
            notify(result.message, result.success);
            if (result.success) closeModal();
            return;
        }
        if (event.target.id === 'newBookRequestForm') {
            event.preventDefault();
            const form = new FormData(event.target);
            const payload = Object.fromEntries(form.entries());
            payload.type = 'book_request';
            const result = await api('contact', { method: 'POST', body: JSON.stringify(payload) });
            notify(result.message, result.success);
            if (result.success) closeModal();
            return;
        }
        if (event.target.id === 'contactSupportForm') {
            event.preventDefault();
            const form = new FormData(event.target);
            const payload = Object.fromEntries(form.entries());
            payload.type = 'contact';
            const result = await api('contact', { method: 'POST', body: JSON.stringify(payload) });
            notify(result.message, result.success);
            if (result.success) closeModal();
            return;
        }
        if (event.target.id === 'commentForm') {
            event.preventDefault();
            const book = state.activeBook || state.detailBook;
            if (!book) {
                notify(tr('book.unavailable'), false);
                return;
            }
            const form = new FormData(event.target);
            const chosenEmail = form.get('email');
            const result = await api('comments', { method: 'POST', body: JSON.stringify({ book_id: book.id, text: form.get('text'), email: chosenEmail }) });
            notify(result.message, result.success);
            if (result.success) {
                event.target.reset();
                const emailInput = event.target.querySelector('[name="email"]');
                if (emailInput) emailInput.value = chosenEmail || config.user?.email || '';
                const comments = await api(`comments/${book.id}`);
                $('#bookComments').innerHTML = commentsHtml(comments.data || []);
                refreshIcons();
            }
        }
    });

    const openFilters = $('#openCatalogFilters');
    const closeFilters = $('#closeCatalogFilters');
    const sidebarBackdrop = $('#catalogSidebarBackdrop');
    if (openFilters) openFilters.addEventListener('click', () => document.body.classList.add('catalog-sidebar-open'));
    if (closeFilters) closeFilters.addEventListener('click', closeCatalogSidebar);
    if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeCatalogSidebar);
    const availabilityFilter = $('#catalogAvailabilityFilter');
    if (availabilityFilter && availabilityFilter.dataset.ajaxCatalog === 'true') availabilityFilter.addEventListener('change', () => {
        const params = new URLSearchParams(window.location.search);
        if (availabilityFilter.value) params.set('availability', availabilityFilter.value); else params.delete('availability');
        params.delete('page');
        setCatalogUrl(params);
        loadCatalogBooks(true);
    });

    if (page === 'home') {
        initHome();
        const params = new URLSearchParams(window.location.search);
        if (params.get('contact') === '1') {
            params.delete('contact');
            const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`;
            window.history.replaceState({}, '', nextUrl);
            openContactForm();
        }
    }
    if (page === 'catalog') {
        layoutCatalogShelf();
        let shelfResizeFrame = 0;
        const scheduleShelfLayout = () => {
            window.cancelAnimationFrame(shelfResizeFrame);
            shelfResizeFrame = window.requestAnimationFrame(layoutCatalogShelf);
        };
        const shelf = $('#catalogBookGrid');
        if (shelf && 'ResizeObserver' in window) {
            const shelfResizeObserver = new ResizeObserver(scheduleShelfLayout);
            shelfResizeObserver.observe(shelf);
        } else {
            window.addEventListener('resize', scheduleShelfLayout, { passive: true });
        }
        const params = new URLSearchParams(window.location.search);
        if (params.get('show_categories') === '1') {
            if (window.matchMedia('(max-width: 820px)').matches) {
                document.body.classList.add('catalog-sidebar-open');
            } else {
                $('#categories')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }
    window.addEventListener('pageshow', cleanupBookPullout);
    refreshIcons();
