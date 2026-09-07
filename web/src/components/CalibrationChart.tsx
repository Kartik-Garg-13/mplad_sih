const SIZE = 220;
const PAD = 28;
const PLOT = SIZE - PAD * 2;

function toX(v: number) {
  return PAD + v * PLOT;
}
function toY(v: number) {
  return SIZE - PAD - v * PLOT;
}

export default function CalibrationChart({
  meanPredicted,
  fractionPositive,
}: {
  meanPredicted: number[];
  fractionPositive: number[];
}) {
  const points = meanPredicted.map((x, i) => [x, fractionPositive[i]] as const);
  const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${toX(x)} ${toY(y)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} role="img" aria-label="Calibration curve">
      {/* axes */}
      <line x1={PAD} y1={SIZE - PAD} x2={SIZE - PAD} y2={SIZE - PAD} stroke="#cbd5e1" />
      <line x1={PAD} y1={PAD} x2={PAD} y2={SIZE - PAD} stroke="#cbd5e1" />
      {/* perfect-calibration diagonal */}
      <line x1={toX(0)} y1={toY(0)} x2={toX(1)} y2={toY(1)} stroke="#e2e8f0" strokeDasharray="4 3" />
      <text x={toX(1) - 4} y={toY(1) - 6} fontSize="8" fill="#94a3b8" textAnchor="end">
        perfect
      </text>
      {/* model curve */}
      <path d={path} fill="none" stroke="#6366f1" strokeWidth={1.5} />
      {points.map(([x, y], i) => (
        <circle key={i} cx={toX(x)} cy={toY(y)} r={2.5} fill="#6366f1" />
      ))}
      <text x={SIZE / 2} y={SIZE - 6} fontSize="8" fill="#94a3b8" textAnchor="middle">
        predicted risk
      </text>
      <text x={10} y={SIZE / 2} fontSize="8" fill="#94a3b8" textAnchor="middle" transform={`rotate(-90 10 ${SIZE / 2})`}>
        actual stalled share
      </text>
    </svg>
  );
}
