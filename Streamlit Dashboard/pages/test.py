import streamlit as st

st.set_page_config(page_title="Temperature Zones", layout="centered")

st.markdown("### 🌡️ Temperature Zones")

# Example values (replace with your own dynamic ones)
present_value = 220
set_value = 285

# Calculate percentage difference
diff = (set_value - present_value) / set_value * 100

# Choose bar color
if diff <= 5:
    color = "#00c853"   # green
elif diff <= 10:
    color = "#ffd600"   # yellow
else:
    color = "#d50000"   # red

# Percentage of bar to fill
percent = present_value / set_value
percent = max(0, min(percent, 1))

# Styled progress bar using HTML/CSS
st.markdown(
    f"""
    <div style="background-color:#1e293b;padding:20px;border-radius:10px;">
        <div style="color:white;font-size:18px;margin-bottom:8px;">
            Preform Zone 1 
            <span style="float:right;">{present_value}°C / {set_value}°C</span>
        </div>
        <div style="background-color:#0f172a;border-radius:10px;height:12px;">
            <div style="width:{percent*100}%;background:{color};
                        height:12px;border-radius:10px;"></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
