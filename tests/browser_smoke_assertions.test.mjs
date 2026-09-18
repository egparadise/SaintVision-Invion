// Execute the actual smoke assertion lines without importing the network runner.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source = readFileSync(new URL('../tools/run_browser_smoke.mjs', import.meta.url), 'utf8');
const lines = source.split('\n').filter(line => line.includes("assert('All shards confirm"));
assert.equal(lines.length, 2, 'Both production shard assertions must be exercised');
const valid = () => ({ physicallyStopped: true, outputHash: 'sha256:synthetic' });
function evaluate(items) {
  const result = [];
  vm.runInNewContext(lines.join('\n'), { shData: { items }, assert: (title, ok) => result.push(Boolean(ok)) });
  return result;
}
for (const [name, items] of [
  ['absent', undefined], ['null', null], ['empty', []], ['object', {}],
  ['array-like', { length: 2 }], ['one', [valid()]],
  ['three', [valid(), valid(), valid()]], ['null row', [null, valid()]],
]) {
  test(`both claims reject ${name} input`, () => assert.deepEqual(evaluate(items), [false, false]));
}
test('two valid shard observations pass', () => assert.deepEqual(evaluate([valid(), valid()]), [true, true]));
test('stop rejection does not become hash rejection', () => assert.deepEqual(evaluate([{ ...valid(), physicallyStopped: false }, valid()]), [false, true]));
test('missing output hash fails independently', () => assert.deepEqual(evaluate([{ physicallyStopped: true }, valid()]), [true, false]));
test('baseline empty-array expression exposes the original gap', () => {
  assert.equal(Boolean([] && [].every(s => s.physicallyStopped)), true);
  assert.deepEqual(evaluate([]), [false, false]);
});
