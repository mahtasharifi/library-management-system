'use strict';

let translations = {};
const tr = (key) => translations[key] || key;

let translationsReady = Promise.resolve();

async function loadTranslations() {
    const url = document.body?.dataset.siteTranslationsUrl || '';
    if (!url) return;
    try {
        const response = await fetch(url, {headers: {'Accept': 'application/json'}});
        if (!response.ok) return;
        translations = (await response.json()).translations || {};
    } catch (error) {
        translations = {};
    }
}

const esc = (value = '') => String(value ?? '').replace(/[&<>'\"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;'
})[char]);

const iconFor = (kind) => ({
    approved: 'check-circle',
    rejected: 'x-circle',
    read: 'eye',
    answered: 'message-square',
})[kind] || 'bell';

function formatDate(value) {
    if (window.LIBRARY_PERSIAN_UI) {
        return window.LIBRARY_PERSIAN_UI.formatDate(value, true);
    }
    return value || '';
}

function renderItems(target, items) {
    if (!items.length) {
        target.innerHTML = `<div class="notification-popover-empty"><i data-feather="bell-off"></i><strong>${tr('notifications.empty_title')}</strong><span>${tr('notifications.empty_help')}</span></div>`;
        return;
    }
    target.innerHTML = items.map((item) => `
        <article class="notification-popover-item ${item.is_read ? '' : 'unread'}">
            <span class="kind-${esc(item.kind)}"><i data-feather="${iconFor(item.kind)}"></i></span>
            <div>
                <div><strong>${esc(item.title)}</strong>${item.is_read ? '' : `<b>${tr('notifications.new')}</b>`}</div>
                <p>${esc(item.message)}</p>
                <time>${formatDate(item.created_at)}</time>
            </div>
        </article>
    `).join('');
}

function refreshIconsAndDates(target) {
    if (window.feather) window.feather.replace();
    if (window.LIBRARY_PERSIAN_UI) window.LIBRARY_PERSIAN_UI.localize(target);
}

function setup(host) {
    if (host.dataset.notificationReady === '1') return;
    host.dataset.notificationReady = '1';

    const toggle = host.querySelector('[data-notification-toggle]');
    const popover = host.querySelector('[data-notification-popover]');
    const close = host.querySelector('[data-notification-close]');
    const list = host.querySelector('[data-notification-list]');
    if (!toggle || !popover || !close || !list) return;

    let loaded = false;
    let loadingPromise = null;

    const positionMobilePopover = () => {
        if (!window.matchMedia('(max-width: 700px)').matches) {
            popover.style.removeProperty('--notification-mobile-left');
            popover.style.removeProperty('--notification-mobile-top');
            popover.style.removeProperty('--notification-mobile-width');
            return;
        }
        const rect = toggle.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const width = Math.min(320, Math.max(260, viewportWidth - 24));
        const preferredLeft = rect.right - width;
        const left = Math.max(12, Math.min(viewportWidth - width - 12, preferredLeft));
        const top = Math.max(58, Math.round(rect.bottom + 8));
        popover.style.setProperty('--notification-mobile-left', `${Math.round(left)}px`);
        popover.style.setProperty('--notification-mobile-top', `${top}px`);
        popover.style.setProperty('--notification-mobile-width', `${Math.round(width)}px`);
    };

    const hide = () => {
        popover.classList.add('hidden');
        toggle.setAttribute('aria-expanded', 'false');
    };

    const load = async () => {
        if (loaded) return;
        if (loadingPromise) return loadingPromise;
        loadingPromise = (async () => {
            try {
                await translationsReady;
                const response = await fetch(host.dataset.notificationEndpoint, {
                    credentials: 'same-origin',
                    headers: {
                        'Accept': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                if (!response.ok) throw new Error('request-failed');
                const data = await response.json();
                if (!data.success) throw new Error('request-failed');
                renderItems(list, data.items || []);
                loaded = true;
                refreshIconsAndDates(list);
            } catch (error) {
                await translationsReady;
                list.innerHTML = `<div class="notification-popover-empty"><i data-feather="wifi-off"></i><strong>${tr('notifications.load_failed')}</strong><span>${tr('notifications.retry')}</span></div>`;
                refreshIconsAndDates(list);
            } finally {
                loadingPromise = null;
            }
        })();
        return loadingPromise;
    };

    toggle.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const willOpen = popover.classList.contains('hidden');
        document.querySelectorAll('[data-notification-popover]').forEach((item) => {
            if (item !== popover) item.classList.add('hidden');
        });
        if (!willOpen) {
            hide();
            return;
        }
        positionMobilePopover();
        popover.classList.remove('hidden');
        toggle.setAttribute('aria-expanded', 'true');
        await load();
    });

    close.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        hide();
    });
    document.addEventListener('click', (event) => {
        if (!host.contains(event.target)) hide();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') hide();
    });
    window.addEventListener('resize', () => {
        if (!popover.classList.contains('hidden')) positionMobilePopover();
    }, {passive: true});
    window.addEventListener('scroll', () => {
        if (!popover.classList.contains('hidden')) positionMobilePopover();
    }, {passive: true});
}

function boot() {
    translationsReady = loadTranslations();
    document.querySelectorAll('[data-notification-host]').forEach(setup);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
} else {
    boot();
}
