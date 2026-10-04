# CareVoice Navigation System Module
# Provides responsive navigation with mobile bottom bar and desktop sidebar

import streamlit as st
from html import escape
import secrets

from db import carevoice_db as db


# Navigation Items Configuration
NAV_ITEMS = [
    {
        "label": "My Home",
        "icon": "🏠",
        "description": "Dashboard",
        "page": "Home",
        "primary": True
    },
    {
        "label": "My Medicines",
        "icon": "💊",
        "description": "Schedule & Prescriptions",
        "page": "Medicines",
        "primary": True
    },
    {
        "label": "My Prescriptions",
        "icon": "📋",
        "description": "3-Step Upload Workflow",
        "page": "Prescriptions",
        "primary": True
    },
    {
        "label": "My Health",
        "icon": "🩺",
        "description": "Health Metrics & Charts",
        "page": "Health",
        "primary": True
    },
    {
        "label": "My Voice Assistant",
        "icon": "🎙️",
        "description": "CareVoice Siri Hub",
        "page": "Voice Assistant",
        "primary": True,
    },
    {
        "label": "My Diet",
        "icon": "🥗",
        "description": "Daily Nutrition Guidance",
        "page": "Diet",
        "primary": True
    },
    {
        "label": "My Settings",
        "icon": "⚙️",
        "description": "Preferences & Language",
        "page": "Settings",
        "primary": False
    }
]


TELUGU_NAV_LABELS = {
    "Home": "నా హోమ్",
    "Medicines": "నా మందులు",
    "Prescriptions": "నా ప్రిస్క్రిప్షన్లు",
    "Health": "నా ఆరోగ్యం",
    "Voice Assistant": "నా వాయిస్ సహాయకుడు",
    "Diet": "నా ఆహారం",
    "Settings": "నా సెట్టింగ్‌లు",
}


def navigation_label(item: dict, is_te: bool = False) -> str:
    if is_te:
        return TELUGU_NAV_LABELS[item["page"]]
    return item["label"]


def _session_get(key: str, default=None):
    state = st.session_state
    if hasattr(state, "get"):
        return state.get(key, default)
    return getattr(state, key, default)


def _session_set(key: str, value) -> None:
    state = st.session_state
    if hasattr(state, "__setitem__"):
        state[key] = value
    else:
        setattr(state, key, value)


def navigate_to_page(page_name: str) -> None:
    """
    Helper function for programmatic navigation.
    Updates session state and triggers page rerun.
    
    Args:
        page_name: The name of the page to navigate to (e.g., "Home", "Medicines")
    """
    if page_name in [item["page"] for item in NAV_ITEMS]:
        _session_set("current_page", page_name)
        st.rerun()
    else:
        st.error(f"Invalid page: {page_name}")


def _close_mobile_menu() -> None:
    _session_set("mobile_nav_open", False)


def _sign_out_from_mobile_menu() -> None:
    db.revoke_auth_session(_session_get("auth_session_token", ""))
    _session_set("auth_session_token", "")
    _session_set("user", None)
    _session_set("view", "landing")
    _session_set("current_page", "Home")
    _session_set("mobile_nav_open", False)
    _session_set("pending_auth_cookie", {
        "action": "clear",
        "nonce": secrets.token_urlsafe(12),
    })
    st.rerun()


