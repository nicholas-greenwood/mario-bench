export const LEVEL_DISTANCE = 3168;

export type Replay = { id: string; score: number; seconds: number; seed: number };
export type Model = { id: string; name: string; score: number; cost: number; runs: Replay[] };

const entries = [
  { id: 'jev', name: 'JEV', score: 94.2, cost: 0.028 },
  { id: 'gpt', name: 'GPT-4.1', score: 81.6, cost: 0.094 },
  { id: 'claude', name: 'Claude Sonnet 4.5', score: 73.8, cost: 0.086 },
  { id: 'gemini', name: 'Gemini 2.5 Pro', score: 67.4, cost: 0.061 },
  { id: 'qwen', name: 'Qwen3-235B', score: 52.1, cost: 0.019 },
  { id: 'deepseek', name: 'DeepSeek V3', score: 44.8, cost: 0.012 },
];

export const MODELS: Model[] = entries.map((model, index) => ({
  ...model,
  runs: Array.from({ length: 10 }, (_, i) => ({
    id: `${model.id}-${i + 1}`,
    score: Math.round(Math.max(4, model.score - i * (4.1 + index * .7)) * 10) / 10,
    seconds: 28 + index * 5 + i * 3,
    seed: index * 17 + i * 7,
  })),
}));

export type Side = 'left' | 'right';
