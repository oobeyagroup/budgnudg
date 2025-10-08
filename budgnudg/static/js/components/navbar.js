/* ===============================================
   Navbar Component JavaScript
   =============================================== */

// Navbar functionality
window.BudgNudgNavbar = {
    
    scrollThreshold: 50,
    
    init: function() {
        this.setupScrollEffect();
        this.setupMobileMenu();
        this.setupDropdowns();
    },
    
    setupScrollEffect: function() {
        const navbar = $('.navbar');
        const self = this;
        
        function updateNavbar() {
            const scrollTop = $(window).scrollTop();
            
            if (scrollTop > self.scrollThreshold) {
                navbar.addClass('scrolled');
            } else {
                navbar.removeClass('scrolled');
            }
        }
        
        // Initial check
        updateNavbar();
        
        // Throttled scroll handler for performance
        let scrollTimeout;
        $(window).on('scroll', function() {
            if (!scrollTimeout) {
                scrollTimeout = setTimeout(function() {
                    updateNavbar();
                    scrollTimeout = null;
                }, 10);
            }
        });
    },
    
    setupMobileMenu: function() {
        // Enhanced mobile menu behavior
        $('.navbar-toggler').on('click', function() {
            const $navbar = $('.navbar');
            const $collapse = $('.navbar-collapse');
            
            // Add animation class
            $navbar.toggleClass('mobile-menu-open');
            
            // Close menu when clicking outside
            $(document).one('click', function(e) {
                if (!$(e.target).closest('.navbar').length) {
                    $collapse.collapse('hide');
                    $navbar.removeClass('mobile-menu-open');
                }
            });
        });
    },
    
    setupDropdowns: function() {
        // Enhanced dropdown behavior
        $('.dropdown-toggle').on('show.bs.dropdown', function() {
            $(this).closest('.dropdown').addClass('dropdown-active');
        });
        
        $('.dropdown-toggle').on('hide.bs.dropdown', function() {
            $(this).closest('.dropdown').removeClass('dropdown-active');
        });
        
        // Close dropdown on escape key
        $(document).on('keydown', function(e) {
            if (e.key === 'Escape') {
                $('.dropdown-menu.show').dropdown('hide');
            }
        });
    }
};