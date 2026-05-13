/* Tiny visualization primitives — sparkline, area chart, bar histogram */

const Sparkline = ({ points, color = "var(--accent)", w = 88, h = 36, area = true, full = false }) => {
  if (!points || points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const stepX = w / (points.length - 1);
  const pts = points.map((v, i) => `${i * stepX},${h - ((v - min) / range) * (h - 4) - 2}`).join(" ");
  const areaPts = `0,${h} ${pts} ${w},${h}`;
  return (
    <svg width={full ? "100%" : w} height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio={full ? "none" : "xMidYMid meet"} style={{ display: "block" }}>
      {area && <polyline points={areaPts} fill={color} opacity="0.14" />}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

const AreaChart = ({ data, height = 220, color = "var(--accent)", showAxis = true }) => {
  // data: [{i, v}]
  const w = 1000;
  const padL = 38, padR = 8, padT = 14, padB = 22;
  const vw = w - padL - padR;
  const vh = height - padT - padB;
  const vals = data.map(d => d.v);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const stepX = vw / (data.length - 1);
  const startV = data[0].v;
  const endV   = data[data.length - 1].v;
  const isPos  = endV >= startV;
  const stroke = isPos ? "var(--pos)" : "var(--neg)";
  const fillCls = isPos ? "area-pos" : "area-neg";
  const lineCls = isPos ? "line-pos" : "line-neg";

  const pts = data.map((d, i) => [padL + i * stepX, padT + vh - ((d.v - min) / range) * vh]);
  const ptStr = pts.map(p => p.join(",")).join(" ");
  const areaStr = `${padL},${padT + vh} ${ptStr} ${padL + vw},${padT + vh}`;

  // gridlines (4 horizontal)
  const gridYs = [0.25, 0.5, 0.75].map(p => padT + vh * p);
  const labels = [max, min + range * 0.5, min].map(v => v.toFixed(0));

  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} preserveAspectRatio="none" style={{display:"block"}}>
      {showAxis && gridYs.map((y, i) => (
        <g key={i}>
          <line x1={padL} x2={w - padR} y1={y} y2={y} className="grid-line" strokeDasharray="2 4"/>
          <text x={padL - 6} y={y + 3} textAnchor="end" className="axis-tick">{labels[i]}</text>
        </g>
      ))}
      <polygon points={areaStr} className={fillCls} />
      <polyline points={ptStr} className={lineCls} />
      {/* end dot */}
      {pts.length && <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="3.5" fill={stroke} stroke="var(--bg)" strokeWidth="1.5"/>}
    </svg>
  );
};

const StackedBars = ({ data, height = 130 }) => {
  // data: [{h, buy, sell, hold}]
  const w = 800;
  const padL = 26, padR = 8, padT = 8, padB = 22;
  const vw = w - padL - padR;
  const vh = height - padT - padB;
  const totals = data.map(d => d.buy + d.sell + d.hold);
  const max = Math.max(...totals) || 1;
  const barW = (vw / data.length) * 0.65;
  const gap  = (vw / data.length) * 0.35;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} preserveAspectRatio="none" style={{display:"block"}}>
      <line x1={padL} x2={w-padR} y1={padT+vh} y2={padT+vh} className="grid-line"/>
      {data.map((d, i) => {
        const x = padL + i * (barW + gap) + gap/2;
        const total = d.buy + d.sell + d.hold;
        const hHold = (d.hold / max) * vh;
        const hSell = (d.sell / max) * vh;
        const hBuy  = (d.buy  / max) * vh;
        let y = padT + vh;
        const segs = [];
        // bottom = hold (muted), middle = sell (red), top = buy (green)
        y -= hHold; segs.push(<rect key="h" x={x} y={y} width={barW} height={hHold} fill="oklch(40% 0.012 250)"/>);
        y -= hSell; segs.push(<rect key="s" x={x} y={y} width={barW} height={hSell} fill="var(--neg)" opacity="0.85"/>);
        y -= hBuy;  segs.push(<rect key="b" x={x} y={y} width={barW} height={hBuy}  fill="var(--pos)" opacity="0.95"/>);
        return (
          <g key={i}>
            {segs}
            {i % 3 === 0 && <text x={x + barW/2} y={padT + vh + 14} textAnchor="middle" className="axis-tick">{String(d.h).padStart(2, '0')}</text>}
          </g>
        );
      })}
    </svg>
  );
};

const Donut = ({ value, label, color = "var(--accent)", size = 88, stroke = 10 }) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--surface-hi)" strokeWidth={stroke}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
                strokeDasharray={`${c * pct} ${c}`} transform={`rotate(-90 ${size/2} ${size/2})`}/>
      </svg>
      <div style={{ position:"absolute", inset:0, display:"grid", placeItems:"center", fontFamily:"var(--mono)", fontSize:13, color:"var(--text)" }}>
        {label}
      </div>
    </div>
  );
};

// fake sparkline data per symbol
const sparks = {
  AAPL:  [174, 175, 173, 176, 177, 175, 178, 176, 178, 179, 178],
  GOOGL: [148, 146, 145, 144, 143, 144, 142, 143, 141, 142, 142],
  MSFT:  [388, 386, 384, 383, 385, 382, 381, 380, 379, 381, 380],
  ASML:  [902, 906, 904, 908, 910, 909, 912, 913, 914, 913, 914],
  TSM:   [148, 149, 149, 150, 151, 150, 152, 152, 153, 152, 153],
  NVO:   [122, 121, 121, 120, 120, 119, 120, 119, 120, 119, 119],
};

Object.assign(window, { Sparkline, AreaChart, StackedBars, Donut, sparks });
