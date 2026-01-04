/**
 * CAH Transformation Engine - Dashboard Controller
 * High-end minimalist command center interface
 */

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initializeClock();
    loadOptimizationResults();
    initializeAnimationDelays();
    initializeBedInteractions();
});

/**
 * Real-time clock display
 */
function initializeClock() {
    const timeEl = document.getElementById('time');
    const dateEl = document.getElementById('date');
    
    function updateClock() {
        const now = new Date();
        
        // Time with leading zeros
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        timeEl.textContent = `${hours}:${minutes}:${seconds}`;
        
        // Date formatting
        const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 
                       'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
        const day = String(now.getDate()).padStart(2, '0');
        const month = months[now.getMonth()];
        const year = now.getFullYear();
        dateEl.textContent = `${month} ${day}, ${year}`;
    }
    
    updateClock();
    setInterval(updateClock, 1000);
}

/**
 * Animated number counters
 */
function initializeCounters() {
    // Revenue counter
    const revenueCounters = document.querySelectorAll('[data-count]');
    
    revenueCounters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-count'));
        animateCounter(counter, target, 2000);
    });
}

function animateCounter(element, target, duration) {
    const start = 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function for smooth animation
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(start + (target - start) * easeOutQuart);
        
        // Format with commas
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    // Delay start for staggered effect
    setTimeout(() => {
        requestAnimationFrame(update);
    }, 500);
}

/**
 * Revenue trend chart using Chart.js
 */
function initializeChart() {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;
    
    // Chart.js configuration with minimal styling
    const chartConfig = {
        type: 'line',
        data: {
            labels: ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'],
            datasets: [
                {
                    label: 'Revenue',
                    data: [1420, 1380, 1510, 1490, 1620, 1580, 1540, 1610, 1590, 1650, 1580, 1605],
                    borderColor: '#ffffff',
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    borderWidth: 1.5,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: '#ffffff',
                    pointHoverBorderColor: '#ffffff',
                },
                {
                    label: 'Expenses',
                    data: [1480, 1520, 1490, 1580, 1550, 1620, 1590, 1640, 1610, 1680, 1650, 1620],
                    borderColor: 'rgba(255, 51, 102, 0.7)',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [4, 4],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: '#ff3366',
                    pointHoverBorderColor: '#ff3366',
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#0d0d0d',
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                    borderWidth: 1,
                    titleColor: '#888888',
                    titleFont: {
                        family: "'Share Tech Mono', monospace",
                        size: 10,
                        weight: 'normal'
                    },
                    bodyColor: '#ffffff',
                    bodyFont: {
                        family: "'Orbitron', sans-serif",
                        size: 12,
                        weight: 'bold'
                    },
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => items[0].label,
                        label: (item) => `$${item.raw}K`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#444444',
                        font: {
                            family: "'Share Tech Mono', monospace",
                            size: 9
                        }
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#444444',
                        font: {
                            family: "'Share Tech Mono', monospace",
                            size: 9
                        },
                        callback: (value) => `$${value}K`
                    },
                    min: 1200,
                    max: 1800
                }
            },
            animation: {
                duration: 1500,
                easing: 'easeOutQuart',
                delay: (context) => {
                    return context.dataIndex * 50;
                }
            }
        }
    };
    
    // Create chart with delayed initialization
    setTimeout(() => {
        new Chart(ctx, chartConfig);
    }, 600);
}

/**
 * Set animation delays based on data attributes
 */
function initializeAnimationDelays() {
    const elements = document.querySelectorAll('[data-delay]');
    
    elements.forEach(el => {
        const delay = parseInt(el.getAttribute('data-delay'));
        el.style.setProperty('--delay', delay);
    });
}

/**
 * Bed grid interactions
 */
