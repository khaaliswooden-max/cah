/**
 * CAH Transformation Engine — tab controller.
 * 6-tab landing: #cah, #problem, #benchmark, #solution, #solved, #paper.
 */

const TABS = ['cah', 'problem', 'benchmark', 'solution', 'solved', 'paper'];
const DEFAULT_TAB = 'problem';

function showTab(name) {
    if (!TABS.includes(name)) name = DEFAULT_TAB;

    document.querySelectorAll('.tab').forEach(btn => {
        const active = btn.dataset.tab === name;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.hidden = panel.id !== `tab-${name}`;
    });
}

function initTabs() {
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const name = btn.dataset.tab;
            if (!name) return;
            if (location.hash !== `#${name}`) {
                history.pushState(null, '', `#${name}`);
            }
            showTab(name);
            window.scrollTo({ top: 0, behavior: 'instant' });
        });
    });

    window.addEventListener('hashchange', () => {
        showTab((location.hash || '').replace(/^#/, '') || DEFAULT_TAB);
    });
}

function initFromHash() {
    const fromHash = (location.hash || '').replace(/^#/, '');
    showTab(fromHash || DEFAULT_TAB);
}

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFromHash();
});
