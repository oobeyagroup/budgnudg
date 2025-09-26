# atdd_tracker.py
"""
Acceptance Test-Driven Development tracker for linking user stories to automated tests.

This module provides decorators and utilities to annotate tests with user story
and acceptance criteria information, enabling generation of living documentation
that shows the real-time status of acceptance criteria implementation.
"""

import functools
import json
from typing import Dict, List, Optional, NamedTuple
from pathlib import Path


class TestMetadata(NamedTuple):
    """Metadata structure for ATDD test annotations."""

    story_path: str
    criteria_id: str
    test_name: str
    bdd_given: str
    bdd_when: str
    bdd_then: str


# Global registry for test mappings
TEST_REGISTRY: Dict[str, List[TestMetadata]] = {}


def user_story(app: str, story: str):
    """
    Link a test to a specific user story file.

    Args:
        app: The application name (e.g., 'ingest', 'transactions', 'budgets')
        story: The story filename without extension (e.g., 'import_csv_transactions')

    Example:
        @user_story("ingest", "import_csv_transactions")
        def test_upload_validation():
            pass
    """

    def decorator(func):
        if not hasattr(func, "_atdd_metadata"):
            func._atdd_metadata = {}
        func._atdd_metadata["story"] = f"{app}/{story}"
        return func

    return decorator


def acceptance_test(name: str, criteria_id: str, given: str, when: str, then: str):
    """
    Map a test to specific acceptance criteria with BDD format.

    Args:
        name: Human-readable test name
        criteria_id: Unique identifier matching the criteria ID in the user story markdown
        given: BDD Given clause describing the initial state
        when: BDD When clause describing the action
        then: BDD Then clause describing the expected outcome

    Example:
        @acceptance_test(
            name="CSV Upload Validation",
            criteria_id="csv_upload_validation",
            given="I have a valid CSV file",
            when="I upload it through the interface",
            then="the system validates format and creates import batch"
        )
        def test_upload_creates_batch():
            pass
    """

    def decorator(func):
        if not hasattr(func, "_atdd_metadata"):
            func._atdd_metadata = {}

        func._atdd_metadata.update(
            {
                "test_name": name,
                "criteria_id": criteria_id,
                "bdd": {"given": given, "when": when, "then": then},
            }
        )

        # Register in global registry
        story = func._atdd_metadata.get("story", "unknown")
        if story not in TEST_REGISTRY:
            TEST_REGISTRY[story] = []

        TEST_REGISTRY[story].append(
            TestMetadata(
                story_path=story,
                criteria_id=criteria_id,
                test_name=name,
                bdd_given=given,
                bdd_when=when,
                bdd_then=then,
            )
        )

        return func

    return decorator


def get_test_registry() -> Dict[str, List[TestMetadata]]:
    """
    Get the current test registry mapping stories to their tests.

    Returns:
        Dictionary mapping story paths to lists of test metadata
    """
    return TEST_REGISTRY.copy()


def clear_test_registry():
    """Clear the test registry (useful for testing)."""
    global TEST_REGISTRY
    TEST_REGISTRY = {}


def save_test_registry(output_path: Path):
    """
    Save the current test registry to a JSON file.

    Args:
        output_path: Path where to save the registry JSON
    """
    serializable_registry = {}
    for story_path, tests in TEST_REGISTRY.items():
        serializable_registry[story_path] = [
            {
                "story_path": test.story_path,
                "criteria_id": test.criteria_id,
                "test_name": test.test_name,
                "bdd": {
                    "given": test.bdd_given,
                    "when": test.bdd_when,
                    "then": test.bdd_then,
                },
            }
            for test in tests
        ]

    output_path.write_text(json.dumps(serializable_registry, indent=2))


class ATDDValidator:
    """Utility class for validating ATDD annotations."""

    @staticmethod
    def validate_metadata(func) -> Optional[str]:
        """
        Validate that a test function has proper ATDD metadata.

        Args:
            func: Test function to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not hasattr(func, "_atdd_metadata"):
            return f"Test {func.__name__} missing ATDD metadata"

        metadata = func._atdd_metadata

        if "story" not in metadata:
            return f"Test {func.__name__} missing @user_story decorator"

        if "criteria_id" not in metadata:
            return f"Test {func.__name__} missing @acceptance_test decorator"

        required_bdd = ["given", "when", "then"]
        bdd = metadata.get("bdd", {})

        for clause in required_bdd:
            if clause not in bdd or not bdd[clause]:
                return f"Test {func.__name__} missing BDD '{clause}' clause"

        return None

    @staticmethod
    def find_orphaned_tests(
        test_functions: List, user_story_criteria: Dict[str, List[str]]
    ) -> List[str]:
        """
        Find tests that reference criteria IDs that don't exist in user stories.

        Args:
            test_functions: List of test functions with ATDD metadata
            user_story_criteria: Dict mapping story paths to lists of criteria IDs

        Returns:
            List of error messages for orphaned tests
        """
        errors = []

        for func in test_functions:
            if not hasattr(func, "_atdd_metadata"):
                continue

            metadata = func._atdd_metadata
            story_path = metadata.get("story")
            criteria_id = metadata.get("criteria_id")

            if story_path and criteria_id:
                story_criteria = user_story_criteria.get(story_path, [])
                if criteria_id not in story_criteria:
                    errors.append(
                        f"Test {func.__name__} references criteria '{criteria_id}' "
                        f"not found in story '{story_path}'"
                    )

        return errors
