// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Intersection Observer for fade-in animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Observe all cards and steps
document.addEventListener('DOMContentLoaded', () => {
    // Add fade-in class to elements
    const elements = document.querySelectorAll('.feature-card, .service-card, .step');
    elements.forEach(el => {
        el.classList.add('fade-in');
        observer.observe(el);
    });

    // Track button clicks (analytics placeholder)
    document.querySelectorAll('.cta-button').forEach(button => {
        button.addEventListener('click', () => {
            console.log('CTA clicked:', button.textContent.trim());
            // Add analytics tracking here if needed
        });
    });
});

// Add parallax effect to hero background
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const heroBackground = document.querySelector('.hero-background');
    if (heroBackground) {
        heroBackground.style.transform = `translateY(${scrolled * 0.5}px)`;
    }
});
