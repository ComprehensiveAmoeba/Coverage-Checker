import streamlit as st
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt

# Function to determine match type
def determine_match_type(campaign_name):
    if campaign_name.startswith("OW_"):
        return "exact"
    elif campaign_name.startswith("BR_"):
        return "broad"
    elif campaign_name.startswith("PH_"):
        return "phrase"
    return "other"

# Function to assign funnel segment
def assign_funnel_segment(target, avg_word_count, std_dev):
    word_count = len(target.split())
    if word_count < avg_word_count - std_dev:
        return "Short"
    elif avg_word_count - std_dev <= word_count <= avg_word_count + std_dev:
        return "Mid"
    else:
        return "Long"

# Function to process uploaded file
def process_file(uploaded_file):
    df = pd.read_excel(uploaded_file)
    df['Match Type'] = df['Campaign Name'].apply(determine_match_type)
    df = df[df['Match Type'] != 'other']

    target_word_counts = df['Target'].apply(lambda x: len(x.split()))
    avg_word_count = target_word_counts.mean()
    std_dev = target_word_counts.std()

    df['Funnel Segment'] = df['Target'].apply(lambda x: assign_funnel_segment(x, avg_word_count, std_dev))
    return df

# Function to analyze coverage
def analyze_coverage(df, asin_targets_dict):
    covered_targets = []
    missing_targets = []

    # Adjusting the ASIN values in the dataframe and converting to lowercase
    df['ASIN'] = df['ASIN'].apply(lambda x: ''.join(filter(str.isalnum, x))[:10].lower())
    df['Target'] = df['Target'].str.lower()

    # Processing user input for case-insensitivity
    processed_asin_targets_dict = {k.lower(): [t.lower() for t in v] for k, v in asin_targets_dict.items()}

    for asin, targets in processed_asin_targets_dict.items():
        for target in targets:
            for match_type in ['exact', 'broad', 'phrase']:
                processed_asin = ''.join(filter(str.isalnum, asin))[:10]
                if ((df['ASIN'] == processed_asin) & (df['Target'] == target) & (df['Match Type'] == match_type)).any():
                    covered_targets.append({'ASIN': asin, 'Target': target, 'Match Type': match_type})  # Keeping original ASIN
                else:
                    funnel_segment = assign_funnel_segment(target, df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std())
                    missing_targets.append({'ASIN': processed_asin, 'Target': target, 'Match Type': match_type, 'Funnel Segment': funnel_segment})

    covered_df = pd.DataFrame(covered_targets)
    missing_df = pd.DataFrame(missing_targets)
    return covered_df, missing_df

# Function to download DataFrame as Excel
def download_df_as_excel(df, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    st.download_button(label=f"Download {filename}", data=processed_data, file_name=filename, mime="application/vnd.ms-excel")

# Function to plot bar chart
def plot_bar_chart(df, asin, asin_targets_dict):
    df = df[df['ASIN'] == asin.lower()]
    total_targets_per_funnel = {funnel: len([t for t in asin_targets_dict[asin] if assign_funnel_segment(t.lower(), df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std()) == funnel]) for funnel in ['Low', 'Mid', 'Top']}

    coverage_data = df.groupby(['Funnel Segment', 'Match Type']).size().unstack(fill_value=0)
    coverage_percentage = coverage_data.divide(coverage_data.sum(axis=1), axis=0) * 100

    # Adjust for total targets per funnel
    coverage_percentage = coverage_percentage.divide(pd.Series(total_targets_per_funnel), axis=0)

    coverage_percentage.plot(kind='bar', stacked=True)
    plt.xlabel("Funnel Segment")
    plt.ylabel("Coverage Percentage")
    plt.title(f"Coverage Analysis for ASIN {asin}")
    st.pyplot(plt)

# Main app
def main():
    st.set_page_config(page_title='SP Coverage Checker', page_icon='https://thrassvent.de/wp-content/uploads/2024/01/5.png')

    st.title("SP Coverage Checker")

    with st.sidebar:
        st.image('https://thrassvent.de/wp-content/uploads/2024/01/5.png', width=200)
        st.header("Input ASINs and Targets")
        asin_targets_dict = {}
        asin_input = st.text_area("Enter ASINs (one per line)")
        if asin_input:
            for asin in asin_input.split('\n'):
                asin = asin.strip()
                if asin:  # Check if the ASIN is not empty
                    targets_input = st.text_area(f"Enter Targets for ASIN {asin} (one per line)")
                    if targets_input:
                        asin_targets_dict[asin] = targets_input.split('\n')

    uploaded_file = st.file_uploader("Upload a BMT output", type=["xlsx"])

    if uploaded_file:
        try:
            df = process_file(uploaded_file)
            st.success("File processed successfully!")

            covered_df, missing_df = analyze_coverage(df, asin_targets_dict)

            st.subheader("Coverage Analysis")
            for asin in asin_targets_dict.keys():
                st.markdown(f"### ASIN: {asin}")
                plot_bar_chart(df, asin, asin_targets_dict)

            st.subheader("Download Reports")
            if not covered_df.empty:
                download_df_as_excel(covered_df, "covered_targets.xlsx")
            if not missing_df.empty:
                download_df_as_excel(missing_df, "missing_targets.xlsx")
        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
