import * as Accordion from '@radix-ui/react-accordion';
import { ChevronDown } from 'lucide-react';

// ── Generic metric definitions ────────────────────────────────────────────────

const metricExplanations = [
  {
    name: 'Completeness',
    description:
      'Measures whether all required structured fields are present in the document. This ensures that no critical information is missing from the data extraction process.',
  },
  {
    name: 'Accuracy',
    description:
      'Evaluates extracted data against validation logic and known constraints. This verifies that the extracted values are correct and match expected patterns or ranges.',
  },
  {
    name: 'Consistency',
    description:
      'Checks logical relationships between fields to ensure they align correctly. For example, line items should sum to the total amount, or dates should follow a logical sequence.',
  },
  {
    name: 'Validity',
    description:
      'Ensures values conform to expected formats and standards. This includes checking email formats, phone numbers, postal codes, and other structured data types.',
  },
  {
    name: 'Timeliness',
    description:
      'Assesses the recency of time-sensitive fields. This is particularly important for documents with expiration dates or time-bound information.',
  },
  {
    name: 'Uniqueness',
    description:
      'Identifies duplicate structured entries or data points. This helps prevent data redundancy and ensures each piece of information is unique within the document.',
  },
];

// ── Banking metric type (mirrors BankingMetricCard's interface) ───────────────

interface BankingMetricSummary {
  name: string;
  description: string;
  calculation_logic: string;
  risk_impact: string;
}

interface MetricExplanationProps {
  /** Banking domain name — when provided, triggers the domain-specific section. */
  bankingDomain?: string | null;
  /** Banking metrics to display in the domain-specific section. */
  bankingMetrics?: BankingMetricSummary[];
}

// ── Component ─────────────────────────────────────────────────────────────────

export function MetricExplanation({ bankingDomain, bankingMetrics }: MetricExplanationProps) {
  const hasBankingMetrics = bankingDomain && bankingMetrics && bankingMetrics.length > 0;

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <Accordion.Root type="multiple" defaultValue={[]}>

        {/* Generic quality dimensions */}
        <Accordion.Item value="explanations">
          <Accordion.Trigger className="flex items-center justify-between w-full group">
            <h2 className="text-xl sm:text-2xl font-semibold text-gray-900 text-left">
              How We Evaluate Document Quality
            </h2>
            <ChevronDown className="w-5 h-5 sm:w-6 sm:h-6 text-gray-500 transition-transform group-data-[state=open]:rotate-180 flex-shrink-0 ml-4" />
          </Accordion.Trigger>
          <Accordion.Content className="pt-6 data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up overflow-hidden">
            <div className="space-y-6">
              {metricExplanations.map((metric) => (
                <div key={metric.name}>
                  <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-2">
                    {metric.name}
                  </h3>
                  <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">
                    {metric.description}
                  </p>
                </div>
              ))}
            </div>
          </Accordion.Content>
        </Accordion.Item>

        {/* Banking-specific metrics — only rendered when a domain is detected */}
        {hasBankingMetrics && (
          <Accordion.Item value="banking" className="mt-4">
            <Accordion.Trigger className="flex items-center justify-between w-full group">
              <div className="text-left">
                <h2 className="text-xl sm:text-2xl font-semibold text-gray-900">
                  Banking-Specific Metrics
                  <span className="ml-2 text-sm font-normal text-[#1E3A8A]">
                    — {bankingDomain}
                  </span>
                </h2>
              </div>
              <ChevronDown className="w-5 h-5 sm:w-6 sm:h-6 text-gray-500 transition-transform group-data-[state=open]:rotate-180 flex-shrink-0 ml-4" />
            </Accordion.Trigger>

            <Accordion.Content className="pt-6 data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up overflow-hidden">
              {/* Blending model explainer */}
              <div className="mb-6 px-4 py-3 rounded-lg bg-[#1E3A8A]/5 border border-[#1E3A8A]/15">
                <p className="text-xs sm:text-sm text-[#1E3A8A] leading-relaxed">
                  <span className="font-semibold">Hybrid scoring model (70/30):</span> Each banking
                  metric is scored as{' '}
                  <span className="font-mono font-medium">
                    S = (D × 0.7) + (L × 0.3)
                  </span>
                  , where <span className="font-semibold">D</span> is the deterministic rule-engine
                  score and <span className="font-semibold">L</span> is the LLM semantic score.
                  This &quot;Rule-Anchored, AI-Nudged&quot; architecture ensures audit-grade
                  reliability while capturing contextual nuance.
                </p>
              </div>

              <div className="space-y-8">
                {bankingMetrics!.map((metric) => (
                  <div key={metric.name} className="border-b border-gray-100 pb-6 last:border-0 last:pb-0">
                    <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-3">
                      {metric.name}
                    </h3>

                    <div className="space-y-3">
                      <div>
                        <p className="text-xs font-semibold text-[#1E3A8A] uppercase tracking-wide mb-1">
                          What it measures
                        </p>
                        <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">
                          {metric.description}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs font-semibold text-[#1E3A8A] uppercase tracking-wide mb-1">
                          How it is calculated
                        </p>
                        <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">
                          {metric.calculation_logic}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs font-semibold text-[#DC2626] uppercase tracking-wide mb-1">
                          Risk impact
                        </p>
                        <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">
                          {metric.risk_impact}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Accordion.Content>
          </Accordion.Item>
        )}
      </Accordion.Root>
    </div>
  );
}
