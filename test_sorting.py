#!/usr/bin/env python3
"""
Test script to verify the Budget Report sorting logic matches the Payoree Report sorting.
"""


def budget_sort_key(item):
    """Same sorting logic used in both payoree report and budget report"""
    total = item[1]["total_amount"]
    # positives: (0, -total), negatives: (1, total)
    return (0, -total) if total >= 0 else (1, total)


# Test data simulating categories/subcategories with different total amounts
test_data = [
    ("Category A", {"total_amount": 1000.0}),
    ("Category B", {"total_amount": -500.0}),
    ("Category C", {"total_amount": 200.0}),
    ("Category D", {"total_amount": -800.0}),
    ("Category E", {"total_amount": 50.0}),
    ("Category F", {"total_amount": -200.0}),
]

print("Original order:")
for name, data in test_data:
    print(f"  {name}: ${data['total_amount']}")

print("\nSorted order (positives descending, negatives ascending):")
sorted_data = sorted(test_data, key=budget_sort_key)
for name, data in sorted_data:
    print(f"  {name}: ${data['total_amount']}")

print("\nExpected result:")
print("  Category A: $1000.0  (highest positive)")
print("  Category C: $200.0   (next positive)")
print("  Category E: $50.0    (lowest positive)")
print("  Category D: $-800.0  (most negative)")
print("  Category B: $-500.0  (next most negative)")
print("  Category F: $-200.0  (least negative)")
