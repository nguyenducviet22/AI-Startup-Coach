# Coaching-Harness Spec — AI Startup Coach

**Version:** 1.0
**Purpose:** Technical spec to hand off to Codex (via the `hs:brainstorm → hs:plan → hs:build → hs:code-review → hs:ship` workflow) for building the backend of AI Startup Coach.

---

## 1. Overview

`coaching-harness` is the scaffolding layer wrapped around the LLM. It is responsible for:
- Tracking each student's progress through the startup journey (stage state)
- Providing tools to read/write data (DB)
- Providing skills (domain content) so the LLM generates properly structured documents
- Orchestrating the loop: receive message → load context → call LLM → handle tool calls → persist results → respond

```
coaching-harness + LLM (OpenAI API) = Coaching Agent
```

---

## 2. Overall Architecture

```
┌──────────────┐
│   Frontend    │
└──────┬───────┘
       │ REST / WebSocket
┌──────▼─────────────────────────────┐
│  FastAPI Backend                     │
│  ┌────────────────────────────────┐ │
│  │ API Layer (routes)               │ │
│  └──────────┬───────────────────────┘ │
│  ┌──────────▼───────────────────────┐ │
│  │ Agent Orchestrator                │ │  ← coaching-harness core
│  │  - Stage manager                  │ │
│  │  - Context builder                │ │
│  │  - Tool dispatcher                │ │
│  └──────────┬───────────────────────┘ │
│  ┌──────────▼───────────────────────┐ │
│  │ Tool Functions                    │ │
│  └──────────┬───────────────────────┘ │
│  ┌──────────▼───────────────────────┐ │
│  │ Skill Content (prompt templates)  │ │
│  └──────────┬───────────────────────┘ │
│  ┌──────────▼───────────────────────┐ │
│  │ State/Memory Service              │ │
│  └──────────┬───────────────────────┘ │
└─────────────┼─────────────────────────┘
              │
       ┌──────▼───────┐
       │ PostgreSQL    │
       └───────────────┘
```

---

## 3. Stage State Machine

| # | Stage code | Name | Entry condition | Readiness to advance |
|---|---|---|---|---|
| 1 | `idea` | Idea formation | Session start | Problem, target customer, and rough solution identified |
| 2 | `lean_canvas` | Lean Canvas | Stage 1 complete | All 9 required fields filled (see 5.1) |
| 3 | `bmc` | Business Model Canvas | Stage 2 complete | All 9 BMC blocks filled |
| 4 | `swot` | SWOT Analysis | Stage 3 complete | All 4 groups (S/W/O/T) populated, ≥2 items each |
| 5 | `product_plan` | Product development plan | Stage 4 complete | MVP scope + milestone timeline defined |
| 6 | `marketing` | Marketing strategy | Stage 5 complete | Channels, key messages, budget estimate defined |
| 7 | `funding` | Basic fundraising guidance | Stage 6 complete | Pitch outline + rough valuation guidance provided |
| 8 | `completed` | Completed | Stage 7 complete | — |

**Stage transition rules:**
- The agent **never auto-advances** the stage. After each turn, the orchestrator calls `check_stage_readiness` (section 5.6) to evaluate readiness — if met, it asks the student for confirmation before advancing (e.g. "You have enough info for a Lean Canvas draft — shall I generate it?").
- Students can **go back to a previous stage** to edit at any time (this is not a rigid one-way flow).

---

## 4. Database Schema

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Startup projects (a user may have multiple startups)
CREATE TABLE startups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) NOT NULL,
    name VARCHAR(255),
    current_stage VARCHAR(50) NOT NULL DEFAULT 'idea',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Lean Canvas (versioned — keeps edit history)
