import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import story from "./story.json";

export const FPS = 30;
export const DURATION_FRAMES = 22 * FPS;

type Row = { t: number; truth: [number, number, number]; reported: [number, number] };
type Run = {
  rows: Row[];
  farthest_from_start_m: number;
  approved_rel_s: number | null;
  touchdown_rel_s: number | null;
  end_rel_s: number;
};
const RUNS = story.runs as unknown as { none: Run; land: Run };

const C = {
  bg: "#070b12",
  panel: "#0c121c",
  line: "#1b2736",
  text: "#e8eef7",
  muted: "#8b9ab0",
  truth: "#4cd6ff",
  believed: "#ffb020",
  bad: "#ff4d57",
  ok: "#3ddc97",
};
const FONT = "-apple-system, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif";
const MONO = "'SF Mono', Menlo, Consolas, monospace";

// video seconds -> simulated seconds relative to the fault (the clock on screen says which)
const TIME_MAP: [number, number][] = [
  [0, -8],
  [5.4, -8],
  [6.2, 0],
  [7.0, 0],
  [12.0, 24.3],
  [18.0, 173],
  [22, 173],
];
const simTime = (videoS: number) =>
  interpolate(videoS, TIME_MAP.map((p) => p[0]), TIME_MAP.map((p) => p[1]), { extrapolateRight: "clamp" });

