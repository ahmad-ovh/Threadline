# Lantern Harbor — example design
The player earns passage by introducing themselves and repairing a lantern. Memory stores explicit events; rules authorize the outcome; dialogue explains the state; the canvas only renders it.

This is a new example built for Threadline, not THRESHOLD or a copy of its source. Its purpose is to prove source-backed feature navigation and live change tracking.

## Feature: remembered favors
`memory.js` records the event. `rules.js` gates permission. `dialogue.js` turns that state into a response. `main.js` connects the player to these modules.
