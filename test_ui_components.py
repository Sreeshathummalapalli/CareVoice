# Unit Tests for CareVoice UI Component Helper Functions

import pytest
import re
from ui_components import (
    render_card,
    render_sage_card,
    render_status_badge,
    render_empty_state,
    render_icon,
    render_section_header,
    render_error_message,
    render_metric_card,
    render_medicine_timeline_item
)


class TestRenderCard:
    """Test suite for render_card function"""
    
    def test_render_card_basic(self, monkeypatch):
        """Test basic card rendering with default parameters"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        # Mock streamlit.markdown
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("<p>Test content</p>")
        
        assert len(captured_html) == 1
        html = captured_html[0]
        
        # Verify key CSS properties
        assert 'background: #FFFFFF' in html
        assert 'border: 1px solid #E2E8F0' in html
        assert 'border-radius: 14px' in html
        assert 'padding: 24px' in html
        assert 'margin-bottom: 16px' in html
        assert 'box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02)' in html
        assert '<p>Test content</p>' in html
    
    def test_render_card_custom_padding(self, monkeypatch):
        """Test card with custom padding"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("<p>Content</p>", padding="32px")
        
        html = captured_html[0]
        assert 'padding: 32px' in html
    
    def test_render_card_custom_border_radius(self, monkeypatch):
        """Test card with custom border radius"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("<p>Content</p>", border_radius="20px")
        
        html = captured_html[0]
        assert 'border-radius: 20px' in html
    
    def test_render_card_extra_styles(self, monkeypatch):
        """Test card with extra custom styles"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("<p>Content</p>", extra_styles="max-width: 600px;")
        
        html = captured_html[0]
        assert 'max-width: 600px;' in html


class TestRenderSageCard:
    """Test suite for render_sage_card function"""
    
    def test_render_sage_card_basic(self, monkeypatch):
        """Test basic sage card rendering"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_sage_card("<p>Highlighted content</p>")
        
        html = captured_html[0]
        
        # Verify sage-specific styling
        assert 'background: #F0FDF4' in html
        assert 'border: 1px solid #BBF7D0' in html
        assert 'border-radius: 14px' in html
        assert '<p>Highlighted content</p>' in html
    
    def test_render_sage_card_custom_padding(self, monkeypatch):
        """Test sage card with custom padding"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_sage_card("<p>Content</p>", padding="16px")
        
        html = captured_html[0]
        assert 'padding: 16px' in html


class TestRenderStatusBadge:
    """Test suite for render_status_badge function"""
    
    def test_status_badge_taken(self):
        """Test 'taken' status badge"""
        html = render_status_badge("taken")
        
        assert 'background: #DCFCE7' in html
        assert 'color: #166534' in html
        assert 'Taken' in html
        assert 'border-radius: 20px' in html
        assert 'font-weight: 600' in html
    
    def test_status_badge_pending(self):
        """Test 'pending' status badge"""
        html = render_status_badge("pending")
        
        assert 'background: #FEF3C7' in html
        assert 'color: #92400E' in html
        assert 'Pending' in html
    
    def test_status_badge_skipped(self):
        """Test 'skipped' status badge"""
        html = render_status_badge("skipped")
        
        assert 'background: #FEE2E2' in html
        assert 'color: #991B1B' in html
        assert 'Skipped' in html
    
    def test_status_badge_normal(self):
        """Test 'normal' status badge"""
        html = render_status_badge("normal")
        
        assert 'background: #DBEAFE' in html
        assert 'color: #1E40AF' in html
        assert 'Normal' in html
    
    def test_status_badge_optimal(self):
        """Test 'optimal' status badge"""
        html = render_status_badge("optimal")
        
        assert 'background: #DCFCE7' in html
        assert 'color: #166534' in html
        assert 'Optimal' in html
    
    def test_status_badge_high(self):
        """Test 'high' status badge"""
        html = render_status_badge("high")
        
        assert 'background: #FEE2E2' in html
        assert 'color: #991B1B' in html
        assert 'High' in html
    
    def test_status_badge_low(self):
        """Test 'low' status badge"""
        html = render_status_badge("low")
        
        assert 'background: #FEF3C7' in html
        assert 'color: #92400E' in html
        assert 'Low' in html
    
    def test_status_badge_critical(self):
        """Test 'critical' status badge"""
        html = render_status_badge("critical")
        
        assert 'background: #FEE2E2' in html
        assert 'color: #7F1D1D' in html
        assert 'Critical' in html
    
    def test_status_badge_custom_text(self):
        """Test badge with custom text"""
        html = render_status_badge("taken", custom_text="Completed")
        
        assert 'Completed' in html
        assert 'Taken' not in html
    
    def test_status_badge_unknown_status(self):
        """Test badge with unknown status (should use default styling)"""
        html = render_status_badge("unknown")
        
        assert 'background: #F1F5F9' in html
        assert 'color: #475569' in html
        assert 'Unknown' in html
    
    def test_status_badge_case_insensitive(self):
        """Test badge with mixed case status"""
        html = render_status_badge("TAKEN")
        
        assert 'background: #DCFCE7' in html
        assert 'Taken' in html


