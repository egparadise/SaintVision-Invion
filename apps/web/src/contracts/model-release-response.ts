/* Generated from contracts/model-release-response.schema.json. Do not edit by hand. */

export type Contentsha256 = string;
export type Modelid = string;
export type Modelversionid = string;
export type Stage = 'released';
export type Version = string;

/**
 * The released version, echoed back by identity.
 *
 * ``stage`` is a literal rather than a free string: the only state this
 * response can describe is the one the route just established, so a future
 * change that returns a different stage under the same type breaks the
 * contract instead of quietly widening it.
 *
 * Python field names avoid the ``model_`` prefix because Pydantic reserves
 * that namespace; the wire names are the aliases.
 */
export interface ModelReleaseResponse {
  contentSha256: Contentsha256;
  modelId: Modelid;
  modelVersionId: Modelversionid;
  stage: Stage;
  version: Version;
}
