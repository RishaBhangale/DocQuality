import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
} from 'recharts';

interface RadarMetric {
  name: string;
  score: number;
}

interface MetricRadarChartProps {
  metrics: RadarMetric[];
}

export function MetricRadarChart({ metrics }: MetricRadarChartProps) {
  const data = metrics.map((m) => ({
    metric: m.name,
    score: m.score,
    fullMark: 100,
  }));

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
        Metric Comparison
      </h3>
      <div className="w-full h-[300px] sm:h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
            <PolarGrid stroke="#E5E7EB" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: '#374151', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#9CA3AF', fontSize: 10 }}
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
            />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#1E3A8A"
              fill="#1E3A8A"
              fillOpacity={0.15}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
