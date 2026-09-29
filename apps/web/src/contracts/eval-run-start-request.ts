/* Generated from contracts/eval-run-start-request.schema.json. Do not edit by hand. */

export type Adapter = string;
export type Requiremodelpinning = boolean;

/**
 * What a caller may choose when starting an eval run (G-05 W5).
 *
 * Three fields, and what is *absent* matters as much as what is here.
 *
 * ``adapter`` is a **name**, not an endpoint or a credential. The server resolves
 * it through ``adapters.agents.adapter_for``, whose ``BY_NAME`` is the configured
 * allowlist, so a caller can pick one of the platform's four CLIs and nothing
 * else. A request that could name a URL would let the caller point this route --
 * which spends money -- at a host of their choosing.
 *
 * ``componentVersions`` is part of the run's identity: "the agent scored 72%"
 * means nothing without which prompt, context and model produced it. It is
 * bounded, and the three keys the service fills in itself are **refused**:
 * ``run_suite`` merges them with ``setdefault``, so a caller who sent
 * ``{"adapter": "something-else"}`` would have their own value recorded as the
 * identity of the run. Refusing them is the only place that can be stopped
 * without changing the service's signature.
 *
 * ``requireModelPinning`` defaults to **true**, which is the service's own
 * default: a score from an adapter that cannot say which model build produced it
 * is not reproducible. Passing false is allowed and is recorded on the run
 * (``modelPinned: "false"``) rather than merely decided at the call site.
 */
export interface EvalRunStartRequest {
  adapter: Adapter;
  componentVersions?: Componentversions;
  requireModelPinning?: Requiremodelpinning;
}
export interface Componentversions {
  [k: string]: string;
}
