# Feature Feedback System - Implementation Guide

**Created:** April 12, 2026  
**Purpose:** Collect user feedback on features to continuously improve the product

---

## 🎯 Overview

This system implements a **3-question survey** that appears after users complete key actions:

1. **Did this work as expected?** (Yes/No)
2. **What do you like?** (Optional text)
3. **What could be improved?** (Optional text)
4. **Star rating** (1-5 stars)

---

## 📋 When to Show Feedback

Show the survey after these actions:

### AI Features
- ✅ **After AI duplicate detection completes**
- ✅ **After AI transcription finishes**
- ✅ **After AI PDF comparison**

### Manual Features  
- ✅ **After manual transcription upload**
- ✅ **After algorithm duplicate detection**
- ✅ **After PDF assembly/export**

### Frequency
- **Once per week** per feature per user
- Track in localStorage: `feedback_shown_${feature}_${userId}_${week}`
- Don't annoy users - only ask for feedback occasionally

---

## 🗄️ Database Models

### FeatureFeedback
Stores individual feedback submissions:

```python
class FeatureFeedback(models.Model):
    user = ForeignKey(User)
    feature = CharField(choices=[
        'ai_duplicate_detection',
        'ai_transcription',
        'ai_pdf_comparison',
        'manual_transcription',
        'algorithm_detection',
        'pdf_upload',
        'audio_assembly',
        'project_management',
        'other'
    ])
    
    # Survey responses
    worked_as_expected = BooleanField()
    what_you_like = TextField(blank=True)
    what_to_improve = TextField(blank=True)
    rating = IntegerField(1-5)
    
    # Metadata
    audio_file_id = IntegerField(optional)
    user_plan = CharField()  # Auto-populated
    created_at = DateTimeField()
    
    # Admin
    admin_notes = TextField()
    status = CharField()  # new, reviewed, addressed, implemented
```

### FeatureFeedbackSummary
Aggregated statistics updated nightly:

```python
class FeatureFeedbackSummary(models.Model):
    feature = CharField(unique=True)
    total_responses = IntegerField()
    average_rating = DecimalField()
    
    rating_5_count = IntegerField()
    rating_4_count = IntegerField()
    rating_3_count = IntegerField()
    rating_2_count = IntegerField()
    rating_1_count = IntegerField()
    
    worked_as_expected_count = IntegerField()
    worked_as_expected_percentage = DecimalField()
    
    last_updated = DateTimeField()
```

---

## 🚀 Implementation

### Step 1: Run Migrations

```bash
ssh nickd@82.165.221.205
cd /opt/audioapp/backend

# Add feedback models to accounts/models.py
cat >> accounts/models.py << 'EOF'

# Import feedback models
from .models_feedback import FeatureFeedback, FeatureFeedbackSummary
EOF

# Create migration
python manage.py makemigrations accounts
python manage.py migrate

# Verify tables created
python manage.py dbshell
> \dt accounts_featurefeedback*
> \q
```

### Step 2: Add URL Routes

```python
# accounts/urls.py

from .views_feedback import (
    submit_feedback,
    user_feedback_history,
    feature_summary,
    all_feature_summaries,
    quick_feedback,
    FeatureFeedbackListView
)

urlpatterns = [
    # ... existing routes ...
    
    # Feedback routes
    path('feedback/submit/', submit_feedback, name='submit_feedback'),
    path('feedback/my-feedback/', user_feedback_history, name='user_feedback_history'),
    path('feedback/summary/<str:feature_name>/', feature_summary, name='feature_summary'),
    path('feedback/summaries/', all_feature_summaries, name='all_feature_summaries'),
    path('feedback/quick/', quick_feedback, name='quick_feedback'),
    path('feedback/all/', FeatureFeedbackListView.as_view(), name='all_feedback'),
]
```

### Step 3: Frontend Integration

**Add to Tab3Duplicates.js** (after AI detection completes):

```javascript
import FeedbackSurvey from '../FeedbackSurvey';

function Tab3Duplicates() {
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackFeature, setFeedbackFeature] = useState(null);

  const handleAIDetectDuplicates = async () => {
    // ... existing code ...
    
    // After AI detection completes successfully
    if (statusPayload.state === 'SUCCESS') {
      await loadDuplicateGroups();
      
      // Check if should show feedback
      const shouldShow = shouldShowFeedback('ai_duplicate_detection');
      if (shouldShow) {
        setFeedbackFeature('ai_duplicate_detection');
        setShowFeedback(true);
      }
    }
  };

  const shouldShowFeedback = (featureName) => {
    const userId = localStorage.getItem('userId');
    const currentWeek = new Date().toISOString().slice(0, 10);
    const key = `feedback_shown_${featureName}_${userId}_${currentWeek}`;
    
    if (localStorage.getItem(key)) {
      return false; // Already shown this week
    }
    
    // 50% chance to show (don't annoy users)
    if (Math.random() > 0.5) {
      localStorage.setItem(key, 'true');
      return true;
    }
    
    return false;
  };

  const handleFeedbackSubmit = (feedbackData) => {
    console.log('Feedback submitted:', feedbackData);
    // Could show a thank you message
  };

  return (
    <>
      {/* ... existing component ... */}
      
      {showFeedback && (
        <FeedbackSurvey
          feature={feedbackFeature}
          featureName="AI Duplicate Detection"
          audioFileId={selectedAudioFile?.id}
          onClose={() => setShowFeedback(false)}
          onSubmit={handleFeedbackSubmit}
        />
      )}
    </>
  );
}
```

