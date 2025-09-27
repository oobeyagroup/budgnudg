# Advanced Transaction Search & Filtering

**Status**: 🚧 IN PROGRESS  
**Epic**: Transaction Management & Analysis  
**Priority**: Could Have  
**Estimated Effort**: 3 points  
**Target Release**: Current Sprint  
**ATDD Status**: Converting to incremental test-driven development  

## User Story

As a **detailed budget tracker**, I want to **search and filter my transactions using advanced criteria and saved search patterns** so that **I can quickly find specific transactions, analyze spending patterns, and generate custom reports for different purposes**.

## Business Context

Users often need to:
- Find specific transactions by multiple criteria (amount range, date, payoree, category, description keywords)
- Create complex filters for analysis (e.g., "all dining transactions over $50 in the last 3 months")
- Save frequently used search patterns for repeated analysis
- Export filtered results for external analysis or record-keeping
- Track recurring transaction patterns across different time periods

This feature transforms basic transaction listing into a powerful analysis tool that helps users understand their spending in granular detail.

## Acceptance Criteria

### Basic Search Functionality (MVP)
- [ ] 🚧 `search_by_date_range` Given I have transactions across multiple dates, when I filter by a date range, then I see only transactions within that range
- [ ] 🚧 `search_by_amount_range` Given I have transactions of various amounts, when I filter by amount range ($50-$200), then I see only transactions within that range
- [ ] 🚧 `search_by_category` Given I have transactions in different categories, when I filter by a specific category, then I see only transactions in that category
- [ ] 🚧 `search_by_description_keywords` Given I have transactions with various descriptions, when I search by keywords, then I see transactions containing those keywords

### Advanced Search Capabilities
- [ ] ⏳ `search_multiple_criteria` Given transaction history, when I use advanced search, then I can filter by amount ranges, date ranges, multiple categories, multiple payorees, and description keywords simultaneously
- [ ] ⏳ `search_negative_filters` Given search criteria, when I want to exclude results, then I can use negative filters (e.g., "NOT category:groceries")
- [ ] ⏳ `search_logical_operators` Given complex searches, when I build search queries, then I can use logical operators (AND, OR, NOT) between different criteria
- [ ] ⏳ `search_comparison_operators` Given transaction amounts, when I search, then I can use comparison operators (greater than, less than, equal to, between)

### Quick Filter Interface
- [ ] ⏳ `quick_filter_buttons` Given common search needs, when I want fast filtering, then I have quick-access buttons for frequent criteria (This Month, Last Month, High Amounts, Uncategorized)
- [ ] ⏳ `filter_refinement` Given search results, when I want to refine further, then I can add additional filters without losing current results
- [ ] ⏳ `applied_filter_display` Given applied filters, when I review them, then I can see all active filters clearly and remove individual filters easily
- [ ] ⏳ `search_history` Given search history, when I want to repeat searches, then I can access my recent searches from a dropdown

### Results Analysis & Export
- [ ] ⏳ `search_results_summary` Given search results, when I view them, then I can see summary statistics (total amount, transaction count, average amount, category breakdown)
- [ ] ⏳ `csv_export` Given filtered transactions, when I want to export, then I can download results as CSV with customizable column selection
- [ ] ⏳ `results_grouping` Given search results, when I analyze patterns, then I can view results grouped by payoree, category, amount ranges, or time periods
- [ ] ⏳ `visual_charts` Given filtered data, when I need reporting, then I can generate visual charts (spending over time, category distribution) directly from search results

### Saved Search Patterns  
- [ ] 💡 `save_search_patterns` Given frequently used search criteria, when I create a search, then I can save it with a custom name for future reuse
- [ ] 💡 `manage_saved_searches` Given saved searches, when I access them, then I can modify, duplicate, or delete existing saved patterns
- [ ] 💡 `relative_date_searches` Given saved search patterns, when I run them, then they automatically apply current date ranges or use relative dates ("last 30 days")
- [ ] 💡 `organize_searches` Given multiple saved searches, when organizing them, then I can group them into folders or categories

## MoSCoW Prioritization

### Must Have ⏳
- Multi-criteria search (amount, date, category, payoree, description)
- Quick filter buttons for common searches
- Clear display of applied filters with easy removal
- Basic export to CSV functionality

### Should Have ⏳  
- Saved search patterns with custom names
- Summary statistics for search results
- Recent searches history
- Logical operators (AND, OR, NOT) in search queries

