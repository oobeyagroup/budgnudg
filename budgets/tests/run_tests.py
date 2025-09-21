"""
Test runner for budget app tests.

Run specific test suites or all budget tests.
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner


def run_budget_tests():
    """Run all budget app tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgnudg.settings")
    django.setup()

    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    # Run all budget tests
    failures = test_runner.run_tests(
        [
            "budgets.tests.test_models",
            "budgets.tests.test_services",
            "budgets.tests.test_views",
        ]
    )

    if failures:
        sys.exit(bool(failures))
    else:
        print("✓ All budget tests passed!")


def run_model_tests():
    """Run only model tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgnudg.settings")
    django.setup()

    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    failures = test_runner.run_tests(["budgets.tests.test_models"])

    if failures:
        sys.exit(bool(failures))
    else:
        print("✓ Budget model tests passed!")


def run_service_tests():
    """Run only service tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgnudg.settings")
    django.setup()

    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    failures = test_runner.run_tests(["budgets.tests.test_services"])

    if failures:
        sys.exit(bool(failures))
    else:
        print("✓ Budget service tests passed!")


def run_view_tests():
    """Run only view tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "budgnudg.settings")
    django.setup()

    TestRunner = get_runner(settings)
    test_runner = TestRunner()

    failures = test_runner.run_tests(["budgets.tests.test_views"])

    if failures:
        sys.exit(bool(failures))
    else:
        print("✓ Budget view tests passed!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run budget app tests")
    parser.add_argument("--models", action="store_true", help="Run model tests only")
    parser.add_argument(
        "--services", action="store_true", help="Run service tests only"
    )
    parser.add_argument("--views", action="store_true", help="Run view tests only")

    args = parser.parse_args()

    if args.models:
        run_model_tests()
    elif args.services:
        run_service_tests()
    elif args.views:
        run_view_tests()
    else:
        run_budget_tests()
