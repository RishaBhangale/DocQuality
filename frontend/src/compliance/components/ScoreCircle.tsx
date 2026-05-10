interface ScoreCircleProps {
  score: number;
  disableAnimation?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function ScoreCircle({ score, disableAnimation, size = 'lg' }: ScoreCircleProps) {
  const getColor = (score: number) => {
    if (score >= 90) return '#16A34A';
    if (score >= 70) return '#EAB308';
    return '#DC2626';
  };

  const color = getColor(score);
  const circumference = 2 * Math.PI * 70;
  const strokeDashoffset = Math.max(0, circumference - (score / 100) * circumference);

  const sizeClasses = {
    sm: "w-16 h-16 sm:w-24 sm:h-24",
    md: "w-24 h-24 sm:w-32 sm:h-32",
    lg: "w-32 h-32 sm:w-40 sm:h-40"
  };

  const textClasses = {
    sm: "text-2xl sm:text-3xl",
    md: "text-3xl sm:text-4xl",
    lg: "text-4xl sm:text-5xl"
  };

  const subtextClasses = {
    sm: "text-xs sm:text-sm",
    md: "text-sm sm:text-base",
    lg: "text-base sm:text-lg"
  };

  return (
    <div className={`relative ${sizeClasses[size]}`}>
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 160 160">
        <circle
          cx="80"
          cy="80"
          r="70"
          fill="none"
          stroke="#E5E7EB"
          strokeWidth="10"
        />
        <circle
          cx="80"
          cy="80"
          r="70"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className={disableAnimation ? "" : "transition-all duration-1000 ease-out"}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-bold text-gray-900 leading-none ${textClasses[size]}`}>{score}</span>
        <span className={`text-gray-500 leading-tight ${subtextClasses[size]}`}>/100</span>
      </div>
    </div>
  );
}