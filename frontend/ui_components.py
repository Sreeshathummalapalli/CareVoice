# CareVoice UI Component Helper Functions
# Provides reusable UI components for consistent design across the application

import streamlit as st
from typing import Optional, Dict, Any


def render_card(content: str, **kwargs) -> None:
    """
    Render a standard white card with subtle shadow and border.
    
    Args:
        content: HTML content to display inside the card
        **kwargs: Optional styling parameters
            - padding: Card padding (default: "24px")
            - margin_bottom: Bottom margin (default: "16px")
            - border_radius: Corner radius (default: "14px")
            - extra_styles: Additional CSS styles as string
    
    Validates: Requirements 18.1, 18.2, 18.3, 19.1, 19.5
    """
    padding = kwargs.get('padding', '24px')
    margin_bottom = kwargs.get('margin_bottom', '16px')
    border_radius = kwargs.get('border_radius', '14px')
    extra_styles = kwargs.get('extra_styles', '')
    
    card_html = f"""
        <div style='
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: {border_radius};
            padding: {padding};
            margin-bottom: {margin_bottom};
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
            transition: box-shadow 0.2s ease;
            {extra_styles}
        '>
            {content}
        </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_sage_card(content: str, **kwargs) -> None:
    """
    Render a highlighted card with sage green background for emphasized content.
    
    Args:
        content: HTML content to display inside the card
        **kwargs: Optional styling parameters
            - padding: Card padding (default: "24px")
            - margin_bottom: Bottom margin (default: "16px")
            - border_radius: Corner radius (default: "14px")
            - extra_styles: Additional CSS styles as string
    
    Validates: Requirements 18.4, 18.5, 19.2, 19.3
    """
    padding = kwargs.get('padding', '24px')
    margin_bottom = kwargs.get('margin_bottom', '16px')
    border_radius = kwargs.get('border_radius', '14px')
    extra_styles = kwargs.get('extra_styles', '')
    
    card_html = f"""
        <div style='
            background: #F0FDF4;
            border: 1px solid #BBF7D0;
            border-radius: {border_radius};
            padding: {padding};
            margin-bottom: {margin_bottom};
            {extra_styles}
        '>
            {content}
        </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_status_badge(status: str, custom_text: Optional[str] = None) -> str:
    """
    Render a status badge/pill for medicine or health status display.
    
    Args:
        status: Status type - "taken", "pending", "skipped", "normal", "high", "low", "optimal", "critical"
        custom_text: Optional custom text to display (defaults to status capitalized)
    
    Returns:
        HTML string for the status badge
    
    Validates: Requirements 18.6, 18.7, 19.4, 19.6
    """
    display_text = custom_text if custom_text else status.capitalize()
    
    # Define status styles
    status_styles = {
        'taken': {
            'bg': '#DCFCE7',
            'color': '#166534',
            'text': 'Taken'
        },
        'pending': {
            'bg': '#FEF3C7',
            'color': '#92400E',
            'text': 'Pending'
        },
        'skipped': {
            'bg': '#FEE2E2',
            'color': '#991B1B',
            'text': 'Skipped'
        },
        'normal': {
            'bg': '#DBEAFE',
            'color': '#1E40AF',
            'text': 'Normal'
        },
        'optimal': {
            'bg': '#DCFCE7',
            'color': '#166534',
            'text': 'Optimal'
        },
        'high': {
            'bg': '#FEE2E2',
            'color': '#991B1B',
            'text': 'High'
        },
        'low': {
            'bg': '#FEF3C7',
            'color': '#92400E',
            'text': 'Low'
        },
        'critical': {
            'bg': '#FEE2E2',
            'color': '#7F1D1D',
            'text': 'Critical'
        }
    }
    
    style = status_styles.get(status.lower(), {
        'bg': '#F1F5F9',
        'color': '#475569',
        'text': display_text
    })
    
    if custom_text:
        style['text'] = custom_text
    
    badge_html = f"""
        <span style='
            background: {style["bg"]};
            color: {style["color"]};
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            display: inline-block;
        '>
            {style["text"]}
        </span>
    """
    return badge_html


