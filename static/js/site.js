document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch(document.body.dataset.siteTranslationsUrl || '', {headers: {'Accept':'application/json'}});
    const translations = response.ok ? ((await response.json()).translations || {}) : {};
    const tr = (key) => translations[key] || key;
    if (window.feather) window.feather.replace();
    const toggle = document.querySelector('[data-menu-toggle]');
    const menu = document.querySelector('[data-site-menu]');

    if (toggle && menu) {
        const closeMenu = () => {
            menu.classList.remove('is-open');
            toggle.setAttribute('aria-expanded', 'false');
        };

        toggle.addEventListener('click', () => {
            const isOpen = menu.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', String(isOpen));
        });

        menu.querySelectorAll('a, button').forEach((item) => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) closeMenu();
            });
        });

        document.addEventListener('click', (event) => {
            if (!menu.contains(event.target) && !toggle.contains(event.target)) closeMenu();
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') closeMenu();
        });
    }

    document.querySelectorAll('[data-password-toggle]').forEach((button) => {
        button.addEventListener('click', () => {
            const input = document.getElementById(button.dataset.passwordToggle);
            if (!input) return;
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            button.setAttribute('aria-pressed', String(isPassword));
            button.setAttribute('aria-label', isPassword ? tr('password.hide') : tr('password.show'));
            if (window.feather) window.feather.replace();
        });
    });
});
