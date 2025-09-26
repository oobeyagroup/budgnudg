# ATDD Dashboard System Design

## Overview
This design creates a direct link between user story acceptance criteria and automated tests, turning your user story markdown files into a living acceptance test dashboard.

## Core Components

### 1. Test Annotation System
Tests are annotated with user story references using a standardized format:

```python
import pytest
from atdd_tracker import acceptance_test, user_story

@user_story("ingest", "import_csv_transactions")
@acceptance_test("File Upload Processing", 
                criteria_id="csv_upload_validation",
                given="I have a valid CSV file",
                when="I upload it through the interface", 
                then="the system validates format and creates import batch")
def test_upload_creates_batch_and_rows(client, csv_bytes_basic):
    # existing test implementation
    pass
```

### 2. Criteria ID Mapping
Each acceptance criteria checkbox in markdown gets a unique ID:

```markdown
### CSV File Processing
- [ ] ✅ `csv_upload_validation` Given I have a valid CSV file, when I upload it through the interface, then the system validates format and creates import batch
- [ ] ✅ `csv_duplicate_detection` Given I upload a CSV with duplicate transactions, when the system processes it, then duplicates are flagged for review
```

### 3. Dashboard Generation
A Django management command generates real-time dashboard views:

```python
# management/commands/generate_atdd_dashboard.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        dashboard = ATDDDashboardGenerator()
        dashboard.generate_reports()
```

### 4. Living Documentation
The dashboard shows:
- User story completion status
- Test coverage per acceptance criteria
- Recent test results and trends
- Missing test coverage gaps

## Implementation Details

### Test Annotation Decorators
```python
# atdd_tracker.py
import functools
from typing import Dict, List
import json

# Global registry for test mappings
TEST_REGISTRY = {}

def user_story(app: str, story: str):
    """Link test to a specific user story file"""
    def decorator(func):
        if not hasattr(func, '_atdd_metadata'):
            func._atdd_metadata = {}
        func._atdd_metadata['story'] = f"{app}/{story}"
        return func
    return decorator

def acceptance_test(name: str, criteria_id: str, given: str, when: str, then: str):
    """Map test to specific acceptance criteria"""
    def decorator(func):
        if not hasattr(func, '_atdd_metadata'):
            func._atdd_metadata = {}
        func._atdd_metadata.update({
            'test_name': name,
            'criteria_id': criteria_id,
            'bdd': {'given': given, 'when': when, 'then': then}
        })
        
        # Register in global registry
        story = func._atdd_metadata.get('story', 'unknown')
        if story not in TEST_REGISTRY:
            TEST_REGISTRY[story] = []
        TEST_REGISTRY[story].append({
            'function': func.__name__,
            'criteria_id': criteria_id,
            'name': name,
            'bdd': func._atdd_metadata['bdd']
        })
        return func
    return decorator
```