### Could Have ⏳
- Advanced search query builder with visual interface
- Search result grouping and analysis views
- Custom export column selection
- Chart generation from filtered results

### Won't Have (This Release)
- ❌ Natural language search ("show me expensive restaurant meals last month")
- ❌ Machine learning-powered search suggestions
- ❌ Integration with external analysis tools
- ❌ Collaborative shared saved searches

## Technical Implementation

### Search Service Architecture
```python
# Proposed search engine architecture
class TransactionSearchService:
    def __init__(self):
        self.query_builder = QueryBuilder()
        self.filter_engine = FilterEngine()
        
    def search(self, criteria: SearchCriteria, user: User) -> SearchResults:
        """Execute search with complex criteria"""
        query = self.query_builder.build_query(criteria)
        results = self.filter_engine.apply_filters(query, user)
        return SearchResults(results, criteria)

class SearchCriteria:
    def __init__(self):
        self.amount_min: Decimal = None
        self.amount_max: Decimal = None
        self.date_start: date = None  
        self.date_end: date = None
        self.categories: List[str] = []
        self.payorees: List[str] = []
        self.description_keywords: List[str] = []
        self.exclude_categories: List[str] = []
        self.logical_operator: str = "AND"  # AND, OR
        
class QueryBuilder:
    def build_query(self, criteria: SearchCriteria) -> Q:
        """Convert search criteria to Django Q objects"""
        query = Q()
        
        # Amount filters
        if criteria.amount_min:
            query &= Q(amount__gte=criteria.amount_min)
        if criteria.amount_max:
            query &= Q(amount__lte=criteria.amount_max)
            
        # Date filters  
        if criteria.date_start:
            query &= Q(transaction_date__gte=criteria.date_start)
        if criteria.date_end:
            query &= Q(transaction_date__lte=criteria.date_end)
            
        # Category filters
        if criteria.categories:
            if criteria.logical_operator == "OR":
                category_query = Q()
                for cat in criteria.categories:
                    category_query |= Q(category__name=cat)
                query &= category_query
            else:
                for cat in criteria.categories:
                    query &= Q(category__name=cat)
                    
        # Exclude filters
        for exclude_cat in criteria.exclude_categories:
            query &= ~Q(category__name=exclude_cat)
            
        return query

class SavedSearch(models.Model):
    user = ForeignKey(User)
    name = CharField(max_length=100)
    description = TextField(blank=True)
    criteria_json = JSONField()  # Serialized SearchCriteria
    folder = CharField(max_length=50, blank=True)
    created_date = DateTimeField(auto_now_add=True)
    last_used = DateTimeField(null=True)
    use_count = IntegerField(default=0)
    
    def get_criteria(self) -> SearchCriteria:
        """Deserialize saved search criteria"""
        return SearchCriteria.from_dict(self.criteria_json)
```

### Database Optimization
```python
# Database indexes for search performance
class Transaction(models.Model):
    # ... existing fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'transaction_date']),
            models.Index(fields=['user', 'amount']),  
            models.Index(fields=['user', 'category', 'transaction_date']),
            models.Index(fields=['user', 'payoree', 'transaction_date']),
            models.Index(fields=['description']),  # For text search
        ]

# Full-text search capabilities
class TransactionSearchIndex:
    """PostgreSQL full-text search integration"""
    
    @classmethod
    def add_search_vector(cls):
        """Add search vector for description text search"""
        from django.contrib.postgres.search import SearchVector
        
        Transaction.objects.update(
            search_vector=SearchVector('description', 'payoree__name', 'category__name')
        )
    
    @classmethod 
    def search_text(cls, query_text: str, user: User):
        """Perform full-text search on transactions"""
        from django.contrib.postgres.search import SearchQuery, SearchRank
        
        search_query = SearchQuery(query_text)
        return Transaction.objects.filter(
            user=user,
            search_vector=search_query
        ).annotate(
            rank=SearchRank('search_vector', search_query)
        ).order_by('-rank')
```

