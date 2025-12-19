#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) file operations module.
Handles reading and writing configuration files.
"""

import os
import json
import csv
from typing import Tuple, Optional


class SFCFileOperations:
    """Handles file operations for SFC configurations"""

    @staticmethod
    def read_config_from_file(filename: str) -> str:
        """Read configuration from a JSON file

        Args:
            filename: Name of the file to read the configuration from

        Returns:
            String result message with the loaded configuration
        """
        try:
            # Add file extension if not provided
            if not filename.lower().endswith(".json"):
                filename += ".json"

            # Check if file exists
            if not os.path.exists(filename):
                return f"❌ File not found: '{filename}'"

            # Read from file
            with open(filename, "r") as file:
                config = json.load(file)

            # Convert back to JSON string with proper indentation
            config_json = json.dumps(config, indent=2)

            return f"✅ Configuration loaded successfully from '{filename}':\n\n```json\n{config_json}\n```"
        except json.JSONDecodeError:
            return f"❌ Invalid JSON format in file: '{filename}'"
        except Exception as e:
            return f"❌ Error reading configuration: {str(e)}"

    @staticmethod
    def save_config_to_file(config_json: str, filename: str) -> str:
        """Save configuration to a JSON file

        Args:
            config_json: SFC configuration to save
            filename: Name of the file to save the configuration to

        Returns:
            String result message indicating success or failure
        """
        try:
            # Parse the JSON to ensure it's valid
            config = json.loads(config_json)

            # Add file extension if not provided
            if not filename.lower().endswith(".json"):
                filename += ".json"

            # Create the stored_configs directory if it doesn't exist
            storage_dir = ".sfc/stored_configs"
            os.makedirs(storage_dir, exist_ok=True)

            # Create the full path
            full_path = os.path.join(storage_dir, os.path.basename(filename))

            # Write to file
            with open(full_path, "w") as file:
                json.dump(config, file, indent=2)

            return f"✅ Configuration saved successfully to '{full_path}'"
        except json.JSONDecodeError:
            return "❌ Invalid JSON configuration provided"
        except Exception as e:
            return f"❌ Error saving configuration: {str(e)}"

    @staticmethod
    def save_results_to_file(
        content: str, filename: str, current_config_name: str = None
    ) -> str:
        """Save content to a file with specified extension

        Args:
            content: Content to save to the file
            filename: Name of the file to save the content to
            current_config_name: Current config run name (optional)

        Returns:
            String result message indicating success or failure
        """
        try:
            # List of allowed file extensions
            allowed_extensions = ["txt", "vm", "md"]
            default_extension = "txt"

            # Check if filename has an extension
            has_extension = False
            for ext in allowed_extensions:
                if filename.lower().endswith(f".{ext}"):
                    has_extension = True
                    break

            # Add default extension if no valid extension is provided
            if not has_extension:
                filename += f".{default_extension}"

            # Get base filename (without path)
            base_filename = os.path.basename(filename)

            # Create the stored_results directory if it doesn't exist
            storage_dir = ".sfc/stored_results"
            os.makedirs(storage_dir, exist_ok=True)

            # Create the full path for the main storage directory
            full_path = os.path.join(storage_dir, base_filename)

            # Write to file in the main storage directory
            with open(full_path, "w") as file:
                file.write(content)

            # Save additional copy in the current run directory if provided
            run_path = None
            if current_config_name:
                run_dir = os.path.join(".sfc/runs", current_config_name)
                if os.path.exists(run_dir):
                    run_path = os.path.join(run_dir, base_filename)
                    with open(run_path, "w") as file:
                        file.write(content)

            # Prepare the result message
            if run_path:
                return f"✅ Results saved successfully to:\n- '{full_path}'\n- '{run_path}'"
            else:
                return f"✅ Results saved successfully to '{full_path}'"
        except Exception as e:
            return f"❌ Error saving results: {str(e)}"

    @staticmethod
    def read_context_from_file(file_path: str) -> Tuple[bool, str, Optional[str]]:
        """Read content from various file types to use as context

        Supports: PDF, Excel (xls, xlsx), Markdown (md), CSV, Word (doc, docx),
                 Rich Text Format (rtf), and Text (txt) files.

        Args:
            file_path: Path to the file (relative to where the agent was started)

        Returns:
            Tuple containing:
            - Success flag (bool)
            - Message (str) - Success or error message
            - Content (Optional[str]) - File content or None if error occurred
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return False, f"❌ File not found: '{file_path}'", None

            # Check file size (max 500KB)
            file_size = os.path.getsize(file_path) / 1024  # Convert to KB
            if file_size > 500:
                return (
                    False,
                    f"❌ File size ({file_size:.1f} KB) exceeds the maximum limit of 500 KB",
                    None,
                )

            # Get file extension
            file_ext = os.path.splitext(file_path)[1].lower()

            # List of supported file extensions
            supported_extensions = [
                ".pdf",
                ".xls",
                ".xlsx",
                ".md",
                ".csv",
                ".doc",
                ".docx",
                ".rtf",
                ".txt",
            ]

            if file_ext not in supported_extensions:
                return (
                    False,
                    f"❌ Unsupported file type: '{file_ext}'. Supported types: pdf, xls, xlsx, md, csv, doc, docx, rtf, txt",
                    None,
                )

            content = None

            # Process different file types
            if file_ext == ".pdf":
                content = SFCFileOperations._extract_pdf_content(file_path)
            elif file_ext in [".xls", ".xlsx"]:
                content = SFCFileOperations._extract_excel_content(file_path)
            elif file_ext == ".csv":
                content = SFCFileOperations._extract_csv_content(file_path)
            elif file_ext in [".doc", ".docx"]:
                content = SFCFileOperations._extract_word_content(file_path)
            elif file_ext == ".rtf":
                content = SFCFileOperations._extract_rtf_content(file_path)
            elif file_ext == ".md" or file_ext == ".txt":
                # Plain text files can be read directly
                with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                    content = file.read()

            if content:
                return (
                    True,
                    f"✅ Successfully read content from '{file_path}' ({file_size:.1f} KB)",
                    content,
                )
            else:
                return False, f"❌ Failed to extract content from '{file_path}'", None

        except Exception as e:
            return False, f"❌ Error reading file: {str(e)}", None

    @staticmethod
    def _extract_pdf_content(file_path: str) -> str:
        """Extract text content from a PDF file"""
        try:
            # Try importing PyPDF2, if not available use a simpler method
            try:
                import PyPDF2

                text = ""
                with open(file_path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)
                    for page_num in range(len(reader.pages)):
                        text += reader.pages[page_num].extract_text() + "\n\n"
                return text
            except ImportError:
                return f"[PDF CONTENT] Import PyPDF2 to properly extract content from '{file_path}'"
        except Exception as e:
            return f"[PDF EXTRACTION ERROR] {str(e)}"

    @staticmethod
    def _extract_excel_content(file_path: str) -> str:
        """Extract data from Excel files"""
        try:
            # Try importing pandas and openpyxl, if not available use a simpler method
            try:
                import pandas as pd

                # Read Excel file into pandas DataFrames (one per sheet)
                excel_data = pd.read_excel(file_path, sheet_name=None)

                result = []
                for sheet_name, df in excel_data.items():
                    # Add sheet name as header
                    result.append(f"--- Sheet: {sheet_name} ---")

                    # Convert DataFrame to string representation
                    result.append(df.to_string(index=False))
                    result.append("\n")

                return "\n".join(result)
            except ImportError:
                return f"[EXCEL CONTENT] Import pandas and openpyxl to properly extract content from '{file_path}'"
        except Exception as e:
            return f"[EXCEL EXTRACTION ERROR] {str(e)}"

    @staticmethod
    def _extract_csv_content(file_path: str) -> str:
        """Extract data from CSV files"""
        try:
            result = []
            with open(
                file_path, "r", newline="", encoding="utf-8", errors="replace"
            ) as csvfile:
                csv_reader = csv.reader(csvfile)
                for row in csv_reader:
                    result.append(", ".join(row))
            return "\n".join(result)
        except Exception as e:
            return f"[CSV EXTRACTION ERROR] {str(e)}"

    @staticmethod
    def _extract_word_content(file_path: str) -> str:
        """Extract text from Word documents"""
        try:
            # Try importing python-docx, if not available use a simpler method
            try:
                import docx

                doc = docx.Document(file_path)
                full_text = []
                for para in doc.paragraphs:
                    full_text.append(para.text)
                return "\n".join(full_text)
            except ImportError:
                return f"[WORD CONTENT] Import python-docx to properly extract content from '{file_path}'"
        except Exception as e:
            return f"[WORD EXTRACTION ERROR] {str(e)}"

    @staticmethod
    def _extract_rtf_content(file_path: str) -> str:
        """Extract text from RTF files"""
        try:
            # Try importing striprtf, if not available use a simpler method
            try:
                from striprtf.striprtf import rtf_to_text

                with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                    rtf_text = file.read()
                    plain_text = rtf_to_text(rtf_text)
                    return plain_text
            except ImportError:
                # Basic RTF stripping (not perfect but better than nothing)
                with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                    rtf_text = file.read()
                    # Very simple RTF cleaning (removes control sequences)
                    import re

                    cleaned_text = re.sub(r"[\\][a-z0-9]+\s?", " ", rtf_text)
                    cleaned_text = re.sub(r"[{}]", "", cleaned_text)
                    return cleaned_text
        except Exception as e:
            return f"[RTF EXTRACTION ERROR] {str(e)}"
