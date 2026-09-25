# OSIRIS Companion — PUBG Ally translated into the Chatman ecosystem

**Date:** 2026-09-25  
**Repository:** seanchatmangpt/autofde-lab  
**Research input:** PUBG Ally: A Conversational Embodied Agent as an AI Teammate, arXiv:2609.29837  
**Fictional product reference:** Richard K. Morgan, Thin Air. OSIRIS expands to **Onboard Situational Insight and Resource Interface Support**.  
**Standing ceiling:** repository-local candidate kernel. This PR does not claim a live microphone, TTS, production BRCE connection, or external actuation.

## Translation

The reusable idea in PUBG Ally is not "put an LLM in a voice assistant." It is a split between an event-driven deliberation layer and a faster stateful control layer. The slow layer gets bounded observations and events, chooses speech and high-level intent, and carries only unfinished work forward. The fast layer owns admission, priority, interruption, freshness, and recovery.

For OSIRIS the split is stricter:

~~~
voice/runtime event
      |
      v
OSIRIS fast kernel
  bounded priority queue
  fresh observations only
  independent speech/action policy
  0/2/6/6 response budget
      |
      v
replaceable deliberator
  SELECT / CONSTRUCT only
      |
      +----> speech candidate
      |
      +----> typed action candidate
                  |
                  v
           BRCERequest(CANDIDATE)
                  |
           authority boundary
                  |
                  v
           BRCE.DO elsewhere
~~~

The paper's System 1 is not copied as one behavior tree. In this ecosystem its responsibilities can be factored across formal planners, GymAct rehearsal worlds, SA2A capability contracts, XaaS delivery, BRCE authority, and receipts/replay. OSIRIS owns the low-latency conversational kernel that binds those surfaces.

## Thin Air product shape, changed authority model

The fictional OSIRIS is useful as a product shape: an always-available situational and crisis-management companion attached to one person. This implementation intentionally does not reproduce its ambient authority. The companion may observe admitted state, speak, select or construct a candidate, and manufacture a request. Consequential DO remains external and receipted.

The default voice profile is executable configuration:

~~~
D/I/S/C = 0/2/6/6
max spoken response = 72 words

lead with changed state / changed edge / next executable step
compact, plainspoken, low social filler
do not infer emotion or motivation
preserve candidate != truth != authority != DO != standing
say UNKNOWN when evidence is absent or stale
prefer a falsifier or reusable mechanism over explanation
~~~

## Paper primitive → Chatman primitive

| PUBG Ally primitive | OSIRIS / Chatman translation |
|---|---|
| Event-driven System 2 | Replaceable Deliberator invoked from bounded admitted events |
| Stateful System 1 | Existing formal/runtime machinery; OSIRIS itself never owns DO |
| Bounded tool interface | Typed IntentKind → Surface router |
| Action availability | Candidate BRCERequest; authority resolved beyond this module |
| Speech/action reactivity | Independent ResponsePolicy per modality |
| Priority event queue | EventPriority plus bounded admission |
| Controlled proactivity | No action without an admitted trigger event |
| Recent observations | TTL-bound Observation; stale factual claim is refused |
| compact(plan) | Only carry_plan crosses the turn boundary |
| Action outcome event | Receipt and observation return into the next loop |
| Deployability rules | Deterministic refusal gates plus later GymAct/AutoFDE courts |
| Feedback-driven repair | OCEL → sJira → prior art/ggen → verification → permanent guard |

## Ecosystem routing

The kernel makes primary routes explicit so a deliberator does not rediscover portfolio topology on every turn.

