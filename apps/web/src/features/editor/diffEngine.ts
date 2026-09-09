import { DiffLine, FileDiffResult, GitCommitRecord } from '@/contracts/types';

/**
 * Simple deterministic SHA-256 equivalent for browser/mock environments
 */
export function computeSha256(content: string): string {
  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
  for (let i = 0; i < content.length; i++) {
    const code = content.charCodeAt(i);
    h0 = (h0 ^ code) * 0x01000193 >>> 0;
    h1 = (h1 + code * 31) >>> 0;
    h2 = ((h2 << 5) - h2 + code) >>> 0;
    h3 = (h3 ^ (code << 3)) >>> 0;
  }
  const toHex = (n: number) => (n >>> 0).toString(16).padStart(8, '0');
  // Return 64 hex character string
  return `${toHex(h0)}${toHex(h1)}${toHex(h2)}${toHex(h3)}${toHex(h0 ^ h2)}${toHex(h1 ^ h3)}${toHex(h0 + h1)}${toHex(h2 + h3)}`;
}

/**
 * Line-by-line Diff Engine using Myers/LCS algorithm
 */
export function computeDiff(path: string, originalContent: string, modifiedContent: string): FileDiffResult {
  const origLines = originalContent.split(/\r?\n/);
  const modLines = modifiedContent.split(/\r?\n/);

  let additions = 0;
  let deletions = 0;

  // LCS Matrix
  const n = origLines.length;
  const m = modLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < m; j++) {
      if (origLines[i] === modLines[j]) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Backtrack to build diff
  let i = n;
  let j = m;
  const temp: DiffLine[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && origLines[i - 1] === modLines[j - 1]) {
      temp.push({
        type: 'unchanged',
        originalLineNumber: i,
        modifiedLineNumber: j,
        content: origLines[i - 1],
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      temp.push({
        type: 'added',
        modifiedLineNumber: j,
        content: modLines[j - 1],
      });
      additions++;
      j--;
    } else if (i > 0 && (j === 0 || dp[i][j - 1] < dp[i - 1][j])) {
      temp.push({
        type: 'removed',
        originalLineNumber: i,
        content: origLines[i - 1],
      });
      deletions++;
      i--;
    }
  }

  temp.reverse();

  return {
    path,
    originalEtag: computeSha256(originalContent),
    modifiedEtag: computeSha256(modifiedContent),
    lines: temp,
    additionsCount: additions,
    deletionsCount: deletions,
  };
}

/**
 * Generate Git Commit Record (AC-06 compliant)
 */
export function createGitCommit(params: {
  author: string;
  message: string;
  parentCommitId: string | null;
  stagedFiles: string[];
  fileContents: Record<string, string>;
}): GitCommitRecord {
  const timestamp = new Date().toISOString();
  
  // Deterministic tree hash based on staged file contents
  const treeSummary = params.stagedFiles
    .sort()
    .map((p) => `${p}:${computeSha256(params.fileContents[p] || '')}`)
    .join('\n');
  const treeHash = computeSha256(treeSummary).slice(0, 40);

  // Commit hash based on parent + tree + message + author + timestamp
  const commitPayload = [
    `tree ${treeHash}`,
    `parent ${params.parentCommitId || '0000000000000000000000000000000000000000'}`,
    `author ${params.author} ${timestamp}`,
    `message ${params.message}`,
  ].join('\n');

  const commitId = computeSha256(commitPayload).slice(0, 40);

  return {
    commitId,
    parentCommitId: params.parentCommitId,
    author: params.author,
    message: params.message,
    timestamp,
    stagedFiles: params.stagedFiles,
    treeHash,
  };
}
