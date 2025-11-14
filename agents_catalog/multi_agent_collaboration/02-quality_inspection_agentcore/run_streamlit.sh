#!/bin/bash

# Quality Inspection Streamlit App Runner
echo "Starting Quality Inspection Streamlit App..."

# Install dependencies if needed
pip install -r src/requirements.txt

# Run the Streamlit app
streamlit run src/demo_app/quality-inspection-streamlit-demo.py