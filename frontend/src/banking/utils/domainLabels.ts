/**
 * Domain-specific quality score labels and descriptions.
 * Maps banking domains to their corresponding document quality metrics.
 */

export interface DomainLabel {
  label: string;
  subtitle: string;
}

export function getDomainQualityLabel(domain: string | null | undefined): DomainLabel {
  const labelMap: Record<string, DomainLabel> = {
    'Customer Onboarding (KYC/AML)': {
      label: 'KYC/AML Document Quality',
      subtitle: 'Identity verification and beneficial ownership documentation quality',
    },
    'Loan & Credit Documentation': {
      label: 'Loan Document Quality',
      subtitle: 'Loan agreement and collateral documentation quality',
    },
    'Treasury & Liquidity Reports': {
      label: 'Treasury Report Quality',
      subtitle: 'HQLA and liquidity position reporting quality',
    },
    'Regulatory & Compliance Filings': {
      label: 'Regulatory Filing Quality',
      subtitle: 'Regulatory requirement mapping and data lineage quality',
    },
    'Investment Banking & M&A': {
      label: 'M&A Documentation Quality',
      subtitle: 'Valuation methodology and earnings documentation quality',
    },
    'Fraud & Investigation Records': {
      label: 'Investigation Documentation Quality',
      subtitle: 'SAR narrative and evidence documentation quality',
    },
  };

  return labelMap[domain || ''] || {
    label: 'Domain Quality',
    subtitle: 'Document quality in specialized domain context',
  };
}
