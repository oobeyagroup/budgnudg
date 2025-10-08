/* ===============================================
   DataTables Component Configuration
   =============================================== */

// DataTables configuration objects
window.BudgNudgDataTables = {
    
    // Default configuration for all tables
    defaults: {
        autoWidth: false,
        responsive: true,
        processing: true,
        stateSave: true,
        pageLength: 50,
        lengthMenu: [[25, 50, 100, 250, -1], [25, 50, 100, 250, "All"]],
        language: {
            emptyTable: "No data available",
            processing: "Loading...",
            search: "Search:",
            lengthMenu: "Show _MENU_ entries",
            info: "Showing _START_ to _END_ of _TOTAL_ entries",
            paginate: {
                first: "First",
                last: "Last", 
                next: "Next",
                previous: "Previous"
            }
        },
        dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
             '<"row"<"col-sm-12"tr>>' +
             '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>'
    },
    
    // Transaction table specific configuration
    transactionTable: {
        order: [[2, 'desc']], // Sort by date column
        columnDefs: [
            {
                targets: [3], // Description column
                render: function(data, type, row) {
                    if (type === 'display' && data && data.length > 50) {
                        return '<span title="' + data + '">' + data.substring(0, 47) + '...</span>';
                    }
                    return data || '';
                }
            },
            {
                targets: [4, 5], // Amount columns
                className: 'text-end'
            }
        ]
    },
    
    // Budget table specific configuration
    budgetTable: {
        order: [[0, 'desc']], // Sort by period
        columnDefs: [
            {
                targets: [3, 4, 5], // Amount columns
                className: 'text-end',
                render: function(data, type, row) {
                    if (type === 'display' && data) {
                        const num = parseFloat(data);
                        if (!isNaN(num)) {
                            return '$' + num.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        }
                    }
                    return data;
                }
            },
            {
                targets: [6], // Progress column
                orderable: false,
                render: function(data, type, row) {
                    if (type === 'display' && data) {
                        const progress = parseFloat(data) || 0;
                        const progressClass = progress > 100 ? 'progress-bar-danger' : progress > 80 ? 'progress-bar-warning' : 'progress-bar-success';
                        return `
                            <div class="budget-progress">
                                <div class="budget-progress-bar ${progressClass}" style="width: ${Math.min(progress, 100)}%">
                                </div>
                            </div>
                            <small class="text-muted">${progress.toFixed(1)}%</small>
                        `;
                    }
                    return data;
                }
            }
        ]
    },
    
    // Category table specific configuration
    categoryTable: {
        order: [[0, 'asc']], // Sort by name
        columnDefs: [
            {
                targets: [2], // Transaction count column
                className: 'text-center'
            }
        ]
    },
    
    // Initialize a specific table
    init: function(tableId, config = {}) {
        if (!$.fn.DataTable) {
            console.error('DataTables not loaded');
            return null;
        }
        
        // Merge configurations
        const tableConfig = {
            ...this.defaults,
            ...config
        };
        
        // Check if table exists
        const $table = $('#' + tableId);
        if ($table.length === 0) {
            console.warn('Table not found:', tableId);
            return null;
        }
        
        // Initialize DataTable
        try {
            const dataTable = $table.DataTable(tableConfig);
            console.log('Initialized DataTable:', tableId);
            return dataTable;
        } catch (error) {
            console.error('Error initializing DataTable:', tableId, error);
            return null;
        }
    },
    
    // Initialize all common tables
    initAll: function() {
        // Transaction table
        this.init('transactionTable', this.transactionTable);
        
        // Budget table
        this.init('budgetTable', this.budgetTable);
        
        // Category table
        this.init('categoryTable', this.categoryTable);
        
        // Payoree table
        this.init('payoreeTable', {
            order: [[0, 'asc']],
            columnDefs: [
                {
                    targets: [2], // Transaction count
                    className: 'text-center'
                }
            ]
        });
    }
};