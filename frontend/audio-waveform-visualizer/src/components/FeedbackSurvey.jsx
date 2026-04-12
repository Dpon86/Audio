import React, { useState } from 'react';
import './FeedbackSurvey.css';

/**
 * Feature Feedback Survey Modal
 * 
 * 3-question survey:
 * 1. Did this work as expected?
 * 2. What do you like?
 * 3. What could be improved?
 * 4. Star rating (1-5)
 */
const FeedbackSurvey = ({ 
  feature, 
  featureName, 
  audioFileId = null,
  onClose,
  onSubmit 
}) => {
  const [workedAsExpected, setWorkedAsExpected] = useState(null);
  const [whatYouLike, setWhatYouLike] = useState('');
  const [whatToImprove, setWhatToImprove] = useState('');
  const [rating, setRating] = useState(0);
  const [hoveredStar, setHoveredStar] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (workedAsExpected === null) {
      alert('Please answer: Did this work as expected?');
      return;
    }
    
    if (rating === 0) {
      alert('Please provide a star rating');
      return;
    }

    setIsSubmitting(true);

    const feedbackData = {
      feature: feature,
      worked_as_expected: workedAsExpected,
      what_you_like: whatYouLike.trim(),
      what_to_improve: whatToImprove.trim(),
      rating: rating,
      audio_file_id: audioFileId
    };

    try {
      const token = localStorage.getItem('authToken');
      const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
      
      const response = await fetch(`${API_BASE_URL}/api/feedback/submit/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(feedbackData)
      });

      const data = await response.json();

      if (data.success) {
        setSubmitted(true);
        
        // Call parent callback
        if (onSubmit) {
          onSubmit(feedbackData);
        }
        
        // Auto-close after 2 seconds
        setTimeout(() => {
          onClose();
        }, 2000);
      } else {
        alert('Failed to submit feedback: ' + (data.errors || 'Unknown error'));
        setIsSubmitting(false);
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
      alert('Failed to submit feedback. Please try again.');
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    if (window.confirm('Skip feedback? We really appreciate your input!')) {
      onClose();
    }
  };

  if (submitted) {
    return (
      <div className="feedback-overlay">
        <div className="feedback-modal feedback-success">
          <div className="success-icon">✓</div>
          <h2>Thank You!</h2>
          <p>Your feedback helps us improve the service.</p>
          <p className="closing-message">Closing...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="feedback-overlay">
      <div className="feedback-modal">
        <button className="feedback-close" onClick={handleSkip}>×</button>
        
        <h2 className="feedback-title">
          How was your experience?
        </h2>
        <p className="feedback-subtitle">{featureName}</p>

        <form onSubmit={handleSubmit} className="feedback-form">
          
          {/* Question 1: Did it work as expected? */}
          <div className="feedback-question">
            <label>Did this feature work as you expected?</label>
            <div className="feedback-yes-no">
              <button
                type="button"
                className={`btn-yes-no ${workedAsExpected === true ? 'selected' : ''}`}
                onClick={() => setWorkedAsExpected(true)}
              >
                ✓ Yes
              </button>
              <button
                type="button"
                className={`btn-yes-no ${workedAsExpected === false ? 'selected' : ''}`}
                onClick={() => setWorkedAsExpected(false)}
              >
                ✗ No
              </button>
            </div>
          </div>

          {/* Question 2: What do you like? */}
          <div className="feedback-question">
            <label htmlFor="what-you-like">What do you like about it?</label>
            <textarea
              id="what-you-like"
              value={whatYouLike}
              onChange={(e) => setWhatYouLike(e.target.value)}
              placeholder="Tell us what you enjoyed..."
              rows={3}
              maxLength={500}
            />
            <div className="char-count">{whatYouLike.length}/500</div>
          </div>

          {/* Question 3: What could be improved? */}
          <div className="feedback-question">
            <label htmlFor="what-to-improve">What could be improved or added?</label>
            <textarea
              id="what-to-improve"
              value={whatToImprove}
              onChange={(e) => setWhatToImprove(e.target.value)}
              placeholder="Suggestions for improvement..."
              rows={3}
              maxLength={500}
            />
            <div className="char-count">{whatToImprove.length}/500</div>
          </div>

          {/* Question 4: Star rating */}
          <div className="feedback-question">
            <label>How many stars would you rate this?</label>
            <div className="star-rating">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  className={`star ${star <= (hoveredStar || rating) ? 'filled' : ''}`}
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoveredStar(star)}
                  onMouseLeave={() => setHoveredStar(0)}
                  aria-label={`${star} star${star > 1 ? 's' : ''}`}
                >
                  ★
                </button>
              ))}
              {rating > 0 && (
                <span className="rating-text">{rating} out of 5 stars</span>
              )}
            </div>
          </div>

          {/* Submit buttons */}
          <div className="feedback-actions">
            <button
              type="button"
              className="btn-skip"
              onClick={handleSkip}
              disabled={isSubmitting}
            >
              Skip
            </button>
            <button
              type="submit"
              className="btn-submit"
              disabled={isSubmitting || workedAsExpected === null || rating === 0}
            >
              {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FeedbackSurvey;