const at = (run: Run, rel: number) => {
  const i = Math.max(0, Math.min(run.rows.length - 1, Math.round((rel - run.rows[0].t) / 0.5)));
  return run.rows[i];
};
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
const fade = (v: number, a: number, b: number) => clamp((v - a) / (b - a), 0, 1);
const km = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`);
const clock = (s: number) => {
  const a = Math.abs(Math.round(s));
  return `${s < 0 ? "-" : "+"}${Math.floor(a / 60)}:${String(a % 60).padStart(2, "0")}`;
};

const W = 1000;
const H = 650;
const LEVELS = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000];

function Panel({ run, rel, kind }: { run: Run; rel: number; kind: "none" | "land" }) {
  const now = at(run, rel);
  const upto = run.rows.filter((r) => r.t <= rel);
  const frozen = at(run, 0).reported;
  const pts: [number, number][] = [[0, 0], frozen, ...upto.map((r) => [r.truth[0], r.truth[1]] as [number, number])];
  const minX = Math.min(...pts.map((p) => p[0]));
  const maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1]));
  const maxY = Math.max(...pts.map((p) => p[1]));
  const bw = Math.max(maxX - minX, 160);
  const bh = Math.max(maxY - minY, 160);
  const scale = Math.min((W * 0.78) / bw, (H * 0.58) / bh);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const sx = (x: number) => W / 2 + (x - cx) * scale;
  const sy = (y: number) => H / 2 + 50 - (y - cy) * scale;

  const grid: React.JSX.Element[] = [];
  for (const L of LEVELS) {
    const px = L * scale;
    const o = fade(px, 28, 90) * (1 - fade(px, 420, 700)) * 0.22;
    if (o <= 0.005) continue;
    const x0 = Math.floor((cx - W / 2 / scale) / L) * L;
    const y0 = Math.floor((cy - H / 2 / scale) / L) * L;
    for (let x = x0; sx(x) < W; x += L) grid.push(<line key={`x${L}-${x}`} x1={sx(x)} x2={sx(x)} y1={0} y2={H} stroke="#6f8bb0" strokeOpacity={o} />);
    for (let y = y0; sy(y) > 0; y += L) grid.push(<line key={`y${L}-${y}`} x1={0} x2={W} y1={sy(y)} y2={sy(y)} stroke="#6f8bb0" strokeOpacity={o} />);
  }
  // scale bar: the largest level that fits in 40 percent of the width
  const bar = [...LEVELS].reverse().find((L) => L * scale < W * 0.4) ?? 10;

  const trail = upto.map((r) => `${sx(r.truth[0]).toFixed(1)},${sy(r.truth[1]).toFixed(1)}`).join(" ");
  const afterFault = rel >= 0;
  const landed = run.touchdown_rel_s !== null && rel >= run.touchdown_rel_s;
  const dist = Math.hypot(now.truth[0], now.truth[1]);
  const color = landed ? C.ok : C.truth;
  const approvedAgo = run.approved_rel_s === null ? null : rel - run.approved_rel_s;
  const pulse = (rel * 1.6) % 1;
  const danger = kind === "none" && afterFault ? fade(rel, 8, 60) : 0;

  return (
    <div style={{ position: "relative", width: W, height: H, background: C.panel, border: `2px solid ${danger > 0.05 ? C.bad : C.line}`, overflow: "hidden", boxShadow: danger > 0 ? `inset 0 0 ${60 * danger}px rgba(255,77,87,${0.35 * danger})` : "none" }}>
      <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id={`glow-${kind}`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>
        {grid}
        <circle cx={sx(0)} cy={sy(0)} r={5} fill="none" stroke={C.muted} strokeWidth={2} />
        <text x={sx(0) + 12} y={sy(0) + 5} fill={C.muted} fontSize={22} fontFamily={FONT}>launch</text>
        {trail.length > 0 && (
          <>
            <polyline points={trail} fill="none" stroke={color} strokeWidth={9} strokeOpacity={0.55} filter={`url(#glow-${kind})`} strokeLinejoin="round" />
            <polyline points={trail} fill="none" stroke={color} strokeWidth={3.5} strokeLinejoin="round" />
          </>
        )}
        {afterFault && (
          <>
            <line x1={sx(frozen[0])} y1={sy(frozen[1])} x2={sx(now.truth[0])} y2={sy(now.truth[1])} stroke={C.believed} strokeWidth={2.5} strokeDasharray="10 8" strokeOpacity={0.8} />
            <circle cx={sx(frozen[0])} cy={sy(frozen[1])} r={14 + pulse * 26} fill="none" stroke={C.believed} strokeOpacity={(1 - pulse) * 0.7} strokeWidth={3} />
            <circle cx={sx(frozen[0])} cy={sy(frozen[1])} r={13} fill={C.bg} stroke={C.believed} strokeWidth={4} />
            <text x={sx(frozen[0])} y={sy(frozen[1]) + 48} fill={C.believed} fontSize={26} fontFamily={FONT} fontWeight={600} textAnchor="middle">where it says it is</text>
          </>
        )}
        <circle cx={sx(now.truth[0])} cy={sy(now.truth[1])} r={22} fill={color} fillOpacity={0.35} filter={`url(#glow-${kind})`} />
        <circle cx={sx(now.truth[0])} cy={sy(now.truth[1])} r={10} fill={color} />
        {approvedAgo !== null && approvedAgo >= 0 && approvedAgo < 1.5 && (
          <circle cx={sx(now.truth[0])} cy={sy(now.truth[1])} r={20 + approvedAgo * 120} fill="none" stroke={C.ok} strokeWidth={4} strokeOpacity={1 - approvedAgo / 1.5} />
        )}
        <line x1={W - 24 - bar * scale} x2={W - 24} y1={H - 28} y2={H - 28} stroke={C.muted} strokeWidth={3} />
        <text x={W - 24} y={H - 38} fill={C.muted} fontSize={22} fontFamily={MONO} textAnchor="end">{km(bar)}</text>
      </svg>

      <div style={{ position: "absolute", top: 20, left: 24, right: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-start", fontFamily: FONT }}>
        <div>
          <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: 1.5, color: C.text }}>{kind === "none" ? "NOBODY ACTS" : "A PERSON APPROVES LAND"}</div>
          <div style={{ fontSize: 24, color: C.muted, marginTop: 4, height: 30 }}>
            {kind === "land" && approvedAgo !== null && approvedAgo >= 0 && !landed && "LAND approved, descending"}
            {kind === "land" && landed && "On the ground"}
            {kind === "none" && afterFault && rel > 12 && "Still flying, still reporting the old position"}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: MONO, fontSize: 64, fontWeight: 600, color: landed ? C.ok : danger > 0.3 ? C.bad : C.text, lineHeight: 1 }}>{km(dist)}</div>
          <div style={{ fontSize: 22, color: C.muted, marginTop: 4 }}>from launch</div>
        </div>
      </div>
    </div>
  );
}


const FREEZE_S = 1.6;
const SPEED = 250; // px per second along the route

// a map-app route: bottom left up to top right, sampled once
const ROUTE: { x: number; y: number; d: number }[] = (() => {
  const P = [[150, 1230], [150, 700], [850, 760], [850, 170]];
  const pts: { x: number; y: number; d: number }[] = [];
  let d = 0;
  for (let i = 0; i <= 240; i++) {
    const u = i / 240;
    const b = (k: number) => {
      const m = 1 - u;
      return m * m * m * P[0][k] + 3 * m * m * u * P[1][k] + 3 * m * u * u * P[2][k] + u * u * u * P[3][k];
    };
    const x = b(0);
    const y = b(1);
    if (i > 0) d += Math.hypot(x - pts[i - 1].x, y - pts[i - 1].y);
    pts.push({ x, y, d });
  }
  return pts;
})();
const ROUTE_LEN = ROUTE[ROUTE.length - 1].d;
const routeAt = (dist: number) => {
  const dd = clamp(dist, 0, ROUTE_LEN);
  const k = ROUTE.findIndex((p) => p.d >= dd);
  if (k <= 0) return ROUTE[0];
  const a = ROUTE[k - 1];
  const b = ROUTE[k];
  const f = (dd - a.d) / Math.max(b.d - a.d, 1e-9);
  return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, d: dd };
};
const TUNNEL_FROM = SPEED * FREEZE_S; // the dot freezes where the tunnel begins
const TUNNEL_TO = ROUTE_LEN * 0.8;

