// Lightweight dependency-free ownership-graph visualization.
// Nodes are laid out left-to-right by depth (0 = beneficiary being paid,
// increasing depth = owners further up the chain). Edges point from an owner
// to the company it controls, labelled with the direct ownership %.

const COL = 230 // horizontal gap between depth columns
const ROW = 96 // vertical gap between sibling nodes
const NODE_W = 178
const NODE_H = 70
const PAD = 24

export default function OwnershipGraph({ graph, onNodeClick, selectedName }) {
  const nodes = graph?.nodes ?? []
  const edges = graph?.edges ?? []

  if (!nodes.length) {
    return <p className="status">No ownership structure on record for this party.</p>
  }

  // Group nodes by depth so we can place each depth in its own column.
  const byDepth = {}
  for (const n of nodes) (byDepth[n.depth] ??= []).push(n)
  const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b)
  const maxRows = Math.max(...depths.map((d) => byDepth[d].length))

  const width = PAD * 2 + (depths.length - 1) * COL + NODE_W
  const height = PAD * 2 + (maxRows - 1) * ROW + NODE_H

  // Position (top-left corner) per node id, vertically centred within its column.
  const pos = {}
  depths.forEach((d, di) => {
    const col = byDepth[d]
    const colH = (col.length - 1) * ROW
    const y0 = (height - NODE_H) / 2 - colH / 2
    col.forEach((n, ri) => {
      pos[n.id] = { x: PAD + di * COL, y: y0 + ri * ROW }
    })
  })

  const center = (id) => {
    const p = pos[id]
    return { cx: p.x + NODE_W / 2, cy: p.y + NODE_H / 2 }
  }

  return (
    <div className="graph-scroll">
      <svg
        className="ownership-graph"
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        role="img"
        aria-label="Beneficial ownership graph"
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Edges: owner (from, higher depth) -> company (to, lower depth) */}
        {edges.map((e, i) => {
          const from = pos[e.from]
          const to = pos[e.to]
          if (!from || !to) return null
          const a = center(e.from)
          const b = center(e.to)
          // Connect from the owner's left edge to the company's right edge.
          const x1 = from.x
          const y1 = a.cy
          const x2 = to.x + NODE_W
          const y2 = b.cy
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2
          return (
            <g key={`e-${i}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                className="graph-edge"
                markerEnd="url(#arrow)"
              />
              {e.ownership_pct != null && (
                <g>
                  <rect
                    x={mx - 18}
                    y={my - 11}
                    width="36"
                    height="18"
                    rx="9"
                    className="graph-edge-label-bg"
                  />
                  <text x={mx} y={my + 3} className="graph-edge-label" textAnchor="middle">
                    {e.ownership_pct}%
                  </text>
                </g>
              )}
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map((n) => {
          const p = pos[n.id]
          const flagged = n.is_flagged
          const selected = n.name === selectedName
          return (
            <foreignObject key={n.id} x={p.x} y={p.y} width={NODE_W} height={NODE_H}>
              <div
                className={`graph-node ${flagged ? 'flagged' : ''} ${selected ? 'selected' : ''}`}
                onClick={() => onNodeClick?.(n)}
                title={`Click to see what ${n.name} controls`}
              >
                <div className="graph-node-name">{n.name}</div>
                <div className="graph-node-meta">
                  <span>{n.depth === 0 ? 'beneficiary' : `depth ${n.depth}`}</span>
                  {n.effective_pct != null && <span>{n.effective_pct}% eff.</span>}
                  {flagged && <span className="graph-node-risk">{n.risk}</span>}
                </div>
              </div>
            </foreignObject>
          )
        })}
      </svg>
    </div>
  )
}
