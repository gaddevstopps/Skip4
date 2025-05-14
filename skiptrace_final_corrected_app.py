
import streamlit as st
import pandas as pd
import requests
from difflib import get_close_matches
import io

st.set_page_config(page_title="📦 Skiptrace Preprocessor")

st.title("📦 Final Skiptrace Preprocessor + Apify Trigger")
st.write("Upload property CSVs. We'll extract and clean first/last name and full mailing address, then send to your Apify actor.")

uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

def fuzzy_find(possible_names, column_names):
    for name in possible_names:
        matches = get_close_matches(name.upper(), column_names, n=1, cutoff=0.6)
        if matches:
            return matches[0]
    return None

def call_apify_actor(csv_bytes):
    token = st.secrets["apify"]["token"]
    actor_id = st.secrets["apify"]["actor_id"]
    run_url = f"https://api.apify.com/v2/actors/{actor_id}/runs"

    files = {
        'input': ('Cleaned_For_SkipTrace.csv', csv_bytes, 'text/csv')
    }
    params = {
        "token": token,
        "build": "latest",
        "timeout": 300
    }

    with st.spinner("📤 Sending to Apify actor..."):
        response = requests.post(run_url, files=files, params=params)

    if response.status_code == 201:
        run_data = response.json()
        status_url = run_data["data"]["statusUrl"]
        st.success("✅ Actor triggered successfully!")
        st.markdown(f"[🔍 View run status on Apify]({status_url})")
    else:
        st.error(f"❌ Failed to trigger actor: {response.text}")

if uploaded_file:
    st.success(f"File uploaded: {uploaded_file.name}")

    try:
        df = pd.read_csv(uploaded_file)
        original_columns = df.columns.str.upper().tolist()

        # Smart field matching
        first_name_field = fuzzy_find(['OWNER 1 FIRST NAME', 'FIRST NAME'], original_columns)
        last_name_field = fuzzy_find(['OWNER 1 LAST NAME', 'LAST NAME'], original_columns)
        house_field = fuzzy_find(['MAIL HOUSE NUMBER', 'HOUSE NUMBER'], original_columns)
        street_field = fuzzy_find(['MAIL STREET NAME', 'STREET NAME'], original_columns)
        suffix_field = fuzzy_find(['MAIL STREET NAME SUFFIX', 'SUFFIX'], original_columns)
        unit_field = fuzzy_find(['MAIL UNIT NUMBER', 'UNIT', 'APT', 'SUITE'], original_columns)
        city_field = fuzzy_find(['MAIL CITY', 'CITY'], original_columns)
        state_field = fuzzy_find(['MAIL STATE', 'STATE'], original_columns)
        zip_field = fuzzy_find(['MAIL ZIP/ZIP+4', 'ZIP'], original_columns)

        required = [first_name_field, last_name_field, house_field, street_field, city_field, state_field, zip_field]
        if not all(required):
            st.error("❌ Missing required fields: first name, last name, street, city, state, or ZIP.")
        else:
            df.columns = df.columns.str.upper()

            # Build MAILING ADDRESS LINE 1
            address_line = (
                df[house_field].fillna('').astype(str).str.strip() + ' ' +
                df[street_field].fillna('').astype(str).str.strip()
            )
            if suffix_field:
                address_line += ' ' + df[suffix_field].fillna('').astype(str).str.strip()
            if unit_field:
                address_line += ' ' + df[unit_field].fillna('').astype(str).str.strip()
            address_line = address_line.str.replace(r'\s+', ' ', regex=True).str.strip()

            # Combine into full address
            full_address = (
                address_line + ', ' +
                df[city_field].fillna('').astype(str).str.strip() + ', ' +
                df[state_field].fillna('').astype(str).str.strip() + ' ' +
                df[zip_field].fillna('').astype(str).str.strip()
            ).str.replace(r'\s+', ' ', regex=True).str.strip()

            # Format cleaned first + last name
            full_name = (
                df[first_name_field].fillna('').astype(str).str.strip() + ' ' +
                df[last_name_field].fillna('').astype(str).str.strip()
            ).str.replace(r'\s+', ' ', regex=True).str.strip()

            output_df = pd.DataFrame({
                'OWNER NAME': full_name,
                'MAILING ADDRESS': full_address
            })

            st.write("✅ Final cleaned preview:")
            st.dataframe(output_df.head(10))

            csv_bytes = output_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Cleaned CSV", data=csv_bytes, file_name="Cleaned_For_SkipTrace.csv", mime="text/csv")

            if st.button("🚀 Send to Apify Skip Tracer Actor"):
                call_apify_actor(csv_bytes)

    except Exception as e:
        st.error(f"❌ Error processing file: {e}")
