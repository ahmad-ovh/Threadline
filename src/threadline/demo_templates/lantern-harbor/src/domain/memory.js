// State is explicit so developers can trace remembered actions into dialogue.
export function createMemory() {
  return { introduced: false, repaired: false, granted: false, trust: 0, events: [] };
}
export function remember(memory, action) {
  if (action === 'introduce' && !memory.introduced) {
    memory.introduced = true; memory.trust += 1;
    memory.events.push('The traveler introduced themselves.');
  }
  if (action === 'repair' && !memory.repaired) {
    memory.repaired = true; memory.trust += 2;
    memory.events.push('The traveler repaired the harbor lantern.');
  }
  return memory;
}
export function memorySummary(memory) {
  return memory.events.length ? memory.events.join(' ') : 'No shared history yet.';
}
