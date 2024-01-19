# Coverage-Checker
Streamlit app designed to check coverage

### Using the App

1. **Input ASINs and Targets**:
 - In the sidebar, there's a section to enter ASINs and their associated targets.
 - Enter each ASIN on a new line.
 - For each ASIN entered, a new text area appears below it where you can enter the target keywords, one per line.

2. **Upload an Excel File**:
 - The file should contain your campaign data including the ASINs, Campaign Names, and Targets.
 - The app will process this file to match it with the input ASINs and targets.

3. **Analysis and Visualization**:
 - After uploading the file, the app processes it and displays a coverage analysis for each ASIN.
 - The coverage is shown in bar charts, indicating the percentage coverage for each funnel segment.
 - The charts include a breakdown of the match types contributing to the coverage.

4. **Download Reports**:
 - You can download two types of reports: 'Covered Targets' and 'Missing Targets'.
 - These reports are downloadable as Excel files and provide detailed insights into the coverage analysis.

## Notes

- The comparison of ASINs and targets is case-insensitive.
- The first 10 alphanumeric characters of the ASINs in the uploaded file are considered for analysis.
- The coverage percentage in the visuals is relative to the total entered targets for each ASIN-Funnel, not duplicating targets found in multiple match types.

## Requirements

- Python 3.x
- Streamlit
- Pandas
- Openpyxl
- Matplotlib

---

Developed with streamlit ❤️ and ☕ by Comprehensive Amoeba ;D
