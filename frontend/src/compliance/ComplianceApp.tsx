import { WorkspaceApp, WorkspaceConfig } from '../core/WorkspaceApp';

const complianceConfig: WorkspaceConfig = {
  workspace: 'compliance',
  title: 'Compliance Verification',
  subtitle: 'Automated Standards Verification & Regulatory Alignment',
  theme: {
    primary: '#047857', // Emerald Green
    accent: '#10B981',
    gradient: 'from-[#047857] to-[#10B981]',
    chartStroke: '#2563EB',
  },
  apiBaseUrl: '/compliance/api',
  hasDomainMetrics: false,
  hasLegalHold: false,
  hasRemediation: false,
  hasPdfReport: true,
  hasLinkedStandards: true,
  standardsSectionBadge: 'AI RISK ASSESSMENT',
  analyticsShowSeverityPie: false,
  footerTagline: 'DocQuality — ISO-aligned compliance engine',
};

export default function ComplianceApp() {
  return <WorkspaceApp config={complianceConfig} />;
}