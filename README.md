# Email Processing Tool

A command-line tool for processing, extracting, and visualising email (`.msg` and `.eml`)  files.

All output files are written to an `output/` folder, which is created automatically on first run.

---

## Usage

```
python emails.py [flags]
```

At least one flag is required. Multiple flags can be combined and will run in the order shown below.

| Flag | Short | Description |
|------|-------|-------------|
| `--rename` | `-r` | Rename email files by date and subject |
| `--data` | `-d` | Extract email metadata to `output/results.xlsx` |
| `--visual` | `-v` | Generate an HTML visual report in `output/report.html` |

When `-r` or `-d` are used, you will be prompted to enter the folder path containing the emails.

**Recommended first run:**
```
python emails.py -r -d -v
```
This renames the files, extracts the data, then generates the full visual report in one step.

---

## Output files

All files are saved to the `output/` folder:

| File | Created by | Description |
|------|-----------|-------------|
| `results.xlsx` | `-d` | Email metadata (date, sender, recipients, subject, body, attachments) |
| `relationship_details.csv` | `-v` | All sender–recipient pairs with email counts |
| `network_nodes.csv` | `-v` | Node data for the correspondence network |
| `network_edges.csv` | `-v` | Edge data for the correspondence network |
| `relationship_summary.txt` | `-v` | Human-readable summary: top senders, recipients, and pairs |
| `relationship_summary.json` | `-v` | Same summary in machine-readable JSON format |
| `report.html` | `-v` | Self-contained visual report (open in any browser) |

> **Note:** `-v` requires `output/results.xlsx` to exist. Run `-d` before `-v` if it does not.

---

## Scripts

### `emails.py` — Entry point

Parses command-line flags and calls the appropriate modules in order. The `output/` folder is created here if it does not already exist.

---

### `renamer.py` — File renamer

Renames all `.eml` and `.msg` files in a folder (and all subfolders) to a standardised format:

```
YYYY.MM.DD HH.MM - Subject.ext
```

- Extracts the send date and subject from each email's metadata
- Strips unsafe characters from the subject line
- If a renamed file already exists at the destination, the original is moved to a `potential duplicate/` subfolder

---

### `extractdata.py` — Data extractor

Reads all `.msg` files in a folder (and all subfolders) and exports their metadata to `output/results.xlsx`.

Columns extracted:

| Column | Description |
|--------|-------------|
| `date` | Send date (`YYYY-MM-DD, HH:MM`) |
| `sender` | Sender name and email address |
| `recipient` | To field |
| `cc` | CC field |
| `subject` | Email subject |
| `body` | Email body text (truncated at 32,000 characters) |
| `category` | Outlook category tags |
| `attachments` | List of attachment filenames |

---

### `analyze_relationships.py` — Relationship analyser

Reads `output/results.xlsx` and analyses who sends emails to whom. Runs automatically as part of `-v`, but can also be run standalone:

```
python analyze_relationships.py --input output/results.xlsx --top-n 20
```

Produces `relationship_details.csv`, `network_nodes.csv`, `network_edges.csv`, `relationship_summary.txt`, and `relationship_summary.json` in `output/`.

---

### `visualise.py` — Visual report generator

Reads `output/results.xlsx` and generates `output/report.html` — a self-contained file containing two interactive visualisations:

**Email Volume Over Time**
- Bar chart of email counts per day, month, or year (granularity auto-scales to the date range)
- Long gaps in activity are collapsed and marked with `//` break indicators
- A trend line is overlaid

**Correspondence Network**
- Interactive force-directed graph of the top 25 most active people
- Node size reflects total activity; colour shows whether a person primarily sends (blue), receives (orange), or both (grey)
- Edge width reflects the number of emails exchanged between each pair
- Hover to see sent/received counts; click a node to highlight their connections

---

## Dependencies

```
pip install extract-msg pandas openpyxl matplotlib numpy
```

The visual report loads **Cytoscape.js** from a CDN and **Inter** font from Google Fonts — an internet connection is required when opening `report.html`.
