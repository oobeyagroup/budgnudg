/* ===============================================
   Transaction Pages JavaScript  
   =============================================== */

// Transaction-specific functionality
window.BudgNudgTransactions = {
    
    init: function() {
        this.setupTransactionFilters();
        this.setupTransactionActions();
        this.initTransactionTable();
        this.setupDateFilters();
    },
    
    initTransactionTable: function() {
        // Initialize transaction-specific DataTable
        if (window.BudgNudgDataTables) {
            window.BudgNudgDataTables.init('transactionTable', window.BudgNudgDataTables.transactionTable);
        }
    },
    
    setupTransactionFilters: function() {
        // Filter controls
        $('.transaction-filter').on('change', function() {
            const filterType = $(this).data('filter');
            const filterValue = $(this).val();
            this.applyTransactionFilter(filterType, filterValue);
        }.bind(this));
        
        // Quick filter buttons
        $('.quick-filter-btn').on('click', function(e) {
            e.preventDefault();
            const filter = $(this).data('filter');
            this.applyQuickFilter(filter);
        }.bind(this));
    },
    
    applyTransactionFilter: function(type, value) {
        const table = $('#transactionTable').DataTable();
        
        switch(type) {
            case 'account':
                table.column(1).search(value).draw();
                break;
            case 'category':
                table.column(4).search(value).draw();
                break;
            case 'amount':
                this.filterByAmount(table, value);
                break;
        }
    },
    
    applyQuickFilter: function(filter) {
        const table = $('#transactionTable').DataTable();
        
        switch(filter) {
            case 'no-category':
                table.column(4).search('^$', true, false).draw();
                break;
            case 'no-payoree':
                table.column(5).search('^$', true, false).draw();
                break;
            case 'large-amounts':
                this.filterByAmount(table, 'large');
                break;
        }
    },
    
    filterByAmount: function(table, criteria) {
        // Custom amount filtering logic
        table.draw();
    },
    
    setupDateFilters: function() {
        // Date range picker functionality
        $('.date-filter').on('change', function() {
            const startDate = $('#start-date').val();
            const endDate = $('#end-date').val();
            this.filterByDateRange(startDate, endDate);
        }.bind(this));
    },
    
    filterByDateRange: function(startDate, endDate) {
        const table = $('#transactionTable').DataTable();
        // Custom date range filtering
        table.draw();
    },
    
    setupTransactionActions: function() {
        // Transaction row actions
        $('.transaction-action').on('click', function(e) {
            e.preventDefault();
            const action = $(this).data('action');
            const transactionId = $(this).data('transaction-id');
            
            switch(action) {
                case 'edit':
                    this.editTransaction(transactionId);
                    break;
                case 'categorize':
                    this.categorizeTransaction(transactionId);
                    break;
                case 'split':
                    this.splitTransaction(transactionId);
                    break;
            }
        }.bind(this));
        
        // Bulk actions
        $('.bulk-action-btn').on('click', function(e) {
            const action = $(this).data('action');
            const selectedIds = this.getSelectedTransactions();
            this.performBulkAction(action, selectedIds);
        }.bind(this));
    },
    
    editTransaction: function(transactionId) {
        // Handle transaction editing
        console.log('Edit transaction:', transactionId);
    },
    
    categorizeTransaction: function(transactionId) {
        // Handle transaction categorization
        console.log('Categorize transaction:', transactionId);
    },
    
    splitTransaction: function(transactionId) {
        // Handle transaction splitting
        console.log('Split transaction:', transactionId);
    },
    
    getSelectedTransactions: function() {
        // Get selected transaction IDs
        const selected = [];
        $('.transaction-checkbox:checked').each(function() {
            selected.push($(this).val());
        });
        return selected;
    },
    
    performBulkAction: function(action, transactionIds) {
        if (transactionIds.length === 0) {
            alert('Please select transactions first');
            return;
        }
        
        switch(action) {
            case 'categorize':
                this.bulkCategorize(transactionIds);
                break;
            case 'delete':
                this.bulkDelete(transactionIds);
                break;
        }
    },
    
    bulkCategorize: function(transactionIds) {
        // Handle bulk categorization
        console.log('Bulk categorize:', transactionIds);
    },
    
    bulkDelete: function(transactionIds) {
        if (confirm(`Delete ${transactionIds.length} transactions?`)) {
            console.log('Bulk delete:', transactionIds);
        }
    }
};