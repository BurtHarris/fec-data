# FEC Data Normalization and PowerBI Model Recommendations

This document outlines best practices for normalizing FEC data and creating a PowerBI-friendly semantic model. The goal is to unify the FEC’s disparate naming conventions and data structures into a consistent, readable, and performant model.

## 1. Normalize the Three FEC “Views of the World”

The FEC uses different names for the same concepts across:
- **Web UI**
- **Bulk CSVs**
- **OpenFEC API**

A PowerBI model benefits from one canonical name per concept, regardless of source.

### Recommended Canonical Entity Names
- `Candidate`
- `Committee`
- `Contribution` (instead of “receipts,” “schedule A,” “individual contributions”)
- `Disbursement` (instead of “expenditures,” “schedule B”)
- `IndependentExpenditure`
- `Election`
- `Filing`
- `ReportSummary`

These names are short, unambiguous, and align with PowerBI’s preference for singular table names.

---

## 2. Standardize Table Names for Bulk CSV Imports

Bulk files have names like `itcont.txt`, `cn.txt`, `pas2.txt`, etc. Rename them to something meaningful in a semantic model.

### Suggested PowerBI Table Names
| PowerBI Table Name         | Source Files                          |
|----------------------------|---------------------------------------|
| `Candidates`               | `cn.txt` / `all_candidates.csv`       |
| `Committees`               | `cm.txt` / `all_committees.csv`       |
| `CandidateCommitteeLinks`  | `ccl.txt`                             |
| `IndividualContributions`  | `itcont.txt`                          |
| `CommitteeContributions`   | `contributions_from_committees.*`     |
| `Disbursements`            | `itoth.txt`                           |
| `IndependentExpenditures`  | `independent_expenditures.*`          |
| `CommitteeSummaries`       | `committee_summary.*`                 |
| `CandidateSummaries`       | `candidate_summary.*`                 |

These names are:
- Readable
- Consistent
- Aligned with PowerBI’s semantic model conventions

---

## 3. Standardize Column Names Across All Sources

The FEC mixes column naming conventions:
- `cand_id`, `candidate_id`, `CAND_ID`
- `cmte_id`, `committee_id`, `committeeid`
- `transaction_amt`, `amount`, `TRANSACTION_AMT`
- `receipt_date`, `date`, `TRANSACTION_DT`

### Recommended Column Naming Rules
- Use `snake_case` or `camelCase` (PowerBI works well with either).
- Use full words, not abbreviations.
- Apply consistent prefixes for foreign keys.

### Example Canonical Column Names
| Canonical Name       | Example Usage                  |
|----------------------|--------------------------------|
| `candidate_id`       | Foreign key for candidates     |
| `committee_id`       | Foreign key for committees     |
| `transaction_id`     | Unique transaction identifier  |
| `transaction_date`   | Date of transaction            |
| `transaction_amount` | Amount of transaction          |
| `employer_name`      | Contributor’s employer         |
| `occupation`         | Contributor’s occupation       |
| `election_cycle`     | Election cycle                 |
| `report_type`        | Type of report filed           |
| `filing_id`          | Unique filing identifier       |

This makes DAX and Power Query dramatically easier to read.

---

## 4. Create a Unified “Schedule” Abstraction

The FEC’s “Schedule A/B/E/etc.” naming is cryptic for analysts.

### Recommended PowerBI-Friendly Mapping
| FEC Schedule | Canonical Name       | Meaning               |
|--------------|----------------------|-----------------------|
| A            | `Contribution`       | Money received        |
| B            | `Disbursement`       | Money spent           |
| E            | `IndependentExpenditure` | Outside spending |
| D/F/H        | Ignore or map as needed | Rarely used       |

This lets you build a single fact table with a `schedule_type` column if desired.

---

## 5. Create Semantic-Friendly Surrogate Keys

FEC IDs are meaningful but messy. PowerBI works better with clean surrogate keys.

### Examples
| Surrogate Key       | Description                          |
|---------------------|--------------------------------------|
| `candidate_key`     | Integer surrogate for `candidate_id` |
| `committee_key`     | Integer surrogate for `committee_id` |
| `transaction_key`   | Integer surrogate for each row in Schedule A/B |

This improves:
- Relationship diagrams
- Incremental refresh
- Model performance

---

## 6. Provide User-Friendly Display Names

PowerBI lets you separate:
- **Technical names** (for DAX)
- **Display names** (for visuals)

