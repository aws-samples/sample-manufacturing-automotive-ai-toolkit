# Design Agent MCP Tool Usage Guidelines


When a JSON output has been detected from the `mcp_automotive_design_automotive_design_generator` or `automotive_design_generator` MCP tool, examine the content and automatically save the generated technical design document.

When a user asks for the generation of technical designs using an SRS and a BRD document (such as User: "Generate technical design for weather app using weather_app_brd.md and weather_app_srs.md"), execute the following steps

## Processing Steps

1. Construct the payload using the absolute file paths (use pwd tool)

2. Call the automotive design generator tool

3. **Detect Design Generation Output**: Look for JSON responses from the automotive design generator tool that contain a `step1_design_generation.design` field.

4. **Extract Design Content**: Extract the complete technical design document from the `design` field in the JSON response.

5. **Determine Save Location**: Save the technical design document using this priority order:
   - If a project-specific technical design directory exists (e.g., `*/technical-design/`), save there
   - If a project root directory is identifiable, create a `technical-design/` subdirectory
   - Otherwise, save in the current working directory under `technical-design/`

6. **Generate Filename**: Create an appropriate filename based on:
   - Project name if identifiable from the requirements documents
   - Use format: `{project_name}_technical_design.md`

7. **Save Document**: Write the complete technical design document to the determined location with the generated filename.
   - **Important**: Break large documents into chunks (first 50 lines with `fsWrite`, then use `fsAppend` for remaining content)
   - Process the entire document content without truncation
   - Ensure all sections from the MCP tool output are preserved

8. **Provide Confirmation**: Inform the user of the save location and filename.

## Example Usage Pattern

```
User: "Generate technical design for weather app using weather_app_brd.md and weather_app_srs.md"
→ Kiro calls MCP tool supplying documents absolute file paths
→ MCP tool generates design
→ Kiro detects JSON output with technical design content
→ Kiro saves technical design to: weather-app/technical-design/weather_app_technical_design.md
→ Kiro confirms: "Technical design saved to weather-app/technical-design/weather_app_technical_design.md"
```

## File Structure Guidelines

When saving technical design documents, maintain this structure:
```
{project_name}/
├── technical-design/
│   ├── {project_name}_technical_design.md
│   ├── architecture-diagrams/
│   ├── component-specifications/
│   └── implementation-guides/
├── business-requirements/
├── technical-requirements/
└── other-project-files/
```

## Notes

- Always preserve the complete technical design document structure
- Maintain markdown formatting for readability
- Include document metadata (version, date, author) when available
- Support both single-project and multi-project workspace scenarios