class TestRenderEmptyState:
    """Test suite for render_empty_state function"""
    
    def test_empty_state_basic(self, monkeypatch):
        """Test basic empty state rendering"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_empty_state(
            icon="📭",
            title="No Data Available",
            message="You haven't added any items yet."
        )
        
        html = captured_html[0]
        
        assert '📭' in html
        assert 'No Data Available' in html
        assert "You haven't added any items yet." in html
        assert 'text-align: center' in html
        assert 'font-size: 48px' in html
    
    def test_empty_state_with_action_button(self, monkeypatch):
        """Test empty state with action button"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_empty_state(
            icon="💊",
            title="No Medicines",
            message="Add your first medicine to get started.",
            action_button={'text': 'Add Medicine', 'key': 'add_med'}
        )
        
        html = captured_html[0]
        
        assert 'Add Medicine' in html
        assert 'background: #166534' in html


class TestRenderIcon:
    """Test suite for render_icon function"""
    
    def test_icon_basic(self):
        """Test basic icon rendering"""
        html = render_icon("💊")
        
        assert '💊' in html
        assert 'font-size: 20px' in html
        assert 'color: #64748B' in html
        assert 'margin-right: 8px' in html
    
    def test_icon_custom_size(self):
        """Test icon with custom size"""
        html = render_icon("💊", size="32px")
        
        assert 'font-size: 32px' in html
    
    def test_icon_custom_color(self):
        """Test icon with custom color"""
        html = render_icon("💊", color="#166534")
        
        assert 'color: #166534' in html
    
    def test_icon_no_margin(self):
        """Test icon with no margin"""
        html = render_icon("💊", margin_right="0px")
        
        assert 'margin-right: 0px' in html


class TestRenderSectionHeader:
    """Test suite for render_section_header function"""
    
    def test_section_header_basic(self, monkeypatch):
        """Test basic section header"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_section_header("My Medicines")
        
        html = captured_html[0]
        
        assert 'My Medicines' in html
        assert 'font-size: 28px' in html
        assert 'font-weight: 700' in html
        assert 'color: #0F172A' in html
    
    def test_section_header_with_icon(self, monkeypatch):
        """Test section header with icon"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_section_header("My Medicines", icon="💊")
        
        html = captured_html[0]
        
        assert '💊' in html
        assert 'My Medicines' in html
    
    def test_section_header_with_subtitle(self, monkeypatch):
        """Test section header with subtitle"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_section_header(
            "My Medicines",
            subtitle="Manage your daily medication schedule"
        )
        
        html = captured_html[0]
        
        assert 'My Medicines' in html
        assert 'Manage your daily medication schedule' in html
    
    def test_section_header_custom_size(self, monkeypatch):
        """Test section header with custom title size"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_section_header("My Medicines", title_size="36px")
        
        html = captured_html[0]
        
        assert 'font-size: 36px' in html


