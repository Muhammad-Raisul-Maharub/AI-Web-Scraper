---
name: web-animation-scraper
description: Comprehensive workflow and cheatsheet for scraping animations (CSS keyframes, Lottie, Rive, SVGs, background video loops) and bypassing bot/locale interstitials across modern web applications.
---

# Web Animation & Motion Asset Scraper Skill

This skill provides production-tested patterns for extracting web animations, motion assets, and styles from modern SPAs and enterprise web applications.

## 1. Dynamic CSSOM Animation Extraction (Selenium / Playwright)
When pages use external CDN stylesheets, CSS-in-JS, or dynamically injected stylesheets, simple HTML regex on `<style>` tags misses critical `@keyframes`. Use this in-browser execution script:

```javascript
const keyframes = [];
for (let i = 0; i < document.styleSheets.length; i++) {
  try {
    const sheet = document.styleSheets[i];
    const rules = sheet.cssRules || sheet.rules;
    if (!rules) continue;
    for (let j = 0; j < rules.length; j++) {
      const rule = rules[j];
      if (rule.type === CSSRule.KEYFRAMES_RULE || rule.type === 7) {
        keyframes.push({
          name: rule.name,
          css: rule.cssText.slice(0, 400)
        });
      }
    }
  } catch (e) {
    // Gracefully handle cross-origin SecurityError from external CDNs
    continue;
  }
}
return keyframes;
```

## 2. Motion Media & Video Loop Detection
High-end apparel and luxury brands favor video loops over Lottie:
- Inspect `<video autoplay loop muted>` elements.
- Inspect both `src` attributes and child `<source src="...">` elements.
- Capture common web motion formats: `.mp4`, `.webm`, `.gif`, `.apng`.

## 3. Handling Bot & Locale Interstitials
Enterprise e-commerce sites (e.g., Uniqlo, H&M, Levi's, Lululemon) often show location/consent gates to headless browsers:
- Inject pre-warmed cookies (e.g. `country=US; currency=USD; locale=en_US`).
- Mask `navigator.webdriver` via Chrome flags (`--disable-blink-features=AutomationControlled`).
- Use realistic viewport dimensions (`1920x1080`) with natural scroll events before capturing screenshots.
