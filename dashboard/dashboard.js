/**
 * CAH Transformation Engine - Dashboard Controller
 * High-end minimalist command center interface
 */

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initializeClock();
    initializeCounters();
    initializeChart();
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
 * Console branding
 */
console.log(`
%c╔═══════════════════════════════════════════════╗
║  CAH TRANSFORMATION ENGINE                    ║
║  Command Center Dashboard v1.0.0              ║
║                                               ║
║  Visionblox LLC × Zuup Innovation Lab         ║
╚═══════════════════════════════════════════════╝
`, 'color: #ffffff; background: #000000; font-family: monospace; padding: 10px;');