/** The analogy: a map app's dot freezes in a tunnel while you keep moving. Same symbols as the
 * drone panels: the ring is what the app shows, the dot is where you really are. Not data. */
function MapAnalogy({ s }: { s: number }) {
  const real = routeAt(s * SPEED);
  const shown = routeAt(Math.min(s * SPEED, TUNNEL_FROM));
  const frozen = s >= FREEZE_S;
  const pulse = frozen ? (s * 1.4) % 1 : 0;
  const gap = fade(s, FREEZE_S + 0.3, FREEZE_S + 1.0);
  const line = (a: number, b: number) =>
    ROUTE.filter((p) => p.d >= a && p.d <= b).map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const portal = (dist: number) => {
    const a = routeAt(dist - 6);
    const b = routeAt(dist + 6);
    const nx = -(b.y - a.y);
    const ny = b.x - a.x;
    const n = Math.hypot(nx, ny) || 1;
    const c = routeAt(dist);
    return { x1: c.x + (nx / n) * 34, y1: c.y + (ny / n) * 34, x2: c.x - (nx / n) * 34, y2: c.y - (ny / n) * 34 };
  };
  const inn = portal(TUNNEL_FROM);
  const out = portal(TUNNEL_TO);
  const mid = routeAt((TUNNEL_FROM + TUNNEL_TO) / 2);
  return (
    <div style={{ position: "relative", width: W, height: 1330, background: C.panel, border: `2px solid ${C.line}`, overflow: "hidden", fontFamily: FONT }}>
      <svg width={W} height={1330} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id="ma-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" /></filter>
        </defs>
        {Array.from({ length: 11 }, (_, i) => <line key={`h${i}`} x1={0} x2={W} y1={i * 133} y2={i * 133} stroke="#6f8bb0" strokeOpacity={0.09} />)}
        {Array.from({ length: 8 }, (_, i) => <line key={`v${i}`} y1={0} y2={1330} x1={i * 143} x2={i * 143} stroke="#6f8bb0" strokeOpacity={0.09} />)}
        {/* the road, and the tunnel as a covered stretch */}
        <polyline points={line(0, ROUTE_LEN)} fill="none" stroke="#1e2b3d" strokeWidth={34} strokeLinecap="round" strokeLinejoin="round" />
        <polyline points={line(0, ROUTE_LEN)} fill="none" stroke="#3b4d66" strokeWidth={4} strokeDasharray="22 18" />
        <polyline points={line(TUNNEL_FROM, TUNNEL_TO)} fill="none" stroke="#05080d" strokeWidth={50} strokeLinecap="butt" strokeLinejoin="round" />
        <polyline points={line(TUNNEL_FROM, TUNNEL_TO)} fill="none" stroke="#56677f" strokeWidth={4} strokeDasharray="10 14" />
        {[inn, out].map((q, k) => <line key={k} {...q} stroke="#8aa0bd" strokeWidth={8} strokeLinecap="round" />)}
        <text x={mid.x + 54} y={mid.y + 8} fill="#8aa0bd" fontSize={34} fontWeight={700} letterSpacing={3}>TUNNEL</text>
        {/* what the app shows, and where you really are */}
        {frozen && <line x1={shown.x} y1={shown.y} x2={real.x} y2={real.y} stroke={C.believed} strokeWidth={3} strokeDasharray="10 9" strokeOpacity={0.85 * gap} />}
        <circle cx={shown.x} cy={shown.y} r={26 + pulse * 30} fill="none" stroke={C.believed} strokeOpacity={frozen ? (1 - pulse) * 0.5 : 0} strokeWidth={3} />
        <circle cx={shown.x} cy={shown.y} r={26} fill="none" stroke={C.believed} strokeWidth={6} />
        <circle cx={real.x} cy={real.y} r={26} fill={C.truth} fillOpacity={0.4} filter="url(#ma-glow)" />
        <circle cx={real.x} cy={real.y} r={12} fill={C.truth} />
      </svg>
      <div style={{ position: "absolute", top: 22, left: 26, display: "flex", flexDirection: "column", gap: 14, fontSize: 30, fontWeight: 600 }}>
        <div style={{ color: C.truth }}>● where you really are</div>
        <div style={{ color: C.believed }}>◯ what the app shows</div>
      </div>
      <div style={{ position: "absolute", top: 26, right: 26, fontSize: 24, letterSpacing: 2, color: C.muted }}>ANALOGY, NOT DATA</div>
    </div>
  );
}

