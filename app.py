import streamlit as st
import feedparser
import urllib.parse
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="AI News Collector",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS for Premium Design ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main {
        background-color: #f8f9fa;
    }

    /* Card Styling */
    .news-card {
        background: white;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
    }

    .news-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        border-color: #6366f1;
    }

    .news-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 8px;
        line-height: 1.4;
    }

    .news-date {
        font-size: 0.875rem;
        color: #718096;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
    }

    .news-summary {
        font-size: 1rem;
        color: #4a5568;
        line-height: 1.6;
        margin-bottom: 20px;
    }

    .news-link {
        display: inline-block;
        background-color: #6366f1;
        color: white !important;
        padding: 10px 20px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.875rem;
        transition: background-color 0.2s;
    }

    .news-link:hover {
        background-color: #4f46e5;
    }

    /* Header Styling */
    .header-container {
        padding: 2rem 0;
        text-align: center;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border-radius: 20px;
        margin-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("🔍 検索設定")
search_query = st.sidebar.text_input("キーワードを入力", value="Artificial Intelligence")
st.sidebar.info("Google News RSSを使用して最新の情報を取得します。")

# --- News Fetching Logic ---
@st.cache_data(ttl=3600)  # 1 hour cache
def fetch_news(query):
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    return feed.entries

# --- Main Page ---
st.markdown('<div class="header-container"><h1>🤖 AIニュース収集ダッシュボード</h1><p>最新のテクノロジー・トレンドをチェック</p></div>', unsafe_allow_html=True)

if search_query:
    with st.spinner(f"「{search_query}」のニュースを取得中..."):
        entries = fetch_news(search_query)

    if not entries:
        st.warning("ニュースが見つかりませんでした。別のキーワードを試してください。")
    else:
        # Display news in cards (Grid layout)
        # Using columns for responsiveness
        cols = st.columns(1) # We can change this to 2 or 3 for wider screens, but Streamlit columns behave differently. 
        # For simplicity and clean card stacking, we'll use a single column of wide cards.

        for entry in entries[:15]: # Show top 15 news
            # Format date
            try:
                dt = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                formatted_date = dt.strftime('%Y年%m月%d日 %H:%M')
            except:
                formatted_date = entry.published

            # Render Card
            st.markdown(f"""
            <div class="news-card">
                <div class="news-title">{entry.title}</div>
                <div class="news-date">📅 {formatted_date}</div>
                <div class="news-summary">{entry.summary}</div>
                <a href="{entry.link}" target="_blank" class="news-link">記事を読む</a>
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("左のサイドバーから検索ワードを入力してください。")

# --- Footer ---
st.markdown("---")
st.markdown('<p style="text-align: center; color: #718096;">Powered by Streamlit & Google News RSS</p>', unsafe_allow_html=True)
