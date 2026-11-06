(() => {
    'use strict';
    const treatment = document.getElementById('history-treatments-tab');
    const prescription = document.getElementById('history-prescriptions-tab');
    const panel = document.getElementById('clinical-history-panel');
    if (!treatment || !prescription || !panel) return;
    const nav = treatment.parentElement;
    const counts = document.querySelector('.clinical-history-summary');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const activeAnimations = new Map();
    let selected = null;

    function animateContent(element, direction) {
        if (!element) return;
        activeAnimations.get(element)?.cancel();
        activeAnimations.delete(element);
        if (reducedMotion.matches || typeof element.animate !== 'function') return;
        const animation = element.animate([
            { opacity: .65, transform: `translateX(${direction * 8}px)` },
            { opacity: 1, transform: 'translateX(0)' },
        ], { duration: 180, easing: 'cubic-bezier(.22, 1, .36, 1)' });
        activeAnimations.set(element, animation);
    }

    function positionIndicator(animate = false) {
        const current = treatment.getAttribute('aria-selected') === 'true'
            ? treatment : prescription;
        const containerRect = nav.getBoundingClientRect();
        const tabRect = current.getBoundingClientRect();
        nav.style.setProperty('--history-tab-x', `${tabRect.left - containerRect.left - nav.clientLeft}px`);
        nav.style.setProperty('--history-tab-y', `${tabRect.top - containerRect.top - nav.clientTop}px`);
        nav.style.setProperty('--history-tab-width', `${tabRect.width}px`);
        nav.style.setProperty('--history-tab-height', `${tabRect.height}px`);
        if (animate && selected && current !== selected) {
            const direction = current === prescription ? 1 : -1;
            animateContent(panel, direction);
            animateContent(counts, direction);
        }
        selected = current;
    }

    nav.classList.add('history-tabs-motion');
    positionIndicator();
    window.requestAnimationFrame(() => {
        positionIndicator();
        nav.classList.add('history-tabs-motion-ready');
    });
    const observer = new MutationObserver(() => positionIndicator(true));
    for (const tab of [treatment, prescription]) {
        observer.observe(tab, { attributes: true, attributeFilter: ['aria-selected'] });
    }
    let resizeObserver;
    if (typeof ResizeObserver === 'function') {
        resizeObserver = new ResizeObserver(() => positionIndicator());
        resizeObserver.observe(nav);
        resizeObserver.observe(treatment);
        resizeObserver.observe(prescription);
    } else {
        window.addEventListener('resize', () => positionIndicator());
    }
    reducedMotion.addEventListener('change', () => {
        for (const animation of activeAnimations.values()) animation.cancel();
        activeAnimations.clear();
    });
    window.addEventListener('pagehide', () => {
        for (const animation of activeAnimations.values()) animation.cancel();
        activeAnimations.clear();
    });
    // No click/keyboard handlers or API calls are replaced. The existing page
    // owns selection, filtering, loading states and stale-request protection.
})();
