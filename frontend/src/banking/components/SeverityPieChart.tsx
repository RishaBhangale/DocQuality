import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

interface Issue {
  fieldName: string;
  issueType: string;
  description: string;
  severity: 'good' | 'warning' | 'critical';
}

interface SeverityPieChartProps {
  issues: Issue[];
}

const SEVERITY_CONFIG = {
  critical: { label: 'Critical', color: '#DC2626' },
  warning: { label: 'Moderate', color: '#EAB308' },
  good: { label: 'Minor', color: '#16A34A' },
};

export function SeverityPieChart({ issues }: SeverityPieChartProps) {
  const counts: Record<string, number> = { critical: 0, warning: 0, good: 0 };
  issues.forEach((issue) => {
    if (counts[issue.severity] !== undefined) {
      counts[issue.severity]++;
    }
  });

  const data = Object.entries(SEVERITY_CONFIG)
    .map(([key, config]) => ({
      name: config.label,
      value: counts[key] || 0,
      color: config.color,
    }))
    .filter((d) => d.value > 0);

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
        <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
          Issue Distribution
        </h3>
        <div className="flex flex-col items-center justify-center py-12">
          <div className="w-14 h-14 rounded-full bg-[#16A34A]/10 flex items-center justify-center mb-3">
            <svg className="w-7 h-7 text-[#16A34A]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-base font-medium text-gray-900">No issues detected</p>
          <p className="text-sm text-gray-500 mt-1">Document passes all checks</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
        Issue Distribution
      </h3>
      <div className="w-full h-[300px] sm:h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ left: 20, right: 20, top: 10, bottom: 10 }}>
            <Pie
              data={data}
              cx="50%"
              cy="45%"
              innerRadius={55}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              strokeWidth={0}
              label={({ name, value, cx, cy, midAngle, outerRadius: or2 }) => {
                const RADIAN = Math.PI / 180;
                const radius = or2 + 22;
                const x = cx + radius * Math.cos(-midAngle * RADIAN);
                const y = cy + radius * Math.sin(-midAngle * RADIAN);
                return (
                  <text x={x} y={y} textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={12} fontWeight={600} fill="#374151">
                    {name} ({value})
                  </text>
                );
              }}
              labelLine={{ stroke: '#9CA3AF', strokeWidth: 1 }}
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: '#FFFFFF',
                border: '1px solid #E5E7EB',
                borderRadius: '8px',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                fontSize: '13px',
              }}
              formatter={(value: number, name: string) => [
                `${value} issue${value !== 1 ? 's' : ''}`,
                name,
              ]}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              iconType="circle"
              iconSize={10}
              formatter={(value) => (
                <span style={{ color: '#374151', fontSize: '13px' }}>{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
