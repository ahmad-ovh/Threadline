import { remember, memorySummary } from '../domain/memory.js';
import { canGrantPassage } from '../domain/rules.js';

export function respond(memory, action) {
  remember(memory, action);
  if (action === 'introduce') return 'Keeper: A name is a beginning. Our lantern still needs a careful hand.';
  if (action === 'repair') return 'Keeper: The harbor shines again. I will remember your help.';
  if (action === 'request' && canGrantPassage(memory)) {
    memory.granted = true;
    return 'Keeper: You have earned our trust. The boat is yours. Safe passage!';
  }
  if (action === 'request') return 'Keeper: Introduce yourself and help repair our lantern first.';
  return 'Keeper: Welcome, traveler. There is a boat leaving at dawn.';
}
export function explainMemory(memory) {
  return memorySummary(memory);
}
