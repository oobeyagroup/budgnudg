/* ===============================================
   Main Application JavaScript
   =============================================== */

$(document).ready(function() {
    // ===============================================
    // Navbar Scroll Effect
    // ===============================================
    
    const navbar = $('.navbar');
    const scrollThreshold = 50; // Pixels to scroll before effect triggers
    
    function updateNavbar() {
        const scrollTop = $(window).scrollTop();
        
        if (scrollTop > scrollThreshold) {
            navbar.addClass('scrolled');
        } else {
            navbar.removeClass('scrolled');
        }
    }
    
    // Initial check
    updateNavbar();
    
    // Update on scroll with throttling for performance
    let scrollTimeout;
    $(window).on('scroll', function() {
        if (!scrollTimeout) {
            scrollTimeout = setTimeout(function() {
                updateNavbar();
                scrollTimeout = null;
            }, 10); // Throttle to every 10ms for smooth animation
        }
    });

    // ===============================================
    // DataTables Initialization
    // ===============================================
    
    // Initialize DataTables for Transactions
    $('#transactionTable').DataTable({
        language: {
            emptyTable: "No transactions found."
        },
        autoWidth: false,
        pageLength: 50,
        lengthMenu: [[25, 50, 100, 250, -1], [25, 50, 100, 250, "All"]],
        order: [[2, 'desc']], // Sort by date column (3rd column, 0-indexed)
        responsive: true,
        processing: true,
        stateSave: true, // Remember user preferences
        columnDefs: [
            {
                targets: [3], // Description column
                render: function(data, type, row) {
                    if (type === 'display' && data.length > 50) {
                        return '<span title="' + data + '">' + data.substring(0, 47) + '...</span>';
                    }
                    return data;
                }
            }
        ],
        dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
             '<"row"<"col-sm-12"tr>>' +
             '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>'
    });

    // Initialize Categories DataTable
    $('#categoryTable').DataTable({
        autoWidth: false,
        pageLength: 50,
        order: [[0, 'asc']],
        responsive: true
    });

    // ===============================================
    // Additional UI Enhancements
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
});