### Markdown Parser for Criteria Extraction
```python
# atdd_parser.py
import re
from pathlib import Path
from typing import Dict, List, NamedTuple

class AcceptanceCriteria(NamedTuple):
    criteria_id: str
    status: str  # ✅, 🚧, ⏳, etc.
    description: str
    category: str

class UserStoryParser:
    def __init__(self, docs_path: Path):
        self.docs_path = docs_path
        
    def parse_all_stories(self) -> Dict[str, List[AcceptanceCriteria]]:
        """Parse all user story files and extract criteria"""
        stories = {}
        
        for story_file in self.docs_path.rglob("*.md"):
            relative_path = story_file.relative_to(self.docs_path)
            story_key = str(relative_path.with_suffix(''))
            
            stories[story_key] = self.parse_story_file(story_file)
            
        return stories
    
    def parse_story_file(self, file_path: Path) -> List[AcceptanceCriteria]:
        """Parse individual story file for acceptance criteria"""
        content = file_path.read_text()
        criteria = []
        current_category = "General"
        
        # Find acceptance criteria section
        criteria_section = re.search(
            r'## Acceptance Criteria\s*\n(.*?)(?=\n## |$)', 
            content, 
            re.DOTALL
        )
        
        if not criteria_section:
            return criteria
            
        criteria_text = criteria_section.group(1)
        
        # Parse categories and criteria
        for line in criteria_text.split('\n'):
            # Category headers (### Something)
            category_match = re.match(r'^### (.+)$', line.strip())
            if category_match:
                current_category = category_match.group(1)
                continue
                
            # Criteria items with IDs
            criteria_match = re.match(
                r'^- \[ \] ([✅🚧⏳💡]) `([^`]+)` (.+)$', 
                line.strip()
            )
            
            if criteria_match:
                status = criteria_match.group(1)
                criteria_id = criteria_match.group(2)
                description = criteria_match.group(3)
                
                criteria.append(AcceptanceCriteria(
                    criteria_id=criteria_id,
                    status=status,
                    description=description,
                    category=current_category
                ))
                
        return criteria
```

### Test Results Collector
```python
# test_collector.py
import pytest
import json
from datetime import datetime
from pathlib import Path

class ATDDTestCollector:
    def __init__(self):
        self.results = {}
        
    def pytest_runtest_makereport(self, item, call):
        """Collect test results with ATDD metadata"""
        if call.when == "call":
            # Extract ATDD metadata from test function
            metadata = getattr(item.function, '_atdd_metadata', {})
            
            if metadata:
                story = metadata.get('story', 'unknown')
                criteria_id = metadata.get('criteria_id')
                
                result = {
                    'test_name': item.name,
                    'criteria_id': criteria_id,
                    'status': 'PASS' if call.excinfo is None else 'FAIL',
                    'duration': call.duration,
                    'timestamp': datetime.now().isoformat(),
                    'bdd': metadata.get('bdd', {}),
                    'error': str(call.excinfo) if call.excinfo else None
                }
                
                if story not in self.results:
                    self.results[story] = []
                self.results[story].append(result)
    
    def save_results(self, output_path: Path):
        """Save test results to JSON file"""
        output_path.write_text(json.dumps(self.results, indent=2))

# conftest.py addition
def pytest_configure(config):
    config.pluginmanager.register(ATDDTestCollector(), "atdd_collector")
```

### Dashboard Generator
```python
# atdd_dashboard.py
from django.template.loader import render_to_string
from pathlib import Path
import json
from datetime import datetime
from .atdd_parser import UserStoryParser
from .test_collector import ATDDTestCollector

class ATDDDashboardGenerator:
    def __init__(self):
        self.docs_path = Path("docs/user_stories")
        self.results_path = Path("test_results/atdd_results.json")
        self.dashboard_path = Path("docs/atdd_dashboard")
        
    def generate_reports(self):
        """Generate comprehensive ATDD dashboard"""
        # Parse user stories
        parser = UserStoryParser(self.docs_path)
        stories = parser.parse_all_stories()
        
        # Load test results
        test_results = self.load_test_results()
        
        # Generate dashboard pages
        self.generate_overview(stories, test_results)
        self.generate_story_details(stories, test_results)
        self.generate_coverage_report(stories, test_results)
        
    def load_test_results(self) -> dict:
        """Load latest test results"""
        if self.results_path.exists():
            return json.loads(self.results_path.read_text())
        return {}
    
    def generate_overview(self, stories: dict, test_results: dict):
        """Generate main dashboard overview"""
        summary = self.calculate_summary(stories, test_results)
        
        html = render_to_string('atdd/overview.html', {
            'summary': summary,
            'stories': stories,
            'test_results': test_results,
            'generated_at': datetime.now()
        })
        
        (self.dashboard_path / "index.html").write_text(html)
    
    def calculate_summary(self, stories: dict, test_results: dict) -> dict:
        """Calculate overall project metrics"""
        total_criteria = 0
        completed_criteria = 0
        tested_criteria = 0
        passing_tests = 0
        total_tests = 0
        
        for story_key, criteria_list in stories.items():
            for criteria in criteria_list:
                total_criteria += 1
                
                if criteria.status == '✅':
                    completed_criteria += 1
                    
                # Check if criteria has test coverage
                story_tests = test_results.get(story_key, [])
                for test in story_tests:
                    total_tests += 1
                    if test['criteria_id'] == criteria.criteria_id:
                        tested_criteria += 1
                        if test['status'] == 'PASS':
                            passing_tests += 1
        
        return {
            'total_criteria': total_criteria,
            'completed_criteria': completed_criteria,
            'tested_criteria': tested_criteria,
            'coverage_percentage': (tested_criteria / total_criteria * 100) if total_criteria > 0 else 0,
            'test_pass_rate': (passing_tests / total_tests * 100) if total_tests > 0 else 0,
            'total_tests': total_tests
        }
```

### Django Management Command
```python
# management/commands/run_atdd_dashboard.py
from django.core.management.base import BaseCommand
from django.test.utils import get_runner
from django.conf import settings
from atdd_tracker.dashboard import ATDDDashboardGenerator
import subprocess
import json

class Command(BaseCommand):
    help = 'Run tests and generate ATDD dashboard'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--generate-only',
            action='store_true',
            help='Only generate dashboard from existing test results'
        )
        
    def handle(self, *args, **options):
        if not options['generate_only']:
            # Run tests with ATDD collection
            self.stdout.write("Running tests with ATDD collection...")
            result = subprocess.run([
                'pytest', 
                '--json-report', 
                '--json-report-file=test_results/atdd_results.json',
                '-v'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                self.stdout.write(
                    self.style.WARNING(f"Tests failed: {result.stderr}")
                )
        
        # Generate dashboard
        self.stdout.write("Generating ATDD dashboard...")
        dashboard = ATDDDashboardGenerator()
        dashboard.generate_reports()
        
        self.stdout.write(
            self.style.SUCCESS("ATDD Dashboard generated at docs/atdd_dashboard/")
        )
```

### Dashboard Templates
```html
<!-- templates/atdd/overview.html -->
<!DOCTYPE html>
<html>
<head>
    <title>ATDD Dashboard - BudgNudg</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container">
        <h1>Acceptance Test-Driven Development Dashboard</h1>
        <p class="text-muted">Generated: {{ generated_at }}</p>
        
        <div class="row">
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5>Total Criteria</h5>
                        <h2>{{ summary.total_criteria }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5>Test Coverage</h5>
                        <h2>{{ summary.coverage_percentage|floatformat:1 }}%</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5>Pass Rate</h5>
                        <h2>{{ summary.test_pass_rate|floatformat:1 }}%</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body">
                        <h5>Total Tests</h5>
                        <h2>{{ summary.total_tests }}</h2>
                    </div>
                </div>
            </div>
        </div>
        
        <h2 class="mt-4">User Stories</h2>
        <div class="row">
            {% for story_key, criteria_list in stories.items %}
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-header">
                        <h5>{{ story_key|title }}</h5>
                    </div>
                    <div class="card-body">
                        <div class="criteria-status">
                            {% for criteria in criteria_list %}
                            <span class="badge 
                                {% if criteria.status == '✅' %}bg-success
                                {% elif criteria.status == '🚧' %}bg-warning  
                                {% elif criteria.status == '⏳' %}bg-secondary
                                {% else %}bg-light{% endif %}">
                                {{ criteria.status }}
                            </span>
                            {% endfor %}
                        </div>
                        <p class="mt-2">
                            {{ criteria_list|length }} acceptance criteria
                        </p>
                        <a href="story_{{ story_key|slugify }}.html" class="btn btn-primary">
                            View Details
                        </a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

## Integration with Existing Tests

### Example: Enhanced Ingest Test
```python
# ingest/tests/test_acceptance_ingest_happy_path.py
from atdd_tracker import acceptance_test, user_story

@user_story("ingest", "import_csv_transactions")  
@acceptance_test(
    name="CSV Upload Validation",
    criteria_id="csv_upload_validation", 
    given="I have a valid CSV file with transaction data",
    when="I upload it through the web interface",
    then="the system validates the format and creates an import batch"
)
def test_upload_creates_batch_and_rows(client, csv_bytes_basic):
    # existing implementation unchanged
    resp = _upload(client, csv_bytes_basic)
    assert resp.status_code == 200
    batch = ImportBatch.objects.order_by("-id").first()
    assert batch is not None
    assert batch.status == "uploaded"
    assert batch.rows.count() == 2

@user_story("ingest", "import_csv_transactions")
@acceptance_test(
    name="Profile Application", 
    criteria_id="csv_profile_mapping",
    given="I have uploaded a CSV file and have a matching profile",
    when="I apply the profile to map columns",
    then="the system parses data correctly and shows preview"
)
def test_apply_profile_populates_parsed_normals_and_preview(
    client, profile_basic, csv_bytes_basic
):
    # existing implementation unchanged
    # ... rest of test
```

## Usage Workflow

1. **Write User Stories** with criteria IDs in markdown
2. **Write Tests** with ATDD annotations linking to criteria IDs  
3. **Run Dashboard Command**: `./manage.py run_atdd_dashboard`
4. **View Living Documentation** at `docs/atdd_dashboard/index.html`

## Benefits

- **Traceability**: Direct link between requirements and tests
- **Coverage Visibility**: See which criteria lack test coverage
- **Living Documentation**: Always up-to-date test status
- **Team Communication**: Shared understanding of progress
- **Quality Metrics**: Track testing effectiveness over time

This system would transform your user story files into a living acceptance test dashboard that shows real-time progress on implementing your requirements.