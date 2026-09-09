/**
 * Layout do Sankey, separado do componente para poder ser testado sem
 * renderizar nada. Recebe os nos/links da API e devolve geometria pronta.
 */

import type { SankeyData } from '@/api/types';

export const NODE_WIDTH = 10;
export const NODE_GAP = 8;

export interface LaidOutNode {
  id: string;
  label: string;
  stage: number;
  value: number;
  x: number;
  y: number;
  height: number;
  outCursor: number;
  inCursor: number;
}

export interface Ribbon {
  key: string;
  path: string;
  thickness: number;
  fromStage: number;
}

export interface SankeyLayout {
  nodes: LaidOutNode[];
  ribbons: Ribbon[];
  scale: number;
}

export function buildLayout(data: SankeyData, width: number, height: number): SankeyLayout {
  const nodes = data.nodes.map((n) => ({ ...n, value: Number(n.value) }));
  const stages = [...new Set(nodes.map((n) => n.stage))].sort((a, b) => a - b);
  if (stages.length === 0) return { nodes: [], ribbons: [], scale: 0 };

  const stageTotals = stages.map((stage) =>
    nodes.filter((n) => n.stage === stage).reduce((sum, n) => sum + n.value, 0),
  );
  const stageCounts = stages.map((stage) => nodes.filter((n) => n.stage === stage).length);

  // Escala unica para todos os estagios: se cada coluna tivesse a sua, fitas de
  // valores diferentes apareceriam com a mesma espessura e o grafico mentiria.
  const maxGaps = Math.max(...stageCounts.map((count) => (count - 1) * NODE_GAP));
  const maxTotal = Math.max(...stageTotals, 1);
  const scale = Math.max(0, height - maxGaps) / maxTotal;

  const columnStep = stages.length > 1 ? (width - NODE_WIDTH) / (stages.length - 1) : 0;

  const laidOut: LaidOutNode[] = [];
  stages.forEach((stage, index) => {
    const stageNodes = nodes.filter((n) => n.stage === stage).sort((a, b) => b.value - a.value);
    const used =
      stageNodes.reduce((sum, n) => sum + n.value * scale, 0) + (stageNodes.length - 1) * NODE_GAP;
    let cursor = Math.max(0, (height - used) / 2);

    stageNodes.forEach((node) => {
      const nodeHeight = Math.max(2, node.value * scale);
      laidOut.push({
        ...node,
        x: index * columnStep,
        y: cursor,
        height: nodeHeight,
        outCursor: cursor,
        inCursor: cursor,
      });
      cursor += nodeHeight + NODE_GAP;
    });
  });

  const byId = new Map(laidOut.map((node) => [node.id, node]));
  const ribbons: Ribbon[] = [];

  data.links.forEach((link, index) => {
    const source = byId.get(link.source);
    const target = byId.get(link.target);
    if (!source || !target) return;

    const thickness = Math.max(1, Number(link.value) * scale);
    const sy0 = source.outCursor;
    const sy1 = sy0 + thickness;
    const ty0 = target.inCursor;
    const ty1 = ty0 + thickness;
    source.outCursor = sy1;
    target.inCursor = ty1;

    const x0 = source.x + NODE_WIDTH;
    const x1 = target.x;
    const cx = x0 + (x1 - x0) / 2;

    ribbons.push({
      key: `${link.source}->${link.target}-${index}`,
      path:
        `M ${x0} ${sy0} C ${cx} ${sy0}, ${cx} ${ty0}, ${x1} ${ty0} ` +
        `L ${x1} ${ty1} C ${cx} ${ty1}, ${cx} ${sy1}, ${x0} ${sy1} Z`,
      thickness,
      fromStage: source.stage,
    });
  });

  return { nodes: laidOut, ribbons, scale };
}