| Intent | Primary surface | Role |
|---|---|---|
| PLAN | autofde-lab | planner league, hypothesis, formal planning |
| MESSAGE | sa2a | semantic/capability envelope |
| WORK | sjira | durable work/control-plane item |
| REUSE | ggen-marketplace | prior-art pack discovery/composition |
| MANUFACTURE | ggen | generated projection/artifact |
| REHEARSE | gymact | authorized simulation/rehearsal world |
| CLOUD_CAPABILITY | ash_kudzu | external/cloud capability surface |
| AGENT_INTEROP | ash_a2a | Ash-facing agent interoperability |
| PROCESS_EVIDENCE | wasm4pm | OCEL/process evidence and conformance |
| DELIVER | xaas | delivery/product/runtime plane |
| LIFE | lifegym | personal/life-world planning |
| DOCTRINE | godslaw | provenance-bound interpretive profile |
| MARKETPLACE | zoe-marketplace | ZOE opportunity/marketplace surface |
| ACTUATE | brce | sole authority-bearing DO route |

Every action candidate, including one targeting ggen, sJira, or XaaS, is emitted as a BRCERequest with standing=CANDIDATE. target_surface identifies the capability owner; route_surface=BRCE identifies the authorization path.

## Fast-loop invariants

1. No stale claims: speech may claim only fresh admitted observation keys.
2. No ambient proactivity: an action requires at least one admitted trigger event.
3. Independent modality policy: an event may require speech while forbidding action, or vice versa.
4. Bounded overload: higher-priority events survive queue pressure.
5. Bounded voice: 0/2/6/6 speech has a hard word budget.
6. No raw-state memory masquerading as continuity: events are consumed and observations must remain fresh; only explicit task obligations carry forward.
7. No companion DO: OSIRIS.cycle can return speech, BRCERequest, and CompanionReceipt; it has no executor method.
8. Deterministic receipts: identical subject/events/decision manufacture identical request and receipt identifiers.
9. Process projection: every turn receipt has an OCEL-shaped projection for wasm4pm/process mining.
10. Deliberator retirement remains possible: the kernel has no LLM dependency. A model can implement Deliberator now; HDDL, FOND, Datalog, SPARQL, ggen or native code can replace recurrent classes later.

## Portfolio loop

~~~
STT / keyboard / runtime event
        |
        v
OSIRIS event admission + priority + freshness
        |
        v
Deliberator
        |
        +--> voice candidate --> TTS
        |
        +--> typed intent
               |
               +--> SA2A capability semantics
               +--> AutoFDE plan / FOND / HDDL
               +--> ggen-marketplace prior art
               +--> ggen manufacture
               +--> GymAct rehearsal
               +--> ash_kudzu / ash_a2a external capability
               +--> sJira durable work
               +--> LifeGym / GodsLaw / ZOE Marketplace domains
               +--> XaaS delivery
               |
               v
            BRCE request
               |
          authorize / refuse
               |
               v
              DO
               |
               v
receipt + outcome observation
        |
        +--> wasm4pm / OCEL / conformance
        +--> sJira repair work
        +--> ggen-marketplace reusable pack
        +--> AutoFDE/GymAct falsifier + benchmark
        +--> next OSIRIS event
~~~

The endpoint is not a permanently smarter LLM companion. It is an **LLM-retiring companion runtime**: recurrence becomes rules, schemas, planners, generated code, or verified policies, so the next OSIRIS turn needs less general inference.

## Falsifiers in this PR

The vertical slice fails if any of these is possible:

- stale observation supports spoken factual output;
- an action candidate bypasses BRCERequest;
- action is manufactured with no admitted trigger;
- a sole DO_NOT action trigger still yields a request;
- low-priority overflow evicts a higher-priority event;
- consumed events silently survive compaction;
- identical admitted input and decision produce different receipt IDs;
- OSIRIS introduces a direct LLM/provider dependency.

tests/companion/test_osiris.py exercises these boundaries without an LLM, network, microphone, or production actuation. Passing it establishes the bounded Python kernel only.

## Next manufacture

Connect one real audio path and one real BRCE sandbox capability:

~~~
microphone -> STT -> voice.user Event -> OSIRIS
OSIRIS speech -> TTS
OSIRIS action -> BRCE sandbox -> receipt -> Observation/Event -> OSIRIS
~~~

Record that session as OCEL and run GymAct/AutoFDE cases for interruption, stale state, speech/action disagreement, preemption, recovery, and receipt replay. Once recurrent voice decisions are visible in those traces, IEC can select them for formalization and retirement.
