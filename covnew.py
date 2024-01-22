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
    covered_targets_df = pd.DataFrame()
    missing_targets = []

    # Adjusting the ASIN values in the dataframe and converting to lowercase for comparison
    df['ASIN_Compare'] = df['ASIN'].apply(lambda x: ''.join(filter(str.isalnum, x))[:10].lower())
    df['Target_Compare'] = df['Target'].str.lower()

    # Processing user input for case-insensitivity
    processed_asin_targets_dict = {k.lower(): [t.lower() for t in v] for k, v in asin_targets_dict.items()}

    for asin, targets in processed_asin_targets_dict.items():
        for target in targets:
            for match_type in ['exact', 'broad', 'phrase']:
                processed_asin = ''.join(filter(str.isalnum, asin))[:10]
                match_condition = ((df['ASIN_Compare'] == processed_asin) & (df['Target_Compare'] == target) & (df['Match Type'] == match_type))
                if match_condition.any():
                    # Add rows that meet the condition to the covered_targets_df
                    covered_rows = df[match_condition]
                    covered_rows['Match Type'] = match_type  # Add Match Type
                    # Compute Funnel Segment and add to covered_rows
                    covered_rows['Funnel Segment'] = covered_rows['Target'].apply(lambda x: assign_funnel_segment(x, df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std()))
                    covered_targets_df = pd.concat([covered_targets_df, covered_rows], ignore_index=True)
                else:
                    funnel_segment = assign_funnel_segment(target, df['Target'].str.split().str.len().mean(), df['Target'].str.split().str.len().std())
                    missing_targets.append({'ASIN': processed_asin, 'Target': target, 'Match Type': match_type, 'Funnel Segment': funnel_segment})

    # Remove the comparison columns
    covered_targets_df.drop(['ASIN_Compare', 'Target_Compare'], axis=1, inplace=True)

    missing_df = pd.DataFrame(missing_targets)
    return covered_targets_df, missing_df


# Function to download DataFrame as Excel
def download_df_as_excel(df, filename):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    st.download_button(label=f"Download {filename}", data=processed_data, file_name=filename, mime="application/vnd.ms-excel")

def plot_bar_chart(df, asin, asin_targets_dict):
    asin_processed = asin.lower()

    # Filter DataFrame for the specific ASIN
    df_filtered = df[df['ASIN'].str.lower() == asin_processed]

    if df_filtered.empty:
        st.error(f"No coverage data found for ASIN {asin}.")
        return

    # Debugging: Check if the necessary columns are present and have the correct data type
    if not all(column in df_filtered.columns for column in ['Funnel Segment', 'Match Type']):
        st.error("Required columns for plotting are missing.")
        return

    # Check if the 'Funnel Segment' column has the expected segments
    if not set(['Short', 'Mid', 'Long']).issubset(df_filtered['Funnel Segment'].unique()):
        st.error("Invalid funnel segments data.")
        return

    # Calculate coverage data
    coverage_data = df_filtered.groupby(['Funnel Segment', 'Match Type']).size().unstack(fill_value=0)

    # Debugging: Print coverage_data to see its structure
    print("Coverage Data:", coverage_data)

    # Calculating coverage percentages
    coverage_percentage = coverage_data.divide(coverage_data.sum(axis=1), axis=0) * 100

    # Plotting
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
