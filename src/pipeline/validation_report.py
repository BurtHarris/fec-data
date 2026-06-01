"""Generate markdown exception reports for early-quality validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class ValidationRow:
    table_name: str
    column_name: str
    invalid_count: int


@dataclass(frozen=True)
class JHspLinkageSummary:
    total_j_hsp: int
    missing_cand_id: int
    bad_shape_cand_id: int
    linked_via_ccl: int
    unresolved_no_link: int


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cycle_table(table: str, cycle: int) -> str:
    return f"{table}_{cycle}"


def table_exists(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, table],
    ).fetchone()
    return bool(row and row[0] > 0)


def build_summary_sql(cycle: int, available_tables: set[str]) -> str:
    checks: list[str] = []

    def add_check(table: str, column: str, condition: str) -> None:
        checks.append(
            "\n".join(
                [
                    "SELECT",
                    f"    '{table}' AS table_name,",
                    f"    '{column}' AS column_name,",
                    "    COUNT(*) AS invalid_count",
                    f"FROM raw_fec.{cycle_table(table, cycle)}",
                    f"WHERE {condition}",
                ]
            )
        )

    if "indiv" in available_tables:
        add_check("indiv", "AMNDT_IND", "coalesce(trim(AMNDT_IND), '') = '' OR NOT regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')")
        add_check("indiv", "RPT_TP", "coalesce(trim(RPT_TP), '') = '' OR NOT regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')")
        add_check("indiv", "TRANSACTION_PGI", "coalesce(trim(TRANSACTION_PGI), '') <> '' AND NOT regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')")
        add_check("indiv", "TRANSACTION_TP", "coalesce(trim(TRANSACTION_TP), '') = '' OR NOT regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')")
        add_check("indiv", "ENTITY_TP", "coalesce(trim(ENTITY_TP), '') = '' OR NOT regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')")
        add_check("indiv", "IMAGE_NUM", "coalesce(trim(IMAGE_NUM), '') <> '' AND NOT regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')")
        add_check("indiv", "OTHER_ID", "coalesce(trim(OTHER_ID), '') <> '' AND NOT regexp_matches(upper(trim(OTHER_ID)), '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')")
        add_check("indiv", "MEMO_CD", "coalesce(trim(MEMO_CD), '') <> '' AND upper(trim(MEMO_CD)) <> 'X'")
        add_check("indiv", "SUB_ID", "SUB_ID IS NULL OR SUB_ID <= 0")

    if "cm" in available_tables:
        add_check("cm", "CMTE_ID", "coalesce(trim(CMTE_ID), '') = '' OR NOT regexp_matches(upper(trim(CMTE_ID)), '^C[0-9]{8}$')")
        add_check("cm", "CMTE_DSGN", "coalesce(trim(CMTE_DSGN), '') = '' OR NOT regexp_matches(upper(trim(CMTE_DSGN)), '^[ABDJPU]$')")
        add_check("cm", "CMTE_TP", "coalesce(trim(CMTE_TP), '') = '' OR NOT regexp_matches(upper(trim(CMTE_TP)), '^[A-Z]$')")
        add_check("cm", "CMTE_FILING_FREQ", "coalesce(trim(CMTE_FILING_FREQ), '') <> '' AND NOT regexp_matches(upper(trim(CMTE_FILING_FREQ)), '^[ADMQTW]$')")
        add_check("cm", "ORG_TP", "coalesce(trim(ORG_TP), '') <> '' AND NOT regexp_matches(upper(trim(ORG_TP)), '^[CLMTVW]$')")
        add_check(
            "cm",
            "CAND_ID_MISSING_FOR_HSP",
            "upper(trim(CMTE_TP)) IN ('H', 'S', 'P') AND coalesce(trim(CAND_ID), '') = ''",
        )
        add_check(
            "cm",
            "CAND_ID_BAD_SHAPE_FOR_HSP",
            "upper(trim(CMTE_TP)) IN ('H', 'S', 'P') AND coalesce(trim(CAND_ID), '') <> '' AND NOT regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')",
        )

    if "cn" in available_tables:
        add_check("cn", "CAND_ID", "coalesce(trim(CAND_ID), '') = '' OR NOT regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')")
        add_check("cn", "CAND_OFFICE", "coalesce(trim(CAND_OFFICE), '') = '' OR NOT regexp_matches(upper(trim(CAND_OFFICE)), '^[HSP]$')")
        add_check("cn", "CAND_OFFICE_ST", "upper(trim(CAND_OFFICE)) IN ('H', 'S') AND NOT regexp_matches(trim(CAND_OFFICE_ST), '^[A-Z]{2}$')")
        add_check("cn", "CAND_STATUS", "coalesce(trim(CAND_STATUS), '') <> '' AND NOT regexp_matches(upper(trim(CAND_STATUS)), '^[CNPF]$')")
        add_check("cn", "CAND_ICI", "coalesce(trim(CAND_ICI), '') <> '' AND NOT regexp_matches(upper(trim(CAND_ICI)), '^[CIO]$')")
        add_check("cn", "CAND_PCC", "coalesce(trim(CAND_PCC), '') <> '' AND NOT regexp_matches(upper(trim(CAND_PCC)), '^C[0-9]{8}$')")
        add_check("cn", "CAND_ELECTION_YR", "CAND_ELECTION_YR IS NULL OR CAND_ELECTION_YR < 1900 OR CAND_ELECTION_YR > 2100 OR (CAND_ELECTION_YR % 2) <> 0")

    for table in ("oth", "pas2"):
        if table in available_tables:
            add_check(table, "AMNDT_IND", "coalesce(trim(AMNDT_IND), '') = '' OR NOT regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')")
            add_check(table, "RPT_TP", "coalesce(trim(RPT_TP), '') = '' OR NOT regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')")
            add_check(table, "TRANSACTION_PGI", "coalesce(trim(TRANSACTION_PGI), '') <> '' AND NOT regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')")
            add_check(table, "TRANSACTION_TP", "coalesce(trim(TRANSACTION_TP), '') = '' OR NOT regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')")
            add_check(table, "ENTITY_TP", "coalesce(trim(ENTITY_TP), '') = '' OR NOT regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')")
            add_check(table, "IMAGE_NUM", "coalesce(trim(IMAGE_NUM), '') <> '' AND NOT regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')")
            add_check(table, "OTHER_ID", "coalesce(trim(OTHER_ID), '') <> '' AND NOT regexp_matches(upper(trim(OTHER_ID)), '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')")
            add_check(table, "MEMO_CD", "coalesce(trim(MEMO_CD), '') <> '' AND upper(trim(MEMO_CD)) <> 'X'")
            add_check(table, "SUB_ID", "SUB_ID IS NULL OR SUB_ID <= 0")

    if "oppexp" in available_tables:
        add_check("oppexp", "AMNDT_IND", "coalesce(trim(AMNDT_IND), '') = '' OR NOT regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')")
        add_check("oppexp", "RPT_TP", "coalesce(trim(RPT_TP), '') = '' OR NOT regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')")
        add_check("oppexp", "TRANSACTION_PGI", "coalesce(trim(TRANSACTION_PGI), '') <> '' AND NOT regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')")
        add_check("oppexp", "ENTITY_TP", "coalesce(trim(ENTITY_TP), '') = '' OR NOT regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')")
        add_check("oppexp", "IMAGE_NUM", "coalesce(trim(IMAGE_NUM), '') <> '' AND NOT regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')")
        add_check("oppexp", "MEMO_CD", "coalesce(trim(MEMO_CD), '') <> '' AND upper(trim(MEMO_CD)) <> 'X'")
        add_check("oppexp", "SUB_ID", "SUB_ID IS NULL OR SUB_ID <= 0")

    # Candidate-shape checks used by early_candidate_id_shape test.
    for table in ("ccl", "pas2", "weball"):
        if table in available_tables:
            add_check(
                table,
                "CAND_ID",
                "CAND_ID IS NOT NULL AND NOT regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')",
            )

    return "\nUNION ALL\n".join(checks)


def fetch_summary_rows(conn: duckdb.DuckDBPyConnection, cycle: int) -> list[ValidationRow]:
    candidate_tables = {"indiv", "oth", "pas2", "oppexp", "ccl", "cm", "cn", "weball"}
    available = {
        table
        for table in candidate_tables
        if table_exists(conn, "raw_fec", cycle_table(table, cycle))
    }

    summary_sql = build_summary_sql(cycle, available)
    if not summary_sql:
        return []

    query = (
        "WITH combined AS (\n"
        + summary_sql
        + "\n)\n"
        + "SELECT table_name, column_name, invalid_count FROM combined WHERE invalid_count > 0 ORDER BY table_name, column_name"
    )

    rows = conn.execute(query).fetchall()
    return [ValidationRow(table_name=row[0], column_name=row[1], invalid_count=int(row[2])) for row in rows]


def fetch_top_values(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
    row: ValidationRow,
    limit: int = 10,
) -> list[tuple[str, int]]:
    table = cycle_table(row.table_name, cycle)
    if not table_exists(conn, "raw_fec", table):
        return []

    where_clause = None
    value_column = row.column_name

    if row.column_name == "CAND_ID":
        where_clause = "CAND_ID IS NOT NULL AND NOT regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')"
    elif row.column_name == "CAND_ID_MISSING_FOR_HSP":
        value_column = "CAND_ID"
        where_clause = "upper(trim(CMTE_TP)) IN ('H', 'S', 'P') AND coalesce(trim(CAND_ID), '') = ''"
    elif row.column_name == "CAND_ID_BAD_SHAPE_FOR_HSP":
        value_column = "CAND_ID"
        where_clause = "upper(trim(CMTE_TP)) IN ('H', 'S', 'P') AND coalesce(trim(CAND_ID), '') <> '' AND NOT regexp_matches(upper(trim(CAND_ID)), '^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')"
    elif row.column_name == "OTHER_ID":
        where_clause = "coalesce(trim(OTHER_ID), '') <> '' AND NOT regexp_matches(upper(trim(OTHER_ID)), '^(C[0-9]{8}|[HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$')"
    elif row.column_name == "ENTITY_TP":
        where_clause = "coalesce(trim(ENTITY_TP), '') = '' OR NOT regexp_matches(upper(trim(ENTITY_TP)), '^[A-Z]{3}$')"
    elif row.column_name == "TRANSACTION_PGI":
        where_clause = "coalesce(trim(TRANSACTION_PGI), '') <> '' AND NOT regexp_matches(upper(trim(TRANSACTION_PGI)), '^([A-Z]|[A-Z][0-9]{4})$')"
    elif row.column_name == "RPT_TP":
        where_clause = "coalesce(trim(RPT_TP), '') = '' OR NOT regexp_matches(upper(trim(RPT_TP)), '^[A-Z0-9]{2,3}$')"
    elif row.column_name == "AMNDT_IND":
        where_clause = "coalesce(trim(AMNDT_IND), '') = '' OR NOT regexp_matches(upper(trim(AMNDT_IND)), '^[A-Z]$')"
    elif row.column_name == "TRANSACTION_TP":
        where_clause = "coalesce(trim(TRANSACTION_TP), '') = '' OR NOT regexp_matches(upper(trim(TRANSACTION_TP)), '^[A-Z0-9]{2,3}$')"
    elif row.column_name == "IMAGE_NUM":
        where_clause = "coalesce(trim(IMAGE_NUM), '') <> '' AND NOT regexp_matches(trim(IMAGE_NUM), '^([0-9]{11}|[0-9]{18})$')"
    elif row.column_name == "MEMO_CD":
        where_clause = "coalesce(trim(MEMO_CD), '') <> '' AND upper(trim(MEMO_CD)) <> 'X'"
    elif row.column_name == "SUB_ID":
        where_clause = "SUB_ID IS NULL OR SUB_ID <= 0"
    elif row.column_name == "CMTE_ID":
        where_clause = "coalesce(trim(CMTE_ID), '') = '' OR NOT regexp_matches(upper(trim(CMTE_ID)), '^C[0-9]{8}$')"
    elif row.column_name == "CMTE_DSGN":
        where_clause = "coalesce(trim(CMTE_DSGN), '') = '' OR NOT regexp_matches(upper(trim(CMTE_DSGN)), '^[ABDJPU]$')"
    elif row.column_name == "CMTE_TP":
        where_clause = "coalesce(trim(CMTE_TP), '') = '' OR NOT regexp_matches(upper(trim(CMTE_TP)), '^[A-Z]$')"
    elif row.column_name == "CMTE_FILING_FREQ":
        where_clause = "coalesce(trim(CMTE_FILING_FREQ), '') <> '' AND NOT regexp_matches(upper(trim(CMTE_FILING_FREQ)), '^[ADMQTW]$')"
    elif row.column_name == "ORG_TP":
        where_clause = "coalesce(trim(ORG_TP), '') <> '' AND NOT regexp_matches(upper(trim(ORG_TP)), '^[CLMTVW]$')"
    elif row.column_name == "CAND_OFFICE":
        where_clause = "coalesce(trim(CAND_OFFICE), '') = '' OR NOT regexp_matches(upper(trim(CAND_OFFICE)), '^[HSP]$')"
    elif row.column_name == "CAND_OFFICE_ST":
        where_clause = "upper(trim(CAND_OFFICE)) IN ('H', 'S') AND NOT regexp_matches(trim(CAND_OFFICE_ST), '^[A-Z]{2}$')"
    elif row.column_name == "CAND_STATUS":
        where_clause = "coalesce(trim(CAND_STATUS), '') <> '' AND NOT regexp_matches(upper(trim(CAND_STATUS)), '^[CNPF]$')"
    elif row.column_name == "CAND_ICI":
        where_clause = "coalesce(trim(CAND_ICI), '') <> '' AND NOT regexp_matches(upper(trim(CAND_ICI)), '^[CIO]$')"
    elif row.column_name == "CAND_PCC":
        where_clause = "coalesce(trim(CAND_PCC), '') <> '' AND NOT regexp_matches(upper(trim(CAND_PCC)), '^C[0-9]{8}$')"
    elif row.column_name == "CAND_ELECTION_YR":
        where_clause = "CAND_ELECTION_YR IS NULL OR CAND_ELECTION_YR < 1900 OR CAND_ELECTION_YR > 2100 OR (CAND_ELECTION_YR % 2) <> 0"

    if where_clause is None:
        return []

    value_expr = "coalesce(cast({col} as varchar), '<NULL>')".format(col=value_column)
    query = (
        f"SELECT {value_expr} AS invalid_value, COUNT(*) AS row_count "
        f"FROM raw_fec.{table} WHERE {where_clause} "
        f"GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit}"
    )
    return [(str(value), int(count)) for value, count in conn.execute(query).fetchall()]


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "|" + "|".join(["---"] * len(headers)) + "|"
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    if body:
        return "\n".join([header_line, sep_line, body])
    return "\n".join([header_line, sep_line])


def fetch_j_hsp_linkage_focus(
    conn: duckdb.DuckDBPyConnection,
    cycle: int,
) -> tuple[JHspLinkageSummary | None, list[list[str]]]:
    cm_table = cycle_table("cm", cycle)
    ccl_table = cycle_table("ccl", cycle)
    if not table_exists(conn, "raw_fec", cm_table):
        return None, []

    candidate_shape = "^([HS][0-9][A-Z]{2}[0-9]{5}|P[0-9]{8})$"
    ccl_join = ""
    ccl_link_expr = "0"
    if table_exists(conn, "raw_fec", ccl_table):
        ccl_join = (
            f"LEFT JOIN raw_fec.{ccl_table} ccl "
            f"ON ccl.cmte_id = cm.cmte_id "
            f"AND ccl.cand_id IS NOT NULL "
            f"AND regexp_matches(upper(trim(ccl.cand_id)), '{candidate_shape}')"
        )
        ccl_link_expr = "count(distinct ccl.cand_id)"

    summary_query = (
        "WITH j_hsp AS (\n"
        "    SELECT\n"
        "        cm.cmte_id,\n"
        "        cm.cmte_nm,\n"
        "        cm.cmte_tp,\n"
        "        cm.cmte_dsgn,\n"
        "        cm.cand_id,\n"
        f"        {ccl_link_expr} AS ccl_candidate_links\n"
        f"    FROM raw_fec.{cm_table} cm\n"
        f"    {ccl_join}\n"
        "    WHERE upper(trim(cm.cmte_dsgn)) = 'J'\n"
        "      AND upper(trim(cm.cmte_tp)) IN ('H','S','P')\n"
        "    GROUP BY 1,2,3,4,5\n"
        ")\n"
        "SELECT\n"
        "    count(*) AS total_j_hsp,\n"
        "    sum(CASE WHEN coalesce(trim(cand_id), '') = '' THEN 1 ELSE 0 END) AS missing_cand_id,\n"
        f"    sum(CASE WHEN coalesce(trim(cand_id), '') <> '' AND NOT regexp_matches(upper(trim(cand_id)), '{candidate_shape}') THEN 1 ELSE 0 END) AS bad_shape_cand_id,\n"
        "    sum(CASE WHEN ccl_candidate_links > 0 THEN 1 ELSE 0 END) AS linked_via_ccl,\n"
        "    sum(CASE WHEN coalesce(trim(cand_id), '') = '' AND ccl_candidate_links = 0 THEN 1 ELSE 0 END) AS unresolved_no_link\n"
        "FROM j_hsp"
    )
    summary_row = conn.execute(summary_query).fetchone()
    if not summary_row or int(summary_row[0]) == 0:
        return None, []

    sample_query = (
        "WITH j_hsp AS (\n"
        "    SELECT\n"
        "        cm.cmte_id,\n"
        "        cm.cmte_nm,\n"
        "        cm.cmte_tp,\n"
        "        cm.cmte_dsgn,\n"
        "        cm.cand_id,\n"
        f"        {ccl_link_expr} AS ccl_candidate_links\n"
        f"    FROM raw_fec.{cm_table} cm\n"
        f"    {ccl_join}\n"
        "    WHERE upper(trim(cm.cmte_dsgn)) = 'J'\n"
        "      AND upper(trim(cm.cmte_tp)) IN ('H','S','P')\n"
        "    GROUP BY 1,2,3,4,5\n"
        ")\n"
        "SELECT cmte_id, cmte_nm, cmte_tp, cmte_dsgn\n"
        "FROM j_hsp\n"
        "WHERE coalesce(trim(cand_id), '') = '' AND ccl_candidate_links = 0\n"
        "ORDER BY cmte_tp, cmte_id\n"
        "LIMIT 20"
    )
    sample_rows = conn.execute(sample_query).fetchall()

    summary = JHspLinkageSummary(
        total_j_hsp=int(summary_row[0]),
        missing_cand_id=int(summary_row[1]),
        bad_shape_cand_id=int(summary_row[2]),
        linked_via_ccl=int(summary_row[3]),
        unresolved_no_link=int(summary_row[4]),
    )

    samples: list[list[str]] = []
    for cmte_id, cmte_nm, cmte_tp, cmte_dsgn in sample_rows:
        committee_cell = f"[{cmte_id}](https://www.fec.gov/data/committee/{cmte_id}/) {cmte_nm}"
        samples.append([committee_cell, str(cmte_tp), str(cmte_dsgn)])

    return summary, samples


def write_validation_report(root: Path, cycle: int) -> Path:
    db_path = root / "db" / "fec.duckdb"
    report_dir = root / "artifacts" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = utc_stamp()
    report_path = report_dir / f"validation_exceptions_{cycle}_{timestamp}.md"
    latest_path = report_dir / f"validation_exceptions_latest_{cycle}.md"

    if not db_path.exists():
        report_path.write_text(
            "\n".join(
                [
                    f"# Validation Exceptions Report ({cycle})",
                    "",
                    f"Generated at: {timestamp}",
                    "",
                    "DuckDB database not found at `db/fec.duckdb`; no validation details available.",
                ]
            ),
            encoding="utf-8",
        )
        latest_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
        return report_path

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        summary_rows = fetch_summary_rows(conn, cycle)
        j_summary, j_samples = fetch_j_hsp_linkage_focus(conn, cycle)

        lines: list[str] = [
            f"# Validation Exceptions Report ({cycle})",
            "",
            f"Generated at (UTC): {timestamp}",
            "",
            "## Exception Summary",
            "",
        ]

        if summary_rows:
            summary_table_rows = [
                [row.table_name, row.column_name, str(row.invalid_count)] for row in summary_rows
            ]
            if j_summary is not None:
                summary_table_rows.extend(
                    [
                        ["cm", "J_HSP_TOTAL", str(j_summary.total_j_hsp)],
                        ["cm", "J_HSP_MISSING_CAND_ID", str(j_summary.missing_cand_id)],
                        ["cm", "J_HSP_BAD_SHAPE_CAND_ID", str(j_summary.bad_shape_cand_id)],
                        ["cm", "J_HSP_LINKED_VIA_CCL", str(j_summary.linked_via_ccl)],
                        ["cm", "J_HSP_UNRESOLVED_NO_LINK", str(j_summary.unresolved_no_link)],
                    ]
                )
            lines.append(markdown_table(["table_name", "column_name", "invalid_count"], summary_table_rows))
            lines.extend(["", "## Exception Details", ""])

            for row in summary_rows:
                lines.append(f"### {row.table_name}.{row.column_name} ({row.invalid_count})")
                lines.append("")
                top_values = fetch_top_values(conn, cycle, row)
                if top_values:
                    value_rows = [[value, str(count)] for value, count in top_values]
                    lines.append(markdown_table(["invalid_value", "row_count"], value_rows))
                else:
                    lines.append("No value-level breakdown available for this exception.")
                lines.append("")

            if j_summary is not None:
                lines.extend(["## J/H/S Joint-Fundraiser Linkage Focus", ""])
                lines.append(
                    markdown_table(
                        [
                            "total_j_hsp",
                            "missing_cand_id",
                            "bad_shape_cand_id",
                            "linked_via_ccl",
                            "unresolved_no_link",
                        ],
                        [
                            [
                                str(j_summary.total_j_hsp),
                                str(j_summary.missing_cand_id),
                                str(j_summary.bad_shape_cand_id),
                                str(j_summary.linked_via_ccl),
                                str(j_summary.unresolved_no_link),
                            ]
                        ],
                    )
                )
                lines.append("")
                if j_samples:
                    lines.append("Top unresolved committees (missing CAND_ID and no CCL candidate link):")
                    lines.append("")
                    lines.append(markdown_table(["committee", "CMTE_TP", "CMTE_DSGN"], j_samples))
                    lines.append("")
        else:
            lines.append("No exceptions found for configured early-quality checks.")
            lines.append("")

        lines.extend(
            [
                "## Notes",
                "",
                "- This report is auto-generated as part of validation routines.",
                "- Counts reflect current `raw_fec.*_<cycle>` tables in `db/fec.duckdb`.",
            ]
        )

        report_path.write_text("\n".join(lines), encoding="utf-8")
        latest_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
        return report_path
    finally:
        conn.close()
