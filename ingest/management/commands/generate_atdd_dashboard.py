# ingest/management/commands/generate_atdd_dashboard.py
"""
Django management command to generate ATDD dashboard.

This command:
1. Parses user story markdown files for acceptance criteria
2. Collects test metadata from test files
3. Runs tests and captures results
4. Generates HTML dashboard showing test coverage and status

Usage:
    ./manage.py generate_atdd_dashboard
    ./manage.py generate_atdd_dashboard --generate-only  # Skip test run
"""

from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.conf import settings
from pathlib import Path
import subprocess
import json
import re
import importlib
import sys
from datetime import datetime
from typing import Dict, List, NamedTuple, Optional


class AcceptanceCriteria(NamedTuple):
    """Structure for acceptance criteria parsed from markdown."""

    criteria_id: str
    status: str  # ✅, 🚧, ⏳, 💡, etc.
    description: str
    category: str


class TestResult(NamedTuple):
    """Structure for test execution results."""

    test_name: str
    criteria_id: str
    status: str  # PASS, FAIL, SKIP
    duration: float
    error_message: Optional[str]


class ATDDDashboardGenerator:
    """Generator for ATDD dashboard from user stories and tests."""

    def __init__(self):
        self.project_root = Path(settings.BASE_DIR)
        self.docs_path = self.project_root / "docs" / "user_stories"
        self.dashboard_path = self.project_root / "docs" / "atdd_dashboard"
        self.dashboard_path.mkdir(exist_ok=True)

    def parse_user_stories(self) -> Dict[str, List[AcceptanceCriteria]]:
        """Parse all user story markdown files for acceptance criteria."""
        stories = {}

        if not self.docs_path.exists():
            return stories

        for story_file in self.docs_path.rglob("*.md"):
            if "atdd" in story_file.name:  # Use ATDD-enhanced versions
                relative_path = story_file.relative_to(self.docs_path)
                story_key = str(relative_path.with_suffix(""))
                story_key = story_key.replace(
                    "_atdd", ""
                )  # Remove ATDD suffix for matching

                stories[story_key] = self.parse_story_file(story_file)

        return stories

    def parse_story_file(self, file_path: Path) -> List[AcceptanceCriteria]:
        """Parse individual story file for acceptance criteria with IDs."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return []

        criteria = []
        current_category = "General"

        # Find acceptance criteria section
        criteria_section = re.search(
            r"## Acceptance Criteria\s*\n(.*?)(?=\n## |$)", content, re.DOTALL
        )

        if not criteria_section:
            return criteria

        criteria_text = criteria_section.group(1)

        # Parse categories and criteria
        for line in criteria_text.split("\n"):
            line = line.strip()

            # Category headers (### Something)
            category_match = re.match(r"^### (.+)$", line)
            if category_match:
                current_category = category_match.group(1)
                continue

            # Criteria items with IDs: - [ ] ✅ `criteria_id` Description
            criteria_match = re.match(r"^- \[ \] ([✅🚧⏳💡❌]) `([^`]+)` (.+)$", line)

            if criteria_match:
                status = criteria_match.group(1)
                criteria_id = criteria_match.group(2)
                description = criteria_match.group(3)

                criteria.append(
                    AcceptanceCriteria(
                        criteria_id=criteria_id,
                        status=status,
                        description=description,
                        category=current_category,
                    )
                )

        return criteria

    def collect_test_metadata(self) -> Dict[str, List[Dict]]:
        """Collect test metadata by importing test modules."""
        test_metadata = {}

        # Import atdd_tracker to access registry
        try:
            # Add project root to Python path
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            atdd_tracker = importlib.import_module("atdd_tracker")

            # Find and import all test files with ATDD annotations
            test_files = list(self.project_root.rglob("*test*atdd*.py"))

            for test_file in test_files:
                try:
                    # Convert file path to module name
                    relative_path = test_file.relative_to(self.project_root)
                    module_path = str(relative_path.with_suffix(""))
                    module_name = module_path.replace("/", ".")

                    # Import the test module to trigger decorator registration
                    importlib.import_module(module_name)

                except Exception as e:
                    print(f"Warning: Could not import test module {test_file}: {e}")

            # Get registered test metadata
            test_metadata = atdd_tracker.get_test_registry()

        except Exception as e:
            print(f"Warning: Could not collect test metadata: {e}")

        return test_metadata

    def run_tests_and_collect_results(self) -> Dict[str, List[TestResult]]:
        """Run pytest and collect test results."""
        results = {}

        try:
            # Run pytest with JSON reporting
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "--tb=short",
                    "-v",
                    "ingest/tests/test_acceptance_ingest_happy_path_atdd.py",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
            )

            # Parse pytest output for test results
            # This is a simplified parser - in production you'd use pytest-json-report
            output_lines = result.stdout.split("\n")

            for line in output_lines:
                # Look for test result lines
                if "::test_" in line and ("PASSED" in line or "FAILED" in line):
                    parts = line.split()
                    test_name = (
                        parts[0].split("::")[-1] if "::" in parts[0] else parts[0]
                    )
                    status = "PASS" if "PASSED" in line else "FAIL"

                    # Extract duration if available
                    duration = 0.0
                    for part in parts:
                        if "s]" in part and "[" in part:
                            try:
                                duration = float(part.strip("[]s"))
                            except ValueError:
                                pass

                    # For demo purposes, assign to ingest story
                    story_key = "ingest/import_csv_transactions"
                    if story_key not in results:
                        results[story_key] = []

                    results[story_key].append(
                        TestResult(
                            test_name=test_name,
                            criteria_id="unknown",  # Would need metadata parsing
                            status=status,
                            duration=duration,
                            error_message=None,
                        )
                    )

        except Exception as e:
            print(f"Warning: Could not run tests: {e}")

        return results

    def generate_dashboard_html(
        self, stories: Dict, test_metadata: Dict, test_results: Dict
    ):
        """Generate HTML dashboard."""

        # Calculate summary statistics
        summary = self.calculate_summary(stories, test_metadata, test_results)

        # Generate main dashboard page
        try:
            html_content = self.generate_html_template(
                summary, stories, test_metadata, test_results
            )

            dashboard_file = self.dashboard_path / "index.html"
            dashboard_file.write_text(html_content, encoding="utf-8")

            print(f"Dashboard generated at: {dashboard_file}")

        except Exception as e:
            print(f"Error generating dashboard: {e}")

    def calculate_summary(
        self, stories: Dict, test_metadata: Dict, test_results: Dict
    ) -> Dict:
        """Calculate overall metrics."""
        total_criteria = sum(len(criteria_list) for criteria_list in stories.values())
        completed_criteria = sum(
            1
            for criteria_list in stories.values()
            for criteria in criteria_list
            if criteria.status == "✅"
        )

        total_tests = sum(len(results) for results in test_results.values())
        passing_tests = sum(
            1
            for results in test_results.values()
            for result in results
            if result.status == "PASS"
        )

        return {
            "total_criteria": total_criteria,
            "completed_criteria": completed_criteria,
            "total_tests": total_tests,
            "passing_tests": passing_tests,
            "test_coverage": len(test_metadata),
            "pass_rate": (passing_tests / total_tests * 100) if total_tests > 0 else 0,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def generate_html_template(
        self, summary: Dict, stories: Dict, test_metadata: Dict, test_results: Dict
    ) -> str:
        """Generate HTML content for dashboard."""

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATDD Dashboard - BudgNudg</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .status-badge {{
            font-size: 1.2em;
            margin-right: 0.5em;
        }}
        .criteria-row {{
            padding: 0.5em;
            border-left: 3px solid #dee2e6;
            margin-bottom: 0.5em;
        }}
        .criteria-completed {{ border-left-color: #198754; }}
        .criteria-planned {{ border-left-color: #ffc107; }}
        .criteria-future {{ border-left-color: #6c757d; }}
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="row">
            <div class="col-12">
                <h1 class="mb-4">ATDD Dashboard</h1>
                <p class="text-muted">Acceptance Test-Driven Development Status</p>
                <p class="text-muted">Generated: {summary['generated_at']}</p>
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body text-center">
                        <h5 class="card-title">Total Criteria</h5>
                        <h2 class="text-primary">{summary['total_criteria']}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body text-center">
                        <h5 class="card-title">Completed</h5>
                        <h2 class="text-success">{summary['completed_criteria']}</h2>
                        <small class="text-muted">
                        {summary['completed_criteria']/summary['total_criteria']*100:.1f}%
                        </small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body text-center">
                        <h5 class="card-title">Tests</h5>
                        <h2 class="text-info">{summary['total_tests']}</h2>
                        <small class="text-muted">Pass Rate: {summary['pass_rate']:.1f}%</small>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card">
                    <div class="card-body text-center">
                        <h5 class="card-title">Coverage</h5>
                        <h2 class="text-warning">{summary['test_coverage']}</h2>
                        <small class="text-muted">Stories with tests</small>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- User Stories Detail -->
        <div class="row">
"""

        for story_key, criteria_list in stories.items():
            story_results = test_results.get(story_key, [])
            story_metadata = test_metadata.get(story_key, [])

            html += f"""
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">{story_key.replace('/', ' / ').title()}</h5>
                        <small class="text-muted">
                            {len(criteria_list)} criteria | 
                            {len(story_results)} tests | 
                            {sum(1 for r in story_results if r.status == 'PASS')} passing
                        </small>
                    </div>
                    <div class="card-body">
            """

            for criteria in criteria_list:
                css_class = {
                    "✅": "criteria-completed",
                    "🚧": "criteria-planned",
                    "⏳": "criteria-future",
                    "💡": "criteria-future",
                }.get(criteria.status, "criteria-future")

                # Find matching test
                matching_test = None
                for result in story_results:
                    if (
                        criteria.criteria_id in result.test_name
                        or result.criteria_id == criteria.criteria_id
                    ):
                        matching_test = result
                        break

                test_indicator = ""
                if matching_test:
                    if matching_test.status == "PASS":
                        test_indicator = (
                            "<span class='badge bg-success ms-2'>PASS</span>"
                        )
                    else:
                        test_indicator = (
                            "<span class='badge bg-danger ms-2'>FAIL</span>"
                        )
                else:
                    test_indicator = (
                        "<span class='badge bg-light text-dark ms-2'>NO TEST</span>"
                    )

                html += f"""
                        <div class="criteria-row {css_class}">
                            <span class="status-badge">{criteria.status}</span>
                            <strong>{criteria.criteria_id}</strong>: {criteria.description}
                            {test_indicator}
                        </div>
                """

            html += """
                    </div>
                </div>
            </div>
            """

        html += """
        </div>
    </div>
</body>
</html>
        """

        return html


