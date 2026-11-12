# Milestone 1: report classifier
1. Put reports.json and taxonomy.json (and questions.json for later) in `./data/`
2. `pip install -r requirements.txt`, copy `.env.example` to `.env`, add your key and model name
3. `python classifier.py`
   - `classified_reports.json`: reports.json with one new field per report, "repair" or "verdict"
   - `classification_debug.json`: reason + confidence per report (for checking only)
