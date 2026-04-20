import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';

interface MetricBarData {
  name: string;
  score: number;
  status: 'good' | 'warning' | 'critical';
}

interface MetricBarChartProps {
  metrics: MetricBarData[];
}

const STATUS_COLORS = {
  good: '#16A34A',
  warning: '#EAB308',
  critical: '#DC2626',
};

export function MetricBarChart({ metrics }: MetricBarChartProps) {
  const data = metrics.map((m) => ({
    name: m.name,
    score: m.score,
    fill: STATUS_COLORS[m.status] || '#1E3A8A',
  }));

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
        Metric Scores
      </h3>
      <div className="w-full h-[300px] sm:h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
            <XAxis
              dataKey="name"
              tick={{ fill: '#374151', fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: '#E5E7EB' }}
              angle={-35}
              textAnchor="end"
              interval={0}
              height={60}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#9CA3AF', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#E5E7EB' }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#FFFFFF',
                border: '1px solid #E5E7EB',
                borderRadius: '8px',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                fontSize: '13px',
              }}
              formatter={(value: number) => [`${value}%`, 'Score']}
              cursor={{ fill: 'rgba(30, 58, 138, 0.05)' }}
            />
            <Bar dataKey="score" radius={[6, 6, 0, 0]} maxBarSize={50}>
              {data.map((entry, index) => (
                <Cell key={`bar-${index}`} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