class Command(BaseCommand):
    """Django management command for generating ATDD dashboard."""

    help = "Generate Acceptance Test-Driven Development dashboard"

    def add_arguments(self, parser):
        parser.add_argument(
            "--generate-only",
            action="store_true",
            help="Only generate dashboard from existing data, skip test run",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            help="Output directory for dashboard files",
            default="docs/atdd_dashboard",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting ATDD dashboard generation...")

        generator = ATDDDashboardGenerator()

        # Parse user stories
        self.stdout.write("Parsing user story files...")
        stories = generator.parse_user_stories()
        self.stdout.write(f"Found {len(stories)} user stories")

        # Collect test metadata
        self.stdout.write("Collecting test metadata...")
        test_metadata = generator.collect_test_metadata()
        self.stdout.write(f"Found metadata for {len(test_metadata)} test suites")

        # Run tests and collect results
        if not options["generate_only"]:
            self.stdout.write("Running tests...")
            test_results = generator.run_tests_and_collect_results()
            self.stdout.write(
                f"Collected results for {sum(len(results) for results in test_results.values())} tests"
            )
        else:
            test_results = {}
            self.stdout.write("Skipping test run...")

        # Generate dashboard
        self.stdout.write("Generating dashboard HTML...")
        generator.generate_dashboard_html(stories, test_metadata, test_results)

        self.stdout.write(self.style.SUCCESS(f"ATDD Dashboard generated successfully!"))
        self.stdout.write(f"View at: {generator.dashboard_path}/index.html")