def render_empty_state(icon: str, title: str, message: str, action_button: Optional[Dict[str, str]] = None) -> None:
    """
    Render an empty state component for no-data scenarios.
    
    Args:
        icon: Unicode emoji or icon character
        title: Heading text for the empty state
        message: Descriptive message explaining the empty state
        action_button: Optional dict with 'text' and 'key' for a call-to-action button
    
    Validates: Requirements 18.1, 18.2, 18.3, 19.7, 19.8
    """
    button_html = ""
    if action_button:
        button_html = f"""
            <div style='margin-top: 20px;'>
                <button style='
                    background: #166534;
                    color: #FFFFFF;
                    padding: 12px 24px;
                    border-radius: 10px;
                    font-weight: 600;
                    font-size: 15px;
                    border: 1px solid #166534;
                    cursor: pointer;
                    transition: all 0.2s ease;
                '>
                    {action_button.get('text', 'Get Started')}
                </button>
            </div>
        """
    
    empty_state_html = f"""
        <div style='
            text-align: center;
            padding: 48px 24px;
            color: #64748B;
        '>
            <div style='font-size: 48px; margin-bottom: 16px;'>{icon}</div>
            <h3 style='
                color: #0F172A;
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 8px;
            '>{title}</h3>
            <p style='
                color: #64748B;
                font-size: 15px;
                line-height: 1.6;
                margin: 0;
            '>{message}</p>
            {button_html}
        </div>
    """
    st.markdown(empty_state_html, unsafe_allow_html=True)


def render_icon(icon: str, **kwargs) -> str:
    """
    Render a consistent icon with specified size and color.
    
    Args:
        icon: Unicode emoji or icon character
        **kwargs: Optional styling parameters
            - size: Font size (default: "20px")
            - color: Icon color (default: "#64748B")
            - margin_right: Right margin (default: "8px")
    
    Returns:
        HTML string for the icon
    
    Validates: Requirements 19.5, 19.6, 20.1
    """
    size = kwargs.get('size', '20px')
    color = kwargs.get('color', '#64748B')
    margin_right = kwargs.get('margin_right', '8px')
    
    icon_html = f"""
        <span style='
            font-size: {size};
            color: {color};
            margin-right: {margin_right};
            display: inline-block;
            vertical-align: middle;
        '>
            {icon}
        </span>
    """
    return icon_html