CREATE TABLE lean_canvas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    problem TEXT,
    solution TEXT,
    unique_value_proposition TEXT,
    unfair_advantage TEXT,
    customer_segments TEXT,
    key_metrics TEXT,
    channels TEXT,
    cost_structure TEXT,
    revenue_streams TEXT,
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Business Model Canvas
CREATE TABLE bmc (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    key_partners TEXT,
    key_activities TEXT,
    key_resources TEXT,
    value_propositions TEXT,
    customer_relationships TEXT,
    channels TEXT,
    customer_segments TEXT,
    cost_structure TEXT,
    revenue_streams TEXT,
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- SWOT
CREATE TABLE swot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    strengths JSONB,      -- array of strings
    weaknesses JSONB,
    opportunities JSONB,
    threats JSONB,
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Product roadmap
CREATE TABLE product_plan (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    mvp_scope TEXT,
    features JSONB,        -- [{name, priority, effort}, ...]
    timeline JSONB,        -- [{milestone, target_date}, ...]
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Marketing strategy
CREATE TABLE marketing_strategy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    target_audience TEXT,
    channels JSONB,
    key_messages TEXT,
    budget_estimate TEXT,
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Funding guide
CREATE TABLE funding_guide (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    pitch_outline JSONB,     -- [{slide_title, content}, ...]
    valuation_notes TEXT,
    funding_stage_recommendation VARCHAR(100),
    version INT NOT NULL DEFAULT 1,
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Conversation history
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id UUID REFERENCES startups(id) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) NOT NULL,
    role VARCHAR(20) NOT NULL,   -- 'user' | 'assistant' | 'tool'
    content TEXT NOT NULL,
    tool_call_data JSONB,        -- stores tool_calls if any
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Design notes:**
- Each document table (`lean_canvas`, `bmc`, `swot`, ...) uses the `version` + `is_current` pattern — when a student edits, insert a new row instead of UPDATE, preserving the evolution history of the idea (genuine educational value for the student).
- `chat_messages.tool_call_data` supports debugging/auditing what tools the agent called.

---

## 5. Tool Definitions

Tools follow the OpenAI function-calling standard (`type: function`). Below are summarized schemas (use full JSON Schema during actual implementation).

### 5.1 `generate_lean_canvas`
```json
{
  "name": "generate_lean_canvas",
  "description": "Create or update the Lean Canvas based on information gathered from the student",
  "parameters": {
    "type": "object",
    "properties": {
      "problem": {"type": "string"},
      "solution": {"type": "string"},
      "unique_value_proposition": {"type": "string"},
      "unfair_advantage": {"type": "string"},
      "customer_segments": {"type": "string"},
      "key_metrics": {"type": "string"},
      "channels": {"type": "string"},
      "cost_structure": {"type": "string"},
      "revenue_streams": {"type": "string"}
    },
    "required": ["problem", "solution", "customer_segments", "unique_value_proposition"]
  }
}
```
*Note:* the 4 required fields are the minimum for a draft; remaining fields can be left blank, and the agent should proactively ask about them in later turns.

### 5.2 `generate_bmc`
Same pattern as above, using the 9 standard Business Model Canvas blocks (Osterwalder).

### 5.3 `generate_swot`
```json
{
  "name": "generate_swot",
  "parameters": {
    "type": "object",
    "properties": {
      "strengths": {"type": "array", "items": {"type": "string"}},
      "weaknesses": {"type": "array", "items": {"type": "string"}},
      "opportunities": {"type": "array", "items": {"type": "string"}},
      "threats": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["strengths", "weaknesses", "opportunities", "threats"]
  }
}
```

### 5.4 `generate_product_plan`
```json
{
  "name": "generate_product_plan",
  "parameters": {
    "type": "object",
    "properties": {
      "mvp_scope": {"type": "string"},
      "features": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "priority": {"type": "string", "enum": ["must-have", "should-have", "nice-to-have"]},
            "effort": {"type": "string", "enum": ["low", "medium", "high"]}
          }
        }
      },
      "timeline": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "milestone": {"type": "string"},
            "target_date": {"type": "string"}
          }
        }
      }
    },
    "required": ["mvp_scope", "features"]
  }
}
```

### 5.5 `generate_marketing_strategy`
```json
{
  "name": "generate_marketing_strategy",
  "parameters": {
    "type": "object",
    "properties": {
      "target_audience": {"type": "string"},
      "channels": {"type": "array", "items": {"type": "string"}},
      "key_messages": {"type": "string"},
      "budget_estimate": {"type": "string"}
    },
    "required": ["target_audience", "channels"]
  }
}
```

### 5.6 `check_stage_readiness`
```json
{
  "name": "check_stage_readiness",
  "description": "Evaluate whether the current information is sufficient to advance to the next stage",
  "parameters": {
    "type": "object",
    "properties": {
      "current_stage": {"type": "string"},
      "missing_fields": {"type": "array", "items": {"type": "string"}},
      "ready": {"type": "boolean"}
    },
    "required": ["current_stage", "ready"]
  }
}
```
*Implementation note:* this can be **fully LLM-judged** (no complex custom logic needed) — the model returns JSON per this schema, and the harness simply reads it to decide whether to prompt the student for stage-advance confirmation.

### 5.7 `save_progress` / `get_progress` (internal, not exposed to the LLM directly)
These are internal harness functions, invoked automatically by the orchestrator after every successful tool call — **not tools the LLM actively calls**, but default orchestrator behavior (persist to DB + update `current_stage` when applicable).

### 5.8 `generate_funding_guide`
```json
{
  "name": "generate_funding_guide",
  "parameters": {
    "type": "object",
    "properties": {
      "pitch_outline": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "slide_title": {"type": "string"},
            "content": {"type": "string"}
          }
        }
      },
      "valuation_notes": {"type": "string"},
      "funding_stage_recommendation": {"type": "string"}
    },
    "required": ["pitch_outline"]
  }
}
```

---

## 6. Skill Content (system prompt per stage)

Each stage has its own skill file (markdown), loaded into the system prompt based on the startup's `current_stage`. Suggested folder structure:

```
/skills
  ├── idea.md
  ├── lean_canvas.md
  ├── bmc.md
  ├── swot.md
  ├── product_plan.md
  ├── marketing.md
  └── funding.md
```

**Each skill file should include:**
1. The underlying framework definition (e.g. what the 9 Lean Canvas blocks are)
2. A sample set of discovery questions (so the agent asks focused questions instead of rambling)
3. Good vs. bad examples (helps the model calibrate output quality)
4. Common student mistakes the agent should proactively flag (e.g. vague value proposition, overly broad target customer)
5. Criteria for considering the information "sufficient" to advance to the next stage

**Example skeleton for `lean_canvas.md`:**
```markdown
# Skill: Lean Canvas

## Role
You are guiding the student through building a Lean Canvas — a 9-block
tool for quickly validating a startup idea, focused on the biggest risk first.

## Discovery order (ask in groups, not all at once)
1. Problem — What problem is the student solving? Top 3 pain points?
2. Customer Segments — Who feels this problem most acutely? (a specific early adopter, not "everyone")
3. Solution — Rough solution for each pain point from step 1
4. Unique Value Proposition — One sentence explaining why choose you over alternatives
... (continue for the remaining 5 blocks)

## Common warnings
- Customer segment too broad ("everyone who uses a smartphone") → ask to narrow it down
- Solution defined before Problem (thinking of the solution before validating the problem) → nudge the student back to validating the problem first

## Criteria for a draft canvas
Has a specific problem + specific customer segment + rough solution + clear UVP.
Remaining blocks can be drafted tentatively by the agent, student refines later.
```

---

## 7. Agent Orchestrator — Processing Flow

```python
async def handle_message(startup_id: str, user_message: str) -> str:
    # 1. Load state
    startup = await get_startup(startup_id)
    history = await get_recent_messages(startup_id, limit=20)
    current_doc = await get_current_stage_document(startup_id, startup.current_stage)

    # 2. Build context
    skill_content = load_skill(startup.current_stage)
    system_prompt = build_system_prompt(startup, skill_content, current_doc)

    # 3. Call LLM with tools
    messages = [{"role": "system", "content": system_prompt}, *history,
                {"role": "user", "content": user_message}]
    response = await openai_client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        tools=get_tools_for_stage(startup.current_stage),
    )

    assistant_msg = response.choices[0].message

    # 4. Handle tool calls
    if assistant_msg.tool_calls:
        for call in assistant_msg.tool_calls:
            result = await execute_tool(call.function.name, call.function.arguments, startup_id)
            messages.append(tool_result_message(call.id, result))

            if call.function.name == "check_stage_readiness":
                result_data = json.loads(result)
                if result_data.get("ready"):
                    await maybe_advance_stage(startup_id, result_data)

        # call the LLM again to produce a natural response based on tool results
        response = await openai_client.chat.completions.create(
            model="gpt-4.1", messages=messages
        )
        assistant_msg = response.choices[0].message

    # 5. Persist
    await save_message(startup_id, "user", user_message)
    await save_message(startup_id, "assistant", assistant_msg.content)

    return assistant_msg.content
```

**Required error-handling rules:**
- Tool call returns arguments that don't match the schema → validate with Pydantic; on failure, return a clear error back to the LLM (don't crash) so it can self-correct on the next call
- OpenAI API timeout/rate limit → retry up to 2 times with backoff, then return a friendly error message to the student
- `history` exceeds context limit → truncate the oldest messages, keeping the system prompt + the N most recent messages (N configurable, default 20)

---

## 8. API Endpoints (proposed)

| Method | Path | Description |
|---|---|---|
| POST | `/startups` | Create a new startup for a user |
| GET | `/startups/{id}` | Get startup info + current stage |
| POST | `/startups/{id}/chat` | Send a message, receive the agent's response |
| GET | `/startups/{id}/documents/{doc_type}` | Get the current document (canvas, swot, etc.) |
| GET | `/startups/{id}/documents/{doc_type}/history` | Get the version history of a document |
| POST | `/startups/{id}/advance-stage` | Manually confirm advancing to the next stage (when the student wants to proceed even if not fully "ready") |
| PATCH | `/startups/{id}/stage` | Go back to a previous stage to edit |

---

## 9. Acceptance Criteria (for review once Codex finishes building)

- [ ] The agent never auto-advances the stage without student confirmation
- [ ] Every document creation/edit (canvas, SWOT, etc.) creates a new version, never loses prior history
- [ ] A student returning after several days gets the correct prior context loaded, without having to repeat themselves
- [ ] A tool call with schema-mismatched arguments does not crash the system; the agent self-recovers on the next turn
- [ ] Each stage only exposes the skill content + tools relevant to that stage (no cross-stage tool noise)
- [ ] At least one end-to-end test case exists covering: idea → lean canvas → bmc (enough to verify the orchestrator works correctly)

---

## 10. Out of Scope for This Spec (not built in the first pass)

- AgentOps (detailed logging, cost tracking, eval sets) — to be built once the core harness is stable
- Detailed auth/permissions — assumed to be handled by a separate auth middleware
- UI rendering for canvases — left to the frontend to decide how to display the returned JSON
