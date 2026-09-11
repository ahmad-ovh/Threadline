export function canGrantPassage(memory) {
  return memory.introduced && memory.repaired && memory.trust >= 3;
}
