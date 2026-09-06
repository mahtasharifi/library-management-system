'use strict';

    const digitMap = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    const ignoredTags = new Set(['SCRIPT', 'STYLE', 'CODE', 'PRE', 'TEXTAREA']);
    const dateFormatter = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
        year: 'numeric', month: '2-digit', day: '2-digit',
    });
    const dateTimeFormatter = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    });
    const yearFormatter = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { year: 'numeric' });

    function toFaDigits(value) {
        return String(value ?? '').replace(/[0-9]/g, (digit) => digitMap[Number(digit)]);
    }

    function formatDate(value, includeTime = true) {
        if (!value) return '—';
        const date = value instanceof Date ? value : new Date(value);
        if (Number.isNaN(date.getTime())) return toFaDigits(value);
        return (includeTime ? dateTimeFormatter : dateFormatter).format(date);
    }

    function shouldIgnoreText(node) {
        const parent = node.parentElement;
        return !parent || ignoredTags.has(parent.tagName) || parent.closest('[data-keep-latin]');
    }

    function localizeTextNode(node) {
        if (shouldIgnoreText(node)) return;
        const converted = toFaDigits(node.nodeValue);
        if (converted !== node.nodeValue) node.nodeValue = converted;
    }

    function localize(root = document) {
        if (!root) return;
        const scope = root.nodeType === Node.ELEMENT_NODE || root.nodeType === Node.DOCUMENT_NODE ? root : root.parentElement;
        if (!scope) return;

        if (root.nodeType === Node.TEXT_NODE) localizeTextNode(root);
        const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) localizeTextNode(node);

        const elements = scope.matches?.('[data-persian-date], [data-persian-current-year]')
            ? [scope, ...scope.querySelectorAll('[data-persian-date], [data-persian-current-year]')]
            : [...scope.querySelectorAll('[data-persian-date], [data-persian-current-year]')];
        elements.forEach((element) => {
            if (element.hasAttribute('data-persian-current-year')) {
                element.textContent = yearFormatter.format(new Date());
                return;
            }
            const raw = element.getAttribute('datetime') || element.dataset.persianDate;
            element.textContent = formatDate(raw, element.dataset.persianDate !== 'date');
        });

        scope.querySelectorAll?.('[placeholder], [title], [aria-label]').forEach((element) => {
            ['placeholder', 'title', 'aria-label'].forEach((attribute) => {
                if (element.hasAttribute(attribute)) {
                    element.setAttribute(attribute, toFaDigits(element.getAttribute(attribute)));
                }
            });
        });
    }

    window.LIBRARY_PERSIAN_UI = { toFaDigits, formatDate, localize };

    document.addEventListener('DOMContentLoaded', () => {
        localize(document);
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'characterData') localizeTextNode(mutation.target);
                mutation.addedNodes.forEach((node) => localize(node));
            });
        });
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    });
