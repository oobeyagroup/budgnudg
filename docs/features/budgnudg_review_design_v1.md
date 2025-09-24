# BudgNudg: Behavioral Review & Recommendation System (v1)

A weekly, monthly, quarterly review wizard.  

Goals:  
1. A UI to support discussion by a couple about their spending patterns
2. To create a set of specific actions and behavior recommendation to improve alignment between  spending behavior and budget plan.

UI: Gamify a monthly transaction by transaction assessment. Each transaction is scored by the user based on their reflection of whether it was a 'good' purchase on a scale of 1-5.  Multiple users (ex. husband an wife) can score the transaction.  This does not need be supported by a whole user account apparatus.  A transaction can just have multiple score values (limit 5).   This leaves us with each transaction having 1-5 score values from which we can derive a single score value and range if multiple.

Analysis:  Combining the transactions category, subcategory, payoree and payoree.needs_level field and the new evaluation field, each category and subcategory can be assigned a grade and set of recommendations, even down to the payoree, for the coming period.

Output: Specific actions and behaviors for the coming time period

Output Examples: "Reduce grocery spending", "Skip restaurants this month", "Can splurge on clothes or gifts this quarter"


## 🧩 Model Changes

**Transaction model:**
```python
# In transactions/models.py
score_value = models.PositiveSmallIntegerField(
    null=True, blank=True,
    help_text="User reflection score: 1 (regret) to 5 (proud)"
)
```
- Stores a single numeric score representing user reflection on the transaction quality.
- Editable in Django admin for convenience.

**Optional @property for summary:**
```python
@property
def score_summary(self):
    if not self.score_value:
        return None
    return self.score_value  # Placeholder for future aggregation logic
```

---

## 🧠 Review Wizard Design

### Structure
The review process is **fractal**, meaning:
- **Quarterly** review depends on 3 completed **Monthly** reviews.
- **Monthly** review depends on 4–5 completed **Weekly** reviews.

### UI Flow
1. **Launch Wizard (Weekly, Monthly, or Quarterly)**
2. **If lower-level reviews are missing**, guide the user to complete those first.
3. **Transaction Review UI** (for each period):
   - View: Date, Payoree, Amount, Needs Level, Category, Subcategory
   - Input: 1–5 scale with labels
4. **Summary Report:**
   - Average scores by category, subcategory, and payoree.
   - Budget variance.
   - Recommendation suggestions.

---

## 🧠 Analysis Strategy

### Score Scale (Fixed)
| Score | Label         |
|-------|---------------|
| 1     | Deep Regret   |
| 2     | Some Regret   |
| 3     | Neutral       |
| 4     | Satisfied     |
| 5     | Proud         |

### Aggregation Targets
- Average score per **category**, **subcategory**, **payoree**, and **needs_level**
- Count of scored transactions (must be ≥3 to generate insights)
- Actual spend vs. Budget

### Judging Behavior Based on Score

| Avg Score Range | Interpretation         | Suggested Nudge                    |
|-----------------|------------------------|------------------------------------|
| 4.5–5.0         | Excellent alignment     | “Continue as is”                   |
| 3.5–4.4         | Generally aligned       | “Maintain spending”                |
| 2.5–3.4         | Neutral/conflicted      | “Review choices more carefully”    |
| 1.5–2.4         | Misaligned              | “Reduce spending in this area”     |
| < 1.5           | Strong misalignment     | “Pause or eliminate spending here” |

### Recommendation Logic

#### Conditions:
- High spend + low score → “Cut Back”
- High spend + high score → “Sustain with caution”
- Low spend + low score → “Good restraint”
- Low spend + high score → “Room to enjoy more”

#### Output Examples:
- “Skip restaurants this month”
- “Continue spending on streaming services”
- “Pause Amazon purchases temporarily”
- “Consider switching grocery stores”

---

## 🚧 Recommended Design Steps

1. **Model Update:**
   - Add `score_value` to `Transaction` model and admin.

2. **Review Wizard UI:**
   - Weekly, Monthly, Quarterly selection
   - Show pending reviews (based on completion logic)
   - Paginated batch scoring interface

3. **Analysis Engine:**
   - Score aggregation & budget comparison
   - Rule-based recommendation generation

4. **Output Summary UI:**
   - Human-readable recommendation list
   - Color-coded heatmap for alignment indicators

---

## ✅ Finalized Design Plan (v1)

- Single score per transaction (1–5 scale)
- Editable through the review wizard or admin
- Weekly → Monthly → Quarterly dependency enforced
- Reflective gamified review with minimal keystrokes
- Insights derived from score + budget variance
- Text-based and visual recommendations for the next period
- Option to auto assign or filter out recurring transactions
---

## 🧪 Future Enhancements

- Support for multiple scores per transaction (multi-user households)
- Optional feedback comment field per transaction
- Longitudinal trend graphs for category behavior
- AI-generated recommendation tuning over time