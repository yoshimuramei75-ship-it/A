import streamlit as st
import google.generativeai as genai
import json
from PIL import Image
import re 

# ==========================================
# 🔑 APIキー（Web公開用の安全な設定）
# ==========================================
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    API_KEY = ""

# ==========================================
# 🧠 超・数学的抽出ロジック（絶対に狂わない）
# ==========================================
def extract_floats_strictly(text):
    if not text: return []
    matches = re.findall(r"\d*\.\d+|\d+", str(text))
    return [float(x) for x in matches]

def parse_input_val(val_str):
    nums = extract_floats_strictly(val_str)
    return nums[0] if nums else 0.0

def get_calc_nums(text):
    left_side = str(text).split('=')[0]
    return extract_floats_strictly(left_side)

def my_round(val):
    return round(val + 0.000001, 1)

def is_match_flexible(calc_val, input_val):
    raw_calc = round(calc_val, 2)
    rounded_calc = my_round(calc_val)
    if input_val == 0.0:
        return raw_calc == 0.0 or rounded_calc == 0.0
    return abs(input_val - raw_calc) < 0.001 or abs(input_val - rounded_calc) < 0.001

def get_check_message_flexible(title, calc_val, input_val, unit="人"):
    rounded_calc = my_round(calc_val)
    if input_val == 0.0:
        if is_match_flexible(calc_val, input_val):
            if calc_val == 0.0:
                return (f"✅ {title}", "空欄（作業なし）のためパスしました。")
            else:
                return (f"✅ {title}", f"OK: 計算値 {rounded_calc}{unit} ＝ 記入値 0.0{unit}（空欄）")
        else:
            return (f"❌ {title}", f"NG: 記入もれ、または計算が合いません")
    
    if is_match_flexible(calc_val, input_val):
        return (f"✅ {title}", f"OK: 計算値 {rounded_calc}{unit} ＝ 記入値 {input_val}{unit}")
    else:
        return (f"❌ {title}", f"NG: 計算が合いません")