### Examples
| Technical Name       | Display Name       |
|----------------------|--------------------|
| `transaction_amount` | Amount             |
| `committee_name`     | Committee          |
| `election_cycle`     | Cycle              |

This keeps the model clean for you and readable for consumers.

---

## 7. Mapping 2-Year Cycles to DuckDB OLAP Tables

The FEC organizes bulk data in 2-year cycles. To enable reporting over longer periods, we can design a schema that abstracts cycle-specific data into unified tables with additional metadata columns. This approach ensures seamless querying for longitudinal analysis.

### Unified Fact Tables
Combine data from multiple cycles into a single fact table for each entity (e.g., contributions, disbursements). Add a `cycle` column to indicate the 2-year cycle of the data.

#### Example: `contributions` Table
| Column Name          | Data Type   | Description                                   |
|----------------------|-------------|-----------------------------------------------|
| `contribution_id`    | INTEGER     | Surrogate key for the contribution record.    |
| `candidate_id`       | STRING      | Foreign key to the `candidates` table.        |
| `committee_id`       | STRING      | Foreign key to the `committees` table.        |
| `transaction_date`   | DATE        | Date of the contribution.                     |
| `transaction_amount` | DECIMAL(10,2) | Amount of the contribution.                  |
| `cycle`              | INTEGER     | 2-year cycle (e.g., 2024, 2026).              |
| `election_type`      | STRING      | Type of election (e.g., general, primary).    |
| `state`              | STRING      | State where the contribution occurred.        |
| `district`           | STRING      | Congressional district (if applicable).       |

### Dimension Tables
Create dimension tables for entities like candidates, committees, and elections. Include metadata columns to capture information that spans multiple cycles.

#### Example: `candidates` Table
| Column Name       | Data Type   | Description                                   |
|-------------------|-------------|-----------------------------------------------|
| `candidate_id`    | STRING      | Unique identifier for the candidate.          |
| `candidate_name`  | STRING      | Full name of the candidate.                   |
| `party`           | STRING      | Political party affiliation.                  |
| `state`           | STRING      | State where the candidate is running.         |
| `district`        | STRING      | Congressional district (if applicable).       |
| `office`          | STRING      | Office sought (e.g., President, Senate).      |
| `active_cycles`   | STRING      | Comma-separated list of cycles (e.g., 2024, 2026). |

### Surrogate Keys
Generate surrogate keys for all entities to simplify relationships and improve query performance.

#### Example: `transactions` Table
| Column Name          | Data Type   | Description                                   |
|----------------------|-------------|-----------------------------------------------|
| `transaction_id`     | INTEGER     | Surrogate key for the transaction.            |
| `schedule_type`      | STRING      | Type of transaction (A, B, E).                |
| `candidate_id`       | STRING      | Foreign key to the `candidates` table.        |
| `committee_id`       | STRING      | Foreign key to the `committees` table.        |
| `transaction_date`   | DATE        | Date of the transaction.                      |
| `transaction_amount` | DECIMAL(10,2) | Amount of the transaction.                  |
| `cycle`              | INTEGER     | 2-year cycle (e.g., 2024, 2026).              |

### Time Dimension
Create a `time` dimension table to enable reporting over longer periods. Include columns for year, quarter, month, and cycle.

#### Example: `time` Table
| Column Name       | Data Type   | Description                                   |
|-------------------|-------------|-----------------------------------------------|
| `date`            | DATE        | Specific date.                                |
| `year`            | INTEGER     | Year (e.g., 2024).                            |
| `quarter`         | STRING      | Quarter (e.g., Q1, Q2).                       |
| `month`           | STRING      | Month name (e.g., January).                   |
| `cycle`           | INTEGER     | 2-year cycle (e.g., 2024, 2026).              |

### ETL Workflow for Loading Data
1. **Extract**:
   - Download bulk data files for each cycle.
   - Parse files into staging tables in DuckDB.

2. **Transform**:
   - Normalize column names (e.g., `cand_id` → `candidate_id`).
   - Map FEC schedules to unified tables.
   - Generate surrogate keys for all entities.
   - Add a `cycle` column to each fact table.

3. **Load**:
   - Append data to unified fact and dimension tables.
   - Ensure referential integrity between fact and dimension tables.

### Benefits of This Approach
- **Consistency**: Unified tables and column names simplify analysis.
- **Scalability**: Supports reporting over multiple cycles without duplicating tables.
- **Performance**: Surrogate keys and normalized tables improve query efficiency.
- **Flexibility**: Enables both cycle-specific and longitudinal analysis.