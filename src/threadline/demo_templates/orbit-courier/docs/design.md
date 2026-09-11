# Orbit Courier — example design
A turn-based grid game, intentionally different from Lantern Harbor. Each legal step uses energy. Cargo pickup and delivery are separate from movement and rendering. Win by carrying the cargo to the station before energy runs out.

Trace the Delivery loop feature to discover how core.js calls cargo.js, which depends on world/map.js. A literal import is observable evidence of a source reference, not proof that every possible runtime path uses it.