class TestRenderErrorMessage:
    """Test suite for render_error_message function"""
    
    def test_error_message_error_type(self, monkeypatch):
        """Test error type message"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_error_message("error", "An error occurred")
        
        html = captured_html[0]
        
        assert 'background: #FEE2E2' in html
        assert 'border: 1px solid #FCA5A5' in html
        assert 'color: #991B1B' in html
        assert 'An error occurred' in html
        assert '❌' in html
    
    def test_error_message_warning_type(self, monkeypatch):
        """Test warning type message"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_error_message("warning", "Warning message")
        
        html = captured_html[0]
        
        assert 'background: #FEF3C7' in html
        assert 'color: #92400E' in html
        assert 'Warning message' in html
        assert '⚠️' in html
    
    def test_error_message_info_type(self, monkeypatch):
        """Test info type message"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_error_message("info", "Information message")
        
        html = captured_html[0]
        
        assert 'background: #DBEAFE' in html
        assert 'color: #1E40AF' in html
        assert 'Information message' in html
        assert 'ℹ️' in html
    
    def test_error_message_with_details(self, monkeypatch):
        """Test error message with details"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_error_message(
            "error",
            "Upload failed",
            details="File size exceeds 10MB limit"
        )
        
        html = captured_html[0]
        
        assert 'Upload failed' in html
        assert 'File size exceeds 10MB limit' in html
    
    def test_error_message_custom_icon(self, monkeypatch):
        """Test error message with custom icon"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_error_message("error", "Error", icon="🚨")
        
        html = captured_html[0]
        
        assert '🚨' in html


class TestRenderMetricCard:
    """Test suite for render_metric_card function"""
    
    def test_metric_card_basic(self, monkeypatch):
        """Test basic metric card rendering"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_metric_card("Blood Pressure", "120/80", "mmHg")
        
        # Should capture 2 markdown calls: one for content, one for card wrapper
        assert len(captured_html) >= 1
        html = ' '.join(captured_html)
        
        assert 'Blood Pressure' in html
        assert '120/80' in html
        assert 'mmHg' in html
    
    def test_metric_card_with_status(self, monkeypatch):
        """Test metric card with status badge"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_metric_card("Blood Pressure", "120/80", "mmHg", status="optimal")
        
        html = ' '.join(captured_html)
        
        assert 'Blood Pressure' in html
        assert '120/80' in html
        assert 'Optimal' in html
    
    def test_metric_card_with_icon(self, monkeypatch):
        """Test metric card with icon"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_metric_card("Blood Pressure", "120/80", "mmHg", icon="🩺")
        
        html = ' '.join(captured_html)
        
        assert '🩺' in html


class TestRenderMedicineTimelineItem:
    """Test suite for render_medicine_timeline_item function"""
    
    def test_medicine_timeline_basic(self, monkeypatch):
        """Test basic medicine timeline item"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        medicine = {
            'name': 'Aspirin',
            'dosage': '100mg (1 Tablet)',
            'time_slot': 'Morning - 8:00 AM',
            'status': 'pending',
            'instructions': 'Take with food'
        }
        
        render_medicine_timeline_item(medicine)
        
        html = ' '.join(captured_html)
        
        assert 'Aspirin' in html
        assert '100mg (1 Tablet)' in html
        assert 'Morning - 8:00 AM' in html
        assert 'Take with food' in html
        assert 'Pending' in html
    
    def test_medicine_timeline_with_actions(self, monkeypatch):
        """Test medicine timeline with action buttons"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        medicine = {
            'name': 'Aspirin',
            'dosage': '100mg',
            'time_slot': 'Morning',
            'status': 'pending',
            'instructions': 'Take with food'
        }
        
        render_medicine_timeline_item(medicine, show_actions=True)
        
        html = ' '.join(captured_html)
        
        assert 'Mark Taken' in html
        assert 'Skip' in html
    
    def test_medicine_timeline_no_actions_when_taken(self, monkeypatch):
        """Test medicine timeline doesn't show actions for taken medicine"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        medicine = {
            'name': 'Aspirin',
            'dosage': '100mg',
            'time_slot': 'Morning',
            'status': 'taken',
            'instructions': 'Take with food'
        }
        
        render_medicine_timeline_item(medicine, show_actions=True)
        
        html = ' '.join(captured_html)
        
        # Should not show action buttons for taken medicine
        assert 'Mark Taken' not in html
    
    def test_medicine_timeline_without_actions(self, monkeypatch):
        """Test medicine timeline without showing actions"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        medicine = {
            'name': 'Aspirin',
            'dosage': '100mg',
            'time_slot': 'Morning',
            'status': 'pending',
            'instructions': 'Take with food'
        }
        
        render_medicine_timeline_item(medicine, show_actions=False)
        
        html = ' '.join(captured_html)
        
        assert 'Mark Taken' not in html
        assert 'Skip' not in html


# Edge case tests
class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_content_card(self, monkeypatch):
        """Test card with empty content"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("")
        
        assert len(captured_html) == 1
    
    def test_special_characters_in_content(self, monkeypatch):
        """Test card with special characters"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        render_card("<p>Test & 'special' \"chars\"</p>")
        
        html = captured_html[0]
        assert "<p>Test & 'special' \"chars\"</p>" in html
    
    def test_very_long_message(self, monkeypatch):
        """Test error message with very long text"""
        captured_html = []
        
        def mock_markdown(html, unsafe_allow_html=False):
            captured_html.append(html)
        
        import streamlit as st
        monkeypatch.setattr(st, 'markdown', mock_markdown)
        
        long_message = "A" * 500
        render_error_message("error", long_message)
        
        html = captured_html[0]
        assert long_message in html
