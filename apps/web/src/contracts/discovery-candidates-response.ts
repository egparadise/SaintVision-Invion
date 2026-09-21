/* Generated from contracts/discovery-candidates-response.schema.json. Do not edit by hand. */

export type Announcecount = number;
export type Announcementid = string;
export type Claimedcpucores = number;
export type Claimedgpucount = number;
export type Claimedhostname = string;
export type Claimedostype = string;
export type Claimedrambytes = number;
export type Firstseenat = string;
export type Instanceid = string;
export type Lastseenat = string;
export type Sourceip = string;
export type Stale = boolean;
export type State = 'candidate';
export type Verified = false;
export type Items = DiscoveryCandidateResponse[];
export type Note = string;

export interface DiscoveryCandidatesResponse {
  items: Items;
  note: Note;
}
/**
 * One unverified announcement offered for operator admission.
 */
export interface DiscoveryCandidateResponse {
  announceCount: Announcecount;
  announcementId: Announcementid;
  claimedCpuCores: Claimedcpucores;
  claimedGpuCount: Claimedgpucount;
  claimedHostname: Claimedhostname;
  claimedOsType: Claimedostype;
  claimedRamBytes: Claimedrambytes;
  firstSeenAt: Firstseenat;
  instanceId: Instanceid;
  lastSeenAt: Lastseenat;
  sourceIp: Sourceip;
  stale: Stale;
  state: State;
  verified: Verified;
}
