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
    elif campaign_name.startswith("OP_"):
        return "product"
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

    df['Funnel Segment'] = df.apply(lambda x: assign_funnel_segment(x['Target'], avg_word_count, std_dev) if x['Match Type'] != 'product' else '', axis=1)
    return df

# Function to analyze coverage
def analyze_coverage(df, asin_targets_dict, bulk_sheet_df=None):
    covered_targets_df = pd.DataFrame()
    missing_targets = []

    # Adjusting the ASIN values in the dataframe and converting to lowercase for comparison
    df['ASIN_Compare'] = df['ASIN'].apply(lambda x: ''.join(filter(str.isalnum, x))[:10].lower())
    df['Target_Compare'] = df['Target'].str.lower()

    # Processing user input for case-insensitivity
    processed_asin_targets_dict = {k.lower(): [t.lower() for t in v] for k, v in asin_targets_dict.items()}

    for asin, targets in processed_asin_targets_dict.items():
        for target in targets:
            processed_asin = ''.join(filter(str.isalnum, asin))[:10].lower()
            if target.startswith("b0"):
                match_type = 'product'
                match_condition = ((df['ASIN_Compare'] == processed_asin) & (df['Target_Compare'] == target) & (df['Match Type'] == match_type))
                if match_condition.any():
                    covered_rows = df[match_condition]
                    covered_targets_df = pd.concat([covered_targets_df, covered_rows], ignore_index=True)
                else:
                    missing_targets.append({'ASIN': processed_asin, 'Target': target, 'Match Type': match_type, 'Funnel Segment': ''})
            else:
                for match_type in ['exact', 'broad', 'phrase']:
                    match_condition = ((df['ASIN_Compare'] == processed_asin) & (df['Target_Compare'] == target) & (df['Match Type'] == match_type))
                    if match_condition.any():
                        covered_rows = df[match_condition]
                        covered_rows['Match Type'] = match_type
                        covered_rows['Funnel Segment'] = covered_rows['Target'].apply(lambda x: assign_funnel_segment(x, df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std()))
                        covered_targets_df = pd.concat([covered_targets_df, covered_rows], ignore_index=True)
                    else:
                        funnel_segment = assign_funnel_segment(target, df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std())
                        missing_targets.append({'ASIN': processed_asin, 'Target': target, 'Match Type': match_type, 'Funnel Segment': funnel_segment})

    covered_targets_df.drop(['ASIN_Compare', 'Target_Compare'], axis=1, inplace=True)

    if bulk_sheet_df is not None:
        covered_targets_df = add_effective_bid(covered_targets_df, bulk_sheet_df)

    missing_df = pd.DataFrame(missing_targets)
    return covered_targets_df, missing_df

# Function to add effective bid columns
def add_effective_bid(covered_targets_df, bulk_sheet_df):
    bulk_sheet_df = bulk_sheet_df[bulk_sheet_df['Entity'] == 'Bidding Adjustment']
    bulk_sheet_df['Campaign Name'] = bulk_sheet_df['Campaign Name (Informational only)']

    # Group by Campaign Name and find the maximum percentage
    max_placement = bulk_sheet_df.groupby('Campaign Name')['Percentage'].max().reset_index()

    # Merge to get all placements with the maximum percentage
    max_placement_df = pd.merge(bulk_sheet_df, max_placement, on=['Campaign Name', 'Percentage'])

    # Aggregate placements into a comma-separated string for each campaign
    max_placement_df = max_placement_df.groupby('Campaign Name').agg({
        'Placement': lambda x: ', '.join(x),
        'Percentage': 'max'
    }).reset_index()
    max_placement_df.columns = ['Campaign Name', 'maximum placement', 'maximum percentage']

    covered_targets_df = covered_targets_df.merge(max_placement_df, on='Campaign Name', how='left')

    covered_targets_df['effective bid'] = covered_targets_df['Current Bid'] * (1 + (covered_targets_df['maximum percentage'] / 100))
    return covered_targets_df


# Function to download DataFrame as Excel
def download_df_as_excel(df, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    st.download_button(label=f"Download {filename}", data=processed_data, file_name=filename, mime="application/vnd.ms-excel")

def plot_bar_chart(df, asin, asin_targets_dict):
    asin_processed = asin.lower()

    df_filtered = df[df['ASIN'].str.lower() == asin_processed]

    if df_filtered.empty:
        st.error(f"No coverage data found for ASIN {asin}.")
        return

    if not all(column in df_filtered.columns for column in ['Funnel Segment', 'Match Type']):
        st.error("Required columns for plotting are missing.")
        return

    if not set(['Short', 'Mid', 'Long']).issubset(df_filtered['Funnel Segment'].unique()):
        st.error("Invalid funnel segments data.")
        return

    coverage_data = df_filtered.groupby(['Funnel Segment', 'Match Type']).size().unstack(fill_value=0)

    coverage_percentage = coverage_data.divide(coverage_data.sum(axis=1), axis=0) * 100

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
                if asin:
                    targets_input = st.text_area(f"Enter Targets for ASIN {asin} (one per line)")
                    if targets_input:
                        asin_targets_dict[asin] = targets_input.split('\n')

        add_effective_bid_option = st.checkbox("Add effective bid")
        bulk_sheet_file = None
        if add_effective_bid_option:
            bulk_sheet_file = st.file_uploader("Upload a bulk sheet (including campaigns with zero impressions and placement data)", type=["xlsx"])

    uploaded_file = st.file_uploader("Upload a BMT output", type=["xlsx"])

    if uploaded_file:
        try:
            df = process_file(uploaded_file)
            st.success("File processed successfully!")

            bulk_sheet_df = None
            if add_effective_bid_option and bulk_sheet_file:
                bulk_sheet_df = pd.read_excel(bulk_sheet_file, sheet_name=None)
                bulk_sheet_df = pd.concat([bulk_sheet_df[sheet] for sheet in bulk_sheet_df if 'Sponsored Products Campaigns' in sheet])

            covered_df, missing_df = analyze_coverage(df, asin_targets_dict, bulk_sheet_df)

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
