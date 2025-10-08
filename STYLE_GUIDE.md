# BudgNudg Design System & Style Guide

## 🎨 Overview

This document outlines the design system and style guide for the BudgNudg Django application, featuring a modern glassmorphism UI with modular CSS architecture.

## 📁 Architecture

### CSS Structure
```
budgnudg/static/css/
├── base/
│   ├── variables.css      # Design tokens and CSS custom properties
│   └── typography.css     # Font hierarchy and text styles
├── components/
│   ├── layout.css         # Page layout and containers
│   ├── glassmorphism.css  # Glass effects and navigation
│   └── tables.css         # DataTables and table styling
├── pages/
│   ├── transactions.css   # Transaction-specific styles
│   ├── budgets.css        # Budget-specific styles
│   └── lists.css          # General list views
└── main.css              # Entry point with imports
```

### JavaScript Structure
```
budgnudg/static/js/
├── components/
│   ├── datatables.js      # DataTables configurations
│   └── navbar.js          # Navigation functionality
├── pages/
│   ├── budgets.js         # Budget page interactions
│   └── transactions.js    # Transaction page interactions
└── main.js               # Application initialization
```

## 🎯 Design Tokens

### Colors

#### Primary Palette
- **Brand Purple**: `#667eea` (rgba(102, 126, 234, 1))
- **Brand Purple Light**: `#764ba2` (rgba(118, 75, 162, 1))

#### Text Colors
- **Primary**: `#1f2937` - Main content text
- **Secondary**: `#374151` - Supporting text
- **Muted**: `#6b7280` - Disabled/placeholder text
- **Inverse**: `#ffffff` - Text on dark backgrounds

#### Navbar Colors
- **Text Primary**: `#374151` - Default navbar text
- **Text Hover**: `#1f2937` - Hover state
- **Text Active**: `#667eea` - Active/selected state

#### Semantic Colors
- **Success**: `#059669` - Positive amounts, success states
- **Danger**: `#dc2626` - Negative amounts, errors
- **Warning**: `#d97706` - Warnings, alerts
- **Info**: `#0284c7` - Information, neutral amounts

### Spacing Scale
- **XS**: `0.25rem` (4px)
- **SM**: `0.5rem` (8px)
- **MD**: `1rem` (16px)
- **LG**: `1.5rem` (24px)
- **XL**: `2rem` (32px)
- **2XL**: `3rem` (48px)

### Typography Scale
- **Font Family**: Inter, system fonts
- **Weights**: 
  - Normal: 400
  - Medium: 500
  - Semibold: 600
  - Bold: 700
- **Line Heights**:
  - Tight: 1.25
  - Body: 1.5
  - Loose: 1.75

### Border Radius
- **SM**: `0.375rem` (6px)
- **MD**: `0.5rem` (8px)
- **LG**: `0.75rem` (12px)
- **XL**: `1rem` (16px)

### Shadows
- **Soft**: `0 4px 15px rgba(0, 0, 0, 0.05)`
- **Medium**: `0 8px 25px rgba(0, 0, 0, 0.1)`
- **Strong**: `0 20px 50px rgba(0, 0, 0, 0.15)`

### Glass Effects
- **Subtle**: `blur(10px)`
- **Medium**: `blur(20px)`
- **Heavy**: `blur(16px)`
- **Strong**: `blur(25px)`

## 🧩 Components

### Glassmorphism Cards
```css
.glass-card {
  background: linear-gradient(145deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(248, 250, 252, 0.9) 100%);
  backdrop-filter: var(--blur-medium);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: var(--shadow-soft);
}
```

### Navigation States
- **Initial**: Nearly transparent (`rgba(255, 255, 255, 0.05)`)
- **Scrolled**: Solid glassmorphism with enhanced blur and shadows

### Interactive Elements
- **Hover**: Subtle gradient background + transform
- **Focus**: Enhanced visibility with proper accessibility
- **Active**: Pressed state with reduced transform

## 📊 DataTables Styling

### Configuration
- **Modern Headers**: Gradient backgrounds with brand colors
- **Row Hovers**: Glassmorphism-style hover effects
- **Pagination**: Custom styled with brand colors
- **Responsive**: Mobile-first responsive design

### Currency Display
- **Positive**: Green (`#059669`)
- **Negative**: Red (`#dc2626`) 
- **Warning**: Orange (`#d97706`)
- **Info**: Blue (`#0284c7`)

## 🎭 Animations

### Transitions
- **Fast**: `0.15s ease-in-out`
- **Normal**: `0.3s ease-in-out`
- **Slow**: `0.5s ease-in-out`

### Transform Effects
- **Hover Lift**: `translateY(-2px)`
- **Row Slide**: `translateX(4px)`
- **Button Press**: `scale(0.98)`

## 📱 Responsive Design

### Breakpoints
- **Mobile**: `< 768px`
- **Tablet**: `768px - 1024px` 
- **Desktop**: `> 1024px`

### Mobile Adaptations
- Reduced padding/margins
- Stacked layouts
- Touch-friendly sizing
- Simplified interactions

## 🔧 Usage Guidelines

### CSS Custom Properties
All design tokens are available as CSS custom properties:
```css
color: var(--color-text-primary);
padding: var(--space-lg);
border-radius: var(--radius-md);
```

### JavaScript Modules
Components are modular and self-contained:
```javascript
// Initialize specific components
BudgNudgNavbar.init();
BudgNudgDataTables.initAll();
```

### Page-Specific Styling
Add page identifiers to body class:
```html
<body class="budget-page">
<body class="transaction-page">
```

## 🎨 Best Practices

### Performance
- Use CSS transforms for animations (GPU accelerated)
- Throttle scroll events (10ms intervals)
- Leverage CSS custom properties for consistency

### Accessibility
- WCAG compliant color contrast ratios
- Focus states for keyboard navigation
- Semantic HTML structure
- Screen reader friendly labels

### Maintainability
- Modular CSS architecture
- Consistent naming conventions
- Documented design tokens
- Component-based JavaScript

## 🚀 Implementation

### Adding New Pages
1. Create page-specific CSS in `pages/`
2. Import in `main.css`
3. Add JavaScript module in `pages/`
4. Initialize in `main.js`

### Extending Components
1. Follow existing patterns in `components/`
2. Use design tokens from `variables.css`
3. Maintain glassmorphism aesthetic
4. Test across all breakpoints

## 🔄 Future Enhancements

- CSS/JS minification pipeline
- Component documentation
- Interactive style guide
- Design system automation
- Performance optimization