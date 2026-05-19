#!/bin/bash

# This script generates the semantic model diagram SVG from the Mermaid.js source.
# Requires: mermaid-cli (mmdc) installed globally.

# Define paths
MERMAID_SOURCE="../artifacts/diagrams/semantic_model_diagram.md"
OUTPUT_SVG="../artifacts/diagrams/semantic_model_diagram.svg"

# Generate the diagram
mmdc -i "$MERMAID_SOURCE" -o "$OUTPUT_SVG" --backgroundColor transparent

echo "Diagram regenerated: $OUTPUT_SVG"