---

## 📊 Admin Dashboard

### View All Feedback

Navigate to Django Admin:
```
https://audio.precisepouchtrack.com/admin/accounts/featurefeedback/
```

**Filters:**
- By feature
- By rating
- By status (new, reviewed, etc.)
- By "needs attention" (rating ≤ 2 or didn't work as expected)

### View Summary Statistics

```bash
python manage.py shell

from accounts.models_feedback import FeatureFeedbackSummary

# Update all summaries
for feature in ['ai_duplicate_detection', 'ai_transcription', 'manual_transcription']:
    FeatureFeedbackSummary.update_summary(feature)

# View summary
summary = FeatureFeedbackSummary.objects.get(feature='ai_duplicate_detection')
print(f"AI Duplicate Detection: {summary.average_rating}/5 stars")
print(f"Total responses: {summary.total_responses}")
print(f"Worked as expected: {summary.worked_as_expected_percentage}%")
```

### Set Up Nightly Summary Update

**Create:** `backend/accounts/management/commands/update_feedback_summaries.py`

```python
from django.core.management.base import BaseCommand
from accounts.models_feedback import FeatureFeedback, FeatureFeedbackSummary

class Command(BaseCommand):
    help = 'Update feature feedback summaries'

    def handle(self, *args, **kwargs):
        features = FeatureFeedback.objects.values_list('feature', flat=True).distinct()
        
        for feature in features:
            summary = FeatureFeedbackSummary.update_summary(feature)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated {feature}: {summary.total_responses} responses, '
                    f'{summary.average_rating}/5 avg'
                )
            )
```

**Add to crontab:**
```bash
# Run daily at 2am
0 2 * * * cd /opt/audioapp/backend && python manage.py update_feedback_summaries
```

---

## 📈 Using Feedback Data

### Identify Problem Areas

```python
# Features that need attention
problems = FeatureFeedback.objects.filter(
    rating__lte=2
) | FeatureFeedback.objects.filter(
    worked_as_expected=False
)

for feedback in problems:
    print(f"\n{feedback.user.username} - {feedback.get_feature_display()}")
    print(f"Rating: {feedback.rating}/5")
    print(f"Worked as expected: {feedback.worked_as_expected}")
    print(f"Improve: {feedback.what_to_improve}")
```

### Track Feature Performance Over Time

```python
from django.db.models import Avg, Count
from datetime import datetime, timedelta

# Last 30 days average rating per feature
thirty_days_ago = datetime.now() - timedelta(days=30)

stats = FeatureFeedback.objects.filter(
    created_at__gte=thirty_days_ago
).values('feature').annotate(
    avg_rating=Avg('rating'),
    total=Count('id'),
    worked_count=Count('id', filter=Q(worked_as_expected=True))
)

for stat in stats:
    worked_pct = (stat['worked_count'] / stat['total']) * 100
    print(f"{stat['feature']}: {stat['avg_rating']:.1f}/5 ({worked_pct:.0f}% worked)")
```

### Export for Analysis

```python
import csv

# Export all feedback to CSV
feedbacks = FeatureFeedback.objects.all().select_related('user')

with open('feedback_export.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        'Date', 'User', 'Plan', 'Feature', 'Worked as Expected',
        'Rating', 'What You Like', 'What to Improve'
    ])
    
    for f in feedbacks:
        writer.writerow([
            f.created_at.strftime('%Y-%m-%d'),
            f.user.username,
            f.user_plan,
            f.get_feature_display(),
            'Yes' if f.worked_as_expected else 'No',
            f.rating,
            f.what_you_like,
            f.what_to_improve
        ])
```

---

## 🎨 Customization

### Change Survey Questions

Edit `FeedbackSurvey.jsx`:

```javascript
// Add custom questions
<div className="feedback-question">
  <label>How easy was this to use? (1-5)</label>
  <input 
    type="range" 
    min="1" 
    max="5" 
    value={easeOfUse}
    onChange={(e) => setEaseOfUse(e.target.value)}
  />
</div>
```

### Change When to Show

```javascript
// Show after every 3rd use
const useCount = parseInt(localStorage.getItem(`${feature}_use_count`) || 0) + 1;
localStorage.setItem(`${feature}_use_count`, useCount);

if (useCount % 3 === 0) {
  setShowFeedback(true);
}
```

### Custom Styling

Edit `FeedbackSurvey.css` to match your brand colors.

---

## 📊 Analytics Dashboard

### Create Public Stats Page

Show users how features are rated:

```jsx
// frontend/src/pages/FeatureStats.jsx

function FeatureStats() {
  const [summaries, setSummaries] = useState([]);
  
  useEffect(() => {
    fetch('/api/feedback/summaries/')
      .then(res => res.json())
      .then(data => setSummaries(data.summaries));
  }, []);
  
  return (
    <div className="feature-stats">
      <h1>Feature Ratings</h1>
      
      {summaries.map(summary => (
        <div key={summary.feature} className="feature-card">
          <h2>{summary.feature}</h2>
          <div className="rating">
            {summary.average_rating}/5 ⭐
          </div>
          <div className="stats">
            <p>{summary.total_responses} reviews</p>
            <p>{summary.worked_as_expected_percentage}% satisfied</p>
          </div>
          
          <div className="rating-bars">
            {[5,4,3,2,1].map(rating => (
              <div key={rating} className="bar">
                <span>{rating}★</span>
                <div className="bar-fill" style={{
                  width: `${(summary[`rating_${rating}_count`] / summary.total_responses) * 100}%`
                }} />
                <span>{summary[`rating_${rating}_count`]}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## 🔔 Notifications

### Email Alerts for Low Ratings

```python
# accounts/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models_feedback import FeatureFeedback

@receiver(post_save, sender=FeatureFeedback)
def notify_low_rating(sender, instance, created, **kwargs):
    """Send email alert for ratings ≤ 2"""
    if created and instance.rating <= 2:
        send_mail(
            subject=f'Low Rating Alert: {instance.get_feature_display()}',
            message=f"""
            User: {instance.user.username}
            Feature: {instance.get_feature_display()}
            Rating: {instance.rating}/5
            Worked as expected: {instance.worked_as_expected}
            
            What to improve:
            {instance.what_to_improve}
            
            View: https://audio.precisepouchtrack.com/admin/accounts/featurefeedback/{instance.id}/
            """,
            from_email='alerts@precisepouchtrack.com',
            recipient_list=['support@precisepouchtrack.com'],
            fail_silently=True,
        )
```

---

## 🧪 Testing

### Test Feedback Submission

```bash
curl -X POST http://audio.precisepouchtrack.com/api/feedback/submit/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "feature": "ai_duplicate_detection",
    "worked_as_expected": true,
    "what_you_like": "Very fast and accurate!",
    "what_to_improve": "Could show more detail on confidence scores",
    "rating": 5,
    "audio_file_id": 123
  }'
