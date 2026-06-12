# Requirements Agent MCP Tool Usage Guidelines

When a JSON output has been detected from the `mcp_automotive_requirements_automotive_requirements_analyzer` or `automotive_requirements_analyzer` MCP tool, examine the content and automatically save the generated requirements analysis and user acceptance tests.

When a user asks for requirements analysis using requirements documents (such as User: "Analyze requirements for weather app using weather_app_requirements.md"), execute the following steps

## Processing Steps

1. Construct the payload using the absolute file path (use pwd tool)

2. Call the automotive requirements analyzer tool

3. **Detect Requirements Analysis Output**: Look for JSON responses from the automotive requirements analyzer tool that contain requirements analysis and user acceptance test content.

4. **Extract Analysis Content**: Extract both the requirements analysis summary and user acceptance test specifications from the response.

5. **Determine Save Location for Analysis**: Save the requirements analysis using this priority order:
   - Next to the respective requirements file in the same directory
   - If a project-specific requirements directory exists (e.g., `*/requirements/`), save there
   - If a project root directory is identifiable, create a `requirements-analysis/` subdirectory
   - Otherwise, save in the current working directory under `requirements-analysis/`

6. **Determine Save Location for UAT**: Save the user acceptance tests using this priority order:
   - If existing user acceptance test files or directories exist, save there
   - If a project-specific test directory exists (e.g., `*/uat/` or `*/user-acceptance-tests/`), save there
   - If a project root directory is identifiable, create a `user-acceptance-tests/` subdirectory
   - Otherwise, save in the current working directory under `user-acceptance-tests/`

7. **Generate Filenames**: Create appropriate filenames based on:
   - Project name if identifiable from the requirements documents
   - Use format: `{project_name}_requirements_analysis.md` for analysis
   - Use format: `{project_name}_user_acceptance_tests.md` for UAT

8. **Save Documents**: Write both the requirements analysis and user acceptance test documents to their determined locations.
   - **Important**: Break large documents into chunks (first 50 lines with `fsWrite`, then use `fsAppend` for remaining content)
   - Process the entire document content without truncation
   - Ensure all sections from the MCP tool output are preserved

9. **Provide Confirmation**: Inform the user of both save locations and filenames.

## Example Usage Pattern

```
User: "Analyze requirements for weather app using weather_app_requirements.md"
→ Cline calls MCP tool supplying requirements document content
→ MCP tool generates analysis report and UAT
→ Cline detects JSON output with analysis report and UAT content
→ Cline saves analysis to: weather-app/requirements-analysis/weather_app_requirements_analysis.md
→ Cline saves UAT to: weather-app/user-acceptance-tests/weather_app_user_acceptance_tests.md
→ Cline confirms: "Requirements analysis saved to weather-app/requirements-analysis/weather_app_requirements_analysis.md and UAT saved to weather-app/user-acceptance-tests/weather_app_user_acceptance_tests.md"
```

## File Structure Guidelines

When saving requirements analysis and user acceptance test documents, maintain this structure:
```
{project_name}/
├── requirements-analysis/
│   ├── {project_name}_requirements_analysis.md
│   ├── consistency-reports/
│   └── quality-assessments/
├── user-acceptance-tests/
│   ├── {project_name}_user_acceptance_tests.md
│   ├── test-scenarios/
│   └── acceptance-criteria/
├── business-requirements/
├── technical-requirements/
└── other-project-files/
```

## Notes

- Always preserve the complete requirements analysis and UAT document structure
- Maintain markdown formatting for readability
- Include document metadata (version, date, author) when available
- Support both single-project and multi-project workspace scenarios
- Handle both requirements analysis summaries and user acceptance test specifications appropriately
