// ─────────────────────────────────────────────────────────────────────────────
// core/dependency-graph.ts
// Topological sort and cycle detection for domain execution ordering.
// Used by the orchestrator to resolve dependsOn declarations.
// ─────────────────────────────────────────────────────────────────────────────

export interface GraphNode {
  name: string;
  dependsOn: string[];
}

export interface SortResult {
  ok: boolean;
  /** Execution order — safe to run sequentially in this order. */
  order: string[];
  /** Populated when ok = false. Lists the cycle as a readable path. */
  cycle?: string[];
  /** Domain names referenced in dependsOn that are not in the graph. */
  missing: string[];
}

/**
 * Performs a topological sort (Kahn's algorithm) on a set of domain nodes.
 * Returns the safe execution order and reports any cycles or missing deps.
 */
export function topologicalSort(nodes: GraphNode[]): SortResult {
  const names = new Set(nodes.map((n) => n.name));
  const missing: string[] = [];

  // Check for missing dependency references
  for (const node of nodes) {
    for (const dep of node.dependsOn) {
      if (!names.has(dep)) {
        missing.push(`${node.name} → ${dep} (not found)`);
      }
    }
  }

  // Build adjacency map and in-degree count
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  for (const node of nodes) {
    if (!inDegree.has(node.name)) inDegree.set(node.name, 0);
    if (!adjacency.has(node.name)) adjacency.set(node.name, []);
  }

  for (const node of nodes) {
    for (const dep of node.dependsOn) {
      if (!names.has(dep)) continue; // Skip missing — already reported
      const depAdj = adjacency.get(dep) ?? [];
      depAdj.push(node.name);
      adjacency.set(dep, depAdj);
      inDegree.set(node.name, (inDegree.get(node.name) ?? 0) + 1);
    }
  }

  // Kahn's algorithm
  const queue: string[] = [];
  for (const [name, degree] of inDegree) {
    if (degree === 0) queue.push(name);
  }

  const order: string[] = [];
  while (queue.length > 0) {
    const current = queue.shift()!;
    order.push(current);

    for (const neighbour of adjacency.get(current) ?? []) {
      const newDegree = (inDegree.get(neighbour) ?? 1) - 1;
      inDegree.set(neighbour, newDegree);
      if (newDegree === 0) queue.push(neighbour);
    }
  }

  if (order.length !== nodes.length) {
    // Cycle detected — find it via DFS
    const cycle = findCycle(nodes);
    return { ok: false, order: [], cycle, missing };
  }

  return { ok: true, order, missing };
}

/**
 * DFS-based cycle finder. Returns the cycle as a readable path string array.
 * Called only when Kahn's algorithm detects a cycle.
 */
function findCycle(nodes: GraphNode[]): string[] {
  const visited = new Set<string>();
  const stack = new Set<string>();
  const depMap = new Map(nodes.map((n) => [n.name, n.dependsOn]));

  function dfs(name: string, path: string[]): string[] | null {
    if (stack.has(name)) {
      const cycleStart = path.indexOf(name);
      return path.slice(cycleStart).concat(name);
    }
    if (visited.has(name)) return null;

    visited.add(name);
    stack.add(name);

    for (const dep of depMap.get(name) ?? []) {
      const result = dfs(dep, [...path, name]);
      if (result) return result;
    }

    stack.delete(name);
    return null;
  }

  for (const node of nodes) {
    const cycle = dfs(node.name, []);
    if (cycle) return cycle;
  }

  return ["unknown cycle"];
}

/**
 * Formats a SortResult into human-readable diagnostic lines.
 * Used by the validate command and pre-flight check.
 */
export function formatSortDiagnostics(result: SortResult): string[] {
  const lines: string[] = [];

  if (result.missing.length > 0) {
    lines.push("Missing dependency references:");
    for (const m of result.missing) lines.push(`  ✗ ${m}`);
  }

  if (!result.ok && result.cycle) {
    lines.push("Circular dependency detected:");
    lines.push(`  ${result.cycle.join(" → ")}`);
  }

  return lines;
}
