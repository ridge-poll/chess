function cacheKey(fen, multipv) {
  return `${fen}\u0000${multipv}`;
}

export class ProgressiveEngineRegistry {
  constructor() {
    this.channels = new Map();
    this.cache = new Map();
    this.sequence = 0;
  }

  peek(fen, targetDepth, multipv = 2) {
    const snapshots = this.cache.get(cacheKey(fen, multipv)) || [];
    return snapshots
      .filter((snapshot) => Number(snapshot.depth) <= Number(targetDepth))
      .sort((left, right) => Number(right.depth) - Number(left.depth))[0] || null;
  }

  begin(channel, { fen, targetDepth, multipv = 2 }) {
    this.cancel(channel);
    const id = `${channel}-${++this.sequence}`;
    const controller = new AbortController();
    this.channels.set(channel, { id, fen, targetDepth, multipv, controller });
    return { id, signal: controller.signal, cached: this.peek(fen, targetDepth, multipv) };
  }

  accept(channel, id, snapshot) {
    const active = this.channels.get(channel);
    if (!active || active.id !== id || active.fen !== snapshot.fen) return false;
    const key = cacheKey(snapshot.fen, active.multipv);
    const snapshots = this.cache.get(key) || [];
    const withoutDepth = snapshots.filter((item) => Number(item.depth) !== Number(snapshot.depth));
    this.cache.set(key, [...withoutDepth, snapshot]);
    return true;
  }

  isCurrent(channel, id) {
    return this.channels.get(channel)?.id === id;
  }

  cancel(channel) {
    this.channels.get(channel)?.controller.abort();
    this.channels.delete(channel);
  }
}

export async function consumeNdjson(response, onValue) {
  if (!response.body) throw new Error("Streaming response is unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) await onValue(JSON.parse(line));
    }
    if (done) break;
  }
  if (buffer.trim()) await onValue(JSON.parse(buffer));
}