def render_mobile_drawer(user_name: str, current_page: str, is_te: bool) -> None:
    state = st.session_state
    if hasattr(state, "__contains__"):
        if "mobile_nav_open" not in state:
            _session_set("mobile_nav_open", False)
    elif not hasattr(state, "mobile_nav_open"):
        _session_set("mobile_nav_open", False)

    st.markdown("""
    <style>
    @media (max-width: 767px) {
      section[data-testid="stSidebar"] { display:none !important; }
      .main .block-container { padding-top:4.25rem !important; }
      div.st-key-carevoice_mobile_menu_toggle {
        position:fixed; top:12px; left:12px; z-index:10002; width:46px;
      }
      div.st-key-carevoice_mobile_menu_toggle button {
        width:46px; height:46px; padding:0; border:1px solid #dbe5df;
        border-radius:12px; background:#fff; color:#166534; font-size:25px;
        box-shadow:0 3px 12px #0f172a18;
      }
      div.st-key-carevoice_mobile_panel {
        position:fixed; inset:0 auto 0 0; z-index:10001; box-sizing:border-box;
        width:min(340px, 88vw); height:100dvh; overflow-y:auto; padding:20px 16px;
        background:#fff; box-shadow:0 0 0 100vmax #0f172a66, 8px 0 28px #0f172a24;
      }
      div.st-key-carevoice_mobile_panel button {
        min-height:48px; text-align:left; text-decoration:none !important;
        border-bottom:0 !important;
      }
      div.st-key-carevoice_mobile_panel .stMarkdown h2,
      div.st-key-carevoice_mobile_panel .stMarkdown p {
        text-decoration:none !important; border-bottom:0 !important;
      }
    }
    @media (min-width: 768px) {
      div.st-key-carevoice_mobile_menu_toggle,
      div.st-key-carevoice_mobile_panel { display:none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    menu_label = "నావిగేషన్ మెను" if is_te else "Navigation menu"
    if st.button("☰", key="carevoice_mobile_menu_toggle", help=menu_label):
        _session_set("mobile_nav_open", not _session_get("mobile_nav_open", False))

    if not _session_get("mobile_nav_open", False):
        return

    with st.container(key="carevoice_mobile_panel"):
        header_col, close_col = st.columns([5, 1])
        with header_col:
            st.markdown(
                f"<h2 style='margin:0; color:#166534;'>🌿 CareVoice</h2>"
                f"<p style='margin:2px 0 12px; color:#64748b;'>{escape(str(user_name))}</p>",
                unsafe_allow_html=True,
            )
        with close_col:
            if st.button("×", key="carevoice_mobile_menu_close", help=(
                "మెను మూసివేయండి" if is_te else "Close menu"
            )):
                _close_mobile_menu()
                st.rerun()

        for item in NAV_ITEMS:
            active = item["page"] == current_page
            if st.button(
                f'{item["icon"]}  {navigation_label(item, is_te)}',
                key=f'carevoice_mobile_nav_{item["page"].lower().replace(" ", "_")}',
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                _session_set("mobile_nav_open", False)
                navigate_to_page(item["page"])

        if st.button(
            "🚪 లాగ్ అవుట్" if is_te else "🚪 Sign Out",
            key="carevoice_mobile_sign_out",
            use_container_width=True,
            type="secondary",
        ):
            _sign_out_from_mobile_menu()


def render_sidebar_navigation() -> None:
    """
    Renders desktop sidebar navigation with all pages.
    Shows full navigation list with icons, labels, and active state highlighting.
    Includes language settings, elderly mode toggle, and sign out button.
    
    Responsive: Displayed when screen width >= 768px
    """
    user = st.session_state.get("user")
    if not user:
        return
    
    user_name = user.get("name", "User")
    current_page = st.session_state.get("current_page", "Home")
    is_te = st.session_state.get("lang_code", "en-IN") == "te-IN"
    page_labels_te = {
        "Home": ("నా హోమ్", "డాష్‌బోర్డ్"),
        "Medicines": ("నా మందులు", "మందుల షెడ్యూల్ మరియు వివరాలు"),
        "Prescriptions": ("నా ప్రిస్క్రిప్షన్లు", "ప్రిస్క్రిప్షన్ అప్‌లోడ్"),
        "Health": ("నా ఆరోగ్యం", "ఆరోగ్య కొలతలు మరియు చార్ట్‌లు"),
        "Voice Assistant": ("నా వాయిస్ సహాయకుడు", "కేర్‌వాయిస్"),
        "Diet": ("నా ఆహారం", "రోజువారీ పోషకాహార సూచనలు"),
        "Settings": ("నా సెట్టింగ్‌లు", "ప్రాధాన్యతలు మరియు భాష"),
    }
    
    with st.sidebar:
        # Logo and User Profile Header
        st.markdown(f"""
            <div style='display:flex; align-items:center; gap:12px; margin-bottom:20px;'>
                <div style='background:#166534; color:white; width:40px; height:40px; border-radius:10px; 
                            display:flex; align-items:center; justify-content:center; font-size:20px; font-weight:bold;'>🌿</div>
                <div>
                    <h2 style='margin:0; font-size:20px; color:#166534;'>CareVoice</h2>
                    <p style='margin:0; font-size:12px; color:#64748b;'>{user_name}</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Navigation Items
        for item in NAV_ITEMS:
            is_active = current_page == item["page"]
            label, description = page_labels_te.get(
                item["page"], (item["label"], item["description"])
            ) if is_te else (item["label"], item["description"])
            btn_label = f"{item['icon']}  {label}"
            
            # Create unique key for each button
            btn_key = f"nav_sidebar_{item['page']}"
            
            if st.button(
                btn_label, 
                use_container_width=True, 
                type="primary" if is_active else "secondary",
                key=btn_key,
                help=description
            ):
                navigate_to_page(item["page"])
        
        st.markdown("---")
        
        # Language Selection
        st.caption("🌐 భాష" if is_te else "🌐 Language")
        lang_options = ["ఇంగ్లీష్", "తెలుగు"] if is_te else ["English", "తెలుగు"]
        lang_index = 1 if is_te else 0
        
        lang_sel = st.radio(
            "Language Select", 
            lang_options, 
            index=lang_index, 
            label_visibility="collapsed",
            key="sidebar_lang_select"
        )
        
        new_lang_code = "te-IN" if "తెలుగు" in lang_sel else "en-IN"
        if new_lang_code != st.session_state.lang_code:
            st.session_state.lang_code = new_lang_code
            if user:
                from db import carevoice_db as db
                db.update_user_preferences(user["id"], language=new_lang_code)
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Elderly Mode Toggle
        elderly_mode = st.session_state.get("elderly_mode", False)
        new_elderly_mode = st.toggle(
            "👵 వృద్ధుల మోడ్" if is_te else "👵 Elderly Mode",
            value=elderly_mode,
            key="sidebar_elderly_toggle"
        )
        
        if new_elderly_mode != elderly_mode:
            st.session_state.elderly_mode = new_elderly_mode
            st.rerun()
        
        st.markdown("---")
        
        # Sign Out Button
        if st.button("🚪 సైన్ అవుట్" if is_te else "🚪 Sign Out", use_container_width=True, type="secondary", key="sidebar_signout"):
            db.revoke_auth_session(st.session_state.get("auth_session_token", ""))
            st.session_state.auth_session_token = ""
            st.session_state.user = None
            st.session_state.view = "landing"
            st.session_state.current_page = "Home"
            st.session_state.pending_auth_cookie = {
                "action": "clear",
                "nonce": secrets.token_urlsafe(12),
            }
            st.rerun()


def render_bottom_navigation() -> None:
    """
    Renders mobile bottom navigation bar with 5 primary items.
    Fixed position at bottom of screen with icons and labels.
    Shows active state highlighting and provides quick access to main features.
    
    Responsive: Displayed when screen width < 768px
    Primary Items: Home, Medicines, Prescriptions, Health, Voice
    """
    current_page = st.session_state.get("current_page", "Home")
    is_te = st.session_state.get("lang_code", "en-IN") == "te-IN"
    mobile_labels_te = {
        "Home": "నా హోమ్",
        "Medicines": "నా మందులు",
        "Prescriptions": "నా ప్రిస్క్రిప్షన్లు",
        "Health": "నా ఆరోగ్యం",
        "Voice Assistant": "నా వాయిస్",
    }
    
    # Get primary navigation items only (first 5)
    primary_items = [item for item in NAV_ITEMS if item.get("primary", False)][:5]
    
    # Build bottom navigation HTML
    nav_html = """
    <style>
    .bottom-nav {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #FFFFFF;
        border-top: 1px solid #E2E8F0;
        display: flex;
        justify-content: space-around;
        align-items: center;
        padding: 8px 0;
        z-index: 1000;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
    }
    
    .bottom-nav-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        flex: 1;
        padding: 8px 4px;
        text-decoration: none;
        color: #64748B;
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        min-width: 60px;
        border-radius: 8px;
    }
    
    .bottom-nav-item:hover {
        background: #FFFFFF;
    }
    
    .bottom-nav-item.active {
        color: #166534;
        background: #FFFFFF;
    }
    
    .bottom-nav-icon {
        font-size: 24px;
        margin-bottom: 4px;
    }
    
    .bottom-nav-label {
        font-size: 11px;
        line-height: 1;
        text-align: center;
    }
    
    /* Only show on mobile */
    @media (min-width: 768px) {
        .bottom-nav {
            display: none;
        }
    }
    
    /* Add padding to main content to prevent overlap */
    .main .block-container {
        padding-bottom: 80px !important;
    }
    </style>
    
    <div class="bottom-nav" id="bottomNav">
    """
    
    for item in primary_items:
        is_active = current_page == item["page"]
        active_class = "active" if is_active else ""
        display_label = mobile_labels_te[item["page"]] if is_te else item["label"]
        
        nav_html += f"""
        <div class="bottom-nav-item {active_class}" onclick="navigateToPage('{item['page']}')" 
             title="{item['description']}" tabindex="0" 
             onkeypress="if(event.key==='Enter') navigateToPage('{item['page']}')">
            <div class="bottom-nav-icon">{item['icon']}</div>
            <div class="bottom-nav-label">{display_label}</div>
        </div>
        """
    
    nav_html += """
    </div>
    
    <script>
    function navigateToPage(page) {
        // Set query parameter to trigger navigation
        const url = new URL(window.location);
        url.searchParams.set('nav_to', page);
        window.location.href = url.toString();
    }
    
    // Keyboard navigation support
    document.addEventListener('keydown', function(event) {
        const items = document.querySelectorAll('.bottom-nav-item');
        const activeIndex = Array.from(items).findIndex(item => 
            document.activeElement === item
        );
        
        if (event.key === 'ArrowLeft' && activeIndex > 0) {
            items[activeIndex - 1].focus();
            event.preventDefault();
        } else if (event.key === 'ArrowRight' && activeIndex < items.length - 1) {
            items[activeIndex + 1].focus();
            event.preventDefault();
        }
    });
    </script>
    """
    
    # Render the HTML
    st.markdown(nav_html, unsafe_allow_html=True)
    
    # Handle navigation from query parameters (for bottom nav clicks)
    query_params = st.query_params
    nav_to = query_params.get("nav_to")
    if nav_to:
        # Clear the query parameter
        st.query_params.clear()
        # Navigate to the page
        navigate_to_page(nav_to)


def render_responsive_navigation() -> None:
    """
    Renders appropriate navigation based on screen size:
    - Desktop (>=768px): Sidebar navigation
    - Mobile (<768px): Bottom navigation bar
    
    Uses CSS media queries to handle responsive switching automatically.
    Includes keyboard navigation support for accessibility.
    """
    # Always render sidebar (CSS will hide on mobile)
    render_sidebar_navigation()
    
    # Always render bottom nav (CSS will hide on desktop)
    render_bottom_navigation()


def init_navigation_state() -> None:
    """
    Initializes navigation state in session storage.
    Sets default current_page to "Home" if not already set.
    Should be called once during app initialization.
    """
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Home"


def get_current_page() -> str:
    """
    Returns the current active page name.
    
    Returns:
        str: Current page name (e.g., "Home", "Medicines")
    """
    return st.session_state.get("current_page", "Home")


def get_page_config(page_name: str) -> dict:
    """
    Returns configuration dictionary for a specific page.
    
    Args:
        page_name: The page name to get config for
        
    Returns:
        dict: Page configuration with icon, description, etc.
        None if page not found
    """
    for item in NAV_ITEMS:
        if item["page"] == page_name:
            return item
    return None