def check_report(data):
    results = []

    # 0. 作業時間のチェック
    working_time_str = data.get('working_time', '')
    nm_nums = get_calc_nums(data.get('normal_worker_calc_str', ''))
    nm_hours = nm_nums[0] if len(nm_nums) > 0 else 0.0 

    calc_hours = 0.0
    if working_time_str:
        times = re.findall(r"(\d{1,2}):(\d{2})", working_time_str)
        if len(times) >= 2:
            start_h, start_m = int(times[0][0]), int(times[0][1])
            end_h, end_m = int(times[1][0]), int(times[1][1])
            start_time = start_h + start_m / 60.0
            end_time = end_h + end_m / 60.0
            calc_hours = round(end_time - start_time, 1)

    if calc_hours == 0.0 and nm_hours == 0.0:
        results.append(("✅ 作業時間の整合性", "空欄のためパスしました。"))
    elif abs(calc_hours - nm_hours) < 0.001:
        results.append(("✅ 作業時間の整合性", f"OK: 作業時間({working_time_str} ＝ {calc_hours}h) ＝ 計算式の時間({nm_hours}h)"))
    else:
        results.append(("❌ 作業時間の整合性", f"NG: 作業時間({working_time_str} ＝ {calc_hours}h) に対して、普通作業員の時間が({nm_hours}h) となっており、ずれています！"))

    st.write("---") 

    # 1. 記入値のパース
    special_in = parse_input_val(data.get('special_worker_input', ''))
    normal_in  = parse_input_val(data.get('normal_worker_input', ''))
    driver_in  = parse_input_val(data.get('driver_input', ''))
    backhoe_in = parse_input_val(data.get('backhoe_input', ''))
    truck_in   = parse_input_val(data.get('truck_input', ''))

    # 2. 特殊作業員
    sp_nums = get_calc_nums(data.get('special_worker_calc_str', ''))
    sp_calc = (sp_nums[0] / 8.0) if len(sp_nums) > 0 else 0.0
    results.append(get_check_message_flexible("特殊作業員", sp_calc, special_in))

    # 3. 普通作業員
    nm_calc = 0.0
    if len(nm_nums) > 0:
        ops = nm_nums[:-1] if nm_nums[-1] in [8.0, 8] else nm_nums
        h = ops[0] if len(ops) > 0 else 0.0
        p = ops[1] if len(ops) > 1 else 0.0
        adds = sum(ops[2:]) if len(ops) > 2 else 0.0 
        nm_calc = (h * p + adds) / 8.0
    results.append(get_check_message_flexible("普通作業員", nm_calc, normal_in))

    # 4. 一般運転手
    dr_calc = truck_in / 8.0
    driver_calc_str = str(data.get('driver_calc_str', ''))
    if driver_in == 0.0 and '0.0' in driver_calc_str:
        results.append(("✅ 一般運転手", "OK: 記入欄は空欄ですが、計算結果が 0.0人 のためパスしました。"))
    else:
        results.append(get_check_message_flexible("一般運転手", dr_calc, driver_in))

    # 5. 小型バックホウ (転記)
    bh_nums = get_calc_nums(data.get('backhoe_calc_str', ''))
    bh_calc = bh_nums[0] if bh_nums else 0.0
    if backhoe_in == 0.0:
        if bh_calc == 0.0:
            results.append(("✅ 小型バックホウ (転記)", "空欄（稼働なし）のためパスしました。"))
        else:
            results.append(("❌ 小型バックホウ (転記)", f"NG: 記入もれ、または転記ミスがあります！"))
    elif backhoe_in == bh_calc:
        results.append(("✅ 小型バックホウ (転記)", f"OK: 記入値 {backhoe_in}h ＝ 計算欄 {bh_calc}h"))
    else:
        results.append(("❌ 小型バックホウ (転記)", f"NG: 転記ミスがあります！"))

    # 6. 距離の転記
    tr_nums = get_calc_nums(data.get('truck_calc_str', ''))
    tr_dist = tr_nums[0] if tr_nums else 0.0
    m_nums = extract_floats_strictly(data.get('material_distance_str', ''))
    mat_dist = m_nums[-1] if m_nums else 0.0
    if tr_dist == 0.0 and mat_dist == 0.0:
        results.append(("✅ 距離の転記", "空欄のためパスしました。"))
    elif tr_dist == mat_dist:
        results.append(("✅ 距離の転記", f"OK: 資材合計 {mat_dist}km ＝ トラック計算欄 {tr_dist}km"))
    else:
        results.append(("❌ 距離の転記", f"NG: 転記ミスがあります！"))

    # 7. トラック稼働時間
    if truck_in == 0.0:
        results.append(("✅ トラック稼働時間", "空欄（稼働なし）のためパスしました。"))
    else:
        tr_calc = 0.0
        if len(tr_nums) > 0:
            dist = tr_nums[0]
            mult = 1.0 
            if len(tr_nums) >= 3 and tr_nums[1] in [30.0, 30]:
                mult = tr_nums[2]
            tr_calc = (dist / 30.0) * mult
        tr_calc_rounded = my_round(tr_calc)
        if tr_calc_rounded == truck_in or round(tr_calc, 2) == truck_in:
            results.append(("✅ トラック稼働時間", f"OK: 計算値 {tr_calc_rounded}h ＝ 記入値 {truck_in}h"))
        else:
            results.append(("❌ トラック稼働時間", f"NG: 計算が合いません"))

    return results

# ==========================================
# 🎨 画面レイアウト（タブを廃止し、最速貼り付け特化！）
# ==========================================
st.set_page_config(page_title="応急作業日報チェック", layout="centered")

if 'processed_image' not in st.session_state:
    st.session_state['processed_image'] = None

st.title("🚧 応急作業日報 自動チェックアプリ 🐙")

st.markdown("### 📋 スクショをそのまま貼り付け！")
st.success("💡 **最速のやり方**\n1. `Win` + `Shift` + `S` キーで日報のスクショを撮る\n2. アプリを開いて、どこもクリックせずにそのまま **`Ctrl` + `V`** を押すだけ！")

# タブをなくして、常に貼り付けを受け付ける状態にしました
uploaded_file = st.file_uploader("📂 万が一貼り付けられない場合は、ここから選んでください", type=['png', 'jpg', 'jpeg'], key="file_uploader", label_visibility="collapsed")

# スマホの人向けに、カメラも下に出しておきます
with st.expander("📸 スマホから直接撮影する場合はこちらをタップ"):
    camera_file = st.camera_input("カメラで撮影", label_visibility="collapsed")
