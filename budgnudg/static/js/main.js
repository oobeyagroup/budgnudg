/* ===============================================
   Main Application JavaScript
   =============================================== */

/* ===============================================
   BudgNudg - Main Application JavaScript
   Modern Modular Architecture
   =============================================== */

$(document).ready(function() {
    // ===============================================
    // Initialize Core Components
    // ===============================================
    
    // Initialize navbar functionality
    if (window.BudgNudgNavbar) {
        window.BudgNudgNavbar.init();
    }
    
    // Initialize DataTables
    if (window.BudgNudgDataTables) {
        window.BudgNudgDataTables.initAll();
    }
    
    // ===============================================
    // Initialize Page-Specific Functionality
    // ===============================================
    
    // Budget pages
    if (window.BudgNudgBudgets && $('body').hasClass('budget-page')) {
        window.BudgNudgBudgets.init();
    }
    
    // Transaction pages  
    if (window.BudgNudgTransactions && $('body').hasClass('transaction-page')) {
        window.BudgNudgTransactions.init();
    }
    
    // ===============================================
    // Global UI Enhancements
    // ===============================================
    
    // Smooth scroll for anchor links
    $('a[href^="#"]').on('click', function(e) {
        const target = $(this.getAttribute('href'));
        if (target.length) {
            e.preventDefault();
            $('html, body').animate({
                scrollTop: target.offset().top - 70 // Account for navbar height
            }, 600);
        }
    });
    
    // Loading state management
    $(document).on('ajaxStart', function() {
        $('body').addClass('loading');
    }).on('ajaxStop', function() {
        $('body').removeClass('loading');
    });
    
    // Toast notifications
    if (typeof bootstrap !== 'undefined' && $('.toast').length) {
        $('.toast').each(function() {
            new bootstrap.Toast(this).show();
        });
    }
    
    // Initialize tooltips
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    console.log('BudgNudg application initialized successfully');
});