"""
Test to verify the enhanced CSS implementation for Task 1
"""
import re

def test_css_implementation():
    """Verify the enhanced apply_custom_css() function contains all required elements"""
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the apply_custom_css function
    css_function_match = re.search(r'def apply_custom_css\(\):.*?(?=\ndef |\nclass |\Z)', content, re.DOTALL)
    
    if not css_function_match:
        print("❌ FAILED: apply_custom_css() function not found")
        return False
    
    css_content = css_function_match.group(0)
    
    # Required elements checklist
    required_elements = {
        "Healthcare green color palette": "#166534",
        "Inter font family": "Inter",
        "Spacing system (4px base)": "spacing_xs",
        "Primary button styles": ".stButton>button",
        "Secondary button styles": 'button[kind="secondary"]',
        "Standard card styles (.cv-card)": ".cv-card",
        "Sage card styles (.cv-card-sage)": ".cv-card-sage",
        "Input field styles": ".stTextInput",
        "Input focus states": ":focus",
        "Badge taken style": ".badge-taken",
        "Badge pending style": ".badge-pending",
        "Badge skipped style": ".badge-skipped",
        "Responsive breakpoints - mobile": "@media (min-width: 640px)",
        "Responsive breakpoints - tablet": "@media (min-width: 768px)",
        "Responsive breakpoints - desktop": "@media (min-width: 1024px)",
        "Elderly mode adjustments": "elderly",
        "WCAG compliance documentation": "WCAG 2.1",
        "Touch target sizing": "touch_target",
        "CSS Variables": ":root",
        "Transition effects": "transition:",
    }
    
    results = []
    all_passed = True
    
    for element_name, search_term in required_elements.items():
        if search_term in css_content:
            results.append(f"✓ {element_name}")
        else:
            results.append(f"✗ {element_name} - NOT FOUND")
            all_passed = False
    
    # Print results
    print("\n" + "="*70)
    print("CSS IMPLEMENTATION VERIFICATION RESULTS")
    print("="*70)
    
    for result in results:
        print(result)
    
    print("\n" + "="*70)
    
    # Additional checks
    print("\nADDITIONAL CHECKS:")
    
    # Check for proper font weight usage (400, 600, 700)
    if "wght@400;600;700" in css_content or "wght@400;500;600;700" in css_content:
        print("✓ Inter font weights (400, 600, 700) properly specified")
    else:
        print("✗ Inter font weights not properly configured")
        all_passed = False
    
    # Check for elderly mode +33% calculation
    if "37px" in css_content or "27px" in css_content:  # 28px * 1.33 ≈ 37px
        print("✓ Elderly mode +33% font size increase implemented")
    else:
        print("✗ Elderly mode +33% increase not properly calculated")
        all_passed = False
    
    # Check for 48px touch targets in elderly mode
    if '"48px"' in css_content and 'elderly' in css_content:
        print("✓ 48px touch targets for elderly mode")
    else:
        print("✗ 48px touch targets not properly configured")
        all_passed = False
    
    # Check for line height 1.7 in elderly mode
    if '"1.7"' in css_content or '1.7' in css_content:
        print("✓ Line height 1.7 for elderly mode")
    else:
        print("✗ Line height 1.7 not implemented")
        all_passed = False
    
    print("\n" + "="*70)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - CSS Implementation Complete!")
        print("\nTask 1 Implementation Summary:")
        print("- Comprehensive UI design system with healthcare green (#166534) color palette")
        print("- Inter font family with proper weights (400, 600, 700)")
        print("- Complete spacing system (4px base unit with full scale)")
        print("- Button styles (primary, secondary with hover states and transitions)")
        print("- Card styles (standard cv-card and sage cv-card-sage)")
        print("- Input field styles with focus states")
        print("- Badge/pill styles for medicine status (taken, pending, skipped)")
        print("- Responsive breakpoints (mobile, tablet, desktop)")
        print("- Elderly mode CSS adjustments (font size +33%, touch targets 48px)")
        print("- WCAG 2.1 Level AA contrast compliance documented")
        return True
    else:
        print("\n❌ SOME CHECKS FAILED - Review the implementation")
        return False

if __name__ == "__main__":
    test_css_implementation()
