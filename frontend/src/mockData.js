/**
 * Generates sample SAR (Suspicious Activity Report) files in-memory for instant 1-click testing.
 */

export function createSampleSarFiles(caseId = "SAR-CASE-2026-001") {
  // 1. Case Alert & SAR Metadata (JSON)
  const caseAlert = {
    case_id: caseId,
    alert_id: "ALT-FINCRIME-8842",
    filing_institution: "First Global Commercial Bank",
    compliance_division: "Anti-Money Laundering & Sanctions Screening",
    created_at: new Date().toISOString(),
    urgency: "HIGH",
    primary_violation: "Structuring, Layering & Rapid Movement of Offshore Funds",
    narrative_summary:
      "Subject entity received multiple rapid wire transfers from foreign shell companies followed immediately by structured cash withdrawals just beneath reporting thresholds ($10,000 USD).",
    investigator_assigned: "J. Mercer, Senior AML Analyst",
    status: "INVESTIGATION_IN_PROGRESS"
  };

  // 2. Subject / Entity KYC Profile (JSON)
  const subjectProfile = {
    subject_id: "SUB-ENT-55910",
    legal_name: "Horizon Meridian Trading LLC",
    registration_jurisdiction: "Panama / British Virgin Islands",
    incorporation_date: "2021-04-12",
    beneficial_owner: "Viktor Vance",
    pep_status: "YES (Politically Exposed Person via family association)",
    kyc_risk_tier: "TIER_1_CRITICAL",
    industry_sector: "Commodities & Wholesale Import/Export",
    sanction_screening_result: "NO_DIRECT_MATCH_WATCHLIST_FLAGGED",
    tax_identifier: "PA-77821-X",
    registered_agent: "Mossack & Partners Legal Services"
  };

  // 3. Transactions Ledger (CSV)
  const transactionsCsv = `tx_id,date,amount,currency,tx_type,counterparty,origin_country,destination_country,risk_flag
TX-9011,2026-10-01,9850.00,USD,WIRE_INBOUND,Apex Global Holdings,CYPRUS,USA,STRUCTURING_SUSPECTED
TX-9012,2026-10-02,9900.00,USD,WIRE_INBOUND,Zenith Maritime Ltd,SEYCHELLES,USA,STRUCTURING_SUSPECTED
TX-9013,2026-10-03,9750.00,USD,CASH_WITHDRAWAL,Branch ATM #441,USA,USA,BELOW_CTR_THRESHOLD
TX-9014,2026-10-04,45000.00,USD,SWIFT_OUTBOUND,Silverstone Capital,PANAMA,SWITZERLAND,HIGH_RISK_JURISDICTION
TX-9015,2026-10-05,9920.00,USD,WIRE_INBOUND,Kestrel Enterprises,UAE,USA,STRUCTURING_SUSPECTED
TX-9016,2026-10-06,125000.00,EUR,INTERNATIONAL_WIRE,Baltic Freight Corp,ESTONIA,GERMANY,LARGE_VALUE_ROUND_SUM`;

  // 4. Accounts & Supporting Records (CSV)
  const accountsCsv = `account_id,account_number,account_type,status,current_balance,currency,open_date,risk_rating
ACC-101,1144778822,CORPORATE_CHECKING,ACTIVE,384250.00,USD,2021-05-10,HIGH_RISK
ACC-102,9933114455,OFFSHORE_TREASURY,RESTRICTED,125400.00,EUR,2022-01-18,CRITICAL_RISK
ACC-103,4488226611,ESCROW_HOLDING,FROZEN,4500.00,USD,2023-08-22,HIGH_RISK`;

  // Convert to browser File objects
  const file1 = new File(
    [JSON.stringify(caseAlert, null, 2)],
    "case_alert_metadata.json",
    { type: "application/json" }
  );

  const file2 = new File(
    [JSON.stringify(subjectProfile, null, 2)],
    "subject_kyc_profile.json",
    { type: "application/json" }
  );

  const file3 = new File(
    [transactionsCsv],
    "financial_transactions.csv",
    { type: "text/csv" }
  );

  const file4 = new File(
    [accountsCsv],
    "supporting_accounts_audit.csv",
    { type: "text/csv" }
  );

  return {
    json_file_1: file1,
    json_file_2: file2,
    csv_file_1: file3,
    csv_file_2: file4,
    caseId,
  };
}
