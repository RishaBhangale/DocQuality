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
  /** Omit outer card + title (parent provides section chrome). */
  embedded?: boolean;
  strokeColor?: string;
  fillColor?: string;
}

export function MetricRadarChart({
  metrics,
  embedded,
  strokeColor = '#2563EB',
  fillColor = '#2563EB',
}: MetricRadarChartProps) {
  const data = metrics.map((m) => ({
    metric: m.name,
    score: m.score,
    fullMark: 100,
  }));

  const chart = (
    <div className={`w-full ${embedded ? 'h-[280px]' : 'h-[300px] sm:h-[350px]'}`}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="#E5E7EB" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: '#374151', fontSize: 11 }}
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
            formatter={(value: number) => [`${Number(value).toFixed(1)}%`, 'Score']}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke={strokeColor}
            fill={fillColor}
            fillOpacity={0.18}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );

  if (embedded) {
    return chart;
  }

  return (
    <div className="bg-white rounded-lg p-6 sm:p-8 shadow-sm border border-gray-100">
      <h3 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4">
        Metric Comparison
      </h3>
      {chart}
    </div>
  );
}
