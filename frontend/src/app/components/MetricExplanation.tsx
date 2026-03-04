import * as Accordion from '@radix-ui/react-accordion';
import { ChevronDown } from 'lucide-react';

const metricExplanations = [
  {
    name: 'Completeness',
    description: 'Measures whether all required structured fields are present in the document. This ensures that no critical information is missing from the data extraction process.',
  },
  {
    name: 'Accuracy',
    description: 'Evaluates extracted data against validation logic and known constraints. This verifies that the extracted values are correct and match expected patterns or ranges.',
  },
  {
    name: 'Consistency',
    description: 'Checks logical relationships between fields to ensure they align correctly. For example, line items should sum to the total amount, or dates should follow a logical sequence.',
  },
  {
    name: 'Validity',
    description: 'Ensures values conform to expected formats and standards. This includes checking email formats, phone numbers, postal codes, and other structured data types.',
  },
  {
    name: 'Timeliness',
    description: 'Assesses the recency of time-sensitive fields. This is particularly important for documents with expiration dates or time-bound information.',
  },
  {
    name: 'Uniqueness',
    description: 'Identifies duplicate structured entries or data points. This helps prevent data redundancy and ensures each piece of information is unique within the document.',
  },
];

export function MetricExplanation() {
  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <Accordion.Root type="single" collapsible>
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
      </Accordion.Root>
    </div>
  );
}