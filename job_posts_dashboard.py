import streamlit as st
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

# Set page config
st.set_page_config(
    page_title="LinkedIn Job Posts Dashboard",
    page_icon="📊",
    layout="wide"
)

def load_job_data() -> List[Dict[str, Any]]:
    """Load all job data from JSON files in linked_job_posts directory."""
    job_posts_dir = Path("linked_job_posts")
    job_data = []

    if not job_posts_dir.exists():
        st.error(f"Directory 'linked_job_posts' not found!")
        return []

    # Find all JSON files
    json_files = list(job_posts_dir.glob("*.json"))

    if not json_files:
        st.warning("No job data files found in linked_job_posts directory!")
        return []

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Add filename for reference (optional)
            data['filename'] = json_file.name
            job_data.append(data)

        except Exception as e:
            st.error(f"Error loading {json_file}: {e}")

    return job_data


def main():
    st.title("📊 LinkedIn Job Posts Dashboard")
    st.markdown("---")

    # Load job data
    with st.spinner("Loading job data..."):
        job_data = load_job_data()

    if not job_data:
        st.info("No job data available. Please run the job extraction workflow first.")
        return

    st.success(f"Loaded {len(job_data)} job postings")

    # Convert to DataFrame for better table display
    df = pd.DataFrame(job_data)

    # Select and reorder columns for display
    display_columns = [
        'jobId', 'job_name', 'original_job_title', 'location', 'job_status',
        'posted_when', 'amount_spent', 'views', 'apply_clicks', 'apply_url'
    ]

    # Filter to only columns that exist in the data
    available_columns = [col for col in display_columns if col in df.columns]

    # Reorder columns with apply_url last
    final_columns = [col for col in available_columns if col != 'apply_url']
    if 'apply_url' in available_columns:
        final_columns.append('apply_url')

    df_display = df[final_columns].copy()

    # Format the apply_url column to be clickable HTML links
    if 'apply_url' in df_display.columns:
        df_display['apply_url'] = df_display['apply_url'].apply(
            lambda url: f'<a href="{url}" target="_blank" style="color: #007bff; text-decoration: none;">Apply Url</a>' if url else ''
        )

    # Rename columns for better display
    column_rename_map = {
        'jobId': 'Job ID',
        'job_name': 'Job Name',
        'original_job_title': 'Original Title',
        'location': 'Location',
        'job_status': 'Status',
        'posted_when': 'Posted',
        'amount_spent': 'Amount Spent',
        'views': 'Views',
        'apply_clicks': 'Apply Clicks',
        'apply_url': 'Apply Url'
    }

    df_display = df_display.rename(columns=column_rename_map)

    # Display the table
    st.subheader("📋 Job Postings Summary")

    # Convert dataframe to HTML for clickable links
    if not df_display.empty:
        # Convert to HTML table with markdown rendering support
        html_table = df_display.to_html(
            index=False,
            escape=False,  # Allow HTML/markdown in cells
            table_id="job-posts-table",
            bold_rows=False
        )

        # Add some custom CSS styling
        st.markdown("""
        <style>
        #job-posts-table {
            width: 100%;
            border-collapse: collapse;
        }
        #job-posts-table th {
            background-color: #f8f9fa;
            color: #212529;
            padding: 12px;
            text-align: left;
            border-bottom: 2px solid #dee2e6;
            font-weight: bold;
        }
        #job-posts-table td {
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
            vertical-align: top;
        }
        #job-posts-table a {
            color: #007bff;
            text-decoration: none;
        }
        #job-posts-table a:hover {
            text-decoration: underline;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown(html_table, unsafe_allow_html=True)
    else:
        st.info("No job data available to display.")

    # Add summary statistics
    st.markdown("---")
    st.subheader("📈 Summary Statistics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_jobs = len(job_data)
        st.metric("Total Jobs", total_jobs)

    with col2:
        active_jobs = len([job for job in job_data if job.get('job_status') == 'Active'])
        st.metric("Active Jobs", active_jobs)

    with col3:
        total_views = sum(int(job.get('views', '0').split()[0]) for job in job_data if job.get('views'))
        st.metric("Total Views", total_views)

    with col4:
        total_applies = sum(int(job.get('apply_clicks', '0').split()[0]) for job in job_data if job.get('apply_clicks'))
        st.metric("Total Apply Clicks", total_applies)

    # Show detailed view toggle
    st.markdown("---")
    if st.checkbox("Show Detailed JSON Data", value=False):
        st.subheader("🔍 Detailed Job Data")

        selected_job = st.selectbox(
            "Select a job to view details:",
            options=[f"{job.get('jobId', 'Unknown')} - {job.get('job_name', 'Unknown')}" for job in job_data],
            index=0 if job_data else None
        )

        if selected_job:
            # Extract job ID from selection
            job_id = selected_job.split(' - ')[0]

            # Find the matching job data
            selected_job_data = next((job for job in job_data if job.get('jobId') == job_id), None)

            if selected_job_data:
                st.json(selected_job_data)
            else:
                st.error("Job data not found")

if __name__ == "__main__":
    main()