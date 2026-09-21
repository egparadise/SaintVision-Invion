/* Generated from contracts/placement-preview-response.schema.json. Do not edit by hand. */

export type Candidatecount = number;
export type Headroom = number;
export type Hostname = string;
export type Nodeid = string;
export type Cpumillicores = number;
export type Gpudevices = number;
export type Rambytes = number;
export type Candidates = PlacementPreviewCandidateResponse[];
export type Poolid = string;

export interface PlacementPreviewResponse {
  candidateCount: Candidatecount;
  candidates: Candidates;
  poolId: Poolid;
  units: Units;
}
export interface PlacementPreviewCandidateResponse {
  headroom: Headroom;
  hostname: Hostname;
  nodeId: Nodeid;
  spare: PoolResourceAmounts;
}
export interface PoolResourceAmounts {
  cpuMillicores: Cpumillicores;
  gpuDevices: Gpudevices;
  ramBytes: Rambytes;
}
export interface Units {
  [k: string]: string;
}
