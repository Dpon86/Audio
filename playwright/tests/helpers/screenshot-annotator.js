const fs = require('fs');
const path = require('path');

/**
 * Enhanced screenshot capturer with visual annotations
 * Adds red circles, arrows, and highlights to specific UI elements
 */

const screenshotDir = path.join(__dirname, '..', '..', 'user-manual-screenshots');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

/**
 * Add visual annotation overlay to highlight an element
 * @param {Page} page - Playwright page object
 * @param {string} selector - CSS selector for element to highlight
 * @param {object} options - Annotation options
 */
async function addAnnotation(page, selector, options = {}) {
  const {
    type = 'box', // 'box', 'circle', 'arrow'
    color = '#ef4444', // Red
    thickness = 4,
    pulse = true,
    arrow = null, // { from: 'top'|'bottom'|'left'|'right', length: 50 }
  } = options;

  await page.evaluate(({ selector, type, color, thickness, pulse, arrow }) => {
    const el = document.querySelector(selector);
    if (!el) {
      console.warn(`Annotation: Element not found for selector: ${selector}`);
      return;
    }

    const rect = el.getBoundingClientRect();
    const padding = 8;
    
    // Create container for all annotation elements
    const container = document.createElement('div');
    container.className = 'playwright-annotation-container';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 999999;
    `;

    if (type === 'box' || type === 'circle') {
      const highlight = document.createElement('div');
      const isCircle = type === 'circle';
      
      highlight.style.cssText = `
        position: absolute;
        left: ${rect.left - padding}px;
        top: ${rect.top - padding}px;
        width: ${rect.width + padding * 2}px;
        height: ${rect.height + padding * 2}px;
        border: ${thickness}px solid ${color};
        border-radius: ${isCircle ? '50%' : '8px'};
        box-shadow: 
          0 0 0 ${thickness}px rgba(239, 68, 68, 0.1),
          0 0 20px rgba(239, 68, 68, 0.3),
          inset 0 0 20px rgba(239, 68, 68, 0.1);
        ${pulse ? 'animation: pulse-annotation 2s ease-in-out infinite;' : ''}
      `;
      container.appendChild(highlight);
    }

    // Add arrow if specified
    if (arrow) {
      const arrowEl = document.createElement('div');
      const arrowLength = arrow.length || 50;
      let arrowStyle = `
        position: absolute;
        border: ${thickness}px solid ${color};
        filter: drop-shadow(0 2px 8px rgba(239, 68, 68, 0.4));
      `;

      switch(arrow.from) {
        case 'top':
          arrowStyle += `
            left: ${rect.left + rect.width / 2 - thickness}px;
            top: ${rect.top - arrowLength - padding * 2}px;
            height: ${arrowLength}px;
            width: 0;
            border-left: ${thickness * 2}px solid transparent;
            border-right: ${thickness * 2}px solid transparent;
            border-top: ${thickness * 3}px solid ${color};
          `;
          break;
        case 'bottom':
          arrowStyle += `
            left: ${rect.left + rect.width / 2 - thickness}px;
            top: ${rect.bottom + padding * 2}px;
            height: ${arrowLength}px;
            width: 0;
            border-left: ${thickness * 2}px solid transparent;
            border-right: ${thickness * 2}px solid transparent;
            border-bottom: ${thickness * 3}px solid ${color};
          `;
          break;
        case 'left':
          arrowStyle += `
            left: ${rect.left - arrowLength - padding * 2}px;
            top: ${rect.top + rect.height / 2 - thickness}px;
            width: ${arrowLength}px;
            height: 0;
            border-top: ${thickness * 2}px solid transparent;
            border-bottom: ${thickness * 2}px solid transparent;
            border-left: ${thickness * 3}px solid ${color};
          `;
          break;
        case 'right':
          arrowStyle += `
            left: ${rect.right + padding * 2}px;
            top: ${rect.top + rect.height / 2 - thickness}px;
            width: ${arrowLength}px;
            height: 0;
            border-top: ${thickness * 2}px solid transparent;
            border-bottom: ${thickness * 2}px solid transparent;
            border-right: ${thickness * 3}px solid ${color};
          `;
          break;
      }
      arrowEl.style.cssText = arrowStyle;
      container.appendChild(arrowEl);
    }

    // Add pulse animation styles
    if (pulse && !document.getElementById('annotation-pulse-styles')) {
      const style = document.createElement('style');
      style.id = 'annotation-pulse-styles';
      style.textContent = `
        @keyframes pulse-annotation {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.7; transform: scale(1.02); }
        }
      `;
      document.head.appendChild(style);
    }

    document.body.appendChild(container);

    // Store reference for cleanup
    if (!window.__annotationContainers) {
      window.__annotationContainers = [];
    }
    window.__annotationContainers.push(container);
  }, { selector, type, color, thickness, pulse, arrow });
}

/**
 * Remove all annotations from the page
 */
async function clearAnnotations(page) {
  await page.evaluate(() => {
    if (window.__annotationContainers) {
      window.__annotationContainers.forEach(container => {
        if (container.parentNode) {
          container.parentNode.removeChild(container);
        }
      });
      window.__annotationContainers = [];
    }
  });
}

/**
 * Capture screenshot with optional annotations
 * @param {Page} page - Playwright page object
 * @param {number} stepNumber - Step number for filename
 * @param {string} stepName - Step name/description
 * @param {object} annotationConfig - Optional annotation configuration
 */
async function captureStepWithAnnotation(page, stepNumber, stepName, annotationConfig = null) {
  // Add annotation if specified
  if (annotationConfig) {
    await addAnnotation(page, annotationConfig.selector, annotationConfig.options);
    // Wait a moment for animation to render
    await page.waitForTimeout(300);
  }

  // Take screenshot
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `step-${stepNumber.toString().padStart(2, '0')}-${stepName}-${timestamp}.png`;
  const filepath = path.join(screenshotDir, filename);
  await page.screenshot({ path: filepath, fullPage: true });
  console.log(`📸 Screenshot saved: ${filename}${annotationConfig ? ' (with annotation)' : ''}`);

  // Clean up annotations
  if (annotationConfig) {
    await clearAnnotations(page);
  }

  return filepath;
}

/**
 * Standard captureStep without annotations (for backward compatibility)
 */
async function captureStep(page, stepNumber, stepName) {
  return captureStepWithAnnotation(page, stepNumber, stepName, null);
}

module.exports = {
  captureStep,
  captureStepWithAnnotation,
  addAnnotation,
  clearAnnotations,
};
