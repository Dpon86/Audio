import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getApiUrl } from '../../config/api';
import './Pricing.css';

const PricingPage = ({ user, subscription }) => {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [billingCycle, setBillingCycle] = useState('monthly');
    const [checkoutLoading, setCheckoutLoading] = useState(null);
    const navigate = useNavigate();

    useEffect(() => {
        fetchPlans();
    }, []);

    const fetchPlans = async () => {
        try {
            const response = await fetch(getApiUrl('/api/auth/plans/'));
            const data = await response.json();
            setPlans(data);
        } catch (error) {
            console.error('Error fetching plans:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSubscribe = async (planId) => {
        if (!user) {
            navigate('/register');
            return;
        }

        setCheckoutLoading(planId);
        
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/api/auth/checkout/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Token ${token}`,
                },
                body: JSON.stringify({
                    plan_id: planId,
                    billing_cycle: billingCycle,
                }),
            });

            const data = await response.json();

            if (response.ok) {
                // Redirect to Stripe Checkout
                window.location.href = data.checkout_url;
            } else {
                alert(data.error || 'Failed to create checkout session');
            }
        } catch (error) {
            alert('Network error. Please try again.');
        } finally {
            setCheckoutLoading(null);
        }
    };

    const isCurrentPlan = (planName) => {
        return subscription?.plan?.name === planName;
    };

    const getPlanPrice = (plan) => {
        if (billingCycle === 'yearly' && plan.price_yearly) {
            return plan.price_yearly;
        }
        return plan.price_monthly;
    };

    const formatPrice = (price) => {
        return price === 0 ? 'Free' : `£${price}`;
    };

    if (loading) {
        return (
            <div className="pricing-container">
                <div className="loading">Loading pricing plans...</div>
            </div>
        );
    }

    return (
        <div className="pricing-container">
            <div className="pricing-hero">
                <h1>Choose Your Plan</h1>
                <p>Start with our free trial, then pick the plan that works best for you.</p>
                
                <div className="billing-toggle">
                    <label className={billingCycle === 'monthly' ? 'active' : ''}>
                        <input
                            type="radio"
                            value="monthly"
                            checked={billingCycle === 'monthly'}
                            onChange={() => setBillingCycle('monthly')}
                        />
                        Monthly
                    </label>
                    <label className={billingCycle === 'yearly' ? 'active' : ''}>
                        <input
                            type="radio"
                            value="yearly"
                            checked={billingCycle === 'yearly'}
                            onChange={() => setBillingCycle('yearly')}
                        />
                        Yearly <span className="savings">Save 17%</span>
                    </label>
                </div>
            </div>

            <div className="pricing-grid">
                {plans.map((plan) => {
                    const price = getPlanPrice(plan);
                    const isCurrent = isCurrentPlan(plan.name);
                    const isPopular = plan.name === 'enterprise'; // Annual unlimited is best value
                    
                    return (
                        <div 
                            key={plan.id} 
                            className={`pricing-card ${isPopular ? 'popular' : ''} ${isCurrent ? 'current' : ''}`}
                        >
                            {isPopular && <div className="popular-badge">Most Popular</div>}
                            {isCurrent && <div className="current-badge">Current Plan</div>}
                            
                            <div className="plan-header">
                                <h3>{plan.display_name}</h3>
                                <div className="price">
                                    <span className="amount">{formatPrice(price)}</span>
                                    {price > 0 && (
                                        <span className="period">
                                            /{billingCycle === 'yearly' ? 'year' : 'month'}
                                        </span>
                                    )}
                                </div>
                                {billingCycle === 'yearly' && price > 0 && plan.price_monthly && plan.name !== 'enterprise' && (
                                    <div className="monthly-equivalent">
                                        £{(price / 12).toFixed(2)}/month billed annually
                                    </div>
                                )}
                                {plan.name === 'enterprise' && (
                                    <div className="annual-only">
                                        Annual billing only
                                    </div>
                                )}
                                <p className="description">{plan.description}</p>
                            </div>

                            <div className="plan-features">
                                <ul>
                                    {plan.features.map((feature, index) => (
                                        <li key={index}>{feature}</li>
                                    ))}
                                </ul>
                            </div>

                            <div className="plan-action">
                                {plan.name === 'free' ? (
                                    user ? (
                                        isCurrent ? (
                                            <button className="plan-button current" disabled>
                                                Current Plan
                                            </button>
                                        ) : (
                                            <button 
                                                className="plan-button"
                                                onClick={() => handleSubscribe(plan.id)}
                                                disabled={checkoutLoading === plan.id}
                                            >
                                                {checkoutLoading === plan.id ? 'Processing...' : 'Downgrade'}
                                            </button>
                                        )
                                    ) : (
                                        <Link to="/register" className="plan-button primary">
                                            Start Free Trial
                                        </Link>
                                    )
                                ) : (
                                    isCurrent ? (
                                        <button className="plan-button current" disabled>
                                            Current Plan
                                        </button>
                                    ) : (
                                        <button 
                                            className={`plan-button ${isPopular ? 'primary' : ''}`}
                                            onClick={() => handleSubscribe(plan.id)}
                                            disabled={checkoutLoading === plan.id}
                                        >
                                            {checkoutLoading === plan.id ? 'Processing...' : 
                                             user ? 'Upgrade Now' : 'Get Started'}
                                        </button>
                                    )
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="pricing-faq">
                <h2>Frequently Asked Questions</h2>
                
                <div className="faq-grid">
                    <div className="faq-item">
                        <h4>Can I change plans anytime?</h4>
                        <p>Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately, and billing is prorated.</p>
                    </div>
                    
                    <div className="faq-item">
                        <h4>What happens during my free trial?</h4>
                        <p>Your 7-day free trial includes up to 60 minutes of audio processing. No credit card required to start.</p>
                    </div>
                    
                    <div className="faq-item">
                        <h4>How does the usage system work?</h4>
                        <p>Each "use" means processing one complete project (PDF + audio file). Basic plan gets 1 use per month, Professional gets 10 uses, and Annual Unlimited has no limits.</p>
                    </div>
                    
                    <div className="faq-item">
                        <h4>Is my data secure?</h4>
                        <p>Yes, all files are encrypted and stored securely. We never share your content with third parties.</p>
                    </div>
                </div>
            </div>

            {!user && (
                <div className="cta-section">
                    <h2>Ready to get started?</h2>
                    <p>Join thousands of creators who trust Audio Duplicate Detection</p>
                    <Link to="/register" className="cta-button">
                        Start Your Free Trial Today
                    </Link>
                </div>
            )}
        </div>
    );
};

export default PricingPage;