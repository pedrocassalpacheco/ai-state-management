# Documentation

This folder contains technical documentation for the AI State Management system.

## Files

### [SCHEMA.md](./SCHEMA.md)
**Comprehensive database schema documentation**
- Complete data dictionary for all tables
- Field descriptions, types, and constraints
- Relationship explanations
- Common query patterns
- Design decision rationale
- Migration notes

**Start here if you want to understand the database structure.**

---

### [schema-erd.mmd](./schema-erd.mmd)
**Entity-Relationship Diagram (Mermaid format)**
- Visual representation of all tables and relationships
- Can be viewed in VS Code, GitHub, or Mermaid Live Editor
- Exportable to PNG/SVG/PDF

**How to view:**
```bash
# In VS Code with Mermaid extension
code schema-erd.mmd
# Press Cmd+Shift+V (Mac) or Ctrl+Shift+V (Windows)

# Generate image with mermaid-cli
mmdc -i schema-erd.mmd -o schema-erd.png
```

---

### [PLACEMENT_RULES.md](./PLACEMENT_RULES.md)
**TiDB data colocation and partitioning strategy**
- Explains partitioning by (user_id, bot_id)
- Performance benefits of data colocation
- Difference between standard and colocated schemas
- Setup instructions
- Monitoring and verification queries

**Read this if you need to understand distributed data placement.**

---

## Quick Links

- **Getting Started**: [../README.md](../README.md)
- **System Architecture**: [../design.md](../design.md)
- **Scripts Documentation**: [../scripts/README.md](../scripts/README.md)

## Viewing ER Diagrams

### Recommended Tools

1. **VS Code** (Free)
   - Extension: "Markdown Preview Mermaid Support" by Matt Bierner
   - Renders .mmd files natively

2. **Mermaid Live Editor** (Web-based, Free)
   - URL: https://mermaid.live
   - Paste diagram code and export as image

3. **GitHub** (Free)
   - Just view the .mmd file on GitHub - renders automatically

4. **Draw.io / diagrams.net** (Free)
   - Can import Mermaid diagrams
   - URL: https://app.diagrams.net

5. **mermaid-cli** (Command-line)
   ```bash
   npm install -g @mermaid-js/mermaid-cli
   mmdc -i schema-erd.mmd -o schema-erd.png
   ```

## Contributing

When updating the schema:
1. Update the SQL files: `scripts/init_schema.sql` and `scripts/init_schema_with_placement.sql`
2. Update [SCHEMA.md](./SCHEMA.md) data dictionary
3. Update [schema-erd.mmd](./schema-erd.mmd) ER diagram
4. Update related documentation in [PLACEMENT_RULES.md](./PLACEMENT_RULES.md) if partitioning changes