function initializeBedInteractions() {
    const beds = document.querySelectorAll('.bed');
    
    beds.forEach((bed, index) => {
        // Add staggered animation on load
        bed.style.animationDelay = `${600 + (index * 30)}ms`;
        bed.style.opacity = '0';
        bed.style.animation = 'fadeIn 0.3s ease forwards';
        
        // Add hover interaction
        bed.addEventListener('mouseenter', () => {
            if (bed.classList.contains('occupied')) {
                bed.title = 'Occupied';
            } else {
                bed.title = 'Available';
            }
        });
    });
    
    // Add CSS animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.8); }
            to { opacity: 1; transform: scale(1); }
        }
    `;
    document.head.appendChild(style);
}

/**
 * Utility: Format currency
 */
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * Utility: Format percentage
 */
function formatPercentage(value, decimals = 1) {
    return `${value.toFixed(decimals)}%`;
}

/**
 * Simulate real-time data updates (demo purposes)
 */
function simulateDataUpdates() {
    setInterval(() => {
        // Randomly toggle a bed status
        const beds = document.querySelectorAll('.bed');
        const randomBed = beds[Math.floor(Math.random() * beds.length)];
        
        // Small chance to toggle
        if (Math.random() > 0.95) {
            randomBed.classList.toggle('occupied');
            randomBed.classList.toggle('available');
            
            // Update census stats
            updateCensusStats();
        }
    }, 5000);
}

/**
 * Update census statistics
 */
function updateCensusStats() {
    const occupiedBeds = document.querySelectorAll('.bed.occupied').length;
    const totalBeds = document.querySelectorAll('.bed').length;
    const availableBeds = totalBeds - occupiedBeds;
    
    const stats = document.querySelectorAll('.census-stat .stat-num');
    if (stats.length >= 3) {
        stats[0].textContent = occupiedBeds;
        stats[1].textContent = availableBeds;
        stats[2].textContent = totalBeds;
    }
}

// Start simulated updates (comment out for production)
// simulateDataUpdates();

/**
 * Intersection Observer for scroll animations
 */
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Observe all animated elements
document.querySelectorAll('.panel, .stat-card, .action-panel').forEach(el => {
    observer.observe(el);
});

/**
 * Keyboard shortcuts
 */
document.addEventListener('keydown', (e) => {
    // Press 'R' to refresh data (demo)
    if (e.key === 'r' || e.key === 'R') {
        if (e.ctrlKey || e.metaKey) return; // Don't interfere with browser refresh
        console.log('Manual refresh triggered');
    }
    
    // Press 'F' for fullscreen toggle
    if (e.key === 'f' || e.key === 'F') {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    }
});

/**
 * Load optimization results from JSON files
 */
async function loadOptimizationResults() {
    try {
        // Load optimization summary
        const summaryResponse = await fetch('../reports/optimization_summary.json');
        if (summaryResponse.ok) {
            const summary = await summaryResponse.json();
            updateDashboardWithResults(summary);
        } else {
            console.warn('Optimization results not found, using default data');
            initializeCounters();
            initializeChart();
        }
        
        // Load Pareto front for visualization
        const paretoResponse = await fetch('../reports/pareto_front.json');
        if (paretoResponse.ok) {
            const pareto = await paretoResponse.json();
            updateParetoVisualization(pareto);
        }
    } catch (error) {
        console.error('Error loading optimization results:', error);
        initializeCounters();
        initializeChart();
    }
}

/**
 * Update dashboard with optimization results
 */
function updateDashboardWithResults(summary) {
    const opt = summary.optimal_solution;
    const alloc = summary.resource_allocation;
    const uncertainty = summary.uncertainty_analysis;
    
    // Update Operating Margin card
    const marginCard = document.querySelector('.stat-card.primary');
    if (marginCard) {
        const valueEl = marginCard.querySelector('.value');
        const deltaEl = marginCard.querySelector('.stat-delta');
        const barFill = marginCard.querySelector('.bar-fill');
        
        const marginPercent = opt.operating_margin_percent.toFixed(1);
        valueEl.textContent = marginPercent;
        valueEl.setAttribute('data-value', marginPercent);
        
        // Update delta and styling based on performance
        if (opt.operating_margin >= 0.05) {
            marginCard.classList.remove('critical');
            deltaEl.classList.remove('negative');
            deltaEl.classList.add('positive');
            deltaEl.innerHTML = '<span class="delta-icon">▲</span><span class="delta-value">' + 
                (opt.operating_margin_percent - 5).toFixed(1) + '% above target</span>';
            barFill.classList.remove('negative');
            barFill.classList.add('good');
            barFill.style.setProperty('--fill', Math.min(100, opt.operating_margin_percent * 5) + '%');
        }
    }
    
    // Update financial panel
    const revenueValue = document.querySelector('.revenue-value span[data-count]');
    if (revenueValue) {
        revenueValue.setAttribute('data-count', Math.round(opt.annual_revenue));
        animateCounter(revenueValue, Math.round(opt.annual_revenue), 2000);
    }
    
    // Update revenue items
    const revenueItems = document.querySelectorAll('.revenue-item');
    if (revenueItems.length >= 3) {
        revenueItems[0].querySelector('.value').textContent = '$' + formatLargeNumber(opt.annual_revenue);
        revenueItems[1].querySelector('.value').textContent = '$' + formatLargeNumber(opt.annual_revenue - opt.annual_profit);
        revenueItems[2].querySelector('.value').textContent = '$' + formatLargeNumber(opt.annual_profit);
        revenueItems[2].classList.remove('deficit');
        revenueItems[2].classList.add('surplus');
    }
    
    // Update census display with optimal allocation
    const censusStats = document.querySelectorAll('.census-stat .stat-num');
    if (censusStats.length >= 3) {
        const acuteBeds = Math.round(alloc.acute_beds);
        const swingBeds = Math.round(alloc.swing_beds);
        const totalBeds = acuteBeds + swingBeds;
        const census = Math.round(alloc.expected_daily_census);
        
        censusStats[0].textContent = census;
        censusStats[1].textContent = totalBeds - census;
        censusStats[2].textContent = totalBeds;
    }
    
    // Update bed occupancy card
    const occupancyCard = document.querySelectorAll('.stat-card')[1];
    if (occupancyCard) {
        const totalBeds = Math.round(alloc.total_beds);
        const census = Math.round(alloc.expected_daily_census);
        const occupancy = (census / totalBeds * 100).toFixed(1);
        
        const valueEl = occupancyCard.querySelector('.value');
        if (valueEl) valueEl.textContent = occupancy;
    }
    
    // Update Gap Analysis panel to show optimization success
    updateGapAnalysis(summary);
    
    // Update recommendations
    updateRecommendations(summary.recommendations);
    
    // Initialize chart with optimization data
    initializeOptimizedChart(summary);
}

/**
 * Update Gap Analysis panel
 */
function updateGapAnalysis(summary) {
    const gapItems = document.querySelectorAll('.gap-item');
    if (gapItems.length >= 1) {
        const marginGap = gapItems[0];
        const marginPercent = summary.optimal_solution.operating_margin_percent;
        
        // Update to show optimization success
        marginGap.classList.remove('critical');
        marginGap.classList.add('success');
        
        const currentLabel = marginGap.querySelector('.gap-current .label');
        const targetLabel = marginGap.querySelector('.gap-target .label');
        const impactValue = marginGap.querySelector('.gap-impact .impact-value');
        
        if (currentLabel) currentLabel.textContent = marginPercent.toFixed(1) + '%';
        if (impactValue) {
            impactValue.textContent = 'Optimized: $' + formatLargeNumber(summary.optimal_solution.annual_profit) + '/yr profit';
        }
        
        // Adjust bar positions
        const currentBar = marginGap.querySelector('.gap-current');
        if (currentBar) currentBar.style.left = '75%';
    }
}

/**
 * Update recommendations panel
 */
function updateRecommendations(recommendations) {
    const actionCards = document.querySelectorAll('.action-card');
    
    recommendations.forEach((rec, index) => {
        if (actionCards[index]) {
            const card = actionCards[index];
            const title = card.querySelector('h3');
            const desc = card.querySelector('p');
            const impact = card.querySelector('.impact');
            const timeline = card.querySelector('.timeline');
            
            if (title) title.textContent = rec.area + ': ' + rec.priority + ' Priority';
            if (desc) desc.textContent = rec.recommendation;
            if (impact) impact.textContent = rec.action;
            if (timeline) timeline.textContent = '';
        }
    });
}

/**
 * Initialize chart with optimization data
 */
function initializeOptimizedChart(summary) {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;
    
    const opt = summary.optimal_solution;
    const monthlyRevenue = opt.annual_revenue / 12;
    const monthlyExpenses = (opt.annual_revenue - opt.annual_profit) / 12;
    
    // Generate projected monthly data
    const revenueData = [];
    const expenseData = [];
    for (let i = 0; i < 12; i++) {
        const variance = 1 + (Math.random() - 0.5) * 0.1;
        revenueData.push(Math.round(monthlyRevenue * variance / 1000));
        expenseData.push(Math.round(monthlyExpenses * variance / 1000));
    }
    
    const chartConfig = {
        type: 'line',
        data: {
            labels: ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'],
            datasets: [
                {
                    label: 'Revenue',
                    data: revenueData,
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                },
                {
                    label: 'Expenses',
                    data: expenseData,
                    borderColor: 'rgba(255, 200, 100, 0.8)',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    borderDash: [4, 4],
                    fill: false,
                    tension: 0.3,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0d0d0d',
                    borderColor: 'rgba(0, 255, 136, 0.3)',
                    borderWidth: 1,
                    titleColor: '#888888',
                    bodyColor: '#00ff88',
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: (item) => '$' + item.raw + 'K'
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#444444', font: { size: 9 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: {
                        color: '#444444',
                        font: { size: 9 },
                        callback: (value) => '$' + value + 'K'
                    }
                }
            },
            animation: { duration: 1500, easing: 'easeOutQuart' }
        }
    };
    
    setTimeout(() => new Chart(ctx, chartConfig), 600);
}

/**
 * Update Pareto front visualization
 */
function updateParetoVisualization(pareto) {
    // Store pareto data for potential use in modal or expanded view
    window.paretoData = pareto;
    console.log('Pareto front loaded:', pareto.n_pareto_optimal, 'solutions');
    console.log('Margin range:', (pareto.margin_range[0] * 100).toFixed(1) + '% to ' + (pareto.margin_range[1] * 100).toFixed(1) + '%');
    console.log('Quality range:', pareto.quality_range[0].toFixed(3) + ' to ' + pareto.quality_range[1].toFixed(3));
}

/**
 * Format large numbers (e.g., 15586160 -> "15.6M")
 */
function formatLargeNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(0) + 'K';
    }
    return num.toFixed(0);
}

/**
 * Console branding
 */
console.log(`
%c╔═══════════════════════════════════════════════╗
║  CAH TRANSFORMATION ENGINE                    ║
║  Command Center Dashboard v1.0.0              ║
║  OPTIMIZATION MODULE ACTIVE                   ║
║                                               ║
║  Visionblox LLC × Zuup Innovation Lab         ║
╚═══════════════════════════════════════════════╝
`, 'color: #00ff88; background: #000000; font-family: monospace; padding: 10px;');