### Search Results Processing
```python
class SearchResults:
    def __init__(self, transactions: QuerySet, criteria: SearchCriteria):
        self.transactions = transactions
        self.criteria = criteria
        self._summary = None
        
    @property
    def summary(self) -> dict:
        """Generate summary statistics for search results"""
        if self._summary is None:
            self._summary = {
                'total_count': self.transactions.count(),
                'total_amount': self.transactions.aggregate(Sum('amount'))['amount__sum'] or 0,
                'average_amount': self.transactions.aggregate(Avg('amount'))['amount__avg'] or 0,
                'date_range': {
                    'earliest': self.transactions.aggregate(Min('transaction_date'))['transaction_date__min'],
                    'latest': self.transactions.aggregate(Max('transaction_date'))['transaction_date__max'],
                },
                'category_breakdown': self._get_category_breakdown(),
                'payoree_breakdown': self._get_payoree_breakdown(),
            }
        return self._summary
    
    def _get_category_breakdown(self) -> dict:
        """Break down results by category"""
        return dict(
            self.transactions
            .values('category__name')
            .annotate(
                count=Count('id'),
                total=Sum('amount')
            )
            .values_list('category__name', 'total')
        )
        
    def export_csv(self, columns: List[str] = None) -> str:
        """Export search results to CSV format"""
        import csv
        import io
        
        if columns is None:
            columns = ['date', 'amount', 'description', 'category', 'payoree']
            
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(columns)
        
        # Data rows
        for transaction in self.transactions:
            row = []
            for column in columns:
                if column == 'date':
                    row.append(transaction.transaction_date.strftime('%Y-%m-%d'))
                elif column == 'amount':
                    row.append(str(transaction.amount))
                elif column == 'description':
                    row.append(transaction.description)
                elif column == 'category':
                    row.append(transaction.category.name if transaction.category else '')
                elif column == 'payoree':
                    row.append(transaction.payoree.name if transaction.payoree else '')
            writer.writerow(row)
            
        return output.getvalue()
```

## User Interface Design

