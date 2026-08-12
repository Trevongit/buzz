# Core product vs operator skill packs

## Core (block/buzz and compatible forks)

Belongs in the monorepo when it is **product**:

- Relay, auth, event kinds, desktop/mobile UX  
- Managed agents, Remote Agents UI, place proof APIs  
- buzz-cli commands and stable contracts  
- Security, multi-tenant boundaries  

## Operator doctrine + skills (public pack repos)

Belongs in **versioned packs** when it is **how we run fleets**:

- Soft-wake watcher policies and stdout contract  
- Staff lifecycle scripts  
- Phone keys menus  
- Presence lease daemons  
- Multi-host install cards  
- Grok Build skill wrappers (use-buzz, GCR-style companions)  

## Why split?

If doctrine only lives in private dogfood, a public fork looks like “just another fork.”  

If everything is forced into core before contracts stabilize, upstream review freezes experimentation.

**Healthy pattern:** dogfood contracts in packs → document publicly → upstream the stable product pieces with design notes.