def render_section_header(title: str, icon: Optional[str] = None, subtitle: Optional[str] = None, **kwargs) -> None:
    """
    Render a consistent section header with optional icon and subtitle.
    
    Args:
        title: Header title text
        icon: Optional icon character/emoji
        subtitle: Optional subtitle/description text
        **kwargs: Optional styling parameters
            - margin_bottom: Bottom margin (default: "24px")
            - title_size: Title font size (default: "28px")
    
    Validates: Requirements 19.1, 19.3, 20.2
    """
    margin_bottom = kwargs.get('margin_bottom', '24px')
    title_size = kwargs.get('title_size', '28px')
    
    icon_html = ""
    if icon:
        icon_html = render_icon(icon, size="32px", color="#166534", margin_right="12px")
    
    subtitle_html = ""
    if subtitle:
        subtitle_html = f"""
            <p style='
                color: #64748B;
                font-size: 15px;
                line-height: 1.6;
                margin: 4px 0 0 0;
            '>{subtitle}</p>
        """
    
    header_html = f"""
        <div style='margin-bottom: {margin_bottom};'>
            <div style='display: flex; align-items: center;'>
                {icon_html}
                <h2 style='
                    color: #0F172A;
                    font-size: {title_size};
                    font-weight: 700;
                    margin: 0;
                    letter-spacing: -0.01em;
                '>{title}</h2>
            </div>
            {subtitle_html}
        </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_loading_spinner(message: str = "Loading...", **kwargs) -> None:
    """
    Render a loading spinner for async operations.
    
    Args:
        message: Loading message text
        **kwargs: Optional styling parameters
            - size: Spinner size (default: "medium")
            - center: Center align spinner (default: True)
    
    Validates: Requirements 20.3, 20.4
    """
    center = kwargs.get('center', True)
    
    # Use Streamlit's native spinner for consistency
    if center:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.spinner(message):
                pass
    else:
        with st.spinner(message):
            pass


def render_error_message(error_type: str, message: str, details: Optional[str] = None, **kwargs) -> None:
    """
    Render a consistent error message component.
    
    Args:
        error_type: Type of error - "error", "warning", "info"
        message: Main error message
        details: Optional detailed error information
        **kwargs: Optional styling parameters
            - dismissible: Show dismiss button (default: False)
            - icon: Custom icon (default: based on error_type)
    
    Validates: Requirements 20.1, 20.2, 20.5, 20.6, 20.7
    """
    icon = kwargs.get('icon', None)
    
    # Define error type styles and default icons
    error_styles = {
        'error': {
            'bg': '#FEE2E2',
            'border': '#FCA5A5',
            'color': '#991B1B',
            'icon': icon or '❌'
        },
        'warning': {
            'bg': '#FEF3C7',
            'border': '#FDE68A',
            'color': '#92400E',
            'icon': icon or '⚠️'
        },
        'info': {
            'bg': '#DBEAFE',
            'border': '#BFDBFE',
            'color': '#1E40AF',
            'icon': icon or 'ℹ️'
        },
        'success': {
            'bg': '#DCFCE7',
            'border': '#BBF7D0',
            'color': '#166534',
            'icon': icon or '✅'
        }
    }
    
    style = error_styles.get(error_type.lower(), error_styles['info'])
    
    details_html = ""
    if details:
        details_html = f"""
            <div style='
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid {style["border"]};
                font-size: 13px;
                color: {style["color"]};
                opacity: 0.8;
            '>
                {details}
            </div>
        """
    
    error_html = f"""
        <div style='
            background: {style["bg"]};
            border: 1px solid {style["border"]};
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: flex-start;
        '>
            <div style='
                font-size: 20px;
                margin-right: 12px;
                flex-shrink: 0;
            '>
                {style["icon"]}
            </div>
            <div style='flex: 1;'>
                <div style='
                    color: {style["color"]};
                    font-size: 15px;
                    font-weight: 600;
                    line-height: 1.5;
                '>
                    {message}
                </div>
                {details_html}
            </div>
        </div>
    """
    st.markdown(error_html, unsafe_allow_html=True)


# Additional utility functions for common UI patterns

def render_metric_card(label: str, value: str, unit: str = "", status: Optional[str] = None, icon: Optional[str] = None) -> None:
    """
    Render a metric card for health data display.
    
    Args:
        label: Metric label/name
        value: Metric value
        unit: Unit of measurement
        status: Optional status badge ("normal", "high", "low", etc.)
        icon: Optional icon character
    
    Validates: Requirements 19.1, 19.4, 19.6
    """
    icon_html = ""
    if icon:
        icon_html = f"<div style='font-size: 32px; margin-bottom: 8px;'>{icon}</div>"
    
    status_html = ""
    if status:
        status_html = render_status_badge(status)
    
    content = f"""
        <div style='text-align: center;'>
            {icon_html}
            <div style='
                font-size: 14px;
                color: #64748B;
                margin-bottom: 4px;
                font-weight: 500;
            '>{label}</div>
            <div style='
                font-size: 32px;
                color: #0F172A;
                font-weight: 700;
                margin-bottom: 4px;
                line-height: 1;
            '>
                {value}<span style='font-size: 18px; color: #64748B; margin-left: 4px;'>{unit}</span>
            </div>
            {status_html}
        </div>
    """
    render_card(content, padding="20px")


def render_medicine_timeline_item(medicine: Dict[str, Any], show_actions: bool = True) -> None:
    """
    Render a medicine item in timeline format.
    
    Args:
        medicine: Dictionary containing medicine data (name, dosage, time_slot, status, etc.)
        show_actions: Whether to show action buttons
    
    Validates: Requirements 18.6, 19.4, 19.7
    """
    status = medicine.get('status', 'pending').lower()
    status_badge = render_status_badge(status)
    
    time_slot = medicine.get('time_slot', 'Not scheduled')
    name = medicine.get('name', 'Unknown Medicine')
    dosage = medicine.get('dosage', '')
    instructions = medicine.get('instructions', '')
    
    actions_html = ""
    if show_actions and status == 'pending':
        actions_html = """
            <div style='margin-top: 12px; display: flex; gap: 8px;'>
                <button style='
                    background: #166534;
                    color: #FFFFFF;
                    padding: 8px 16px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 13px;
                    border: none;
                    cursor: pointer;
                '>Mark Taken</button>
                <button style='
                    background: #F8FAFC;
                    color: #0F172A;
                    padding: 8px 16px;
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 13px;
                    border: 1px solid #E2E8F0;
                    cursor: pointer;
                '>Skip</button>
            </div>
        """
    
    content = f"""
        <div style='display: flex; align-items: flex-start; gap: 16px;'>
            <div style='
                background: #F0FDF4;
                border: 2px solid #BBF7D0;
                border-radius: 10px;
                width: 48px;
                height: 48px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                flex-shrink: 0;
            '>💊</div>
            <div style='flex: 1;'>
                <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;'>
                    <div>
                        <div style='
                            font-size: 17px;
                            font-weight: 600;
                            color: #0F172A;
                            margin-bottom: 2px;
                        '>{name}</div>
                        <div style='
                            font-size: 14px;
                            color: #64748B;
                        '>{dosage}</div>
                    </div>
                    {status_badge}
                </div>
                <div style='
                    font-size: 13px;
                    color: #166534;
                    font-weight: 600;
                    margin-bottom: 4px;
                '>⏰ {time_slot}</div>
                <div style='
                    font-size: 14px;
                    color: #64748B;
                    line-height: 1.5;
                '>{instructions}</div>
                {actions_html}
            </div>
        </div>
    """
    render_card(content)
