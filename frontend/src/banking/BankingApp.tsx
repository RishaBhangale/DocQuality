import { WorkspaceApp, WorkspaceConfig } from '../core/WorkspaceApp';

const bankingConfig: WorkspaceConfig = {
  workspace: 'banking',
  title: 'Banking Intelligence',
  subtitle: 'Automated Document Quality & Regulatory Compliance Analysis',
  theme: {
    primary: '#1E3A8A', // Deep Blue
    accent: '#3B82F6',
    gradient: 'from-[#1E3A8A] to-[#3B82F6]',
    chartStroke: '#3B82F6',
  },
  apiBaseUrl: '/banking/api',
  hasDomainMetrics: true,
  hasLegalHold: true,
  hasRemediation: true,
  hasPdfReport: true,
  hasLinkedStandards: true,
  analyticsShowSeverityPie: false,
};

export default function BankingApp() {
  return <WorkspaceApp config={bankingConfig} />;
}