const Text = ({ children, from, to, size = 76, color = C.text, weight = 700 }: { children: React.ReactNode; from: number; to: number; size?: number; color?: string; weight?: number }) => {
  const f = useCurrentFrame() / FPS;
  const o = fade(f, from, from + 0.4) * (1 - fade(f, to - 0.4, to));
  const dy = (1 - fade(f, from, from + 0.4)) * 24;
  return (
    <div style={{ position: "absolute", left: 40, right: 40, top: 0, opacity: o, transform: `translateY(${dy}px)`, fontFamily: FONT, fontSize: size, fontWeight: weight, color, lineHeight: 1.08 }}>{children}</div>
  );
};

export const Story = () => {
  const frame = useCurrentFrame();
  const s = frame / FPS;
  const rel = simTime(s);
  const endCard = fade(s, 18.2, 18.9);
  const toDrone = fade(s, 5.0, 5.5);
  return (
    <AbsoluteFill style={{ background: C.bg, fontFamily: FONT, color: C.text }}>
      <div style={{ position: "absolute", left: 40, right: 40, top: 70, height: 230 }}>
        <Text from={0.2} to={2.6} size={68}>Your map app loses GPS in a tunnel.</Text>
        <Text from={0.9} to={2.6} size={44} weight={500} color={C.muted}>
          <div style={{ marginTop: 150 }}>The dot freezes. You keep moving.</div>
        </Text>
        <Text from={2.7} to={4.9} size={62}>No warning. The app still<br />looks fine. You are far ahead.</Text>
        <Text from={5.0} to={7.6}>The same thing<br />happens to a drone.</Text>
        <Text from={7.7} to={11.8} size={60}>No alarm fires: the frozen position still looks valid.</Text>
        <Text from={11.9} to={15.3} size={56}>The system notices:<br />other sensors disagree.<br />A person decides.</Text>
        <Text from={15.6} to={22} size={72}>Same fault.<br />Very different outcome.</Text>
      </div>

      <div style={{ position: "absolute", left: 0, right: 0, top: 900, textAlign: "center", zIndex: 5, fontSize: 120, fontWeight: 800, letterSpacing: 4, color: C.believed, opacity: fade(s, 6.15, 6.3) * (1 - fade(s, 6.7, 7.0)), textShadow: "0 0 40px rgba(255,176,32,0.8), 0 0 8px #000" }}>
        GPS FROZEN
      </div>

      <div style={{ position: "absolute", left: 40, top: 330, opacity: 1 - toDrone }}>
        <MapAnalogy s={s} />
      </div>
      <div style={{ position: "absolute", left: 40, top: 330, opacity: toDrone }}>
        <Panel run={RUNS.none} rel={Math.min(rel, RUNS.none.end_rel_s)} kind="none" />
      </div>
      <div style={{ position: "absolute", left: 40, top: 1010, opacity: toDrone }}>
        <Panel run={RUNS.land} rel={Math.min(rel, RUNS.land.end_rel_s)} kind="land" />
      </div>

      <div style={{ position: "absolute", left: 40, right: 40, top: 1690, height: 200 }}>
        <div style={{ fontFamily: MONO, fontSize: 40, color: C.text, opacity: toDrone }}>
          simulated time since the fault {clock(rel)}
        </div>
        <div style={{ marginTop: 18, fontSize: 25, lineHeight: 1.35, color: C.muted, opacity: 1 - endCard }}>
          {s < 5.2
            ? "An illustration to explain the idea. It is not footage and not data. The ring and the dot mean the same in the drone view."
            : "SIMULATION (PX4 SITL), recorded runs replayed. The operator is scripted: LAND 15 s after the fault."}
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 54, opacity: endCard, fontSize: 28, lineHeight: 1.4, color: C.text }}>
          Nothing moves without an operator's approval.
          <div style={{ color: C.muted, fontSize: 24, marginTop: 8 }}>
            One recorded run per action, one simulator. Furthest point from launch within 220 s. github.com/Telschow/nav-trust-c2
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