```

### Test Summary Endpoint

```bash
curl http://audio.precisepouchtrack.com/api/feedback/summary/ai_duplicate_detection/
```

---

## 📋 Deployment Checklist

- [ ] Add feedback models to `accounts/models.py`
- [ ] Run migrations
- [ ] Add URL routes
- [ ] Deploy FeedbackSurvey component
- [ ] Integrate survey triggers in Tab3, Tab2, etc.
- [ ] Set up admin permissions
- [ ] Create nightly summary update cron job
- [ ] Test feedback submission
- [ ] Test admin dashboard
- [ ] Set up email alerts for low ratings
- [ ] Update Free Trial plan: ai_monthly_cost_limit=1.00 (1 free AI test)
- [ ] Create public stats page (optional)

---

## 💡 Best Practices

### Timing
- **Don't show immediately** - Wait 1-2 seconds after action completes
- **Don't show too often** - Max once per week per feature
- **Random sampling** - Show to 50% of eligible users

### Questions
- **Keep it short** - 3 questions max
- **Make it optional** - Allow skip
- **Be specific** - "Did AI detection work as expected?" vs "Did this work?"

### Follow-up
- **Respond to negative feedback** - Email users with rating ≤ 2
- **Share improvements** - "Based on your feedback, we added..."
- **Show appreciation** - Thank users who provide feedback

---

## 🎯 Success Metrics

Track these weekly:

- **Response rate:** % of users who complete survey
- **Average rating per feature:** Target ≥ 4.0 stars
- **Worked as expected %:** Target ≥ 90%
- **Actionable feedback:** Comments with specific suggestions
- **Improvement rate:** % of feedback marked "implemented"

---

**Implementation Time:** 2-3 hours  
**Maintenance:** ~30 min/week to review feedback  
**Value:** Priceless insights for product improvement 🚀