else:
    camera_file = None

# 画像のセット
temp_image = None
if uploaded_file:
    temp_image = Image.open(uploaded_file)
elif camera_file:
    temp_image = Image.open(camera_file)

if temp_image:
    st.session_state['processed_image'] = temp_image

# --- 解析セクション ---
if st.session_state['processed_image']:
    st.write("---")
    image = st.session_state['processed_image']
    st.image(image, caption="読み込んだ日報", use_container_width=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🗑️ 画像をクリアしてやり直す", use_container_width=True):
            st.session_state['processed_image'] = None
            st.rerun()
    with col2:
        analyze_button = st.button("✨ AIで計算・転記チェック！", type="primary", use_container_width=True)

    if analyze_button:
        if not API_KEY:
             st.error("⚠️ StreamlitのSecretsにAPIキーが設定されていません！")
        else:
            with st.spinner('🤖 AIが画像を分析中...（数秒〜十数秒かかります）'):
                try:
                    genai.configure(api_key=API_KEY)
                    model = genai.GenerativeModel('gemini-2.0-flash')

                    prompt = """
                    あなたは建設業の書類転記のプロです。画像に書かれている文字を「そのまま」書き起こし、JSON形式で出力してください。
                    カッコ、＋、×などの記号、空欄の「人」なども含めて、見たままの文字を出力してください。AI自身で計算は不要です。

                    【抽出する項目】
                    0. 作業時間
                       - 「作業時間」の欄の文字: (例: "14:00 ～ 17:00"、空欄なら必ず "" と出力)
                    1. 特殊作業員
                       - 左側の「人」の前の文字: (空欄なら必ず "" と出力)
                       - 中央の計算式の文字: (例: "2.0 h / 8.0 ="、空欄なら "")
                    2. 普通作業員
                       - 左側の「人」の前の文字: (例: "1.5"、空欄なら "")
                       - 中央の計算式の文字: (例: "(3.0 h × 3.0人 ＋ 2.1 ＋ 1.0 ) / 8.0 ="、カッコがない場合もあるので注意)
                    3. 一般運転手
                       - 左側の「人」の前の文字: (空欄なら必ず "" と出力)
                       - 右側の計算式と結果の文字: (例: "0.1 h / 8.0 = 0.0人"、空欄なら "")
                    4. 小型バックホウ
                       - 左側の「時間」の前の文字: (空欄なら必ず "" と出力)
                       - 中央の文字: (空欄なら "")
                    5. トラック[普通]
                       - 左側の「時間」の前の文字: (例: "0.9"、空欄なら "")
                       - 中央の計算式の文字: (例: "28.0 km / 30.0km =" や "27.5 km / 30.0km × 2.0 =")
                    6. 資材 (一番下の行)
                       - 一番右側の計算結果周辺の文字すべて: (例: "= 27.55 (他0.45) 28.0km")

                    【出力JSONのキー名（値はすべて文字列型にすること）】
                    {
                      "working_time": "",
                      "special_worker_input": "",
                      "special_worker_calc_str": "",
                      "normal_worker_input": "",
                      "normal_worker_calc_str": "",
                      "driver_input": "",
                      "driver_calc_str": "",
                      "backhoe_input": "",
                      "backhoe_calc_str": "",
                      "truck_input": "",
                      "truck_calc_str": "",
                      "material_distance_str": ""
                    }
                    """

                    response = model.generate_content(
                        [prompt, st.session_state['processed_image']],
                        generation_config=genai.types.GenerationConfig(temperature=0.0)
                    )
                    
                    result_text = response.text.replace("```json", "").replace("```", "").strip()
                    extracted_data = json.loads(result_text)

                    st.success("読み取り完了！")
                    
                    with st.expander("👀 AIが読み取った生の文字データ（クリックで開く）"):
                        st.json(extracted_data)

                    check_results = check_report(extracted_data)
                    for title, detail in check_results:
                        if "✅" in title:
                            st.success(f"**{title}**\n\n{detail}")
                        else:
                            st.error(f"**{title}**\n\n{detail}")

                except json.JSONDecodeError:
                    st.error("❌ AIの返答がJSON形式ではありませんでした。もう一度ボタンを押してみてください。")
                except Exception as e:
                    st.error(f"❌ エラーが発生しました: {e}")