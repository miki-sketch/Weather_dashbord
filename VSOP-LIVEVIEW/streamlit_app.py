import streamlit as st
import pandas as pd

# ページ設定
st.set_page_config(page_title="VSOPライブ情報", layout="wide")

# スタイル設定
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stSelectbox label {
        font-weight: bold;
    }
    .song-row {
        padding: 5px 0;
        border-bottom: 1px solid #eee;
    }
    </style>
    """, unsafe_allow_html=True)

# 1. 接続仕様
def load_data():
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # シートIDの定義
        gid_lives = "0"
        gid_songs = "1476106697" # 演奏曲目シート

        # URL構築
        lives_url = f"{base_url}/export?format=csv&gid={gid_lives}"
        songs_url = f"{base_url}/export?format=csv&gid={gid_songs}"

        # データ読み込み
        df_lives = pd.read_csv(lives_url, encoding='utf-8')
        df_songs = pd.read_csv(songs_url, encoding='utf-8')

        # 4. エラーガード: 列名の前後の空白を削除
        df_lives.columns = df_lives.columns.str.strip()
        df_songs.columns = df_songs.columns.str.strip()

        return df_lives, df_songs
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None

df_lives, df_songs = load_data()

if df_lives is not None and df_songs is not None:
    # 2. アプリの構造
    st.title("VSOPライブ情報")

    # サイドバー: 検索・選択フレーム
    with st.sidebar:
        st.header("検索・選択")
        
        # A) ライブ名の選択
        # 必要な列の存在確認
        if '日付' in df_lives.columns and 'ライブ名' in df_lives.columns:
            # 日付とライブ名を結合
            df_lives['display_name'] = df_lives['日付'].astype(str) + " " + df_lives['ライブ名'].astype(str)
            live_list = df_lives['display_name'].tolist()
            
            selected_live_display = st.selectbox("ライブを選択してください", live_list)
            
            # 選択されたライブの行を特定
            selected_live_row = df_lives[df_lives['display_name'] == selected_live_display].iloc[0]
        else:
            st.error("「ライブ情報」シートに '日付' または 'ライブ名' 列が見つかりません。")
            st.stop()

    # 右側: 結果表示フレーム
    # B) データの紐付け
    if 'ライブID' in df_lives.columns and 'ライブID' in df_songs.columns:
        live_id = selected_live_row['ライブID']
        songs_to_display = df_songs[df_songs['ライブID'] == live_id].copy()
    else:
        # ライブIDがない場合は名前で紐付けを試みる（仕様にはないがフォールバックまたはエラー表示）
        # 仕様では「選択されたライブに基づき」なので、適切な紐付けキーが必要。
        # ここでは「日付」と「ライブ名」の組み合わせでフィルタリングすることを想定。
        # もし「ライブID」がない場合、df_livesの選択行とdf_songsをどう紐付けるか確認が必要だが、
        # 一般的にはIDが使われるため、ここではIDがあると仮定するか、名前でマッチング。
        st.warning("紐付け用の 'ライブID' が見つかりません。シートの構成を確認してください。")
        st.stop()

    # C) 楽曲情報の表示
    st.subheader(f"演奏曲目: {selected_live_display}")

    # ソート: 「曲順」の昇順
    if '曲順' in songs_to_display.columns:
        songs_to_display = songs_to_display.sort_values(by='曲順')
    else:
        st.warning("'曲順' 列が見つからないため、読み込み順で表示します。")

    # D) YouTubeリンクの生成
    video_link_base = selected_live_row.get('動画リンク', "")
    
    # 必須列の確認
    required_cols = ['楽曲名', 'ボーカル', 'STARTTIME']
    missing_cols = [col for col in required_cols if col not in songs_to_display.columns]
    
    if not missing_cols:
        for _, song in songs_to_display.iterrows():
            song_name = song['楽曲名']
            vocal = song['ボーカル']
            starttime = song['STARTTIME']
            
            # リンク生成: リンク?t=秒数
            youtube_link = ""
            if pd.notna(video_link_base) and pd.notna(starttime):
                try:
                    # STARTTIMEを整数（または秒数）として扱う
                    seconds = int(starttime)
                    connector = "&" if "?" in str(video_link_base) else "?"
                    youtube_link = f"{video_link_base}{connector}t={seconds}"
                except ValueError:
                    youtube_link = video_link_base # 数値でない場合はそのまま

            # 表示: 「楽曲名」 ＋ 「ボーカル」 ＋ 「リンク」
            display_text = f"{song_name} {vocal} {youtube_link}".strip()
            st.write(display_text)
    else:
        st.error(f"「演奏曲目」シートに必要な列がありません: {', '.join(missing_cols)}")
else:
    st.info("Secrets に Google スプレッドシートの URL を設定してください。")