### Advanced Search Interface
```
┌─ Transaction Search ───────────────────────────────────────────────────────┐
│ ┌─ Quick Filters ─────────────────────────────────────────────────────────┐ │
│ │ [This Month] [Last Month] [High Amount] [Uncategorized] [Dining]       │ │ 
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─ Advanced Criteria ─────────────────────────────────────────────────────┐ │
│ │ Amount: $[____] to $[____]  Date: [MM/DD/YYYY] to [MM/DD/YYYY]        │ │
│ │                                                                         │ │
│ │ Categories: [▼ Select Multiple]  Payorees: [▼ Select Multiple]         │ │
│ │ ☑ Groceries  ☑ Dining  ☐ Gas                                          │ │
│ │                                                                         │ │
│ │ Description contains: [________________]                                │ │
│ │ ☐ Exclude categories: [▼ Select]  Logic: ( • AND  ○ OR )             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [🔍 Search] [💾 Save Search] [📋 Recent Searches ▼] [🗑️ Clear All]      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ Applied Filters ──────────────────────────────────────────────────────────┐
│ Amount: $50-$200 [✕]  │  Date: Last 30 days [✕]  │  Category: Dining [✕] │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Search Results with Analysis
```
┌─ Search Results: 47 transactions found ───────────────────────────────────┐
│ ┌─ Summary ─────────────────────────────────────────────────────────────────┐ │
│ │ Total: $2,347.89  │  Average: $49.95  │  Range: Oct 1 - Oct 31, 2025  │ │
│ │ Top Category: Dining (23 transactions, $1,245)                         │ │
│ │ Top Payoree: Whole Foods (8 transactions, $456)                        │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ View: ( • List  ○ Group by Category  ○ Group by Payoree  ○ Chart )      │
│ [📊 Show Chart] [📤 Export CSV] [📋 Save as Report]                      │
│                                                                             │
│ ┌─ Transactions ────────────────────────────────────────────────────────────┐ │
│ │ Oct 31  Olive Garden        $67.89  Dining                             │ │
│ │ Oct 30  Whole Foods         $123.45  Groceries                         │ │
│ │ Oct 28  Shell Gas           $52.10   Transportation                     │ │
│ │ Oct 26  Starbucks          $8.75    Dining                             │ │
│ │ ...                                                      [Show 43 more] │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Saved Searches Management
```
┌─ Saved Searches ───────────────────────────────────────────────────────────┐
│ ┌─ Monthly Reports ─────────────────────────────────────────────────────────┐ │
│ │ 📊 High Spending Days (>$100)              Last used: 3 days ago       │ │
│ │ 🍽️ Restaurant Analysis                     Last used: 1 week ago       │ │
│ │ 🚗 Transportation Costs                    Last used: 2 weeks ago      │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌─ Ad-hoc Analysis ─────────────────────────────────────────────────────────┐ │
│ │ 🔍 Uncategorized Large Transactions        Last used: 1 day ago        │ │
│ │ 💳 Credit Card vs Cash Comparison          Last used: 5 days ago       │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [+ New Folder] [+ New Search] [📤 Export All] [⚙️ Manage]                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Success Metrics & KPIs

### User Engagement
- [ ] 📊 40% of active users use advanced search at least once per month  
- [ ] 📊 Average of 2.5 saved searches per user who uses the feature
- [ ] 📊 60% of users who create saved searches reuse them within 30 days

### Feature Effectiveness  
- [ ] 📊 Average search completion time under 30 seconds
- [ ] 📊 85% of searches return meaningful results (>0 transactions)
- [ ] 📊 70% user satisfaction rate with search relevance and speed

### System Performance
- [ ] 📊 Search queries complete in under 3 seconds for 10,000+ transactions
- [ ] 📊 Saved search execution time under 2 seconds
- [ ] 📊 CSV export generation under 10 seconds for 1,000+ transactions

## Testing Strategy

### Functionality Testing
- [ ] 🧪 Test all search criteria combinations work correctly  
- [ ] 🧪 Validate logical operators (AND, OR, NOT) produce expected results
- [ ] 🧪 Test saved search creation, modification, and deletion
- [ ] 🧪 Verify export functionality with various column selections

### Performance Testing
- [ ] 🧪 Load test with large transaction datasets (100K+ records)
- [ ] 🧪 Test concurrent search executions don't impact performance
- [ ] 🧪 Validate database query optimization and indexing effectiveness
- [ ] 🧪 Memory usage testing for large result sets

### User Experience Testing
- [ ] 🧪 Usability test search interface with different user skill levels
- [ ] 🧪 Test mobile responsiveness of search interface
- [ ] 🧪 A/B test different quick filter button arrangements
- [ ] 🧪 Validate search result presentation clarity and usefulness

## Dependencies & Prerequisites

### Data Requirements
- [ ] 📋 Adequate transaction history for meaningful search results
- [ ] 📋 Proper database indexing for search performance  
- [ ] 📋 Full-text search capabilities (PostgreSQL or similar)

### Technical Dependencies
- [ ] 🔧 Enhanced database query optimization
- [ ] 🔧 Background processing for complex searches
- [ ] 🔧 CSV export generation system
- [ ] 🔧 Search result caching mechanism

### User Experience Dependencies  
- [ ] 🎨 Advanced form controls for multi-select and date ranges
- [ ] 🎨 Chart generation library integration
- [ ] 🎨 Responsive design for mobile search interface
- [ ] 🎨 User guidance and help documentation for advanced features

## Risk Assessment & Mitigation

### Performance Risks
- **Slow searches on large datasets**: Complex queries may timeout  
  - *Mitigation*: Database optimization, query limits, background processing
- **Memory usage with large results**: Large result sets could cause issues
  - *Mitigation*: Pagination, result limits, progressive loading

### User Experience Risks  
- **Feature complexity**: Advanced search may overwhelm casual users
  - *Mitigation*: Progressive disclosure, good defaults, simple mode option
- **Search result irrelevance**: Poor search results decrease user trust
  - *Mitigation*: Search result relevance testing, user feedback integration

### Technical Risks
- **Database performance impact**: Search queries may slow down other operations
  - *Mitigation*: Read replicas, query optimization, off-peak processing
- **Export system abuse**: Users generating excessive large exports
  - *Mitigation*: Rate limiting, export size limits, background processing

## Future Enhancement Opportunities

### Intelligent Search
- **Natural language processing**: Allow searches like "expensive meals last month"
- **Machine learning suggestions**: Recommend searches based on user behavior
- **Smart categorization**: Auto-suggest categories based on search patterns

### Advanced Analytics
- **Trend analysis**: Show spending trends within search results
- **Comparative analysis**: Compare search results across different time periods  
- **Predictive insights**: Forecast future spending based on search patterns

### Integration & Collaboration
- **Report sharing**: Share saved searches and results with family members
- **External tool integration**: Export to Excel, Google Sheets, financial software
- **API access**: Allow third-party tools to access search functionality