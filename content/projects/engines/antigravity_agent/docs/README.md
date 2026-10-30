# DevCore & Siraugga Framework Documentation

All architectural textbooks, Zero-Trust security manuals, 5-pillar devlogs,
and technical specifications are centrally maintained and version-controlled
in the **Central Documentation Vault** on GitHub:

🔗 **GitHub Repository**: [https://github.com/MikeyMike99/Central_Docs](https://github.com/MikeyMike99/Central_Docs)
📁 **Local Working Tree**: `../Central_Docs/projects/siraugga_framework/`

### How to Run Documentation Audits & Syncs
To audit doc compliance across the workspace, use the unified pipeline:
```bash
python3 scripts/workspace_pipeline.py --audit
```
To synchronize published docs with the e_profile web portal:
```bash
python3 ../Central_Docs/scripts/sync_to_eprofile.py
```
