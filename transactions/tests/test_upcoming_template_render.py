from django.test import SimpleTestCase
from django.template import Template, Context
import datetime


class UpcomingTemplateRenderTests(SimpleTestCase):
    def test_rowspan_date_once_per_group(self):
        # build minimal context with one week containing one row with two transactions
        weeks = [
            {
                "week_start": datetime.date(2025, 9, 1),
                "rows": [
                    {
                        "date": datetime.date(2025, 9, 1),
                        "transactions": [
                            {"payoree": "Alice", "description": "", "amount": 10},
                            {"payoree": "Bob", "description": "", "amount": 20},
                        ],
                    }
                ],
            }
        ]

        tpl = Template(
            """{% for week in weeks %}{% for row in week.rows %}{% for t in row.transactions %}
                <tr>
                    {% if forloop.first %}
                        <td rowspan="{{ row.transactions|length }}">{{ row.date|date:"Y-m-d" }}</td>
                    {% endif %}
                    <td>{{ t.payoree|default:t.description }}</td>
                    <td>{{ t.amount }}</td>
                </tr>
            {% endfor %}{% endfor %}{% endfor %}"""
        )

        rendered = tpl.render(Context({"weeks": weeks}))

        # date should appear exactly once for the two transactions in the group
        assert rendered.count("2025-09-01") == 1
