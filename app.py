import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import swisseph as swe
import math
import pandas as pd
from datetime import date, datetime, timedelta, timezone, time

# --- THIS MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(layout="wide", page_title="Astrolabe Explorer")

# --- 1. PASSWORD PROTECTION GATE ---
def check_password():
    """Returns `True` if the user had the correct password."""
    if st.session_state.get("password_correct", False):
        return True

    st.markdown("### 🔒 Astrolabe Secure Login")
    entered_pwd = st.text_input("Enter Passkey", type="password")
    
    if entered_pwd:
        if entered_pwd == st.secrets["app_password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
            
    return False

if not check_password():
    st.stop()

# ==========================================
# ASTROLOGY CONSTANTS & MAPPINGS
# ==========================================
NL_SEQUENCE = ["KE", "VE", "SU", "MO", "MA", "RA", "JU", "SA", "ME"]
KP_YEARS = {"KE": 7, "VE": 20, "SU": 6, "MO": 10, "MA": 7, "RA": 18, "JU": 16, "SA": 19, "ME": 17}

RASHI_LORDS = {
    1: "MA", 2: "VE", 3: "ME", 4: "MO", 5: "SU", 6: "ME",
    7: "VE", 8: "MA", 9: "JU", 10: "SA", 11: "SA", 12: "JU"
}

LORD_TO_RASHIS = {}
for rashi, lord in RASHI_LORDS.items():
    LORD_TO_RASHIS.setdefault(lord, []).append(rashi)

SECTORS = {
    "Banking / Financials": ["JU", "VE", "SA"],
    "Auto": ["MA", "VE", "SU"],
    "FMCG": ["MO", "VE", "JU"],
    "IT": ["ME", "RA", "SA"],
    "Infra": ["SA", "MA", "SU"],
    "Reality": ["MO", "VE", "SA"],
    "Pharma": ["KE", "SA", "JU"],
    "Energy": ["SU", "MA", "SA"],
    "Media": ["ME", "RA", "MO"],
    "Metals": ["MA", "SA", "RA"]
}

ZONE_SCORES = [1, 1, -1, 1, 0, -1, 1, -1, 1, -1, 1, -1]

# ==========================================
# CORE CALCULATION FUNCTIONS
# ==========================================
def get_current_ist_rounded():
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    minute = 5 * round(ist_now.minute / 5)
    if minute >= 60:
        ist_now += timedelta(hours=1)
        minute = 0
    rounded_time = ist_now.replace(minute=minute, second=0, microsecond=0)
    
    final_time = rounded_time.time()
    if final_time < time(9, 15): final_time = time(9, 15)
    if final_time > time(15, 30): final_time = time(15, 30)
    return rounded_time.date(), final_time

def get_jd(year, month, day, hour, minute):
    utc_hour = hour - 5
    utc_min = minute - 30
    if utc_min < 0:
        utc_min += 60
        utc_hour -= 1
    return swe.julday(year, month, day, utc_hour + utc_min/60.0)

def get_nl_sl(longitude):
    long_min = longitude * 60.0
    nak_idx = int(long_min / 800.0)
    nl = NL_SEQUENCE[nak_idx % 9]
    rem_min = long_min % 800.0
    start_idx = NL_SEQUENCE.index(nl)
    cum_span = 0.0
    for i in range(9):
        sl = NL_SEQUENCE[(start_idx + i) % 9]
        span = KP_YEARS[sl] * (800.0 / 120.0)
        cum_span += span
        if rem_min < cum_span:
            return nl, sl
    return nl, nl

def get_lagna(year, month, day, hour, minute):
    jd = get_jd(year, month, day, hour, minute)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    cusps, ascmc = swe.houses_ex(jd, 12.9716, 77.5946, b'P', swe.FLG_SIDEREAL)
    return int(math.floor(ascmc[0] + 0.5)) % 360

def get_moon_nl_sl(year, month, day, hour, minute):
    jd = get_jd(year, month, day, hour, minute)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    pos, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    return get_nl_sl(pos[0])

def get_planetary_positions(year, month, day, hour, minute):
    jd = get_jd(year, month, day, hour, minute)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    
    planets = {
        "SU": swe.SUN, "MO": swe.MOON, "MA": swe.MARS, "ME": swe.MERCURY, 
        "JU": swe.JUPITER, "VE": swe.VENUS, "SA": swe.SATURN, "RA": swe.MEAN_NODE
    }
    positions = {}
    ra_exact_lon = 0
    for name, p_id in planets.items():
        pos, _ = swe.calc_ut(jd, p_id, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
        lon = pos[0]
        if name == "RA": ra_exact_lon = lon
        positions[name] = {"deg": int(math.floor(lon + 0.5)) % 360, "nl": get_nl_sl(lon)[0], "sl": get_nl_sl(lon)[1]}
        
    ke_exact_lon = (ra_exact_lon + 180) % 360
    ke_nl, ke_sl = get_nl_sl(ke_exact_lon)
    positions["KE"] = {"deg": int(math.floor(ke_exact_lon + 0.5)) % 360, "nl": ke_nl, "sl": ke_sl}
    return positions

def get_tithi_info(year, month, day, hour=9, minute=15):
    jd = get_jd(year, month, day, hour, minute)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    sun_pos, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    moon_pos, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    
    diff = (moon_pos[0] - sun_pos[0]) % 360
    tithi_num = math.floor(diff / 12) + 1
    
    t_type = tithi_num % 5
    if t_type == 1:
        return f"Tithi {tithi_num} (Nanda) - 📈 Trending Day Likely. Ride the momentum."
    elif t_type == 2:
        return f"Tithi {tithi_num} (Bhadra) - ⚖️ Steady/Balanced Day. Respect technical levels."
    elif t_type == 3:
        return f"Tithi {tithi_num} (Jaya) - 🚀 Victory/Bullish Bias. Look for breakout longs."
    elif t_type == 4:
        return f"Tithi {tithi_num} (Rikta) - ⚠️ 'Empty' Hands. High Risk of SL Hunting & Volatility."
    else: 
        return f"Tithi {tithi_num} (Purna) - 🔄 Reversal Day. Watch for major market turning points."

def ang_dist(d1, d2):
    return min(abs(d1 - d2), 360 - abs(d1 - d2))

# ==========================================
# ADVANCED SECTOR SCORING (NAKSHATRA FILTER)
# ==========================================
def calculate_sector_scores(year, month, day, hour, minute):
    lagna = get_lagna(year, month, day, hour, minute)
    planets = get_planetary_positions(year, month, day, hour, minute)
    inner_offset = 30 - lagna
    
    planet_true_scores = {}
    
    for p_name, data in planets.items():
        shifted_deg = (data["deg"] + inner_offset) % 360
        planet_zone_score = ZONE_SCORES[int(shifted_deg // 30)]
        
        nl = data["nl"]
        nl_shifted_deg = (planets[nl]["deg"] + inner_offset) % 360
        nl_zone_score = ZONE_SCORES[int(nl_shifted_deg // 30)]
        
        planet_true_scores[p_name] = planet_zone_score + nl_zone_score
        
    sector_results = []
    for sector, governing_planets in SECTORS.items():
        score = sum([planet_true_scores[p] for p in governing_planets])
        
        if score >= 2:
            sentiment = "Strong Buy"
            color = "#00CC96" 
        elif score <= -2:
            sentiment = "Strong Sell"
            color = "#EF553B" 
        else:
            sentiment = "Choppy / Wait"
            color = "#888888" 
            
        sector_results.append({
            "Sector": sector,
            "Score": score,
            "Sentiment": sentiment,
            "Color": color
        })
        
    return pd.DataFrame(sector_results), planets, lagna

# ==========================================
# PRE-CALCULATED DAILY TIMELINES (CACHED)
# ==========================================
@st.cache_data(show_spinner=False)
def generate_all_trends_html(year, month, day):
    start_t = datetime(year, month, day, 9, 15)
    end_t = datetime(year, month, day, 15, 30)
    
    nifty_html_parts = []
    sector_html_parts = {s: [] for s in SECTORS.keys()}
    
    curr_t = start_t
    while curr_t <= end_t:
        df_sectors, _, _ = calculate_sector_scores(year, month, day, curr_t.hour, curr_t.minute)
        time_str = curr_t.strftime("%H:%M")
        
        banking = df_sectors[df_sectors["Sector"] == "Banking / Financials"].iloc[0]["Score"]
        it = df_sectors[df_sectors["Sector"] == "IT"].iloc[0]["Score"]
        energy = df_sectors[df_sectors["Sector"] == "Energy"].iloc[0]["Score"]
        fmcg = df_sectors[df_sectors["Sector"] == "FMCG"].iloc[0]["Score"]
        
        nifty_total = (banking * 3) + (it * 2) + energy + fmcg
        
        if nifty_total >= 6: n_color = "#00CC96"
        elif nifty_total <= -6: n_color = "#EF553B"
        else: n_color = "#2b2b2b"
            
        n_hover = f"{time_str} | True Score: {nifty_total}"
        nifty_html_parts.append(f"<div style='flex: 1; background-color: {n_color}; border-right: 1px solid #111;' title='{n_hover}'></div>")
        
        for _, row in df_sectors.iterrows():
            s_name = row["Sector"]
            s_score = row["Score"]
            
            if s_score >= 2: s_color = "#00CC96"
            elif s_score <= -2: s_color = "#EF553B"
            else: s_color = "#2b2b2b"
                
            s_hover = f"{time_str} | Score: {s_score:+}"
            sector_html_parts[s_name].append(f"<div style='flex: 1; background-color: {s_color}; border-right: 1px solid #222;' title='{s_hover}'></div>")
            
        curr_t += timedelta(minutes=5)
        
    nifty_html = "<div style='display: flex; width: 100%; height: 25px; border-radius: 5px; overflow: hidden; border: 1px solid #444;'>" + "".join(nifty_html_parts) + "</div>"
    nifty_html += "<div style='display: flex; justify-content: space-between; font-size: 12px; color: #aaa; margin-top: 4px; font-weight: bold;'><span>09:15</span><span>12:15</span><span>15:30</span></div>"
    
    sector_html_dict = {}
    for s_name, parts in sector_html_parts.items():
        s_html = "<div style='display: flex; width: 100%; height: 12px; border-radius: 3px; overflow: hidden; border: 1px solid #444; margin-top: 10px;'>" + "".join(parts) + "</div>"
        sector_html_dict[s_name] = s_html
        
    return nifty_html, sector_html_dict

# ==========================================
# CIRCULAR HOROSCOPE DRAWING ENGINE
# ==========================================
def draw_circular_horoscope(year, month, day, hour, minute):
    current_lagna = get_lagna(year, month, day, hour, minute)
    planet_positions = get_planetary_positions(year, month, day, hour, minute)
    inner_offset = 30 - current_lagna

    time_markers = []
    start_t = datetime(year, month, day, 9, 15)
    end_t = datetime(year, month, day, 15, 30)
    curr_t = start_t
    while curr_t <= end_t:
        l_val = get_lagna(year, month, day, curr_t.hour, curr_t.minute)
        time_markers.append((curr_t.strftime("%H:%M"), l_val))
        curr_t += timedelta(minutes=15)
        
    moon_transitions = []
    curr_m = start_t
    prev_nl, prev_sl = get_moon_nl_sl(year, month, day, curr_m.hour, curr_m.minute)
    l_val_start = get_lagna(year, month, day, curr_m.hour, curr_m.minute)
    moon_transitions.append((l_val_start, f"{prev_nl}-{prev_sl}"))
    
    curr_m += timedelta(minutes=1)
    while curr_m <= end_t:
        curr_nl, curr_sl = get_moon_nl_sl(year, month, day, curr_m.hour, curr_m.minute)
        if curr_nl != prev_nl or curr_sl != prev_sl:
            l_val = get_lagna(year, month, day, curr_m.hour, curr_m.minute)
            moon_transitions.append((l_val, f"{curr_nl}-{curr_sl}"))
            prev_nl, prev_sl = curr_nl, curr_sl
        curr_m += timedelta(minutes=1)

    fig = plt.figure(figsize=(16, 16), dpi=150) 
    fig.patch.set_facecolor('#0e1117') 
    ax = fig.add_subplot(111, projection='polar')
    ax.set_facecolor('#0e1117')
    ax.set_theta_zero_location("N") 
    ax.set_theta_direction(1)       
    ax.axis('off')
    
    # Expand boundaries slightly to ensure the new outer numbers fit nicely
    ax.set_rmax(16.5)

    theta_circle = np.linspace(0, 2 * np.pi, 500)
    ax.plot(theta_circle, np.full_like(theta_circle, 10), color='white', lw=2, zorder=3)
    ax.plot(theta_circle, np.full_like(theta_circle, 14), color='white', lw=2, zorder=3)

    market_zones = [
        (0, "+ve stability in market", "#00CC96"), (30, "Accumulation, internal buying", "#636EFA"),
        (60, "-ve disposal / selling", "#EF553B"), (90, "+ve less up move, no down", "#00CC96"),
        (120, "Sideways no buying or selling", "gray"), (150, "-ve selling / profit booking", "#EF553B"),
        (180, "+ve uprise / partner", "#00CC96"), (210, "-ve loss / obstacle", "#EF553B"),
        (240, "+ve gain house, income house", "#00CC96"), (270, "-ve consumption of income", "#EF553B"),
        (300, "+ve big lots buying", "#00CC96"), (330, "-ve heavily -ve", "#EF553B")
    ]

    # --- Outer Labels (Fixed on screen) ---
    for angle in range(0, 360, 30):
        theta = np.radians(angle)
        ax.plot([theta, theta], [10, 14], color='white', lw=1.5, zorder=2)
        # Degree Text
        ax.text(theta, 14.5, f"{angle}°", ha='center', va='center', fontsize=14, fontweight='bold', color='white')
        
        # --- NEW: Fixed Market Zone Numbers (1 to 12) at outer edge ---
        ax.text(np.radians(angle + 15), 15.5, str((angle // 30) + 1), ha='center', va='center', fontsize=22, fontweight='bold', color='white')

    # --- Market Zone Text ---
    for start_deg, text, color in market_zones:
        center_deg = start_deg + 15
        theta = np.radians(center_deg)
        rot = center_deg
        if 90 < rot <= 270: rot += 180
        ax.text(theta, 12.0, text, ha='center', va='center', fontsize=11, fontweight='bold', color=color, rotation=rot)

    ax.plot(theta_circle, np.full_like(theta_circle, 4), color='white', lw=1.5, zorder=3)
    ax.plot(theta_circle, np.full_like(theta_circle, 7), color='white', lw=1.5, zorder=3)

    empty_rashis = []
    for rashi_idx in range(1, 13):
        start_angle = (rashi_idx - 1) * 30
        end_angle = start_angle + 30
        has_planet = any(start_angle <= data["deg"] < end_angle for data in planet_positions.values())
        if not has_planet:
            empty_rashis.append(rashi_idx) 
            ax.fill_between(np.radians(np.linspace(start_angle + inner_offset, end_angle + inner_offset, 50)), 0, 4, color='#1f2937', alpha=0.6, zorder=1)

    # --- Inner Rotating Grid & Numbers ---
    for angle in range(0, 360, 5):
        theta = np.radians(angle + inner_offset)
        if angle % 30 == 0:
            ax.plot([theta, theta], [0, 10], color='white', lw=2, zorder=2)
            # --- MOVED: Rashi Numbers (1 to 12) placed in innermost circle (radius 2.0) ---
            ax.text(np.radians(angle + 15 + inner_offset), 2.0, str((angle // 30) + 1), ha='center', va='center', fontsize=22, fontweight='bold', color='white', zorder=2)
        else:
            ax.plot([theta, theta], [0, 10], color='gray', lw=1, linestyle='--', zorder=2)
            ax.text(theta, 9.4, str(angle % 30), ha='center', va='center', fontsize=9, color='#AB63FA', fontweight='bold')

    # --- Plot Planets ---
    used_positions_inner = []
    for planet, data in planet_positions.items():
        shifted_deg = (data["deg"] + inner_offset) % 360
        theta = np.radians(shifted_deg)
        radius = 3.4 
        while any(ang_dist(shifted_deg, p_deg) < 4.0 and abs(radius - p_rad) < 0.6 for p_deg, p_rad in used_positions_inner):
            radius -= 0.65 
        used_positions_inner.append((shifted_deg, radius))
        ax.text(theta, radius, planet, ha='center', va='center', fontsize=9, fontweight='bold', color='black', bbox=dict(boxstyle="circle,pad=0.2", fc="#E2E8F0", ec="none", alpha=1.0), zorder=6)

    # --- RING 1 - Nakshatra Lords ---
    ring1_plots = {p: [] for p in planet_positions.keys()}
    for planet, data in planet_positions.items():
        nl = data["nl"]
        if planet not in ring1_plots[nl]: ring1_plots[nl].append(planet)
        if nl in ["RA", "KE"]:
            proxy_lord = RASHI_LORDS[(planet_positions[nl]["deg"] // 30) + 1]
            if planet not in ring1_plots[proxy_lord]: ring1_plots[proxy_lord].append(planet)

    for target_planet, visitors in ring1_plots.items():
        if len(visitors) == 0:
            visitors.append(target_planet)

    ring1_where_is_planet = {p: {"degrees": set(), "rashis": set()} for p in planet_positions.keys()}
    ring1_rashi_filled = {r: False for r in range(1, 13)}

    used_positions_ring1 = []
    for target_planet, visitors in ring1_plots.items():
        if not visitors: continue
        target_deg = planet_positions[target_planet]["deg"]
        shifted_deg = (target_deg + inner_offset) % 360
        theta = np.radians(shifted_deg)
        ring1_rashi_filled[(target_deg // 30) + 1] = True
        
        for visitor in visitors:
            ring1_where_is_planet[visitor]["degrees"].add(target_deg) 
            radius = 4.3 
            while any(ang_dist(shifted_deg, p_deg) < 3.5 and abs(radius - p_rad) < 0.45 for p_deg, p_rad in used_positions_ring1):
                radius += 0.45 
            used_positions_ring1.append((shifted_deg, radius))
            ax.text(theta, radius, visitor, ha='center', va='center', fontsize=7, fontweight='bold', color='#111827', bbox=dict(boxstyle="round,pad=0.1", fc="#93C5FD", ec="white", lw=0.5, alpha=0.9), zorder=6)

    rashi_governors = {r: [] for r in empty_rashis}
    for planet, data in planet_positions.items():
        nl = data["nl"]
        effective_lord = RASHI_LORDS[(planet_positions[nl]["deg"] // 30) + 1] if nl in ["RA", "KE"] else nl
        for r_owned in LORD_TO_RASHIS.get(effective_lord, []):
            if r_owned in empty_rashis and planet not in rashi_governors[r_owned]:
                rashi_governors[r_owned].append(planet)

    for rashi_idx, governors in rashi_governors.items():
        if not governors: continue
        ring1_rashi_filled[rashi_idx] = True
        for g in governors: ring1_where_is_planet[g]["rashis"].add(rashi_idx) 
        theta = np.radians(((rashi_idx - 1) * 30 + 15 + inner_offset) % 360)
        ax.text(theta, 5.5, "-".join(governors), ha='center', va='center', fontsize=11, fontweight='bold', color='white', bbox=dict(boxstyle="round,pad=0.15", fc="#3B82F6", ec="none", alpha=0.95), zorder=7)
        ax.annotate('', xy=(theta + np.radians(13.5), 5.5), xytext=(theta + np.radians(7), 5.5), arrowprops=dict(arrowstyle="-|>", color='#60A5FA', lw=2, mutation_scale=12), zorder=6)
        ax.annotate('', xy=(theta - np.radians(13.5), 5.5), xytext=(theta - np.radians(7), 5.5), arrowprops=dict(arrowstyle="-|>", color='#60A5FA', lw=2, mutation_scale=12), zorder=6)

    for r in range(1, 13):
        if not ring1_rashi_filled[r]:
            lord = RASHI_LORDS[r]
            ring1_where_is_planet.setdefault(lord, {"degrees": set(), "rashis": set()})["rashis"].add(r)
            theta = np.radians(((r - 1) * 30 + 15 + inner_offset) % 360)
            ax.text(theta, 5.5, lord, ha='center', va='center', fontsize=11, fontweight='bold', color='white', bbox=dict(boxstyle="round,pad=0.15", fc="#3B82F6", ec="none", alpha=0.95), zorder=7)
            ax.annotate('', xy=(theta + np.radians(13.5), 5.5), xytext=(theta + np.radians(7), 5.5), arrowprops=dict(arrowstyle="-|>", color='#60A5FA', lw=2, mutation_scale=12), zorder=6)
            ax.annotate('', xy=(theta - np.radians(13.5), 5.5), xytext=(theta - np.radians(7), 5.5), arrowprops=dict(arrowstyle="-|>", color='#60A5FA', lw=2, mutation_scale=12), zorder=6)

    # --- RING 2 - Sub Lords ---
    ring2_plots_radial = {}
    ring2_governors = {r: [] for r in empty_rashis}
    ring2_rashi_filled = {r: False for r in range(1, 13)}

    for planet, data in planet_positions.items():
        sl = data["sl"]
        if sl in ring1_where_is_planet:
            for deg in ring1_where_is_planet[sl]["degrees"]: ring2_plots_radial.setdefault(deg, []).append(planet)
            for r_idx in ring1_where_is_planet[sl]["rashis"]:
                if planet not in ring2_governors[r_idx]: ring2_governors[r_idx].append(planet)

    used_positions_ring2 = []
    for target_deg, visitors in ring2_plots_radial.items():
        shifted_deg = (target_deg + inner_offset) % 360
        theta = np.radians(shifted_deg)
        if visitors: ring2_rashi_filled[(target_deg // 30) + 1] = True
        for visitor in visitors:
            radius = 7.3 
            while any(ang_dist(shifted_deg, p_deg) < 3.5 and abs(radius - p_rad) < 0.45 for p_deg, p_rad in used_positions_ring2):
                radius += 0.45 
            used_positions_ring2.append((shifted_deg, radius))
            ax.text(theta, radius, visitor, ha='center', va='center', fontsize=7, fontweight='bold', color='#111827', bbox=dict(boxstyle="round,pad=0.1", fc="#FCA5A5", ec="white", lw=0.5, alpha=0.9), zorder=6)

    for rashi_idx, governors in ring2_governors.items():
        if not governors: continue
        ring2_rashi_filled[rashi_idx] = True
        theta = np.radians(((rashi_idx - 1) * 30 + 15 + inner_offset) % 360)
        ax.text(theta, 8.5, "-".join(governors), ha='center', va='center', fontsize=11, fontweight='bold', color='white', bbox=dict(boxstyle="round,pad=0.15", fc="#EF4444", ec="none", alpha=0.95), zorder=7)
        ax.annotate('', xy=(theta + np.radians(13.5), 8.5), xytext=(theta + np.radians(7), 8.5), arrowprops=dict(arrowstyle="-|>", color='#F87171', lw=2, mutation_scale=12), zorder=6)
        ax.annotate('', xy=(theta - np.radians(13.5), 8.5), xytext=(theta - np.radians(7), 8.5), arrowprops=dict(arrowstyle="-|>", color='#F87171', lw=2, mutation_scale=12), zorder=6)

    for r in range(1, 13):
        if not ring2_rashi_filled[r]:
            t_start = np.radians(((r - 1) * 30 + inner_offset) % 360)
            t_end = np.radians((r * 30 + inner_offset) % 360)
            ax.plot([t_start, t_end], [7, 10], color='#EF4444', lw=2, alpha=0.4, zorder=3)
            ax.plot([t_start, t_end], [10, 7], color='#EF4444', lw=2, alpha=0.4, zorder=3)

    # --- Draw Time Markers ---
    for t_str, l_val in time_markers:
        theta = np.radians((l_val + inner_offset) % 360)
        ax.plot([theta, theta], [10, 14], color='gray', lw=1.5, linestyle=':', zorder=4)
        rot_deg = (l_val + inner_offset) % 360
        if 90 < rot_deg <= 270: rot_deg += 180
        
        is_current = (t_str == f"{hour:02d}:{minute:02d}")
        f_size = 9 if is_current else 6
        color = '#00CC96' if is_current else 'gray'
        ax.text(theta, 13.0, f"L-{t_str}", ha='center', va='center', rotation=rot_deg, fontsize=f_size, fontweight='bold', color=color, bbox=dict(boxstyle="round,pad=0.15", fc="#1f2937", ec="none", alpha=0.9), zorder=5)

    # --- Draw Minute-by-Minute Moon Transition Text ---
    for l_val, transition_text in moon_transitions:
        theta = np.radians((l_val + inner_offset) % 360)
        ax.plot([theta, theta], [10, 14], color='#F59E0B', lw=2, linestyle='--', zorder=4)
        rot_deg = (l_val + inner_offset) % 360
        if 90 < rot_deg <= 270: rot_deg += 180
        ax.text(theta, 13.6, transition_text, ha='center', va='center', rotation=rot_deg, fontsize=8, fontweight='bold', color='#111827', bbox=dict(boxstyle="square,pad=0.1", fc="#F59E0B", ec="none", alpha=0.9), zorder=5)

    plt.tight_layout()
    return fig

# ==========================================
# STREAMLIT UI (LAYOUT & DASHBOARD)
# ==========================================
default_date, default_time = get_current_ist_rounded()

if "time_slider" not in st.session_state:
    st.session_state.time_slider = default_time

def reset_time_on_date_change():
    st.session_state.time_slider = time(9, 15)

st.title("Financial Astrolabe - Master Edition")
tithi_banner_placeholder = st.empty()

ctrl_col1, ctrl_col2 = st.columns([1, 3])

with ctrl_col1:
    selected_date = st.date_input("Select Date", default_date, on_change=reset_time_on_date_change)
    
with ctrl_col2:
    with st.spinner("Pre-calculating Nakshatra filters..."):
        nifty_trend_html, sector_trend_htmls = generate_all_trends_html(selected_date.year, selected_date.month, selected_date.day)
        st.markdown(nifty_trend_html, unsafe_allow_html=True)
    
    selected_time = st.slider(
        "⏳ Slide to Rotate Time",
        min_value=time(9, 15),
        max_value=time(15, 30),
        value=st.session_state.time_slider,
        step=timedelta(minutes=5),
        format="HH:mm",
        key="time_slider",
        label_visibility="collapsed"
    )

st.divider()

tithi_message = get_tithi_info(selected_date.year, selected_date.month, selected_date.day, 9, 15)
tithi_banner_placeholder.markdown(
    f"<div style='padding: 10px; border-radius: 5px; background-color: #2D3748; text-align: center; border: 1px solid #4A5568; margin-bottom: 20px;'>"
    f"<h4 style='color: #E2E8F0; margin: 0;'>🌌 Daily Cosmic Environment: {tithi_message}</h4>"
    f"</div>", 
    unsafe_allow_html=True
)

col_left, col_right = st.columns([6, 4], gap="large")

with col_left:
    st.subheader(f"Astrolabe Mapping at {selected_time.strftime('%H:%M')}")
    with st.spinner("Calculating Ephemeris..."):
        fig = draw_circular_horoscope(
            selected_date.year, selected_date.month, selected_date.day, 
            selected_time.hour, selected_time.minute
        )
        st.pyplot(fig, use_container_width=True)
        
    if selected_time >= time(15, 15):
        st.markdown("---")
        st.markdown("### 🌙 BTST Astro-Gap Predictor (15:15 Trigger)")
        jd_close = get_jd(selected_date.year, selected_date.month, selected_date.day, 15, 15)
        moon_close = swe.calc_ut(jd_close, swe.MOON)[0][0]
        sun_close = swe.calc_ut(jd_close, swe.SUN)[0][0]
        
        if moon_close > sun_close:
            st.success("**GAP UP EXPECTED**\nThe Moon's longitudinal dominance over the Sun at market close favors positive overnight sentiment.")
        else:
            st.error("**GAP DOWN EXPECTED**\nThe Sun's dominance over the Moon at market close suggests overnight pressure / Gap Down.")

with col_right:
    df_sectors, planet_positions, current_lagna = calculate_sector_scores(
        selected_date.year, selected_date.month, selected_date.day, 
        selected_time.hour, selected_time.minute
    )
    
    st.subheader("Intraday Live Scoring")
    
    malefics = ["SA", "MA", "RA"]
    warnings = []
    for m in malefics:
        dist = ang_dist(current_lagna, planet_positions[m]["deg"])
        if abs(dist - 150) < 3 or abs(dist - 210) < 3:
            warnings.append(f"⚠️ **6/8 Shadastak Alert:** Lagna is severely afflicted by {m}. High risk of sudden intraday reversal or heavy profit booking right now.")
        elif abs(dist - 90) < 3:
            warnings.append(f"⚠️ **4/10 Square Alert:** Lagna is squaring {m}. Expect friction and sudden volatility spikes.")
            
    if warnings:
        for w in warnings:
            st.warning(w)
            
    banking_score = df_sectors[df_sectors["Sector"] == "Banking / Financials"].iloc[0]["Score"]
    it_score = df_sectors[df_sectors["Sector"] == "IT"].iloc[0]["Score"]
    energy_score = df_sectors[df_sectors["Sector"] == "Energy"].iloc[0]["Score"]
    fmcg_score = df_sectors[df_sectors["Sector"] == "FMCG"].iloc[0]["Score"]
    
    nifty_total = (banking_score * 3) + (it_score * 2) + energy_score + fmcg_score
    
    st.markdown("### NIFTY 50 Directional Bias (True Strength)")
    if nifty_total >= 6:
        st.success(f"📈 **POWERFUL BULLISH (+)**\n\nNIFTY True Score: **{nifty_total}**\n\nHeavyweights AND their Star Lords are aligned in positive zones.")
    elif nifty_total <= -6:
        st.error(f"📉 **POWERFUL BEARISH (-)**\n\nNIFTY True Score: **{nifty_total}**\n\nHeavyweights AND their Star Lords are aligned in disposal zones.")
    elif nifty_total > 0:
        st.info(f"↗️ **SLIGHT BULLISH / SIDEWAYS**\n\nNIFTY True Score: **{nifty_total}**\n\nMixed Star Lord support. Watch technical breakouts.")
    elif nifty_total < 0:
        st.warning(f"↘️ **SLIGHT BEARISH / SIDEWAYS**\n\nNIFTY True Score: **{nifty_total}**\n\nMixed Star Lord support. Watch technical breakdowns.")
    else:
        st.warning(f"⚖️ **CHOPPY / NEUTRAL**\n\nNIFTY True Score: **0**\n\nPlanets and Star Lords are completely contradicting each other. Avoid Index trading.")
    
    st.divider()
    
    st.markdown("### Individual Sector True Scores")
    st.caption("Score incorporates Planet Zone + Nakshatra Lord Zone. ±2 required for strong conviction.")
    
    grid_cols = st.columns(2)
    for index, row in df_sectors.iterrows():
        col = grid_cols[index % 2]
        sector_name = row['Sector']
        with col:
            st.markdown(
                f"<div style='padding: 10px; border-radius: 5px; background-color: #1f2937; margin-bottom: 10px; border-left: 5px solid {row['Color']}'>"
                f"<strong style='color: white; font-size: 16px;'>{sector_name}</strong><br>"
                f"<span style='color: {row['Color']}; font-weight: bold;'>True Score: {row['Score']:+d} ({row['Sentiment']})</span>"
                f"{sector_trend_htmls[sector_name]}"
                f"</div>", 
                unsafe_allow_html=True
            )
