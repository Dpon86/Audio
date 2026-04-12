import React, { useState } from 'react';
import './PricingPlans.css';

const PricingPlans = () => {
  const [billingPeriod, setBillingPeriod] = useState('monthly');

  const plans = [
    {
      id: 'free-trial',
      icon: '🆓',
      name: 'Free Trial',
      price: { monthly: 0, yearly: 0 },
      period: '7 days',
      description: 'Perfect for testing the platform',
      features: [
        'Upload & manage audio files',
        'Manual transcription tools',
        'Algorithm duplicate detection',
        'PDF assembly & export',
        { text: '1 FREE AI use (test any feature)', highlight: true }
      ],
      limits: [
        '60 minutes audio',
        '3 projects max',
        '0.5 GB storage',
        '50 MB max file size'
      ],
      aiFeatures: [
        { name: 'AI Duplicate Detection', enabled: '1 test' },
        { name: 'AI Transcription', enabled: '1 test' },
        { name: 'AI PDF Comparison', enabled: '1 test' }
      ],
      button: { text: 'Start Free Trial', style: 'secondary' },
      popular: false
    },
    {
      id: 'starter',
      icon: '🎯',
      name: 'Starter',
      price: { monthly: 4.99, yearly: 4.08 },
      period: 'per month',
      description: 'For manual workflows',
      features: [
        'All Free Trial features',
        'Unlimited manual transcription',
        'Algorithm duplicate detection',
        'PDF assembly & export',
        'Email support'
      ],
      limits: [
        '300 minutes audio/month',
        '10 projects',
        '2 GB storage',
        '100 MB max file size'
      ],
      aiFeatures: [
        { name: 'AI Duplicate Detection', enabled: false },
        { name: 'AI Transcription', enabled: false },
        { name: 'AI PDF Comparison', enabled: false }
      ],
      button: { text: 'Get Started', style: 'secondary' },
      popular: false
    },
    {
      id: 'basic',
      icon: '⭐',
      name: 'Basic',
      price: { monthly: 9.99, yearly: 8.25 },
      period: 'per month',
      description: 'AI-powered duplicate detection',
      features: [
        'All Starter features',
        { text: 'AI Duplicate Detection', highlight: true },
        'Sentence-level detection',
        'Paragraph expansion',
        'Confidence scores',
        'Priority email support'
      ],
      limits: [
        '500 minutes audio/month',
        '20 projects',
        '5 GB storage',
        '150 MB max file size',
        '£20 AI budget (~33 files)'
      ],
      aiFeatures: [
        { name: 'AI Duplicate Detection', enabled: true },
        { name: 'AI Transcription', enabled: false },
        { name: 'AI PDF Comparison', enabled: false }
      ],
      button: { text: 'Start Basic Plan', style: 'primary' },
      popular: true
    },
    {
      id: 'pro',
      icon: '🚀',
      name: 'Professional',
      price: { monthly: 24.99, yearly: 20.75 },
      period: 'per month',
      description: 'Full AI suite for professionals',
      features: [
        'All Basic features',
        { text: 'ALL AI Features', highlight: true },
        'AI Transcription (95% accuracy)',
        'AI PDF Comparison',
        'Speaker detection',
        'Advanced analytics',
        'API access (beta)',
        'Priority support (24h)'
      ],
      limits: [
        '2000 minutes audio/month',
        'Unlimited projects',
        '20 GB storage',
        '300 MB max file size',
        '£60 AI budget (~100 files)'
      ],
      aiFeatures: [
        { name: 'AI Duplicate Detection', enabled: true },
        { name: 'AI Transcription', enabled: true },
        { name: 'AI PDF Comparison', enabled: true }
      ],
      button: { text: 'Start Pro Plan', style: 'primary' },
      popular: false
    },
    {
      id: 'enterprise',
      icon: '💼',
      name: 'Enterprise',
      price: { monthly: 49.99, yearly: 41.58 },
      period: 'per month',
      description: 'For power users & teams',
      features: [
        'All Pro features',
        { text: 'Unlimited AI processing', highlight: true },
        'Dedicated account manager',
        'Priority processing queue',
        'Custom integrations',
        'SLA guarantees',
        'Full API access',
        'White-label options',
        'Team collaboration'
      ],
      limits: [
        'Unlimited audio minutes',
        'Unlimited projects',
        '100 GB storage',
        '500 MB max file size',
        '£200 AI budget (~330 files)'
      ],
      support: [
        '4-hour response time',
        'Phone & video support',
        'Custom onboarding'
      ],
      button: { text: 'Contact Sales', style: 'enterprise' },
      popular: false,
      enterprise: true
    }
  ];

  const handlePlanSelect = (planId) => {
    console.log('Selected plan:', planId);
    // Implement plan selection logic here
    // e.g., navigate to checkout, open modal, etc.
  };

  return (
    <div className="pricing-container">
      <div className="pricing-header">
        <h1>Choose Your Perfect Plan</h1>
        <p>AI-powered audio processing with flexible pricing for every need</p>
      </div>

      <div className="billing-toggle">
        <div className="toggle-wrapper">
          <button
            className={`toggle-btn ${billingPeriod === 'monthly' ? 'active' : ''}`}
            onClick={() => setBillingPeriod('monthly')}
          >
            Monthly
          </button>
          <button
            className={`toggle-btn ${billingPeriod === 'yearly' ? 'active' : ''}`}
            onClick={() => setBillingPeriod('yearly')}
          >
            Yearly
            <span className="save-badge">Save 17%</span>
          </button>
        </div>
      </div>

      <div className="pricing-cards">
        {plans.map(plan => (
          <div
            key={plan.id}
            className={`pricing-card ${plan.popular ? 'popular' : ''} ${plan.enterprise ? 'enterprise' : ''}`}
          >
            {plan.popular && <div className="popular-badge">⭐ MOST POPULAR</div>}
            
            <div className="card-header">
              <div className="plan-icon">{plan.icon}</div>
              <div className="plan-name">{plan.name}</div>
              <div className="plan-price">
                <span className="price-currency">£</span>
                <span className="price-amount">
                  {billingPeriod === 'monthly' ? plan.price.monthly : plan.price.yearly}
                </span>
              </div>
              <div className="price-period">{plan.period}</div>
              <div className="plan-description">{plan.description}</div>
            </div>

            <div className="card-body">
              <ul className="features-list">
                {plan.features.map((feature, index) => (
                  <li key={index} className={typeof feature === 'object' && feature.highlight ? 'highlight' : ''}>
                    {typeof feature === 'object' ? feature.text : feature}
                  </li>
                ))}
              </ul>

              {plan.limits && (
                <>
                  <div className="feature-category">Limits</div>
                  <ul className="features-list">
                    {plan.limits.map((limit, index) => (
                      <li key={index}>{limit}</li>
                    ))}
                  </ul>
                </>
              )}

              {plan.aiFeatures && (
                <>
                  <div className="feature-category">AI Features</div>
                  <ul className="features-list">
                    {plan.aiFeatures.map((ai, index) => (
                      <li
                        key={index}
                        className={!ai.enabled || ai.enabled === false ? 'disabled' : ''}
                      >
                        {ai.name}
                        {ai.enabled === true && ' ✓'}
                        {ai.enabled && ai.enabled !== true && ai.enabled !== false && ` (${ai.enabled})`}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {plan.support && (
                <>
                  <div className="feature-category">Support</div>
                  <ul className="features-list">
                    {plan.support.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            <button
              className={`cta-button ${plan.button.style}`}
              onClick={() => handlePlanSelect(plan.id)}
            >
              {plan.button.text}
            </button>
          </div>
        ))}
      </div>

      <div className="faq-section">
        <h2>❓ Frequently Asked Questions</h2>
        
        <div className="faq-item">
          <div className="faq-question">What happens after my free trial ends?</div>
          <div className="faq-answer">
            Your account remains active but you must upgrade to a paid plan to continue processing audio. 
            Your data is preserved for 30 days.
          </div>
        </div>

        <div className="faq-item">
          <div className="faq-question">Can I change plans anytime?</div>
          <div className="faq-answer">
            Yes! You can upgrade or downgrade anytime. Upgrades take effect immediately, and downgrades 
            are prorated to your next billing cycle.
          </div>
        </div>

        <div className="faq-item">
          <div className="faq-question">What counts as "1 AI use"?</div>
          <div className="faq-answer">
            Running AI duplicate detection, transcription, or PDF comparison on one audio file counts as 
            1 AI use (approximately £0.60-£1.20 depending on length).
          </div>
        </div>

        <div className="faq-item">
          <div className="faq-question">Is there a money-back guarantee?</div>
          <div className="faq-answer">
            Yes! We offer a 30-day money-back guarantee on all paid plans. No questions asked.
          </div>
        </div>
      </div>
    </div>
  );
};

export default PricingPlans;
