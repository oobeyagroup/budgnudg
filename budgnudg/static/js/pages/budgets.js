/* ===============================================
   Budget Pages JavaScript
   =============================================== */

// Budget-specific functionality
window.BudgNudgBudgets = {
    
    init: function() {
        this.setupBudgetFilters();
        this.setupProgressBars();
        this.setupBudgetActions();
        this.initBudgetTable();
    },
    
    initBudgetTable: function() {
        // Initialize budget-specific DataTable
        if (window.BudgNudgDataTables) {
            window.BudgNudgDataTables.init('budgetTable', window.BudgNudgDataTables.budgetTable);
        }
    },
    
    setupBudgetFilters: function() {
        // Enhanced filter functionality
        $('.budget-filter-button').on('click', function(e) {
            e.preventDefault();
            
            const $button = $(this);
            const filterType = $button.data('filter');
            const filterValue = $button.data('value');
            
            // Update active state
            $button.siblings().removeClass('active');
            $button.addClass('active');
            
            // Apply filter
            this.applyFilter(filterType, filterValue);
            
            // Visual feedback
            this.showFilterFeedback($button);
        }.bind(this));
        
        // Clear filters
        $('.clear-filters').on('click', function(e) {
            e.preventDefault();
            $('.budget-filter-button').removeClass('active');
            this.clearAllFilters();
        }.bind(this));
    },
    
    applyFilter: function(type, value) {
        const table = $('#budgetTable').DataTable();
        
        switch(type) {
            case 'period':
                table.column(0).search(value).draw();
                break;
            case 'category':
                table.column(2).search(value).draw();
                break;
            case 'status':
                // Custom status filter logic
                this.filterByStatus(table, value);
                break;
        }
    },
    
    filterByStatus: function(table, status) {
        // Custom filtering for budget status
        table.draw();
    },
    
    clearAllFilters: function() {
        const table = $('#budgetTable').DataTable();
        table.search('').columns().search('').draw();
    },
    
    showFilterFeedback: function($button) {
        // Visual feedback for filter application
        $button.addClass('filter-applied');
        setTimeout(() => {
            $button.removeClass('filter-applied');
        }, 300);
    },
    
    setupProgressBars: function() {
        // Animate progress bars on page load
        $('.budget-progress-bar').each(function() {
            const $bar = $(this);
            const width = $bar.data('progress') || $bar.css('width');
            
            $bar.css('width', '0%');
            setTimeout(() => {
                $bar.animate({width: width}, 1000, 'easeOutCubic');
            }, 200);
        });
    },
    
    setupBudgetActions: function() {
        // Budget action buttons
        $('.budget-action-btn').on('click', function(e) {
            const action = $(this).data('action');
            const budgetId = $(this).data('budget-id');
            
            switch(action) {
                case 'edit':
                    this.editBudget(budgetId);
                    break;
                case 'delete':
                    this.deleteBudget(budgetId);
                    break;
                case 'duplicate':
                    this.duplicateBudget(budgetId);
                    break;
            }
        }.bind(this));
    },
    
    editBudget: function(budgetId) {
        // Handle budget editing
        console.log('Edit budget:', budgetId);
    },
    
    deleteBudget: function(budgetId) {
        // Handle budget deletion with confirmation
        if (confirm('Are you sure you want to delete this budget allocation?')) {
            console.log('Delete budget:', budgetId);
        }
    },
    
    duplicateBudget: function(budgetId) {
        // Handle budget duplication
        console.log('Duplicate budget:', budgetId);
    }
};